FROM python:3.11

WORKDIR /app

# Python 의존성 설치
COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 전체 소스 복사
COPY . .

# 필요 디렉토리 생성
RUN mkdir -p /app/trading/results /app/trading/feedback /app/results

# matplotlib 비대화형 백엔드
ENV MPLBACKEND=Agg
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV PYTHONUNBUFFERED=1

# 빌드 시 검증
RUN python -c "import fastapi, uvicorn, yfinance, pandas, numpy, matplotlib, mplfinance, PIL; print('[OK] All packages imported')"
RUN python -c "from server.app import app; print('[OK] server.app loaded')"

EXPOSE 8080

CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
