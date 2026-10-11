"""
级联模型、置信度校准与信誉评分测试
"""

from backend.app.services.engine.cascade_model import cascade_engine
from backend.app.services.accounting.reputation_engine import reputation_engine
from backend.app.services.accounting.decision_guard import decision_guard
from backend.app.models.schemas import ActionEnum

def test_cascade_and_confidence_threshold():
    # 模拟高置信度场景 (倍率深度偏向看涨，联动同向)
    features = {
        "latest_diff": -1.2,
        "tail_jump": -0.40,
        "price_return_pct": 0.50
    }
    cross = {"peer_same_period_dir": 1}
    action, raw_p, calib_conf, hit_rules = cascade_engine.predict("BTC", features, cross)

    assert action == ActionEnum.CALL
    assert calib_conf >= 0.80, f"触发 CALL 时置信度必须达到 80% 门槛 (当前: {calib_conf})"

    # 模拟中等置信度 (低于 80% 硬门槛必须输出观望)
    features_med = {
        "latest_diff": -0.2,
        "tail_jump": 0.0,
        "price_return_pct": 0.05
    }
    action_med, _, calib_conf_med, _ = cascade_engine.predict("BTC", features_med, cross)
    assert action_med == ActionEnum.STAND_BY, "低于 80% 门槛必须强制输出观望"
    print("test_cascade_and_confidence_threshold passed!")

def test_decision_guard_timing():
    # 开局 30 秒 (T_early 之前) 必须拦截
    act, msg = decision_guard.check_timing_constraints(sec_offset=30, raw_action=ActionEnum.CALL)
    assert act == ActionEnum.STAND_BY
    assert "开局早期" in msg

    # 尾盘 280 秒 (T_cutoff 之后) 必须拦截
    act, msg = decision_guard.check_timing_constraints(sec_offset=285, raw_action=ActionEnum.CALL)
    assert act == ActionEnum.STAND_BY
    assert "临近结算" in msg

    # 黄金窗口 150 秒放行
    act, msg = decision_guard.check_timing_constraints(sec_offset=150, raw_action=ActionEnum.CALL)
    assert act == ActionEnum.CALL
    print("test_decision_guard_timing passed!")

def test_reputation_scoring():
    score = reputation_engine.calculate_score(
        recent_win_rate=0.82,
        baseline_rate=0.505,
        sample_count=400,
        claimed_conf=0.82,
        consecutive_fails=0
    )
    assert score >= 80.0, "高质量高样本规则信誉分应在 80 分以上"
    print("test_reputation_scoring passed!")

if __name__ == "__main__":
    test_cascade_and_confidence_threshold()
    test_decision_guard_timing()
    test_reputation_scoring()
