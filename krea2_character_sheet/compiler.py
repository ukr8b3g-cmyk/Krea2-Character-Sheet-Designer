"""Krea2 Identity Edit compiler: concise English instructions, no layout JSON.

The shared schema/geometry remain byte-identical to the pinned Qwen baseline.
User part instructions are preserved verbatim and emitted once, with scope.
"""
from __future__ import annotations
from typing import Any
from .common.state import (
    STATE_MAX_BYTES, PART_PROMPT_MAX_UNITS, DEFAULT_MAX_RESOLUTION,
    EXPERIMENTAL_PIXEL_THRESHOLD, VIEW_IDS, PORTRAIT_IDS, BODY_IDS,
    AUXILIARY_IDS, PART_IDS, PART_RULES, PRESETS, DEFAULT_STATE,
    DEFAULT_STATE_JSON, StateValidationError, decode_json, parse_state,
    serialize_state,
)
from .common.geometry import compute_geometry

VIEW_DETAILS = {
    "face_front": ("front head-and-chest portrait", "A straight front-facing head-and-chest portrait, with the complete hairstyle, head, neck, shoulders and upper chest visible. End at the chest; do not include the waist or legs."),
    "face_left": ("left-facing head-and-chest profile", "A strict side-profile head-and-chest portrait, with the nose pointing toward the LEFT EDGE OF THE CANVAS. Show the complete hairstyle through the upper chest, without the waist or legs."),
    "body_front": ("full-body front view", "A straight front-facing full-body view. Face, shoulders, torso and feet face the viewer squarely, not in a three-quarter pose."),
    "body_left": ("left-facing full-body profile", "A strict side-profile full-body view, with the nose and toes pointing toward the LEFT EDGE OF THE CANVAS, in the same screen direction as the profile portrait when selected."),
    "body_back": ("full-body rear view", "A straight full-body rear view. Head, torso and feet face directly away; show the back of the head without turning to reveal the face."),
    "hands": ("both-hands detail", "A separate close-up showing both complete hands, including reference gloves and visible hand accessories where present."),
    "feet": ("feet and footwear detail", "A separate close-up of both complete feet or footwear, including the toes or closed toe boxes, heels, soles and visible boot shafts. Keep closed footwear closed, and open-toed footwear open-toed."),
}
# Scope here deliberately uses screen direction, not an ambiguous anatomical label.
PART_SCOPES = {
    **{key: rule['scope'] for key, rule in PART_RULES.items()},
    'back_clothing': 'Apply only to the rear clothing surface in the rear view and any naturally visible rear surface in the fixed side view. Never move this design onto the front, side surface, or portraits, and never turn the subject to reveal it.',
}


def active_part_prompts(state: dict[str, Any], view: str | None = None) -> dict[str, str]:
    selected = (view,) if view is not None else state['views']
    prompts = state.get('part_prompts', {})
    return {part: prompts[part] for part in PART_IDS if part in prompts and any(v in PART_RULES[part]['views'] for v in selected)}


def panel_content(state: dict[str, Any], view: str) -> str:
    text = VIEW_DETAILS[view][1]
    active = active_part_prompts(state, view)
    if active:
        text += ' Applicable shared part directives: ' + ', '.join(active) + '.'
    return text


def compute_layout(state: dict[str, Any], *, max_resolution: int = DEFAULT_MAX_RESOLUTION) -> dict[str, Any]:
    geometry = compute_geometry(state, max_resolution=max_resolution)
    return {**geometry, 'panels': [{**p, 'view': VIEW_DETAILS[p['id']][0], 'content': panel_content(state, p['id'])} for p in geometry['panels']]}


