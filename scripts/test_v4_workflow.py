#!/usr/bin/env python
"""Regression tests for V4 manual layout, prompt review, backup, and resume state."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from PIL import Image
from openpyxl import Workbook

import generate_modules_toapi as generator
import generation_state as genstate
from build_api_prompt_review import build_review
from generation_state import load_state, module_state, update_module_state
from validate_manual_layout_prompts import validate


class FakeResponse:
    def __init__(self, body: dict[str, Any] | None = None, content: bytes = b"") -> None:
        self._body = body or {}
        self.content = content
        self.status_code = 200

    def json(self) -> dict[str, Any]:
        return self._body

    def raise_for_status(self) -> None:
        return None


def png_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (210, 90), "navy").save(stream, format="PNG")
    return stream.getvalue()


def make_product(base: Path, marketplace: str = "US") -> tuple[Path, Path]:
    product = base / "SKU-TEST"
    product.mkdir()
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["field", "value"])
    sheet.append(["marketplace", marketplace])
    workbook.save(product / "1-产品属性表.xlsx")
    workbook.close()
    prompt_dir = product / "_aplus_creative_work" / "module_prompts"
    prompt_dir.mkdir(parents=True)
    prompt = prompt_dir / "section-01-brand-banner.txt"
    prompt_text = (
        "Visual Direction:\nLayout task: Build an asymmetric hero composition with the full-height model as the primary anchor and a smaller construction-detail proof as supporting evidence. Keep the garment silhouette, plaid hood lining, heart embroidery, zipper path, and cocoa trim clearly readable while creating a distinct editorial opening story.\n\n"
        "Headline:\nTest Headline\n\n"
        "Layout execution: Place the dominant full-height model slightly right of center at the largest scale, with a smaller rectangular construction crop behind the lower-left silhouette as secondary evidence. Build depth through one cocoa trim plane, a restrained plaid overlap, and a soft shadow layer, then connect those planes with the real zipper line so the eye travels from the headline zone at upper left through the model and into the detail proof. Keep headline, copy, and short callouts inside named quiet areas on the left without crossing the face, embroidery, zipper, hood edge, or garment outline. Preserve the complete silhouette, construction, trim color, and product graphics unobstructed, and replace any unrelated source signage with unbranded texture.\n\n"
        "Product Accuracy:\nKeep the exact supplied garment color, construction, and trim.\n\n"
        "Text / Callouts:\nPlaid hood lining | Heart embroidery | Full-zip construction\n\n"
        "Negative Prompt:\nNo malformed product details.\n"
    )
    prompt.write_text(prompt_text, encoding="utf-8-sig")
    (product / "_aplus_creative_work" / "aplus_full_prompt.txt").write_text(prompt_text, encoding="utf-8-sig")
    (product / "_aplus_creative_work" / "module_reference_images.json").write_text(
        '{"section-01-brand-banner.txt": ["AIGC/front.png"]}',
        encoding="utf-8",
    )
    return product, prompt


class ManualLayoutAndReviewTests(unittest.TestCase):
    def test_manual_layout_validator_requires_exactly_one_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product, prompt = make_product(Path(tmp))
            self.assertEqual(validate(product), [])
            prompt.write_text("Visual Direction:\nNo manual layout.\n", encoding="utf-8-sig")
            self.assertTrue(validate(product))

    def test_layout_language_follows_german_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product, prompt = make_product(Path(tmp), marketplace="DE")
            self.assertTrue(any("must be German" in error for error in validate(product)))
            german_text = (
                "Visual Direction:\nLayout task: Erstelle eine asymmetrische Hero-Komposition mit dem Ganzkörpermodel als primärem Anker und einem kleineren Konstruktionsbeleg als unterstützender Ebene. Halte Silhouette, Karofutter der Kapuze, Herzstickerei, Reißverschluss und kakaofarbene Besätze klar lesbar und entwickle daraus eine eigenständige redaktionelle Eröffnung.\n\n"
                "Headline:\nTest\n\n"
                "Layout execution: Platziere das dominante Ganzkörpermodel leicht rechts von der Mitte und in größtem Maßstab; ordne einen kleineren rechteckigen Konstruktionsausschnitt hinter der unteren linken Silhouette als sekundären Beleg an. Erzeuge Tiefe mit einer kakaofarbenen Fläche, einer zurückhaltenden Karo-Überlappung und einer weichen Schattenebene, und verbinde diese Zonen über die echte Reißverschlusslinie, sodass der Blick von der Überschrift oben links über das Model zum Detailbeleg geführt wird. Halte Überschrift, Text und kurze Callouts in benannten ruhigen Bereichen links, ohne Gesicht, Stickerei, Reißverschluss, Kapuzenkante oder Kleidungsumriss zu überdecken. Bewahre Silhouette, Konstruktion, Besatzfarbe und Produktgrafik unverdeckt und ersetze fremde Beschilderung durch markenfreie Textur.\n\n"
                "Product Accuracy:\nBewahre Farbe, Konstruktion und Besätze des Produkts exakt.\n\n"
                "Text / Callouts:\nKarofutter | Herzstickerei | Durchgehender Reißverschluss\n\n"
                "Negative Prompt:\nKeine fehlerhaften Produktdetails.\n"
            )
            prompt.write_text(german_text, encoding="utf-8-sig")
            (product / "_aplus_creative_work" / "aplus_full_prompt.txt").write_text(german_text, encoding="utf-8-sig")
            self.assertEqual(validate(product), [])

    def test_layout_language_follows_english_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product, prompt = make_product(Path(tmp), marketplace="US")
            prompt.write_text(
                "Visual Direction:\nLayout task: Build a hero composition.\n\n"
                "Headline:\nTest\n\n"
                "Layout execution: Platziere das Ganzkörpermodel leicht rechts von der Mitte "
                "und halte den linken Bereich für die Überschrift frei. Verwende gestaffelte "
                "Flächen hinter der Figur, damit die Silhouette und die Produktdetails klar bleiben.\n\n"
                "Product Accuracy:\nKeep the exact product.\n\n"
                "Text / Callouts:\nPlaid lining | Heart embroidery\n\n"
                "Negative Prompt:\nNo malformed product details.\n",
                encoding="utf-8-sig",
            )
            self.assertTrue(any("must be English" in error for error in validate(product)))

    def test_layout_must_sit_between_layout_task_and_product_accuracy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product, prompt = make_product(Path(tmp))
            prompt.write_text(
                "Visual Direction:\nLayout task: Build a hero composition.\n\n"
                "Product Accuracy:\nExact product.\n\n"
                "Layout execution: Place the model right and build layered trim planes.\n\n"
                "Text / Callouts:\nPlaid lining | Heart embroidery\n\n"
                "Negative Prompt:\nNo malformed details.\n",
                encoding="utf-8-sig",
            )
            errors = validate(product)
            self.assertTrue(any("between Layout task and Product Accuracy" in error for error in errors))

    def test_validator_rejects_over_minimal_prompt_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product, prompt = make_product(Path(tmp))
            prompt.write_text(
                "Visual Direction:\nLayout task: Use a restrained commercial page feel with generous white space.\n\n"
                "Main color:\nCreamy ivory garment on a warm-white body.\n\n"
                "Background:\nPale white wall with restrained shadows and generous negative space.\n\n"
                "Layout execution: Add a cocoa trim plane and plaid overlap around the product.\n\n"
                "Product Accuracy:\nExact product.\n\n"
                "Text / Callouts:\nPlaid lining | Heart embroidery\n\n"
                "Negative Prompt:\nNo malformed details.\n",
                encoding="utf-8-sig",
            )
            self.assertTrue(any("over-stacks" in error for error in validate(product)))

    def test_validator_rejects_negative_empty_layout_correction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product, prompt = make_product(Path(tmp))
            text = prompt.read_text(encoding="utf-8-sig")
            text = text.replace(
                "and replace any unrelated source signage with unbranded texture.",
                "rather than leaving the banner visually empty, and replace any unrelated source signage with unbranded texture.",
            )
            prompt.write_text(text, encoding="utf-8-sig")
            self.assertTrue(any("negative correction" in error for error in validate(product)))

    def test_api_normalizer_places_manual_fields_in_semantic_order(self) -> None:
        prompt = (
            "Visual Direction:\nLayout task: Build a hero composition around the product.\n\n"
            "Text / Callouts:\nPlaid lining | Heart embroidery\n\n"
            "Product Accuracy:\nKeep the exact product.\n\n"
            "Layout execution: Build cocoa and plaid layers around the product.\n\n"
            "Negative Prompt:\nNo malformed details."
        )
        normalized = generator.normalize_manual_prompt_structure(prompt)
        self.assertLess(normalized.index("Layout task:"), normalized.index("Layout execution:"))
        self.assertLess(normalized.index("Layout execution:"), normalized.index("Product Accuracy:"))
        self.assertLess(normalized.index("Product Accuracy:"), normalized.index("Text / Callouts:"))
        self.assertLess(normalized.index("Text / Callouts:"), normalized.index("Negative Prompt:"))

    def test_prompt_review_deduplicates_exact_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product, _ = make_product(Path(tmp))
            submitted = product / "_aplus_creative_work" / "api_submitted_prompts"
            submitted.mkdir()
            shared = "Shared Product Accuracy:\nKeep the exact product."
            (submitted / "section-01-a.txt").write_text(
                f"{shared}\n\nUnique one.",
                encoding="utf-8-sig",
            )
            (submitted / "section-02-b.txt").write_text(
                f"{shared}\n\nUnique two.",
                encoding="utf-8-sig",
            )
            review = build_review(product)
            self.assertIsNotNone(review)
            text = review.read_text(encoding="utf-8-sig")
            self.assertEqual(text.count(shared), 1)
            self.assertIn("section-01-a.txt, section-02-b.txt", text)
            self.assertIn("Unique one.", text)
            self.assertIn("Unique two.", text)


class BackupTests(unittest.TestCase):
    def test_overwrite_backup_preserves_existing_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product, prompt = make_product(Path(tmp))
            split = product / "_aplus_creative_work" / "generated_split"
            split.mkdir()
            final = split / "section-01-brand-banner-1464x600.png"
            raw = split / "section-01-brand-banner-raw.png"
            final.write_bytes(b"old-final")
            raw.write_bytes(b"old-raw")
            backup = generator.backup_existing_module_outputs(product, prompt, (1464, 600))
            self.assertIsNotNone(backup)
            self.assertFalse(final.exists())
            self.assertFalse(raw.exists())
            backed_up = list(backup.rglob("*.png"))
            self.assertEqual(len(backed_up), 2)
            self.assertTrue((backup / "backup_manifest.txt").exists())


class StateWriteTests(unittest.TestCase):
    def test_atomic_write_retries_transient_network_access_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generation_state.json"
            real_replace = os.replace
            attempts = 0

            def flaky_replace(source: Any, target: Any) -> None:
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise PermissionError(13, "transient SMB access conflict")
                real_replace(source, target)

            with mock.patch.object(genstate.os, "replace", side_effect=flaky_replace):
                genstate._atomic_write(path, {"status": "completed"})

            self.assertEqual(attempts, 3)
            self.assertEqual(path.read_text(encoding="utf-8"), '{\n  "status": "completed"\n}')


class ResumeStateTests(unittest.TestCase):
    def test_existing_task_id_resumes_query_only_without_submission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product, prompt = make_product(Path(tmp))
            update_module_state(
                product,
                prompt.name,
                status="submitted",
                provider="gpt-rh",
                provider_task_id="TASK-EXISTING",
            )

            class FakeRequests:
                def __init__(self) -> None:
                    self.posts: list[str] = []

                def post(self, url: str, **kwargs: Any) -> FakeResponse:
                    self.posts.append(url)
                    self.assert_query(url)
                    return FakeResponse(
                        {
                            "status": "SUCCESS",
                            "results": [{"url": "https://result.local/image.png"}],
                        }
                    )

                @staticmethod
                def assert_query(url: str) -> None:
                    if url != generator.RH_QUERY_URL:
                        raise AssertionError(f"Unexpected submission during query-only resume: {url}")

                @staticmethod
                def get(url: str, **kwargs: Any) -> FakeResponse:
                    if url != "https://result.local/image.png":
                        raise AssertionError(url)
                    return FakeResponse(content=png_bytes())

            requests = FakeRequests()
            ok = generator.generate_one_module(
                requests,
                "Bearer test",
                generator.PROVIDER_RH,
                prompt,
                product,
                [],
                "21:9",
                "2K",
                "gpt-image-2",
                "high",
                (1464, 600),
                30,
                10,
                False,
                [],
                "",
                False,
            )
            self.assertTrue(ok)
            self.assertEqual(requests.posts, [generator.RH_QUERY_URL])
            self.assertEqual(module_state(product, prompt.name)["status"], "completed")

    def test_task_id_is_persisted_before_first_poll(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            product, prompt = make_product(Path(tmp))

            class FakeRequests:
                def __init__(self) -> None:
                    self.submit_count = 0

                def post(self, url: str, **kwargs: Any) -> FakeResponse:
                    if url in {generator.RH_GENERATE_URL, generator.RH_TEXT_TO_IMAGE_URL}:
                        self.submit_count += 1
                        return FakeResponse({"taskId": "TASK-NEW", "status": "QUEUED"})
                    if url == generator.RH_QUERY_URL:
                        saved = load_state(product)
                        saved_task = (
                            saved.get("modules", {})
                            .get(prompt.name, {})
                            .get("provider_task_id")
                        )
                        if saved_task != "TASK-NEW":
                            raise AssertionError("taskId was not persisted before polling")
                        return FakeResponse(
                            {
                                "status": "SUCCESS",
                                "results": [{"url": "https://result.local/new.png"}],
                            }
                        )
                    raise AssertionError(url)

                @staticmethod
                def get(url: str, **kwargs: Any) -> FakeResponse:
                    if url != "https://result.local/new.png":
                        raise AssertionError(url)
                    return FakeResponse(content=png_bytes())

            requests = FakeRequests()
            ok = generator.generate_one_module(
                requests,
                "Bearer test",
                generator.PROVIDER_RH,
                prompt,
                product,
                [],
                "21:9",
                "2K",
                "gpt-image-2",
                "high",
                (1464, 600),
                30,
                10,
                False,
                [],
                "",
                False,
            )
            self.assertTrue(ok)
            self.assertEqual(requests.submit_count, 1)
            self.assertEqual(module_state(product, prompt.name)["provider_task_id"], "TASK-NEW")


if __name__ == "__main__":
    unittest.main(verbosity=2)
