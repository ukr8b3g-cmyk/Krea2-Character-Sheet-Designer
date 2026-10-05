"""Render the local atlas at the Designer's exact output size, without inference.

Adapted from Qwen Designer f6274130 layout_image.py. Krea keeps its existing
screen-left profiles and border-free sheet style. UI labels/baseline are not
image content. Pillow, NumPy and torch are supplied by ComfyUI, loaded lazily.
"""
from pathlib import Path

ATLAS_PATH = Path(__file__).resolve().parents[1] / 'web/assets/mannequin-atlas.png'
ATLAS_CROPS = {
    'face_front': (0, 75, 470, 560),
    'face_left': (1010, 35, 140, 205),
    'body_front': (495, 20, 350, 625),
    'body_left': (904, 20, 350, 625),
    'body_back': (55, 625, 350, 625),
    'hands': (415, 755, 445, 400),
    'feet': (860, 820, 380, 340),
}
MIRRORED_VIEWS = frozenset(('face_left', 'body_left'))


def render_layout_image(layout: dict):
    from PIL import Image, ImageOps

    width, height = layout['canvas']
    canvas = Image.new('RGB', (width, height), 'white')
    with Image.open(ATLAS_PATH) as source:
        atlas = source.convert('RGBA')
    for panel in layout['panels']:
        x, y, w, h = panel['rect']
        left, top = round(x * width), round(y * height)
        right, bottom = round((x + w) * width), round((y + h) * height)
        crop_x, crop_y, crop_w, crop_h = ATLAS_CROPS[panel['id']]
        artwork = atlas.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
        if panel['id'] in MIRRORED_VIEWS:
            artwork = ImageOps.mirror(artwork)
        artwork = ImageOps.contain(artwork, (max(1, right - left), max(1, bottom - top)), Image.Resampling.LANCZOS)
        position = (left + (right - left - artwork.width) // 2,
                    top + (bottom - top - artwork.height) // 2)
        canvas.paste(artwork, position, artwork)
    return canvas


def layout_image_tensor(layout: dict):
    import numpy as np
    import torch

    image = render_layout_image(layout)
    # Standard ComfyUI IMAGE: CPU float32, [batch, height, width, RGB], 0..1.
    # Normalize in place: a second full float32 image would add 12 bytes/pixel
    # of transient RAM at the user's uncapped manual dimensions.
    pixels = np.array(image, dtype=np.float32)
    pixels /= np.float32(255.0)
    return torch.from_numpy(pixels).unsqueeze(0)
