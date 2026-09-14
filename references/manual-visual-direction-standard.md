# Main-Agent Visual Direction Standard

Read this file before manually rewriting any final `Layout task:` or `Layout execution:` field.

## Authorship boundary

- Treat every script- or analysis-model-produced `Layout task:` as a disposable draft that identifies module function only.
- Inspect the readable SKU contact sheet, product attributes, complete module prompt, neighboring module plans, and exact `module_reference_images.json` uploads.
- Have the main agent fully replace both layout fields. Do not ask GPT/Gemini, a script, a pose library, a category template, or a phrase-combination routine to write either final field.
- Keep the literal labels and order: `Layout task:` then `Layout execution:` then `Product Accuracy:`.

## Layout task standard

Write two to four compact sentences that define the design idea, not merely the module type. Include:

1. The composition purpose and primary focal relationship.
2. The exact product evidence that must remain readable.
3. One visual device derived from the real product or source scene, such as a brim arc, plaid diagonal, drawcord path, embroidery contour, shutter rhythm, court line, fleece sweep, hardware glint, or print fragment.
4. How this module differs from the other modules in the same SKU.

For a product-detail/fabric/graphic/construction section, select a straight-edged device instead: seam alignment, stitch rows, zipper track, rectangular label proportion, orthogonal panel boundary, straight brim-stitch spacing, or another visibly supported linear construction cue. Do not turn a physical curve, fold, hood edge, crown panel, or fabric sweep into the geometry of a crop, window, frame, mask, divider, or collage structure.

Do not retain stock starters such as:

- `Build a horizontal hero/brand banner...`
- `Create a model fit board with multiple model angles...`
- `Create a combined model-plus-flat-lay composition...`
- `Create a people-free detail/macro collage...`
- `Create a text-free, people-free, style-matched background module...`

Naming a hero, fit board, proof composition, macro collage, or replacement background is allowed only as part of a newly authored, product-specific design concept.

## Layout execution standard

Write one dense executable paragraph. Cover the following through concrete instructions rather than a fixed sentence template:

- hierarchy: identify the dominant subject and supporting evidence;
- unequal scale and placement: specify where subjects sit and how their scales differ;
- depth: specify overlap, crop relationships, planes, arcs, bands, panels, frames, shadows, or foreground/background transitions;
- visual connection: use a product- or scene-derived line, shape, texture, color, or material rhythm to connect zones;
- typography: place headline, copy, and callouts in named quiet areas and protect model faces and product graphics;
- reading path: state how the eye moves through the composition;
- product protection: keep critical silhouette, construction, print, embroidery, hardware, closures, front/back proof, and identity unobstructed;
- source cleanup: remove readable third-party storefront signs, location names, unrelated wordmarks, and unrelated logos, rebuilding those areas with unbranded scene texture.

Use exact observed product details. Do not invent measurements, functions, materials, colors, hardware, graphics, or views.

## Product-detail section geometry gate

Apply this gate only when the exact prompt is classified in `module_reference_requirements.json` as `construction_detail`, `fabric_detail`, or `graphic_detail`, or when the current template function unambiguously identifies a people-free product-detail/fabric/construction/macro section. Do not extend this gate to hero, model/fit, model-plus-flat-lay, lifestyle, influencer, placeholder, or background sections.

For an affected detail section:

- Build `Layout task:` and `Layout execution:` with straight-edged rectangular or orthogonal crops, frames, panels, dividers, labels, and windows.
- Do not use curved, arched, or arcing crops/windows/frames/panels/masks, including nested crown-panel arcs and smaller crops fanned around a curved macro.
- Do not use windows or masks that follow a garment fold, drape, fleece sweep, hood curve, seam curve, or product contour.
- Do not use irregular, crescent, organic, blob-shaped, freeform, or asymmetric curved viewport geometry.
- Do not make a material surface into a dominant diagonal field rising from lower-left to upper-right and overlap a curved hood or product crop into its upper edge. Reject the same construction when paraphrased or written in German.
- Physical product facts remain valid. A phrase such as `curved brim` may describe the real cap, but the brim curve must not become a curved crop, viewport, frame, nested arc, or collage boundary.

Before approval, run `scripts\validate_manual_layout_prompts.py`. The validator reads the dynamic module role and scans only the two layout fields for this detail-section geometry rule.

## Anti-template rules

- Do not use equal-width cards, three equal portraits, a default 50/50 photo-text split, or a regular thumbnail grid unless the source evidence makes that exact structure uniquely appropriate.
- Do not repeat the same dominant-subject side, panel geometry, arc direction, connector device, or reading path across all modules of one SKU.
- Do not copy or lightly paraphrase another SKU's layout. Re-inspect the current SKU and derive its motif from current evidence.
- Do not compensate for weak design with repeated `minimal`, `restrained`, `clean`, `generous white space`, or `premium` language.
- Do not describe a result by negation such as `not a basic catalog grid`; state the intended positive construction directly.
- Keep intentional empty replacement backgrounds genuinely empty, but design their architecture, light, depth, and future compositing zone specifically.

## Reference-quality characteristics

The July 2026 manual-layout test succeeded because its strongest modules used asymmetry, deliberate scale contrast, layered scene-derived geometry, product-specific connector lines, differentiated crop shapes, protected typography zones, and explicit reading order. Use those characteristics as a quality level, not as reusable wording or a fixed composition recipe.

If the user supplies a calibration folder of approved prompts and outputs, inspect it before authoring a new batch. This folder is optional and is not bundled with the skill. If none is supplied, apply the reference-quality characteristics above.

Do not copy its remaining generic `Layout task:` starters. Study the detailed `Layout execution:` passages and rendered spatial decisions, then write both fields anew for the current SKU.

## Final comparison gate

Before validation:

1. Read all modules of the current SKU side by side.
2. Confirm each module has a distinct compositional idea and spatial rhythm.
3. Compare the same section against sibling SKUs in the current root and rewrite near-duplicates.
4. Confirm every direction can be traced to the current SKU's images, product attributes, template function, or selected uploads.
5. Run `scripts\validate_manual_layout_prompts.py`; do not bypass a failure.
