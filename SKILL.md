---
name: amazon-aplus-strict-model-placeholder-v4-7-2
description: Strict-model Amazon A+ v4.7.2 synchronous per-SKU workflow with semantic image analysis, SKU-root model-image exclusion, dynamic module contracts, detail-section straight-edged layout enforcement, current-SKU-only references, manual visual direction, recovery, stitching, and root output collection.
---

# Amazon A+ Creative Director With Strict Model Lock And Placeholders

## Purpose

This skill is the v4.7.2 strict-model placeholder workflow. It preserves the v4.6 identity, callout, prompt-balance, QA-backup, taskId recovery, one-SKU synchronous execution, exact-path semantic tagging, dynamic module-function contracts, and human visual-direction requirements. It additionally excludes model/person images located directly in the SKU root and enforces straight-edged, non-fold-following composition geometry only for sections whose dynamic function is product detail, fabric, graphic, or construction evidence.

Do not overwrite:

- `amazon-aplus-creative-director-api`
- `amazon-aplus-creative-director-influencer-api`
- `amazon-aplus-creative-director-influencer-api-strict-model`
- `amazon-influencer-selfie-generator`

## Mandatory Rules

1. In every A+ module that contains a model, preserve the model identity from the supplied model reference images. Match visible face shape, skin tone, hair color/style, body type, age range, expression mood, pose attitude, and styling character. Do not let the API invent a different model unless the product folder has no usable model reference.
2. Use product-only flat lays and detail images for garment accuracy only. Do not treat flat lays, LOGO images, or Excel screenshots as model identity references. Never infer that an image contains a person merely because its path includes `上身`; require visual-analysis tags or an explicit human-selected `model_identity_reference`.
3. Before writing `_aplus_creative_work\aplus_creative_brief.md`, choose and record a `Model Identity Lock`. Treat its `model_identity_reference` as the reusable identity anchor for all identity-sensitive modules, including Section 2:
   - `model_identity_reference`: clearest front-facing model image, not LOGO and not product-only flat lay.
   - `model_identity_notes`: concise description of the reference model's visible face, hair, skin tone, body type, and attitude.
   - `model_identity_policy`: all A+ model scenes must use this same person; do not change ethnicity, gender presentation, face, hair, or body type.
4. Derive `target_gender` from the visible gender presentation of the selected `model_identity_reference` whenever a usable supplied model image exists:
   - Visible woman / female-presenting model -> `target_gender: women`.
   - Visible man / male-presenting model -> `target_gender: men`.
   - Ambiguous presentation -> `target_gender: unisex`, while preserving that same person's identity and presentation consistently.
   - Treat spreadsheet `target_customer`, template gender wording, and product-category gender cues as advisory metadata only. They must never override, replace, pause, or conflict-block a usable supplied model identity.
   - Only when no usable model identity exists, or its visible gender presentation remains unknown after visual analysis, may the attribute table provide the fallback `target_gender`; record the fallback source explicitly.
5. Preserve the selected supplied model's visible gender presentation across all model and influencer outputs. Do not silently replace the person to make the output agree with `target_customer`; keep any differing attribute-table value as reference metadata only.
6. Every final A+ module prompt must use the language selected from the product attribute table's `marketplace`: German for `DE`, `AT`, and `CH`; English for `US`, `UK`, `CA`, and `AU`. Strip local Windows paths, Chinese/CJK characters, template notes, and prompt metadata from prompts using these supported marketplace mappings. Visible text must not contain an unintended second language, bilingual labels, or file paths.
7. Each A+ module must receive only the reference images it truly needs. Model/fit modules should receive the model identity references plus a small number of garment accuracy references; detail/fabric modules should receive product flat-lay/detail references; influencer modules should receive generated influencer references. Do not pass all product images to every module unless the user explicitly requests that broad reference strategy.
8. Distinguish influencer background templates from color-block placeholders:
   - If a module instruction says only `不需要生成网红图`, `无需生成网红图`, `并不需要生成网红图`, `用于后续替换为网红图`, `背景图`, or `不需要任何文案`, do not run influencer/selfie generation. Generate a style-matched, text-free empty background module for later influencer replacement. Do not generate color blocks unless the template explicitly asks for them.
   - Generate equal-size color-block placeholders only when the instruction explicitly says `占位符`, `等大色块`, `色块`, `placeholder`, or `color blocks`.
