#!/usr/bin/env python
"""Regression tests for Excel completeness, section ownership, and manual baselines."""

from __future__ import annotations

import importlib
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
INFLUENCER_DIR = SCRIPT_DIR.parent / "influencer_scripts"
if str(INFLUENCER_DIR) not in sys.path:
    sys.path.insert(0, str(INFLUENCER_DIR))

builder = importlib.import_module("build_creative_module_prompts")
briefs = importlib.import_module("generate_creative_briefs_gemini")
prepare = importlib.import_module("prepare_aplus_batch")
reader = importlib.import_module("excel_reader")
generator = importlib.import_module("generate_modules_toapi")
reference_builder = importlib.import_module("build_module_reference_images")
manual_validator = importlib.import_module("validate_manual_layout_prompts")
selfie_prepare = importlib.import_module("prepare_selfie_batch")
selfie_builder = importlib.import_module("build_selfie_prompts")


def make_stale_dimension_workbook(path: Path) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["field", "value"])
    sheet.append(["marketplace", "DE"])
    sheet.append(["Section 1 Headline", "EIGENER LOOK"])
    sheet.append(["Section 2 Copy", "Weicher Griff und klare Linien für jeden Tag."])
    workbook.save(path)
    workbook.close()

    rewritten = path.with_suffix(".rewritten.xlsx")
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(rewritten, "w") as target:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                text = payload.decode("utf-8")
                text = re.sub(r'<dimension ref="[^"]+"\s*/>', '<dimension ref="A1"/>', text, count=1)
                payload = text.encode("utf-8")
            target.writestr(item, payload)
    rewritten.replace(path)


def baseline(main: str, supporting: str, background: str, texture: str) -> str:
    return f"""## Suggested Visual Baseline
Main color: {main}
Supporting colors: {supporting}
Background: {background}
Texture: {texture}
Style balance: {builder.FIXED_STYLE_BALANCE}
"""


class ExcelCompletenessTests(unittest.TestCase):
    def test_stale_dimension_does_not_truncate_either_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            product_dir = Path(temp_dir) / "SKU"
            product_dir.mkdir()
            workbook_path = product_dir / "1-产品属性表.xlsx"
            make_stale_dimension_workbook(workbook_path)

            sheet, rows, _dimension = reader.read_active_worksheet_rows(workbook_path)
            self.assertEqual(sheet, "Sheet")
            self.assertGreaterEqual(len(rows), 4)

            summary = prepare.read_excel_summary(workbook_path)
            self.assertEqual(summary["key_values"]["marketplace"], "DE")
            self.assertEqual(summary["key_values"]["Section 2 Copy"], "Weicher Griff und klare Linien für jeden Tag.")

            overrides = builder.read_excel_section_copy(product_dir)
            self.assertEqual(overrides[1]["Headline"], "EIGENER LOOK")
            self.assertEqual(overrides[2]["Copy"], "Weicher Griff und klare Linien für jeden Tag.")
            self.assertEqual(builder.excel_value_language(product_dir), "German")


class SectionOwnershipTests(unittest.TestCase):
    def test_blank_excel_field_keeps_gemini_field(self) -> None:
        sections = [{"index": 1, "fields": {"Headline": "Gemini headline", "Copy": "Gemini copy"}}]
        builder.apply_excel_copy_overrides(sections, {1: {"Headline": "Excel headline", "Copy": ""}})
        self.assertEqual(sections[0]["fields"]["Headline"], "Excel headline")
        self.assertEqual(sections[0]["fields"]["Copy"], "Gemini copy")

    def test_excel_section_two_copy_in_section_one_is_a_hard_error(self) -> None:
        authoritative = "Soft brushed comfort follows you from street to studio."
        sections = [
            {"index": 1, "fields": {"Headline": "Hero", "Copy": authoritative}},
            {"index": 2, "fields": {"Headline": "Comfort", "Copy": "Gemini draft"}},
        ]
        overrides = {2: {"Copy": authoritative}}
        builder.apply_excel_copy_overrides(sections, overrides)
        with self.assertRaisesRegex(SystemExit, "Section 2 Copy was found in Section 1 Copy"):
            builder.validate_excel_section_ownership(sections, overrides)

    def test_resolved_cross_section_copy_duplicate_is_a_hard_error(self) -> None:
        repeated = "One distinctive product benefit written long enough for duplicate validation."
        sections = [
            {"index": 1, "fields": {"Resolved Headline": "A", "Resolved Copy": repeated}},
            {"index": 2, "fields": {"Resolved Headline": "B", "Resolved Copy": repeated}},
        ]
        with self.assertRaisesRegex(SystemExit, "Cross-section duplicate Copy"):
            builder.validate_cross_section_duplicates(sections)


