from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


tags = load_module("tag_contact_sheet_with_toapi.py", "contact_tags")


class ContactSheetTagTests(unittest.TestCase):
    def test_exact_product_rejects_comma_separated_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SKU-A").mkdir()
            with self.assertRaises(ValueError):
                tags.exact_product(root, "SKU-A,SKU-B")

    def test_validate_tags_requires_exact_coverage_and_normalizes_back_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product = Path(tmp) / "SKU-A"
            image = product / "AIGC" / "back.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"test")
            manifest = [{"id": "I001", "path": str(image)}]
            raw = {
                "I001": {
                    "contains_person": True,
                    "subject_type": "model_person",
                    "view": "back",
                    "framing": "full_body",
                    "usable_for_identity": True,
                    "identity_quality": "low",
                    "gender_presentation": "woman",
                    "notes": "rear view",
                }
            }
            result = tags.validate_tags(raw, manifest, product, "gpt-test")
            tag = result["AIGC\\back.jpg"] if "AIGC\\back.jpg" in result else result["AIGC/back.jpg"]
            self.assertFalse(tag["usable_for_identity"])
            self.assertEqual(tag["source"], "gpt-test")
            with self.assertRaises(ValueError):
                tags.validate_tags({}, manifest, product, "gpt-test")

    def test_non_person_cannot_become_identity_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product = Path(tmp) / "SKU-A"
            image = product / "上身" / "flat.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"test")
            manifest = [{"id": "I001", "path": str(image)}]
            raw = {"I001": {
                "contains_person": False, "subject_type": "model_person", "view": "front",
                "framing": "unknown", "usable_for_identity": True, "identity_quality": "unknown",
                "gender_presentation": "woman", "notes": "flat lay",
            }}
            tag = next(iter(tags.validate_tags(raw, manifest, product, "gpt-test").values()))
            self.assertFalse(tag["usable_for_identity"])
            self.assertEqual(tag["gender_presentation"], "unknown")
            self.assertNotEqual(tag["subject_type"], "model_person")


if __name__ == "__main__":
    unittest.main()
