"""
降采样与关键特征点保留算法
严格按第十章 10.2 节落地：
对一条 300 点的倍率差/价格曲线不存 300 点，
改为存：
1. 每分钟端点 (60, 120, 180, 240, 300 秒)
2. 区间极值点 (该分钟内最大值与最小值及其时刻)
3. 倍率差正负翻转的交叉点 (倍率分析的核心事件，一个都不能丢)
4. 首尾点 (第 0 秒与第 300 秒)
将 300 点压至 20~40 点且关键统计指标绝不失真。
"""

from typing import Any

def downsample_odds_ticks(ticks: list[dict[str, Any]], max_target_points: int = 40) -> list[dict[str, Any]]:
    """
    对局内秒级 ticks 列表执行自适应关键点保留降采样
    ticks 元素要求包含: sec_offset, up_odds, down_odds, odds_diff, price
    """
    if len(ticks) <= max_target_points:
        return ticks

    # 按 sec_offset 排序
    sorted_ticks = sorted(ticks, key=lambda x: x["sec_offset"])
    n = len(sorted_ticks)
    if n == 0:
        return []

    selected_indices = set()
    # 1. 必选首尾点
    selected_indices.add(0)
    selected_indices.add(n - 1)

    # 2. 必选每分钟端点 (按秒偏移接近 60, 120, 180, 240, 300)
    minute_targets = {60, 120, 180, 240, 300}
    for target in minute_targets:
        closest_idx = min(range(n), key=lambda i: abs(sorted_ticks[i]["sec_offset"] - target))
        selected_indices.add(closest_idx)

    # 3. 必选正负交叉点 (odds_diff 符号翻转点，核心事件不可丢失)
    for i in range(1, n):
        prev_diff = sorted_ticks[i - 1]["odds_diff"]
        curr_diff = sorted_ticks[i]["odds_diff"]
        if (prev_diff > 0 and curr_diff <= 0) or (prev_diff < 0 and curr_diff >= 0):
            selected_indices.add(i - 1)
            selected_indices.add(i)

    # 4. 区间极值点 (按 60 秒为区间，找 odds_diff 最大与最小点)
    intervals = [(0, 60), (60, 120), (120, 180), (180, 240), (240, 300)]
    for start_sec, end_sec in intervals:
        sub_indices = [
            i for i, t in enumerate(sorted_ticks)
            if start_sec <= t["sec_offset"] <= end_sec
        ]
        if sub_indices:
            max_idx = max(sub_indices, key=lambda i: sorted_ticks[i]["odds_diff"])
            min_idx = min(sub_indices, key=lambda i: sorted_ticks[i]["odds_diff"])
            selected_indices.add(max_idx)
            selected_indices.add(min_idx)

    # 5. 按原时间序排列输出
    result = [sorted_ticks[i] for i in sorted(selected_indices)]
    return result