9. Build prompts in the same content style as a polished template result: first create one full-page creative prompt, then split it into module prompts. Do not put internal execution wording into image prompts, such as `product folder`, `Excel screenshots`, or long hidden workflow rules that the image model cannot see.
10. If a module prompt or template instruction mentions a model/person/on-body look, send suitable model reference images to the generation API for that module. This overrides rigid reference-role defaults. If the module does not mention a model/person, do not send model references just because they exist.
11. Treat the spreadsheet inside each SPU folder as `1-产品属性表.xlsx` even when the filename is different. Prefer an exact `1-产品属性表.xlsx` match when present; otherwise use the first non-temporary Excel workbook in that SPU folder. If that spreadsheet contains `Section {n}` and matching copy fields for a module, use that spreadsheet copy directly in Section n prompts. If Section n copy is missing, write clear marketplace-language copy from the module function in `模板.txt` and the product attributes in the spreadsheet.
12. Section 1 is the only default LOGO-exposure section, unless the root `模板.txt`, template analysis, or section prompt explicitly says not to use brand LOGO/wordmark/brand mark as a layout design element. When LOGO is allowed, attach the product-local `LOGO` image to Section 1 generation when available and use a generic supplied-LOGO instruction without embedding reference numbers, filenames, paths, or a reference map in the API prompt. Record the exact LOGO file and upload position only in `module_reference_upload_log.json`. When layout LOGO usage is disabled by the template, do not attach standalone LOGO references, remove LOGO-reference wording from the submitted prompt, and add a clear no-layout-logo instruction plus narrow negative prompt terms. Do not ask the model to erase small logos, labels, embroidery, tags, patches, or brand details that naturally exist on the product references.
13. Section 1 model pose must feel like fashion magazine editorial posing, and Section 1 poses must not repeat exactly across SPUs in the same batch. Assign concrete, vivid pose language deterministically by batch order. Do not send internal cross-product instructions like "do not repeat other SPUs" to the image model.
14. Every generated module must log the reference images submitted and API submit/status/download/error information immediately per module, not only after the full product finishes.
15. After all module images for a product are generated or confirmed present, stitch that product's module images into one long vertical A+ image.
16. Sections within the same SPU should not reuse the exact same supplied model reference image when enough distinct AIGC/model references exist. Identity consistency overrides this preference: Section 2 must always reuse the brief `model_identity_reference`, and any later identity-sensitive section may reuse it when unused references would weaken identity. If unused references run out, reuse the clearest earlier front/three-quarter references so the module still receives at least two supplied identity references.
17. When a module needs `model_identity`, attach at least two confirmed-person references when available. Section 2 must include the brief identity anchor plus a different confirmed front/three-quarter AIGC/model reference when available. At least one selected reference must be a full-body or clear front/on-body image when present. Product flats do not count toward this minimum.
18. Generated section copy must read like shopper-facing Amazon A+ copy, not image-generation instructions. Avoid prompt-like phrases such as "shown with", "captured through", "true front-and-back product clarity", "module", "layout", or "reference". Use short benefit-led copy that can plausibly appear on the final A+ image.
19. Clean every parsed section title before writing prompt files. Strip stray `?`, `？`, replacement characters, mojibake separators, and repeated `Section {n}` prefixes so final prompts use `Section {n} - <clean title>`.
20. Section 3 and Section 4 fallback headlines must be product-specific. Use product type, color, fit, fabric, feature rows, and product-analysis text to produce concrete shopper-facing headlines. Do not fall back to repeated generic phrases such as `STYLE FROM EVERY ANGLE` or `DETAIL THAT HOLDS UP`.
21. Visible prompt language follows spreadsheet values, not spreadsheet field names. If product attribute values are German, generate German visible-copy instructions, German fallback headline/copy, and a German-friendly negative prompt. Preserve German spelling, capitalization, and umlauts. Default to English only when values are English.
22. After stitching each SPU long image, create `<ROOT>\输出结果` when needed and copy the stitched long image there with the filename unchanged.
23. If the spreadsheet contains a plain `Section {n}` row, use that row's value directly as the module `Copy` field. Do not split it into Headline/Copy, do not summarize it, and do not translate it unless the spreadsheet itself provides a translated value.
24. Prompt language follows `marketplace` first. `DE`, `AT`, and `CH` generate German module prompts and German fallback visible copy; `US`, `UK`, `CA`, and `AU` keep English prompts and English fallback visible copy. If `marketplace` is missing, fall back to spreadsheet value-language detection.
25. Never use a supplied model back-view image as the only model reference for a module. If any selected model reference is a back-view image, also attach at least one additional supplied model image when available, preferably a front-facing, full-body, or clear on-body image. If no second model image exists, omit the lone back-view model reference instead of sending it by itself.
26. Fallback visible copy, especially for Section 3 and Section 4, must read like shopper-facing advertising copy rather than module/layout explanation. Avoid phrases such as `product views`, `views show`, `front and back views`, `on-body and product views`, `in context`, `module`, `layout`, and `reference`. Convert these into benefit-led copy about styling value, comfort, fit, construction, graphic impact, texture, or everyday use.
27. Use one labeled contact sheet and one request to the user-selected analysis model for each exact SKU. Tag every allowed image recursively, including `素材`, `上身1`, `上身`, `AIGC`, and root-level images, before module reference allocation. Required fields are `contains_person`, `subject_type`, `view`, `framing`, `usable_for_identity`, `identity_quality`, `gender_presentation`, and `detail_types`. Require complete ID coverage and record the selected model in every tag's `source`; never silently replace an API failure with heuristic tags. A root-level image may be tagged so its content can be identified, but when its exact SKU-relative path has only one component and its semantic tag says `contains_person: true` or `subject_type: model_person`, force `usable_for_identity: false`, record `source_excluded_reason: sku_root_model_image`, and exclude it from every downstream creative/reference input. Reference allocation must use only visual-semantic tags, never filenames or directory names.
28. If the final reference list submitted to the image API contains no model/person/on-body reference image, clean the entire submitted prompt before API submission. Remove `Reference note` model-reference claims and any strong model-reference cues from Visual Direction, Product Information, Product Accuracy, or other sections, then add an explicit no-people/no-random-model instruction.
29. Product-category detection for fallback headlines/copy must prioritize explicit spreadsheet fields such as `Product type`, then use word-boundary matching. Never classify by loose substring matches such as `hat` inside `that`; this causes unrelated SPUs to inherit cap/hat copy.
30. If the spreadsheet does not provide Section n copy, generate product-specific `Headline`, `Copy`, and `Visual Direction` from the current root `模板.txt` module function plus `product_type`, `fit`, `fabric`, `feature`, `target_customer`, color, and marketplace language. Do not use fixed repeated fallback text for a section number or broad product category. The same section number may mean different things when the template changes, and two pants/caps/hoodies in the same batch must still get different copy when their features differ, such as pinstripe pleats vs dachshund embroidery vs rhinestone cargo details.
31. Template-level no-logo instructions have higher priority than default Section 1 logo behavior. Treat phrases such as `不要出现品牌LOGO`, `不出现LOGO`, `不露出LOGO`, `无LOGO`, `禁止LOGO`, `no logo`, `without logo`, `do not show logo`, and `no wordmark` as hard constraints against using standalone LOGO assets or logo-like marks as layout design elements. In that mode, generated prompts must not mention attached LOGO references and submitted reference lists must exclude standalone `LOGO.*` files. The image prompt should say: `Do not add, enlarge, redesign, or use any brand LOGO, wordmark, brand mark, brand badge, or logo-like emblem as a separate layout design element. Preserve any small logo, label, embroidery, tag, patch, or brand detail that already exists naturally on the product reference images as part of the actual garment/product.`
32. Final module prompt files must be prompt-ready API text, not intermediate analysis briefs. Do not include `Product Folder`, `Reference Images To Inspect`, `Logo References`, `Visual Observations`, local/UNC paths, draft placeholders, or other workflow-only inspection sections in `module_prompts` or submitted API prompts. Never append `Attached Reference Image Map:` or any filename/path list to the API prompt. Record exact submitted reference filenames only in `module_reference_upload_log.json`. The prompt saved in `api_submitted_prompts` must match the text sent to the API.
33. If the root `模板.txt` or a section instruction says a module should not upload/send/use reference images, treat that as a hard per-section rule. Recognize phrases such as `不要上传参考图`, `不上传参考图`, `无需参考图`, `不要发送参考图`, `不发送参考图`, `不传参考图`, `no reference images`, `without reference images`, `do not upload reference images`, and `do not send reference images`. For that section, `module_reference_images.json` must have no references, API `imageUrls` / `image_urls` must be empty, no LOGO/model/product references should be uploaded, and the final submitted prompt must not mention attached/supplied reference images.
34. Section 1 must never use supplied model back-view images as model references. If the model pool contains front/three-quarter/side/full-body references, Section 1 must select from those only. If only back-view model references exist, omit model identity references for Section 1 rather than using a back-view model reference.
35. If Section 2 and Section 3 reuse any supplied model reference, do not use a safe-action library, category action template, deterministic pose phrase, Gemini/GPT action, or scripted pose insertion. The main agent must inspect the SKU contact sheet, the actual product silhouette/details, the Section 2 composition, the planned Section 3 layout, and the final selected uploads, then design one concrete, image-adapted fashion action that is visibly different from Section 2 while preserving identity and product readability. Append that action directly inside Section 3's existing `Layout task:` paragraph in the marketplace-selected prompt language. Do not create a separate `Section 3 fashion action:` heading or block. Reference planning must hard-fail until the action-bearing `Layout task:` is present and validated.
36. Treat the `Layout task:` emitted by `build_creative_module_prompts.py` as a draft scaffold only. Before generation, the main agent must inspect the current SKU contact sheet, final selected uploads, product truth, and neighboring module plans, then completely replace that draft with a human-written, product-specific composition concept. Preserve the current `模板.txt` Section n function, but do not retain or merely append to stock starters such as `Build a horizontal hero/brand banner`, `Create a model fit board`, `Create a combined model-plus-flat-lay composition`, `Create a people-free detail/macro collage`, or `Create a text-free, people-free, style-matched background module`. Scripts, GPT/Gemini analysis, category templates, phrase libraries, and string combinations must not author the final `Layout task:`.
37. Headline and Copy generation uses a hybrid copy system. GPT/Gemini analysis should propose shopper-facing A+ copy from the actual `product_type`, `fit`, `fabric`, `color`, `feature_*`, model mood, and current Section task; local prompt-building rules then enforce product-specific fallback copy and same-SKU de-duplication. Do not use fixed category sentences such as one generic zip-hoodie/cardigan line across multiple SPUs. Within one SKU, every Section Headline and Copy must use a distinct selling angle unless the spreadsheet explicitly supplied identical copy; spreadsheet-authored text remains authoritative, while generated text is rewritten when duplicate or near-duplicate content is detected.
38. Use the explicit spreadsheet-derived `product_type` as product context for copy, reference planning, and the main agent's Section 3 action judgment. Never reduce the action decision to a normalized category lookup or fixed top/bottom/hat/general pose library. Use word-boundary fallback matching only when `product_type` is missing; never classify by loose substring checks such as `"hat" in text`.
39. Orchestrate every multi-SPU batch synchronously, one exact SKU per command. Wait for that SKU's process to return or reach the configured timeout, close the execution cell, verify that no child process remains, and only then launch the next SKU. Every command must contain exactly one `--product "<ONE_PRODUCT_FOLDER_NAME>"`; never generate a whole root, pass comma-separated names, or hide several SKUs inside a loop or wrapper invocation.
40. Run generation only through `scripts\run_sync_product_generation.py`. The wrapper must write `<ROOT>\_aplus_sync_run_status.json`, enforce a finite timeout, terminate the complete child process tree on timeout or interruption, and return a terminal exit code. Set the outer shell/tool timeout at least 60 seconds longer than `--timeout-seconds` so the wrapper has time to perform cleanup; a shell timeout alone is not cleanup. After every return, inspect the process command line and verify module count, dimensions, logs, stitched long image, and root `输出结果` copy before marking the SKU complete.
41. At task start, before any preparation or analysis, remove every `color_options` row from every direct SKU attribute workbook. Back up each changed workbook and write the root audit JSON. Stop if any workbook removal or verification fails.
42. Creative-brief preparation and module construction must use the same shared, normal-mode Excel reader. Always load with `read_only=False` and iterate the physical worksheet rows. Never use a read-only streaming worksheet for either stage, because stale worksheet dimension metadata can truncate valid cells to `A1`.
43. Excel `Section N Headline` and `Section N Copy` belong only to Section N. Override only the matching field in the matching section, and leave Gemini-generated Headline or Copy unchanged when the corresponding Excel cell is empty. After resolution, validate section ownership and cross-section duplicates. If any authoritative Section N Headline/Copy appears in another section, stop before reference planning or image generation.
44. Do not address missing rendered copy by adding fixed text-area percentages, mandatory split layouts, rigid text-safe blocks, or extra design restrictions. Keep the original design freedom. Treat a missing rendered title/copy as image-output QA and regenerate that module when necessary.
45. `Suggested Visual Baseline` is a main-agent visual-analysis deliverable, not a scripted or Gemini-composed field. For every SKU, inspect its model images and product/flat-lay/detail images yourself, then write four genuinely product-specific dynamic lines. Do not create baselines by rules, palettes, category templates, string combinations, scripts, or copied sibling wording. Keep the `Style balance` line exactly fixed. If visual inspection cannot be completed, stop instead of fabricating a baseline.
46. Gemini and prompt-building scripts must not author `Text / Callouts:`. After the first reference-planning pass has produced `module_reference_images.json`, the main agent must inspect the existing layout plan, the exact images selected for upload, and the complete existing module prompt, then manually write exactly one `Text / Callouts:` block for every module. The wording must be supported by visible product/reference evidence, complement rather than repeat `Headline` or `Copy`, and never conflict with `Visual Direction`, `Layout task`, `Layout execution`, or `Product Accuracy`. Do not invent measurements, materials, functions, construction, colors, or views that are not supported. For an intentionally text-free module, keep the field and explicitly state that no visible callout text should be rendered.
47. Before every SKU submission, read `references\manual-visual-direction-standard.md` in full, inspect that SKU's readable model/product contact sheet and exact selected uploads yourself, and manually rewrite both Visual Direction fields. Write exactly one detailed `Layout task:` block followed immediately by exactly one `Layout execution:` paragraph before `Product Accuracy:`. Use the marketplace-selected language: German for `DE`, `AT`, and `CH`; English for `US`, `UK`, `CA`, and `AU`; otherwise use the same spreadsheet value-language fallback as the prompt builder. The task must express a bespoke composition idea, product evidence goal, and product-derived design motif. The execution must specify hierarchy, unequal subject scale and placement, controlled negative space, text placement, visual flow, depth/overlap, visual connectors, product-detail emphasis, and protection of critical graphics/construction. Use actual silhouette, colors, material, graphics, model identity, pose mood, scene tone, and final uploads. Sanitize readable third-party signs, storefront names, source-location wordmarks, and unrelated logos from source environments by replacing them with unbranded scene texture. For visually light products, create contrast and rhythm from real lining, drawcords, zippers, embroidery, hardware, seams, plaid, print, or texture. Describe desired additions positively. Preserve required proper nouns, but do not let them change the paragraph language. Gemini, GPT, scripts, palette rules, category templates, and string combinations must not author either final field. Stop if direct visual inspection cannot be completed.
48. After the first Section 2/3 reference-planning pass, inspect `module_reference_requirements.json`. When `section3_human_fashion_action_required` is true, compare the actual Section 2 and Section 3 reference images and compositions yourself, then append a specific body action, hand/arm relationship, gaze or torso direction, product-clearance logic, and relationship to the Section 3 composition directly to the existing `Layout task:` paragraph. Do not create a separate action heading, mention shared filenames, internal comparison rules, or workflow metadata in the API prompt. Rerun reference planning; it must validate the action-bearing `Layout task:` without rewriting it.
49. Run `validate_manual_layout_prompts.py` after the reference plan and before submission. No module may enter API generation unless it contains exactly one main-agent-authored `Layout task:`, exactly one main-agent-authored `Layout execution:` immediately before `Product Accuracy:`, and exactly one manually written `Text / Callouts:` after Product Accuracy content. The validator must reject unchanged draft starters, short or generic layout fields, insufficient designed-composition dimensions, same-SKU or sibling-SKU near-duplicate visual directions, separate Section 3 action blocks, unsupported callouts, negative empty-layout correction phrases, and over-minimal positive-prompt stacks. Rewrite rejected fields from direct image inspection; never weaken or bypass the validator. If Section 3 reuses Section 2 model references, `build_module_reference_images.py` must also report `section3_human_fashion_action_validated: true`.
50. Immediately before writing each exact final API prompt, defensively remove any legacy `Attached Reference Image Map:` block, reject any separate `Section 3 fashion action:` block, preserve the human-authored directive text verbatim, and normalize the canonical order to `Layout task:` -> `Layout execution:` -> `Product Accuracy:` -> `Text / Callouts:`. Do not remove the manually written `Text / Callouts:` field. Write that exact prompt to `api_submitted_prompts` and update `api_prompt_review_deduplicated.md`. The review file must show repeated exact prompt blocks once, list the modules to which each shared block applies, and retain only unique content in each per-module section.
51. When `--overwrite` is used for output QA, first copy the existing final module, raw result, and current stitched long-image copies into a new timestamped `_aplus_creative_work\generation_result_backups` folder with a manifest. Only after the backup succeeds may the active module result be replaced. Never silently overwrite a rejected image.
52. After the provider returns a taskId, write it atomically and immediately to `_aplus_creative_work\generation_state.json` before normal event logging or polling. Record provider, module, submitted prompt path, timestamps, provider status, result URL, output paths, and completion state without API keys. The root synchronous status and per-SKU provider state must agree.
53. Do not launch detached supervisors, background workers, `Start-Process`, or unmonitored yielded cells. The synchronous wrapper starts `generate_modules_toapi.py` as one child process, waits for it, and owns cleanup of that complete process tree.
54. On interruption or timeout, read `generation_state.json` before rerunning. If a `provider_task_id` exists, recovery must be query-only and reuse that taskId; skip uploads and submission so the interrupted attempt cannot create a second billed task. If no taskId exists, classify the attempt as unsubmitted before a new submission.
55. Hard-exclude every image inside any directory named or containing `弃用`, `过程文件`, `生成结果`, `输出结果`, `备份`, or `backup`, plus all `_aplus*` and `_influencer*` operational directories, from semantic-analysis candidates, reference-role maps, module mappings, shared discovery, and API uploads. These exclusions cannot be relaxed by a filename, an old mapping, or module fallback.
56. Match semantic tags only by the normalized complete path relative to the current SKU. Basename-only lookup, filename fallback, directory-name inference, and absolute-path aliases are forbidden. Two images with the same filename in different SKU subdirectories must remain independent records.
57. Every business reference must resolve to an existing image beneath the current SKU and outside every hard-excluded directory immediately when the mapping is built and again before upload. External paths, sibling-SKU paths, old batch paths, deleted files, and stale historical absolute paths are hard failures.
58. Rebuild `module_reference_images.json` from an empty dictionary on every reference-planning pass. Never read, merge, preserve, or silently retain the previous mapping when a new role selection is empty or fails. A failed dynamic contract stops processing and leaves no historical selection masquerading as a fresh result.
59. Derive each module's image-role contract dynamically from the current `模板.txt` analysis and complete module prompt semantics; never bind reference roles to a section number. The required sequence is: template/module prompt -> identify this run's module function -> derive required and optional image roles -> select from visually analyzed current-SKU images -> hard-validate source and role. If the function cannot be resolved, stop.
60. Enforce the derived contract: `模特正侧背/多角度版型` requires a front model and back model, with side or three-quarter model optional when unavailable; `模特＋平铺正背面` requires a front-facing identity model, product flat-lay front, and product flat-lay back; `面料/工艺/细节特写` requires visually confirmed fabric, neckline, cuff, zipper, print, stitching, hem, pocket, hardware, closure, or general-detail images and prefers `素材`; `纯背景/无需参考图` uploads no business reference. Missing required roles are hard failures, not invitations to guess or reuse history.
61. Apply the following layout-geometry rule only when `module_reference_requirements.json` classifies the section as `construction_detail`, `fabric_detail`, or `graphic_detail`, or the current template function unambiguously identifies a people-free product-detail/fabric/construction/macro section. In that section's final `Visual Direction` fields, both `Layout task:` and `Layout execution:` must use straight-edged rectangular or orthogonal panels, crops, frames, dividers, and windows. Do not use curved/arched/arcing crops or windows, crown-panel arcs as nested frames, fan-shaped curved crops, fold-following windows, crescent windows, irregular windows, organic-shaped masks, or a dominant diagonal material field rising from lower-left to upper-right with a curved crop overlapping its upper edge. Reject close paraphrases and equivalent German wording. This restriction does not apply to hero, model/fit, model-plus-flat-lay, lifestyle, influencer, placeholder, or background sections, and it does not prohibit accurately describing a physical product feature such as a curved brim when that feature is not being used as layout geometry.
62. Never use a model/person image stored directly in the SKU folder root. A visually confirmed root-level model/person image must not become `model_identity_reference`, `front_model_reference`, a creative-brief request image, an influencer reference, a module reference, a fallback reference, or an API upload. This is a semantic rule: do not infer person content from the filename. Root-level non-person product flat lays, product details, and eligible product-local LOGO files remain available under their normal contracts. Enforce the exclusion again immediately before API upload so stale historical mappings cannot bypass it.

