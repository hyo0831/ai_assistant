"""
피드백 관리 시스템
사용자 피드백을 저장하고 AI 학습에 활용
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, List


class FeedbackManager:
    """피드백 저장 및 관리"""

    def __init__(self, feedback_dir: str = "feedback"):
        self.feedback_dir = feedback_dir
        os.makedirs(feedback_dir, exist_ok=True)
        self.summary_file = os.path.join(feedback_dir, "feedback_summary.json")

    def save_feedback(self, ticker: str, analysis: str, verdict: str,
                     rating: int, comment: str = ""):
        """
        피드백 저장

        Args:
            ticker: 종목 코드
            analysis: AI 분석 결과
            verdict: AI 판단 (BUY NOW/WATCH & WAIT/AVOID)
            rating: 1-5 평가
            comment: 사용자 코멘트
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        feedback_data = {
            "ticker": ticker,
            "timestamp": timestamp,
            "verdict": verdict,
            "rating": rating,
            "comment": comment,
            "analysis_preview": analysis[:500]  # 처음 500자만 저장
        }

        # 개별 피드백 파일 저장
        filename = f"{ticker}_{timestamp}.json"
        filepath = os.path.join(self.feedback_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(feedback_data, f, indent=2, ensure_ascii=False)

        # 요약 파일 업데이트
        self._update_summary(feedback_data)

        print(f"[✓] Feedback saved: {filename}")

    def _update_summary(self, feedback_data: Dict):
        """피드백 요약 파일 업데이트"""
        summary = self._load_summary()

        ticker = feedback_data["ticker"]
        if ticker not in summary:
            summary[ticker] = {
                "total_analyses": 0,
                "avg_rating": 0.0,
                "ratings": [],
                "common_issues": [],
                "recent_feedback": []
            }

        # 통계 업데이트
        summary[ticker]["total_analyses"] += 1
        summary[ticker]["ratings"].append(feedback_data["rating"])
        summary[ticker]["avg_rating"] = sum(summary[ticker]["ratings"]) / len(summary[ticker]["ratings"])

        # 최근 피드백 저장 (최대 5개)
        summary[ticker]["recent_feedback"].append({
            "timestamp": feedback_data["timestamp"],
            "verdict": feedback_data["verdict"],
            "rating": feedback_data["rating"],
            "comment": feedback_data["comment"]
        })
        if len(summary[ticker]["recent_feedback"]) > 5:
            summary[ticker]["recent_feedback"] = summary[ticker]["recent_feedback"][-5:]

        # 저장
        with open(self.summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

    def _load_summary(self) -> Dict:
        """요약 파일 로드"""
        if os.path.exists(self.summary_file):
            with open(self.summary_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_feedback_context(self, ticker: Optional[str] = None) -> str:
        """
        과거 피드백을 기반으로 학습 컨텍스트 생성

        Args:
            ticker: 종목 코드 (None이면 전체)

        Returns:
            프롬프트에 추가할 피드백 컨텍스트
        """
        summary = self._load_summary()

        if not summary:
            return ""

        context_lines = ["\n## FEEDBACK LEARNING CONTEXT"]
        context_lines.append("Based on previous user feedback, pay attention to:")

        # 전체 평균 평가
        all_ratings = []
        for ticker_data in summary.values():
            all_ratings.extend(ticker_data["ratings"])

        if all_ratings:
            avg_rating = sum(all_ratings) / len(all_ratings)
            context_lines.append(f"- Overall analysis quality: {avg_rating:.1f}/5.0")

        # 특정 종목의 과거 피드백
        if ticker and ticker in summary:
            ticker_data = summary[ticker]
            context_lines.append(f"\n### Previous analysis of {ticker}:")
            context_lines.append(f"- Analyzed {ticker_data['total_analyses']} times")
            context_lines.append(f"- Average rating: {ticker_data['avg_rating']:.1f}/5.0")

            if ticker_data["recent_feedback"]:
                context_lines.append("\nRecent feedback:")
                for fb in ticker_data["recent_feedback"][-3:]:  # 최근 3개
                    if fb["comment"]:
                        context_lines.append(f"  - {fb['timestamp']}: \"{fb['comment']}\"")

        # 자주 나오는 개선 사항 (향후 확장)
        context_lines.append("\n### General improvements from feedback:")
        context_lines.append("- Use exact dates from DATA CONTEXT")
        context_lines.append("- Calculate precise percentages")
        context_lines.append("- Reference specific price levels")

        return "\n".join(context_lines) + "\n"

    def get_stats(self) -> Dict:
        """전체 통계 반환"""
        summary = self._load_summary()

        total_analyses = sum(data["total_analyses"] for data in summary.values())

        all_ratings = []
        for ticker_data in summary.values():
            all_ratings.extend(ticker_data["ratings"])

        avg_rating = sum(all_ratings) / len(all_ratings) if all_ratings else 0

        return {
            "total_tickers": len(summary),
            "total_analyses": total_analyses,
            "avg_rating": avg_rating,
            "ticker_breakdown": {
                ticker: {
                    "analyses": data["total_analyses"],
                    "avg_rating": data["avg_rating"]
                }
                for ticker, data in summary.items()
            }
        }


def collect_feedback(ticker: str, analysis: str, verdict: str) -> Optional[Dict]:
    """
    사용자로부터 피드백 수집

    Args:
        ticker: 종목 코드
        analysis: AI 분석 결과
        verdict: AI 판단

    Returns:
        피드백 딕셔너리 또는 None
    """
    print("\n" + "=" * 80)
    print("📝 AI 분석 피드백 (선택사항 - 엔터를 누르면 건너뜀)")
    print("=" * 80)

    try:
        rating_input = input("이 분석 평가 (1-5, 엔터=건너뜀): ").strip()

        if not rating_input:
            print("[건너뜀] 피드백이 저장되지 않았습니다.")
            return None

        rating = int(rating_input)
        if rating < 1 or rating > 5:
            print("[오류] 1-5 사이의 숫자를 입력해주세요.")
            return None

        comment = input("간단한 코멘트 (선택사항): ").strip()

        return {
            "ticker": ticker,
            "analysis": analysis,
            "verdict": verdict,
            "rating": rating,
            "comment": comment
        }

    except ValueError:
        print("[오류] 숫자를 입력해주세요.")
        return None
    except KeyboardInterrupt:
        print("\n[취소됨]")
        return None


if __name__ == "__main__":
    # 테스트
    manager = FeedbackManager()

    # 테스트 피드백 저장
    manager.save_feedback(
        ticker="AAPL",
        analysis="Test analysis for AAPL...",
        verdict="WATCH & WAIT",
        rating=4,
        comment="정확한 분석. 날짜가 정확했음."
    )

    # 컨텍스트 생성
    context = manager.get_feedback_context("AAPL")
    print(context)

    # 통계 출력
    stats = manager.get_stats()
    print("\nStats:", json.dumps(stats, indent=2))