class ManualBaselineTests(unittest.TestCase):
    def test_exact_manual_baseline_is_preserved(self) -> None:
        text = baseline(
            "mineral blue",
            "weathered navy, pale stone, brushed silver",
            "cool concrete alcove with a narrow daylight cut",
            "dense washed jersey, matte grain, crisp metal accents",
        )
        parsed = builder.extract_manual_visual_baseline(text)
        self.assertEqual(builder.visual_baseline_text(parsed), text.split("\n", 1)[1].strip())

    def test_changed_style_balance_is_rejected(self) -> None:
        text = baseline("black", "grey", "studio", "cotton").replace("70% Amazon", "60% Amazon")
        with self.assertRaisesRegex(SystemExit, "must keep Style balance exactly"):
            builder.extract_manual_visual_baseline(text)

    def test_near_duplicate_sibling_baseline_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "SKU-A"
            second = root / "SKU-B"
            for product in (first, second):
                (product / "_aplus_creative_work").mkdir(parents=True)
            shared = baseline(
                "warm cream",
                "sand, oat, faded brown",
                "sunlit plaster corner with soft window shadow",
                "brushed fleece, dry paper grain, calm warmth",
            )
            (first / "_aplus_creative_work" / "aplus_creative_brief.md").write_text(shared, encoding="utf-8")
            current = builder.extract_manual_visual_baseline(shared)
            with self.assertRaisesRegex(SystemExit, "similar to SKU 'SKU-A'"):
                builder.ensure_manual_visual_baseline_is_unique(second, current)

    def test_gemini_cannot_rewrite_human_baseline(self) -> None:
        manual = {
            "Main color": "storm purple",
            "Supporting colors": "weathered concrete, faded red, steel grey",
            "Background": "sunlit stadium steps behind a wire fence",
            "Texture": "washed cotton, dry masonry, hard summer light",
            "Style balance": builder.FIXED_STYLE_BALANCE,
        }
        draft = """## Product Truth
- Product type: tee

## Suggested Visual Baseline
Main color: generic black
Supporting colors: generic grey
Background: generic studio
Texture: generic fabric
Style balance: wrong

## Target And Language
- marketplace: US
"""
        enforced = briefs.enforce_manual_baseline(draft, manual)
        parsed = builder.extract_manual_visual_baseline(enforced)
        self.assertEqual(parsed, manual)

    def test_gemini_brief_prompt_has_no_copy_missing_layout_workaround(self) -> None:
        source = (SCRIPT_DIR / "generate_creative_briefs_gemini.py").read_text(encoding="utf-8")
        forbidden = ("35%", "fixed text-safe", "mandatory split layout", "reserve a clean text-safe area")
        for phrase in forbidden:
            self.assertNotIn(phrase, source)


