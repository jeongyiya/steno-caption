# app.py
import os
import time
import string
import secrets
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from flask_socketio import SocketIO

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")  # 배포 시 Environment에 설정 권장

# 세션 만료(원하면 시간 조절)
app.permanent_session_lifetime = timedelta(hours=24)

# ✅ gevent 사용 (eventlet 코드/monkey_patch는 절대 넣지 마세요)
socketio = SocketIO(
    app,
    async_mode='gevent',
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=60,
)

# ---- 간단 in-memory job 저장소 ----
# jobs[job_id] = {'pin': '1234', 'created': 1234567890, 'active': True}
jobs = {}

def gen_job_id(n=6):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

def gen_pin():
    return '{:04d}'.format(secrets.randbelow(10000))

# ---- 유틸/상태 확인 라우트(헬스체크용) ----
@app.route('/healthz')
def healthz():
    return "ok", 200

@app.route('/ping')
def ping():
    return "pong", 200

# ---- 페이지 라우트 ----
@app.route('/')
def index():
    # 기본적으로 viewer로 이동 (원하면 안내 페이지로 교체 가능)
    return redirect(url_for('viewer'))

@app.route('/writer')
def writer():
    return render_template('writer.html')

@app.route('/viewer')
def viewer():
    return render_template('viewer.html')

# ---- API: 세션 생성(속기사) ----
@app.post('/create_job')
def create_job():
    job_id = gen_job_id(6)
    pin = gen_pin()
    jobs[job_id] = {'pin': pin, 'created': time.time(), 'active': True}
    return jsonify({'job_id': job_id, 'pin': pin})

# ---- API: 인증(이용자 PIN 제출) ----
@app.post('/auth_job')
def auth_job():
    data = request.get_json(force=True)
    job_id = data.get('job_id')
    pin = data.get('pin')

    if not job_id or pin is None:
        return jsonify({'ok': False, 'message': 'job_id/pin 필요'}), 400

    job = jobs.get(job_id)
    if not job or not job.get('active'):
        return jsonify({'ok': False, 'message': '유효하지 않은 세션입니다.'}), 403

    if job.get('pin') != str(pin).zfill(4):
        return jsonify({'ok': False, 'message': '비밀번호가 틀립니다.'}), 403

    # 성공: 세션에 승인 표시
    auth = session.get('authorized_jobs', {})
    auth[job_id] = True
    session['authorized_jobs'] = auth
    session.permanent = True
    return jsonify({'ok': True})

# ---- API: 세션 종료(속기사) ----
@app.post('/end_job')
def end_job():
    data = request.get_json(force=True)
    job_id = data.get('job_id')
    if job_id and job_id in jobs:
        jobs[job_id]['active'] = False
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 404

# ---- Socket.IO: 전체 텍스트 방송 (job_id 포함) ----
@socketio.on('full_text')
def handle_full_text(data):
    # expected: { "job_id": "ABC123", "text": "..." }
    if not isinstance(data, dict):
        return
    job_id = data.get('job_id')
    text = data.get('text')
    if not job_id or text is None:
        return
    # (옵션) 작성자 인증 강제하려면 세션 확인 추가 가능
    socketio.emit('show_full_text', {'job_id': job_id, 'text': text})

# ---- 외부앱(AHK 등)에서 전체 텍스트 반영용(선택) ----
@app.post('/api/fulltext')
def api_fulltext():
    text = request.get_data(as_text=True) or ""
    socketio.emit('show_full_text', {'job_id': 'GLOBAL', 'text': text})
    return Response("OK", mimetype="text/plain")

# ---- 로컬 실행 ----
if __name__ == '__main__':
    # 로컬 개발용 포트(배포 시에는 gunicorn이 --bind 0.0.0.0:$PORT 로 실행)
    socketio.run(app, host='0.0.0.0', port=5000)
