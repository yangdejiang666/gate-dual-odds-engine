// 控制台前端主交互逻辑

function switchPage(pageId) {
  document.querySelectorAll(".page-container").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));

  const targetPage = document.getElementById(pageId);
  if (targetPage) targetPage.classList.add("active");

  const titles = {
    "p-dashboard": "总览 Dashboard",
    "p-live": "实时信号面板",
    "p-browser": "数据浏览器",
    "p-rules": "规则库与信誉分",
    "p-backtest": "回测与长跑中心",
    "p-models": "模型中心 (SHAP)",
    "p-analysis": "规律与联动分析",
    "p-system": "系统与监控设置"
  };
  document.getElementById("page-title").innerText = titles[pageId] || "控制台";

  // 触发对应页面数据加载
  if (pageId === "p-browser") loadPeriodsData();
  if (pageId === "p-rules") loadRulesData();
  if (pageId === "p-models") loadShapData();
  if (pageId === "p-analysis") loadAnalysisData();
  if (pageId === "p-dashboard") loadHealthData();
}

// 建立实时 WebSocket 连接
const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
const wsUrl = `${wsProto}//${window.location.host}/ws/live`;
let liveSocket;

function initWebSocket() {
  liveSocket = new WebSocket(wsUrl);
  liveSocket.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      updateLivePanel(msg);
    } catch (e) {}
  };
  liveSocket.onclose = () => setTimeout(initWebSocket, 2000);
}
initWebSocket();

function updateLivePanel(data) {
  if (!data) return;
  document.getElementById("live-period").innerText = data.period_id || "--";
  document.getElementById("live-sec").innerText = data.remaining_sec || "--";

  if (data.btc) {
    document.getElementById("live-btc-diff").innerText = data.btc.odds_diff;
  }
  if (data.eth) {
    document.getElementById("live-eth-diff").innerText = data.eth.odds_diff;
  }

  const sig = data.signal || {};
  const actEl = document.getElementById("live-action");
  actEl.innerText = sig.action || "STAND_BY";
  actEl.className = sig.action === "CALL" ? "tag-up" : (sig.action === "PUT" ? "tag-down" : "");
  document.getElementById("live-conf").innerText = sig.calibrated_conf ? `${(sig.calibrated_conf * 100).toFixed(1)}%` : "--%";
  document.getElementById("live-advice").innerText = sig.advice || "--";
}

// 页面 1: 健康状态加载
async function loadHealthData() {
  try {
    const res = await fetch("/api/system/health");
    const d = await res.json();
    document.getElementById("dash-today-count").innerText = d.today_periods_count || 0;
    document.getElementById("dash-evolve-state").innerText = d.evolve_state || "IDLE";
    document.getElementById("dash-rss").innerText = `${d.rss_mb} MB`;
    document.getElementById("dash-disk").innerText = `${d.disk_free_gb} GB`;
    document.getElementById("dash-uptime").innerText = `${d.uptime_seconds} 秒`;
  } catch (e) {}
}

// 页面 3: 期数列表加载
async function loadPeriodsData() {
  const sym = document.getElementById("filter-symbol").value;
  const dir = document.getElementById("filter-dir").value;
  const ano = document.getElementById("filter-anomaly").value;

  let url = `/api/periods?page_size=30`;
  if (sym) url += `&symbol=${sym}`;
  if (dir) url += `&direction=${dir}`;
  if (ano) url += `&is_anomaly=${ano}`;

  try {
    const res = await fetch(url);
    const d = await res.json();
    const tbody = document.getElementById("period-table-body");
    tbody.innerHTML = "";
    (d.data || []).forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${r.period_id}</td>
        <td><strong>${r.symbol}</strong></td>
        <td>${r.open_price}</td>
        <td>${r.close_price}</td>
        <td class="${r.direction === 'UP' ? 'tag-up' : 'tag-down'}">${r.direction}</td>
        <td>${r.amplitude_pct.toFixed(2)}%</td>
        <td>${r.final_up_odds}</td>
        <td>${r.final_down_odds}</td>
        <td>${r.is_anomaly ? '<span class="tag-blocked">异常局</span>' : '正常'}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {}
}

// 页面 4: 规则列表加载与启停
async function loadRulesData() {
  try {
    const res = await fetch("/api/rules");
    const d = await res.json();
    const tbody = document.getElementById("rules-table-body");
    tbody.innerHTML = "";
    (d.rules || []).forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${r.rule_id}</td>
        <td>${r.name}</td>
        <td>${r.symbol}</td>
        <td>${r.sample_count}</td>
        <td>${(r.win_rate * 100).toFixed(1)}%</td>
        <td>${(r.confidence * 100).toFixed(1)}%</td>
        <td><strong>${r.reputation_score}</strong></td>
        <td><span class="${r.status === 'ACTIVE' ? 'tag-active' : 'tag-blocked'}">${r.status}</span></td>
        <td><button class="btn" onclick="toggleRule('${r.rule_id}')">切换状态</button></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {}
}

async function toggleRule(ruleId) {
  await fetch(`/api/rules/${ruleId}/toggle`, { method: "POST" });
  loadRulesData();
}

// 页面 5: 长跑一键启停与回测
async function startEvolveRun() {
  const target = parseFloat(document.getElementById("evolve-target").value);
  const res = await fetch("/api/evolve/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_confidence: target, max_rounds: 30 })
  });
  const d = await res.json();
  document.getElementById("evolve-status-text").innerText = d.status;
}

async function stopEvolveRun() {
  await fetch("/api/evolve/stop", { method: "POST" });
  document.getElementById("evolve-status-text").innerText = "STOPPING";
}

async function submitBacktest() {
  const sym = document.getElementById("bt-symbol").value;
  const conf = parseFloat(document.getElementById("bt-conf").value);
  const res = await fetch("/api/backtest/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbol: sym,
      date_start: "2026-10-01T00:00:00Z",
      date_end: "2026-10-11T00:00:00Z",
      min_confidence: conf
    })
  });
  const d = await res.json();
  document.getElementById("bt-total").innerText = d.total_trades;
  document.getElementById("bt-winrate").innerText = `${(d.win_rate * 100).toFixed(1)}%`;
  document.getElementById("bt-profit").innerText = `+${d.net_profit}`;
  document.getElementById("bt-drawdown").innerText = `${d.max_drawdown_pct}%`;
}

// 页面 6: SHAP 数据
async function loadShapData() {
  try {
    const res = await fetch("/api/models/metrics/shap");
    const d = await res.json();
    const tbody = document.getElementById("shap-table-body");
    tbody.innerHTML = "";
    (d.features || []).forEach(f => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${f.name}</strong></td>
        <td>${(f.importance * 100).toFixed(1)}%</td>
        <td>${f.desc}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {}
}

// 页面 7: 规律信息量地图
async function loadAnalysisData() {
  try {
    const res = await fetch("/api/analysis/information_map");
    const d = await res.json();
    const tbody = document.getElementById("info-map-body");
    tbody.innerHTML = "";
    (d.slices || []).forEach(s => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${s.slice}</strong></td>
        <td>${s.info_gain}</td>
        <td>${(s.win_rate_conditioned * 100).toFixed(1)}%</td>
        <td>${s.desc}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {}
}

// 页面 8: 一键导出诊断包
async function downloadDiagnostics() {
  const res = await fetch("/api/system/diagnostics");
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `gate_diagnostics_${Date.now()}.json`;
  a.click();
}

function triggerQuickCheck() {
  loadHealthData();
}

// 默认首屏加载
loadHealthData();
