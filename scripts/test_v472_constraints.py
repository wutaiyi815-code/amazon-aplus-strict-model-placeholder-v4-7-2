from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import build_module_reference_images as reference_builder
import generate_creative_briefs_gemini as brief_builder
import generate_modules_toapi as generator
import tag_contact_sheet_with_toapi as contact_tagger
from validate_manual_layout_prompts import validate_detail_section_geometry


def semantic_tag(*, person: bool, subject: str, usable: bool = True) -> dict[str, object]:
    return {
        "contains_person": person,
        "subject_type": subject,
        "view": "front",
        "framing": "full_body" if person else "unknown",
        "usable_for_identity": usable,
        "identity_quality": "high" if person else "unknown",
        "gender_presentation": "woman" if person else "unknown",
        "detail_types": [],
        "notes": "",
    }


def layout_prompt(task: str, execution: str) -> str:
    return (
        f"Visual Direction:\nLayout task: {task}\n"
        f"Layout execution: {execution}\n"
        "Product Accuracy: Preserve the physical product.\n"
        "Text / Callouts: Keep details factual.\n"
    )


class RootModelPolicyTests(unittest.TestCase):
    def test_contact_sheet_tags_mark_only_root_model_as_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            product = Path(temp) / "SKU"
            (product / "AIGC").mkdir(parents=True)
            root_model = product / "root-model.jpg"
            nested_model = product / "AIGC" / "front.jpg"
            root_flat = product / "flat.jpg"
            manifest = [
                {"id": "IMG_001", "path": str(root_model)},
                {"id": "IMG_002", "path": str(nested_model)},
                {"id": "IMG_003", "path": str(root_flat)},
            ]
            raw = {
                "IMG_001": semantic_tag(person=True, subject="model_person"),
                "IMG_002": semantic_tag(person=True, subject="model_person"),
                "IMG_003": semantic_tag(person=False, subject="product_flatlay"),
            }
            tags = contact_tagger.validate_tags(raw, manifest, product, "gpt-5.6-sol")
            self.assertFalse(tags["root-model.jpg"]["usable_for_identity"])
            self.assertEqual(tags["root-model.jpg"]["source_excluded_reason"], "sku_root_model_image")
            self.assertTrue(tags[str(Path("AIGC") / "front.jpg")]["usable_for_identity"])
            self.assertEqual(tags["flat.jpg"]["source_excluded_reason"], "")

    def test_brief_and_reference_helpers_reject_root_model_only(self) -> None:
        root_model = semantic_tag(person=True, subject="model_person")
        nested_model = semantic_tag(person=True, subject="model_person")
        self.assertTrue(brief_builder.is_sku_root_model_tag("root.jpg", root_model))
        self.assertFalse(brief_builder.is_sku_root_model_tag("AIGC/front.jpg", nested_model))

    def test_reference_builder_and_upload_gate_reject_stale_root_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            product = Path(temp) / "SKU"
            work = product / "_aplus_creative_work"
            nested = product / "AIGC"
            work.mkdir(parents=True)
            nested.mkdir()
            root_model = product / "root.jpg"
            nested_model = nested / "front.jpg"
            root_model.write_bytes(b"root")
            nested_model.write_bytes(b"nested")
            tags = {
                "root.jpg": {
                    **semantic_tag(person=True, subject="model_person", usable=False),
                    "source": "gpt-5.6-sol",
                    "source_excluded_reason": "sku_root_model_image",
                },
                "AIGC/front.jpg": {
                    **semantic_tag(person=True, subject="model_person", usable=True),
                    "source": "gpt-5.6-sol",
                    "source_excluded_reason": "",
                },
            }
            (work / "aigc_model_view_tags.json").write_text(
                json.dumps(tags, ensure_ascii=False), encoding="utf-8"
            )
            reference_builder.MODEL_VIEW_TAG_PRODUCT_DIR = product
            reference_builder.MODEL_VIEW_TAGS = reference_builder.load_model_view_tags(product)
            self.assertTrue(reference_builder.is_sku_root_model_image(root_model))
            self.assertFalse(reference_builder.is_model_identity_image(root_model))
            self.assertTrue(reference_builder.is_model_identity_image(nested_model))
            self.assertTrue(generator.is_forbidden_sku_root_model_reference(root_model, product))
            with self.assertRaisesRegex(RuntimeError, "Root-level SKU model/person"):
                generator.validate_current_sku_reference(product, root_model)
            self.assertEqual(generator.validate_current_sku_reference(product, nested_model), nested_model.resolve())


class DetailGeometryTests(unittest.TestCase):
    def test_rejects_user_examples_only_for_detail_role(self) -> None:
        samples = [
            (
                "Build a people-free construction panorama and fan out smaller curved crops for stitching and closure evidence.",
                "Use crown-panel arcs as nested frames and connect the windows around the main macro while keeping copy clear.",
            ),
            (
                "Build a product-detail proof with windows that follow the fold rather than a regular grid.",
                "Keep the dominant crop left and let every supporting mask trace the fleece crease before reaching the callouts.",
            ),
            (
                "Make the soft fleece surface a dominant diagonal field rising from lower-left to upper-right.",
                "Overlap a large curved hood crop into its upper edge, then place smaller evidence panels beneath it.",
            ),
            (
                "Use irregular crescent windows to isolate the embroidery, zipper, and seam details.",
                "Arrange each organic-shaped mask around the main product crop and preserve the factual callout zone.",
            ),
        ]
        for index, (task, execution) in enumerate(samples, 1):
            path = Path(f"section-{index:02d}.txt")
            text = layout_prompt(task, execution)
            self.assertTrue(validate_detail_section_geometry(path, text, "construction_detail"))
            self.assertEqual(validate_detail_section_geometry(path, text, "hero_model"), [])

    def test_physical_curved_brim_is_allowed_with_rectangular_geometry(self) -> None:
        text = layout_prompt(
            "Use a straight-edged product proof that keeps the curved brim, crown stitching, and rear snap physically accurate.",
            "Place one dominant rectangular macro at left and three smaller orthogonal panels at right; keep every window edge straight and the curved brim unobstructed.",
        )
        self.assertEqual(
            validate_detail_section_geometry(Path("section-04.txt"), text, "construction_detail"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
