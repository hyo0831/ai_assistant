# 🔧 .env 파일 설정 가이드

## 개요

ORION 웹 서비스는 OpenAI API 키를 `.env` 파일에서 읽습니다. 사용자는 웹에서 API 키를 입력할 필요가 없으므로 더 보안이 좋습니다.

## 파일 위치

```
yongaa/
├── .env                 ← 실제 API 키 (Git에 커밋하지 않음)
├── .env.example         ← 예제 파일 (참고용)
└── .gitignore          ← .env 파일 무시 설정
```

## 설정 방법

### 1️⃣ OpenAI API 키 발급

1. https://platform.openai.com/api-keys 방문
2. "Create new secret key" 클릭
3. API 키를 복사합니다 (예: `sk-proj-xxxxxxx...`)

### 2️⃣ .env 파일 생성 및 편집

#### 방법 A: 파일로 열기
```bash
# Mac/Linux
nano yongaa/.env

# Windows
notepad yongaa\.env
```

#### 방법 B: 코드 에디터에서 열기
1. VSCode, Sublime Text 등에서 `yongaa/.env` 파일 열기
2. 내용 편집

### 3️⃣ API 키 입력

`.env` 파일의 내용:

```env
# OpenAI API Key
OPENAI_API_KEY=sk-proj-your_actual_api_key_here
```

**예시:**
```env
OPENAI_API_KEY=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
```

### 4️⃣ 파일 저장

**중요**: 파일을 저장한 후 Flask 서버를 재시작하세요!

```bash
# 기존 프로세스 종료 (Ctrl+C)
# 다시 실행
python app.py
```

## 보안 주의사항

### ✅ 안전한 방법
- API 키를 `.env` 파일에 저장
- `.env` 파일을 `.gitignore`에 추가
- API 키를 Git 저장소에 커밋하지 않음
- 팀원과 API 키를 공유하지 않음
- 주기적으로 API 키를 회전

### ❌ 위험한 방법
- API 키를 코드에 하드코딩
- API 키를 메시지/채팅으로 공유
- API 키를 문서에 남겨두기
- `.env` 파일을 Git에 커밋

## 확인 방법

### 1️⃣ 파일 존재 확인

```bash
ls -la yongaa/.env
```

파일이 존재하면 다음과 같이 출력됩니다:
```
-rw-r--r--  1 user  staff  123 Feb 20 10:00 yongaa/.env
```

### 2️⃣ 내용 확인 (터미널)

```bash
cat yongaa/.env
```

### 3️⃣ 서버 로그 확인

Flask 서버 시작 시 `.env` 파일을 읽었다면, 별도의 에러가 없어야 합니다.

## 문제 해결

### 문제: ".env 파일에 OPENAI_API_KEY를 설정하세요"

**원인**: `.env` 파일이 없거나 API 키가 설정되지 않음

**해결책**:
1. `yongaa/.env` 파일이 있는지 확인
2. `OPENAI_API_KEY=...` 줄이 있는지 확인
3. API 키 값이 정상인지 확인
4. 파일 저장 후 서버 재시작

### 문제: "Invalid API key provided"

**원인**: API 키가 잘못됨

**해결책**:
1. https://platform.openai.com/api-keys 에서 새 키 생성
2. `.env` 파일의 API 키를 새 키로 교체
3. 서버 재시작

### 문제: .env 파일이 텍스트로 보이지 않음

**원인**: `.env` 파일이 숨김 파일로 설정됨

**해결책** (Mac):
```bash
defaults write com.apple.Finder AppleShowAllFiles true
killall Finder
```

**해결책** (Windows):
1. 폴더 → 보기 → 옵션
2. "숨겨진 파일, 폴더, 드라이브 표시" 체크

## .env.example 사용

`.env.example`은 Git에 커밋할 수 있는 템플릿입니다. 새로운 개발자가 프로젝트를 받을 때:

```bash
# 1. 예제 파일 복사
cp yongaa/.env.example yongaa/.env

# 2. .env 파일에 자신의 API 키 입력
# (텍스트 에디터로 열기)

# 3. Flask 서버 시작
python yongaa/app.py
```

## 환경 변수 읽기 (개발자용)

app.py에서 환경 변수를 읽는 방법:

```python
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수 읽기
api_key = os.getenv('OPENAI_API_KEY')

# API 키 확인
if not api_key:
    print("ERROR: OPENAI_API_KEY가 설정되지 않았습니다")
else:
    print("✓ API 키가 정상 로드되었습니다")
```

## 참고 자료

- [OpenAI API 문서](https://platform.openai.com/docs)
- [python-dotenv 문서](https://github.com/theskumar/python-dotenv)
- [환경 변수 보안 모범 사례](https://12factor.net/config)

---

**질문이 있으신가요?**

설정 관련 문제가 발생하면 서버 로그에서 에러 메시지를 확인하세요.

```bash
# 서버 실행 시 상세 로그 표시
FLASK_DEBUG=1 python yongaa/app.py
```
