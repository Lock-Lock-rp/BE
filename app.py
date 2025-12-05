from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv
import os
from supabase import create_client, Client
from datetime import datetime
import cv2
import numpy as np
import base64
import json
from io import BytesIO
from PIL import Image
import threading
import time

# 환경변수 로드
load_dotenv()

# Flask 앱 초기화
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')

# Supabase 클라이언트 초기화
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
supabase: Client = create_client(supabase_url, supabase_key)

# 전역 변수
camera = None
output_frame = None
lock = threading.Lock()

# OpenCV 얼굴 검출기 초기화
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# 설정값
DEVICE_ID = os.getenv('DEVICE_ID', 'raspberry_pi_01')

# ============================================
# 카메라 초기화
# ============================================

def initialize_camera():
    """카메라 초기화 (웹캠)"""
    global camera
    try:
        camera = cv2.VideoCapture(0)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print("✅ 웹캠 초기화 성공")
        return True
    except Exception as e:
        print(f"❌ 카메라 초기화 실패: {e}")
        return False

# ============================================
# 얼굴 감지 함수 (OpenCV 사용)
# ============================================

def detect_faces(frame):
    """프레임에서 얼굴 감지"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    
    results = []
    for (x, y, w, h) in faces:
        results.append({
            'location': (y, x+w, y+h, x),  # top, right, bottom, left
            'confidence': 0.8,  # OpenCV는 신뢰도를 제공하지 않으므로 고정값
        })
    
    return results

# ============================================
# 비상 알림 생성
# ============================================

def create_alert(image_data, access_log_id=None):
    """미등록 사용자 감지 시 비상 알림 생성"""
    try:
        # 이미지를 Storage에 업로드
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"alert_{timestamp}.jpg"
        
        # Base64 -> 바이너리
        if ',' in image_data:
            image_binary = base64.b64decode(image_data.split(',')[1])
        else:
            image_binary = base64.b64decode(image_data)
        
        # Supabase Storage에 업로드
        storage_response = supabase.storage.from_('alert-images').upload(
            filename,
            image_binary,
            {'content-type': 'image/jpeg'}
        )
        
        # 이미지 URL 생성
        image_url = supabase.storage.from_('alert-images').get_public_url(filename)
        
        # alerts 테이블에 삽입
        alert_data = {
            'alert_type': 'unauthorized_access',
            'severity': 'critical',
            'title': '⚠️ 얼굴 감지됨',
            'message': '얼굴이 감지되었습니다. (데모 모드 - 모든 얼굴을 미등록으로 처리)',
            'image_url': image_url,
            'access_log_id': access_log_id,
            'is_read': False,
            'is_resolved': False
        }
        
        response = supabase.table('alerts').insert(alert_data).execute()
        print(f"✅ 비상 알림 생성 완료: {response.data[0]['id']}")
        
        return response.data[0]
    except Exception as e:
        print(f"❌ 비상 알림 생성 실패: {e}")
        return None

# ============================================
# 출입 기록 저장
# ============================================

def save_access_log(access_type, status, confidence, image_data):
    """출입 기록 저장"""
    try:
        # 이미지 Storage에 업로드
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"access_{timestamp}.jpg"
        
        if ',' in image_data:
            image_binary = base64.b64decode(image_data.split(',')[1])
        else:
            image_binary = base64.b64decode(image_data)
        
        storage_response = supabase.storage.from_('access-captures').upload(
            filename,
            image_binary,
            {'content-type': 'image/jpeg'}
        )
        
        image_url = supabase.storage.from_('access-captures').get_public_url(filename)
        
        # access_logs 테이블에 삽입
        log_data = {
            'user_id': None,  # 데모 모드에서는 항상 None
            'access_type': access_type,
            'status': status,
            'confidence': confidence,
            'image_url': image_url,
            'device_id': DEVICE_ID,
            'notes': 'Demo mode - Face recognition not active'
        }
        
        response = supabase.table('access_logs').insert(log_data).execute()
        return response.data[0]
    except Exception as e:
        print(f"❌ 출입 기록 저장 실패: {e}")
        return None

# ============================================
# API 엔드포인트
# ============================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """서버 상태 확인"""
    return jsonify({
        'status': 'ok',
        'device_id': DEVICE_ID,
        'mode': 'demo',
        'message': 'OpenCV face detection only (no recognition)'
    })

@app.route('/api/detect', methods=['POST'])
def detect():
    """얼굴 감지 및 알림 생성 (데모 모드)"""
    try:
        data = request.json
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'error': 'image가 필요합니다'}), 400
        
        # Base64 이미지 디코딩
        if ',' in image_data:
            image_binary = base64.b64decode(image_data.split(',')[1])
        else:
            image_binary = base64.b64decode(image_data)
            
        nparr = np.frombuffer(image_binary, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 얼굴 감지
        results = detect_faces(frame)
        
        if len(results) == 0:
            return jsonify({
                'success': False,
                'message': '얼굴이 감지되지 않았습니다',
                'face_detected': False
            })
        
        # 출입 기록 저장 (데모: 모든 얼굴을 미등록으로 처리)
        access_log = save_access_log(
            access_type='unauthorized',
            status='denied',
            confidence=results[0]['confidence'],
            image_data=image_data
        )
        
        # 비상 알림 생성
        alert = create_alert(image_data, access_log['id'] if access_log else None)
        
        return jsonify({
            'success': True,
            'face_detected': True,
            'faces_count': len(results),
            'message': '얼굴이 감지되었습니다. 비상 알림이 전송되었습니다.',
            'access_log_id': access_log['id'] if access_log else None,
            'alert_id': alert['id'] if alert else None
        })
        
    except Exception as e:
        print(f"에러: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# 실시간 스트리밍
# ============================================

def generate_frames():
    """실시간 비디오 프레임 생성"""
    global camera
    
    while True:
        if camera is None or not camera.isOpened():
            time.sleep(0.1)
            continue
        
        try:
            success, frame = camera.read()
            if not success:
                continue
            
            # 얼굴 감지
            results = detect_faces(frame)
            
            # 얼굴 위치에 박스 그리기
            for result in results:
                top, right, bottom, left = result['location']
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(frame, "Face Detected", (left, top - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # JPEG로 인코딩
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                   
        except Exception as e:
            print(f"스트리밍 에러: {e}")
            continue

@app.route('/api/video-feed')
def video_feed():
    """실시간 비디오 스트리밍"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# ============================================
