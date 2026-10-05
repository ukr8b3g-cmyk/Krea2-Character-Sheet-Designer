# Verification record

Date: 2026-10-05 UTC. The current distributed workflow is the user's latest attachment, preserved byte-for-byte. Static inspection and regression tests do not establish successful ComfyUI import, Queue execution or GPU generation.

## Current canonical attachment

File: [Krea2_Layout_Reference_Designer.json](../workflows/Krea2_Layout_Reference_Designer.json)

- Supplied filename: `Krea2_Layout_Reference_Designer_wf.json`
- Size: **77,129 bytes**
- SHA-256: `cd15879da50979467637eeae41dc5d94cec099b4cb5bfdf4a02f925f40ba8e14`
- **5 root nodes / 6 root links**, one subgraph with **12 inner nodes / 35 links**
- Root nodes: character `LoadImage`, `Krea2LayoutImageSheetDesigner`, license/provenance `Note`, subgraph instance, `SaveImage`
- No independent `PreviewImage` node and no external layout `LoadImage`
- Designer state: schema v1, five views (`face_front`, `face_left`, `body_front`, `body_left`, `body_back`), Manual **1696×768**, body_height **672**

Inspection of the attachment confirms layout image first and character identity second throughout positive and negative conditioning, VAE encoding and the pixel path. Designer prompt and dimensions cross the subgraph boundary into positive conditioning and EmptySD3LatentImage. The same EmptySD3 latent feeds KSampler and ModelPatch.target_latent.

### Saved settings: outer controls and inner values

The outer subgraph's saved named controls contain:

- Seed `1088049369132323`, steps **10**, CFG **1**
- VAE `qwen_image_vae.safetensors`
- CLIP `qwen3vl_4b_fp8_scaled.safetensors`
- UNET `krea2\krea2_turbo_int8_convrot.safetensors`
- LoRA `krea2\krea2_identity_edit_v1_2.safetensors`

The inner UNET and LoRA nodes retain `SELECT_KREA2_TURBO_INT8_CONVROT.safetensors` and `SELECT_IDENTITY_EDIT_V1_2.safetensors` as saved fallback widget values. Their model-selection inputs are supplied through the subgraph boundary. Read the promoted controls when describing this attachment; do not present the inner placeholders as its outer saved settings.

Other inner settings are fixed seed / euler / simple / denoise 1, LoRA strength 1.0, CLIP type `krea2`, grounding 768, `ref_boost=4`, `ref_boost_a=1`, and `fit`. The negative prompt is blank. The character LoadImage retains a supplied `.webp` filename; no character image or model bytes are included. Users must reselect their own files.

Serialized metadata records frontend `1.53.6` and mixed Core node version tags (`0.26.0` and `0.38.0`). These are saved provenance, not tested minimum-version requirements. The graph's old “sanitized” and “experimental” metadata is intentionally preserved with the rest of the attachment.

## Current publication checks

The current run checked the exact canonical file and the unchanged runtime node implementation:

- Python unittest: **58 passed, 1 skipped (59 tests)**; the skip is real torch, which is unavailable
- JavaScript state/artwork/profile suite: **81 passed**
- jsdom integration suite: **46 passed**, using the simulated host rather than real ComfyUI
- Canonical static graph validation: **passed**, including sparse promoted host sockets and positional widget values
- **14 workflow-specific tests** cover graph mutations, nested subgraph resolution and byte-integrity checks
- Flattening: **16 leaf nodes including the Note**, or **15 executable leaves**
- Python compileall and `git diff --check`: **passed**
- Canonical bytes match the supplied attachment; runtime node source files are unchanged

Current logs: [Python](../verification/python_tests.log), [JavaScript](../verification/javascript_tests.log), [jsdom](../verification/dom_tests.log), and [workflow validation](../verification/workflow_results.json). These files record this publication run. Historical counts below are retained only as background.

## Current verification limits

