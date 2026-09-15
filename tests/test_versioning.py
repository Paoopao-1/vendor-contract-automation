import uuid
from app.db import get_client
from app.versioning import (
    bump_version, get_current_version, is_critical_change,
    get_version_history, diff_fields,
)
from app.state_machine import DRAFT

def make_contract(version=1):
    cid = str(uuid.uuid4())
    conn = get_client()
    conn.execute(
        "INSERT INTO contracts (id, vendor_name, status, version) VALUES (?, ?, ?, ?)",
        (cid, "Test Vendor", DRAFT, version)
    )
    conn.commit()
    conn.close()
    return cid

def test_any_field_is_critical():
    """新规则：任意字段变化都算关键变化。"""
    assert is_critical_change(["platform_share"]) is True
    assert is_critical_change(["signer_email"]) is True
    assert is_critical_change(["vendor_address"]) is True
    assert is_critical_change(["region"]) is True
    assert is_critical_change(["vendor_address", "region"]) is True
    print("✅ test_any_field_is_critical 通过")

def test_unknown_field():
    try:
        is_critical_change(["hacker_field"])
        assert False
    except ValueError as e:
        assert "未知字段" in str(e)
    print("✅ test_unknown_field 通过")

def test_empty_changed_fields():
    try:
        is_critical_change([])
        assert False
    except ValueError:
        print("✅ test_empty_changed_fields 通过")

def test_bump_on_any_field():
    cid = make_contract(version=1)
    new_v = bump_version(cid, ["platform_share"], "Alice")
    assert new_v == 2
    assert get_current_version(cid) == 2

    new_v = bump_version(cid, ["vendor_address"], "Alice")
    assert new_v == 3
    assert get_current_version(cid) == 3
    print("✅ test_bump_on_any_field 通过")

def test_old_approvals_invalidated():
    cid = make_contract(version=1)
    conn = get_client()
    conn.execute(
        "INSERT INTO approvals (id, contract_id, approver, version, decision, is_valid) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), cid, "Legal_Alice", 1, "approved", 1)
    )
    conn.commit()
    conn.close()

    bump_version(cid, ["platform_share"], "Alice")

    conn = get_client()
    cursor = conn.cursor()
    cursor.execute("SELECT is_valid FROM approvals WHERE contract_id = ?", (cid,))
    rows = cursor.fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["is_valid"] == 0
    print("✅ test_old_approvals_invalidated 通过")

def test_snapshot_saved():
    cid = make_contract(version=1)
    bump_version(cid, ["refund_policy"], "Alice")
    history = get_version_history(cid)
    assert len(history) == 1
    assert history[0]["version"] == 2
    print("✅ test_snapshot_saved 通过")

def test_version_never_decreases():
    cid = make_contract(version=1)
    bump_version(cid, ["platform_share"], "Alice")
    bump_version(cid, ["platform_share"], "Alice")
    assert get_current_version(cid) == 3
    print("✅ test_version_never_decreases 通过")

def test_diff_fields_detect_change():
    cid = make_contract()
    conn = get_client()
    conn.execute("UPDATE contracts SET platform_share = 0.7, vendor_address = 'Old Addr' WHERE id = ?", (cid,))
    conn.commit()
    conn.close()

    # 只改 vendor_address，platform_share 传相同值
    changed = diff_fields(cid, {"platform_share": 0.7, "vendor_address": "New Addr"})
    assert changed == ["vendor_address"], f"期望 ['vendor_address']，实际 {changed}"
    print("✅ test_diff_fields_detect_change 通过")

def test_diff_fields_no_change():
    cid = make_contract()
    conn = get_client()
    conn.execute("UPDATE contracts SET platform_share = 0.7 WHERE id = ?", (cid,))
    conn.commit()
    conn.close()

    changed = diff_fields(cid, {"platform_share": 0.7})
    assert changed == []
    print("✅ test_diff_fields_no_change 通过")

def test_diff_fields_whitespace_ignored():
    cid = make_contract()
    conn = get_client()
    conn.execute("UPDATE contracts SET vendor_name = 'Acme' WHERE id = ?", (cid,))
    conn.commit()
    conn.close()

    # '  Acme  ' 应该视为与 'Acme' 相同
    changed = diff_fields(cid, {"vendor_name": "  Acme  "})
    assert changed == []
    print("✅ test_diff_fields_whitespace_ignored 通过")

def test_diff_fields_string_number_equivalent():
    cid = make_contract()
    conn = get_client()
    conn.execute("UPDATE contracts SET platform_share = 0.7 WHERE id = ?", (cid,))
    conn.commit()
    conn.close()

    # '0.7' 和 0.7 应视为相同
    changed = diff_fields(cid, {"platform_share": "0.7"})
    assert changed == []
    print("✅ test_diff_fields_string_number_equivalent 通过")

if __name__ == "__main__":
    test_any_field_is_critical()
    test_unknown_field()
    test_empty_changed_fields()
    test_bump_on_any_field()
    test_old_approvals_invalidated()
    test_snapshot_saved()
    test_version_never_decreases()
    test_diff_fields_detect_change()
    test_diff_fields_no_change()
    test_diff_fields_whitespace_ignored()
    test_diff_fields_string_number_equivalent()
    print("\n🎉 versioning 全部测试通过！")