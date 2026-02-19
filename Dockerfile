FROM python:3.11

WORKDIR /app

# 의존성 설치
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사 (engine + backend + frontend)
COPY engine/ ./engine/
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# 필요 디렉토리 생성
RUN mkdir -p /app/backend/results /app/backend/feedback

# matplotlib 비대화형 백엔드
ENV MPLBACKEND=Agg
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV PYTHONUNBUFFERED=1

# 빌드 시 검증
RUN python -c "import fastapi, uvicorn, yfinance, pandas, numpy, matplotlib, mplfinance, PIL; print('[OK] All packages imported')"

EXPOSE 8080

CMD ["sh", "-c", "cd /app/backend && uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
