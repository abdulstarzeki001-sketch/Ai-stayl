import json
import platform
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import star_ai

PAGE = (star_ai.BASE / "chat_ar.html").read_text(encoding="utf-8")
PORT = 17849
DEVICE_ORIGINS = {
    "https://agent-ai-stayl.abdulstarzeki001.workers.dev",
    "https://abdulstarzeki001-sketch.github.io",
}
DEVICE_ACTIONS = {
    "notepad": ("open_app", {"app": "notepad"}),
    "calculator": ("open_app", {"app": "calculator"}),
    "explorer": ("open_app", {"app": "explorer"}),
    "powershell": ("open_app", {"app": "powershell"}),
    "kali": ("kali_status", {}),
    "status": ("system_status", {}),
}
DEVICE_LOCK = threading.Lock()


TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
state = {"busy": False, "output": [], "prompt": None}
decision = threading.Event()
approved = False


def emit(*parts):
    with LOCK:
        state["output"].append(" ".join(map(str, parts)).strip())


def approve(title):
    with LOCK:
        decision.clear()
        state["prompt"] = title
    if not decision.wait(120):
        return False
    with LOCK:
        return approved


def respond(question):
    db = None
    try:
        db = star_ai.connect_db()
        if question == "/status":
            emit(star_ai.run_tool("system_status", {}))
        elif question == "/kali":
            emit(star_ai.run_tool("kali_status", {}, approve=approve))
        else:
            star_ai.handle(db, question, emit=emit, approve=approve)
    except Exception as error:
        emit(f"تعذّر إكمال الطلب. {error}")
    finally:
        if db is not None:
            db.close()
        with LOCK:
            state.update(busy=False, prompt=None)


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body="", content_type="text/plain"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        origin = self.headers.get("Origin")
        if self.path == "/device-action" and origin in DEVICE_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            if self.command == "OPTIONS":
                self.send_header("Access-Control-Allow-Methods", "POST")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                if self.headers.get("Access-Control-Request-Private-Network") == "true":
                    self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        return (self.headers.get("Host") == self.server.host
                and secrets.compare_digest(self.headers.get("X-Star-Token", ""), TOKEN))

    def do_GET(self):
        if self.headers.get("Host") != self.server.host:
            self.send(403)
        elif self.path == "/":
            self.send(200, PAGE.replace("__STAR_TOKEN__", TOKEN), "text/html")
        elif self.path == "/state" and self.authorized():
            with LOCK:
                payload = json.dumps(state, ensure_ascii=False)
            self.send(200, payload, "application/json")
        else:
            self.send(404)

    def device_origin_allowed(self):
        return (self.headers.get("Host") == self.server.host
                and self.headers.get("Origin") in DEVICE_ORIGINS)

    def do_OPTIONS(self):
        if (self.path == "/device-action" and self.device_origin_allowed()
                and self.headers.get("Access-Control-Request-Method") == "POST"):
            self.send(204)
        else:
            self.send(403)

    def device_action(self):
        if not self.device_origin_allowed() or self.headers.get_content_type() != "application/json":
            self.send(403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 256:
                raise ValueError
            payload = json.loads(self.rfile.read(length))
            action = payload.get("action") if isinstance(payload, dict) else None
            if not isinstance(action, str) or action not in DEVICE_ACTIONS:
                raise ValueError
        except (ValueError, UnicodeError):
            self.send(400)
            return
        if not DEVICE_LOCK.acquire(blocking=False):
            self.send(409)
            return
        try:
            tool, args = DEVICE_ACTIONS[action]
            if platform.system() != "Windows":
                reply = "أوامر الجهاز متاحة على Windows."
            elif action == "status":
                reply = f"Windows: {platform.version()}"
                star_ai.audit("system_status", "device:version")
            else:
                reply = star_ai.run_tool(tool, args, approve=lambda _: True)
        except Exception:
            reply = "تعذّر تنفيذ الإجراء المحلي."
        finally:
            DEVICE_LOCK.release()
        self.send(200, json.dumps({"reply": reply}, ensure_ascii=False), "application/json")

    def do_POST(self):
        global approved
        if self.path == "/device-action":
            self.device_action()
            return
        if not self.authorized() or self.headers.get("Origin") != f"http://{self.server.host}":
            self.send(403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 25000:
                raise ValueError
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError
        except (ValueError, UnicodeError):
            self.send(400)
            return

        with LOCK:
            if self.path == "/ask" and not state["busy"]:
                question = payload.get("text")
                if not isinstance(question, str) or not question.strip() or len(question) > 6000:
                    self.send(400)
                    return
                state.update(busy=True, output=[], prompt=None)
                threading.Thread(target=respond, args=(question.strip(),), daemon=True).start()
            elif self.path == "/confirm" and state["prompt"] is not None:
                approved = payload.get("allow") is True
                state["prompt"] = None
                decision.set()
            else:
                self.send(409)
                return
        self.send(204)

    def log_message(self, *_args):
        pass


def main():
    with ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as server:
        server.host = f"127.0.0.1:{server.server_port}"
        star_ai.audit("startup", f"browser:{star_ai.MODEL}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

