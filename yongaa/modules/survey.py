"""
설문지 로더 & 실행기
- data/{market}_survey.json 을 읽어 터미널에서 문답 진행
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load_survey(market: str) -> dict:
    path = DATA_DIR / f"{market}_survey.json"
    if not path.exists():
        raise FileNotFoundError(f"설문 파일 없음: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_survey(survey: dict) -> dict:
    title = survey.get("title", "설문지")
    note  = survey.get("note", "")

    print("\n" + "=" * 62)
    print(f"  {title}")
    print("=" * 62)
    if note:
        print(f"\n  💡 {note}")
    print("\n  숫자 선택 또는 직접 입력 모두 가능합니다.\n")

    answers     = {}
    last_part   = None

    for q in survey.get("questions", []):
        # 파트 구분선
        part = q.get("part", "")
        if part and part != last_part:
            print(f"\n  ── {part} ──\n")
            last_part = part

        # 질문 출력
        print(f"  {q['text']}")
        for opt in q.get("options", []):
            print(f"    {opt}")
        print(f"    [직접 입력/기타]:")

        ans = input("  → ").strip()
        answers[q["id"]] = ans
        print()

    return answers
