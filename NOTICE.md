# Source provenance and licensing

This is a derivative of the user's Designer code. It does not assign a new blanket license to upstream material.

## Designer

UI, state validation, rational geometry, artwork and regression oracle originate from:

- H3 Character Sheet Designer, commit `bf792c652a9f50e895409e49fce667fef0f73c25`: https://github.com/ukr8b3g-cmyk/H3-Character-Sheet-Designer
- Qwen Image 2.1 Character Sheet Designer, commit `604ec0c6ea4046a3460e2c662d41f564870c15d8`: https://github.com/ukr8b3g-cmyk/Qwen-Image-2.1-Character-Sheet-Designer

The common state and geometry modules and web state controller are unchanged from the pinned Qwen baseline. UI and integration use a Krea-specific namespace, two reference-role profiles and screen-left camera labels. The original 1254×1254 mannequin atlas is bundled unchanged: Git blob `35dd5fabbe138b7b181b89d55432a6e53d0e9c34`, SHA-256 `7213405d101a6ccc0152304680ab5a1b4f17ba456086f3469b41be1319b2b8f6`. It is UI-only. The face_left and body_left SVG viewports are mirrored at render time to match this package’s screen-left prompts; the atlas bytes and crop rectangles remain unchanged. No user's character-reference bytes or generated character sheets are included.

Preserve applicable upstream notices and licensing when redistributing. This repository does not assert that the H3/Qwen material is Apache-2.0.

## Identity Edit workflow

Source: Conrad Locke / lbouaraba, `comfyui-krea2edit`, commit `86f886dac23013d88996e3a2e99093ba44d322fb`:

https://github.com/lbouaraba/comfyui-krea2edit/tree/86f886dac23013d88996e3a2e99093ba44d322fb

The unmodified workflow is included at `tools/upstream/krea2_identity_edit.json` (Git blob `a707d8d27cb8504f8a63ab38babe3855ac797c59`) with its full Apache-2.0 license at `tools/upstream/LICENSE-IdentityEdit`. The license is also embedded in each derivative workflow's collapsed Note. Model weights have separate terms and are not bundled.

Modified 2026-10-05: new Krea Designer node and dedicated prompt compiler, connected dimensions/prompt, single-reference default and role-labelled two-reference experimental variant, fixed seed, placeholders and explanatory notes. The original Identity Edit nodes themselves are not bundled as runtime code or modified.

Static schema review also used ComfyUI sources at `5c460d8172fe30761ff67c0df3d5643bb74e0d70`. The supplied graph preserves that source's SaveImage IMAGE output and EmptySD3LatentImage contract; it is not a guarantee for every installed ComfyUI version.
