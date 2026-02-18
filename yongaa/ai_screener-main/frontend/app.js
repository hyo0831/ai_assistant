const state = {
  market: null,
  horizon: null,
  goal: "",
  theme: "",
  themeMode: "light",
};

const apiBase = "http://localhost:8000";

const helpBtn = document.getElementById("helpBtn");
const helpModal = document.getElementById("helpModal");
const helpBackdrop = document.getElementById("helpBackdrop");
const helpClose = document.getElementById("helpClose");
const appRoot = document.getElementById("appRoot");
const themeToggle = document.getElementById("themeToggle");
const langToggle = document.getElementById("langToggle");

const goalInput = document.getElementById("goalInput");
const themeInput = document.getElementById("themeInput");
const runBtn = document.getElementById("runBtn");
const requiredHint = document.getElementById("requiredHint");
const loadingWrap = document.getElementById("loadingWrap");
const loadingText = document.getElementById("loadingText");
const progressBar = document.getElementById("progressBar");

const resultSection = document.getElementById("resultSection");
const formulaTitle = document.getElementById("formulaTitle");
const formulaDesc = document.getElementById("formulaDesc");
const asOf = document.getElementById("asOf");
const noteEl = document.getElementById("note");
const rulesList = document.getElementById("rulesList");
const rankingList = document.getElementById("rankingList");
const themeHint = document.getElementById("themeHint");

function init() {
  setLang("ko");
  if (helpModal) {
    helpModal.hidden = true;
    helpModal.classList.add("hidden");
    helpModal.style.display = "none";
  }
  bindChipGroup("marketChips", "market");
  bindChipGroup("horizonChips", "horizon");
  bindModal();
  bindThemeToggle();
  bindLangToggle();
  bindRun();
}

function bindChipGroup(id, key) {
  const group = document.getElementById(id);
  group.querySelectorAll(".chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      group.querySelectorAll(".chip").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state[key] = btn.getAttribute("data-value");
    });
  });
}

function bindModal() {
  if (!helpBtn || !helpModal || !helpBackdrop || !helpClose) return;
  const open = () => {
    helpModal.hidden = false;
    helpModal.classList.remove("hidden");
    helpModal.style.display = "grid";
    if (appRoot) appRoot.inert = true;
    helpClose.focus();
  };
  const close = () => {
    helpModal.classList.add("hidden");
    helpModal.hidden = true;
    helpModal.style.display = "none";
    if (appRoot) appRoot.inert = false;
    helpBtn.focus();
  };

  helpBtn.addEventListener("click", open);
  helpBackdrop.addEventListener("click", close);
  helpClose.addEventListener("click", close);
}

function bindThemeToggle() {
  themeToggle.addEventListener("click", () => {
    state.themeMode = state.themeMode === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", state.themeMode);
    themeToggle.textContent = state.themeMode === "light" ? I18N[getLang()].toggleTheme : "Light";
  });
}

function bindLangToggle() {
  langToggle.addEventListener("click", () => {
    const next = getLang() === "ko" ? "en" : "ko";
    setLang(next);
    themeToggle.textContent = state.themeMode === "light" ? I18N[next].toggleTheme : "Light";
  });
}

