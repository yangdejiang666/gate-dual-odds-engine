"""
自动验证长跑接口
严格按第二十章与第二十七章落地
"""

from fastapi import APIRouter, HTTPException
from backend.app.models.schemas import EvolveStartRequest
from backend.app.services.evolve.evolve_runner import evolve_runner
from backend.app.services.evolve.manifest_repo import manifest_repo

router = APIRouter(prefix="/api/evolve", tags=["Evolve"])

@router.post("/start")
async def start_evolve(req: EvolveStartRequest):
    await evolve_runner.start(target_confidence=req.target_confidence, max_rounds=req.max_rounds)
    return {
        "status": "STARTED",
        "run_id": evolve_runner.run_id,
        "target_confidence": req.target_confidence
    }

@router.post("/stop")
async def stop_evolve():
    await evolve_runner.stop()
    return {"status": "STOPPING"}

@router.get("/status")
def get_evolve_status():
    return {
        "run_id": evolve_runner.run_id,
        "state": evolve_runner.state.value,
        "current_round": evolve_runner.current_round,
        "target_confidence": evolve_runner.target_confidence,
        "last_accuracy": evolve_runner.last_accuracy,
        "plateau_count": evolve_runner.plateau_count
    }

@router.get("/history")
def get_evolve_history():
    return {"history": manifest_repo.get_history()}

@router.post("/rollback")
def rollback_round(round_index: int):
    success = manifest_repo.rollback_to_round(round_index)
    if not success:
        raise HTTPException(status_code=400, detail="回滚失败，未找到该轮次")
    return {"status": "SUCCESS", "message": f"已成功原子回滚至第 {round_index} 轮版本"}
