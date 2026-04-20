import json
import sqlite3

from src.laudo_app.backups import backup_json_file, backup_sqlite_database, sqlite_integrity_check, write_json_safely


def test_sqlite_backup_is_readable_and_integrity_checked(tmp_path):
    db_path = tmp_path / "laudo_app.db"
    backup_dir = tmp_path / "backups"

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE patients(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO patients(name) VALUES ('Paciente Teste')")

    backup_path = backup_sqlite_database(db_path, backup_dir=backup_dir, label="test")

    assert backup_path is not None
    ok, message = sqlite_integrity_check(backup_path)
    assert ok, message

    with sqlite3.connect(backup_path) as conn:
        row = conn.execute("SELECT name FROM patients WHERE id = 1").fetchone()

    assert row[0] == "Paciente Teste"


def test_json_backup_and_safe_write_keep_valid_json(tmp_path):
    template_path = tmp_path / "colonoscopia_templates.json"
    backup_dir = tmp_path / "template_backups"
    original = {"sections": [{"id": "reto", "models": []}]}
    updated = {"sections": [{"id": "ceco", "models": []}]}

    write_json_safely(template_path, original)
    backup_path = backup_json_file(template_path, backup_dir=backup_dir, label="before")
    write_json_safely(template_path, updated)

    assert json.loads(backup_path.read_text(encoding="utf-8")) == original
    assert json.loads(template_path.read_text(encoding="utf-8")) == updated
