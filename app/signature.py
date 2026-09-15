import uuid
from datetime import datetime
from app.db import get_client
from app.audit import log
from app.state_machine import (
    APPROVED_TO_SEND, SENT_FOR_SIGNATURE, SIGNED, ACTIVE,
    DECLINED, EXPIRED,
    get_status, transition,
)
from app.approval import can_send_for_signature

# 签署完成后应归档的 5 项证据
ARCHIVE_ITEMS = [
    "contract_preview",   # 合同 PDF / HTML 预览
    "approvals",          # 审批记录
    "signature_cert",     # 签署证书
    "schedule_a",         # Schedule A 快照
    "audit_logs",         # 操作日志
]

def send_for_signature(contract_id, operator):
    """发起签署。只有 Approved to Send 才能发。"""
    if not operator:
        raise ValueError("operator 不能为空")
    status = get_status(contract_id)
    if status != APPROVED_TO_SEND:
        raise ValueError(f"当前状态 {status} 不可发起签署，必须处于 Approved to Send")

    conn = get_client()
    cursor = conn.cursor()
    cursor.execute("SELECT signer_name, signer_email FROM contracts WHERE id = ?", (contract_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"合同不存在: {contract_id}")
    if not row["signer_name"] or not row["signer_email"]:
        conn.close()
        raise ValueError("签署人信息不完整，无法发起签署")

    sig_id = str(uuid.uuid4())
    cursor.execute(
        """INSERT INTO signatures (id, contract_id, signer_name, signer_email, cc, status, sent_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (sig_id, contract_id, row["signer_name"], row["signer_email"],
         "legal@company.com", "Sent", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    transition(contract_id, SENT_FOR_SIGNATURE, operator, detail="已发起电子签")
    return sig_id

def _update_signature_status(contract_id, new_status):
    conn = get_client()
    conn.execute(
        "UPDATE signatures SET status = ?, signed_at = ? WHERE contract_id = ? AND status = 'Sent'",
        (new_status, datetime.now().isoformat(), contract_id)
    )
    conn.commit()
    conn.close()

def mock_sign(contract_id, operator="signer"):
    """模拟签署完成 → Signed → Active。"""
    if get_status(contract_id) != SENT_FOR_SIGNATURE:
        raise ValueError("只有 Sent for Signature 状态才能签署")
    _update_signature_status(contract_id, "Signed")
    transition(contract_id, SIGNED, operator, detail="签署人完成签署")

    # 归档证据清单
    conn = get_client()
    conn.execute(
        "UPDATE signatures SET archive_files = ? WHERE contract_id = ?",
        (",".join(ARCHIVE_ITEMS), contract_id)
    )
    conn.commit()
    conn.close()

    log(contract_id, operator, "sign", None, detail="签署完成")
    transition(contract_id, ACTIVE, operator, detail="合同已归档，进入 Active")
    return True

def mock_decline(contract_id, reason="", operator="signer"):
    """模拟拒签。"""
    if get_status(contract_id) != SENT_FOR_SIGNATURE:
        raise ValueError("只有 Sent for Signature 状态才能拒签")
    _update_signature_status(contract_id, "Declined")
    log(contract_id, operator, "decline", None, detail=reason or "签署人拒签")
    transition(contract_id, DECLINED, operator, detail=reason or "签署人拒签")
    return True

def mock_expire(contract_id, operator="system"):
    """模拟签署过期。"""
    if get_status(contract_id) != SENT_FOR_SIGNATURE:
        raise ValueError("只有 Sent for Signature 状态才能过期")
    _update_signature_status(contract_id, "Expired")
    log(contract_id, operator, "expire", None, detail="签署链接过期")
    transition(contract_id, EXPIRED, operator, detail="签署链接过期")
    return True

def get_signature(contract_id):
    if not contract_id:
        raise ValueError("contract_id 不能为空")
    conn = get_client()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signatures WHERE contract_id = ? ORDER BY sent_at DESC LIMIT 1", (contract_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_archive_files(contract_id):
    """返回签署完成后应归档的 5 项证据。"""
    sig = get_signature(contract_id)
    if sig is None:
        raise ValueError("尚未发起签署")
    if sig["status"] != "Signed":
        raise ValueError("尚未完成签署，无法归档")
    return ARCHIVE_ITEMS