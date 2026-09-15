import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db import get_client
from app.audit import log, get_logs
from app.validation import validate_schedule_a, check_and_update_status
from app.versioning import bump_version, get_version_history, get_current_version, diff_fields
from app.approval import approve, reject, can_send_for_signature, get_approvals
from app.signature import (
    send_for_signature, mock_sign, mock_decline, mock_expire,
    get_signature, get_archive_files, ARCHIVE_ITEMS,
)
from app.state_machine import (
    DRAFT, UNDER_REVIEW, get_status, transition,
)

router = APIRouter()

class ContractCreate(BaseModel):
    vendor_name: str = ""
    vendor_country: str = ""
    vendor_address: str = ""
    product_name: str = ""
    business_line: str = ""
    region: str = ""
    customer_scope: str = ""
    pricing_model: str = ""
    currency: str = ""
    revenue_definition: str = ""
    platform_share: float | None = None
    vendor_share: float | None = None
    settlement_cycle: str = ""
    refund_policy: str = ""
    tax_invoice_party: str = ""
    signer_name: str = ""
    signer_title: str = ""
    signer_email: str = ""
    signer_authorized: bool | None = None

class ContractUpdate(BaseModel):
    operator: str
    changed_fields: list[str] | None = None
    values: dict
    
    
class SimpleAction(BaseModel):
    operator: str
    comment: str = ""

def _row_to_dict(row):
    return dict(row) if row else None

@router.get("/contracts")
def list_contracts():
    conn = get_client()
    cursor = conn.cursor()
    cursor.execute("SELECT id, vendor_name, status, version, updated_at FROM contracts ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]

@router.post("/contracts")
def create_contract(payload: ContractCreate):
    cid = str(uuid.uuid4())
    data = payload.model_dump()
    data["signer_authorized"] = 1 if data.get("signer_authorized") else 0
    cols = ["id", "status", "version"] + list(data.keys())
    vals = [cid, DRAFT, 1] + list(data.values())
    placeholders = ",".join(["?"] * len(cols))
    conn = get_client()
    conn.execute(f"INSERT INTO contracts ({','.join(cols)}) VALUES ({placeholders})", vals)
    conn.commit()
    conn.close()
    log(cid, payload.signer_name or "vendor", "submit", 1, detail="创建合同草稿")
    return {"id": cid, "status": DRAFT, "version": 1}

@router.get("/contracts/{contract_id}")
def get_contract(contract_id: str):
    conn = get_client()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    contract = dict(row)
    contract["missing_fields"] = validate_schedule_a(contract_id)
    contract["current_version"] = get_current_version(contract_id)
    return contract

@router.post("/contracts/{contract_id}/submit")
def submit_contract(contract_id: str, action: SimpleAction):
    missing = check_and_update_status(contract_id, action.operator)
    if missing:
        return {"status": get_status(contract_id), "missing_fields": missing, "can_proceed": False}
    transition(contract_id, UNDER_REVIEW, action.operator, detail="提交审批")
    return {"status": get_status(contract_id), "missing_fields": [], "can_proceed": True}

@router.post("/contracts/{contract_id}/update")
def update_contract(contract_id: str, payload: ContractUpdate):
    if not payload.values:
        raise HTTPException(status_code=400, detail="values 不能为空")

    # 状态检查：只有这三个状态允许修改
    editable_states = {"Draft", "Needs Information", "Returned"}
    current_status = get_status(contract_id)
    if current_status not in editable_states:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 {current_status} 不允许修改，只有 Draft / Needs Information / Returned 可改"
        )

    # 传了 changed_fields 就用它；没传就自动 diff
    if payload.changed_fields:
        changed = payload.changed_fields
    else:
        try:
            changed = diff_fields(contract_id, payload.values)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if not changed:
        return {
            "version": get_current_version(contract_id),
            "changed_fields": [],
            "status": get_status(contract_id),
            "message": "无变更，版本不变"
        }

    conn = get_client()
    cursor = conn.cursor()
    for field, value in payload.values.items():
        if field in ("platform_share", "vendor_share") and value is not None:
            try:
                value = float(value)
            except (ValueError, TypeError):
                conn.close()
                raise HTTPException(status_code=400, detail=f"{field} 必须是数字")
        if field == "signer_authorized":
            value = 1 if value else 0
        cursor.execute(f"UPDATE contracts SET {field} = ? WHERE id = ?", (value, contract_id))
    conn.commit()
    conn.close()

    new_version = bump_version(contract_id, changed, payload.operator)
    return {
        "version": new_version,
        "changed_fields": changed,
        "status": get_status(contract_id)
    }