## Workflow

1. Confirm the root directory. Treat every direct child SKU directory as one product. Remove `color_options` rows before any other task step:

```powershell
python "<SKILL_DIR>\scripts\remove_color_options_rows.py" --root "<ROOT>"
```

Confirm `_aplus_color_options_removal.json` reports no errors. Each changed workbook must have a timestamped copy under `_aplus_color_options_backups`.

2. Analyze the root template:

```powershell
python "<SKILL_DIR>\scripts\analyze_template.py" `
  --template "<ROOT>\模板.txt" `
  --out "<ROOT>\_aplus_creative_template_analysis.json"
```

3. Check `modules[*].instruction` in `_aplus_creative_template_analysis.json`.
   - If an instruction contains `占位符`, `等大色块`, `色块`, `placeholder`, or `color blocks`, mark that module as `placeholder_blocks`. Do not generate influencer selfies for it.
   - If an instruction contains `不需要生成网红图`, `无需生成网红图`, `并不需要生成网红图`, `用于后续替换为网红图`, `背景图`, or `不需要任何文案` without explicit color-block wording, mark it as an influencer replacement background. Do not generate influencer selfies, people, social screenshots, color blocks, or visible copy for it.
   - If an instruction contains `网红图`, `网红`, `UGC`, or `influencer` and does not contain placeholder/no-generation wording, generate influencer selfie images before A+ modules.

