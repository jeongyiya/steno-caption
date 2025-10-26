# app.py
import os
import time
import string
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from flask_socketio import SocketIO

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")  # 배포 시 환경변수로 바꾸세요

# socketio - gevent 사용 (로컬에서 gevent 설치 필요)
socketio = SocketIO(
    app,
    async_mode='gevent',
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=60,
)

# ---- in-memory job store (간단용) ----
# jobs[job_id] = {'pin': '1234', 'created': 1234567890, 'active': True}
jobs = {}

def gen_job_id(n=6):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

def gen_pin():
    return '{:04d}'.format(secrets.randbelow(10000))

# ---- routes ----
@app.route('/')
def index():
    return redirect(url_for('viewer'))

@app.route('/writer')
def writer():
    return render_template('writer.html')

@app.route('/viewer')
def viewer():
    return render_template('viewer.html')

# ---- API: create job (속기사용) ----
@app.post('/create_job')
def create_job():
    job_id = gen_job_id(6)
    pin = gen_pin()
    jobs[job_id] = {'pin': pin, 'created': time.time(), 'active': True}
    return jsonify({'job_id': job_id, 'pin': pin})

# ---- API: auth job (뷰어가 PIN 제출하면 세션에 인증 표시) ----
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
    authorized = session.get('authorized_jobs', {})
    authorized[job_id] = True
    session['authorized_jobs'] = authorized
    return jsonify({'ok': True})

# ---- API: end job (속기사용) ----
@app.post('/end_job')
def end_job():
    data = request.get_json(force=True)
    job_id = data.get('job_id')
    if job_id and job_id in jobs:
        jobs[job_id]['active'] = False
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 404

# ---- Socket.IO: 속기사가 전송하면 모든 뷰어에 broadcast (job_id 포함) ----
@socketio.on('full_text')
def handle_full_text(data):
    # expected data: { job_id: 'ABC123', text: '...' }
    job_id = data.get('job_id')
    text = data.get('text')
    if not job_id or text is None:
        return
    # broadcast with job_id so viewers can filter
    socketio.emit('show_full_text', {'job_id': job_id, 'text': text})

# ---- optional API for external apps (AHK) ----
@app.post('/api/fulltext')
def api_fulltext():
    text = request.get_data(as_text=True) or ""
    socketio.emit('show_full_text', {'job_id': 'GLOBAL', 'text': text})
    return Response("OK", mimetype="text/plain")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
