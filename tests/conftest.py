import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
PETSTORE = str(EXAMPLES / "petstore.yaml")


class FakePetstore(BaseHTTPRequestHandler):
    """Tiny local API: records every request and answers like the petstore spec."""
    requests: list[dict] = []

    def _record(self, body=None):
        FakePetstore.requests.append({"method": self.command, "path": self.path, "headers": dict(self.headers), "body": body})

    def _send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._record()
        if self.path.startswith("/v1/pets/"):
            pet_id = int(self.path.split("/")[3].split("?")[0])
            return self._send(200, {"id": pet_id, "name": "Rex", "status": "available"})
        if self.path.startswith("/v1/pets"):
            return self._send(200, [{"id": 1, "name": "Rex"}, {"id": 2, "name": "Mia"}])
        if self.path.startswith("/v1/big"):
            return self._send(200, {"blob": "x" * 5000})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self._record(body)
        self._send(201, {"id": 3, **body})

    def log_message(self, *a):
        pass


@pytest.fixture
def fake_api():
    FakePetstore.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakePetstore)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/v1", FakePetstore.requests
    server.shutdown()
