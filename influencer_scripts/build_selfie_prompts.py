from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FEMALE_PERSONAS = [
    "a distinctive adult Black streetwear influencer with deep brown skin, angular cheekbones, short sculpted curls, a tiny nose stud, natural skin texture, and a relaxed confident expression",
    "a distinctive adult Latina streetwear influencer with warm tan skin, long dark wavy hair, subtle glossy makeup, small hoop earrings, and a calm charismatic expression",
    "a distinctive adult mixed-race streetwear influencer with copper micro braids tied partly back, freckles, narrow sunglasses, and a spontaneous city-post attitude",
    "a distinctive adult South Asian streetwear influencer with warm brown skin, long glossy black hair in a loose low braid, tiny gold hoops, clean natural makeup, and an easy confident smile",
    "a distinctive adult North African streetwear influencer with olive skin, sharp brows, shoulder-length dark curls, layered silver necklaces, and calm camera-aware confidence",
    "a distinctive adult Caribbean streetwear influencer with dark skin, waist-length box braids, glossy lips, small hoop earrings, and expressive relaxed body language",
    "a distinctive adult white streetwear influencer with pale skin, short auburn shag haircut, faint freckles, no-heavy-makeup styling, and a slightly mischievous street-snapshot expression",
    "a distinctive adult East Asian female streetwear influencer with sharp cheekbones, short black bob hair, thin eyebrow slit, small silver ear cuffs, and an unforced confident expression",
    "a distinctive adult Latina streetwear influencer with tan skin, slick high ponytail, bold brows, small nose ring, and warm confident expression",
]

MALE_PERSONAS = [
    "a distinctive adult male streetwear influencer with medium brown skin, close-cropped hair, silver chain necklace, natural skin texture, and a relaxed urban posture",
    "a distinctive adult Black male streetwear influencer with deep skin, short twists, a trimmed goatee, small silver studs, and a relaxed skater-style presence",
    "a distinctive adult East Asian male streetwear influencer with medium-length black hair, slim rectangular glasses, clean skin texture, and understated city-casual confidence",
    "a distinctive adult Latino male streetwear influencer with tan skin, slick dark hair, bold brows, small nose ring, and warm confident expression",
    "a distinctive adult white male streetwear influencer with pale skin, shaggy auburn hair, faint freckles, clean-shaven face, and relaxed skater confidence",
    "a distinctive adult South Asian male streetwear influencer with warm brown skin, wavy black hair, tiny gold hoops, natural skin texture, and easy confident posture",
]

