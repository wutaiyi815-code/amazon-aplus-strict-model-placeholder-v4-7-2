from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import build_module_reference_images as builder
import generate_modules_toapi as generator
import tag_contact_sheet_with_toapi as tagger


class V46ReferenceContractTests(unittest.TestCase):
    def make_image(self, product: Path, relative: str) -> Path:
        path = product / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")
        return path

    def set_tags(self, product: Path, entries: dict[str, dict]) -> None:
        builder.MODEL_VIEW_TAG_PRODUCT_DIR = product
        builder.MODEL_VIEW_TAGS = {
            key.casefold(): {"source": "gpt-5.6-sol", **value} for key, value in entries.items()
        }

    def test_candidate_scan_includes_all_business_folders_and_hard_excludes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            product = Path(temp) / "SKU"
            allowed = {
                self.make_image(product, "AIGC/a.jpg"),
                self.make_image(product, "素材/a.jpg"),
                self.make_image(product, "上身1/a.jpg"),
                self.make_image(product, "root.jpg"),
            }
            for relative in ("弃用/a.jpg", "过程文件/a.jpg", "生成结果/a.jpg", "备份/a.jpg", "backup/a.jpg"):
                self.make_image(product, relative)
            self.assertEqual(set(tagger.candidates(product)), allowed)

    def test_exact_relative_path_prevents_basename_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            product = Path(temp) / "SKU"
            model = self.make_image(product, "AIGC/1.jpg")
            detail = self.make_image(product, "素材/1.jpg")
            self.set_tags(product, {
                "aigc/1.jpg": {"subject_type": "model_person", "contains_person": True, "view": "front"},
                "素材/1.jpg": {"subject_type": "product_detail", "contains_person": False, "view": "detail", "detail_types": ["fabric"]},
            })
            self.assertEqual(builder.image_role(model), "model_front")
            self.assertEqual(builder.image_role(detail), "fabric_closeup")

    def test_dynamic_module_detection_ignores_section_number(self) -> None:
        text = "展示模特正侧背多角度版型"
        self.assertEqual(builder.detect_module_role(text, 1)[0], "model_multi_angle")
        self.assertEqual(builder.detect_module_role(text, 4)[0], "model_multi_angle")
        self.assertEqual(builder.detect_module_role("模特加平铺正背面", 2)[0], "model_flatlay")

    def test_multi_angle_requires_front_and_back_side_is_optional(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            product = Path(temp) / "SKU"
            front = self.make_image(product, "AIGC/front.jpg")
            back = self.make_image(product, "AIGC/back.jpg")
            self.set_tags(product, {
                "aigc/front.jpg": {"subject_type": "model_person", "contains_person": True, "view": "front"},
                "aigc/back.jpg": {"subject_type": "model_person", "contains_person": True, "view": "back"},
            })
            sources = {"model_front": [front], "model_back": [back], "model_side": []}
            refs, contract = builder.select_dynamic_contract_refs(product, "model_multi_angle", "模特正侧背", sources, front, 6)
            self.assertEqual(set(refs), {front.resolve(), back.resolve()})
            self.assertEqual(contract["contract_validation"], "passed")

    def test_model_flatlay_missing_back_hard_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            product = Path(temp) / "SKU"
            front = self.make_image(product, "AIGC/front.jpg")
            flat = self.make_image(product, "上身1/front.jpg")
            self.set_tags(product, {
                "aigc/front.jpg": {"subject_type": "model_person", "contains_person": True, "view": "front"},
                "上身1/front.jpg": {"subject_type": "product_flatlay", "contains_person": False, "view": "front"},
            })
            sources = {"model_front": [front], "product_front": [flat], "product_back": []}
            with self.assertRaisesRegex(RuntimeError, "product_back"):
                builder.select_dynamic_contract_refs(product, "model_flatlay", "模特加平铺正背面", sources, front, 6)

    def test_detail_contract_prefers_semantic_material_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            product = Path(temp) / "SKU"
            material = self.make_image(product, "素材/detail.jpg")
            other = self.make_image(product, "上身1/detail.jpg")
            self.set_tags(product, {
                "素材/detail.jpg": {"subject_type": "product_detail", "contains_person": False, "view": "detail", "detail_types": ["fabric"]},
                "上身1/detail.jpg": {"subject_type": "product_detail", "contains_person": False, "view": "detail", "detail_types": ["cuff"]},
            })
            sources = {"fabric_closeup": [material], "construction_detail": [other], "graphic_detail": [], "product_detail": []}
            refs, _ = builder.select_dynamic_contract_refs(product, "construction_detail", "面料工艺细节特写", sources, None, 6)
            self.assertEqual(refs[0], material.resolve())

    def test_generator_rejects_external_and_excluded_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            product = root / "SKU"
            valid = self.make_image(product, "素材/detail.jpg")
            self.assertEqual(generator.validate_current_sku_reference(product, valid), valid.resolve())
            with self.assertRaisesRegex(RuntimeError, "outside current SKU"):
                generator.validate_current_sku_reference(product, self.make_image(root / "OTHER", "x.jpg"))
            with self.assertRaisesRegex(RuntimeError, "hard-excluded"):
                generator.validate_current_sku_reference(product, self.make_image(product, "弃用/x.jpg"))


if __name__ == "__main__":
    unittest.main()
