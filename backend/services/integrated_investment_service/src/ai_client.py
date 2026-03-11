"""
Gemini AI 클라이언트 — 텍스트 전용 (이미지 없음)
순수 펀더멘털 분석용
"""

import os
import re
import time
from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, LANGUAGE
from src.system_prompt import WILLIAM_ONEIL_FUNDAMENTAL_PERSONA


def _get_language_instruction() -> str:
    """분석 프롬프트에 삽입할 언어 지시 생성"""
    if LANGUAGE == "ko":
        return (
            "\n\nIMPORTANT - LANGUAGE INSTRUCTION:\n"
            "You MUST write your entire analysis in Korean (한국어).\n"
            "Keep technical terms in English where appropriate "
            "(e.g., CAN SLIM, RS Rating, EPS, ROE, P/E, "
            "Accumulation, Distribution).\n"
            "All explanatory text, commentary, and conclusions must be in Korean.\n"
        )
    return ""


def _remove_emojis(text: str) -> str:
    """이모지만 선택적으로 제거하고 한국어/일본어/중국어 등 모든 유니코드 문자 보존"""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U0000FE00-\U0000FE0F"
        "\U0000200D"
        "\U00002B50"
        "\U00002B55"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)


def analyze_fundamentals_with_ai(ticker: str, prompt_text: str, provider: str = "gemini") -> str:
    """
    텍스트 전용 Gemini 호출 — 순수 펀더멘털 분석

    Args:
        ticker: 종목 코드
        prompt_text: CAN SLIM 데이터 통합 텍스트

    Returns:
        AI 분석 결과 텍스트
    """
    provider = (provider or "gemini").lower()
    print(f"[*] {provider.upper()} AI 펀더멘털 분석 중...")

    lang_instruction = _get_language_instruction()

    user_message = f"""다음은 {ticker}의 CAN SLIM 펀더멘털 데이터입니다.
각 요소별 O'Neil 원문 규칙과 함께 실제 데이터가 제공됩니다.
사전 점수 계산 없이 원본 데이터와 O'Neil 규칙을 직접 대조하여 판단하십시오.

{prompt_text}

{lang_instruction}

위 데이터를 바탕으로 {ticker}에 대한 CAN SLIM 기본적 분석 보고서를 작성하십시오.
차트 분석, 매수 시점, 피벗 포인트는 포함하지 마십시오.
순수 펀더멘털 평가만 제공하십시오."""

    max_retries = 2
    for attempt in range(max_retries):
        try:
            if provider == "gemini":
                client = genai.Client(api_key=GEMINI_API_KEY)
                response = client.models.generate_content(
                    model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=WILLIAM_ONEIL_FUNDAMENTAL_PERSONA,
                    )
                )
                output_text = response.text
            elif provider == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                resp = client.chat.completions.create(
                    model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[
                        {"role": "system", "content": WILLIAM_ONEIL_FUNDAMENTAL_PERSONA},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.2,
                )
                output_text = resp.choices[0].message.content
            elif provider == "claude":
                from anthropic import Anthropic
                client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
                resp = client.messages.create(
                    model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
                    max_tokens=4000,
                    system=WILLIAM_ONEIL_FUNDAMENTAL_PERSONA,
                    messages=[{"role": "user", "content": user_message}],
                )
                output_text = "".join(
                    block.text for block in resp.content if getattr(block, "type", "") == "text"
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")

            if output_text:
                print("[OK] 펀더멘털 분석 완료!")
                return _remove_emojis(output_text)
            raise ValueError(f"{provider} 응답이 비어있습니다.")

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[WARN] {provider.upper()} API 오류, 재시도 중... ({e})")
                time.sleep(3)
            else:
                error_msg = f"[ERROR] {provider.upper()} AI 분석 실패: {e}"
                print(error_msg)
                return f"AI 분석을 완료하지 못했습니다. 오류: {e}\n수집된 데이터는 저장됩니다."


def analyze_fundamentals_with_gemini(ticker: str, prompt_text: str) -> str:
    """하위 호환용 래퍼"""
    return analyze_fundamentals_with_ai(ticker, prompt_text, provider="gemini")