4. Prepare influencer selfie plans:

Before preparing plans, complete the selected Gemini/GPT visual tagging pass for every allowed SKU image, including `素材` and `上身1`, so `gender_presentation` is available. If the user's original request already selected the analysis model/provider, do not ask again. `prepare_selfie_batch.py` must prefer the clearest usable tagged model identity from an allowed SKU subdirectory, derive `target_gender` from that image, and record `target_gender_source`. A visually confirmed model/person image stored directly in the SKU root is ineligible. If tags or usable non-root model gender are unavailable, it may record an attribute-table fallback, but the main agent must visually inspect the selected model reference and correct the plan before building selfie prompts.

```powershell
python "<SKILL_DIR>\influencer_scripts\prepare_selfie_batch.py" `
  --root "<ROOT>" `
  --background-root "<BACKGROUND_ROOT>"
```

Use the background folder supplied by the user via `--background-root` or the `APLUS_BACKGROUND_ROOT` environment variable. If neither is set and influencer generation is required, ask for the background image folder.

After preparation, inspect product and background contact sheets. Fill or correct each product's `_influencer_selfie_work\selfie_plan.json`:

- `front_model_reference`: best allowed subdirectory model/product image for Image 1, never LOGO and never a root-level SKU model/person image.
- `target_gender`: women, men, or unisex, taken from the selected model identity's visible gender presentation whenever available.
- `target_gender_source`: `model_identity_reference` when a usable tagged model image supplied the value; use `attribute_table_fallback` only when no usable model identity/gender is available.
- `model_identity_reference`: clearest supplied model image from an allowed SKU subdirectory when one exists; never select a root-level SKU model/person image.
- `model_identity_notes`: visible model identity details for A+ modules.
- `product_subject`: top, T-shirt, pants, sweatpants, skirt, dress, hoodie, etc.
- `product_accuracy_notes`: exact garment details to preserve.
- `background_reference` and `background_reason` for each occasion.
- Avoid reusing the same background mapping mechanically across products unless the user requests a controlled repeat.

5. Build final influencer prompts:

```powershell
python "<SKILL_DIR>\influencer_scripts\build_selfie_prompts.py" `
  --root "<ROOT>" `
  --template "<SKILL_DIR>\assets\selfie_prompt_template.txt"
```

The prompt builder enforces the already-resolved `target_gender` from the model identity. A conflicting `target_customer` value must not override it. Attribute-table gender is only a fallback when `target_gender` remains unspecified because no usable model identity/gender exists.

6. Ask the user for generation method and API supplier:

```text
请选择生图方式：
1. Codex 内置 image_gen 工具
2. API 方式：GPT-ToAPI（原 ToAPIs gpt-image-2）
3. API 方式：GPT-RH（RunningHub rhart-image-g-2-official）
```

If the user chooses API, ask which supplier to use before running generation. Use API keys from `--api-key`, supplier-specific environment variables, or an interactive prompt. Do not write secrets into files.

- GPT-ToAPI uses `TOAPIS_API_KEY` or `OPENAI_API_KEY`.
- GPT-RH uses `RUNNINGHUB_API_KEY`.
- GPT-RH default `quality` is `medium`; allowed values are `low`, `medium`, and `high`.

Also ask for the text/image analysis model before building or revising product briefs:

```text
Provide the exact ToAPIs text/image analysis model ID, for example `gpt-5.6-sol` or a supported Gemini model.
```

Use `TOAPIS_API_KEY` or `OPENAI_API_KEY` and pass the exact selected model to the helper script below for reference-image/product analysis:

```powershell
python "<SKILL_DIR>\scripts\analyze_reference_with_toapi_gpt55.py" `
  --model "<USER_SELECTED_ANALYSIS_MODEL>" `
  --prompt "Analyze these product and model reference images for Amazon A+ planning..." `
  --image "<PRODUCT_OR_MODEL_IMAGE>" `
  --out "<PRODUCT>\_aplus_creative_work\gpt55_reference_analysis.json"
```

Use the selected-model analysis result as product truth and visual-baseline input, but do not copy raw analysis metadata into image-generation prompts.

After the user chooses the analysis model, process one exact SKU at a time. Build one labeled contact sheet containing every allowed image recursively, including `素材` and `上身1` while excluding all forbidden directories, send one request to that model, require exact full SKU-relative-path JSON coverage, and atomically write the validated tags:

```powershell
python "<SKILL_DIR>\scripts\tag_contact_sheet_with_toapi.py" `
  --root "<ROOT>" `
  --product "<ONE_PRODUCT_FOLDER_NAME>" `
  --model "<USER_SELECTED_ANALYSIS_MODEL>" `
  --request-timeout 300 `
  --overwrite
