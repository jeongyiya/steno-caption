# app.py
import os
import time
import string
import secrets
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from flask_socketio import SocketIO

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")
app.permanent_session_lifetime = timedelta(hours=24)

# ✅ eventlet 모드 (gunicorn -k eventlet 와 짝)
socketio = SocketIO(
    app,
    async_mode='eventlet',
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=60,
)

# --- in-memory jobs ---
# jobs[job_id] = {'pin': '1234', 'created': ts, 'active': True}
jobs = {}

def gen_job_id(n=6):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

def gen_pin():
    return f"{secrets.randbelow(10000):04d}"

@app.route('/healthz')
def healthz():
    return "ok", 200

@app.route('/ping')
def ping():
    return "pong", 200

@app.route('/')
def index():
    return redirect(url_for('viewer'))

@app.route('/writer')
def writer():
    return render_template('writer.html')

@app.route('/viewer')
def viewer():
    return render_template('viewer.html')

@app.post('/create_job')
def create_job():
    job_id = gen_job_id(6)
    pin = gen_pin()
    jobs[job_id] = {'pin': pin, 'created': time.time(), 'active': True}
    return jsonify({'job_id': job_id, 'pin': pin})

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
    auth = session.get('authorized_jobs', {})
    auth[job_id] = True
    session['authorized_jobs'] = auth
    session.permanent = True
    return jsonify({'ok': True})

@app.post('/end_job')
def end_job():
    data = request.get_json(force=True)
    job_id = data.get('job_id')
    if job_id and job_id in jobs:
        jobs[job_id]['active'] = False
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 404

@socketio.on('full_text')
def handle_full_text(data):
    # expected: { "job_id": "ABC123", "text": "..." }
    if not isinstance(data, dict):
        return
    job_id = data.get('job_id')
    text = data.get('text')
    if not job_id or text is None:
        return
    socketio.emit('show_full_text', {'job_id': job_id, 'text': text})

@app.post('/api/fulltext')
def api_fulltext():
    text = request.get_data(as_text=True) or ""
    socketio.emit('show_full_text', {'job_id': 'GLOBAL', 'text': text})
    return Response("OK", mimetype="text/plain")

if __name__ == '__main__':
    # 로컬 실행용(배포 시엔 Procfile의 gunicorn이 사용됨)
    socketio.run(app, host='0.0.0.0', port=5000)