# 디바이스 상태 업데이트
# ============================================

def update_device_status():
    """주기적으로 디바이스 상태 업데이트"""
    while True:
        try:
            supabase.table('device_status').update({
                'is_online': True,
                'last_ping': datetime.now().isoformat()
            }).eq('device_id', DEVICE_ID).execute()
            
            time.sleep(30)  # 30초마다 업데이트
        except Exception as e:
            print(f"디바이스 상태 업데이트 실패: {e}")
            time.sleep(30)

# ============================================
# 알림 목록 조회
# ============================================

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """알림 목록 조회"""
    try:
        response = supabase.table('alerts').select('*').order('created_at', desc=True).limit(50).execute()
        return jsonify({
            'success': True,
            'alerts': response.data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts/<alert_id>/read', methods=['POST'])
def mark_alert_read(alert_id):
    """알림 읽음 처리"""
    try:
        response = supabase.table('alerts').update({'is_read': True}).eq('id', alert_id).execute()
        return jsonify({
            'success': True,
            'alert': response.data[0]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# 출입 기록 조회
# ============================================

@app.route('/api/access-logs', methods=['GET'])
def get_access_logs():
    """출입 기록 조회"""
    try:
        response = supabase.table('access_logs').select('*').order('created_at', desc=True).limit(100).execute()
        return jsonify({
            'success': True,
            'logs': response.data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# 메인 실행
# ============================================

if __name__ == '__main__':
    print("🚀 스마트 도어락 백엔드 서버 시작 (데모 모드)...")
    print("⚠️  얼굴 인식 기능 비활성화 - 얼굴 감지만 가능")
    
    # 카메라 초기화
    initialize_camera()
    
    # 디바이스 상태 업데이트 스레드 시작
    status_thread = threading.Thread(target=update_device_status, daemon=True)
    status_thread.start()
    
    # Flask 서버 시작
    port = int(os.getenv('FLASK_PORT', 5000))
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=True)

