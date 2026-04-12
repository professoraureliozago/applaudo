from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.laudo_app import database


def test_patient_uniqueness_and_exam_link(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.ensure_db()

    p1, created1 = database.create_or_get_patient(
        name="Maria Silva",
        sexo="Feminino",
        birth_date_iso="1980-01-02",
    )
    p2, created2 = database.create_or_get_patient(
        name="  maria   silva ",
        sexo="Feminino",
        birth_date_iso="1980-01-02",
    )

    assert created1 is True
    assert created2 is False
    assert p1.id == p2.id

    exam_a = database.create_exam(p1.id, "Dr(a). X", "2026-03-20", "10:00", convenio="Particular")
    exam_b = database.create_exam(p1.id, "Dr(a). Y", "2026-03-21", "11:00", convenio="Unimed")
    exams = database.list_exams(patient_id=p1.id)

    assert exam_a.id != exam_b.id
    assert len(exams) == 2
