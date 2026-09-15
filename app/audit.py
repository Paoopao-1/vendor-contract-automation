import uuid
from datetime import datetime
from app.db import get_client

# 所有合法操作类型，防止乱传
VALID_ACTIONS = {
    "submit",        # 提交申请
    "update",        # 修改合同
    "approve",       # 审批通过
    "reject",        # 退回/驳回
    "send",          # 发起签署
    "sign",          # 签署完成
    "decline",       # 拒签
    "expire",        # 签署过期
    "archive",       # 归档
    "state_change",  # 状态变更
}

def log(contract_id, operator, action, version=None, detail=""):
    """写一条操作日志。任何一步操作后都应该调用它。"""
    # 边界 1：操作类型必须合法
    if action not in VALID_ACTIONS:
        raise ValueError(f"非法操作类型: {action}")
    # 边界 2：contract_id 不能空
    if not contract_id:
        raise ValueError("contract_id 不能为空")
    # 边界 3：operator 不能空
    if not operator:
        raise ValueError("operator 不能为空")

    conn = get_client()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO audit_logs (id, contract_id, operator, action, version, detail, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), contract_id, operator, action, version, detail, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_logs(contract_id):
    """按时间倒序获取某合同的所有日志。"""
    if not contract_id:
        raise ValueError("contract_id 不能为空")

    conn = get_client()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, contract_id, operator, action, version, detail, created_at
           FROM audit_logs WHERE contract_id = ? ORDER BY created_at DESC""",
        (contract_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]