```

Set `TOAPIS_API_KEY` or `OPENAI_API_KEY` in the process environment; do not place the key in saved commands, status, prompts, or logs. Run this as a separate shell/tool invocation for each SKU and wait for it to return. Do not use a PowerShell loop that hides multiple SKU calls inside one execution cell.

The strict contact-sheet script writes `analysis_contact_sheet.jpg`, `analysis_contact_sheet_manifest.json`, `contact_sheet_analysis_raw.json`, the validated `aigc_model_view_tags.json`, and root `_aplus_sync_run_status.json`. It fails without replacing tags when the model times out, returns invalid JSON, omits an ID, adds an unknown ID, or returns an invalid field. It also marks visually confirmed root-level model/person images as downstream-excluded without changing the selected analysis-model source record. Never continue with `source: heuristic`; the legacy per-image helper may use heuristics only when a user explicitly requests `--allow-heuristic-fallback`, and such a run does not pass this skill's generation gate.

Each `aigc_model_view_tags.json` entry must include at least:

- `contains_person`: boolean based on visible image content, never inferred from `上身` alone.
- `subject_type`: `model_person`, `product_flatlay`, `product_detail`, or `unknown`.
- `view`: `front`, `three_quarter`, `side`, `back`, `detail`, or `unknown`.
- `framing`: `full_body`, `half_body`, `upper_body`, `closeup`, or `unknown`.
- `usable_for_identity`: boolean; always `false` for a visually confirmed root-level SKU model/person image.
- `source_excluded_reason`: `sku_root_model_image` for a visually confirmed root-level SKU model/person image, otherwise absent or empty.
- `identity_quality`: `high`, `medium`, `low`, or `unknown`.
- `gender_presentation`: `woman`, `man`, `ambiguous`, or `unknown`.

For API influencer generation:

```powershell
python "<SKILL_DIR>\influencer_scripts\generate_selfies_toapi.py" `
  --root "<ROOT>" `
  --size "4:5" `
  --resolution "2K"
```

7. Run normal A+ preparation:

```powershell
python "<SKILL_DIR>\scripts\prepare_aplus_batch.py" --root "<ROOT>"
```

8. Inspect product references and create each product's `_aplus_creative_work\aplus_creative_brief.md`.

The brief must include:

- Product truth from Excel and image inspection.
- `Model Identity Lock` with an allowed subdirectory reference path and visible identity notes. Do not select or describe a root-level SKU model/person image as the identity anchor.
- Product accuracy notes for exact garment construction, color, print, fabric, and fit.
- A record of the selected identity reference's visible gender presentation as the authoritative `target_gender`, plus spreadsheet `target_customer` retained as advisory metadata. Do not pause or swap the supplied person when they differ.
- Section plans matching the template module count.
- For model sections: require the same supplied model identity.
- For influencer sections: say generated influencer images should be the module's main UGC/photo-tile content.
- For explicit color-block placeholder sections: say no influencer photos, selfies, people, UGC screenshots, or social posts should be generated. The module should use the same global style and show exactly the requested equal-size color-block placeholders.
- For influencer replacement background sections: say no influencer photos, selfies, people, UGC screenshots, social posts, color blocks, or visible copy should be generated. The module should be a clean style-matched background/layout image, ready for later influencer replacement.
- Do not write internal correction language into image-generation prompts. Avoid phrases like "replace the template's original men's Liquid Metal tee" or any mention of irrelevant template products, wrong genders, or obsolete graphics. Final prompts should describe only the actual product and the current module.
- Keep each module prompt focused on that module. Use shared product truth, model identity lock, and visual system notes for consistency; do not append the full creative brief or other modules' directions into every module prompt.
- Preserve template-level design execution requirements from `模板.txt`, especially typography, font family, exact supplied LOGO usage, and brand-asset consistency. Convert them into direct image-generation instructions in both the full-page prompt and every split module prompt.
- If `模板.txt` says no brand LOGO/wordmark/brand mark should appear, this overrides any default Section 1 standalone LOGO behavior. Keep typography and layout requirements, remove standalone LOGO-reference wording, add an explicit no-layout-logo rule, and preserve product-reference logos, labels, embroidery, tags, patches, and brand details that are physically part of the garment/product.
- If `模板.txt` says a section should not upload or use reference images, preserve that section-level instruction in the prompt as a direct no-reference rule and remove wording such as `attached product reference images`, `supplied references`, model-reference notes, LOGO-reference notes, and attached-reference map expectations for that section.
- Write final prompt-ready copy in the marketplace-selected language. Do not carry Chinese template wording, Chinese file paths, or Chinese labels into renderable copy for the supported German/English marketplace mappings.
- Create a downstream creative contact sheet that excludes visually confirmed root-level SKU model/person images while retaining allowed subdirectory model images plus product flat lays/details, inspect it yourself at readable resolution, and write this exact block in the brief:

```text
## Suggested Visual Baseline
Main color: <manually observed product-specific direction>
Supporting colors: <manually observed product-specific direction>
Background: <manually chosen product-specific scene direction>
Texture: <manually observed material and mood direction>
Style balance: 70% Amazon information clarity + 30% light streetwear editorial atmosphere
```

- The first four lines must be independently written for this SKU from the inspected images. Do not ask Gemini or a script to invent them, and do not reuse a rule-combined baseline. The prompt builder rejects missing/incomplete baselines, a changed Style balance line, and near-duplicate sibling baselines.

Save the twelve (or current batch count) human-written baseline objects in `<ROOT>\_aplus_manual_visual_baselines.json`, keyed by exact SKU folder name, using the five exact field names above. Then let the same user-selected analysis model perform the remaining image analysis and creative-copy work while pinning those human values verbatim:

```powershell
python "<SKILL_DIR>\scripts\generate_creative_briefs_gemini.py" `
  --root "<ROOT>" `
  --model "<USER_SELECTED_ANALYSIS_MODEL>" `
  --baseline-file "<ROOT>\_aplus_manual_visual_baselines.json" `
  --overwrite
```

The script may send the contact sheet plus selected model/product references to the selected model, but it must exclude prior output images and may not rewrite the human baseline. It must record the exact selected model and must not add fixed text-safe percentages, rigid split layouts, or other copy-missing workarounds to the creative brief.

9. Build A+ module prompts:

```powershell
python "<SKILL_DIR>\scripts\build_creative_module_prompts.py" `
  --creative-brief "<PRODUCT>\_aplus_creative_work\aplus_creative_brief.md" `
  --template-analysis "<ROOT>\_aplus_creative_template_analysis.json"
```

This script writes:

- `<product>\_aplus_creative_work\aplus_full_prompt.txt`: one full-page prompt in the same structure as the analyzed template result.
- `<product>\_aplus_creative_work\module_prompts\section-XX-*.txt`: per-module prompts split from the full-page direction.

The module prompts should stay close to the template-result format: one complete overall prompt first, then split section prompts with canvas specification, `Suggested Visual Baseline`, template design requirements, product information, section headline/copy, visual direction, product accuracy, optional reference note, and negative prompt. Avoid verbose internal-only constraints. `module_prompts` must be clean API-ready prompt bodies, not creative-brief drafts.

Prompt cleanliness rules:

