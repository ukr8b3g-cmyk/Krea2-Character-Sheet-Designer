"""Deterministic contracts; run with ``python -m unittest tests.test_contract -v``.

These tests exercise the pure compiler and adapters without ComfyUI, torch,
models, a GPU, or an external service.  The pinned H3 compiler is an independent
oracle for state normalization and geometry only, never for Krea2 prompt prose.
"""
from __future__ import annotations

import copy
import importlib.util
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys
import types
import unittest
from unittest import mock

from krea2_character_sheet import compiler, node, preview
from tests.upstream import h3_compiler as upstream

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "tests/fixtures/state_cases.json").read_text())
VIEWS = ("face_front", "face_left", "body_front", "body_left", "body_back", "hands", "feet")
BODIES = ("body_front", "body_left", "body_back")
PORTRAITS = ("face_front", "face_left")
PART_VIEWS = {
    "head_hair": (*PORTRAITS, *BODIES),
    "face": (*PORTRAITS, *BODIES),
    "upper_clothing": (*PORTRAITS, *BODIES),
    "back_clothing": ("body_left", "body_back"),
    "lower_body": BODIES,
    "hands": (*BODIES, "hands"),
    "footwear": (*BODIES, "feet"),
    "other": VIEWS,
}
NODE_CLASSES = (node.Krea2CharacterSheetDesigner, node.Krea2LayoutReferenceSheetDesigner)
MODES = (False, True)


def state(views=VIEWS, *, version=1, mode="auto", parts=None, **sizes):
    result = {
        "schema_version": version,
        "views": list(views),
        "size": {
            "mode": mode, "body_height": 1120,
            "manual_width": 2240, "manual_height": 1280, **sizes,
        },
    }
    if version == 2:
        result["part_prompts"] = dict(parts or {})
    return result


