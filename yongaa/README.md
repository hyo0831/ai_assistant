# AI 투자도우미 - 조건검색편 (로컬 풀스택 템플릿)

## 구성
- `backend/`: FastAPI + OpenAI Responses API
- `frontend/`: Vanilla HTML/CSS/JS (다크/라이트, 한/영)

## 빠른 시작

### 1) 백엔드 실행
```bash
cd /opt/homebrew/var/www/ai-screener-bot/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env에 OPENAI_API_KEY 입력
uvicorn app:app --reload --port 8000
```

### 2) 프론트 실행
```bash
cd /opt/homebrew/var/www/ai-screener-bot/frontend
python -m http.server 5173
```
브라우저에서 `http://localhost:5173` 접속

## OpenAI Responses API 참고
- API 엔드포인트: `POST https://api.openai.com/v1/responses`
- Python SDK 예시 (OpenAI client):
```python
from openai import OpenAI
client = OpenAI(api_key="YOUR_KEY")
resp = client.responses.create(
    model="gpt-5-mini",
    input=[{"role": "user", "content": "Hello"}]
)
print(resp.output_text)
```

## 데이터 교체
`backend/data/sample_universe.csv`를 실제 데이터 파이프라인 결과로 교체하면 됩니다.

## 주의
- 이 프로젝트는 예시용 템플릿입니다. 투자 손익은 본인 책임입니다.
