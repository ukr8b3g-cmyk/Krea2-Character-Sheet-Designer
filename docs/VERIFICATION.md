# Verification record

Date: 2026-10-05 UTC. Scope: deterministic compiler, simulated UI, HTTP preview, and static workflow graphs. No models or GPU were used.

## Passed

- Python unittest: **36 tests**
- Geometry/state sweep: **1,016 combinations**, covering all 127 nonempty view selections × Auto/Manual × schema v1/v2 × both reference-role variants; compared with the pinned H3 oracle
- Strict JSON fixtures: **62 cases**, applied to both nodes and preview paths
- JavaScript state/artwork/profile suite: **81 passed, 0 skipped**
- jsdom integration suite: **32 passed, 0 skipped** for both node types; actual UI modules with mocked ComfyUI host and preview data
- Real aiohttp loopback tests: both preview modes, valid/error responses, strict request envelope, bounded body, runtime resolution validation, sanitized errors, idempotent registration
- New-node defaults: exactly five views, v1, Manual 1696×768, body_height 672, no changes to imported state
- Original bitmap: SHA-256 and all seven crop rectangles match the existing H3 atlas; screen-left profiles are mirrored only by the Krea-specific render stylesheet
- Common state, rational geometry and web state controller: byte-identical to pinned Qwen `604ec0c6`
- Workflow generation is reproducible and both resulting JSONs match `tools/build_workflows.py`

UI checks include canonical-only serialization, correct per-type endpoint, two independent instances, Japanese/English changes, all view/part controls, delayed/stale preview responses, invalid numeric drafts, source-driven Undo/Redo, five remove/re-add cycles, cleanup, partial insertion rollback and raw-state recovery. jsdom does not render pixels or replicate ComfyUI Pinia behavior.

## Workflow review

An independent source/AST review compared ports, widget order and graph paths with Identity Edit `86f886dac23013d88996e3a2e99093ba44d322fb` and supplied ComfyUI schema source `5c460d8172fe30761ff67c0df3d5643bb74e0d70`.

- Standard: **16 nodes / 22 links**, one character reference
- Experimental: **18 nodes / 28 links**, layout first and identity second in every conditioning, VAE and pixel path
- Designer STRING goes to the converted positive prompt socket; INT outputs drive EmptySD3 dimensions
- The same EmptySD3 latent feeds KSampler and ModelPatch.target_latent
- Retained author edges, active modes, topological order, reciprocal typed links, unique UUIDs, model/image placeholders and embedded license checked
- SaveImage's IMAGE output is preserved as declared by the pinned Core source

Static review does not establish that an installed frontend will accept or serialize the graph exactly as expected. The workflow source's schema version cannot guarantee compatibility with arbitrary ComfyUI versions.

## Not run / not claimed

- Real ComfyUI startup and node registration, workflow import, Pinia/Undo integration, graphToPrompt and Queue
- GPU inference, model loading, saved PNG dimensions or metadata, performance and VRAM
- New compiler's visual output quality, exact number/orientation of figures, face/outfit preservation or white-background quality
- Experimental two-image layout/identity separation
- Chromium pixel/interactive harness for this new package; environment launch attempts failed before tests because browser Unix sockets are restricted

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
