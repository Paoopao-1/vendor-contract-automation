from app.db import get_client
from app.audit import log, get_logs

def setup():
    conn = get_client()
    conn.execute("DELETE FROM audit_logs")
    conn.commit()
    conn.close()

def test_log_and_get():
    setup()
    log("test-001", "Alice", "submit", 1, "提交了合同")
    log("test-001", "Bob", "approve", 1, "法务审批通过")
    logs = get_logs("test-001")
    assert len(logs) == 2, f"期望2条，实际{len(logs)}"
    assert logs[0]["operator"] == "Bob"   # 倒序，最新在前
    assert logs[1]["operator"] == "Alice"
    print("✅ test_log_and_get 通过")

def test_invalid_action():
    setup()
    try:
        log("test-002", "Alice", "hack", 1, "")
        assert False, "应该抛 ValueError"
    except ValueError as e:
        assert "非法操作类型" in str(e)
    print("✅ test_invalid_action 通过")

def test_empty_contract_id():
    setup()
    try:
        log("", "Alice", "submit", 1, "")
        assert False, "应该抛 ValueError"
    except ValueError as e:
        assert "contract_id" in str(e)
    print("✅ test_empty_contract_id 通过")

def test_empty_operator():
    setup()
    try:
        log("test-003", "", "submit", 1, "")
        assert False, "应该抛 ValueError"
    except ValueError as e:
        assert "operator" in str(e)
    print("✅ test_empty_operator 通过")

def test_get_logs_empty():
    setup()
    logs = get_logs("nonexistent")
    assert logs == [], f"期望空列表，实际{logs}"
    print("✅ test_get_logs_empty 通过")

def test_get_logs_no_contract_id():
    setup()
    try:
        get_logs("")
        assert False, "应该抛 ValueError"
    except ValueError:
        print("✅ test_get_logs_no_contract_id 通过")

if __name__ == "__main__":
    test_log_and_get()
    test_invalid_action()
    test_empty_contract_id()
    test_empty_operator()
    test_get_logs_empty()
    test_get_logs_no_contract_id()
    print("\n🎉 全部测试通过！")