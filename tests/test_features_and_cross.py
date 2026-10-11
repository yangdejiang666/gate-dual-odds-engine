"""
特征工程与双标的联动引擎测试
"""

from backend.app.services.collector.feature_extractor import feature_extractor
from backend.app.services.collector.cross_analyzer import cross_analyzer
from backend.app.models.schemas import CrossStateEnum, ActionEnum

def test_feature_extraction():
    ticks = [
        {"sec_offset": 0, "up_odds": 1.95, "down_odds": 1.95, "odds_diff": 0.0, "price": 68000.0},
        {"sec_offset": 150, "up_odds": 1.70, "down_odds": 2.20, "odds_diff": -0.5, "price": 68150.0},
        {"sec_offset": 290, "up_odds": 1.60, "down_odds": 2.30, "odds_diff": -0.7, "price": 68250.0}
    ]
    feat = feature_extractor.extract_period_features(ticks, open_price=68000.0)
    assert feat["latest_diff"] == -0.7
    assert feat["min_diff"] == -0.7
    assert feat["price_return_pct"] > 0
    print("test_feature_extraction passed!")

def test_cross_symbol_and_filter():
    cur_ticks = [{"odds_diff": -0.4, "sec_offset": i, "price": 68000.0} for i in range(100)]
    peer_ticks = [{"odds_diff": -0.3, "sec_offset": i, "price": 3600.0} for i in range(100)]

    res = cross_analyzer.compute_cross_features("BTC", cur_ticks, peer_ticks)
    assert res["cross_same_dir_ratio"] == 1.0
    assert res["cross_state"] == CrossStateEnum.CO_DIRECTIONAL.value

    # 测试一致性过滤器：与对方标的下行趋势冲突时强制降级
    action, conf, msg = cross_analyzer.apply_consistency_filter(
        proposed_action=ActionEnum.CALL,
        calibrated_conf=0.85,
        cross_state=CrossStateEnum.CO_DIRECTIONAL,
        peer_dir=-1 # 对方下行
    )
    assert action == ActionEnum.STAND_BY, "冲突时必须降级为观望"
    print("test_cross_symbol_and_filter passed!")

if __name__ == "__main__":
    test_feature_extraction()
    test_cross_symbol_and_filter()
