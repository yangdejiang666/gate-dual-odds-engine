"""
存储与降采样测试
"""

from backend.app.database import db
from backend.app.services.storage.downsampling import downsample_odds_ticks

def test_downsampling_keeps_key_points():
    # 模拟 300 点
    ticks = []
    for s in range(301):
        # 在第 120 秒发生交叉翻转
        diff = -0.5 if s < 120 else 0.5
        ticks.append({
            "sec_offset": s,
            "up_odds": 1.95,
            "down_odds": 1.95,
            "odds_diff": diff,
            "price": 68000.0 + s
        })

    downsampled = downsample_odds_ticks(ticks, max_target_points=40)
    
    # 验证关键点保留
    assert len(downsampled) <= 40
    offsets = [t["sec_offset"] for t in downsampled]
    assert 0 in offsets, "首点必须保留"
    assert 300 in offsets, "尾点必须保留"
    assert any(abs(o - 120) <= 1 for o in offsets), "交叉点翻转时刻必须保留"
    print("test_downsampling_keeps_key_points passed!")

def test_database_crud():
    # 测试基本读写
    db.execute_write(
        "INSERT OR REPLACE INTO page_event (event_type, message) VALUES (?, ?)",
        ("TEST_EVENT", "UnitTest verification event")
    )
    rows = db.execute_read("SELECT * FROM page_event WHERE event_type = ?", ("TEST_EVENT",))
    assert len(rows) >= 1
    assert rows[0]["message"] == "UnitTest verification event"
    print("test_database_crud passed!")

if __name__ == "__main__":
    test_downsampling_keeps_key_points()
    test_database_crud()
