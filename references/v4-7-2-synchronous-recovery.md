# V4.7.2 Synchronous One-SKU Execution And Recovery

Read this file before analysis, generation, resuming an interrupted task, or regenerating a QA-failed module.

## Analysis contract

1. Run `tag_contact_sheet_with_toapi.py` for exactly one direct-child SKU.
2. Pass the analysis model explicitly with `--model`; keep the API key only in the process environment.
3. The script creates one labeled contact sheet for every allowed current-SKU image, including `素材`, `上身1`, `上身`, `AIGC`, and root-level images, while hard-excluding `弃用`, `过程文件`, generated-result, output, backup, and operational directories; it sends one model request. A root-level image may be present in this classification request only so its semantic content can be determined. If it is tagged as a model/person, it becomes downstream-ineligible and must not enter a creative brief, identity lock, reference mapping, influencer plan, or generation upload.
4. Require exact full SKU-relative manifest-path coverage, valid enums and booleans, and `source` equal to the selected model for every tag. Basename matching and filename/directory inference are forbidden.
5. Do not continue when the request times out, JSON is invalid, an ID is missing, a path is stale, or any tag is heuristic. A failed run must not replace a previously valid tag file.
6. Confirm `<ROOT>\_aplus_sync_run_status.json` records a terminal analysis state before processing another SKU.
7. Before submission or recovery, confirm every root-level SKU image tagged `contains_person: true` or `subject_type: model_person` has `usable_for_identity: false` and `source_excluded_reason: sku_root_model_image`. Treat its appearance in any active module mapping as a hard stale-state failure, not as a reason to reuse or re-upload it.

## Reference-contract gate

1. Start `module_reference_images.json` from an empty mapping on every planning pass.
2. Derive each module function from the current template analysis and complete module prompt, then derive required and optional roles.
3. Select only visually tagged current-SKU images and hard-validate every selected role and path.
4. Require model multi-angle modules to contain front and back model roles, model-plus-flat-lay modules to contain front identity model plus flat-lay front and back, and detail modules to contain visually confirmed detail roles with `素材` preferred.
5. Keep pure-background/no-reference module mappings empty. Stop on an unresolved function or missing required role; never preserve old mappings or use shared recursive fallback images.

## Human prompt gate

1. Inspect the readable contact sheet and actual selected uploads for one SKU.
2. Build the reference plan once.
3. Read `manual-visual-direction-standard.md` in full.
4. Completely replace the draft `Layout task:` with a main-agent-authored, SKU-specific design concept.
5. Add exactly one main-agent-authored `Layout execution:` paragraph between `Layout task:` and `Product Accuracy:`.
6. Add exactly one human-authored `Text / Callouts:` block after Product Accuracy content.
7. If Section 3 reuses a Section 2 model reference, include the bespoke fashion action inside the rewritten Section 3 `Layout task:` paragraph.
8. Compare all modules within the SKU and the same section across sibling SKUs; rewrite repeated composition systems.
9. Run `validate_manual_layout_prompts.py`, rerun reference planning, and require every applicable validator to pass.

## Synchronous generation

Use only `run_sync_product_generation.py`. Pass exactly one `--product`; never pass a whole root, comma-separated names, or several products hidden in a shell loop.

The wrapper starts `generate_modules_toapi.py` as one child process, remains attached, writes generation state, enforces the explicit timeout, terminates the complete child tree on timeout or interruption, and returns the child's nonzero exit code.

Set the outer shell/tool timeout at least 60 seconds longer than `--timeout-seconds`. After every invocation, close or reap the cell, inspect process command lines, read final events, verify module count/dimensions/stitched output/root copy, and only then start the next SKU.

## Provider taskId recovery

- `generation_state.json` is authoritative for provider submissions.
- Persist a returned taskId before polling.
- If interruption occurs after a taskId exists, query that taskId without re-uploading or submitting another billed request.
- If no taskId exists, record the attempt as unsubmitted before a new submission.
- Never infer provider state from conversation memory or process name alone.

## QA regeneration

Regenerate only the affected module with `--module "section-XX-name" --overwrite`. Before replacement, preserve the existing final module, raw result, and long-image copies under the timestamped `generation_result_backups` directory with a manifest.

## Completion gate

- Analysis and generation status are terminal for the SKU.
- Semantic tags exactly cover allowed images and no tag uses heuristic provenance.
- Every mapped reference exists under the current SKU, is outside hard-excluded directories, and satisfies its dynamic role contract.
- No stale generator process or yielded execution cell remains.
- Exact submitted prompts, upload logs, provider events, module images, stitched output, and root output copy all agree.