class ManualCalloutTests(unittest.TestCase):
    def test_machine_callouts_are_omitted_by_builder(self) -> None:
        self.assertEqual(builder.render_callouts_block("None."), "")
        self.assertEqual(builder.render_callouts_block("N/A"), "")
        self.assertEqual(builder.render_callouts_block(""), "")
        self.assertEqual(builder.render_callouts_block("Ribbed cuffs\nBrushed interior"), "")

    def test_api_submission_preserves_human_callouts(self) -> None:
        prompt = "Headline:\nWarm Layers\n\nText / Callouts:\nRibbed cuffs\nBrushed interior\n\nNegative Prompt:\nrandom text"
        cleaned = generator.strip_text_callouts(prompt)
        self.assertIn("Text / Callouts", cleaned)
        self.assertIn("Ribbed cuffs", cleaned)
        self.assertIn("Headline:\nWarm Layers", cleaned)
        self.assertIn("Negative Prompt:\nrandom text", cleaned)

    def test_manual_fields_are_canonicalized_around_product_accuracy(self) -> None:
        prompt = (
            "Visual Direction:\nLayout task: Build a model-plus-product composition.\n\n"
            "Text / Callouts:\nPlaid lining | Heart embroidery\n\n"
            "Product Accuracy:\nKeep the exact product.\n\n"
            "Layout execution:\nPlace the model left and layer product cards on the right.\n\n"
            "Negative Prompt:\nNo malformed details."
        )
        cleaned = generator.normalize_manual_prompt_structure(prompt)
        self.assertLess(cleaned.index("Layout task:"), cleaned.index("Layout execution:"))
        self.assertLess(cleaned.index("Layout execution:"), cleaned.index("Product Accuracy:"))
        self.assertLess(cleaned.index("Product Accuracy:"), cleaned.index("Text / Callouts:"))
        self.assertLess(cleaned.index("Text / Callouts:"), cleaned.index("Negative Prompt:"))

    def test_separate_section3_action_is_rejected_by_submission_normalizer(self) -> None:
        prompt = (
            "Visual Direction:\nLayout task: Model and product proof.\n\n"
            "Layout execution:\nLayer the composition.\n\nProduct Accuracy:\nExact product.\n\n"
            "Text / Callouts:\nPlaid lining\n\n"
            "Section 3 fashion action:\nTurn the torso.\n\nNegative Prompt:\nNo errors."
        )
        with self.assertRaises(ValueError):
            generator.normalize_manual_prompt_structure(prompt)

    def test_blank_legacy_callout_does_not_swallow_negative_prompt(self) -> None:
        fields = builder.parse_fields("Text/Callouts:\nNegative Prompt: No mismatched colors.")
        self.assertNotIn("Text/Callouts", fields)
        self.assertEqual(fields["Negative Prompt"], "No mismatched colors.")

    def test_api_submission_strips_attached_reference_map(self) -> None:
        prompt = "Negative Prompt:\nrandom text\n\nAttached Reference Image Map:\n- Reference image #1: 素材\\5.jpg"
        cleaned = generator.strip_attached_reference_map(prompt)
        self.assertEqual(cleaned, "Negative Prompt:\nrandom text")

    def test_gemini_brief_schema_does_not_request_callouts(self) -> None:
        source = (SCRIPT_DIR / "generate_creative_briefs_gemini.py").read_text(encoding="utf-8")
        self.assertNotIn("Text/Callouts:\n", source)

    def test_manual_callouts_cannot_duplicate_existing_copy(self) -> None:
        text = (
            "Headline:\nBuilt for Layers\n\nCopy:\nPlaid lining frames the hood.\n\n"
            "Visual Direction:\nLayout task: Build a layered product composition.\n\n"
            "Layout execution:\nPlace the model left and the detail tile right.\n\n"
            "Product Accuracy:\nKeep the plaid hood lining exact.\n\n"
            "Text / Callouts:\nPlaid lining frames the hood.\n\nNegative Prompt:\nNo errors."
        )
        match = manual_validator.CALLOUT_BLOCK_RE.search(text)
        self.assertIsNotNone(match)
        errors = manual_validator.validate_callouts(Path("section-01.txt"), text, match)
        self.assertTrue(any("duplicates existing Copy" in error for error in errors))

    def test_manual_callouts_cannot_invent_an_unsupported_measurement(self) -> None:
        text = (
            "Headline:\nBuilt for Layers\n\nCopy:\nSoft everyday structure.\n\n"
            "Visual Direction:\nLayout task: Build a layered product composition.\n\n"
            "Layout execution:\nPlace the model left and the detail tile right.\n\n"
            "Product Accuracy:\nKeep all visible construction exact.\n\n"
            "Text / Callouts:\n420 gsm heavyweight fabric\n\nNegative Prompt:\nNo errors."
        )
        match = manual_validator.CALLOUT_BLOCK_RE.search(text)
        self.assertIsNotNone(match)
        errors = manual_validator.validate_callouts(Path("section-01.txt"), text, match)
        self.assertTrue(any("unsupported measurement" in error for error in errors))


