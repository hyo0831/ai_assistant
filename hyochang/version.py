"""
Version tracking for William O'Neil AI Investment Assistant
"""

VERSION = "2.0.0"
VERSION_NAME = "V2 - Enhanced Pattern Detection"

CHANGELOG = {
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
