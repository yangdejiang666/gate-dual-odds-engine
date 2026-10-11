"""
规则库管理接口
按第二十章与第二十三章落地
"""

from fastapi import APIRouter, HTTPException
from backend.app.database import db

router = APIRouter(prefix="/api/rules", tags=["Rules"])

@router.get("")
def list_rules():
    rows = db.execute_read("SELECT * FROM rule_registry ORDER BY reputation_score DESC")
    return {"rules": rows}

@router.post("/{rule_id}/toggle")
def toggle_rule(rule_id: str):
    rows = db.execute_read("SELECT status FROM rule_registry WHERE rule_id = ?", (rule_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="未找到该规则")
    
    current_status = rows[0]["status"]
    new_status = "RETIRED" if current_status == "ACTIVE" else "ACTIVE"
    db.execute_write("UPDATE rule_registry SET status = ? WHERE rule_id = ?", (new_status, rule_id))
    return {"rule_id": rule_id, "status": new_status}
