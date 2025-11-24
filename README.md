# 스마트 도어락 백엔드 서버

## 🚀 설치 방법

### 1. 저장소 클론
```bash
git clone <repository-url>
cd smart-doorlock-backend
```

### 2. 가상환경 생성 및 활성화
```bash
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows
```

### 3. 패키지 설치
```bash
pip install Flask Flask-CORS supabase opencv-python Pillow numpy python-dotenv requests
```

### 4. 환경변수 설정
`.env.example`을 복사하여 `.env` 파일 생성 후 실제 값 입력
```bash
cp .env.example .env
nano .env
```

### 5. 서버 실행
```bash
python app.py
```

## 📡 API 엔드포인트

- `GET /api/health` - 서버 상태 확인
- `POST /api/detect` - 얼굴 감지
- `GET /api/video-feed` - 실시간 영상
- `GET /api/alerts` - 알림 목록
- `GET /api/access-logs` - 출입 기록

## 🔑 Supabase 설정 필요

프로젝트 URL과 API 키를 `.env` 파일에 설정해야 합니다.

