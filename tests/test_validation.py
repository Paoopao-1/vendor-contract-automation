import uuid
from app.db import get_client
from app.validation import (
    validate_schedule_a, is_blocked, check_and_update_status,
)
from app.state_machine import DRAFT, NEEDS_INFO, get_status

FULL_DATA = {
    "vendor_name": "Singapore Cloud Pte Ltd",
    "vendor_country": "Singapore",
    "vendor_address": "1 Marina Blvd",
    "product_name": "API 数据服务",
    "business_line": "SaaS",
    "region": "东南亚",
    "customer_scope": "SMB",
    "pricing_model": "按量计费",
    "currency": "USD",
    "revenue_definition": "按客户实际使用量",
    "platform_share": 0.7,
    "vendor_share": 0.3,
    "settlement_cycle": "月结30天",
    "refund_policy": "供应商承担",
    "tax_invoice_party": "供应商开票",
    "signer_name": "张三",
    "signer_title": "COO",
    "signer_email": "zhang@example.com",
    "signer_authorized": 1,
}

def make_contract(overrides=None, status=DRAFT):
    data = dict(FULL_DATA)
    if overrides:
        data.update(overrides)
    cid = str(uuid.uuid4())
    cols = ["id", "status", "version"] + list(data.keys())
    vals = [cid, status, 1] + list(data.values())
    placeholders = ",".join(["?"] * len(cols))
    conn = get_client()
    conn.execute(f"INSERT INTO contracts ({','.join(cols)}) VALUES ({placeholders})", vals)
    conn.commit()
    conn.close()
    return cid

def test_all_fields_present():
    cid = make_contract()
    assert validate_schedule_a(cid) == []
    assert is_blocked(cid) is False
    print("✅ test_all_fields_present 通过")

def test_missing_share():
    cid = make_contract({"platform_share": None})
    missing = validate_schedule_a(cid)
    assert "平台分成比例" in missing
    assert is_blocked(cid) is True
    print("✅ test_missing_share 通过")

def test_missing_refund():
    cid = make_contract({"refund_policy": ""})
    assert "退款处理" in validate_schedule_a(cid)
    print("✅ test_missing_refund 通过")

def test_whitespace_only():
    cid = make_contract({"vendor_name": "   "})
    assert "供应商法定名称" in validate_schedule_a(cid)
    print("✅ test_whitespace_only 通过")

def test_auto_status_change():
    cid = make_contract({"revenue_definition": None})
    check_and_update_status(cid, "Alice")
    assert get_status(cid) == NEEDS_INFO
    print("✅ test_auto_status_change 通过")

def test_no_change_when_complete():
    cid = make_contract()
    missing = check_and_update_status(cid, "Alice")
    assert missing == []
    assert get_status(cid) == DRAFT
    print("✅ test_no_change_when_complete 通过")

if __name__ == "__main__":
    test_all_fields_present()
    test_missing_share()
    test_missing_refund()
    test_whitespace_only()
    test_auto_status_change()
    test_no_change_when_complete()
    print("\n🎉 validation 全部测试通过！")