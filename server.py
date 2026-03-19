import http.server
import socketserver
import json
import base64
import os
import time
import tarfile
import io
import sqlite3

PORT = 8000
UPLOAD_DIR = 'uploads'
DB_FILE = 'signatures.db'

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            filename TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def check_auth(headers):
    auth_header = headers.get('Authorization')
    if not auth_header:
        return False
    if not auth_header.startswith('Basic '):
        return False

    encoded_credentials = auth_header.split(' ')[1]
    decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')

    if ':' not in decoded_credentials:
        return False

    username, password = decoded_credentials.split(':', 1)

    expected_password = os.environ.get('SENHA_ADMIN')
    if expected_password is None:
        return False

    return username == 'admin' and password == expected_password

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def send_auth_required(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Admin Access"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>401 Unauthorized</h1></body></html>')

    def do_GET(self):
        if self.path == '/admin.html' or self.path.startswith('/api/') or self.path == '/download_tar':
            if not check_auth(self.headers):
                self.send_auth_required()
                return

        if self.path == '/api/signatures':
            try:
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT matricula, nome, filename, timestamp FROM signatures ORDER BY timestamp DESC")
                rows = cursor.fetchall()
                conn.close()

                signatures = [dict(row) for row in rows]

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()

                response = {'status': 'success', 'signatures': signatures}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'status': 'error', 'message': str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif self.path == '/download_tar':
            try:
                # Fetch filenames from DB
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("SELECT filename FROM signatures")
                rows = cursor.fetchall()
                conn.close()

                valid_filenames = {row[0] for row in rows}

                # Create an in-memory tar file
                tar_stream = io.BytesIO()
                with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                    for filename in valid_filenames:
                        file_path = os.path.join(UPLOAD_DIR, filename)
                        if os.path.exists(file_path):
                            tar.add(file_path, arcname=os.path.join('signatures', filename))

                tar_stream.seek(0)

                self.send_response(200)
                self.send_header('Content-type', 'application/x-tar')
                self.send_header('Content-Disposition', 'attachment; filename="signatures.tar"')
                self.end_headers()

                self.wfile.write(tar_stream.read())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'status': 'error', 'message': str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/reset':
            if not check_auth(self.headers):
                self.send_auth_required()
                return

            try:
                # Clear DB
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM signatures")
                conn.commit()
                conn.close()

                # Delete files
                for f in os.listdir(UPLOAD_DIR):
                    if f.endswith('.png'):
                        os.remove(os.path.join(UPLOAD_DIR, f))

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'status': 'success'}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'status': 'error', 'message': str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        if self.path == '/api/delete':
            if not check_auth(self.headers):
                self.send_auth_required()
                return

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode('utf-8'))
                matricula = data.get('matricula')

                if not matricula:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {'status': 'error', 'message': 'Matrícula não informada.'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return

                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()

                # Fetch filename before deleting
                cursor.execute("SELECT filename FROM signatures WHERE matricula = ?", (matricula,))
                row = cursor.fetchone()

                if row:
                    filename = row[0]
                    file_path = os.path.join(UPLOAD_DIR, filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)

                    cursor.execute("DELETE FROM signatures WHERE matricula = ?", (matricula,))
                    conn.commit()
                    conn.close()

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {'status': 'success'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                else:
                    conn.close()
                    self.send_response(404)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {'status': 'error', 'message': 'Assinatura não encontrada.'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'status': 'error', 'message': str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        if self.path == '/upload':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode('utf-8'))
                matricula = data.get('matricula', 'unknown')
                nome = data.get('nome', 'unknown')
                image_data = data.get('image', '')

                # Check if matricula already exists
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM signatures WHERE matricula = ?", (matricula,))
                if cursor.fetchone() is not None:
                    conn.close()
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {'status': 'error', 'message': 'Já existe uma assinatura para a matrícula informada.'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return

                # Get IP
                ip = self.client_address[0]

                # Get timestamp
                timestamp = int(time.time())

                if image_data.startswith('data:image'):
                    # format: data:image/png;base64,iVBORw0KGgo...
                    header, encoded = image_data.split(',', 1)
                else:
                    encoded = image_data

                file_name = f"{timestamp}_{matricula}_{ip}.png"
                file_path = os.path.join(UPLOAD_DIR, file_name)

                with open(file_path, "wb") as fh:
                    fh.write(base64.b64decode(encoded))

                cursor.execute(
                    "INSERT INTO signatures (matricula, nome, filename, timestamp) VALUES (?, ?, ?, ?)",
                    (matricula, nome, file_name, timestamp)
                )
                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'status': 'success', 'file': file_name}
                self.wfile.write(json.dumps(response).encode('utf-8'))

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'status': 'error', 'message': str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

Handler = CustomHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print("Serving at port", PORT)
    httpd.serve_forever()