def raw(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def envelope(state_json):
    return raw({"state_json": state_json}).encode("utf-8")


def geometry(layout):
    return {
        "canvas": layout["canvas"], "feet_y": layout["feet_y"],
        "panels": [{"id": p["id"], "rect": p["rect"]} for p in layout["panels"]],
    }


def fake_nodes(maximum=16384):
    module = types.ModuleType("nodes")
    module.MAX_RESOLUTION = maximum
    return mock.patch.dict(sys.modules, {"nodes": module})


class StateGeometryContract(unittest.TestCase):
    def test_all_127_view_sets_modes_schemas_and_reference_roles_match_upstream(self):
        """508 state/geometry cases, checked in both modes (1,016 compiles)."""
        cases = 0
        for mask in range(1, 1 << len(VIEWS)):
            selected = [view for i, view in enumerate(VIEWS) if mask & (1 << i)]
            for sizing, version in itertools.product(("auto", "manual"), (1, 2)):
                # Reverse and duplicate views to test canonicalization too.
                semantic = state(list(reversed(selected)) + selected[:1], version=version,
                                 mode=sizing, parts={p: f"directive-{p}" for p in PART_VIEWS})
                original = copy.deepcopy(semantic)
                saved = raw(semantic)
                baseline = upstream.compile_state(saved)
                for layout_reference in MODES:
                    with self.subTest(mask=mask, sizing=sizing, version=version,
                                      layout_reference=layout_reference):
                        result = compiler.compile_state(saved, layout_reference=layout_reference)
                        for key in ("state_json", "width", "height", "pixel_count",
                                    "megapixels", "experimental", "max_resolution"):
                            self.assertEqual(result[key], baseline[key], key)
                        self.assertEqual(geometry(result["layout"]), geometry(baseline["layout"]))
                        self.assertEqual(json.loads(result["state_json"])["views"], selected)
                        self.assertEqual(json.loads(result["state_json"])["schema_version"], version)
                        self.assertEqual(result, compiler.compile_state(saved, layout_reference=layout_reference))
                        self.assertEqual(semantic, original, "Compilation must not mutate the source")
                        self.assert_geometry_invariants(result)
                        cases += 1
        self.assertEqual(cases, 1016)

    def assert_geometry_invariants(self, result):
        width, height = result["layout"]["canvas"]
        self.assertEqual((width, height), (result["width"], result["height"]))
        self.assertEqual(width % 32, 0)
        self.assertEqual(height % 32, 0)
        panels = result["layout"]["panels"]
        bodies = [p for p in panels if p["id"] in BODIES]
        for panel in panels:
            x, y, w, h = panel["rect"]
            self.assertGreater(min(x, y, w, h), 0)
            self.assertLess(x + w, 1)
            self.assertLess(y + h, 1)
            for value in panel["rect"]:
                self.assertEqual(value, round(value, 6))
        for first, second in itertools.combinations(panels, 2):
            x, y, w, h = first["rect"]
            a, b, c, d = second["rect"]
            self.assertTrue(x + w <= a or a + c <= x or y + h <= b or b + d <= y,
                            f"Overlapping regions: {first['id']} and {second['id']}")
        if bodies:
            self.assertIsNotNone(result["layout"]["feet_y"])
            for body in bodies:
                self.assertEqual(body["rect"][1:], bodies[0]["rect"][1:])
                self.assertAlmostEqual(body["rect"][1] + body["rect"][3],
                                       result["layout"]["feet_y"], places=5)
        else:
            self.assertIsNone(result["layout"]["feet_y"])

    def test_strict_validation_fixture_acceptance_and_error_codes(self):
        self.assertEqual(len(FIXTURES), 62)
        for case, layout_reference in itertools.product(FIXTURES, MODES):
            with self.subTest(case=case["id"], layout_reference=layout_reference):
                saved = case["raw"]
                if case["valid"]:
                    result = compiler.compile_state(saved, max_resolution=case["max_resolution"],
                                                    layout_reference=layout_reference)
                    self.assertEqual(json.loads(result["state_json"]), case["normalized"])
                    self.assertEqual(compiler.parse_state(saved, max_resolution=case["max_resolution"]),
                                     upstream.parse_state(saved, max_resolution=case["max_resolution"]))
                else:
                    with self.assertRaises(compiler.StateValidationError) as raised:
                        compiler.compile_state(saved, max_resolution=case["max_resolution"],
                                               layout_reference=layout_reference)
                    self.assertEqual(raised.exception.code, case["code"])
                self.assertEqual(case["raw"], saved)

    def test_additional_strict_json_failures(self):
        bad_cases = [
            (None, "invalid_type"), ({}, "invalid_type"), ("", "invalid_json"),
            ("[]", "invalid_type"), ("null", "invalid_type"),
            ("NaN", "non_finite"), ("Infinity", "non_finite"), ("-Infinity", "non_finite"),
            ("[" * 2000 + "]" * 2000, "invalid_json"),
            ('{"key":"\\ud800"}', "invalid_utf8"),
            ('{"key":"\\udc00"}', "invalid_utf8"),
            (" " * (compiler.STATE_MAX_BYTES + 1), "state_too_large"),
            ('"' + "界" * (compiler.STATE_MAX_BYTES // 3) + '"', "state_too_large"),
        ]
        for saved, code in bad_cases:
            with self.subTest(code=code, sample=repr(saved)[:40]):
                with self.assertRaises(compiler.StateValidationError) as raised:
                    compiler.compile_state(saved)
                self.assertEqual(raised.exception.code, code)

    def test_v2_requires_exact_parts_schema_and_v1_never_migrates(self):
        bad = []
        value = state(version=2); del value["part_prompts"]
        bad.append((value, "missing_key"))
        value = state(); value["part_prompts"] = {}
        bad.append((value, "unknown_key"))
        bad.append((state(version=2, parts={"unknown": "x"}), "unknown_part"))
        bad.append((state(version=2, parts={"hands": 1}), "invalid_type"))
        value = state(version=2); value["part_prompts"] = []
        bad.append((value, "invalid_type"))
        for value, code in bad:
            with self.subTest(code=code, value=value):
                with self.assertRaises(compiler.StateValidationError) as raised:
                    compiler.compile_state(raw(value))
                self.assertEqual(raised.exception.code, code)
        for version in (1, 2):
            saved = raw(state(version=version))
            self.assertEqual(compiler.compile_state(saved)["state_json"], saved)

    def test_utf16_limit_and_literal_whitespace_preservation(self):
        for text in ("a" * 1000, "🧤" * 500, "  桜🧤\n  blue  \n", "\u0085"):
            with self.subTest(length=len(text)):
                result = compiler.parse_state(raw(state(version=2, parts={"hands": text})))
                self.assertEqual(result["part_prompts"]["hands"], text)
        for text in ("a" * 1001, "🧤" * 500 + "a"):
            with self.assertRaises(compiler.StateValidationError) as raised:
                compiler.compile_state(raw(state(version=2, parts={"hands": text})))
            self.assertEqual(raised.exception.code, "part_prompt_too_long")
        result = compiler.parse_state(raw(state(version=2, parts={"hands": "\ufeff \t\n\u3000"})))
        self.assertEqual(result["part_prompts"], {})

    def test_five_view_geometry_is_stable_and_horizontal(self):
        result = compiler.compile_state((ROOT / "tests/fixtures/five_view_state.json").read_text())
        self.assertEqual((result["width"], result["height"]), (2816, 1280))
        rects = [p["rect"] for p in result["layout"]["panels"]]
        self.assertEqual([r[1] for r in rects], [0.0625] * 5)
        self.assertEqual([r[3] for r in rects], [0.875] * 5)
        self.assertEqual(result["layout"]["feet_y"], 0.9375)
        self.assertEqual([r[0] for r in rects], sorted(r[0] for r in rects))

    def test_runtime_limits_cover_inactive_fields_and_computed_auto_size(self):
        for mode in ("auto", "manual"):
            value = state(mode=mode, manual_width=4096)
            with self.assertRaises(compiler.StateValidationError) as raised:
                compiler.compile_state(raw(value), max_resolution=3072)
            self.assertEqual(raised.exception.code, "size_limit")
        value = state(body_height=2048, manual_width=2048, manual_height=2048)
        # Every saved dimension fits 2048; the computed multi-column canvas does not.
        compiler.parse_state(raw(value), max_resolution=2048)
        with self.assertRaises(compiler.StateValidationError) as raised:
            compiler.compile_state(raw(value), max_resolution=2048)
        self.assertEqual(raised.exception.code, "size_limit")
        for maximum in (True, 31, 32.0, "16384", None):
            with self.subTest(maximum=maximum), self.assertRaises(ValueError):
                compiler.compile_state(compiler.DEFAULT_STATE_JSON, max_resolution=maximum)

    def test_manual_dimensions_do_not_change_with_view_selection(self):
        for selected in (VIEWS, ("hands",), ("body_back",), PORTRAITS):
            result = compiler.compile_state(raw(state(selected, mode="manual", manual_width=768,
                                                       manual_height=2048)))
            self.assertEqual((result["width"], result["height"]), (768, 2048))
            self.assertEqual(geometry(result["layout"]), geometry(upstream.compile_state(
                raw(state(selected, mode="manual", manual_width=768, manual_height=2048)))["layout"]))

    def test_experimental_metadata_boundary(self):
        for height, experimental in ((672, False), (704, True)):
            result = compiler.compile_state(raw(state(("body_front",), mode="manual",
                                                       manual_width=1536, manual_height=height)))
            self.assertEqual(result["experimental"], experimental)
            self.assertEqual(result["pixel_count"], 1536 * height)
            self.assertEqual(result["megapixels"], result["pixel_count"] / 1_000_000)


class PromptContract(unittest.TestCase):
    def test_reference_roles_are_explicit_and_cannot_enter_saved_schema(self):
        saved = raw(state(version=2))
        regular = compiler.compile_state(saved)
        layout = compiler.compile_state(saved, layout_reference=True)
        self.assertEqual(regular["state_json"], layout["state_json"])
        self.assertEqual(geometry(regular["layout"]), geometry(layout["layout"]))
        self.assertIn("the character reference", regular["prompt"])
        self.assertNotRegex(regular["prompt"], r"\bImage [12]\b")
        self.assertNotIn("mannequin", regular["prompt"].lower())
        self.assertIn("Image 1 is ONLY a composition example", layout["prompt"])
        self.assertIn("Image 2 is the ONLY character identity and appearance reference", layout["prompt"])
        self.assertIn("Replace every mannequin or person from Image 1", layout["prompt"])
        self.assertIn("Do not copy identity", layout["prompt"])
        self.assertIn("from Image 2, except for", layout["prompt"])
        for name in ("reference_mode", "layout_reference", "model"):
            invalid = json.loads(saved); invalid[name] = True
            with self.subTest(name=name), self.assertRaises(compiler.StateValidationError):
                compiler.compile_state(raw(invalid))

    def test_profile_portrait_and_body_both_face_screen_left(self):
        for layout_reference in MODES:
            result = compiler.compile_state(raw(state(("face_left", "body_left"))),
                                            layout_reference=layout_reference)
            for panel in result["layout"]["panels"]:
                text = panel["content"]
                self.assertIn("LEFT EDGE OF THE CANVAS", text)
                self.assertNotIn("anatomical left side", text)
                self.assertIn("strict side-profile", text)
            self.assertIn("nose and toes", result["prompt"])
            self.assertIn("same screen direction", result["prompt"])

    def test_full_bodies_portraits_and_white_canvas_have_required_framing(self):
        for layout_reference in MODES:
            prompt = compiler.compile_state(raw(state()), layout_reference=layout_reference)["prompt"]
            self.assertIn("completely visible from the top of the hairstyle to the soles", prompt)
            self.assertIn("same scale", prompt)
            self.assertIn("Align the feet on one baseline", prompt)
            self.assertIn("do not overlap or crop", prompt)
            self.assertIn("portraits are chest-up", prompt)
            self.assertIn("complete hairstyle", prompt)
            self.assertIn("without the waist or legs", prompt)
            self.assertIn("pure white", prompt)
            self.assertIn("soft diffuse lighting", prompt)
            self.assertIn("No scenery", prompt)
            self.assertIn("cast shadows", prompt)
            self.assertIn("borders", prompt)
            self.assertIn("do not add", prompt.lower())

    def test_no_h3_video_or_qwen_json_prompt_template_leaks(self):
        prohibited = (
            r"\bH3\b", r"\bQwen\b", r"<Subject\s", r"<Picture\s", r"\[Shot\s",
            r"subject_definitions:", r"retention_analysis:", r"overall_soundscape:",
            r"non_diegetic_music:", r"first frame", r"last frame", r"\bvideo\b",
            r"\bcamera motion\b", r"\btransitions\b", r"```", r'"canvas"\s*:',
            r'"panels"\s*:', r'"rect"\s*:', r"\bfeet_y\b",
        )
        for layout_reference in MODES:
            prompt = compiler.compile_state(raw(state()), layout_reference=layout_reference)["prompt"]
            for pattern in prohibited:
                with self.subTest(pattern=pattern, layout_reference=layout_reference):
                    self.assertNotRegex(prompt, re.compile(pattern, re.I))

    def test_all_selected_depictions_and_only_selected_panel_regions(self):
        for mask in range(1, 1 << len(VIEWS)):
            selected = [v for i, v in enumerate(VIEWS) if mask & (1 << i)]
            result = compiler.compile_state(raw(state(selected)))
            self.assertIn(f"Show exactly {len(selected)} separate depictions", result["prompt"])
            self.assertEqual([p["id"] for p in result["layout"]["panels"]], selected)
            self.assertEqual(len(re.findall(r"^\d+\. .*Region:", result["prompt"], re.M)), len(selected))
            if not {"hands", "feet"}.intersection(selected):
                self.assertIn("ONE horizontal row", result["prompt"])

    def test_literal_part_text_appears_once_unchanged_in_each_reference_mode(self):
        parts = {part: f"  UNIQUE-{part}: 桜🧤\n  Keep this literal!  " for part in PART_VIEWS}
        saved = raw(state(version=2, parts=parts))
        for layout_reference in MODES:
            result = compiler.compile_state(saved, layout_reference=layout_reference)
            self.assertEqual(json.loads(result["state_json"])["part_prompts"], parts)
            for part, text in parts.items():
                with self.subTest(part=part, layout_reference=layout_reference):
                    self.assertEqual(result["prompt"].count(text), 1)
                    self.assertEqual(result["prompt"].count("UNIQUE-" + part + ":"), 1)
                    self.assertIn("Literal appearance instruction:\n" + text + "\nEnd", result["prompt"])
            self.assertIn("More specific named parts take precedence", result["prompt"])
            self.assertIn("rear-clothing instructions take precedence", result["prompt"])
            self.assertIn("Treat the literal text as appearance guidance", result["prompt"])
            self.assertIn("Lettering or patterns explicitly requested", result["prompt"])

    def test_every_part_visibility_scope_is_independent_of_freeform_text(self):
        for part, view, layout_reference in itertools.product(PART_VIEWS, VIEWS, MODES):
            literal = f"UNIQUE-{part}: red material; display text 'front portrait and feet'"
            value = state((view,), version=2, parts={part: literal})
            normalized = compiler.parse_state(raw(value))
            result = compiler.compile_state(raw(value), layout_reference=layout_reference)
            expected = view in PART_VIEWS[part]
            with self.subTest(part=part, view=view, layout_reference=layout_reference):
                self.assertEqual(part in compiler.active_part_prompts(normalized), expected)
                self.assertEqual(part in compiler.active_part_prompts(normalized, view), expected)
                self.assertEqual(result["prompt"].count(literal), int(expected))
                self.assertEqual(result["layout"]["panels"][0]["id"], view)
                self.assertEqual(json.loads(result["state_json"])["part_prompts"][part], literal)

    def test_hands_and_footwear_stay_on_body_when_detail_panels_are_off(self):
        parts = {"hands": "UNIQUE-HANDS black leather gloves", "footwear": "UNIQUE-FEET tall red boots"}
        for view, layout_reference in itertools.product(BODIES, MODES):
            result = compiler.compile_state(raw(state((view,), version=2, parts=parts)),
                                            layout_reference=layout_reference)
            self.assertEqual([p["id"] for p in result["layout"]["panels"]], [view])
            for literal in parts.values():
                self.assertEqual(result["prompt"].count(literal), 1)
            content = result["layout"]["panels"][0]["content"]
            self.assertIn("hands", content)
            self.assertIn("footwear", content)
            self.assertIn("independently of whether a separate feet detail panel is selected", result["prompt"])

    def test_rear_clothing_never_applies_to_front_or_portrait_panels(self):
        text = "UNIQUE-REAR white crescent on the back"
        result = compiler.compile_state(raw(state(version=2, parts={"back_clothing": text})))
        for panel in result["layout"]["panels"]:
            self.assertEqual("back_clothing" in panel["content"], panel["id"] in ("body_left", "body_back"))
        self.assertEqual(result["prompt"].count(text), 1)
        self.assertIn("Never move this design onto the front, side surface, or portraits", result["prompt"])
        self.assertIn("never turn the subject to reveal it", result["prompt"])

    def test_part_changes_never_change_geometry(self):
        unmodified = state(version=2)
        modified = copy.deepcopy(unmodified)
        modified["part_prompts"] = {part: "large red embellishment" for part in PART_VIEWS}
        for layout_reference in MODES:
            before = compiler.compile_state(raw(unmodified), layout_reference=layout_reference)
            after = compiler.compile_state(raw(modified), layout_reference=layout_reference)
            self.assertEqual(geometry(before["layout"]), geometry(after["layout"]))

    def test_details_preserve_complete_hands_and_footwear(self):
        result = compiler.compile_state(raw(state(("hands", "feet"))))
        self.assertIn("both complete hands", result["prompt"])
        self.assertIn("both complete feet or footwear", result["prompt"])
        self.assertIn("closed footwear closed", result["prompt"])
        self.assertIn("open-toed footwear open-toed", result["prompt"])
        self.assertIn("Stack the hands detail above the footwear detail", result["prompt"])


class NodeContract(unittest.TestCase):
    def test_two_nodes_expose_exact_three_outputs_and_one_state_input(self):
        expected_default = {
            "schema_version": 1,
            "views": ["face_front", "face_left", "body_front", "body_left", "body_back"],
            "size": {"mode": "manual", "body_height": 672,
                     "manual_width": 1696, "manual_height": 768},
        }
        # New-node UX may have a Krea-specific starting point; the shared
        # historical default and imported state semantics must remain unchanged.
        self.assertEqual(compiler.DEFAULT_STATE_JSON, upstream.DEFAULT_STATE_JSON)
        self.assertEqual(node.DEFAULT_NODE_STATE_JSON, raw(expected_default))
        for cls, role in zip(NODE_CLASSES, MODES):
            with self.subTest(node=cls.__name__):
                self.assertEqual(cls.RETURN_TYPES, ("STRING", "INT", "INT"))
                self.assertEqual(cls.RETURN_NAMES, ("prompt", "width", "height"))
                self.assertEqual(cls.FUNCTION, "compile")
                self.assertEqual(cls.LAYOUT_REFERENCE, role)
                inputs = cls.INPUT_TYPES()
                self.assertEqual(set(inputs), {"required"})
                self.assertEqual(set(inputs["required"]), {"state_json"})
                kind, options = inputs["required"]["state_json"]
                self.assertEqual(kind, "STRING")
                self.assertIs(options["dynamicPrompts"], False)
                self.assertIs(options["multiline"], True)
                self.assertEqual(options["default"], node.DEFAULT_NODE_STATE_JSON)
                self.assertEqual(compiler.parse_state(options["default"]), expected_default)
                compiled = compiler.compile_state(options["default"], layout_reference=role)
                self.assertEqual(compiled["state_json"], options["default"])
                self.assertEqual((compiled["width"], compiled["height"]), (1696, 768))
                self.assertLess(compiled["pixel_count"], 2_000_000)
                self.assertEqual([p["id"] for p in compiled["layout"]["panels"]],
                                 expected_default["views"])
                with fake_nodes():
                    self.assertIs(cls.VALIDATE_INPUTS(options["default"]), True)
                    self.assertEqual(cls().compile(options["default"]),
                                     (compiled["prompt"], 1696, 768))

    def test_nodes_and_preview_share_compiler_contract_for_every_fixture(self):
        for case, cls in itertools.product(FIXTURES, NODE_CLASSES):
            with self.subTest(case=case["id"], node=cls.__name__), fake_nodes(case["max_resolution"]):
                validation = cls.VALIDATE_INPUTS(case["raw"])
                if case["valid"]:
                    self.assertIs(validation, True)
                    compiled = compiler.compile_state(case["raw"], max_resolution=case["max_resolution"],
                                                       layout_reference=cls.LAYOUT_REFERENCE)
                    result = cls().compile(case["raw"])
                    self.assertEqual(result, (compiled["prompt"], compiled["width"], compiled["height"]))
                    self.assertEqual(tuple(type(v) for v in result), (str, int, int))
                    self.assertEqual(preview.compile_preview_request(envelope(case["raw"]),
                        max_resolution=case["max_resolution"], layout_reference=cls.LAYOUT_REFERENCE), compiled)
                else:
                    self.assertIsInstance(validation, str)
                    self.assertTrue(validation)
                    with self.assertRaises(compiler.StateValidationError) as raised:
                        cls().compile(case["raw"])
                    self.assertEqual(raised.exception.code, case["code"])
                    with self.assertRaises(compiler.StateValidationError) as raised:
                        preview.compile_preview_request(envelope(case["raw"]),
                            max_resolution=case["max_resolution"], layout_reference=cls.LAYOUT_REFERENCE)
                    self.assertEqual(raised.exception.code, case["code"])

    def test_core_max_resolution_is_read_at_call_time(self):
        for cls in NODE_CLASSES:
            with fake_nodes(16384):
                self.assertIs(cls.VALIDATE_INPUTS(compiler.DEFAULT_STATE_JSON), True)
                cls().compile(compiler.DEFAULT_STATE_JSON)
            with fake_nodes(1024):
                self.assertIsInstance(cls.VALIDATE_INPUTS(compiler.DEFAULT_STATE_JSON), str)
                with self.assertRaises(compiler.StateValidationError) as raised:
                    cls().compile(compiler.DEFAULT_STATE_JSON)
                self.assertEqual(raised.exception.code, "size_limit")
        for value in (True, 31, 16384.0, "16384", None):
            with self.subTest(maximum=value), fake_nodes(value), self.assertRaises(RuntimeError):
                node.runtime_max_resolution()

    def test_package_registers_both_nodes_without_torch_or_comfyui(self):
        # A fresh interpreter avoids accidentally proving only an import-cache hit.
        script = '''
import builtins, importlib.util, pathlib, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'torch', 'comfy', 'nodes'}:
        raise AssertionError('Heavy/runtime-only import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
root = pathlib.Path.cwd()
spec = importlib.util.spec_from_file_location('krea2_test_pack', root / '__init__.py',
    submodule_search_locations=[str(root)])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
assert set(module.NODE_CLASS_MAPPINGS) == {'Krea2CharacterSheetDesigner', 'Krea2LayoutReferenceSheetDesigner', 'Krea2LayoutImageSheetDesigner'}
assert set(module.NODE_DISPLAY_NAME_MAPPINGS) == set(module.NODE_CLASS_MAPPINGS)
assert module.WEB_DIRECTORY == './web'
from krea2_character_sheet.compiler import compile_state, DEFAULT_STATE_JSON
assert len(compile_state(DEFAULT_STATE_JSON)['layout']['panels']) == 4
'''
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, text=True,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


class PreviewEnvelopeContract(unittest.TestCase):
    def test_envelope_is_exactly_one_string_field_and_strict_json(self):
        cases = [
            (b"{}", "invalid_request"), (b"[]", "invalid_request"),
            (b'{"state_json":null}', "invalid_type"),
            (b'{"state_json":{}}', "invalid_type"),
            (raw({"state_json": compiler.DEFAULT_STATE_JSON, "layout_reference": True}).encode(), "invalid_request"),
            (b'{"state_json":"x","state_json":"x"}', "duplicate_key"),
            (b'{"state_json":NaN}', "non_finite"),
            (b"\xff", "invalid_utf8"), (b"{", "invalid_json"),
            (b" " * (preview.HTTP_MAX_BYTES + 1), "request_too_large"),
            (envelope(" " * (compiler.STATE_MAX_BYTES + 1)), "state_too_large"),
        ]
        for body, code in cases:
            with self.subTest(code=code, size=len(body)):
                with self.assertRaises(compiler.StateValidationError) as raised:
                    preview.compile_preview_request(body, max_resolution=16384)
                self.assertEqual(raised.exception.code, code)

    def test_route_registration_is_independent_and_idempotent(self):
        captured = []
        class Routes:
            def post(self, path):
                def decorate(handler):
                    captured.append((path, handler))
                    return handler
                return decorate
        instance = types.SimpleNamespace(routes=Routes())
        server = types.ModuleType("server")
        server.PromptServer = types.SimpleNamespace(instance=instance)
        with mock.patch.dict(sys.modules, {"server": server}):
            self.assertIs(preview.register_routes(), True)
            self.assertIs(preview.register_routes(), True)
        self.assertEqual(captured, [
            ("/krea2_character_sheet_designer/preview", preview.preview),
            ("/krea2_character_sheet_designer/layout-reference/preview", preview.layout_preview),
            ("/krea2_character_sheet_designer/layout-image/preview", preview.builtin_layout_preview),
        ])

    def test_route_registration_without_server_or_instance_is_safe(self):
        with mock.patch.dict(sys.modules, {"server": None}):
            self.assertIs(preview.register_routes(), False)
        server = types.ModuleType("server")
        server.PromptServer = types.SimpleNamespace(instance=None)
        with mock.patch.dict(sys.modules, {"server": server}):
            self.assertIs(preview.register_routes(), False)


class FakeContent:
    def __init__(self, chunks):
        self.chunks = chunks
        self.read_count = 0

    async def iter_chunked(self, size):
        for chunk in self.chunks:
            self.read_count += 1
            yield chunk


def request(body, *, content_type="application/json", content_length="auto", chunks=None):
    return types.SimpleNamespace(
        content_length=len(body) if content_length == "auto" else content_length,
        content_type=content_type, content=FakeContent(chunks if chunks is not None else [body]),
    )


class PreviewHTTPContract(unittest.IsolatedAsyncioTestCase):
    async def call(self, req, *, layout_reference=False, maximum=16384):
        with fake_nodes(maximum):
            response = await (preview.layout_preview(req) if layout_reference else preview.preview(req))
        self.assertEqual(response.content_type, "application/json")
        return response.status, json.loads(response.body)

    async def test_real_aiohttp_routes_return_matching_node_outputs(self):
        from aiohttp import web
        from aiohttp.test_utils import TestClient, TestServer
        app = web.Application()
        app.router.add_post(preview.PREVIEW_PATH, preview.preview)
        app.router.add_post("/krea2_character_sheet_designer/layout-reference/preview", preview.layout_preview)
        with fake_nodes(), self.subTest(transport="aiohttp loopback"):
            async with TestClient(TestServer(app)) as client:
                for path, cls in zip((preview.PREVIEW_PATH,
                    "/krea2_character_sheet_designer/layout-reference/preview"), NODE_CLASSES):
                    response = await client.post(path, json={"state_json": compiler.DEFAULT_STATE_JSON})
                    self.assertEqual(response.status, 200)
                    payload = await response.json()
                    self.assertEqual(cls().compile(compiler.DEFAULT_STATE_JSON),
                                     (payload["prompt"], payload["width"], payload["height"]))
                    self.assertEqual(payload["max_resolution"], 16384)

    async def test_chunked_unknown_length_success_in_both_modes(self):
        body = envelope(raw(state(version=2, parts={"hands": "桜🧤"})))
        for role in MODES:
            status, payload = await self.call(request(body, content_length=None,
                chunks=[body[i:i+7] for i in range(0, len(body), 7)]), layout_reference=role)
            self.assertEqual(status, 200)
            self.assertEqual(payload, compiler.compile_state(json.loads(body)["state_json"], layout_reference=role))

    async def test_oversized_declared_length_is_rejected_before_read(self):
        req = request(b"", content_length=preview.HTTP_MAX_BYTES + 1)
        status, payload = await self.call(req)
        self.assertEqual((status, payload["error"]["code"]), (413, "request_too_large"))
        self.assertEqual(req.content.read_count, 0)

    async def test_chunked_payload_limit_is_enforced_without_content_length(self):
        chunks = [b" " * 4096] * (preview.HTTP_MAX_BYTES // 4096 + 5)
        req = request(b"", content_length=None, chunks=chunks)
        status, payload = await self.call(req)
        self.assertEqual((status, payload["error"]["code"]), (413, "request_too_large"))
        self.assertLess(req.content.read_count, len(chunks))

    async def test_wrong_content_type_is_rejected_before_read(self):
        req = request(envelope(compiler.DEFAULT_STATE_JSON), content_type="text/plain")
        status, payload = await self.call(req)
        self.assertEqual((status, payload["error"]["code"]), (415, "invalid_content_type"))
        self.assertEqual(req.content.read_count, 0)

    async def test_http_validation_statuses_and_codes(self):
        cases = [
            (b"\xff", 400, "invalid_utf8"), (b"{", 400, "invalid_json"),
            (b"{}", 400, "invalid_request"),
            (envelope("{"), 400, "invalid_json"),
            (envelope(raw(state(()))), 400, "empty_views"),
            (envelope(" " * (compiler.STATE_MAX_BYTES + 1)), 413, "state_too_large"),
        ]
        for body, expected_status, code in cases:
            with self.subTest(code=code):
                status, payload = await self.call(request(body))
                self.assertEqual((status, payload["error"]["code"]), (expected_status, code))
                self.assertIsInstance(payload["error"]["message"], str)
                self.assertEqual(set(payload), {"error"})

    async def test_http_respects_live_core_max_resolution(self):
        status, payload = await self.call(request(envelope(compiler.DEFAULT_STATE_JSON)), maximum=1024)
        self.assertEqual((status, payload["error"]["code"]), (400, "size_limit"))

    async def test_internal_error_is_sanitized_and_never_returns_user_prompt(self):
        secret = "PRIVATE-DIRECTIVE-DO-NOT-RETURN"
        body = envelope(raw(state(version=2, parts={"other": secret})))
        with mock.patch.object(preview, "compile_preview_request", side_effect=RuntimeError(secret)):
            with self.assertLogs(preview.__name__, level="ERROR"):
                status, payload = await self.call(request(body))
        self.assertEqual((status, payload["error"]["code"]), (500, "internal_error"))
        self.assertNotIn(secret, json.dumps(payload))
        self.assertNotIn("RuntimeError", json.dumps(payload))
        self.assertIn("saved state is unchanged", payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()