This publication run did not use real torch, a ComfyUI frontend or GPU execution. The torch-dependent test was explicitly skipped because torch is unavailable in the test environment. The following have **not** been verified for this exact attachment:

- Real ComfyUI startup/node registration, import, Pinia/Undo integration, graphToPrompt, serialization and Queue
- Real torch tensor execution, model loading or GPU inference
- Saved PNG dimensions or metadata, performance or VRAM
- Exact number/orientation of figures, face/outfit preservation, white-background quality or layout/identity separation

No model weights were downloaded or run. An unchanged graph hash proves preservation, not that a frontend can load it or that inference will succeed.

## Historical node and template validation

The following results belong to the earlier implementation and two-template distribution recorded before the latest attachment was selected. They describe prior node regression coverage; they must not be read as a GPU, UI-import or execution result for the current canonical file.

- Python unittest: **51 passed, 1 skipped (52 tests)**; the skip required real torch
- JavaScript state/artwork/profile suite: **81 passed, 0 skipped**
- jsdom integration suite: **46 passed, 0 skipped**, using actual UI modules with a mocked ComfyUI host and preview data
- Geometry/state sweep: **1,016 combinations**, all 127 nonempty view selections × Auto/Manual × schema v1/v2 × two reference-role variants, compared with the pinned H3 oracle; built-in mode additionally checked **508 combinations**
- Strict JSON fixtures: **62 cases**, applied to nodes and preview paths
- Real aiohttp loopback tests covered three preview routes, valid/error responses, strict request envelopes, bounded bodies, resolution validation, sanitized errors and idempotent registration
- Pillow/NumPy raster checks covered all **127 nonempty view selections**, opaque RGB, exact 512×256 output, and each of seven original crops after profile mirroring; extra sizes included 32×32, 3840×2176 and Auto
- Node adapter shape/normalization and renderer pixels were checked with an explicitly marked torch stub, not real torch
- Existing standard and legacy nodes retained their three-output contracts; state, rational geometry and web state controller matched Qwen `604ec0c6`

Historical UI checks included canonical-only state serialization, per-type endpoints, independent instances, Japanese/English changes, view/part controls, delayed/stale responses, invalid numeric drafts, Undo/Redo, five remove/re-add cycles, cleanup, rollback and raw-state recovery. jsdom does not render pixels or replicate ComfyUI Pinia.

The earlier workflow review compared ports, widget order and graph paths against Identity Edit `86f886dac23013d88996e3a2e99093ba44d322fb` and ComfyUI `5c460d8172fe30761ff67c0df3d5643bb74e0d70`. Its **16-node / 22-link** standard graph and **7-root-node / 7-root-link** layout graph were different files, now removed from distribution. Earlier claims about generating two workflows, sanitized placeholder names or a layout PreviewImage apply only to those historical files.

The earlier CPU-generated five-view layout PNG was visually inspected as two chest-up portraits and three full-body mannequins on white, with side profiles pointing left. This was an input image, not a Krea model result. Previously supplied character-sheet images and Qwen repository GPU reports do not validate the current attachment or Krea compiler.

A Chromium harness was not run successfully in the earlier environment because browser Unix sockets were restricted. It has not been run for this publication either.

## Reproduce

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/js/*.test.js
KREA2_JSDOM_PATH=/path/to/jsdom/lib/api.js node --test tests/dom/*.test.js
python tools/validate_workflows.py
python -m compileall -q krea2_character_sheet tools tests
sha256sum workflows/Krea2_Layout_Reference_Designer.json
```

ComfyUI supplies runtime dependencies. jsdom and Playwright are optional developer tools; neither is an execution dependency of the node. jsdom tests skip explicitly when the optional dependency is absent and fail when an explicitly supplied dependency path is invalid.

The supplied workflow is the source of truth; it must not be regenerated from the earlier templates. Test records under `verification/` must be read with their stated scope and date. `manifest.json` records distribution hashes and source pins.
