// 백엔드 API URL (Cloud Run에 배포된 주소)
const API_URL = "https://oneil-ai-1073242702988.asia-northeast3.run.app";

// 로딩 메시지 업데이트용
const LOADING_MESSAGES = [
    "서버를 깨우는 중...",
    "주가 데이터를 다운로드하는 중...",
    "차트를 생성하는 중...",
    "AI가 차트를 분석하는 중...",
    "거의 완료되었습니다...",
];

function updateLoadingMessage(index) {
    const el = document.querySelector("#loading p");
    if (el && index < LOADING_MESSAGES.length) {
        el.textContent = LOADING_MESSAGES[index];
    }
}

async function analyzeStock() {
    const ticker = document.getElementById("ticker").value.trim();
    if (!ticker) {
        showError("종목 코드를 입력해주세요. (예: AAPL, MSFT, 005930.KS)");
        return;
    }

    const mode = document.getElementById("mode").value;
    const interval = document.getElementById("interval").value;

    // UI 상태 변경
    const btn = document.getElementById("analyze-btn");
    btn.disabled = true;
    btn.textContent = "분석 중...";
    hide("error");
    hide("result");
    show("loading");

    // 로딩 메시지 순차 업데이트
    let msgIndex = 0;
    updateLoadingMessage(msgIndex);
    const msgTimer = setInterval(() => {
        msgIndex++;
        updateLoadingMessage(msgIndex);
    }, 10000);

    try {
        // Step 1: 백엔드 깨우기 (health check)
        try {
            await fetch(`${API_URL}/health`, { method: "GET" });
        } catch (e) {
            // health 실패해도 계속 진행 (서버가 깨어나는 중)
        }

        // Step 2: 분석 요청 (3분 타임아웃)
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 180000);

        const response = await fetch(`${API_URL}/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker, mode, interval }),
            signal: controller.signal,
        });
        clearTimeout(timeout);

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || `서버 오류 (${response.status})`);
        }

        const data = await response.json();
        renderResult(data);
    } catch (err) {
        if (err.name === "AbortError") {
            showError("분석 시간이 초과되었습니다 (3분). 다시 시도해주세요.");
        } else if (err.message === "Failed to fetch") {
            showError("서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.");
        } else {
            showError(err.message || "알 수 없는 오류가 발생했습니다.");
        }
    } finally {
        clearInterval(msgTimer);
        btn.disabled = false;
        btn.textContent = "분석 시작";
        hide("loading");
    }
}

function renderResult(data) {
    // 패턴 카드
    const cardsEl = document.getElementById("pattern-cards");
    cardsEl.innerHTML = "";

    if (data.pattern_data) {
        const pd = data.pattern_data;

        // 패턴 타입
        if (pd.best_pattern) {
            addCard(cardsEl, "패턴", pd.best_pattern.type || "N/A", "");
            if (pd.best_pattern.quality_score != null) {
                const score = pd.best_pattern.quality_score;
                const color = score >= 70 ? "green" : score >= 50 ? "yellow" : "red";
                addCard(cardsEl, "품질 점수", score + "/100", color);
            }
            if (pd.best_pattern.pivot_point != null) {
                addCard(cardsEl, "피봇 포인트", "$" + pd.best_pattern.pivot_point.toFixed(2), "");
            }
        }

        // RS 분석
        if (pd.rs_analysis) {
            if (pd.rs_analysis.rs_rating != null) {
                const rs = pd.rs_analysis.rs_rating;
                const color = rs >= 80 ? "green" : rs >= 50 ? "yellow" : "red";
                addCard(cardsEl, "RS Rating", rs, color);
            }
        }

        // 거래량 분석
        if (pd.volume_analysis && pd.volume_analysis.recent_volume_trend) {
            const trend = pd.volume_analysis.recent_volume_trend;
            const color = trend === "ACCUMULATION" ? "green" : trend === "DISTRIBUTION" ? "red" : "yellow";
            addCard(cardsEl, "거래량 추세", trend, color);
        }
    }

    // 차트 이미지
    const chartEl = document.getElementById("chart-container");
    if (data.chart_base64) {
        chartEl.innerHTML = `<img src="${data.chart_base64}" alt="${data.ticker} 차트">`;
    } else {
        chartEl.innerHTML = "";
    }

    // AI 분석 텍스트 (마크다운 → HTML 간단 변환)
    const analysisEl = document.getElementById("analysis");
    analysisEl.innerHTML = formatAnalysis(data.analysis);

    // 타임스탬프
    document.getElementById("timestamp").textContent =
        `${data.ticker} · ${data.mode.toUpperCase()} · ${new Date(data.timestamp).toLocaleString("ko-KR")}`;

    show("result");
}

function formatAnalysis(text) {
    if (!text) return "<p>분석 결과가 없습니다.</p>";

    return text
        // ## 헤더
        .replace(/^### (.+)$/gm, "<h3>$1</h3>")
        .replace(/^## (.+)$/gm, "<h2>$1</h2>")
        // **볼드**
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        // 줄바꿈
        .replace(/\n/g, "<br>");
}

function addCard(container, label, value, colorClass) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
        <div class="card-label">${label}</div>
        <div class="card-value ${colorClass}">${value}</div>
    `;
    container.appendChild(card);
}

function showError(message) {
    const el = document.getElementById("error");
    el.textContent = message;
    el.classList.remove("hidden");
}

function show(id) {
    document.getElementById(id).classList.remove("hidden");
}

function hide(id) {
    document.getElementById(id).classList.add("hidden");
}

// Enter 키로 분석 실행
document.getElementById("ticker").addEventListener("keydown", (e) => {
    if (e.key === "Enter") analyzeStock();
});