- Do not include `Copy Source`, `文案来源`, `Generated from template function and product attributes`, spreadsheet/file names, local paths, or workflow metadata in prompts sent to image generation.
- Do not include draft-only sections such as `Product Folder`, `Reference Images To Inspect`, `Logo References`, `Visual Observations`, image path lists, or inspection placeholders. Product Information should be a concise product-fact summary only.
- Do not include internal product-truth wording such as `Use only verified product details from the spreadsheet`, `source references`, or `Module purpose from template` in prompts sent to image generation. Convert those into concrete visible product facts, such as exact color, fit, fabric, print, logo placement, silhouette, and construction details.
- Do not send cross-product operational rules to the image model. Section 1 may use its approved hero-pose plan. When Section 2/3 model references overlap, the main agent must design the Section 3 action from the actual SKU images, selected uploads, and composition, then append it inside `Layout task:`; never use a category action library or a separate action heading.
- Parse spreadsheet copy such as `Headline: ... / Subheading: ...` into separate `Headline` and `Copy` fields. Never duplicate the same long line in both fields.
- Generate product-specific headlines, copy, and visual direction when Section n copy or product-ready direction is absent. Use product type, color, fit, fabric, print/detail, model mood, and the current template module purpose.
- Use the hybrid copy system for generated text: GPT/Gemini may polish the language, but local rules must first choose a product/section-specific selling angle and then de-duplicate Headline and Copy within the same SKU. If two generated sections produce the same or near-same text, rewrite the later generated section using a different product attribute or section function. Do not alter spreadsheet-authored Section copy for de-duplication.
- Section titles must be cleaned before output. Use `Section n - Title`, never mojibake separators or a stray question mark after `Section n`.
- Section 3 and Section 4 fallback headlines must be concrete to the product/category/detail, not generic repeated titles.
- Shopper-facing copy must be concise and benefit-led. It should sound like final A+ page text, not a camera/layout instruction.
- If non-spreadsheet copy sounds like a module explanation, such as describing product views, references, layout, or what the image shows, replace it with a cleaner advertising line. Keep spreadsheet-authored Section copy unchanged.
- If spreadsheet values are German, prompts must instruct the image model to render German copy and avoid English visible labels. German fallback copy is used when Section n copy is missing.
- If the spreadsheet has a plain `Section n` row, write that row value directly under `Copy:` in the final module prompt.
- Use `marketplace` as the primary language switch: DE/AT/CH -> German prompt output; US/UK/CA/AU -> English prompt output.
- Do not accept Gemini-, spreadsheet-, or script-authored `Text / Callouts:` as final. After `module_reference_images.json` exists, the main agent writes the field from the existing layout plan, exact upload images, and complete prompt context; it must add supported complementary information without duplicating or contradicting existing content.
- Do not output `Attached Reference Image Map:` or raw reference filenames/paths in API prompts. Keep exact file mapping only in `module_reference_upload_log.json`.
- Keep the literal `Layout execution:` label unchanged, write its complete paragraph in the same marketplace-selected language as the module prompt, and place it between `Layout task:` and `Product Accuracy:`, immediately before `Product Accuracy:`. Place the human-authored `Text / Callouts:` after the `Product Accuracy:` content. Do not accept English layout prose in a German module or German layout prose in an English module.
- Treat the builder's `Layout task:` text as a draft. After reference planning, replace it completely with the main agent's two-to-four-sentence design concept and add the main-agent-authored `Layout execution:` paragraph by following `references\manual-visual-direction-standard.md`. Do not submit the builder's stock composition starter or merely append product adjectives to it.
- Do not stack restrained/minimal commercial styling, a white/pale product and background, and repeated generous white/negative-space wording in the same positive prompt. Replace negative corrections about an `empty`, `blank`, `bare`, or `sparse` result with positive executable directions that name concrete overlaps, accents, trims, textures, or product details.
- Insert the manually written `Suggested Visual Baseline` from the creative brief verbatim. Do not derive or rewrite it during module construction.

Excel section-copy behavior:

- The SPU folder's Excel workbook is the product attribute table even if the filename is not `1-产品属性表.xlsx`. If the spreadsheet contains a row or key like `Section 1`, `Section 2`, etc. and neighboring copy/title/callout cells, that copy is authoritative for the matching module.
- Both creative-brief preparation and module construction must call the shared normal-mode reader in `scripts\excel_reader.py`; do not add a second workbook-reading path and do not use `read_only=True`.
- If the spreadsheet contains `Section n Headline`, `Section n Title`, `Section n 主标题`, or equivalent title rows, use that value directly as the module `Headline`. If it contains plain `Section n` or copy/body/subheading rows, use that value as the module `Copy` according to the parsing rules above.
- Apply each non-empty Excel field only to its own Section n and its own field. An empty Excel Headline or Copy does not erase or replace Gemini-generated text. Before writing module prompts, hard-fail if authoritative Section n text appears in any other section; after generated-text resolution, hard-fail unresolved cross-section duplicate Headline/Copy.
- After an ownership hard failure, do not continue to reference planning or image generation. If the misplaced destination field is not itself Excel-authored, regenerate only that destination field with `repair_cross_section_copy_gemini.py --model "<USER_SELECTED_ANALYSIS_MODEL>"`, then rerun the complete module builder and validators. Never rewrite the authoritative Excel-owned source field.
- If the spreadsheet does not provide Section n copy, infer concise renderable copy from the current `模板.txt` Section n function and product attributes. Do not assume Section 2/3/4 always means the same thing across templates, and do not reuse one category-level fallback sentence across multiple SPUs with different product details.
- Section fallback copy and visual direction must be based on the template's actual Section n function for this run: banner/hero, fit/silhouette, model plus flat-lay front/back, detail/macro/fabric, lifestyle/gift, or text-free replacement background. For example, a fit section should discuss cap adjustability, hoodie layering volume, or pants waistband/leg movement depending on the product.
- `Visual Direction` must include the section composition task inferred from the current `模板.txt`, not only a generic product/style statement. Write the layout task as direct API-ready wording, such as a hero banner, multi-angle model board, model-plus-flat-lay composition, people-free macro collage, or text-free replacement background.
- Track copy provenance internally for validation, but never render source labels or spreadsheet filenames in API prompt files.

Section 1 banner behavior:

- Treat Section 1 as the brand/logo hero banner unless the template explicitly disables LOGO exposure.
- Attach product-local `LOGO.*` to Section 1 even if the prompt does not contain the word `logo`, but only when the template does not disable LOGO exposure.
- Record the LOGO filename and upload position in `module_reference_upload_log.json`; do not append a numbered LOGO map or filename to the API prompt.
- Use fashion-magazine editorial pose direction. Across products in the same root batch, rotate concrete pose descriptions so two SPUs do not receive the same default pose. The prompt should describe only the chosen pose, not the batch comparison rule.

Before moving to reference planning or generation for one SKU, follow `references\v4-7-2-synchronous-recovery.md` in full.

10. Inject generated influencer images into A+ prompts only for true influencer sections:

```powershell
python "<SKILL_DIR>\scripts\inject_influencer_sections.py" `
  --root "<ROOT>" `
  --template-analysis "<ROOT>\_aplus_creative_template_analysis.json"
```

This creates `<product>\_aplus_creative_work\module_reference_images.json` and appends influencer UGC layout instructions to affected section prompts.

Explicit placeholder/color-block sections are skipped by this script and handled by the normal module prompt plus `build_module_reference_images.py` as `placeholder_blocks`. No-influencer background sections are also skipped by influencer generation, but are handled as `influencer_background`, not as color blocks.

11. Build per-module reference image maps:

```powershell
python "<SKILL_DIR>\scripts\build_module_reference_images.py" `
  --root "<ROOT>" `
  --template-analysis "<ROOT>\_aplus_creative_template_analysis.json"
```

This starts with an empty mapping, reads the original template analysis plus each complete module prompt, derives a dynamic function contract in Chinese or English, and writes:

- `<product>\_aplus_creative_work\reference_image_roles.json`: explicit role for each source image.
- `<product>\_aplus_creative_work\module_reference_requirements.json`: explicit module role and required reference roles.
- `<product>\_aplus_creative_work\module_reference_images.json`: final image list to upload for each module.

It detects module intent from terms such as `首图`, `模特`, `版型`, `廓形`, `正反面`, `印花`, `面料`, `细节`, `工艺`, `网红图`, `用于后续替换为网红图`, `背景图`, `占位符`, `色块`, plus English equivalents such as `hero`, `model`, `fit`, `silhouette`, `front-back`, `graphic`, `fabric`, `construction`, `UGC`, `influencer`, `background only`, `placeholder`, and `color blocks`.

The final mapping sends only references that satisfy the current module's derived contract:

- Model front/side/back or multi-angle function: front model plus back model are required; a side or three-quarter model is optional.
- Model plus flat-lay front/back function: front identity model, product flat-lay front, and product flat-lay back are all required.
- Fabric/construction/detail close-up function: use only visually verified detail roles and prefer matching images under `素材`.
- Pure-background/no-reference function: write an empty list and upload no business references.
- Other supported functions derive their own required and optional roles from current semantics; section numbers never supply defaults.
- Every selection uses exact full SKU-relative keys from `_aplus_creative_work\aigc_model_view_tags.json`; no basename fallback or filename/directory inference is allowed.
- Every selected path is checked beneath the current SKU and outside hard-excluded directories both during planning and immediately before upload.
- Any exact root-level SKU path tagged as a model/person is excluded from role sources and must hard-fail if a stale mapping attempts to upload it.

11.5. Complete the mandatory manual Visual Direction pass for this exact SKU before generation:

