from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_DB_BACKUP_DIR = Path("data/backups/database")
DEFAULT_TEMPLATE_BACKUP_DIR = Path("data/backups/templates")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def sqlite_integrity_check(db_path: Path) -> tuple[bool, str]:
    if not db_path.exists():
        return True, "Banco ainda nao existe."

    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as exc:
        return False, str(exc)

    message = str(result[0]) if result else "Sem resposta do integrity_check."
    return message.lower() == "ok", message


def backup_sqlite_database(
    db_path: Path,
    backup_dir: Path = DEFAULT_DB_BACKUP_DIR,
    label: str = "auto",
    keep_last: int = 200,
) -> Path | None:
    if not db_path.exists() or db_path.stat().st_size == 0:
        return None

    ok, message = sqlite_integrity_check(db_path)
    if not ok:
        raise RuntimeError(f"Banco de dados com integridade invalida: {message}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = _unique_path(backup_dir / f"{db_path.stem}_{label}_{_timestamp()}{db_path.suffix}")

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as source:
        with sqlite3.connect(backup_path) as destination:
            source.backup(destination)

    ok, message = sqlite_integrity_check(backup_path)
    if not ok:
        backup_path.unlink(missing_ok=True)
        raise RuntimeError(f"Backup do banco falhou na verificacao de integridade: {message}")

    _prune_old_backups(backup_dir, f"{db_path.stem}_*.db", keep_last)
    return backup_path


def backup_json_file(
    file_path: Path,
    backup_dir: Path = DEFAULT_TEMPLATE_BACKUP_DIR,
    label: str = "auto",
    keep_last: int = 300,
) -> Path | None:
    if not file_path.exists() or file_path.stat().st_size == 0:
        return None

    raw = file_path.read_text(encoding="utf-8")
    json.loads(raw)

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = _unique_path(backup_dir / f"{file_path.stem}_{label}_{_timestamp()}{file_path.suffix}")
    shutil.copy2(file_path, backup_path)

    json.loads(backup_path.read_text(encoding="utf-8"))
    _prune_old_backups(backup_dir, f"{file_path.stem}_*.json", keep_last)
    return backup_path


def write_json_safely(file_path: Path, data: dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _unique_path(file_path.with_suffix(file_path.suffix + ".tmp"))
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(temp_path.read_text(encoding="utf-8"))
    temp_path.replace(file_path)


def _prune_old_backups(backup_dir: Path, pattern: str, keep_last: int) -> None:
    if keep_last <= 0:
        return

    backups = sorted(
        (path for path in backup_dir.glob(pattern) if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[keep_last:]:
        old_backup.unlink(missing_ok=True)