class ModelReferenceClassificationTests(unittest.TestCase):
    def test_upbody_flatlays_are_not_inferred_as_people(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            product = Path(temp_dir) / "SKU"
            (product / "AIGC").mkdir(parents=True)
            (product / "上身").mkdir()
            identity = product / "AIGC" / "front.png"
            companion = product / "AIGC" / "three-quarter.png"
            flat_front = product / "上身" / "1.jpg"
            flat_back = product / "上身" / "4.jpg"
            for path in (identity, companion, flat_front, flat_back):
                path.write_bytes(b"test")
            reference_builder.MODEL_VIEW_TAG_PRODUCT_DIR = product
            reference_builder.MODEL_VIEW_TAGS = {
                "aigc/front.png": {
                    "view": "front",
                    "framing": "full_body",
                    "usable_for_identity": True,
                    "contains_person": True,
                    "subject_type": "model_person",
                },
                "aigc/three-quarter.png": {
                    "view": "three_quarter",
                    "framing": "full_body",
                    "usable_for_identity": True,
                    "contains_person": True,
                    "subject_type": "model_person",
                },
                "上身/1.jpg": {"view": "front", "contains_person": False, "subject_type": "product_flatlay"},
                "上身/4.jpg": {"view": "back", "contains_person": False, "subject_type": "product_flatlay"},
            }

            buckets = reference_builder.classify_references(product, identity)
            self.assertEqual({path.name for path in buckets["model"]}, {"front.png", "three-quarter.png"})
            self.assertNotIn(flat_front.resolve(), buckets["model"])
            self.assertNotIn(flat_back.resolve(), buckets["model"])
            self.assertEqual(reference_builder.image_role(flat_front, identity), "product_front")
            self.assertEqual(reference_builder.image_role(flat_back, identity), "product_back")

    def test_section_two_forces_brief_anchor_and_front_companion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            product = Path(temp_dir) / "SKU"
            work = product / "_aplus_creative_work"
            (product / "AIGC").mkdir(parents=True)
            work.mkdir()
            identity = product / "AIGC" / "front.png"
            companion = product / "AIGC" / "three-quarter.png"
            back = product / "AIGC" / "back.png"
            for path in (identity, companion, back):
                path.write_bytes(b"test")
            (work / "aplus_creative_brief.md").write_text(
                "## Model Identity Lock\n- model_identity_reference: AIGC\\front.png\n",
                encoding="utf-8",
            )
            reference_builder.MODEL_VIEW_TAG_PRODUCT_DIR = product
            reference_builder.MODEL_VIEW_TAGS = {
                "aigc/front.png": {"view": "front", "usable_for_identity": True, "contains_person": True},
                "aigc/three-quarter.png": {"view": "three_quarter", "usable_for_identity": True, "contains_person": True},
                "aigc/back.png": {"view": "back", "usable_for_identity": False, "contains_person": True},
            }
            anchor = reference_builder.brief_identity_reference(product)
            self.assertEqual(anchor, identity.resolve())
            sources = {"model_identity": [back, companion, identity]}
            selected, diagnostics = reference_builder.enforce_section_two_identity_lock(
                [back], sources, anchor, 6
            )
            self.assertEqual(selected[0], identity.resolve())
            self.assertIn(companion.resolve(), selected)
            self.assertNotIn(back.resolve(), selected)
            self.assertTrue(diagnostics["section2_identity_anchor_forced"])
            self.assertTrue(diagnostics["section2_identity_companion_added"])

    def test_api_logging_does_not_infer_person_from_upbody_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            product = Path(temp_dir) / "SKU"
            flat = product / "上身" / "1.jpg"
            flat.parent.mkdir(parents=True)
            flat.write_bytes(b"test")
            self.assertEqual(generator.reference_role(product, flat, {}), "")
            self.assertFalse(generator.has_model_reference_images(product, [flat], {}))


class Section3HumanFashionActionTests(unittest.TestCase):
    def test_overlap_requires_action_bearing_layout_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt = Path(temp_dir) / "section-03.txt"
            prompt.write_text("Visual Direction:\nModel plus flat lays.\n\nProduct Accuracy:\nExact product.\n", encoding="utf-8")
            valid, reason = reference_builder.validate_section3_human_fashion_action(prompt)
            self.assertFalse(valid)
            self.assertIn("Layout task", reason)

    def test_legacy_safe_library_block_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt = Path(temp_dir) / "section-03.txt"
            prompt.write_text(
                "Section 3 action adjustment:\nA scripted pose.\n\n"
                "Section 3 fashion action:\nTurn the torso toward camera while one hand lifts near the shoulder and the other arm clears the garment front, keeping the gaze past camera and the complete product silhouette visible.\n",
                encoding="utf-8",
            )
            valid, reason = reference_builder.validate_section3_human_fashion_action(prompt)
            self.assertFalse(valid)
            self.assertIn("separate or legacy", reason)

    def test_detailed_human_action_is_validated_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt = Path(temp_dir) / "section-03.txt"
            original = (
                "Visual Direction:\n"
                "Layout task: Build a model-plus-flat-lay composition. Angle the torso toward the product cards while the right hand lightly gathers the jacket collar and the left arm extends downward outside the graphic area; direct the gaze across the layout so the shoulder line creates movement while keeping the zipper and hem visible and clear.\n\n"
                "Product Accuracy:\nExact product.\n"
            )
            prompt.write_text(original, encoding="utf-8")
            valid, action = reference_builder.validate_section3_human_fashion_action(prompt)
            self.assertTrue(valid)
            self.assertIn("right hand", action)
            self.assertEqual(prompt.read_text(encoding="utf-8"), original)


class ModelAuthoritativeGenderTests(unittest.TestCase):
    def test_model_gender_overrides_attribute_table(self) -> None:
        gender, source = selfie_prepare.resolve_target_gender("man", {"target_customer": "Women"})
        self.assertEqual(gender, "men")
        self.assertEqual(source, "model_identity_reference")

    def test_attribute_table_is_fallback_when_model_gender_unknown(self) -> None:
        gender, source = selfie_prepare.resolve_target_gender("unknown", {"target_customer": "Women"})
        self.assertEqual(gender, "women")
        self.assertEqual(source, "attribute_table_fallback")

    def test_prompt_builder_prioritizes_explicit_model_gender(self) -> None:
        plan = {"target_gender": "men", "facts": {"target_customer": "Women", "product_type": "hoodie"}}
        self.assertEqual(selfie_builder.normalized_gender(plan), "men")


if __name__ == "__main__":
    unittest.main(verbosity=2)
