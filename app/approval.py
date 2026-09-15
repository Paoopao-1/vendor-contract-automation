import uuid
from datetime import datetime
from app.db import get_client
from app.config import APPROVERS
from app.audit import log
from app.validation import validate_schedule_a
from app.state_machine import (
    UNDER_REVIEW, APPROVED_TO_SEND, RETURNED,
    get_status, transition,
)

def _get_current_version(contract_id):
    conn = get_client()
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM contracts WHERE id = ?", (contract_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        raise ValueError(f"合同不存在: {contract_id}")
    return row["version"]

def get_approvals(contract_id, only_valid=True):
    if not contract_id:
        raise ValueError("contract_id 不能为空")
    conn = get_client()
    cursor = conn.cursor()
    if only_valid:
        cursor.execute(
            "SELECT * FROM approvals WHERE contract_id = ? AND is_valid = 1 ORDER BY created_at ASC",
            (contract_id,)
        )
    else:
        cursor.execute(
            "SELECT * FROM approvals WHERE contract_id = ? ORDER BY created_at ASC",
            (contract_id,)
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _upsert_approval(contract_id, approver, version, decision, comment):
    """同一人同一版本只保留一条审批记录（覆盖旧的）。"""
    conn = get_client()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM approvals WHERE contract_id = ? AND approver = ? AND version = ? AND is_valid = 1",
        (contract_id, approver, version)
    )
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            "UPDATE approvals SET decision = ?, comment = ?, created_at = ? WHERE id = ?",
            (decision, comment, datetime.now().isoformat(), existing["id"])
        )
    else:
        cursor.execute(
            "INSERT INTO approvals (id, contract_id, approver, version, decision, comment, is_valid, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            (str(uuid.uuid4()), contract_id, approver, version, decision, comment, datetime.now().isoformat())
        )
    conn.commit()
    conn.close()

def approve(contract_id, approver, comment=""):
    """某审批人审批当前版本。串行审批：法务先，CEO 后。"""
    if approver not in APPROVERS:
        raise ValueError(f"非法审批人: {approver}")
    status = get_status(contract_id)
    if status != UNDER_REVIEW:
        raise ValueError(f"当前状态 {status} 不可审批，必须处于 Under Review")

    version = _get_current_version(contract_id)

    # 串行规则：CEO 必须等法务先批当前版本
    if approver == APPROVERS[1]:  # CEO_Bob
        approvals = get_approvals(contract_id, only_valid=True)
        legal_approved = any(
            a["approver"] == APPROVERS[0]
            and a["version"] == version
            and a["decision"] == "approved"
            for a in approvals
        )
        if not legal_approved:
            raise ValueError("法务尚未审批当前版本，CEO 不能审批")

    _upsert_approval(contract_id, approver, version, "approved", comment)
    log(contract_id, approver, "approve", version, detail=comment or "审批通过")

    # 两人都批同一版本 → 进入 Approved to Send
    if is_fully_approved(contract_id):
        missing = validate_schedule_a(contract_id)
        if missing:
            raise ValueError(f"审批通过但字段仍缺失，无法进入 Approved to Send: {missing}")
        transition(contract_id, APPROVED_TO_SEND, approver, detail="两位审批人同版本通过")
    return True

def reject(contract_id, approver, reason=""):
    """退回修改。"""
    if approver not in APPROVERS:
        raise ValueError(f"非法审批人: {approver}")
    status = get_status(contract_id)
    if status != UNDER_REVIEW:
        raise ValueError(f"当前状态 {status} 不可退回")

    version = _get_current_version(contract_id)
    _upsert_approval(contract_id, approver, version, "rejected", reason)
    log(contract_id, approver, "reject", version, detail=reason or "退回修改")
    transition(contract_id, RETURNED, approver, detail=reason or "退回修改")
    return True

def is_fully_approved(contract_id):
    """两位审批人都在当前版本投了 approved，且审批有效。"""
    version = _get_current_version(contract_id)
    approvals = get_approvals(contract_id, only_valid=True)
    approved_by = {
        a["approver"] for a in approvals
        if a["version"] == version and a["decision"] == "approved"
    }
    return set(APPROVERS).issubset(approved_by)

def can_send_for_signature(contract_id):
    """可发签的条件：状态 = Approved to Send。"""
    return get_status(contract_id) == APPROVED_TO_SEND
