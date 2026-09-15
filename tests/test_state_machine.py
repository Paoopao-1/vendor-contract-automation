import uuid
from app.db import get_client
from app.state_machine import (
    transition, get_status, can_transition,
    DRAFT, NEEDS_INFO, UNDER_REVIEW, APPROVED_TO_SEND,
    SENT_FOR_SIGNATURE, SIGNED, RETURNED,
)

def make_contract(status=DRAFT):
    """造一笔测试合同。"""
    cid = str(uuid.uuid4())
    conn = get_client()
    conn.execute("INSERT INTO contracts (id, vendor_name, status, version) VALUES (?, ?, ?, ?)",
                 (cid, "Test Vendor", status, 1))
    conn.commit()
    conn.close()
    return cid

def test_can_transition():
    assert can_transition(DRAFT, NEEDS_INFO) is True
    assert can_transition(DRAFT, SIGNED) is False
    assert can_transition(RETURNED, UNDER_REVIEW) is True
    print("✅ test_can_transition 通过")

def test_legal_transition():
    cid = make_contract(DRAFT)
    transition(cid, NEEDS_INFO, "Alice", "缺字段")
    assert get_status(cid) == NEEDS_INFO
    transition(cid, UNDER_REVIEW, "Alice", "已补齐")
    assert get_status(cid) == UNDER_REVIEW
    print("✅ test_legal_transition 通过")

def test_illegal_transition():
    cid = make_contract(DRAFT)
    try:
        transition(cid, SIGNED, "Alice", "想直接签")
        assert False, "应该抛异常"
    except ValueError as e:
        assert "非法流转" in str(e)
    print("✅ test_illegal_transition 通过")

def test_unknown_status():
    try:
        can_transition("Hacker", DRAFT)
        assert False, "应该抛异常"
    except ValueError as e:
        assert "未知" in str(e)
    print("✅ test_unknown_status 通过")

def test_contract_not_found():
    try:
        get_status("no-such-id")
        assert False, "应该抛异常"
    except ValueError as e:
        assert "不存在" in str(e)
    print("✅ test_contract_not_found 通过")

def test_transition_writes_log():
    cid = make_contract(DRAFT)
    transition(cid, NEEDS_INFO, "Alice", "缺字段")
    conn = get_client()
    cursor = conn.cursor()
    cursor.execute("SELECT action, operator FROM audit_logs WHERE contract_id = ?", (cid,))
    rows = cursor.fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["action"] == "state_change"
    assert rows[0]["operator"] == "Alice"
    print("✅ test_transition_writes_log 通过")

if __name__ == "__main__":
    test_can_transition()
    test_legal_transition()
    test_illegal_transition()
    test_unknown_status()
    test_contract_not_found()
    test_transition_writes_log()
    print("\n🎉 state_machine 全部测试通过！")