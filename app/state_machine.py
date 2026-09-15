from app.db import get_client
from app.audit import log

# 11 个状态
DRAFT = "Draft"
NEEDS_INFO = "Needs Information"
UNDER_REVIEW = "Under Review"
APPROVED_TO_SEND = "Approved to Send"
SENT_FOR_SIGNATURE = "Sent for Signature"
SIGNED = "Signed"
ACTIVE = "Active"
RETURNED = "Returned"
DECLINED = "Declined"
EXPIRED = "Expired"
SIGNED_UNPAID = "Signed_Unpaid"

ALL_STATUSES = {
    DRAFT, NEEDS_INFO, UNDER_REVIEW, APPROVED_TO_SEND,
    SENT_FOR_SIGNATURE, SIGNED, ACTIVE,
    RETURNED, DECLINED, EXPIRED, SIGNED_UNPAID,
}

# 合法流转表：当前状态 -> 允许流转到的状态集合
TRANSITIONS = {
    DRAFT: {NEEDS_INFO, UNDER_REVIEW},
    NEEDS_INFO: {UNDER_REVIEW},
    UNDER_REVIEW: {RETURNED, APPROVED_TO_SEND},
    RETURNED: {UNDER_REVIEW},
    APPROVED_TO_SEND: {SENT_FOR_SIGNATURE},
    SENT_FOR_SIGNATURE: {SIGNED, DECLINED, EXPIRED},
    DECLINED: {SENT_FOR_SIGNATURE},
    EXPIRED: {SENT_FOR_SIGNATURE},
    SIGNED: {ACTIVE, SIGNED_UNPAID},
    SIGNED_UNPAID: {ACTIVE},
    ACTIVE: set(),
}

def can_transition(from_status, to_status):
    """判断从 from_status 到 to_status 是否合法。"""
    if from_status not in ALL_STATUSES:
        raise ValueError(f"未知的当前状态: {from_status}")
    if to_status not in ALL_STATUSES:
        raise ValueError(f"未知的目标状态: {to_status}")
    return to_status in TRANSITIONS.get(from_status, set())

def get_status(contract_id):
    """查某合同的当前状态。"""
    if not contract_id:
        raise ValueError("contract_id 不能为空")
    conn = get_client()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM contracts WHERE id = ?", (contract_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        raise ValueError(f"合同不存在: {contract_id}")
    return row["status"]

def transition(contract_id, to_status, operator, detail=""):
    """把合同状态从当前状态流转到 to_status，并写日志。"""
    current = get_status(contract_id)

    # 边界 1：非法流转
    if not can_transition(current, to_status):
        raise ValueError(f"非法流转: {current} -> {to_status}")

    # 边界 2：重复流转（同状态）
    if current == to_status:
        raise ValueError(f"合同已处于 {to_status}，无需重复流转")

    conn = get_client()
    cursor = conn.cursor()
    cursor.execute("UPDATE contracts SET status = ? WHERE id = ?", (to_status, contract_id))
    conn.commit()
    conn.close()

    # 自动写日志
    log(contract_id, operator, "state_change", None,
        detail or f"{current} -> {to_status}")
    return to_status