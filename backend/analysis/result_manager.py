"""
분석 결과 JSON 저장
"""

import json
import os
from datetime import datetime

from analysis.config import RESULTS_DIR


def save_result(ticker: str, analysis: str, fundamental_data: dict = None) -> str:
    """
    AI 분석 결과를 JSON 파일로 저장

    Returns:
        저장된 파일 경로 (실패 시 빈 문자열)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{ticker}_{timestamp}_fundamental.json"
    filepath = os.path.join(RESULTS_DIR, filename)

    result = {
        "ticker": ticker,
        "timestamp": timestamp,
        "mode": "fundamental_analysis",
        "ai_analysis": analysis,
        "fundamental_data": fundamental_data,
    }

    try:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"[OK] 분석 결과 저장: {filepath}")
        return filepath
    except Exception as e:
        print(f"[WARN] 결과 저장 실패: {e}")
        return ''
