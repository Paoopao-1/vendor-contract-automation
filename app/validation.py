from app.db import get_client
from app.state_machine import DRAFT, NEEDS_INFO

# 所有必填字段（列名 -> 中文名）
REQUIRED_FIELDS = {
    "vendor_name":       "供应商法定名称",
    "vendor_country":    "注册地",
    "vendor_address":    "注册地址",
    "product_name":      "产品/服务名称",
    "business_line":     "业务线",
    "region":            "地域",
    "customer_scope":    "客户范围",
    "pricing_model":     "收费方式",
    "currency":          "币种",
    "revenue_definition": "收入计算口径",
    "platform_share":    "平台分成比例",
    "vendor_share":      "供应商分成比例",
    "settlement_cycle":  "结算周期",
    "refund_policy":     "退款处理",
    "tax_invoice_party": "税务/开票责任",
    "signer_name":       "签字人姓名",
    "signer_title":      "签字人职务",
    "signer_email":      "签字人邮箱",
    "signer_authorized": "签字人授权确认",
}

# 不可自动推断的字段（这些为空时，最严重，必须阻断）
NON_INFERABLE_FIELDS = {
    "platform_share", "vendor_share",
    "revenue_definition",
    "refund_policy",
    "vendor_name",
}

def _is_empty(value):
    """判断字段是否为空：None、空字符串、纯空格都算空。"""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    # signer_authorized=False 不算空，但 None 算空
    return False

def get_contract(contract_id):
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

def validate_schedule_a(contract_id):
    """返回缺失字段的中文名列表。全部齐全返回空列表。"""
    contract = get_contract(contract_id)
    missing = []
    for field, label in REQUIRED_FIELDS.items():
        if _is_empty(contract.get(field)):
            missing.append(label)
    return missing

def is_blocked(contract_id):
    """有必填字段缺失，就视为阻断。"""
    return len(validate_schedule_a(contract_id)) > 0

def check_and_update_status(contract_id, operator="system"):
    """如果缺字段且当前是 Draft，自动变成 Needs Information。"""
    contract = get_contract(contract_id)
    missing = validate_schedule_a(contract_id)
    if missing and contract["status"] == DRAFT:
        from app.state_machine import transition
        transition(contract_id, NEEDS_INFO, operator,
                   detail=f"缺字段: {', '.join(missing)}")
    return missing