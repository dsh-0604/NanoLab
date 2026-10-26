# -*- coding: utf-8 -*-
"""本地桥接：NanoCode 通过 HTTP 把代码送来，实验室把串口输出送回去。

接口（和之前网页版完全一致，NanoCode 那边不用改地址）：
  GET  /api/health
  POST /api/run     {"code": "...", "board": "...", "filename": "main.cpp"}
  POST /api/stop
  POST /api/serial  {"text": "on"}
  GET  /api/output?since=N
  POST /api/watch   {"path": "D:\\PlatformIO\\c3_blink\\src"}
  GET  /api/lab/open
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8765
VERSION = "2.0.0"


class Bridge:
    def __init__(self, port: int = PORT):
        self.port = port
        self.pending: queue.Queue = queue.Queue()
        self.outbox: list[dict] = []
        self.seq = 0
        self.lock = threading.Lock()
        self.watch_dir: str | None = None
        self._watch_seen: dict[str, float] = {}
        self._stop = threading.Event()
        self.httpd: ThreadingHTTPServer | None = None
        self.error: str | None = None

    # ------------------------------------------------------------ 对外
    def push_output(self, text: str, stream: str = "out"):
        with self.lock:
            self.seq += 1
            self.outbox.append({"seq": self.seq, "text": text, "stream": stream,
                                "t": int(time.time() * 1000) % 100000000})
            if len(self.outbox) > 4000:
                del self.outbox[:2000]

    def take_pending(self):
        items = []
        while True:
            try:
                items.append(self.pending.get_nowait())
            except queue.Empty:
                break
        return items

    def set_watch(self, path: str):
        self.watch_dir = path or None
        self._watch_seen.clear()

    # ------------------------------------------------------------ 启动
    def start(self) -> bool:
        try:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), self._handler())
            self.httpd.daemon_threads = True
        except OSError as e:
            self.error = "端口 %d 被占用：%s" % (self.port, e)
            return False
        threading.Thread(target=self.httpd.serve_forever, name="bridge", daemon=True).start()
        threading.Thread(target=self._watch_loop, name="watch", daemon=True).start()
        return True

    def stop(self):
        self._stop.set()
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

    # ------------------------------------------------------------ 文件监听
    def _watch_loop(self):
        while not self._stop.is_set():
            d = self.watch_dir
            if d and os.path.isdir(d):
                try:
                    names = [n for n in os.listdir(d) if n.lower().endswith((".cpp", ".ino", ".c"))]
                except OSError:
                    names = []
                for n in names:
                    p = os.path.join(d, n)
                    try:
                        m = os.path.getmtime(p)
                    except OSError:
                        continue
                    if self._watch_seen.get(p) == m:
                        continue
                    self._watch_seen[p] = m
                    if m < time.time() - 90:
                        continue
                    try:
                        with open(p, "r", encoding="utf-8", errors="replace") as f:
                            code = f.read()
                    except OSError:
                        continue
                    if code.strip():
                        self.pending.put({"code": code, "board": None, "filename": n})
            self._stop.wait(0.6)

    # ------------------------------------------------------------ HTTP
    def _handler(self):
        bridge = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "NanoCodeLab/" + VERSION

            def log_message(self, fmt, *args):
                pass

            def _send(self, code=200, body=b"", ctype="application/json; charset=utf-8"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def _json(self, obj, code=200):
                self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

            def _body(self):
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    n = 0
                if n <= 0:
                    return {}
                try:
                    return json.loads(self.rfile.read(n).decode("utf-8", "replace"))
                except Exception:
                    return {}

            def do_OPTIONS(self):
                self._send(204)

            def do_GET(self):
                u = urlparse(self.path)
                if u.path == "/api/health":
                    return self._json({"ok": True, "version": VERSION, "mode": "native",
                                       "watch_dir": bridge.watch_dir})
                if u.path == "/api/output":
                    since = 0
                    if u.query:
                        try:
                            since = int((parse_qs(u.query).get("since") or ["0"])[0])
                        except ValueError:
                            since = 0
                    with bridge.lock:
                        lines = [l for l in bridge.outbox if l["seq"] > since][-500:]
                        nxt = bridge.seq
                    return self._json({"lines": lines, "next": nxt})
                if u.path == "/api/pull":
                    return self._json({"pending": None, "command": None})
                if u.path == "/":
                    return self._json({"ok": True, "app": "NanoCode 电子实验室", "version": VERSION})
                return self._json({"ok": False, "error": "unknown api"}, 404)

            def do_POST(self):
                u = urlparse(self.path)
                body = self._body()
                if u.path == "/api/run":
                    code = (body.get("code") or "").strip()
                    if not code:
                        return self._json({"ok": False, "error": "code 为空"}, 400)
                    bridge.pending.put({"code": code, "board": body.get("board"),
                                        "filename": body.get("filename") or "main.cpp"})
                    bridge.push_output("[NanoCode] 收到代码 %d 字节" % len(code), "sys")
                    return self._json({"ok": True})
                if u.path == "/api/stop":
                    bridge.pending.put({"stop": True})
                    return self._json({"ok": True})
                if u.path == "/api/serial":
                    bridge.pending.put({"serial": body.get("text") or ""})
                    return self._json({"ok": True})
                if u.path == "/api/watch":
                    d = (body.get("path") or "").strip()
                    bridge.set_watch(d)
                    return self._json({"ok": True, "watch_dir": bridge.watch_dir})
                if u.path == "/api/arrange":
                    bridge.pending.put({"arrange": True})
                    return self._json({"ok": True})
                if u.path == "/api/lab/open":
                    return self._json({"ok": True, "url": "native"})
                return self._json({"ok": False, "error": "unknown api"}, 404)

        return H
