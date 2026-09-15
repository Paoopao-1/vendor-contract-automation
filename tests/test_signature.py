import uuid
from app.db import get_client
from app.approval import approve
from app.signature import (
    send_for_signature, mock_sign, mock_decline, mock_expire,
    get_signature, get_archive_files, ARCHIVE_ITEMS,
)
from app.config import APPROVERS
from app.state_machine import (
    UNDER_REVIEW, APPROVED_TO_SEND, SIGNED, ACTIVE,
    SENT_FOR_SIGNATURE, DECLINED, EXPIRED, DRAFT,
    get_status, transition,
)

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

def make_contract(status=UNDER_REVIEW):
    cid = str(uuid.uuid4())
    cols = ["id", "status", "version"] + list(FULL_DATA.keys())
    vals = [cid, status, 1] + list(FULL_DATA.values())
    placeholders = ",".join(["?"] * len(cols))
    conn = get_client()
    conn.execute(f"INSERT INTO contracts ({','.join(cols)}) VALUES ({placeholders})", vals)
    conn.commit()
    conn.close()
    return cid

def approve_both(cid):
    approve(cid, APPROVERS[0], "ok")
    approve(cid, APPROVERS[1], "ok")

def test_cannot_send_when_not_approved():
    cid = make_contract(UNDER_REVIEW)
    try:
        send_for_signature(cid, "Alice")
        assert False
    except ValueError as e:
        assert "不可发起签署" in str(e)
    print("✅ test_cannot_send_when_not_approved 通过")

def test_send_after_approved():
    cid = make_contract()
    approve_both(cid)
    send_for_signature(cid, "Alice")
    assert get_status(cid) == SENT_FOR_SIGNATURE
    assert get_signature(cid)["status"] == "Sent"
    print("✅ test_send_after_approved 通过")

def test_mock_sign_goes_active():
    cid = make_contract()
    approve_both(cid)
    send_for_signature(cid, "Alice")
    mock_sign(cid)
    assert get_status(cid) == ACTIVE
    print("✅ test_mock_sign_goes_active 通过")

def test_mock_decline():
    cid = make_contract()
    approve_both(cid)
    send_for_signature(cid, "Alice")
    mock_decline(cid, "不同意")
    assert get_status(cid) == DECLINED
    print("✅ test_mock_decline 通过")

def test_mock_expire():
    cid = make_contract()
    approve_both(cid)
    send_for_signature(cid, "Alice")
    mock_expire(cid)
    assert get_status(cid) == EXPIRED
    print("✅ test_mock_expire 通过")

def test_archive_files_after_sign():
    cid = make_contract()
    approve_both(cid)
    send_for_signature(cid, "Alice")
    mock_sign(cid)
    files = get_archive_files(cid)
    assert files == ARCHIVE_ITEMS
    print("✅ test_archive_files_after_sign 通过")

def test_archive_before_sign_raises():
    cid = make_contract()
    approve_both(cid)
    send_for_signature(cid, "Alice")
    try:
        get_archive_files(cid)
        assert False
    except ValueError as e:
        assert "尚未完成签署" in str(e)
    print("✅ test_archive_before_sign_raises 通过")

def test_decline_then_resend():
    cid = make_contract()
    approve_both(cid)
    send_for_signature(cid, "Alice")
    mock_decline(cid)
    assert get_status(cid) == DECLINED
    # Declined 可以重新发起签署（但要先回到 Approved to Send 或直接从 Declined 重新发）
    # 目前 state_machine 允许 Declined -> Sent for Signature
    transition(cid, SENT_FOR_SIGNATURE, "Alice", "重新发起")
    assert get_status(cid) == SENT_FOR_SIGNATURE
    print("✅ test_decline_then_resend 通过")

if __name__ == "__main__":
    test_cannot_send_when_not_approved()
    test_send_after_approved()
    test_mock_sign_goes_active()
    test_mock_decline()
    test_mock_expire()
    test_archive_files_after_sign()
    test_archive_before_sign_raises()
    test_decline_then_resend()
    print("\n🎉 signature 全部测试通过！")