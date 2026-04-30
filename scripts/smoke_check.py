from __future__ import annotations

import importlib
import os
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULES = [
    "app.main",
    "app.config",
    "app.routers.assistant",
    "app.routers.group_assistant",
    "app.routers.miniapp",
    "app.services.brain",
    "app.services.deep_research",
    "app.services.dialogue",
    "app.services.web_search",
    "app.services.security",
    "app.services.abuse",
    "app.services.backup",
    "app.services.backup_scheduler",
    "app.services.privacy",
    "app.services.audit",
    "app.routers.privacy",
    "app.services.llm",
    "app.services.documents",
]


def _ok(text: str) -> None:
    print(f"✅ {text}")


def _warn(text: str) -> None:
    print(f"⚠️ {text}")


def _fail(text: str) -> None:
    print(f"❌ {text}")


def check_imports() -> bool:
    success = True

    for module_name in MODULES:
        try:
            importlib.import_module(module_name)
            _ok(f"import {module_name}")
        except Exception as exc:
            success = False
            _fail(f"import {module_name}: {exc}")

    return success


def check_env() -> bool:
    env_path = ROOT / ".env"

    if not env_path.exists():
        _warn(".env не найден")
        return True

    env_text = env_path.read_text(encoding="utf-8", errors="ignore")

    required = ["BOT_TOKEN"]
    recommended = ["LLM_API_KEY", "MINI_APP_URL", "WEB_SEARCH_ENABLED"]

    success = True

    for key in required:
        if f"{key}=" not in env_text:
            success = False
            _fail(f".env missing {key}")
        else:
            _ok(f".env has {key}")

    for key in recommended:
        if f"{key}=" not in env_text:
            _warn(f".env missing recommended {key}")
        else:
            _ok(f".env has {key}")

    return success


def check_dirs() -> bool:
    for dirname in ["data", "exports", "logs", "backups"]:
        path = ROOT / dirname
        path.mkdir(parents=True, exist_ok=True)
        _ok(f"dir {dirname}")

    return True


def check_database() -> bool:
    db_path = ROOT / "data" / "manager_ai.sqlite3"

    if not db_path.exists():
        _warn("database file not found yet: data/manager_ai.sqlite3")
        return True

    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        conn.close()
    except Exception as exc:
        _fail(f"database open failed: {exc}")
        return False

    tables = {row[0] for row in rows}
    expected = {"users", "messages", "documents", "queue"}

    for table in expected:
        if table in tables:
            _ok(f"table {table}")
        else:
            _warn(f"table {table} not found")

    return True


def main() -> int:
    print("🧪 Smoke check started\n")

    checks = [
        check_dirs(),
        check_env(),
        check_imports(),
        check_database(),
    ]

    print("\n🧪 Smoke check finished")

    if all(checks):
        _ok("all critical checks passed")
        return 0

    _fail("critical checks failed")
    return 1


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main())
