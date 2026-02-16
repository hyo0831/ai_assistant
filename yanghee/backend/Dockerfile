FROM python:3.11-slim

WORKDIR /app

# matplotlib이 사용하는 시스템 라이브러리 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libfreetype6-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# matplotlib이 GUI 없이 동작하도록 설정
ENV MPLBACKEND=Agg

# 의존성 먼저 설치 (캐시 활용 — 코드가 바뀌어도 재설치 안 함)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# Cloud Run은 PORT 환경변수로 포트를 지정함
ENV PORT=8080
EXPOSE 8080

# 서버 실행
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
