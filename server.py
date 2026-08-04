import os
import json
import subprocess
import tempfile
import signal
import time
import hashlib
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import threading
import queue
import logging

# ========== CONFIG ==========
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

DB_PATH = "codes.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ========== DATABASE SETUP ==========
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS codes (
        id TEXT PRIMARY KEY,
        code TEXT,
        filename TEXT,
        created_at TEXT,
        executed_at TEXT,
        output TEXT,
        error TEXT,
        status TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# ========== SECURITY BLOCKLIST ==========
BLOCKED = [
    "os.", "subprocess", "__import__", "eval", "exec",
    "compile", "open(", "file(", "system(", "popen",
    "globals", "locals", "getattr", "setattr", "delattr",
    "__builtins__", "__dict__", "__class__", "__bases__",
    "__subclasses__", "__mro__", "__code__", "__call__",
    "breakpoint", "input(", "execfile"
]

def is_safe(code: str) -> bool:
    code_lower = code.lower()
    for kw in BLOCKED:
        if kw in code_lower:
            return False
    return True

# ========== EXECUTION ENGINE ==========
def run_python_code(code: str, timeout_sec: int = 10):
    """Execute Python code safely with timeout"""
    if not is_safe(code):
        return {"error": "Blocked: Dangerous keyword detected"}

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            tmp_path = f.name

        # Run with timeout using subprocess
        proc = subprocess.Popen(
            ['python', tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid if os.name != 'nt' else None
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout_sec)
            os.remove(tmp_path)
            return {
                "output": stdout.strip() or "(no output)",
                "error": stderr.strip() or None
            }
        except subprocess.TimeoutExpired:
            # Kill process group
            if os.name != 'nt':
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            else:
                proc.kill()
            stdout, stderr = proc.communicate()
            os.remove(tmp_path)
            return {
                "output": stdout.strip() or "(timeout)",
                "error": f"Timeout after {timeout_sec}s"
            }

    except Exception as e:
        return {"error": str(e)}

# ========== API ENDPOINTS ==========

@app.route('/')
def home():
    return jsonify({
        "name": "Potato Code Hosting Engine",
        "version": "3.0",
        "status": "active",
        "endpoints": {
            "/run": "POST - execute code",
            "/upload": "POST - upload .py file",
            "/code/<id>": "GET - get code details",
            "/history": "GET - list all executions"
        }
    })

@app.route('/run', methods=['POST'])
def run_code():
    data = request.get_json()
    if not data or 'code' not in data:
        return jsonify({'error': 'No code provided'}), 400

    code = data['code']
    timeout = data.get('timeout', 10)

    # Generate unique ID
    code_id = hashlib.sha256(code.encode()).hexdigest()[:12]

    # Execute
    result = run_python_code(code, timeout)

    # Save to DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO codes 
        (id, code, filename, created_at, executed_at, output, error, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (code_id, code, f"{code_id}.py", datetime.now().isoformat(),
         datetime.now().isoformat(), result.get('output'), result.get('error'),
         'success' if not result.get('error') else 'failed'))
    conn.commit()
    conn.close()

    return jsonify({
        'id': code_id,
        'output': result.get('output'),
        'error': result.get('error')
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    if not file.filename.endswith('.py'):
        return jsonify({'error': 'Only .py files allowed'}), 400

    code = file.read().decode('utf-8')
    code_id = hashlib.sha256(code.encode()).hexdigest()[:12]
    filename = f"{code_id}_{file.filename}"

    # Save file
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    with open(filepath, 'w') as f:
        f.write(code)

    # Execute
    result = run_python_code(code, timeout=15)

    # Save to DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO codes 
        (id, code, filename, created_at, executed_at, output, error, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (code_id, code, filename, datetime.now().isoformat(),
         datetime.now().isoformat(), result.get('output'), result.get('error'),
         'success' if not result.get('error') else 'failed'))
    conn.commit()
    conn.close()

    return jsonify({
        'id': code_id,
        'filename': filename,
        'output': result.get('output'),
        'error': result.get('error')
    })

@app.route('/code/<code_id>', methods=['GET'])
def get_code(code_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM codes WHERE id = ?', (code_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Code not found'}), 404

    return jsonify({
        'id': row[0],
        'code': row[1],
        'filename': row[2],
        'created_at': row[3],
        'executed_at': row[4],
        'output': row[5],
        'error': row[6],
        'status': row[7]
    })

@app.route('/history', methods=['GET'])
def get_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, filename, created_at, status FROM codes ORDER BY created_at DESC LIMIT 100')
    rows = c.fetchall()
    conn.close()

    return jsonify([
        {
            'id': row[0],
            'filename': row[1],
            'created_at': row[2],
            'status': row[3]
        } for row in rows
    ])

@app.route('/download/<code_id>', methods=['GET'])
def download_code(code_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT code, filename FROM codes WHERE id = ?', (code_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Not found'}), 404

    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
    temp_file.write(row[0])
    temp_file.close()

    return send_file(temp_file.name, as_attachment=True, download_name=row[1])

@app.route('/delete/<code_id>', methods=['DELETE'])
def delete_code(code_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM codes WHERE id = ?', (code_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'deleted'})

# ========== RUN SERVER ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
