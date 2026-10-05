# Verification record

Date: 2026-10-05 UTC. Scope: deterministic compiler, actual CPU layout-image pixels, simulated UI, HTTP preview, and static workflow graphs. No models or GPU were used.

## Passed

- Python unittest: **51 passed, 1 skipped (52 tests)**; the skipped check requires real torch, which is not installed in this test environment
- Geometry/state sweep: **1,016 combinations**, covering all 127 nonempty view selections × Auto/Manual × schema v1/v2 × both reference-role variants; compared with the pinned H3 oracle. The new built-in mode additionally preserves state/geometry in **508 combinations** (127 selections × Auto/Manual × schema v1/v2)
- Strict JSON fixtures: **62 cases**, applied to both nodes and preview paths
- JavaScript state/artwork/profile suite: **81 passed, 0 skipped**
- jsdom integration suite: **46 passed, 0 skipped** for all three node types; actual UI modules with mocked ComfyUI host and preview data
- Real aiohttp loopback tests: all three preview routes, valid/error responses, strict request envelope, bounded body, runtime resolution validation, sanitized errors, idempotent registration
- New-node defaults: exactly five views, v1, Manual 1696×768, body_height 672, no changes to imported state
- Original bitmap: SHA-256 and all seven crop rectangles match the existing H3 atlas; screen-left profiles are mirrored by the Krea-specific render stylesheet and by the new backend image renderer
- Actual Pillow/NumPy raster checks: **all 127 nonempty view selections**, opaque RGB, exact 512×256 canvas, no artwork outside selected panels; each of seven original crops compared pixel-for-pixel after the required profile mirroring
- Additional image sizes: 32×32, 3840×2176 and Auto; no hidden downscaling
- New node adapter: first three ports preserved, fourth IMAGE port; float32 normalized BHWC array and exact renderer pixels verified with an explicitly marked torch stub, not represented as real torch or ComfyUI execution
- Standard and legacy external-layout nodes retain their original three-output contract and prompt behavior; legacy type remains registered/deprecated
- Common state, rational geometry and web state controller: byte-identical to pinned Qwen `604ec0c6`
- Workflow generation is reproducible and both resulting JSONs match `tools/build_workflows.py`

UI checks include canonical-only serialization, correct per-type endpoint, two independent instances, Japanese/English changes, all view/part controls, delayed/stale preview responses, invalid numeric drafts, source-driven Undo/Redo, five remove/re-add cycles, cleanup, partial insertion rollback and raw-state recovery. jsdom does not render pixels or replicate ComfyUI Pinia behavior.

## Workflow review

An independent source/AST review compared ports, widget order and graph paths with Identity Edit `86f886dac23013d88996e3a2e99093ba44d322fb` and supplied ComfyUI schema source `5c460d8172fe30761ff67c0df3d5643bb74e0d70`.

- Standard: **16 nodes / 22 links**, one character reference
- New experimental: **7 root nodes / 7 root links**, one supplied subgraph with **12 inner nodes / 35 links**, **18 flattened executable leaf nodes**; generated layout first and identity second in every positive/negative conditioning, VAE and pixel path
- Standard JSON is byte-identical to the original published file: SHA-256 `1d36950416ebbaa9f6db677209a1ee1c4474ab8fb6643830664a3cbe94606a12`
- External layout LoadImage removed from the new template; one character LoadImage and a PreviewImage of the actual layout output remain
- Promoted seed, steps, CFG, VAE, CLIP, diffusion-model and LoRA controls retained; supplied int8-convrot model basename retained, private/machine-specific paths removed
- Recursive boundary validation and static flattening check the paths; mutation tests reject swapped references, missing negative B links and stale boundary links, and cover nested subgraph resolution
- Designer STRING goes to the converted positive prompt socket; INT outputs drive EmptySD3 dimensions
- The same EmptySD3 latent feeds KSampler and ModelPatch.target_latent
- Retained author edges, active modes, topological order, reciprocal typed links, unique UUIDs, model/image placeholders and embedded license checked
- SaveImage's IMAGE output is preserved as declared by the pinned Core source

Static review does not establish that an installed frontend will accept or serialize the graph exactly as expected. The workflow source's schema version cannot guarantee compatibility with arbitrary ComfyUI versions.

## Not run / not claimed

- Real torch tensor execution (one explicit skip); ComfyUI provides torch at runtime
- Real ComfyUI startup and node registration, workflow import, Pinia/Undo integration, graphToPrompt and Queue
- GPU inference, model loading, saved PNG dimensions or metadata, performance and VRAM
- New compiler's visual output quality, exact number/orientation of figures, face/outfit preservation or white-background quality
- Experimental two-image layout/identity separation
- Chromium pixel/interactive harness for this new package; environment launch attempts failed before tests because browser Unix sockets are restricted

The new 5-view layout PNG was visually inspected: two large chest-up portraits and three full-body mannequins on white, with both side profiles pointing left. This is an actual CPU-generated input image, not a Krea model result. No black frames were ported from the later Qwen variant. Qwen repository GPU reports are not verification of this Krea implementation.

The previously supplied five-view output images were inspected to guide the initial size and framing. They do not validate this new compiler or experimental two-image version. They are not distributed in this repository.

## Reproduce

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/js/*.test.js
KREA2_JSDOM_PATH=/path/to/jsdom/lib/api.js node --test tests/dom/*.test.js
python tools/build_workflows.py
python tools/validate_workflows.py
python -m compileall -q krea2_character_sheet tools tests
```

ComfyUI supplies aiohttp for runtime preview. jsdom and Playwright are optional developer tools; neither is an execution dependency of the node. jsdom tests skip explicitly when no optional dependency is present and fail when an explicitly supplied dependency path is invalid.

Test logs and workflow hashes are in `verification/`; absolute execution paths in logs are normalized. `manifest.json` records distribution hashes and source pins.
