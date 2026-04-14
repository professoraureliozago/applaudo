from __future__ import annotations

import sqlite3
import json
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

DB_PATH = Path("data/laudo_app.db")


@dataclass(slots=True)
class Patient:
    id: int
    name: str
    normalized_name: str
    sexo: str
    birth_date: str
    created_at: str = ""
    convenio: str = ""


@dataclass(slots=True)
class Exam:
    id: int
    patient_id: int
    doctor_name: str
    exam_date: str
    exam_time: str
    convenio: str
    executante: str
    created_at: str
    updated_at: str


def _normalize_name(name: str) -> str:
    lowered = " ".join(name.strip().lower().split())
    no_accents = "".join(ch for ch in unicodedata.normalize("NFD", lowered) if unicodedata.category(ch) != "Mn")
    return no_accents


def ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                sexo TEXT DEFAULT '',
                birth_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(normalized_name, birth_date)
            );

            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                doctor_name TEXT DEFAULT '',
                exam_date TEXT NOT NULL,
                exam_time TEXT NOT NULL,
                convenio TEXT DEFAULT '',
                executante TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS doctor_suggestions (
                name TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS convenio_suggestions (
                name TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS executante_profiles (
                name TEXT PRIMARY KEY,
                footer_text TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS exam_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                caption TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exam_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exam_reports (
                exam_id INTEGER PRIMARY KEY,
                transcript TEXT DEFAULT '',
                sections_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
            );
            """
        )
        cols = {row[1] for row in conn.execute("PRAGMA table_info(exams)").fetchall()}
        if "convenio" not in cols:
            conn.execute("ALTER TABLE exams ADD COLUMN convenio TEXT DEFAULT ''")
        if "executante" not in cols:
            conn.execute("ALTER TABLE exams ADD COLUMN executante TEXT DEFAULT ''")


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def calculate_age(birth_date_iso: str, as_of: date | None = None) -> int:
    today = as_of or date.today()
    born = datetime.strptime(birth_date_iso, "%Y-%m-%d").date()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def find_patient(name: str, birth_date_iso: str) -> Patient | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM patients WHERE normalized_name = ? AND birth_date = ?",
            (_normalize_name(name), birth_date_iso),
        ).fetchone()
    if not row:
        return None
    return Patient(**dict(row))


def search_patients_by_name(name_fragment: str) -> list[Patient]:
    token = f"%{_normalize_name(name_fragment)}%"
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM patients WHERE normalized_name LIKE ? ORDER BY name LIMIT 50",
            (token,),
        ).fetchall()
    return [Patient(**dict(row)) for row in rows]


def create_or_get_patient(name: str, sexo: str, birth_date_iso: str) -> tuple[Patient, bool]:
    normalized_name = _normalize_name(name)
    existing = find_patient(name, birth_date_iso)
    if existing:
        return existing, False

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO patients(name, normalized_name, sexo, birth_date, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name.strip(), normalized_name, sexo.strip(), birth_date_iso, _now_iso()),
        )
        patient_id = cur.lastrowid
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    return Patient(**dict(row)), True


def create_exam(
    patient_id: int,
    doctor_name: str,
    exam_date_iso: str,
    exam_time_hhmm: str,
    convenio: str = "",
    executante: str = "",
) -> Exam:
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO exams(patient_id, doctor_name, exam_date, exam_time, convenio, executante, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (patient_id, doctor_name.strip(), exam_date_iso, exam_time_hhmm, convenio.strip(), executante.strip(), now, now),
        )
        exam_id = cur.lastrowid
        row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    return Exam(**dict(row))


def update_exam(
    exam_id: int,
    doctor_name: str,
    exam_date_iso: str,
    exam_time_hhmm: str,
    convenio: str = "",
    executante: str = "",
) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE exams SET doctor_name=?, exam_date=?, exam_time=?, convenio=?, executante=?, updated_at=? WHERE id=?",
            (doctor_name.strip(), exam_date_iso, exam_time_hhmm, convenio.strip(), executante.strip(), _now_iso(), exam_id),
        )


def list_exams(patient_id: int | None = None) -> list[dict]:
    query = (
        """
        SELECT e.id, e.patient_id, e.doctor_name, e.exam_date, e.exam_time, e.convenio, e.executante, e.created_at,
               p.name AS patient_name, p.birth_date, p.sexo
        FROM exams e
        JOIN patients p ON p.id = e.patient_id
        """
    )
    params: tuple = ()
    if patient_id is not None:
        query += " WHERE e.patient_id = ?"
        params = (patient_id,)
    query += " ORDER BY e.exam_date DESC, e.exam_time DESC"

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_exam(exam_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT e.id, e.patient_id, e.doctor_name, e.exam_date, e.exam_time, e.convenio, e.executante,
                   p.name AS patient_name, p.birth_date, p.sexo
            FROM exams e
            JOIN patients p ON p.id = e.patient_id
            WHERE e.id = ?
            """,
            (exam_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_exam(exam_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))


def add_exam_image(exam_id: int, file_path: str, caption: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO exam_images(exam_id, file_path, caption, created_at) VALUES (?, ?, ?, ?)",
            (exam_id, file_path, caption, _now_iso()),
        )


def list_exam_images(exam_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM exam_images WHERE exam_id = ? ORDER BY id", (exam_id,)).fetchall()
    return [dict(r) for r in rows]


def add_exam_video(exam_id: int, file_path: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO exam_videos(exam_id, file_path, created_at) VALUES (?, ?, ?)",
            (exam_id, file_path, _now_iso()),
        )


def list_doctor_names() -> list[str]:
    with _connect() as conn:
        exam_rows = conn.execute(
            "SELECT DISTINCT doctor_name FROM exams WHERE doctor_name IS NOT NULL AND TRIM(doctor_name) <> '' ORDER BY doctor_name"
        ).fetchall()
        suggested_rows = conn.execute("SELECT name FROM doctor_suggestions ORDER BY name").fetchall()
    names = {r["doctor_name"] for r in exam_rows} | {r["name"] for r in suggested_rows}
    return sorted(n for n in names if n.strip())


def list_convenios() -> list[str]:
    with _connect() as conn:
        exam_rows = conn.execute(
            "SELECT DISTINCT convenio FROM exams WHERE convenio IS NOT NULL AND TRIM(convenio) <> '' ORDER BY convenio"
        ).fetchall()
        suggested_rows = conn.execute("SELECT name FROM convenio_suggestions ORDER BY name").fetchall()
    names = {r["convenio"] for r in exam_rows} | {r["name"] for r in suggested_rows}
    return sorted(n for n in names if n.strip())


def add_doctor_suggestion(name: str) -> None:
    if not name.strip():
        return
    with _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO doctor_suggestions(name) VALUES (?)", (name.strip(),))


def add_convenio_suggestion(name: str) -> None:
    if not name.strip():
        return
    with _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO convenio_suggestions(name) VALUES (?)", (name.strip(),))


def list_executante_names() -> list[str]:
    with _connect() as conn:
        exam_rows = conn.execute(
            "SELECT DISTINCT executante FROM exams WHERE executante IS NOT NULL AND TRIM(executante) <> '' ORDER BY executante"
        ).fetchall()
        profile_rows = conn.execute("SELECT name FROM executante_profiles ORDER BY name").fetchall()
    names = {r["executante"] for r in exam_rows} | {r["name"] for r in profile_rows}
    return sorted(n for n in names if n.strip())


def upsert_executante_profile(name: str, footer_text: str) -> None:
    if not name.strip():
        return
    with _connect() as conn:
        conn.execute(
            "INSERT INTO executante_profiles(name, footer_text) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET footer_text=excluded.footer_text",
            (name.strip(), footer_text.strip()),
        )


def get_executante_footer(name: str) -> str:
    if not name.strip():
        return ""
    with _connect() as conn:
        row = conn.execute("SELECT footer_text FROM executante_profiles WHERE name = ?", (name.strip(),)).fetchone()
    return row["footer_text"] if row else ""


def save_exam_report(exam_id: int, transcript: str, sections: dict[str, str]) -> None:
    now = _now_iso()
    sections_json = json.dumps(sections, ensure_ascii=False)
    with _connect() as conn:
        exists = conn.execute("SELECT 1 FROM exam_reports WHERE exam_id = ?", (exam_id,)).fetchone()
        if exists:
            conn.execute(
                "UPDATE exam_reports SET transcript=?, sections_json=?, updated_at=? WHERE exam_id=?",
                (transcript, sections_json, now, exam_id),
            )
        else:
            conn.execute(
                "INSERT INTO exam_reports(exam_id, transcript, sections_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (exam_id, transcript, sections_json, now, now),
            )


def get_exam_report(exam_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM exam_reports WHERE exam_id = ?", (exam_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    try:
        data["sections"] = json.loads(data.get("sections_json") or "{}")
    except json.JSONDecodeError:
        data["sections"] = {}
    return data
