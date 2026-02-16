"""
History Analyzer — 과거 분석 기록 학습 모듈

같은 ticker의 과거 분석 JSON을 로드하여:
1. 당시 예측(verdict) vs 실제 수익률 계산
2. 자주 감지된 패턴 / 반복되는 결함 파악
3. AI 프롬프트에 학습 컨텍스트로 주입
"""

import os
import json
import glob
from datetime import datetime
from typing import List, Dict, Optional

from core.config import RESULTS_DIR


def load_past_analyses(ticker: str) -> List[Dict]:
    """
    같은 ticker의 과거 분석 JSON 파일들을 시간순으로 로드

    Returns:
        과거 분석 딕셔너리 리스트 (오래된 순)
    """
    pattern = os.path.join(RESULTS_DIR, f"{ticker}_*.json")
    files = sorted(glob.glob(pattern))  # 파일명 = timestamp 순

    records = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            records.append(data)
        except Exception:
            pass

    return records


def compute_actual_return(past_price: float, current_price: float) -> Optional[float]:
    """과거 분석 시점 가격 → 현재 가격 수익률(%)"""
    if past_price and past_price > 0 and current_price and current_price > 0:
        return round((current_price - past_price) / past_price * 100, 1)
    return None


def extract_price_from_analysis(record: Dict) -> Optional[float]:
    """분석 JSON에서 당시 현재가 추출"""
    # pattern_detection → rs_analysis → rs_vs_sp500 → 주가 계산은 어렵
    # fundamental → S → current_price 또는 pattern_detection summary에서 추출
    try:
        # 방법 1: fundamental S 데이터
        s_data = record.get("fundamental", {}).get("data", {}).get("S", {})
        price = s_data.get("current_price") or s_data.get("regularMarketPrice")
        if price:
            return float(price)
    except Exception:
        pass

    try:
        # 방법 2: pattern_detection summary 텍스트에서 "Current Price: $xxx" 파싱
        summary = record.get("pattern_detection", {}).get("summary", "")
        import re
        m = re.search(r"Current Price[:\s]+\$?([\d.]+)", summary)
        if m:
            return float(m.group(1))
    except Exception:
        pass

    return None


def build_history_context(ticker: str, current_price: float) -> str:
    """
    과거 분석 기록을 AI 프롬프트용 텍스트로 변환

    Args:
        ticker: 종목 코드
        current_price: 현재 가격

    Returns:
        프롬프트에 삽입할 히스토리 컨텍스트 문자열
    """
    records = load_past_analyses(ticker)
    if not records:
        return ""

    # 최근 5개만 사용
    recent = records[-5:]

    lines = [
        "## PAST ANALYSIS HISTORY (Learning Context)",
        f"This stock ({ticker}) has been analyzed {len(records)} time(s) before.",
        "Use this to calibrate your current judgment — learn from what was right and wrong.",
        "",
    ]

    correct = 0
    total_with_price = 0

    for r in recent:
        ts = r.get("timestamp", "unknown")
        verdict = r.get("verdict", "UNKNOWN")
        interval = r.get("interval", "weekly")

        past_price = extract_price_from_analysis(r)
        actual_return = None
        if past_price:
            actual_return = compute_actual_return(past_price, current_price)
            total_with_price += 1

        # 예측 정확도 판정
        accuracy = ""
        if actual_return is not None:
            if verdict == "AVOID" and actual_return < -3:
                accuracy = "✓ CORRECT (price fell)"
                correct += 1
            elif verdict == "BUY NOW" and actual_return > 5:
                accuracy = "✓ CORRECT (price rose)"
                correct += 1
            elif verdict == "WATCH & WAIT":
                accuracy = "(neutral — hard to judge)"
            elif verdict in ("AVOID",) and actual_return > 10:
                accuracy = "✗ WRONG (price rose despite AVOID)"
            elif verdict in ("BUY NOW",) and actual_return < -5:
                accuracy = "✗ WRONG (price fell despite BUY NOW)"
            else:
                accuracy = f"(mixed — {actual_return:+.1f}%)"

        # 패턴 정보
        bp = r.get("pattern_detection", {}).get("best_pattern") or {}
        pattern_str = f"{bp.get('type', 'None')} (Q:{bp.get('quality_score', 0)}, Stage:{r.get('pattern_detection', {}).get('base_stage', {}).get('estimated_stage', '?')})" if bp else "No pattern"

        # RS 정보
        rs = r.get("rs_info", {}) or {}
        rs_str = f"RS {rs.get('rs_rating', 'N/A')} ({rs.get('rs_trend', '')})" if rs.get("rs_rating") else ""

        line = f"- [{ts}] Verdict: {verdict}"
        if past_price:
            line += f" | Price at time: ${past_price:.2f}"
        if actual_return is not None:
            line += f" | Actual return since: {actual_return:+.1f}%"
        if accuracy:
            line += f" | {accuracy}"
        line += f"\n  Pattern: {pattern_str}"
        if rs_str:
            line += f" | {rs_str}"

        # 주요 결함
        faults = r.get("pattern_detection", {}).get("pattern_faults", [])
        if faults:
            line += f"\n  Faults noted: {'; '.join(faults[:2])}"

        lines.append(line)

    # 정확도 요약
    if total_with_price > 0:
        acc_pct = round(correct / total_with_price * 100)
        lines.append("")
        lines.append(f"Past prediction accuracy for {ticker}: {correct}/{total_with_price} ({acc_pct}%)")

    lines.append("")
    lines.append("NOTE: If past AVOID calls were proven correct (price fell), apply the same rigor now.")
    lines.append("If past calls were wrong, examine why and adjust your current assessment accordingly.")

    return "\n".join(lines)


def get_history_summary(ticker: str) -> Dict:
    """
    콘솔 출력용 히스토리 요약

    Returns:
        {'count': int, 'last_verdict': str, 'last_date': str, 'verdicts': Counter}
    """
    records = load_past_analyses(ticker)
    if not records:
        return {"count": 0}

    from collections import Counter
    verdicts = Counter(r.get("verdict", "UNKNOWN") for r in records)
    last = records[-1]

    return {
        "count": len(records),
        "last_verdict": last.get("verdict", "UNKNOWN"),
        "last_date": last.get("timestamp", ""),
        "verdicts": dict(verdicts),
    }
