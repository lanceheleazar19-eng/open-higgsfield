"""Servidor HTTP que imita la API de Ollama (/api/tags y /api/chat en streaming NDJSON)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOllama:
    def __init__(self):
        self.models = [
            {"name": "nomic-embed-text:latest", "size": 274_000_000, "details": {"family": "nomic-bert", "parameter_size": "137M"}},
            {"name": "llama3.2:3b", "size": 2_000_000_000, "details": {"family": "llama", "parameter_size": "3.2B"}},
            {"name": "qwen2.5:7b", "size": 4_700_000_000, "details": {"family": "qwen2", "parameter_size": "7.6B"}},
        ]
        self.reply_chunks = ["Hola", ", tienes ", "2 tareas", " pendientes."]
        self.mode = "ok"  # ok | http_error | midstream_error
        self.json_reply: dict = {"recuerdos": []}
        self.requests: list[dict] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silencio
                pass

            def _json(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/tags":
                    return self._json(200, {"models": fake.models})
                self._json(404, {"error": "not found"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                fake.requests.append(req)
                if fake.mode == "http_error":
                    return self._json(404, {"error": f"model '{req['model']}' not found"})
                if req.get("format") == "json":
                    return self._json(200, {"model": req["model"], "done": True,
                                            "message": {"role": "assistant", "content": json.dumps(fake.json_reply)}})
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                for i, c in enumerate(fake.reply_chunks):
                    if fake.mode == "midstream_error" and i == 2:
                        self.wfile.write(json.dumps({"error": "out of memory"}).encode() + b"\n")
                        return
                    msg = {"model": req["model"], "message": {"role": "assistant", "content": c}, "done": False}
                    self.wfile.write(json.dumps(msg).encode() + b"\n")
                    self.wfile.flush()
                self.wfile.write(json.dumps({"model": req["model"], "message": {"role": "assistant", "content": ""},
                                             "done": True, "done_reason": "stop"}).encode() + b"\n")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def start(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
