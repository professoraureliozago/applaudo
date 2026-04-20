import json

import app


def test_templates_are_migrated_to_user_data_folder(tmp_path, monkeypatch):
    user_templates = tmp_path / "data" / "user_templates" / "colonoscopia_templates.json"
    legacy_templates = tmp_path / "templates" / "colonoscopia_templates.json"
    backup_template = tmp_path / "data" / "backups" / "templates" / "colonoscopia_templates.backup.json"
    legacy_backup = tmp_path / "templates" / "colonoscopia_templates.backup.json"
    default_templates = tmp_path / "templates" / "colonoscopia_templates.default.json"

    monkeypatch.setattr(app, "TEMPLATES_PATH", user_templates)
    monkeypatch.setattr(app, "TEMPLATES_LEGACY_PATH", legacy_templates)
    monkeypatch.setattr(app, "TEMPLATES_BACKUP_PATH", backup_template)
    monkeypatch.setattr(app, "TEMPLATES_LEGACY_BACKUP_PATH", legacy_backup)
    monkeypatch.setattr(app, "TEMPLATES_DEFAULT_PATH", default_templates)

    original = {"sections": [{"id": "reto", "models": []}]}
    updated = {"sections": [{"id": "ceco", "models": []}]}

    legacy_templates.parent.mkdir(parents=True)
    legacy_templates.write_text(json.dumps(original), encoding="utf-8")

    assert app.load_templates() == original
    assert json.loads(user_templates.read_text(encoding="utf-8")) == original

    app.save_templates(updated)

    assert json.loads(user_templates.read_text(encoding="utf-8")) == updated
    assert json.loads(backup_template.read_text(encoding="utf-8")) == updated
    assert json.loads(legacy_templates.read_text(encoding="utf-8")) == original
