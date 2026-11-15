import ctypes
from ctypes import wintypes
import json
import os
import shutil
import subprocess
import platform
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import star_ai

PAGE = (star_ai.BASE / "chat_ar.html").read_text(encoding="utf-8")
PORT = 17849
DEVICE_ORIGINS = {
    "https://agent-ai-stayl.abdulstarzeki001.workers.dev",
    "https://ai-stayl-control.abdulstarzeki001.workers.dev",
    "https://abdulstarzeki001-sketch.github.io",
}
DEVICE_ACTIONS = {
    "notepad": ("open_app", {"app": "notepad"}),
    "calculator": ("open_app", {"app": "calculator"}),
    "explorer": ("open_app", {"app": "explorer"}),
    "powershell": ("open_app", {"app": "powershell"}),
    "kali": ("kali_status", {}),
    "status": ("system_status", {}),
    "diagnostics": ("system_status", {}),
    "terminal": ("open_terminal", {}),
    "kali-terminal": ("open_terminal", {}),
    "troubleshoot": ("open_settings", {}),
    "task-manager": ("open_monitor", {}),
    "resource-monitor": ("open_monitor", {}),
    "flush-dns": ("flush_dns", {}),
}
DEVICE_LOCK = threading.Lock()

# Optional private Tailscale Serve access; both values must be configured
# by the Windows setup script. Public tunnels / Funnel are not supported.
TAILSCALE_HOST = os.environ.get("STAR_AI_TAILSCALE_HOST", "").strip().lower().rstrip(".")
TAILSCALE_LOGIN = os.environ.get("STAR_AI_TAILSCALE_LOGIN", "").strip().lower()
if bool(TAILSCALE_HOST) != bool(TAILSCALE_LOGIN):
    raise RuntimeError("Tailscale access requires both STAR_AI_TAILSCALE_HOST and STAR_AI_TAILSCALE_LOGIN")
if TAILSCALE_HOST and (not TAILSCALE_HOST.endswith(".ts.net")
                      or "/" in TAILSCALE_HOST or ":" in TAILSCALE_HOST):
    raise RuntimeError("Tailscale host must be an exact *.ts.net hostname")



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


class MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.DWORD),
        ("load", wintypes.DWORD),
        ("total_physical", ctypes.c_uint64),
        ("available_physical", ctypes.c_uint64),
        ("total_page_file", ctypes.c_uint64),
        ("available_page_file", ctypes.c_uint64),
        ("total_virtual", ctypes.c_uint64),
        ("available_virtual", ctypes.c_uint64),
        ("available_extended_virtual", ctypes.c_uint64),
    ]


def read_cpu_times(kernel32):
    times = [wintypes.FILETIME() for _ in range(3)]
    if not kernel32.GetSystemTimes(*(ctypes.byref(value) for value in times)):
        return None
    return tuple((value.dwHighDateTime << 32) | value.dwLowDateTime for value in times)


def windows_diagnostics():
    disk = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
    values = [f"Windows OS build: {platform.version()}",
              f"Logical processors: {os.cpu_count() or 'unknown'}",
              f"System drive available: {disk.free / 2**30:.1f} GiB of {disk.total / 2**30:.1f} GiB"]
    kernel32 = ctypes.windll.kernel32
    kernel32.GetTickCount64.restype = ctypes.c_uint64
    values.append(f"Uptime: {kernel32.GetTickCount64() / 3600000:.1f} hours")
    memory = MemoryStatus()
    memory.length = ctypes.sizeof(memory)
    if kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        values.append(f"RAM available: {memory.available_physical / 2**30:.2f} GiB "
                      f"of {memory.total_physical / 2**30:.2f} GiB ({memory.load}% used)")
    before = read_cpu_times(kernel32)
    if before is not None:
        time.sleep(1)
        after = read_cpu_times(kernel32)
        if after is not None:
            idle, kernel, user = (end - start for start, end in zip(before, after))
            total = kernel + user
            if total > 0:
                values.append(f"CPU utilization (1-second sample): {100 * (total - idle) / total:.1f}%")
    return "\n".join(values)