- Read `references\manual-visual-direction-standard.md` in full.
- Inspect the readable contact sheet, the exact selected uploads in `module_reference_images.json`, the full prompt, and all module prompts side by side.
- Completely replace every draft `Layout task:` and write every `Layout execution:` yourself in the marketplace-selected language.
- Read the exact `module_role` for each prompt from `module_reference_requirements.json`. Only for `construction_detail`, `fabric_detail`, or `graphic_detail`, use straight-edged rectangular/orthogonal crops and frames and exclude curved, arched, fold-following, irregular, crescent, organic-mask, nested-arc, fan-shaped, and lower-left-to-upper-right diagonal material-field window architecture from both layout fields. Preserve design freedom in all non-detail roles.
- Make each module use a distinct hierarchy, scale relationship, spatial rhythm, connector device, and reading path derived from the current product or scene.
- Remove readable third-party storefront/location wording and unrelated source logos from scene directions; replace them with unbranded material texture.
- Keep Section 3's required image-adapted action inside its rewritten `Layout task:` when applicable.
- Write the manual `Text / Callouts:` blocks, then rerun `build_module_reference_images.py` so action and upload-plan validation sees the final task wording.
- Synchronize the already-authored layout fields into the full prompt without allowing the script to create or rewrite them:

```powershell
python "<SKILL_DIR>\scripts\sync_manual_visual_directions.py" `
  --product-dir "<PRODUCT>"
```

  Confirm `manual_visual_direction_sync.json` reports the expected pair count and a timestamped backup.
- Run `validate_manual_layout_prompts.py --product-dir "<PRODUCT>"`. Do not generate until it passes.
- Ensure `aplus_full_prompt.txt` contains the same final Visual Direction wording as the module prompts. The generation step will write exact submitted prompts and the de-duplicated review; inspect those files again before accepting submission.

12. Generate A+ modules synchronously, one ready SKU at a time.

Enumerate valid direct-child SPU folders while excluding operational/output/backup folders. Complete and validate one SKU's human layout, run that SKU synchronously, wait for a terminal return, verify it, and close the execution cell before starting the next SKU. Never prepare or launch several SKU generations concurrently.

For GPT-ToAPI:

```powershell
python "<SKILL_DIR>\scripts\run_sync_product_generation.py" `
  --root "<ROOT>" `
  --template-analysis "<ROOT>\_aplus_creative_template_analysis.json" `
  --provider "gpt-toapi" `
  --product "<ONE_PRODUCT_FOLDER_NAME>" `
  --size "21:9" `
  --resolution "2K" `
  --timeout-seconds 1800
```

For RunningHub:

```powershell
python "<SKILL_DIR>\scripts\run_sync_product_generation.py" `
  --root "<ROOT>" `
  --template-analysis "<ROOT>\_aplus_creative_template_analysis.json" `
  --provider "gpt-rh" `
  --product "<ONE_PRODUCT_FOLDER_NAME>" `
  --size "21:9" `
  --resolution "2K" `
  --quality "<low|medium|high>" `
  --timeout-seconds 1800
```

Follow every synchronous state, process-tree cleanup, query-only recovery, prompt-review, overwrite-backup, and completion check in `references\v4-7-2-synchronous-recovery.md`.

Important reference rule for module-specific references:

- Every prompt filename must have a freshly rebuilt entry in `module_reference_images.json`; pass only that entry. Never fall back to a shared recursive image list.
- Section 1 may pass a product `LOGO` only when that exact current-SKU image was visually tagged `brand_logo` and selected by the current semantic contract; no filename-only logo discovery is allowed.
- Section 1 upload logs must retain the exact LOGO filename and upload position; the API prompt must not contain an `Attached Reference Image Map:` block.
- No-logo template instructions override the two Section 1 LOGO rules above. In no-logo mode, do not upload product `LOGO` images, do not add a Section 1 LOGO reference map, and strip any prompt line that says a LOGO reference is attached.
- If the final reference list submitted to the image API contains no model/on-body reference image, strip model-reference notes such as `Reference note: Use the attached model reference images...` before API submission. Never imply that model references are attached when the request only sends product, detail, background, or LOGO images.
- If the prompt disables reference images for a module, do not upload shared references, module-specific references, or LOGO references for that module. Save `mode: no_reference` and an empty `reference_images` list in `module_reference_upload_log.json`, and save the actual submitted prompt in `api_submitted_prompts`. For RunningHub only, because its image-to-image endpoint rejects empty `imageUrls`, upload one blank technical seed image and explicitly tell the model it is not a product/model/style/LOGO reference; log `runninghub_blank_technical_seed: true`.
- This no-model cleanup must scan the whole submitted prompt, not only one exact `Reference note` phrase. Remove lines that imply attached model references, same-person matching, model identity, face/hair/body matching, model styling, on-body fit, model poses, or other model-reference cues in `Reference note`, `Visual Direction`, `Product Information`, `Product Accuracy`, and similar blocks. Then add a clear instruction that no model/person reference images are attached and the module should not generate random people unless attached references explicitly include a person.
- When a module prompt needs a logo or brand mark, read the brand from the SPU folder's Excel workbook, treating it as `1-产品属性表.xlsx` even if the filename differs. Then look for matching image files in the root-level sibling folder `<ROOT>\LOGO` where the file stem equals the brand name. If a sibling brand logo is found, copy the selected logo into the SPU/product folder as `LOGO.<original extension>` and upload that product-local `LOGO` file to the image API. If no sibling brand logo is found, fall back to existing product-local LOGO images.
- Print the final reference image list for every generated module before submitting it to the API, and write the same per-module list to `<product>\_aplus_creative_work\module_reference_upload_log.json`.
- Write `module_reference_upload_log.json` immediately after planning each module so interrupted runs still keep the reference-image record.
- All sections in the same SPU should use distinct supplied model references where possible. Do not map the same AIGC/model file to multiple sections when enough unused model images exist. If a later section explicitly needs model/person/on-body references and unused model images run out, allow reuse of the clearest supplied model images so the module still receives at least two model references.
- Section 2 must include the brief's exact `model_identity_reference` plus a different confirmed front/three-quarter person reference when available. This identity anchor may repeat Section 1; identity consistency takes precedence over cross-section reference uniqueness.
- For any module needing model identity, use two or more model references when available, including at least one full-body or clear front/on-body reference when present. Avoid back-view-only model reference sets.
- Never submit a single back-view model reference by itself. If a planned reference list contains a back-view model image, add another supplied model image before API submission; if no companion model image exists, remove the lone back-view reference.
- Section 1 is stricter than other model sections: remove all back-view model references from Section 1, even when a companion model image exists.
- If Section 3's final model references overlap with Section 2's final model references, the first reference-planning pass must record `section3_human_fashion_action_required: true` and fail before generation when Section 3's `Layout task:` lacks a concrete human-authored action. The main agent then inspects the real contact sheet, both module compositions, and the selected uploads, appends the action inside `Layout task:`, and reruns reference planning until `section3_human_fashion_action_validated: true`. The script must never author, select, or rewrite that action, and a separate `Section 3 fashion action:` block is forbidden.
- If a module is marked as influencer / `网红图` and has generated influencer images, pass only generated influencer images plus product `LOGO` if the prompt explicitly needs a logo or brand mark.
- If a module is marked as `placeholder_blocks`, pass only product color/detail and brand references; never pass generated influencer images.
- If a module is marked as `influencer_background`, pass product color/detail and brand references only; never pass generated influencer images, model references, social UI, or color-block instructions.
- Non-influencer modules must use their module-specific references and obey `Model Identity Lock`; do not send all references to all modules.
- GPT-RH uploads local references through `https://www.runninghub.ai/openapi/v2/media/upload/binary`, submits module generation to `https://www.runninghub.ai/openapi/v2/rhart-image-g-2-official/image-to-image`, sends `imageUrls`, `aspectRatio`, `resolution`, and `quality`, and polls task status through `https://www.runninghub.ai/openapi/v2/query` with the returned `taskId`.
- GPT-RH supports at most 10 reference images per request. If a module maps more than 10 references, keep the first 10 after module-specific and LOGO planning.

## Output Locations

Influencer selfie images:

```text
<product>\_influencer_selfie_work\generated
```

A+ module images:

```text
<product>\_aplus_creative_work\generated_split
```

Injection summary:

```text
<ROOT>\_aplus_influencer_section_injection.json
```

Per-module API reference upload log:

```text
<product>\_aplus_creative_work\module_reference_upload_log.json
```

Final API-submitted prompt text, written immediately before each generation request:

```text
<product>\_aplus_creative_work\api_submitted_prompts\section-XX-*.txt
```

