"""Prompt templates, built from the scene bible so continuity is enforced
by construction. Every prompt pulls the shared palette, style and product
identity out of the bible, which is why brand identity survives fan-out.
"""
from __future__ import annotations

from .bible import Brand, Market, SceneBible, Shot


def _palette(brand: Brand) -> str:
    return ", ".join(brand.palette) if brand.palette else "a cohesive brand palette"


def concept_prompt(bible: SceneBible) -> str:
    b = bible.brand
    markets = ", ".join(f"{m.city} ({m.country})" for m in bible.markets)
    return (
        f"You are a creative director. Using the attached product photos and the "
        f"details below, write ONE tight creative concept for a {bible.duration_s:.0f}-second "
        f"video ad that will be localized to these markets: {markets}.\n\n"
        f"Product: {b.product_name} ({b.category})\n"
        f"Brief: {bible.brief}\n"
        f"Visual style: {b.style}\n"
        f"Palette: {_palette(b)}\n\n"
        f"Return plain text with exactly these sections and nothing else:\n"
        f"TAGLINE: <a short, punchy line>\n"
        f"CONCEPT: <2-3 sentences describing the single hero idea and mood>\n"
        f"HERO MOMENT: <the one signature visual beat the ad builds to>\n"
        f"WHY IT TRAVELS: <one sentence on why this idea works across all the markets>\n"
        f"Keep it concrete and shootable. Do not mention specific people or stereotypes."
    )


def concept_edit_prompt(current: str, instruction: str) -> str:
    return (
        f"Here is the current creative concept:\n\n{current}\n\n"
        f"Revise it based on this instruction: \"{instruction}\".\n"
        f"Keep the same four sections (TAGLINE, CONCEPT, HERO MOMENT, WHY IT TRAVELS) "
        f"and the same plain-text format. Change only what the instruction asks for. "
        f"Return the full revised concept, nothing else."
    )


def _concept_line(bible: SceneBible) -> str:
    """A compact concept reminder to fold into image prompts for continuity."""
    if not bible.concept:
        return ""
    first = bible.concept.strip().splitlines()
    summary = " ".join(line for line in first if line.strip())[:400]
    return f" Creative concept to honour: {summary}."


def brand_sheet_prompt(brand: Brand) -> str:
    return (
        f"Create a brand reference sheet for {brand.product_name} ({brand.category}). "
        f"Show the product from 3 angles on a clean neutral background, a colour palette "
        f"strip using {_palette(brand)}, and a style swatch for \"{brand.style}\". "
        f"Match any attached product photos exactly: shape, label, colours. "
        f"16:9, studio lighting, no text overlays."
    )


def shotlist_prompt(bible: SceneBible) -> str:
    """Ask the model to break the concept into timed scenes across the duration."""
    roles = "\n".join(f'  - {s.id} ({s.role}): {s.description}' for s in bible.shots)
    return (
        f"Break this {bible.duration_s:.0f}-second video ad into exactly "
        f"{len(bible.shots)} sequential timed scenes that together cover 0s to "
        f"{bible.duration_s:.0f}s with no gaps or overlaps.\n\n"
        f"Creative concept:\n{bible.concept}\n\n"
        f"Use these shot roles in order:\n{roles}\n\n"
        f"For each scene give a concrete, shootable visual description that fits its "
        f"time slot and advances the concept, building to the hero moment.\n"
        f"Return STRICT JSON only: a list of objects "
        f'[{{"id": "s1", "start_s": 0.0, "end_s": 1.2, "description": "..."}}, ...] '
        f"with ids matching the roles above, ascending non-overlapping times starting "
        f"at 0.0 and ending at {bible.duration_s:.1f}. No prose, no markdown."
    )


def timeline_beats(bible: SceneBible) -> str:
    """Compact timed-beat string for video prompts, e.g.
    '0.0-1.2s establishing: …; 1.2-2.4s product: …'."""
    parts = []
    for s in bible.shots:
        if s.end_s > s.start_s:
            parts.append(f"{s.start_s:.1f}-{s.end_s:.1f}s {s.role}: {s.description}")
    return "; ".join(parts)


def master_shot_prompt(bible: SceneBible, shot: Shot, index: int) -> str:
    b = bible.brand
    timing = (
        f"This scene runs {shot.start_s:.1f}s-{shot.end_s:.1f}s of the {bible.duration_s:.0f}s ad. "
        if shot.end_s > shot.start_s else ""
    )
    return (
        f"Storyboard frame {index}/{len(bible.shots)} for a {bible.duration_s:.0f}s ad: "
        f"{shot.role}. {timing}{shot.description}. "
        f"Product: {b.product_name} ({b.category}). "
        f"Visual style: {b.style}. Palette: {_palette(b)}. "
        f"{bible.aspect}, cinematic, no text overlays. "
        f"The product must match the attached reference exactly."
        f"{_concept_line(bible)}"
    )


def localized_board_prompt(bible: SceneBible, shot: Shot, market: Market) -> str:
    return (
        f"Re-stage this exact shot for {market.city}, {market.country}. "
        f"Keep the camera angle, composition, product placement and palette identical. "
        f"Change only the setting and props to: {', '.join(market.cultural_cues)}. "
        f"Any visible signage must be in {market.language} ({market.script} script). "
        f"Do not alter the product itself."
    )


def hero_clip_prompt(bible: SceneBible, market: Market) -> str:
    b = bible.brand
    beats = timeline_beats(bible)
    beats_line = f" Follow this timed beat sheet across the clip: {beats}." if beats else ""
    return (
        f"Animate a {bible.duration_s:.0f}s premium ad sequence for {b.product_name} "
        f"from this storyboard frame. Setting: {market.city}, {market.country}. "
        f"Style: {b.style}. Smooth, physically plausible, cinematic motion; "
        f"a satisfying hero moment with realistic light and texture.{beats_line} "
        f"Keep the product identical to the reference. {bible.aspect}, no text overlays."
    )


def regional_track_prompt(bible: SceneBible, market: Market) -> str:
    lift_at = round(bible.duration_s * 0.6, 1)
    return (
        f"{market.music_style}, {bible.bpm} BPM, about {bible.duration_s:.0f} seconds, "
        f"energetic but premium, builds to a small lift around {lift_at}s (the hero moment), "
        f"clean ending. Instrumental only, no vocals."
    )


def master_edit_prompt(bible: SceneBible, market: Market, instruction: str) -> str:
    return (
        f"Apply this change to the ad: \"{instruction}\". "
        f"Preserve all {market.city}-specific localization (setting, signage, props) "
        f"and keep the product identical. Change nothing else. "
        f"{bible.duration_s:.0f}s, {bible.aspect}."
    )


def brand_judge_prompt(brand: Brand) -> str:
    return (
        f"You are a strict brand-consistency checker for {brand.product_name}. "
        f"Compare the generated image against the reference product photos. "
        f"Score 0-100 how faithfully the product's shape, label and colours are preserved, "
        f"and how well it matches the palette {_palette(brand)} and style \"{brand.style}\". "
        f"Respond with strict JSON only: {{\"score\": <int 0-100>, \"issues\": [<short strings>]}}."
    )
