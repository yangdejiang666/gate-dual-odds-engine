# Gate BTC/ETH 五分钟涨跌统计与预测系统 (Gate Dual Odds Engine)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/Architecture-6--Layers%20%2B%20Watchdog-orange.svg)](#系统总体架构)
[![Delivery](https://img.shields.io/badge/Delivery-Decision%20Popup%20%2B%20Web%20Console-purple.svg)](#前端决策悬浮弹窗与web控制台)

> **浏览器实时抓取 · 本地统计 · 数学建模 · 预测回测一体化 · 单机长期无人值守**  
> 严格落地《Gate BTC/ETH 五分钟涨跌统计与预测软件系统设计方案》（v3.0 决策弹窗形态 + 项目计划书化）。

---

## 目录
- [一、项目概述与核心思路](#一项目概述与核心思路)
- [二、系统总体架构](#二系统总体架构)
- [三、技术栈清单与落地](#三技术栈清单与落地)
- [四、核心功能与特色机制](#四核心功能与特色机制)
  - [4.1 页面精准识别与后台常驻保活](#41-页面精准识别与后台常驻保活)
  - [4.2 五分钟一局状态机与三级存储](#42-五分钟一局状态机与三级存储)
  - [4.3 BTC 与 ETH 双标的联动规律引擎](#43-btc-与-eth-双标的联动规律引擎)
  - [4.4 级联预测漏斗与 80%+ 置信度硬门槛](#44-级联预测漏斗与-80-置信度硬门槛)
  - [4.5 命中/失败核算与动态信誉评分体系](#45-命中失败核算与动态信誉评分体系)
  - [4.6 跟随机制与剩余时间机制 (T_early / T_cutoff)](#46-跟随机制与剩余时间机制)
  - [4.7 一键自动验证长跑与拟合度收敛闭环](#47-一键自动验证长跑与拟合度收敛闭环)
- [五、前端双层架构：决策悬浮弹窗 + Web 控制台](#五前端双层架构决策悬浮弹窗--web-控制台)
- [六、目录结构规范](#六目录结构规范)
- [七、快速上手与启动](#七快速上手与启动)
- [八、REST 接口与 WebSocket 契约](#八rest-接口与-websocket-契约)
- [九、数学边界与风控纪律](#九数学边界与风控纪律)

---

## 一、项目概述与核心思路

在**不依赖任何官方 API** 的前提下，纯从浏览器页面实时抓取 Gate 平台 BTC 与 ETH 五分钟涨跌局的倍率变化序列与走势曲线形态，本地 SQLite(WAL)/DuckDB 落库、统计挖掘规律、建立可解释的级联预测模型，在高置信场景下给出“涨/跌/观望”结论，并以悬浮在浏览器页面上方的**置顶决策弹窗**把信号即时送到下单者眼前。

- **第一信号**：倍率变化序列（秒级更新，平台实时资金博弈的浓缩表达）。
- **辅助信号**：曲线价格形态（归一化相对开盘涨跌幅序列）。
- **仅作标签**：结算结果仅用于事后验证，绝不参与特征构造，杜绝未来函数。
- **双品种原则**：BTC 与 ETH 分标的独立统计、口径绝不混合，互为实时环境参考。

---

## 二、系统总体架构

系统自上而下分为六层加一条横切运维层，各层通过异步消息队列与本地数据库解耦，独立进程常驻：

```
                +-------------------------------------------------+
                |   置顶决策悬浮弹窗 (桌面 Always-On-Top 迷你窗)    |
                |   完整 Web 控制台 (8大页面, 筛选/回测/模型/分析)  |
                +------------------------+------------------------+
                                         | REST / WebSocket (/ws/live, /ws/evolve)
+----------------------------------------v----------------------------------------+
| 第一层: 页面精准识别层  (DOM主通道 + SVG/Canvas备通道 + 截图OCR兜底，多数裁决)    |
+----------------------------------------+----------------------------------------+
| 第二层: 五分钟一局状态机 (WAITING -> RUNNING -> SETTLING -> RESULT，双保险驱动)   |
+----------------------------------------+----------------------------------------+
| 第三层: 数据采集与特征 (秒级倍率差、斜率、时间片 0-30s..240-300s、双标的联动引擎) |
+----------------------------------------+----------------------------------------+
| 第四层: 本地存储与压缩 (热层LRU + 温层SQLite WAL + 冷层Parquet/zstd + 关键点降采样) |
+----------------------------------------+----------------------------------------+
| 第五层: 统计与信誉核算 (单特征/组合/分层统计, 动态信誉分 0~100, 异常行情隔离)     |
+----------------------------------------+----------------------------------------+
| 第六层: 级联预测与长跑 (规则过滤 -> 核心模型 -> Platt置信度校准器 -> 80%硬门槛)   |
|         自动验证长跑闭环: 滚动样本外高置信档命中率收敛 (防刷90%护栏)            |
+----------------------------------------+----------------------------------------+
| 横切层: Watchdog 守护进程、每日软重启、防后台节流参数、内存 RSS 软硬限降级保护     |
+---------------------------------------------------------------------------------+
```

---

## 三、技术栈清单与落地

| 环节 | 选型 | 说明 |
|---|---|---|
| **Web 与 API** | FastAPI + Uvicorn + WebSocket | 异步高性能，读写分离只读连接池，绑定 127.0.0.1 安全隔离 |
| **浏览器驱动** | Playwright (主) / 无头仿真驱动 (备) | 全套防节流参数，单 Context 双标签页 (BTC+ETH) 保活 |
| **状态机** | Python Asyncio 有限状态机 | 倒计时秒级驱动 + 期号变化驱动，sec_offset (0~300s) 严格对齐 |
| **本地存储** | SQLite (WAL 模式) + DuckDB 只读挂载 | 零外部依赖落库，自适应降采样算法 (300点压至 20~40点) |
| **特征工程** | pandas / numpy / 自研特征提取器 | 40~60 维特征：时间片、反转时刻、尾盘跳变、量价背离 |
| **双标的联动** | 滚动互相关 CCF / Granger / Pearson | 实时判定同向跟随、领先滞后、背离独立三态，一致性过滤 |
| **预测模型** | LightGBM / XGBoost / 集成加权 | 级联漏斗，输出原始概率与特征重要性 |
| **置信度校准** | Platt Scaling (Sigmoid 拟合) / 等保校准 | 原始概率映射为真实命中率，严格执行 ≥80% 才出手硬约束 |
| **信誉评分** | 动态信誉算法 (EWMA + 样本量收缩 + 惩罚) | 0~100 分信用分，连续失败 4 次熔断，低于 45 分退役 |
| **自动长跑** | 自研 Evolve Runner + Wilson 95% 区间 | 一键启停长跑，8 项防刷 90% 护栏，run_manifest 原子回滚 |
| **前端平台** | 置顶决策悬浮弹窗 + 8页面响应式控制台 | 纯原生深色交易终端，ECharts 图表联动，毫秒级推送 |

---

## 四、核心功能与特色机制

### 4.1 页面精准识别与后台常驻保活
- **三通道识别策略**：DOM 选择器（主） -> SVG/Canvas 解析（备） -> OCR 区域截图（兜底），冲突时多数裁决并留痕。
- **全套防节流参数**：`--disable-background-timer-throttling`, `--disable-renderer-backgrounding`, `--disable-backgrounding-occluded-windows` 等，保证浏览器切到后台或最小化仍持续读数。
- **30 秒心跳保活**：定时向标签页注入空操作，防止连接被平台挂起；每日定时无缝软重启释放渲染内存。

### 4.2 五分钟一局状态机与三级存储
- **四态闭环**：`WAITING` -> `RUNNING` -> `SETTLING` -> `RESULT`。期号为主键，倒计时为辅，冲突时以期号为准防错位。
- **三级存储**：
  - 热层：内存 LRU 字典（最近 5 局秒级时序）
  - 温层：SQLite (WAL) 滚动保留 5000 局
  - 冷层：Parquet + zstd 压缩归档（8:1 ~ 15:1 压缩比）
- **自适应降采样**：300 点提取每分钟端点、极值点、正负交叉点与首尾点，压至 20~40 点，信息无损。

### 4.3 BTC 与 ETH 双标的联动规律引擎 (第十四章)
- **口径绝不混合**：分标的独立统计，杜绝统计污染。
- **过程级联动**：同局内对方标的已走完的过程作为本标的的实时可用特征（不构成未来函数）。
- **三态判定**：同向跟随 (`CO_DIRECTIONAL`)、领先滞后 (`LEAD_LAG`)、背离独立 (`DIVERGENT`)。
- **一致性过滤器**：当预测方向与同向/领先下的对方标的走势冲突时，一律降级观望，宁可少出手。

### 4.4 级联预测漏斗与 80%+ 置信度硬门槛 (第十五章)
- 规则过滤（样本数充足性） -> 核心预测器 -> Platt Scaling 校准器。
- **80% 硬置信度**：校准后置信度 ≥ 0.80 输出 CALL 或 PUT，否则强制输出 STAND_BY（观望）。系统放弃 70%~80% 的低置信局，只在高胜算时出击。

### 4.5 命中/失败核算与动态信誉评分体系 (第二十三章)
- 信号记账三态：`HIT` (命中)、`MISS` (失败)、`STAND_BY` (观望)。
- 动态信誉分 (0~100)：基准净胜率 (30%) + EWMA 命中率 (35%) + 样本量收缩 (15%) + 校准偏差惩罚 (10%) + 连错惩罚 (10%)。
- 熔断机制：连错 4 次触发熔断停用，信誉分低于 45 分退出决策源。

### 4.6 跟随机制与剩余时间机制 (第二十五章)
- **T_early (前 60 秒)**：开局噪声多，只观察不出手。
- **T_work (60~270 秒)**：黄金决策窗口，信号输出。
- **T_cutoff (270 秒后)**：临近结算，停止出手防滑点。

### 4.7 一键自动验证长跑与拟合度收敛闭环 (第二十七章)
- 一键启动/停止长跑：持续抓取、持续复验、自动挖掘量化因子并重训模型。
- **唯一收敛判据**：校准后高置信档滚动样本外实际命中率 ≥ 目标档位（80% -> 85% -> 88% -> 90% 阶梯），Wilson 95% 置信区间下界达标，日均出手数 ≥ 2。
- **8 项防刷 90% 护栏**：泛化差 > 5pp 直接判定过拟合熔断；测试集封存；天花板如实报 `PLATEAU`。
- **迭代留痕与一键回滚**：每轮写 `run_manifest`，支持模型 + 校准 + 规则三者原子回滚。

---

## 五、前端双层架构：决策悬浮弹窗 + Web 控制台

### 1. 置顶决策悬浮弹窗 (主界面，第 16.4~16.7 节)
决策者 95% 时间只需余光关注置顶小窗，无需切换窗口：
- **收起态 (悬浮球)**：倒计时进度、最新信号方向、置信度色环、长跑琥珀色角标。
- **展开态 (480x640 紧凑面板)**：
  - 顶部倒计时条（标注 T_early 60s、T_cutoff 270s 标线）
  - BTC 与 ETH 双标的 mini 实时倍率差曲线
  - 预测结论大卡片（CALL/PUT/STAND_BY，置信度百分比）
  - 命中依据 Top3 规则与信誉分
  - 联动状态标签与操作建议行

### 2. 完整 Web 控制台 (二级界面，第十七章)
用于复盘、调参、回测与监控，包含 8 大核心页面：
1. **总览 Dashboard**
2. **实时信号面板**
3. **数据浏览器**（统一多维筛选器 FilterBar，支持 CSV 导出）
4. **规则库与信誉分**（查看 0~100 信用分，一键启停）
5. **回测中心 + 自动长跑**（Walk-forward 回测、长跑一键启停与原子回滚）
6. **模型中心**（SHAP 特征贡献度排名、校准曲线）
7. **规律分析**（过程时间片信息量地图、反转时刻分布、双标的联动热力）
8. **系统与设置**（RSS 内存、磁盘配额、一键导出诊断包）

---

## 六、目录结构规范

```
gate-dual-odds-engine/
├── docs/                      # 详细项目计划书与技术方案
│   └── PROJECT_PLAN.md        # v3.0 完整方案文档 (33章全集)
├── backend/                   # 后端核心源码
│   └── app/
│       ├── main.py            # FastAPI 应用入口与 WebSocket 广播
│       ├── config.py          # 系统集中配置中心 (含降级保护)
│       ├── database.py        # SQLite (WAL) 数据库管理与表结构
│       ├── models/
│       │   └── schemas.py     # Pydantic 领域模型与数据契约
│       ├── services/
│       │   ├── crawler/       # 识别层与状态机 (browser, recognition, state_machine, watchdog)
│       │   ├── collector/     # 特征提取与双标的联动 (feature_extractor, cross_analyzer)
│       │   ├── storage/       # 存储、降采样与内存保护 (downsampling, compression, memory_guard)
│       │   ├── accounting/    # 核算、信誉与异常隔离 (settlement, reputation, anomaly, decision_guard)
│       │   ├── engine/        # 级联预测漏斗与 Walk-Forward 回测 (cascade_model, walk_forward)
│       │   ├── evolve/        # 自动长跑与护栏 (evolve_runner, factor_miner, guardrails, manifest_repo)
│       │   └── market_api/    # 真实市场 API 扩展接口 (可插拔 Provider)
│       └── routers/           # REST 路由 (periods, odds, rules, backtest, models, analysis, system, evolve, ws)
├── frontend/                  # 前端源码
│   ├── popup.html             # 置顶决策悬浮弹窗 (收起态/展开态)
│   ├── index.html             # 8 页面完整 Web 控制台
│   ├── style.css              # 专业深色交易科技主题
│   └── app.js                 # 控制台数据流与交互逻辑
├── shared/                    # 前后端口径契约
│   ├── metrics_catalog.yaml   # 指标口径契约 (metric_version: v3.0.0)
│   └── schema.json            # JSON Schema 数据规范
├── tasks/                     # 离线与定时调度任务
│   ├── precompute.py          # 每小时预算任务 (agg_hourly_summary 前端秒开)
│   └── report_gen.py          # 自动化日报与周报生成 (带口径水印)
├── deploy/                    # 部署与运维套件
│   ├── mock_simulator.py      # 高保真离线对局仿真发生器 (冷启动测试)
│   ├── start_backend.py       # 后端服务启动器
│   ├── start_crawler.py       # 抓取守护启动器
│   ├── start_popup.py         # 桌面置顶弹窗启动器
│   ├── start_all.bat          # Windows 一键全栈启动脚本
│   ├── docker-compose.yml     # 容器化编排
│   └── .env.example           # 环境变量模版
├── tests/                     # 单元与集成测试套件
│   ├── test_storage.py        # 存储与降采样算法测试
│   ├── test_features_and_cross.py # 特征与联动引擎测试
│   ├── test_cascade_and_reputation.py # 级联模型、置信度与信誉分测试
│   └── test_evolve_and_guardrails.py # 自动长跑与防刷 90% 护栏测试
├── requirements.txt           # 生产依赖清单
├── pyproject.toml             # 工程元数据与打包配置
└── README.md                  # 系统说明文档
```

---

## 七、快速上手与启动

### 7.1 环境要求
- Python 3.10+ (推荐 Python 3.11/3.13)
- Windows 10/11 或 Linux 现代系统

### 7.2 安装依赖
```bash
pip install -r requirements.txt
```
*(系统已实现纯标准库自适应降级，即使尚未安装外部库亦可直接运行核心逻辑与测试)*

### 7.3 Windows 一键启动
双击运行根目录或 `deploy/` 下的：
```cmd
deploy\start_all.bat
```
脚本将自动完成：
1. 检查并初始化 SQLite WAL 本地数据库；
2. 启动 FastAPI + WebSocket 后端服务 (`http://127.0.0.1:8000`)；
3. 唤起置顶决策悬浮弹窗。

### 7.4 运行单元测试套件
```bash
python tests/test_storage.py
python tests/test_features_and_cross.py
python tests/test_cascade_and_reputation.py
python tests/test_evolve_and_guardrails.py
```

---

## 八、REST 接口与 WebSocket 契约

```
GET  /api/periods            期数列表（分页+多维高级筛选）
GET  /api/periods/{id}       单局详情（倍率序列摘要、形态、命中规则）
GET  /api/odds/summary       聚合倍率摘要（图表专用）
GET  /api/rules              规则库列表与信誉分
POST /api/rules/{id}/toggle  启停规则
POST /api/backtest/run       提交 Walk-Forward 回测任务
GET  /api/models             模型版本列表
GET  /api/models/metrics/shap 特征重要性 SHAP 贡献度
GET  /api/analysis/information_map 过程时间片信息量地图
GET  /api/analysis/cross_correlation BTC 与 ETH 联动分析指标
GET  /api/system/health      系统健康度与 RSS 资源采样
GET  /api/system/diagnostics 导出系统诊断包 (JSON)
POST /api/evolve/start       启动自动长跑 (设定目标置信档)
POST /api/evolve/stop        优雅停止长跑
GET  /api/evolve/status      查询长跑实时状态
GET  /api/evolve/history     查询长跑迭代清单 (manifest)
POST /api/evolve/rollback    一键原子回滚到指定轮次
WS   /ws/live                实时增量广播 (倒计时, 倍率差增量, 信号)
WS   /ws/evolve              长跑迭代与收敛事件广播
```

---

## 九、数学边界与风控纪律

1. **长期期望为负**：平台底层抽水与赔率不对称决定了统计模型只能定位短期局部优势，绝不存在“长期必胜公式”。
2. **80% 置信度定义**：指当模型宣称置信度 ≥ 80% 时实际命中率达到该水平，而非所有局都出手；70%~80% 的局强制输出观望是完全正确的做法。
3. **硬止损与熔断**：单日最大连续错误达到 4 次或触发连续回撤即时熔断冻结，杜绝盲目追单。
4. **纸面模拟优先**：默认以影子模式和回测为先，严禁未经验证直接放大实盘。

---

## 许可证
本项目采用 [MIT 许可证](LICENSE)。