De-duplicated human review of those exact submitted prompts:

```text
<product>\_aplus_creative_work\api_prompt_review_deduplicated.md
```

Per-SKU provider recovery state:

```text
<product>\_aplus_creative_work\generation_state.json
```

Root synchronous analysis/generation status:

```text
<ROOT>\_aplus_sync_run_status.json
```

Rejected/QA-failed result backups created before `--overwrite`:

```text
<product>\_aplus_creative_work\generation_result_backups\<timestamp>_<module>\
```

Per-module API submit/status/download/error log:

```text
<product>\_aplus_creative_work\module_generation_api_log.jsonl
```

AIGC/model view tags:

```text
<product>\_aplus_creative_work\aigc_model_view_tags.json
```

Stitched long A+ image:

```text
<product>\_aplus_creative_work\<product>_Aplus_Long_<width>x<height>.png
<product>\_aplus_creative_work\generated_split\<product>_Aplus_Long_<width>x<height>.png
<ROOT>\输出结果\<product>_Aplus_Long_<width>x<height>.png
```

## Quality Gate

Before finishing, confirm:

- `_aplus_color_options_removal.json` reports zero errors, no `color_options` row remains, and every changed workbook has a backup.
- Preparation and module construction both used `scripts\excel_reader.py` in normal mode and read the complete physical worksheet rows despite stale worksheet dimension metadata.
- Every Excel Section N Headline/Copy appears only in Section N; empty Excel fields preserve Gemini-generated copy; ownership and cross-section duplicate validators passed before image generation.
- Every creative brief contains the exact five-line `Suggested Visual Baseline` block, the first four lines were written after direct visual inspection for that SKU, the fixed Style balance line is unchanged, and sibling baselines are not near-duplicates.
- No fixed text-area percentage, rigid text-safe block, or mandatory split layout was added as a workaround for missing rendered copy.
- Every module prompt and API-submitted prompt contains exactly one main-agent-authored `Text / Callouts:` block based on the layout plan, exact selected uploads, and existing prompt; it is supported, complementary, and non-conflicting.
- No API-submitted prompt contains `Attached Reference Image Map:` or raw reference filenames/paths; `module_reference_upload_log.json` contains the exact submitted files instead.
- Every module contains exactly one fully rewritten main-agent-authored `Layout task:` and one main-agent-authored `Layout execution:` based on direct inspection of that SKU's actual model/product images and exact selected uploads. Neither field retains a stock builder starter. They appear in canonical order immediately before `Product Accuracy:`; exactly one `Text / Callouts:` follows Product Accuracy content. Both layout fields use the marketplace-selected language, meet the designed-composition standard, differ materially from the SKU's other modules and sibling SKU equivalents, and pass `validate_manual_layout_prompts.py` before launch.
- Every section classified as `construction_detail`, `fabric_detail`, or `graphic_detail` passes the detail-geometry gate: no curved/arched/arcing crop, window, frame, panel, or mask; no crown-panel/nested arcs; no fan-shaped curved crop sequence; no fold-following, irregular, crescent, or organic-shaped window; and no lower-left-to-upper-right dominant diagonal material field with an overlapping curved crop. Non-detail sections are not subjected to this restriction.
- `api_prompt_review_deduplicated.md` exists and matches the exact files under `api_submitted_prompts`, with repeated exact blocks shown once.
- Any module regenerated with `--overwrite` has a timestamped `generation_result_backups` folder containing the prior final/raw/long files and a manifest.
- `generation_state.json` exists, writes every returned taskId before polling, contains no API key, and reaches a terminal product state; `_aplus_sync_run_status.json` records the same SKU as completed, failed, interrupted, or timed out.
- Every analysis and generation invocation contained exactly one SKU, ran synchronously, returned a terminal exit code, and had its execution cell closed before the next SKU started.
- A resumed module with `provider_task_id` logged query-only recovery and did not upload references or submit a second billed task.
- A timeout or interruption terminated the complete child process tree. If no `provider_task_id` existed, the attempt was recorded as unsubmitted; if one existed, the next run used query-only recovery.
- Template module count and module size.
- Which sections were detected as influencer sections.
- Which sections were detected as placeholder/color-block sections, and which were detected as no-influencer replacement backgrounds.
- `target_gender` for each product, `target_gender_source`, and whether all model/influencer people match the selected model identity's visible gender presentation. A differing attribute-table `target_customer` is advisory and must not block generation.
- `model_identity_reference` and whether A+ model modules resemble that reference.
- `aigc_model_view_tags.json` exists for products with AIGC/model images and labels front/side/back plus full-body/half-body status well enough for reference selection.
- Every tag was produced by the explicitly selected analysis model from one SKU contact-sheet request, every manifest ID is covered exactly once, and no tag has `source: heuristic`.
- Every `上身` image used as a model reference has `contains_person: true`; product-only flat lays are never counted toward the model-reference minimum.
- Every root-level SKU image tagged `contains_person: true` or `subject_type: model_person` has `usable_for_identity: false`, records `source_excluded_reason: sku_root_model_image`, is absent from creative-brief request images, influencer plans, `module_reference_images.json`, and API upload logs, and is rejected if present in a stale mapping.
- Every identity-sensitive Section 2 includes the brief `model_identity_reference` and a second front/three-quarter confirmed-person reference when available.
- Every Section 3 that reuses any Section 2 model reference has a main-agent-authored, image-adapted fashion action embedded in its `Layout task:` paragraph and reports `section3_human_fashion_action_validated: true`; no separate `Section 3 fashion action:`, safe-action library text, or legacy `Section 3 action adjustment:` block remains.
- Any usable model identity gender overrode a differing `target_customer` without changing the supplied person; attribute-table fallback was used only when model gender was unavailable.
- Influencer images generated per product and occasion.
- Affected A+ module prompts have influencer instructions and `module_reference_images.json`.
- Each module's `module_reference_images.json` entry contains only role-appropriate references.
- Each generated module prints and logs the exact reference images submitted to the API.
- The selected API supplier is recorded in `module_generation_api_log.jsonl`; GPT-RH logs include `quality`, defaulting to `medium`.
- Section 1 upload logs identify the LOGO filename and upload position when LOGO is allowed, API prompts contain no numbered filename map, and Section 1 pose directions are not exact duplicates across SPUs in the same batch.
- If the template disables LOGO exposure, Section 1 logs should show `logo_disabled_by_prompt: true`, `logo_requested_by_prompt: false`, no LOGO reference number, and no `LOGO.*` reference image.
- No module submits a lone model back-view image as its only model reference; back-view model references must be paired with another supplied model image or omitted.
- When a module submits no model/person/on-body reference images, its final API prompt contains no model-reference note, no same-person/model-identity language, and no Visual Direction/Product Information cues that would cause random model generation.
- Logo modules use the Excel brand name to resolve `<ROOT>\LOGO\<brand>.*`, copy the selected file into the SPU/product folder as `LOGO.<ext>`, and upload that product-local LOGO before falling back to existing product-local LOGO images.
- `module_generation_api_log.jsonl` exists for generated products and records submit, status, completion, download, and error events.
- Each completed product has a stitched long A+ image.
- Each completed product's stitched long A+ image is also copied into `<ROOT>\输出结果` with the filename unchanged.
- Final prompts, injected instructions, and every `Layout execution:` paragraph use the marketplace-selected module language and explicitly forbid unintended bilingual or Chinese/CJK rendered text for the supported German/English marketplace mappings.
- Final influencer A+ section uses generated influencer images as reference/layout material.
- Final explicit placeholder sections contain style-matched equal-size color blocks and no influencer people, selfies, UGC screenshots, or social UI.
- Final influencer replacement background sections contain a style-matched empty background/layout, with no people, no influencer selfies, no UGC screenshots, no social UI, no color blocks unless explicitly requested, and no visible copy when the template says no copy.
- Any failed influencer or A+ modules are recorded and skipped without stopping the batch.
- Multi-SPU generation used `run_sync_product_generation.py` once per SKU with exactly one `--product` value and no comma-separated, whole-root, loop-hidden, detached, or background generation command.
- Each synchronous command returned or timed out before the next began; no generator child process, yielded execution cell, supervisor, or worker remained after terminal artifact checks.
