import json
import uuid
from datetime import datetime
from app.db import get_client
from app.audit import log

# 关键字段：一改就版本 +1
CRITICAL_FIELDS = {
    "vendor_name", "vendor_country",
    "platform_share", "vendor_share",
    "revenue_definition", "refund_policy",
    "tax_invoice_party", "pricing_model",
    "settlement_cycle", "currency",
    "signer_name", "signer_email", "signer_authorized",
}

# 非关键字段：改了不升版本
NON_CRITICAL_FIELDS = {
    "vendor_address", "product_name", "business_line",
    "region", "customer_scope", "signer_title",
}

def get_contract_dict(contract_id):
    if not contract_id:
        raise ValueError("contract_id 不能为空")
    conn = get_client()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        raise ValueError(f"合同不存在: {contract_id}")
    return dict(row)

def get_current_version(contract_id):
    return get_contract_dict(contract_id)["version"]



def _save_snapshot(contract_id, version, contract_dict):
    conn = get_client()
    conn.execute(
        "INSERT INTO versions (id, contract_id, version, snapshot, created_at) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), contract_id, version,
         json.dumps(contract_dict, ensure_ascii=False, default=str),
         datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def _invalidate_old_approvals(contract_id, old_version):
    """把旧版本的所有审批标记为失效。"""
    conn = get_client()
    conn.execute(
        "UPDATE approvals SET is_valid = 0 WHERE contract_id = ? AND version = ?",
        (contract_id, old_version)
    )
    conn.commit()
    conn.close()

def bump_version(contract_id, changed_fields, operator):
    """任意字段改了 → 版本 +1，快照，旧审批失效，写日志。
       返回新版本号。"""
    if not operator:
        raise ValueError("operator 不能为空")
    contract = get_contract_dict(contract_id)
    current_version = contract["version"]

    # 校验字段合法性（不是关键判断，是防止非法字段混入）
    is_critical_change(changed_fields)

    new_version = current_version + 1
    conn = get_client()
    conn.execute(
        "UPDATE contracts SET version = ?, updated_at = ? WHERE id = ?",
        (new_version, datetime.now().isoformat(), contract_id)
    )
    conn.commit()
    conn.close()

    _save_snapshot(contract_id, new_version, contract)
    _invalidate_old_approvals(contract_id, current_version)

    log(contract_id, operator, "update", new_version,
        detail=f"字段变更: {', '.join(changed_fields)}，版本 {current_version} -> {new_version}，旧审批失效")
    return new_version

def is_critical_change(changed_fields):
    """当前规则：任意字段变化都视为关键变化，触发版本 +1。
    CRITICAL_FIELDS / NON_CRITICAL_FIELDS 保留，用作合法字段白名单。"""
    if not changed_fields:
        raise ValueError("changed_fields 不能为空")
    allowed = CRITICAL_FIELDS | NON_CRITICAL_FIELDS
    for f in changed_fields:
        if f not in allowed:
            raise ValueError(f"未知字段: {f}")
    return True
def get_version_history(contract_id):
    if not contract_id:
        raise ValueError("contract_id 不能为空")
    conn = get_client()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT version, snapshot, created_at FROM versions WHERE contract_id = ? ORDER BY version ASC",
        (contract_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _normalize(v):
    """把值统一成可比较的形式，避免 0.7 和 '0.7' 被当成不同值。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, str):
        v = v.strip()
        if v == "":
            return None
        try:
            return float(v)
        except ValueError:
            return v
    if isinstance(v, (int, float)):
        return float(v)
    return v

def diff_fields(contract_id, new_values):
    """对比数据库旧值和新值，返回真正发生变化的字段名列表。
    未知字段会报错。全部相同时返回空列表。"""
    if not new_values:
        raise ValueError("new_values 不能为空")
    old = get_contract_dict(contract_id)
    allowed = CRITICAL_FIELDS | NON_CRITICAL_FIELDS
    changed = []
    for field, new_value in new_values.items():
        if field not in allowed:
            raise ValueError(f"未知字段: {field}")
        if _normalize(old.get(field)) != _normalize(new_value):
            changed.append(field)
    return changed