"""
自动长跑与防刷 90% 护栏测试
"""

from backend.app.services.evolve.guardrails import guardrails

def test_wilson_lower_bound_small_sample():
    # 20 局全中 (100% 胜率)，但小样本下 Wilson 95% 下界应远低于 95%
    lower = guardrails.calculate_wilson_lower_bound(hits=20, total=20)
    assert lower < 0.90, f"小样本 20 局即使全中，下界 ({lower*100:.1f}%) 也不应虚高超 90%"
    
    # 500 局命中 450 局 (90% 胜率)，大样本下 Wilson 下界应接近 87%
    lower_large = guardrails.calculate_wilson_lower_bound(hits=450, total=500)
    assert lower_large >= 0.865
    print("test_wilson_lower_bound_small_sample passed!")

def test_guardrails_generalization_gap():
    # 训练集 94%，样本外仅 84%，差距 10pp > 5pp，判定过拟合
    passed, msg = guardrails.check_guardrails(
        train_acc=0.94,
        out_of_sample_acc=0.84,
        total_eval_samples=200,
        daily_actions=3.0,
        target_ladder=0.85
    )
    assert not passed
    assert "过拟合" in msg
    print("test_guardrails_generalization_gap passed!")

if __name__ == "__main__":
    test_wilson_lower_bound_small_sample()
    test_guardrails_generalization_gap()