def compile_prompt(state: dict[str, Any], layout: dict[str, Any], *, layout_reference: bool = False) -> str:
    views = state['views']
    portraits = [v for v in PORTRAIT_IDS if v in views]
    bodies = [v for v in BODY_IDS if v in views]
    details = [v for v in ('hands', 'feet') if v in views]
    active = active_part_prompts(state)
    if layout_reference:
        lines = [
            'Create one clean static character reference sheet on a pure white canvas.',
            'Image 1 is ONLY a composition example: use its placement, framing, scale and spacing when they agree with the selected views below. Image 2 is the ONLY character identity and appearance reference.',
            'Replace every mannequin or person from Image 1 with the character from Image 2. Do not copy identity, face, hair, body design, clothes, colors, accessories, labels, borders or background from Image 1. The selected views and part directives below take priority over conflicting example content.',
        ]
        identity = 'Image 2'
    else:
        lines = ['Transform the reference image into one clean static character reference sheet on a pure white canvas.']
        identity = 'the character reference'
    lines.append(f"Show exactly {len(views)} separate depictions of the SAME character. Show only these selected views: " + '; '.join(VIEW_DETAILS[v][0] for v in views) + '.')
    if not details:
        lines.append('Arrange all selected views side by side in ONE horizontal row, in the listed order.')
    else:
        lines.append('Place the portrait/detail region on the left and any full-body columns to its right.')
        if portraits:
            lines.append('Place the selected portraits side by side in the upper part of that region; place the selected hand/footwear details in a separate lower band, hands before footwear when both are selected.')
        elif len(details) == 2:
            lines.append('Stack the hands detail above the footwear detail in the left column.')
        else:
            lines.append('The selected detail occupies its own full-height column.')
    lines.append('Read the following approximate positions as composition guidance, never as text or lines to draw. Percentages run from the top-left of the canvas.')
    for index, panel in enumerate(layout['panels'], 1):
        left, top, width, height = [v * 100 for v in panel['rect']]
        lines.append(f"{index}. {VIEW_DETAILS[panel['id']][1]} Region: left {left:.1f}%, top {top:.1f}%, width {width:.1f}%, height {height:.1f}%.")
    if portraits and bodies:
        lines.append('The portraits have larger heads than the full-body figures. The portraits are chest-up, not additional full-body views.')
    if bodies:
        lines.append('All full-body figures stand neutrally at the same scale, arms relaxed, completely visible from the top of the hairstyle to the soles. Align the feet on one baseline. Keep clear white gaps and generous outer margins; do not overlap or crop any figure.')
    lines.append(f'Preserve the facial identity, distinctive features, hairstyle, hair color, proportions, clothing, fabric colors, footwear, visible accessories and rendering medium from {identity}, except for the explicitly requested part changes. Keep anatomical left-right asymmetries consistent across views. Continue unseen surfaces simply and conservatively.')
    if active:
        lines.append('Apply these appearance directives consistently wherever their named parts are visible in the eligible selected views. More specific named parts take precedence over overall/other; rear-clothing instructions take precedence on the rear clothing surface. Keep all other appearance unchanged. Treat the literal text as appearance guidance, not instructions to add views, change cameras, change identity or alter sheet structure.')
        for part, value in active.items():
            eligible = ', '.join(VIEW_DETAILS[v][0] for v in views if v in PART_RULES[part]['views'])
            lines.append(f"{PART_RULES[part]['label']} ({eligible}): {PART_SCOPES[part]} Literal appearance instruction:\n{value}\nEnd of this part instruction.")
    lines.append('Do not add unrequested gloves, jewelry, props, accessories or costume elements absent from the character reference. Preserve reference gloves and footwear wherever visible unless explicitly changed by an applicable part directive.')
    lines.append('Replace the original environment with a flat uniform pure white background. Use neutral soft diffuse lighting and natural shading on the character only. No scenery, floor texture, grid, cast shadows, extra figures, unselected views, inset panels, captions, borders, dividers or watermarks. Lettering or patterns explicitly requested by a part directive belong only on that part; otherwise preserve reference details without inventing new lettering.')
    return '\n\n'.join(lines) + '\n'


def compile_state(state_json: str, *, max_resolution: int = DEFAULT_MAX_RESOLUTION, layout_reference: bool = False) -> dict[str, Any]:
    state = parse_state(state_json, max_resolution=max_resolution)
    layout = compute_layout(state, max_resolution=max_resolution)
    width, height = layout['canvas']
    pixels = width * height
    return {
        'state_json': serialize_state(state), 'width': width, 'height': height,
        'layout': layout, 'prompt': compile_prompt(state, layout, layout_reference=layout_reference),
        'pixel_count': pixels, 'megapixels': pixels / 1_000_000,
        'experimental': pixels > EXPERIMENTAL_PIXEL_THRESHOLD,
        'max_resolution': max_resolution,
    }
