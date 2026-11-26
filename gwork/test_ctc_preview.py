import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "ctc-billing"
spec = importlib.util.spec_from_file_location("ctc_preview", SKILL / "scripts" / "preview.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class DemoPreviewTests(unittest.TestCase):
    def test_package_matches_github_import(self):
        with ZipFile(ROOT / "ctc-billing.skill") as package:
            sources = {p.relative_to(SKILL).as_posix(): p for p in SKILL.rglob("*")
                       if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith(".")}
            self.assertEqual(set(package.namelist()), set(sources))
            for name, path in sources.items():
                self.assertEqual(package.read(name), path.read_bytes(), name)

    def test_hash_controls_evidence_reuse_and_preserves_duplicates(self):
        contents = b"original training scan"
        key = hashlib.sha256(contents).hexdigest()
        catalog = {"files": {key: {"case": "T", "pages": ["p", "p"]}},
                   "cases": {"T": {"company": "Test", "pages": {"p": "page evidence"}}}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "renamed.pdf"
            source.write_bytes(contents)
            reference = root / "catalog.json"
            reference.write_text(json.dumps(catalog))
            with patch.object(preview, "CATALOG", reference), patch.object(preview, "mock_profile", return_value={}), \
                    patch.object(preview, "ensure_renderer", return_value=False) as renderer:
                matched = preview.preview([source], False)["files"][0]["pages"]
                self.assertEqual([p["reviewed_image"] for p in matched], ["T/p", "T/p"])
                renderer.assert_not_called()
                self.assertIn("pending", preview.preview([source], True)["files"][0])
                source.write_bytes(b"modified training scan")
                self.assertIn("pending", preview.preview([source], False)["files"][0])
