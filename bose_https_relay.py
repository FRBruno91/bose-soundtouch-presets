# -*- coding: utf-8 -*-
"""Relais local : un flux https est redonné en http aux enceintes SoundTouch.

Le serveur n'écoute que pour les enceintes du réseau. L'enregistrement d'une
adresse ne se fait que depuis Home Assistant lui-même. Les adresses privées
sont refusées.
"""
import base64
import ipaddress
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8766
UA = "HomeAssistant-Bose/1.0"
TOKENS = {}
LOCK = threading.Lock()


def lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    finally:
        sock.close()


def client_is_local(host):
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host in ("localhost",)
    return ip.is_loopback


def public_target(url):
    raw = (url or "").strip()
    parts = urllib.parse.urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("adresse")
    if ".m3u8" in raw.lower() or " " in raw or len(raw) > 2000:
        raise ValueError("adresse")
    host = parts.hostname.strip("[]")
    if host.lower() == "localhost":
        raise ValueError("privee")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("adresse") from exc
    if not infos:
        raise ValueError("adresse")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError("privee")
    return raw


def remember(url):
    clean = public_target(url)
    if clean.lower().startswith("http://"):
        return clean
    token = secrets.token_hex(8)
    with LOCK:
        while len(TOKENS) > 80:
            TOKENS.pop(next(iter(TOKENS)))
        TOKENS[token] = clean
    return "http://%s:%s/s/%s" % (lan_ip(), PORT, token)


def open_upstream(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Icy-MetaData": "1"},
    )
    return urllib.request.urlopen(req, timeout=12)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/health":
            if not client_is_local(self.client_address[0]):
                self.send_error(404)
                return
            body = b"ok"
            self._send(200, "text/plain", body)
            return
        if path.startswith("/s/"):
            token = path[3:]
            with LOCK:
                upstream = TOKENS.get(token)
            if not upstream:
                self.send_error(404)
                return
            self._proxy(upstream)
            return
        self.send_error(404)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/register":
            self.send_error(404)
            return
        if not client_is_local(self.client_address[0]):
            self.send_error(403)
            return
        length = int(self.headers.get("Content-Length") or "0")
        if length < 1 or length > 4000:
            self.send_error(400)
            return
        raw = self.rfile.read(length).decode("utf-8", "replace")
        try:
            local = remember(raw)
        except ValueError:
            self.send_error(400)
            return
        self._send(200, "text/plain; charset=utf-8", local.encode("utf-8"))

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, upstream):
        try:
            resp = open_upstream(upstream)
        except Exception:
            self.send_error(502)
            return
        ctype = resp.headers.get("Content-Type", "audio/mpeg")
        if "text/html" in ctype.lower() or "json" in ctype.lower():
            resp.close()
            self.send_error(502)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        for key in ("icy-name", "icy-br", "icy-metaint", "ice-audio-info"):
            value = resp.headers.get(key)
            if value:
                self.send_header(key, value)
        self.end_headers()
        try:
            while True:
                chunk = resp.read(16384)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except Exception:
            pass
        finally:
            resp.close()

    def log_message(self, fmt, *args):
        return


def serve():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()


def healthy():
    try:
        with urllib.request.urlopen("http://127.0.0.1:%s/health" % PORT, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False


def ensure():
    if healthy():
        return
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--serve"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=os.path.dirname(os.path.abspath(__file__)) or "/config",
    )
    for _ in range(25):
        time.sleep(0.2)
        if healthy():
            return
    raise RuntimeError("relais arrete")


def register_and_print(payload):
    url = base64.b64decode(payload).decode("utf-8").strip()
    if url.lower().startswith("http://"):
        public_target(url)
        print(url)
        return
    ensure()
    data = url.encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:%s/register" % PORT,
        data=data,
        headers={"Content-Type": "text/plain"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(resp.read().decode("utf-8").strip())


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--serve":
        serve()
        return 0
    if len(sys.argv) == 3 and sys.argv[1] == "--register":
        register_and_print(sys.argv[2])
        return 0
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(1)
