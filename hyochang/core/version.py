"""
Version tracking for William O'Neil AI Investment Assistant
"""

VERSION = "2.1.0"
VERSION_NAME = "V2.1 - Korean Report + Fundamentals + Compare"

CHANGELOG = {
    "2.1.0": {
        "date": "2026-02-15",
        "name": "V2.1 - Korean Report + Fundamentals + Compare",
        "changes": [
            "Fix: .env auto-loading with python-dotenv",
            "Fix: detect_flat_base() index slicing consistency",
            "Fix: detect_cup_with_handle() handle minimum 2-week data",
            "Fix: analyze_relative_strength() date alignment for S&P 500 comparison",
            "Fix: NaN/missing data handling in volume analysis",
            "Fix: Emoji regex preserves Korean/Unicode text, removes only emojis",
            "Korean report: AI analysis output in Korean (기술 용어는 영어 유지)",
            "Korean UI: Bilingual menu and result headers (한영 병행)",
            "Fundamental analysis: CAN SLIM scoring module (C/A/N/S/I)",
            "V2 integration: Fundamentals included in AI prompt for comprehensive analysis",
            "Multi-stock compare mode: [3] Compare multiple tickers with ranking table",
            "Daily chart support: Weekly/Daily chart selection at startup",
            "RS Rating display in analysis result output",
        ]
    },
    "2.0.0": {
        "date": "2026-02-12",
        "name": "V2 - Enhanced Pattern Detection",
        "changes": [
            "Add V2 mode: code-based pattern detection + AI interpretation",
            "Pattern detector: Cup-with-Handle, Double Bottom, Flat Base, High Tight Flag",
            "Volume analysis: accumulation/distribution days, surges, dry-ups",
            "Base stage counting (1st-4th stage risk assessment)",
            "Pattern quality scoring (0-100) and fault detection",
            "Mode selection at startup (V1 basic / V2 enhanced)",
            "Interactive ticker input",
            "Remove log scale for better chart-analysis match",
        ]
    },
    "1.0.0": {
        "date": "2026-02-11",
        "name": "V1 - Basic AI Analysis",
        "changes": [
            "Mac environment setup (venv, setup script)",
            "William O'Neil system prompt (307-line CAN SLIM framework)",
            "Weekly chart generation with 10-week/40-week moving averages",
            "Gemini 2.5 Flash multimodal AI chart analysis",
            "Data context injection for accurate date/price references",
            "Auto-learning feedback system",
        ]
    }
}


def print_version():
    """Print current version info"""
    print(f"Version: {VERSION} ({VERSION_NAME})")


def print_changelog():
    """Print full changelog"""
    for ver, info in CHANGELOG.items():
        print(f"\n{'='*50}")
        print(f"v{ver} - {info['name']} ({info['date']})")
        print(f"{'='*50}")
        for change in info['changes']:
            print(f"  - {change}")