STYLING_BY_SUBJECT = {
    "pants": [
        "a fitted black rib tank, cropped charcoal zip hoodie worn open, black leather shoulder bag, chunky black skate shoes, and slim silver jewelry",
        "a washed black oversized graphic tee tucked slightly at the waist, dark bomber jacket, black-and-silver sneakers, compact crossbody bag, and narrow sunglasses",
        "a white baby tee layered under a cropped black work jacket, chunky loafers, small silver hoops, and a canvas tote",
        "a cropped navy varsity jacket, fitted white tank, silver chain belt detail, black platform sneakers, and a small nylon shoulder bag",
        "a slim charcoal mockneck top, oversized washed denim jacket, dark beanie, black leather tote, and worn skate shoes",
        "a cropped red long-sleeve top, black puffer vest, silver hoop earrings, chunky sneakers, and a compact camera bag",
    ],
    "default": [
        "washed black baggy cargo jeans, black-and-silver skate sneakers, a compact cobalt-blue crossbody bag, chunky silver bracelet, and narrow rectangular sunglasses",
        "a faded olive low-rise cargo maxi skirt, chunky black platform sandals, sheer burgundy ankle socks, a small metallic shoulder bag, and mismatched silver earrings",
        "very wide dark denim pants, worn leather belt, brown street shoes, small shoulder bag, and minimal silver rings",
        "long faded denim shorts, white socks, retro sneakers, slim black sunglasses, and a compact crossbody pouch",
        "stone-washed wide-leg jeans, black leather belt, red low-profile sneakers, silver ear cuffs, and a tiny black nylon shoulder bag",
        "charcoal parachute pants, cream skate sneakers, dark baseball cap, layered bracelets, and a faded canvas tote",
        "brown cargo mini skirt layered over bike shorts, black lace-up boots, oval sunglasses, and a burgundy shoulder bag",
        "deep indigo carpenter jeans, tan suede sneakers, narrow belt, simple rings, and a vintage camera strap bag",
    ],
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def stable_index(*parts: object, length: int) -> int:
    seed = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % length


def choose_unused(base_index: int, used: set[int], length: int) -> int:
    if len(used) >= length:
        return base_index
    for offset in range(length):
        candidate = (base_index + offset) % length
        if candidate not in used:
            used.add(candidate)
            return candidate
    return base_index


def subject_family(subject: str) -> str:
    s = subject.lower()
    if any(word in s for word in ["pant", "trouser", "jean", "sweatpant"]):
        return "pants"
    return "default"


def normalized_gender(plan: dict) -> str:
    explicit = str(plan.get("target_gender", "")).strip().lower()
    if explicit in {"women", "woman", "female"}:
        return "women"
    if explicit in {"men", "man", "male"}:
        return "men"
    if explicit in {"unisex", "ambiguous", "androgynous"}:
        return "unisex"
    raw = " ".join(
        str(value)
        for value in [
            plan.get("facts", {}).get("target_customer", ""),
            plan.get("facts", {}).get("product_type", ""),
        ]
    ).lower()
    if any(word in raw for word in ["women", "woman", "female", "girl", "ladies", "womens", "women's"]):
        return "women"
    if any(word in raw for word in ["men", "man", "male", "boy", "mens", "men's"]):
        return "men"
    if "unisex" in raw:
        return "unisex"
    return "unspecified"


def personas_for_gender(gender: str) -> tuple[list[str], str, str]:
    if gender == "women":
        return FEMALE_PERSONAS, "adult woman / female-presenting person", "Preserve the model-derived female/female-presenting gender; do not introduce a male or masculine-presenting person."
    if gender == "men":
        return MALE_PERSONAS, "adult man / male-presenting person", "Preserve the model-derived male/male-presenting gender; do not introduce a female or feminine-presenting person."
    return FEMALE_PERSONAS + MALE_PERSONAS, "visibly adult streetwear influencer consistent with the selected model identity", "Keep one intentional gender presentation consistent with the selected model identity; attribute-table customer gender is advisory only."


def image_role_phrase(subject: str) -> str:
    s = subject.lower()
    if any(word in s for word in ["pant", "trouser", "jean", "sweatpant"]):
        return "lower garment"
    if "skirt" in s:
        return "skirt"
    if "dress" in s:
        return "dress"
    return "upper garment"


def occasion_scene(occasion: str, reason: str) -> str:
    occ = occasion.lower()
    if "festival" in occ or "music" in occ:
        return "an outdoor city festival-adjacent street scene with palm-lined sidewalks, warm daylight, relaxed crowd energy, parked cars, and a casual pre-concert social atmosphere"
    if "school" in occ:
        return "a campus-like urban walkway with steps, stone or concrete building fronts, backpacks and students softly blurred in the background, natural daytime light"
    if "travel" in occ:
        return "a realistic travel moment near a train platform, station entrance, parking structure, or transit sidewalk, with suitcase or tote styling and casual movement"
    if "date" in occ or "night" in occ:
        return "a night street scene with storefront glow, traffic lights, city reflections, soft flash-like phone exposure, and a social evening atmosphere"
    if "christmas" in occ or "gift" in occ:
        return "a seasonal shopping street with red storefront accents, warm display-window light, gift-shopping energy, and subtle winter city mood"
    if "work" in occ:
        return "a polished city facade or cafe-adjacent sidewalk suitable for smart-casual workday streetwear, with clean architecture and understated daylight"
    if "city" in occ:
        return "a downtown sidewalk with storefronts, street poles, parked cars, pedestrians softly blurred behind, and an easy city-casual phone snapshot mood"
    return f"a believable urban streetwear location matching this background reference: {reason}"


def composition_for(occasion: str, subject: str) -> str:
    family = subject_family(subject)
    product_visibility = "pants fully visible from waistband to hem" if family == "pants" else f"{subject} fully visible and unobstructed"
    occ = occasion.lower()
    if "travel" in occ:
        action = "one hand loosely holding a small suitcase handle or travel tote, the other relaxed near the pocket"
    elif "festival" in occ or "music" in occ:
        action = "one hand holding sunglasses or a small drink, relaxed stance as if photographed before entering a venue"
    elif "school" in occ:
        action = "one shoulder carrying a casual backpack or tote, relaxed stationary campus posture"
    elif "date" in occ or "night" in occ:
        action = "one hand near a small evening bag, relaxed asymmetrical stance under city lights"
    elif "work" in occ:
        action = "one hand holding an iced coffee or phone, the other near the pocket or bag strap"
    else:
        action = "one hand lightly holding a phone or bag strap, relaxed asymmetrical street-style stance"
    return f"vertical 4:5 smartphone photograph, natural handheld selfie or friend-shot perspective, slightly imperfect casual framing, full-body or near full-body crop from head to shoes, {action}, {product_visibility}"


def build_prompt(_: str, plan: dict, occasion: dict) -> str:
    subject = plan.get("product_subject") or "product garment"
    role = image_role_phrase(subject)
    product_id = plan.get("product_id") or Path(plan.get("product_dir", "")).name or "product"
    occasion_name = occasion.get("name", "")
    background_name = Path(occasion.get("background_reference", "")).name
    gender = normalized_gender(plan)
    personas, gender_phrase, gender_negative = personas_for_gender(gender)
    persona_index = occasion.get("_persona_index")
    if persona_index is None:
        persona_index = stable_index(product_id, occasion_name, background_name, gender, "persona", length=len(personas))
    persona = personas[int(persona_index) % len(personas)]
    styling_options = STYLING_BY_SUBJECT[subject_family(subject)]
    styling_index = occasion.get("_styling_index")
    if styling_index is None:
        styling_index = stable_index(product_id, occasion_name, subject, background_name, "styling", length=len(styling_options))
    styling = styling_options[int(styling_index) % len(styling_options)]
    facts = plan.get("facts", {})
    brand = facts.get("brand", "")
    notes = plan.get("product_accuracy_notes") or "Preserve the product garment exactly as shown in Image 1."
    scene = occasion_scene(occasion_name, occasion.get("background_reason", ""))
    composition = composition_for(occasion_name, subject)

    return f"""Use case: photorealistic-natural. Asset type: Instagram influencer-style streetwear selfie / candid smartphone social post.

Input images: IMAGE 1 is the ONLY PRODUCT REFERENCE for the {role} and must be reproduced accurately; IMAGE 2 is the BACKGROUND, LIGHTING, LOCATION, AND CASUAL COMPOSITION REFERENCE ONLY for the "{occasion_name}" occasion.

Primary request: Create a natural-looking Instagram influencer candid street-style photo of a clearly {gender_phrase} wearing the exact {subject} from Image 1. Use {persona}. The person must match the product's target gender: {gender}. Do not use the opposite gender for this product. The person must not resemble any person in Image 2 or the influencer personas used for other products/occasions in the same batch.

Preserve the {role} exactly: {notes} Keep the garment's product type, color, fit, silhouette, graphics, trims, hardware, waistband/neckline/sleeves, logo placement, print placement, fabric behavior, and proportions accurate. Do not redesign, crop, recolor, simplify, or alter the {subject}. Image 1 controls the {subject} only.

Randomly restyle everything except the {subject}: pair it with {styling}. Accessories, hairstyle, color accents, and pose should feel casual and street-style, and should differ from other products/occasions in the same batch, but must not cover, hide, or visually distort the {subject}.

Occasion: {occasion_name}. The styling and body language should naturally communicate this occasion without using any overlay text.

Scene/backdrop: Use Image 2 only as reference for setting and atmosphere: {scene}. Keep the background believable and close in mood to Image 2, but do not copy exact people, outfits, logos, readable signage, brand text, or exact framing from Image 2.

Composition/framing: {composition}. The product should remain the visual focus while still feeling like a spontaneous social-media post.

Lighting/mood: natural available light matching Image 2, authentic phone-camera exposure, gentle realistic shadows, understated Instagram color processing, spontaneous and credible rather than polished studio campaign.

Materials/textures: realistic fabric drape and folds, accurate garment construction, natural skin texture, believable street surfaces, glass or wall textures where present, slightly worn shoes/accessories, subtle smartphone sharpness.

Constraints: IMAGE 1 controls the {subject} only; IMAGE 2 controls background mood only. Model must be visibly adult and must obey target_gender={gender}. {gender_negative} No generated captions, no overlay text, no watermark, no added brand logos, no QR code, no pricing, no promotional poster text.

Avoid: changing the {subject}'s garment category, color, sleeve/leg length, neckline or waistband, proportions, fit, graphics, hardware, side details, logo position, print placement, fabric texture, or distinctive construction; no excessive accessories hiding the garment, no studio backdrop, no overly polished campaign pose, no copied person from Image 2, no distorted hands, no duplicated limbs, no unrealistic anatomy, no malformed shoulders or legs, no unreadable foreground signage."""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build final selfie prompts, one per occasion.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--template", required=True, help="Loaded as style reference; examples are not copied into final prompts.")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    template = read_text(Path(args.template).expanduser().resolve())
    for plan_path in sorted(root.glob("*/_influencer_selfie_work/selfie_plan.json")):
        plan = json.loads(read_text(plan_path))
        prompt_dir = plan_path.parent / "prompts"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        product_id = plan.get("product_id") or plan_path.parents[1].name
        used_personas: set[int] = set()
        used_styling_by_family: dict[str, set[int]] = {}
        for item in plan.get("occasions", []):
            subject = plan.get("product_subject") or "product garment"
            gender = normalized_gender(plan)
            personas, _, _ = personas_for_gender(gender)
            occasion_name = item.get("name", "")
            background_name = Path(item.get("background_reference", "")).name
            persona_base = stable_index(product_id, occasion_name, background_name, gender, "persona", length=len(personas))
            item["_persona_index"] = choose_unused(persona_base, used_personas, len(personas))
            family = subject_family(subject)
            styling_options = STYLING_BY_SUBJECT[family]
            used_styles = used_styling_by_family.setdefault(family, set())
            styling_base = stable_index(product_id, occasion_name, subject, background_name, "styling", length=len(styling_options))
            item["_styling_index"] = choose_unused(styling_base, used_styles, len(styling_options))
            slug = f"occasion-{int(item['index']):02d}-{''.join(ch if ch.isalnum() else '-' for ch in item['name'].lower()).strip('-')}"
            prompt_path = prompt_dir / f"{slug}.txt"
            prompt_path.write_text(build_prompt(template, plan, item), encoding="utf-8")
            item["prompt_path"] = str(prompt_path)
            out_dir = plan_path.parent / "generated"
            item["output_path"] = str(out_dir / f"{slug}-4x5.png")
            item.pop("_persona_index", None)
            item.pop("_styling_index", None)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        print(plan_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
