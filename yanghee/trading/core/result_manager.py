import json
import os
import re
from datetime import datetime

from core.config import RESULTS_DIR


def save_analysis_result(
    ticker: str,
    analysis: str,
    interval: str,
    pattern_result: dict = None,
    fundamental_result: dict = None,
    rs_info: dict = None,
) -> str:
    """
    AI 분석 결과를 JSON 파일로 저장

    Returns:
        저장된 파일 경로
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{ticker}_{timestamp}.json"
    filepath = os.path.join(RESULTS_DIR, filename)

    # verdict 추출
    verdict = "UNKNOWN"
    for pattern in [
        r'"verdict":\s*"([^"]+)"',
        r'(?:FINAL VERDICT|최종 판단)[:\s]*(BUY NOW|WATCH & WAIT|AVOID)',
        r'\*\*(BUY NOW|WATCH & WAIT|AVOID)\*\*',
    ]:
        m = re.search(pattern, analysis)
        if m:
            verdict = m.group(1)
            break

    result = {
        "ticker": ticker,
        "timestamp": timestamp,
        "interval": "weekly" if interval == "1wk" else "daily",
        "verdict": verdict,
        "ai_analysis": analysis,
        "pattern_detection": pattern_result,
        "fundamental": fundamental_result,
        "rs_info": rs_info,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"[OK] 분석 결과 저장: {filepath}")
    return filepath
