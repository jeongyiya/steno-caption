from flask import Flask, render_template
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

@app.route('/writer')
def writer():
    return render_template('writer.html')

@app.route('/viewer')
def viewer():
    return render_template('viewer.html')

# ✅ 전체 텍스트를 그대로 브로드캐스트
@socketio.on('full_text')
def handle_full_text(data):
    # data: 속기사 입력창의 전체 텍스트(str)
    socketio.emit('show_full_text', data)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
