from __future__ import annotations

import sqlite3
import json
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
    convenio: str
    created_at: str


@dataclass(slots=True)
class Exam:
    id: int
    patient_id: int
    doctor_name: str
    exam_date: str
    exam_time: str
    created_at: str
    updated_at: str


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


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
                convenio TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(normalized_name, birth_date)
            );

            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                doctor_name TEXT DEFAULT '',
                exam_date TEXT NOT NULL,
                exam_time TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
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


def create_or_get_patient(name: str, sexo: str, birth_date_iso: str, convenio: str) -> tuple[Patient, bool]:
    normalized_name = _normalize_name(name)
    existing = find_patient(name, birth_date_iso)
    if existing:
        return existing, False

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO patients(name, normalized_name, sexo, birth_date, convenio, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name.strip(), normalized_name, sexo.strip(), birth_date_iso, convenio.strip(), _now_iso()),
        )
        patient_id = cur.lastrowid
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    return Patient(**dict(row)), True


def create_exam(patient_id: int, doctor_name: str, exam_date_iso: str, exam_time_hhmm: str) -> Exam:
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO exams(patient_id, doctor_name, exam_date, exam_time, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (patient_id, doctor_name.strip(), exam_date_iso, exam_time_hhmm, now, now),
        )
        exam_id = cur.lastrowid
        row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    return Exam(**dict(row))


def update_exam(exam_id: int, doctor_name: str, exam_date_iso: str, exam_time_hhmm: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE exams SET doctor_name=?, exam_date=?, exam_time=?, updated_at=? WHERE id=?",
            (doctor_name.strip(), exam_date_iso, exam_time_hhmm, _now_iso(), exam_id),
        )


def list_exams(patient_id: int | None = None) -> list[dict]:
    query = (
        """
        SELECT e.id, e.patient_id, e.doctor_name, e.exam_date, e.exam_time, e.created_at,
               p.name AS patient_name, p.birth_date, p.sexo, p.convenio
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
            SELECT e.id, e.patient_id, e.doctor_name, e.exam_date, e.exam_time,
                   p.name AS patient_name, p.birth_date, p.sexo, p.convenio
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
