# Source provenance and licensing

This is a derivative of the user's Designer code. It does not assign a new blanket license to upstream material.

## Designer

UI, state validation, rational geometry, artwork and regression oracle originate from:

- [H3 Character Sheet Designer, commit bf792c652a9f50e895409e49fce667fef0f73c25](https://github.com/ukr8b3g-cmyk/H3-Character-Sheet-Designer/tree/bf792c652a9f50e895409e49fce667fef0f73c25)
- [Qwen Image 2.1 Character Sheet Designer, commit 604ec0c6ea4046a3460e2c662d41f564870c15d8](https://github.com/ukr8b3g-cmyk/Qwen-Image-2.1-Character-Sheet-Designer/tree/604ec0c6ea4046a3460e2c662d41f564870c15d8)

The common state and geometry modules and web state controller are unchanged from the pinned Qwen baseline. UI and integration use a Krea-specific namespace, independent reference-role profiles and screen-left camera labels. The original 1254×1254 mannequin atlas is bundled unchanged: Git blob `35dd5fabbe138b7b181b89d55432a6e53d0e9c34`, SHA-256 `7213405d101a6ccc0152304680ab5a1b4f17ba456086f3469b41be1319b2b8f6`. The layout-image node also uses it for the generated layout reference. The face_left and body_left SVG viewports and corresponding generated image crops are mirrored at render time to match this package's screen-left prompts; the atlas bytes and crop rectangles remain unchanged. No user's character-reference bytes or generated character sheets are included.

The layout-image rendering approach is adapted from [Qwen Designer commit f627413028f2c2e05b75ed2b09a30947dea1fec6](https://github.com/ukr8b3g-cmyk/Qwen-Image-2.1-Character-Sheet-Designer/blob/f627413028f2c2e05b75ed2b09a30947dea1fec6/qwen_image21_character_sheet/layout_image.py), Git blob `041d9e12d122e21fe4b6bdd1b679e79cbbc20cfd`. Krea keeps screen-left profiles and omits black panel frames.

Preserve applicable upstream notices and licensing when redistributing. This repository does not assert that the H3/Qwen material is Apache-2.0.

## Identity Edit ancestry

Source: Conrad Locke / lbouaraba, [comfyui-krea2edit commit 86f886dac23013d88996e3a2e99093ba44d322fb](https://github.com/lbouaraba/comfyui-krea2edit/tree/86f886dac23013d88996e3a2e99093ba44d322fb). The historical source workflow has Git blob `a707d8d27cb8504f8a63ab38babe3855ac797c59`.

The full Apache-2.0 license remains at [tools/upstream/LICENSE-IdentityEdit](tools/upstream/LICENSE-IdentityEdit), and the supplied canonical workflow retains its collapsed license/provenance Note. Model weights have separate terms and are not bundled. The original Identity Edit nodes are not bundled as runtime code or modified here.

The earlier adaptation added Krea Designer nodes and a dedicated prompt compiler, connected dimensions/prompt, role-labelled references and built-in layout output. That history is preserved at [Krea Designer commit 17497a98309fc7193452307031635e464ec32d83](https://github.com/ukr8b3g-cmyk/Krea2-Character-Sheet-Designer/tree/17497a98309fc7193452307031635e464ec32d83). Earlier upstream/source workflow JSONs and alternative templates are no longer included in the current distribution.

## Canonical user-supplied workflow

On 2026-10-05, the user's latest `Krea2_Layout_Reference_Designer_wf.json` was selected as the only distributed template, at [workflows/Krea2_Layout_Reference_Designer.json](workflows/Krea2_Layout_Reference_Designer.json). Its contents are preserved byte-for-byte; only the distribution filename changes.

- File size: 77,129 bytes
- SHA-256: `cd15879da50979467637eeae41dc5d94cec099b4cb5bfdf4a02f925f40ba8e14`
- Five root nodes / six root links, with one subgraph containing 12 nodes / 35 links
- `Krea2LayoutImageSheetDesigner` supplies layout image 1; one required character image supplies reference image 2

The supplied graph retains its saved image filename, model paths, widget values, positions, IDs, links, metadata and embedded notices. Earlier wording inside its Note and `extra` metadata, including “sanitized filenames” and “experimental”, records the graph's history; it is not a claim that this publication sanitized or regenerated the latest attachment. Users must select their own installed model files and character image before running it.

The earlier static schema review used [ComfyUI commit 5c460d8172fe30761ff67c0df3d5643bb74e0d70](https://github.com/Comfy-Org/ComfyUI/tree/5c460d8172fe30761ff67c0df3d5643bb74e0d70). The supplied graph retains its SaveImage IMAGE output and EmptySD3LatentImage contract. This provenance does not establish execution or compatibility with every installed ComfyUI/frontend version; see [verification scope](docs/VERIFICATION.md).