function bindRun() {
  runBtn.addEventListener("click", async () => {
    state.goal = goalInput.value.trim();
    state.theme = themeInput.value.trim();

    const missing = [];
    if (!state.market) missing.push(getLang() === "ko" ? "시장" : "market");
    if (!state.goal) missing.push(getLang() === "ko" ? "목표" : "goal");
    if (!state.horizon) missing.push(getLang() === "ko" ? "기간" : "horizon");

    if (missing.length) {
      requiredHint.textContent = I18N[getLang()].missingFields + missing.join(", ");
      requiredHint.style.color = "#ef4444";
      return;
    }

    requiredHint.textContent = I18N[getLang()].requiredHint;
    requiredHint.style.color = "";

    const payload = {
      market: state.market,
      goal: state.goal,
      horizon: state.horizon,
      theme: state.theme || null,
    };

    let timer = null;
    try {
      runBtn.disabled = true;
      runBtn.textContent = I18N[getLang()].analyzing;
      if (loadingWrap) loadingWrap.classList.remove("hidden");
      if (progressBar) progressBar.style.width = "0%";
      if (loadingText) loadingText.textContent = `${I18N[getLang()].analyzing} 0%`;

      let pct = 0;
      timer = setInterval(() => {
        pct = Math.min(95, pct + Math.random() * 8);
        if (progressBar) progressBar.style.width = `${pct.toFixed(0)}%`;
        if (loadingText) loadingText.textContent = `${I18N[getLang()].analyzing} ${pct.toFixed(0)}%`;
      }, 400);

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 20000);
      const res = await fetch(`${apiBase}/api/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      }).finally(() => clearTimeout(timeout));
      if (!res.ok) throw new Error("API error");
      const data = await res.json();
      renderResult(data);
    } catch (err) {
      requiredHint.textContent = getLang() === "ko" ? "백엔드 서버를 확인해 주세요." : "Please check backend server.";
      requiredHint.style.color = "#ef4444";
    } finally {
      if (timer) clearInterval(timer);
      if (progressBar) progressBar.style.width = "100%";
      if (loadingText) loadingText.textContent = I18N[getLang()].done;
      setTimeout(() => {
        if (loadingWrap) loadingWrap.classList.add("hidden");
      }, 600);
      runBtn.disabled = false;
      runBtn.textContent = I18N[getLang()].run;
    }
  });
}

function renderResult(data) {
  resultSection.classList.remove("hidden");

  const intent = data.intent;
  const rec = data.recommendation;

  formulaTitle.textContent = `${rec.formula_name}`;
  const horizonNote = horizonHint(intent.horizon);
  if (getLang() === "en") {
    formulaDesc.textContent = `To find ${intent.goal} picks in ${intent.market}, use the '${rec.formula_name}' formula. ${horizonNote}`;
  } else {
    formulaDesc.textContent = `${intent.market}에서 ${intent.goal} 종목을 찾기 위해 '${rec.formula_name}' 조건식으로 검색하시면 됩니다. ${horizonNote}`;
  }

  rulesList.innerHTML = "";
  rec.rules.forEach((rule) => {
    const key = rule.key;
    const name = rec.indicator_help[key] ? rec.indicator_help[key] : key;
    const explain = rec.explanation_by_rule[key] || "";
    const thresholdLine = ruleLine(rule);
    const el = document.createElement("div");
    el.className = "rule-item";
    el.innerHTML = `
      <div class="rule-title" data-tip="${escapeHtml(name)}">${escapeHtml(keyLabel(key))}</div>
      <div class="rule-desc">${escapeHtml(explain)}</div>
      <div class="muted">${escapeHtml(thresholdLine)}</div>
      <div class="muted">${escapeHtml(name)}</div>
    `;
    rulesList.appendChild(el);
  });

  themeHint.textContent = rec.theme_hint ? rec.theme_hint : "";
  if (asOf) asOf.textContent = `as of ${data.as_of}`;
  if (noteEl) noteEl.textContent = data.note ? data.note : "";

  rankingList.innerHTML = "";
  data.top.forEach((row, idx) => {
    const item = document.createElement("div");
    item.className = "rank-item";
    const breakdownHtml = renderBreakdown(row.rule_breakdown, row.theme_brief, row.news_items);
    item.innerHTML = `
      <div class="rank-head">#${idx + 1} ${escapeHtml(row.name)} <span>${escapeHtml(row.symbol)}</span></div>
      <div class="rank-scores">
        <span>${I18N[getLang()].conditionScore}: ${row.condition_score.toFixed(0)}</span>
        <span>${I18N[getLang()].themeScore}: ${row.theme_score.toFixed(0)}</span>
        <span>${I18N[getLang()].totalScore}: ${row.total_score.toFixed(0)}</span>
      </div>
      <div class="muted">${escapeHtml(row.why)}</div>
      <div class="detail hidden">${breakdownHtml}</div>
    `;
    item.addEventListener("click", () => {
      const detail = item.querySelector(".detail");
      if (detail) detail.classList.toggle("hidden");
    });
    rankingList.appendChild(item);
  });
}

function keyLabel(key) {
  const map = {
    volume: "거래량",
    value: "거래대금",
    foreign_own: "외국인소진율",
    per_low: "저 PER",
    pbr_low: "저 PBR",
    roe_high: "고 ROE",
    ma_cross: "이평선 크로스",
    rsi_range: "RSI 범위",
    obv: "OBV",
  };
  if (getLang() === "ko") return map[key] || key;
  const mapEn = {
    volume: "Volume",
    value: "Value",
    foreign_own: "Foreign Ownership",
    per_low: "Low PER",
    pbr_low: "Low PBR",
    roe_high: "High ROE",
    ma_cross: "MA Cross",
    rsi_range: "RSI Range",
    obv: "OBV",
  };
  return mapEn[key] || key;
}

function horizonHint(horizon) {
  if (getLang() === "en") {
    if (horizon === "day") return "For day trades, focus on intraday (1-5m) charts.";
    if (horizon === "swing") return "For swing trades, use daily charts with short-term setups.";
    if (horizon === "long") return "For long term, use weekly/monthly trends and fundamentals.";
    return "";
  }
  if (horizon === "day") return "단타라면 분봉(1~5분) 위주로 체크하세요.";
  if (horizon === "swing") return "스윙은 일봉 중심으로 단기 추세를 확인하세요.";
  if (horizon === "long") return "중장기는 주봉/월봉과 펀더멘털을 함께 보세요.";
  return "";
}

function ruleLine(rule) {
  const key = rule.key;
  if (rule.op === "between") {
    return `${keyLabel(key)}: ${rule.min} ~ ${rule.max}`;
  }
  if (rule.op === "cross") {
    const fast = rule.meta?.fast || "5";
    const slow = rule.meta?.slow || "20";
    return `${keyLabel(key)}: ${fast}/${slow} 골든크로스`;
  }
  if (rule.value !== null && rule.value !== undefined) {
    return `${keyLabel(key)}: ${formatNum(rule.value)} ${rule.op}`;
  }
  return `${keyLabel(key)} 조건`;
}

function renderBreakdown(breakdown, themeBrief, newsItems) {
  if (!breakdown) breakdown = {};
  const lines = Object.entries(breakdown).map(([key, v]) => {
    const pass = v.passed ? "PASS" : "FAIL";
    if (v.op === "between") {
      return `${keyLabel(key)}: ${formatNum(v.value)} (범위 ${v.min}-${v.max}) [${pass}]`;
    }
    if (v.op === "cross") {
      return `${keyLabel(key)}: ${formatNum(v.value)} (크로스) [${pass}]`;
    }
    return `${keyLabel(key)}: ${formatNum(v.value)} (기준 ${formatNum(v.threshold)} ${v.op}) [${pass}]`;
  });
  const themeLine = themeBrief ? `<div class="muted">테마 노트(추정): ${escapeHtml(themeBrief)}</div>` : "";
  const newsList = Array.isArray(newsItems) && newsItems.length
    ? `<div class="muted">관련 뉴스</div><ul class="news-list">${newsItems.map(n => `<li><a href="${escapeAttr(n.link)}" target="_blank" rel="noopener">${escapeHtml(n.title || "")}</a></li>`).join("")}</ul>`
    : "";
  return `<div class="muted">${lines.join("<br>")}</div>${themeLine}${newsList}`;
}

function formatNum(n) {
  if (n === null || n === undefined) return "-";
  const num = Number(n);
  if (Number.isNaN(num)) return String(n);
  return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;");
}

function escapeAttr(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/\"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

init();
