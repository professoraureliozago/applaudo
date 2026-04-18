from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import src.laudo_app.image_store as image_store


def test_save_and_list_captured_images(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(image_store, "CAPTURE_DIR", tmp_path)

    saved = image_store.save_captured_image(b"abc", suffix=".jpg")
    images = image_store.list_captured_images()

    assert saved.exists()
    assert any(p.name == saved.name for p in images)


def test_load_selected_images(tmp_path: Path):
    file_path = tmp_path / "img1.jpg"
    file_path.write_bytes(b"data")

    data = image_store.load_selected_images_with_captions([str(file_path), str(tmp_path / "missing.jpg")])

    assert data == [(b"data", "")]


def test_infer_caption_from_text():
    caption = image_store.infer_caption_from_text("Foi realizada polipectomia em cólon descendente.")
    assert caption == "pós-polipectomia"
