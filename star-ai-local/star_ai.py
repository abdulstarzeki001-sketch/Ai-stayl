#!/usr/bin/env python3
"""STAR AI Manager Starter: local Ollama + approved, allowlisted desktop tools.

Windows 11, Python stdlib only. No network server or remote access.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import time
import textwrap
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from arabic_reshaper import ArabicReshaper
    from bidi.algorithm import get_display
except ImportError:
    ArabicReshaper = None
    get_display = None

BASE = Path(__file__).resolve().parent
DATA = BASE / "memory"
LOGS = BASE / "logs"
DB = DATA / "star_ai.sqlite3"
AUDIT = LOGS / "events.jsonl"
MODEL = os.environ.get("STAR_AI_MODEL", "qwen3:1.7b")
API = "http://127.0.0.1:11434/api/chat"
reshaper = (
    ArabicReshaper(configuration={"delete_harakat": False, "shift_harakat_position": True})
    if ArabicReshaper is not None else None
)

DATA.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

SYSTEM = """أنت STAR AI MANAGER، مساعد تقني عربي يعمل محلياً على جهاز المستخدم.
تحدّث بالعربية باختصار. لديك أدوات محدودة وآمنة فقط. لا تدّع تنفيذ أي إجراء
إلا إذا أعاد التنفيذ نتيجة نجاح صريحة. إذا لم تكن أداة لازمة أو كانت خارج صلاحياتك
فاشرح ما تستطيع فعله. لا تطلب الأسرار ولا تنفذ أوامر PowerShell أو Kali حرة.
استخدم أداة واحدة في كل استجابة، ولا تستخدم الأداة إذا لم يطلب المستخدم إجراءً فعلياً.
"""

TOOLS = [
    {"type": "function", "function": {
        "name": "system_status", "description": "عرض حالة Windows ونسخة Python والوقت والذاكرة المتوفرة بشكل قراءة فقط",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "open_app", "description": "فتح تطبيق من القائمة المسموح بها بعد موافقة المستخدم: notepad, calculator, vscode, powershell, explorer",
        "parameters": {"type": "object", "properties": {"app": {"type": "string", "enum": ["notepad", "calculator", "vscode", "powershell", "explorer"]}},
                       "required": ["app"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "kali_status", "description": "فحص Kali WSL2 وتشغيل أوامر تعريف ثابتة فقط بعد الموافقة (whoami و uname)",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
]

ALLOWED_APPS = {
    "notepad": (["notepad.exe"], "المفكرة"),
    "calculator": (["calc.exe"], "الحاسبة"),
    "powershell": (["powershell.exe", "-NoProfile"], "PowerShell"),
    "explorer": (["explorer.exe", str(BASE)], "مستكشف الملفات"),
    "vscode": (["code"], "Visual Studio Code"),
}


def terminal_text(text: str, width: int) -> str:
    if reshaper is None or get_display is None:
        return text

    displayed = []
    for line in text.split("\n"):
        if not any(unicodedata.bidirectional(char) == "AL" for char in line):
            displayed.append(line)
            continue
        for part in textwrap.wrap(line, width, break_long_words=False, break_on_hyphens=False):
            displayed.append(get_display(reshaper.reshape(part), base_dir="R"))
    return "\n".join(displayed)


def show(*parts: object) -> None:
    text = " ".join(map(str, parts))
    width = max(1, shutil.get_terminal_size().columns - 1)
    print(terminal_text(text, width) if sys.stdout.isatty() else text)


def audit(event: str, detail: str = "") -> None:
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, "detail": detail[:400]}
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def connect_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB)
    db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)")
    db.commit()
    return db


def save(db: sqlite3.Connection, role: str, content: str) -> None:
    db.execute("INSERT INTO messages(role,content,created_at) VALUES(?,?,?)", (role, content, datetime.now(timezone.utc).isoformat()))
    db.commit()


def history(db: sqlite3.Connection) -> list[dict[str, str]]:
    rows = db.execute("SELECT role,content FROM (SELECT id,role,content FROM messages ORDER BY id DESC LIMIT 10) ORDER BY id").fetchall()
    return [{"role": r, "content": c} for r, c in rows]


def chat(messages: list[dict[str, Any]], *, tools: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": MODEL, "messages": messages, "stream": False, "options": {"num_ctx": 4096, "num_predict": 400}}
    if tools:
        payload["tools"] = TOOLS
    request = urllib.request.Request(API, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
            message = data.get("message", {})
            if not isinstance(message, dict):
                raise ValueError("Ollama did not return a message object")
            return message
    except urllib.error.URLError as e:
        raise RuntimeError("تعذر الاتصال بـ Ollama على 127.0.0.1:11434. افتح Ollama ثم تحقق من وجود النموذج.") from e


def confirm(title: str) -> bool:
    show(f"\n[موافقة مطلوبة] {title}")
    show("اكتب نعم للتنفيذ، وأي شيء آخر للإلغاء.")
    answer = input("> ").strip().lower()
    return answer in {"نعم", "yes", "y"}


def run_tool(name: str, args: dict[str, Any], *, approve=confirm) -> str:
    if name == "system_status":
        result = f"Windows: {platform.platform()}\nPython: {platform.python_version()}\nFolder: {BASE}\nModel: {MODEL}"
        if os.name == "nt":
            try:
                p = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                                    "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
                                   capture_output=True, text=True, timeout=20, check=False)
                if p.returncode == 0 and p.stdout.strip().isdigit():
                    result += f"\nAvailable RAM: {round(int(p.stdout.strip()) / 1048576, 2)} GB"
            except (OSError, subprocess.TimeoutExpired):
                pass
        audit("system_status", "read-only")
        return result

    if name == "open_app":
        app = args.get("app")
        if not isinstance(app, str) or app not in ALLOWED_APPS:
            audit("denied", "unsupported app")
            return "مرفوض: هذا التطبيق غير موجود في القائمة المسموح بها."
        cmd, label = ALLOWED_APPS[app]
        if not approve(f"فتح {label} على جهازك؟"):
            audit("cancelled", f"open_app:{app}")
            return f"ألغيت فتح {label}."
        try:
            if app == "vscode":
                executable = shutil.which("code.cmd") or shutil.which("code.exe") or shutil.which("code")
                if not executable:
                    return "تعذر العثور على VS Code عبر PATH. افتحه يدوياً أو أضف أمر code إلى PATH."
                subprocess.Popen([executable], shell=False)
            else:
                subprocess.Popen(cmd, shell=False)
            audit("executed", f"open_app:{app}")
            return f"تم إرسال أمر فتح {label} بنجاح (لا يؤكد ظهور نافذته على الشاشة)."
        except OSError as e:
            audit("error", f"open_app:{app}")
            return f"فشل تشغيل التطبيق: {type(e).__name__}: {e}"

    if name == "kali_status":
        if os.name != "nt":
            return "فحص Kali عبر WSL متاح على Windows فقط."
        if not approve("تشغيل Kali WSL2 لفحص whoami و uname فقط؟"):
            audit("cancelled", "kali_status")
            return "ألغيت فحص Kali."
        try:
            p = subprocess.run(["wsl.exe", "-d", "kali-linux", "--", "sh", "-c", "whoami; uname -sr"],
                               capture_output=True, text=True, timeout=50, check=False)
            audit("executed", f"kali_status exit:{p.returncode}")
            return f"Exit: {p.returncode}\n{(p.stdout or p.stderr)[:2000]}"
        except (OSError, subprocess.TimeoutExpired) as e:
            audit("error", "kali_status")
            return f"فشل الفحص: {e}"

    audit("denied", "tool not allowlisted")
    return "مرفوض: الأداة غير مسموح بها."


def handle(db: sqlite3.Connection, question: str, *, emit=show, approve=confirm) -> None:
    if len(question) > 6000:
        emit("الطلب طويل جداً لهذه النسخة.")
        return
    # Prefer deterministic routing for our first smoke tests; this does not rely on LLM tool-call accuracy.
    simple = question.strip().lower().replace("أ", "ا").replace("إ", "ا")
    direct_actions = {
        "افتح المفكرة": ("open_app", {"app": "notepad"}),
        "افتح الحاسبة": ("open_app", {"app": "calculator"}),
        "افتح الالة الحاسبة": ("open_app", {"app": "calculator"}),
        "افتح powershell": ("open_app", {"app": "powershell"}),
        "افتح باورشيل": ("open_app", {"app": "powershell"}),
        "افتح vscode": ("open_app", {"app": "vscode"}),
        "افتح vs code": ("open_app", {"app": "vscode"}),
        "افتح مستكشف الملفات": ("open_app", {"app": "explorer"}),
        "افحص kali": ("kali_status", {}),
        "افحص كالي": ("kali_status", {}),
        "ما حالة جهازي؟": ("system_status", {}),
    }
    if simple in direct_actions:
        name, args = direct_actions[simple]
        result = run_tool(name, args, approve=approve)
        emit("\n[نتيجة التنفيذ]\n" + result)
        save(db, "user", question)
        save(db, "assistant", result)
        return
    messages = [{"role": "system", "content": SYSTEM}] + history(db) + [{"role": "user", "content": question}]
    try:
        answer = chat(messages)
        calls = answer.get("tool_calls") or []
        if isinstance(calls, list) and calls:
            item = calls[0]
            fn = item.get("function") if isinstance(item, dict) else None
            fn = fn if isinstance(fn, dict) else {}
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            # Only one tool call per turn; no unrestricted shell input is ever accepted.
            result = run_tool(name, args, approve=approve)
            emit("\n[نتيجة التنفيذ]\n" + result)
            final_text = result
        else:
            final_text = str(answer.get("content", "")).strip() or "لم أستلم رداً مفهوماً من النموذج."
            emit("\nSTAR AI: " + final_text)
        save(db, "user", question)
        save(db, "assistant", final_text)
    except (RuntimeError, ValueError, TimeoutError) as e:
        audit("error", type(e).__name__)
        emit("\nخطأ: " + str(e))


def main() -> int:
    if os.name != "nt":
        show("هذه النسخة مخصصة لـ Windows 11. تستطيع اختبار ملفاتها في بيئات أخرى دون تشغيل التطبيقات.")
    show("\n=== STAR AI MANAGER / local preview ===")
    show(f"النموذج: {MODEL}")
    show("مساعدة: /help | حالة الجهاز: /status | فحص Kali: /kali | خروج: /exit")
    show("لا توجد صلاحيات Administrator أو تنفيذ أوامر حرة. كل إجراء تشغيلي يحتاج موافقتك.")
    audit("startup", MODEL)
    db = connect_db()
    try:
        while True:
            try:
                q = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q:
                continue
            if q.lower() in ("/exit", "/quit", "خروج"):
                break
            if q == "/help":
                show("جرّب: افتح المفكرة، افتح PowerShell، افحص Kali، ما حالة جهازي؟")
                continue
            if q == "/status":
                show(run_tool("system_status", {}))
                continue
            if q == "/kali":
                show(run_tool("kali_status", {}))
                continue
            handle(db, q)
    finally:
        audit("shutdown", "normal")
        db.close()
    show("تم إيقاف STAR AI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
