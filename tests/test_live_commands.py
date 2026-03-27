from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.laudo_app.live_commands import apply_live_command


def test_start_command_activates_capture():
    res = apply_live_command("gravar", recording_active=False, current_draft="")
    assert res.recording_active is True
    assert res.updated_draft == ""


def test_stop_command_pauses_capture():
    res = apply_live_command("parar", recording_active=True, current_draft="texto")
    assert res.recording_active is False
    assert res.updated_draft == "texto"


def test_chunk_appends_when_active():
    res = apply_live_command("mucosa normal", recording_active=True, current_draft="reto")
    assert res.recording_active is True
    assert "reto" in res.updated_draft and "mucosa normal" in res.updated_draft


def test_chunk_ignored_when_inactive():
    res = apply_live_command("mucosa normal", recording_active=False, current_draft="")
    assert res.recording_active is False
    assert res.updated_draft == ""
