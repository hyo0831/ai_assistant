const I18N = {
  ko: {
    title: "AI 투자도우미",
    subtitle: "조건검색편",
    help: "도움말",
    toggleTheme: "다크",
    heroTitle: "조건검색을 한 번에, 쉽고 빠르게",
    heroDesc: "시장·목표·기간만 알려주면 맞춤형 조건식을 추천합니다.",
    goalLabel: "어떤 주식을 찾고 싶나요?",
    goalPlaceholder: "예: 유동성 높은 단타 종목",
    goalExample: "예시 검색어: \"KOSDAQ에서 모멘텀 좋은 스윙 종목\"",
    marketTitle: "어디 시장?",
    horizonTitle: "투자 기간",
    themeTitle: "최근 이슈/테마(선택)",
    themePlaceholder: "예: AI 반도체, 2차전지",
    themeNote: "테마를 적으면 테마 적합 점수를 함께 계산합니다.",
    run: "맞춤 조건식 추천받기",
    requiredHint: "시장/목표/기간은 꼭 입력해 주세요.",
    recommendedRules: "추천 조건식",
    topRank: "Top 랭킹",
    helpTitle: "도움말",
    helpStep1: "1. 시장, 목표, 투자기간을 선택하세요.",
    helpStep2: "2. 테마가 있다면 입력하고 추천을 눌러주세요.",
    helpStep3: "3. 조건식과 상위 종목을 확인하세요.",
    helpIntroTitle: "조건은 총 9가지입니다.",
    helpIntro: "유동성(거래량, 거래대금, 외국인소진율), 마법공식(저 PER, 저 PBR, 고 ROE), 기술(이평선 크로스, RSI 범위, OBV)로 구성됩니다.",
    disclaimer: "이 서비스는 교육/연구 목적의 예시이며 투자 손익은 본인 책임입니다.",
    missingFields: "아래 항목을 채워주세요: ",
    selecting: "선택됨",
    score: "점수",
    conditionScore: "조건",
    themeScore: "테마",
    totalScore: "종합",
    why: "설명",
    analyzing: "분석 중...",
    done: "완료",
  },
  en: {
    title: "AI Investment Helper",
    subtitle: "Condition Screener",
    help: "Help",
    toggleTheme: "Dark",
    heroTitle: "Screener setup, clean and fast",
    heroDesc: "Tell us market, goal, and horizon. We build a custom formula.",
    goalLabel: "What kind of stock are you looking for?",
    goalPlaceholder: "e.g., high-liquidity day trades",
    goalExample: "Example: \"Momentum swing picks in KOSDAQ\"",
    marketTitle: "Which market?",
    horizonTitle: "Investment horizon",
    themeTitle: "Recent theme (optional)",
    themePlaceholder: "e.g., AI chips, EV battery",
    themeNote: "Theme input adds a theme-fit score.",
    run: "Get Custom Formula",
    requiredHint: "Market/goal/horizon are required.",
    recommendedRules: "Recommended Rules",
    topRank: "Top Ranking",
    helpTitle: "Help",
    helpStep1: "1. Choose market, goal, and horizon.",
    helpStep2: "2. Add a theme if needed, then run.",
    helpStep3: "3. Review formula and ranked picks.",
    helpIntroTitle: "There are 9 conditions.",
    helpIntro: "Liquidity (volume, value, foreign ownership), Magic Formula (low PER, low PBR, high ROE), Technical (MA cross, RSI range, OBV).",
    disclaimer: "This is an educational prototype. You are responsible for any investment outcomes.",
    missingFields: "Please fill: ",
    selecting: "Selected",
    score: "Score",
    conditionScore: "Condition",
    themeScore: "Theme",
    totalScore: "Total",
    why: "Why",
    analyzing: "Analyzing...",
    done: "Done",
  }
};

let currentLang = "ko";

function setLang(lang) {
  currentLang = lang;
  document.documentElement.lang = lang === "ko" ? "ko" : "en";

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (I18N[lang][key]) el.textContent = I18N[lang][key];
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (I18N[lang][key]) el.setAttribute("placeholder", I18N[lang][key]);
  });

  const langToggle = document.getElementById("langToggle");
  if (langToggle) langToggle.textContent = lang === "ko" ? "EN" : "KR";
}

window.I18N = I18N;
window.setLang = setLang;
window.getLang = () => currentLang;
