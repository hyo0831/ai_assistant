"""
William O'Neil AI Investment Assistant
실행 진입점 (Entry Point)

사용법:
    python main.py           # 대화형 메뉴
    python cli.py            # 동일
    uvicorn api:app --reload # FastAPI 서버
"""
from cli import main

if __name__ == "__main__":
    main()