@router.get("/contracts/{contract_id}/preview")
def preview_contract(contract_id: str):
    """合同草稿预览（只读）。缺失字段显示为 [待补充]。"""
    conn = get_client()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="合同不存在")

    c = dict(row)

    def v(key, label):
        value = c.get(key)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return f"[待补充] {label}"
        return value

    return {
        "contract_id": contract_id,
        "version": c["version"],
        "status": c["status"],
        "title": "SaaS / API 供应商分销协议",
        "party_a": "本公司",
        "party_b": v("vendor_name", "供应商法定名称"),
        "party_b_country": v("vendor_country", "注册地"),
        "party_b_address": v("vendor_address", "注册地址"),
        "schedule_a": {
            "产品/服务": v("product_name", "产品/服务"),
            "业务线": v("business_line", "业务线"),
            "地域": v("region", "地域"),
            "客户范围": v("customer_scope", "客户范围"),
            "收费方式": v("pricing_model", "收费方式"),
            "币种": v("currency", "币种"),
            "收入计算口径": v("revenue_definition", "收入计算口径"),
            "平台分成比例": c.get("platform_share") if c.get("platform_share") is not None else "[待补充] 平台分成比例",
            "供应商分成比例": c.get("vendor_share") if c.get("vendor_share") is not None else "[待补充] 供应商分成比例",
            "结算周期": v("settlement_cycle", "结算周期"),
            "退款处理": v("refund_policy", "退款处理"),
            "税务/开票责任": v("tax_invoice_party", "税务/开票责任"),
        },
        "signer": {
            "姓名": v("signer_name", "签字人姓名"),
            "职务": v("signer_title", "签字人职务"),
            "邮箱": v("signer_email", "签字人邮箱"),
            "授权确认": "已授权" if c.get("signer_authorized") else "[待补充] 授权确认",
        },
        "missing_fields": validate_schedule_a(contract_id),
        "generated_at": datetime.now().isoformat(),
    }


@router.post("/contracts/{contract_id}/approve")
def approve_contract(contract_id: str, action: SimpleAction):
    try:
        approve(contract_id, action.operator, action.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": get_status(contract_id), "can_send": can_send_for_signature(contract_id)}

@router.post("/contracts/{contract_id}/reject")
def reject_contract(contract_id: str, action: SimpleAction):
    try:
        reject(contract_id, action.operator, action.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": get_status(contract_id)}

@router.post("/contracts/{contract_id}/send")
def send_contract(contract_id: str, action: SimpleAction):
    try:
        send_for_signature(contract_id, action.operator)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": get_status(contract_id), "signature": get_signature(contract_id)}

@router.post("/contracts/{contract_id}/sign")
def sign_contract(contract_id: str, action: SimpleAction):
    try:
        mock_sign(contract_id, action.operator)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": get_status(contract_id)}

@router.post("/contracts/{contract_id}/decline")
def decline_contract(contract_id: str, action: SimpleAction):
    try:
        mock_decline(contract_id, action.comment, action.operator)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": get_status(contract_id)}

@router.post("/contracts/{contract_id}/expire")
def expire_contract(contract_id: str, action: SimpleAction):
    try:
        mock_expire(contract_id, action.operator)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": get_status(contract_id)}

@router.get("/contracts/{contract_id}/logs")
def contract_logs(contract_id: str):
    return get_logs(contract_id)

@router.get("/contracts/{contract_id}/approvals")
def contract_approvals(contract_id: str):
    return get_approvals(contract_id, only_valid=False)

@router.get("/contracts/{contract_id}/versions")
def contract_versions(contract_id: str):
    return get_version_history(contract_id)

@router.get("/contracts/{contract_id}/archive")
def contract_archive(contract_id: str):
    try:
        files = get_archive_files(contract_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"archive_items": files}