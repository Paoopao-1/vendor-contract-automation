import uuid
from app.db import get_client
from app.approval import (
    approve, reject, is_fully_approved, can_send_for_signature,
    get_approvals,
)
from app.versioning import bump_version
from app.state_machine import (
    DRAFT, UNDER_REVIEW, APPROVED_TO_SEND, RETURNED,
    get_status, transition,
)
from app.config import APPROVERS

LEGAL = APPROVERS[0]   # Legal_Alice
CEO = APPROVERS[1]     # CEO_Bob

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

def make_contract(status=UNDER_REVIEW, overrides=None):
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

def test_ceo_before_legal_blocked():
    """串行规则：法务没批，CEO 不能批。"""
    cid = make_contract()
    try:
        approve(cid, CEO, "ok")
        assert False, "应该抛异常"
    except ValueError as e:
        assert "法务尚未审批" in str(e)
    assert is_fully_approved(cid) is False
    print("✅ test_ceo_before_legal_blocked 通过")

def test_single_legal_approval_not_enough():
    cid = make_contract()
    approve(cid, LEGAL, "ok")
    assert is_fully_approved(cid) is False
    assert get_status(cid) == UNDER_REVIEW
    print("✅ test_single_legal_approval_not_enough 通过")

def test_legal_then_ceo_go_to_approved():
    cid = make_contract()
    approve(cid, LEGAL, "ok")
    approve(cid, CEO, "ok")
    assert is_fully_approved(cid) is True
    assert get_status(cid) == APPROVED_TO_SEND
    print("✅ test_legal_then_ceo_go_to_approved 通过")

def test_illegal_approver():
    cid = make_contract()
    try:
        approve(cid, "Hacker", "")
        assert False
    except ValueError as e:
        assert "非法审批人" in str(e)
    print("✅ test_illegal_approver 通过")

def test_approve_when_not_under_review():
    cid = make_contract(status=DRAFT)
    try:
        approve(cid, LEGAL, "")
        assert False
    except ValueError as e:
        assert "不可审批" in str(e)
    print("✅ test_approve_when_not_under_review 通过")

def test_version_change_invalidates_approval():
    cid = make_contract()
    approve(cid, LEGAL, "ok")
    # 关键字段改了 → 版本 +1，旧审批失效
    bump_version(cid, ["platform_share"], "Alice")
    assert is_fully_approved(cid) is False
    # 此时 CEO 也不能批（法务还没批新版本）
    try:
        approve(cid, CEO, "ok")
        assert False
    except ValueError as e:
        assert "法务尚未审批" in str(e)
    print("✅ test_version_change_invalidates_approval 通过")

def test_reject_goes_to_returned():
    cid = make_contract()
    reject(cid, LEGAL, "退款条款要改")
    assert get_status(cid) == RETURNED
    print("✅ test_reject_goes_to_returned 通过")

def test_can_send_only_when_approved():
    cid = make_contract()
    assert can_send_for_signature(cid) is False
    approve(cid, LEGAL, "ok")
    approve(cid, CEO, "ok")
    assert can_send_for_signature(cid) is True
    print("✅ test_can_send_only_when_approved 通过")

def test_approval_missing_field_blocks():
    cid = make_contract(overrides={"refund_policy": ""})
    approve(cid, LEGAL, "ok")
    try:
        approve(cid, CEO, "ok")
        assert False
    except ValueError as e:
        assert "字段仍缺失" in str(e)
    print("✅ test_approval_missing_field_blocks 通过")

def test_approvals_saved_to_db():
    cid = make_contract()
    approve(cid, LEGAL, "legal ok")
    rows = get_approvals(cid)
    assert len(rows) == 1
    assert rows[0]["approver"] == LEGAL
    print("✅ test_approvals_saved_to_db 通过")

if __name__ == "__main__":
    test_ceo_before_legal_blocked()
    test_single_legal_approval_not_enough()
    test_legal_then_ceo_go_to_approved()
    test_illegal_approver()
    test_approve_when_not_under_review()
    test_version_change_invalidates_approval()
    test_reject_goes_to_returned()
    test_can_send_only_when_approved()
    test_approval_missing_field_blocks()
    test_approvals_saved_to_db()
    print("\n🎉 approval 全部测试通过！")