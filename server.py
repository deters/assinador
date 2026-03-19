import http.server
import socketserver
import json
import base64
import os
import time
import tarfile
import io

PORT = 8000
UPLOAD_DIR = 'uploads'

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/signatures':
            try:
                files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith('.png')]
                # Sort by timestamp (filename starts with timestamp)
                files.sort(reverse=True)

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()

                response = {'status': 'success', 'files': files}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'status': 'error', 'message': str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif self.path == '/download_tar':
            try:
                # Create an in-memory tar file
                tar_stream = io.BytesIO()
                with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                    tar.add(UPLOAD_DIR, arcname='signatures')

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
        if self.path == '/upload':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode('utf-8'))
                matricula = data.get('matricula', 'unknown')
                nome = data.get('nome', 'unknown')
                image_data = data.get('image', '')

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