def run_support_action(action):
    if action == "diagnostics":
        star_ai.audit("system_status", "device:diagnostics")
        return windows_diagnostics()
    if action in {"task-manager", "resource-monitor"}:
        executable, title = {
            "task-manager": ("Taskmgr.exe", "مدير المهام"),
            "resource-monitor": ("resmon.exe", "مراقب الموارد"),
        }[action]
        path = os.path.join(os.environ["SystemRoot"], "System32", executable)
        subprocess.Popen([path], shell=False)
        star_ai.audit("executed", f"device:{action}")
        return f"تم إرسال طلب فتح {title}."
    if action == "troubleshoot":
        os.startfile("ms-settings:troubleshoot")
        star_ai.audit("executed", "device:troubleshoot")
        return "تم طلب فتح إعدادات استكشاف الأخطاء في Windows."
    if action == "flush-dns":
        cmd = os.path.join(os.environ["SystemRoot"], "System32", "ipconfig.exe")
        result = subprocess.run([cmd, "/flushdns"], capture_output=True, timeout=15,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        star_ai.audit("executed", f"device:flush-dns exit:{result.returncode}")
        if result.returncode != 0:
            return "تعذّر مسح ذاكرة DNS. تحقّق من صلاحيات حساب Windows."
        return "تم مسح ذاكرة DNS في Windows."
    terminal = shutil.which("wt.exe")
    if not terminal:
        return "تعذّر العثور على Windows Terminal."
    command = [terminal, "new-tab"]
    if action == "kali-terminal":
        command = [terminal, "-w", "-1", "new-tab", "wsl.exe", "--distribution", "kali-linux"]
    subprocess.Popen(command, shell=False)
    star_ai.audit("executed", f"device:{action}")
    return "تم إرسال طلب فتح Kali في نافذة Windows Terminal جديدة." if action == "kali-terminal" else "تم إرسال طلب فتح Windows Terminal."


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
        if self.path in {"/device-action", "/device-status"} and self.device_origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            if self.command == "OPTIONS":
                self.send_header("Access-Control-Allow-Methods", "GET, POST")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Star-Token")
                if self.headers.get("Access-Control-Request-Private-Network") == "true":
                    self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(data)

    def is_remote_request(self):
        host = str(self.headers.get("Host", "")).lower()
        return bool(self.headers.get("Tailscale-User-Login")) or (
            bool(TAILSCALE_HOST) and host in {TAILSCALE_HOST, TAILSCALE_HOST + ":443"}
        )

    def trusted_request(self):
        host = str(self.headers.get("Host", "")).lower()
        if self.is_remote_request():
            # Tailscale Serve injects this identity header after stripping
            # any client-supplied spoofed header. Never use Tailscale Funnel.
            login = str(self.headers.get("Tailscale-User-Login", "")).lower()
            return (bool(TAILSCALE_HOST and TAILSCALE_LOGIN)
                    and secrets.compare_digest(login, TAILSCALE_LOGIN)
                    and host in {TAILSCALE_HOST, TAILSCALE_HOST + ":443", self.server.host})
        return host == self.server.host

    def authorized(self):
        return (self.trusted_request()
                and secrets.compare_digest(str(self.headers.get("X-Star-Token") or ""), TOKEN))

    def page_origin(self):
        if not self.trusted_request():
            return None
        if self.is_remote_request():
            return "https://" + TAILSCALE_HOST
        return f"http://{self.server.host}"

    def do_GET(self):
        if not self.trusted_request():
            self.send(403)
        elif self.path == "/":
            self.send(200, PAGE.replace("__STAR_TOKEN__", TOKEN), "text/html")
        elif self.path == "/state" and self.authorized():
            with LOCK:
                payload = json.dumps(state, ensure_ascii=False)
            self.send(200, payload, "application/json")
        elif self.path == "/device-status" and self.device_authenticated():
            self.send(200, json.dumps({"status": "paired",
                                      "mode": "remote" if self.is_remote_request() else "local"}),
                      "application/json")
        else:
            self.send(404)

    def device_origin_allowed(self):
        return (self.trusted_request()
                and self.headers.get("Origin") in DEVICE_ORIGINS)

    def device_authenticated(self):
        return (self.device_origin_allowed()
                and secrets.compare_digest(str(self.headers.get("X-Star-Token") or ""), TOKEN))

    def do_OPTIONS(self):
        requested_method = self.headers.get("Access-Control-Request-Method")
        if (self.path in {"/device-action", "/device-status"}
                and self.device_origin_allowed()
                and requested_method == ("POST" if self.path == "/device-action" else "GET")):
            self.send(204)
        else:
            self.send(403)

    def device_action(self):
        if not self.device_authenticated() or self.headers.get_content_type() != "application/json":
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
            elif action not in {"status", "diagnostics"} and self.is_remote_request() and payload.get("approved") is not True:
                star_ai.audit("denied", f"remote-device:{action}")
                reply = "يحتاج هذا الإجراء موافقة صريحة من المستخدم على الآيفون."
            elif action not in {"status", "diagnostics"} and not self.is_remote_request() and not (
                ctypes.windll.user32.MessageBoxW(
                    None,
                    f"AI Stayl requests a device action:\n{action}\nAllow this action?",
                    "STAR AI - Local Approval",
                    0x24,
                ) == 6
            ):
                star_ai.audit("denied", f"device:{action}")
                reply = "تم رفض الإجراء من نافذة تأكيد Windows."
            elif action not in {"status", "diagnostics"} and self.is_remote_request():
                star_ai.audit("approved", f"remote-device:{action}")
                reply = run_support_action(action) if action in {
                    "terminal", "kali-terminal", "troubleshoot", "flush-dns",
                    "task-manager", "resource-monitor"
                } else star_ai.run_tool(tool, args, approve=lambda _: True)
            elif action in {"diagnostics", "terminal", "kali-terminal", "troubleshoot", "flush-dns", "task-manager", "resource-monitor"}:
                reply = run_support_action(action)
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
        if not self.authorized() or self.headers.get("Origin") != self.page_origin():
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

