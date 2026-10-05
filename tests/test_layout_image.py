"""CPU raster and new-node contracts; no model download or GPU execution."""
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np
from PIL import Image, ImageOps

from krea2_character_sheet import compiler, node, preview
from krea2_character_sheet.layout_image import ATLAS_CROPS, ATLAS_PATH, MIRRORED_VIEWS, render_layout_image

ROOT = Path(__file__).resolve().parents[1]


def small_state(views=None):
    value = json.loads(node.DEFAULT_NODE_STATE_JSON)
    value['size'].update(manual_width=512, manual_height=256)
    if views is not None:
        value['views'] = list(views)
    return value


class BuiltinLayoutContracts(unittest.TestCase):
    def test_tiny_auto_and_high_resolution_images_keep_requested_canvas(self):
        cases = [(32, 32), (3840, 2176)]
        for width, height in cases:
            value = small_state(compiler.VIEW_IDS)
            value['size'].update(manual_width=width, manual_height=height)
            result = compiler.compile_state(json.dumps(value), builtin_layout=True)
            self.assertEqual(render_layout_image(result['layout']).size, (width, height))
        value['size'].update(mode='auto', body_height=672)
        result = compiler.compile_state(json.dumps(value), builtin_layout=True)
        self.assertEqual(render_layout_image(result['layout']).size, (result['width'], result['height']))

    def test_atlas_crops_and_mirror_direction_match_frontend(self):
        source = (ROOT/'web/artwork.js').read_text()
        crops = {name: tuple(int(v) for v in values.split(',')) for name, values in
                 re.findall(r'(\w+): Object\.freeze\(\[([\d, ]+)\]\)', source)}
        self.assertEqual(crops, ATLAS_CROPS)
        self.assertEqual(MIRRORED_VIEWS, {'face_left', 'body_left'})
        css = (ROOT/'web/style.css').read_text()
        self.assertIn('[data-artwork="face_left"]', css)
        self.assertIn('[data-artwork="body_left"]', css)
        self.assertIn('scaleX(-1)', css)

    def test_all_127_selections_render_only_selected_regions(self):
        for bits in range(1, 128):
            views = [v for i, v in enumerate(compiler.VIEW_IDS) if bits & (1 << i)]
            with self.subTest(bits=bits):
                result = compiler.compile_state(json.dumps(small_state(views)), builtin_layout=True)
                image = render_layout_image(result['layout'])
                self.assertEqual(image.mode, 'RGB')
                self.assertEqual(image.size, (512, 256))
                pixels = np.asarray(image)
                occupied = np.any(pixels < 250, axis=-1)
                regions = np.zeros(occupied.shape, dtype=bool)
                for panel in result['layout']['panels']:
                    x, y, w, h = panel['rect']
                    left, top = round(x * 512), round(y * 256)
                    right, bottom = round((x + w) * 512), round((y + h) * 256)
                    self.assertTrue(occupied[top:bottom, left:right].any(), panel['id'])
                    regions[top:bottom, left:right] = True
                self.assertFalse(occupied[~regions].any())
                self.assertTrue(np.all(pixels[0, 0] == 255))

    def test_exact_crop_and_profile_pixels_match_mirrored_atlas(self):
        with Image.open(ATLAS_PATH) as source:
            atlas = source.convert('RGBA')
        for view in compiler.VIEW_IDS:
            with self.subTest(view=view):
                x, y, width, height = ATLAS_CROPS[view]
                art = atlas.crop((x, y, x + width, y + height))
                if view in MIRRORED_VIEWS:
                    art = ImageOps.mirror(art)
                expected = Image.new('RGB', (width, height), 'white')
                expected.paste(art, (0, 0), art)
                actual = render_layout_image({'canvas': [width, height], 'panels': [{'id': view, 'rect': [0, 0, 1, 1]}]})
                np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected))

    def test_all_selections_sizes_schemas_preserve_state_and_geometry(self):
        for bits, mode, version in itertools.product(range(1, 128), ('auto', 'manual'), (1, 2)):
            value = small_state([v for i, v in enumerate(compiler.VIEW_IDS) if bits & (1 << i)])
            value['size']['mode'] = mode
            value['schema_version'] = version
            if version == 2:
                value['part_prompts'] = {'hands': '  UNIQUE gloves\n', 'footwear': 'UNIQUE boots'}
            raw = json.dumps(value)
            before = compiler.compile_state(raw, layout_reference=True)
            result = compiler.compile_state(raw, layout_reference=True, builtin_layout=True)
            with self.subTest(bits=bits, mode=mode, version=version):
                for key in ('state_json', 'layout', 'width', 'height', 'pixel_count'):
                    self.assertEqual(result[key], before[key])
                self.assertIn('Edit Image 1', result['prompt'])
                self.assertIn('Image 2 is the ONLY character', result['prompt'])
                self.assertNotIn('Region: left', result['prompt'])
                self.assertNotIn('Percentages', result['prompt'])
                for part, literal in value.get('part_prompts', {}).items():
                    self.assertEqual(result['prompt'].count(literal), int(part in compiler.active_part_prompts(value)))
                self.assertEqual([p['id'] for p in result['layout']['panels']], value['views'])

    def test_first_three_ports_and_legacy_nodes_stay_compatible(self):
        cls = node.Krea2LayoutImageSheetDesigner
        self.assertEqual(cls.RETURN_TYPES, ('STRING', 'INT', 'INT', 'IMAGE'))
        self.assertEqual(cls.RETURN_NAMES, ('prompt', 'width', 'height', 'layout_image'))
        self.assertEqual(cls.INPUT_TYPES(), node.Krea2CharacterSheetDesigner.INPUT_TYPES())
        self.assertTrue(node.Krea2LayoutReferenceSheetDesigner.DEPRECATED)
        for legacy in (node.Krea2CharacterSheetDesigner, node.Krea2LayoutReferenceSheetDesigner):
            self.assertEqual(legacy.RETURN_NAMES, ('prompt', 'width', 'height'))

    def test_node_adapter_and_preview_share_exact_raster_and_prompt(self):
        # Exercise the adapter without pretending the lightweight torch stub is
        # a real ComfyUI run. The optional test below checks a real torch tensor.
        raw = json.dumps(small_state())
        result = compiler.compile_state(raw, layout_reference=True, builtin_layout=True)
        tensor_stub = SimpleNamespace(from_numpy=lambda a: SimpleNamespace(unsqueeze=lambda axis: np.expand_dims(a, axis)))
        with mock.patch.dict(sys.modules, {'nodes': SimpleNamespace(MAX_RESOLUTION=16384), 'torch': tensor_stub}):
            self.assertTrue(node.Krea2LayoutImageSheetDesigner.VALIDATE_INPUTS(raw))
            outputs = node.Krea2LayoutImageSheetDesigner().compile(raw)
        self.assertEqual(outputs[:3], (result['prompt'], 512, 256))
        self.assertEqual(outputs[3].shape, (1, 256, 512, 3))
        self.assertEqual(outputs[3].dtype, np.float32)
        np.testing.assert_array_equal(outputs[3][0], np.asarray(render_layout_image(result['layout']), dtype=np.float32) / 255.0)
        response = preview.compile_preview_request(json.dumps({'state_json': raw}).encode(), max_resolution=16384, layout_reference=True, builtin_layout=True)
        self.assertEqual(response, result)

    @unittest.skipUnless(importlib.util.find_spec('torch'), 'torch is not installed; real tensor execution not tested')
    def test_real_cpu_torch_tensor(self):
        import torch
        with mock.patch.dict(sys.modules, {'nodes': SimpleNamespace(MAX_RESOLUTION=16384)}):
            image = node.Krea2LayoutImageSheetDesigner().compile(json.dumps(small_state()))[3]
        self.assertEqual(image.shape, (1, 256, 512, 3))
        self.assertEqual(image.dtype, torch.float32)
        self.assertEqual(image.device.type, 'cpu')
        self.assertFalse(image.requires_grad)
        self.assertGreaterEqual(float(image.min()), 0)
        self.assertEqual(float(image.max()), 1)

    def test_invalid_state_rejected_before_image_or_torch_allocation(self):
        with mock.patch.dict(sys.modules, {'nodes': SimpleNamespace(MAX_RESOLUTION=16384)}):
            with mock.patch('krea2_character_sheet.layout_image.layout_image_tensor') as render:
                self.assertIsInstance(node.Krea2LayoutImageSheetDesigner.VALIDATE_INPUTS('{}'), str)
                with self.assertRaises(compiler.StateValidationError):
                    node.Krea2LayoutImageSheetDesigner().compile('{}')
                render.assert_not_called()


class BuiltinLayoutHTTPContracts(unittest.IsolatedAsyncioTestCase):
    async def test_real_new_preview_route_matches_compiler_without_image_dependencies(self):
        from aiohttp import web
        from aiohttp.test_utils import TestClient, TestServer

        raw = json.dumps(small_state())
        app = web.Application()
        app.router.add_post('/krea2_character_sheet_designer/layout-image/preview', preview.builtin_layout_preview)
        with mock.patch.dict(sys.modules, {'nodes': SimpleNamespace(MAX_RESOLUTION=16384)}):
            async with TestClient(TestServer(app)) as client:
                response = await client.post('/krea2_character_sheet_designer/layout-image/preview', json={'state_json': raw})
                self.assertEqual(response.status, 200)
                self.assertEqual(await response.json(), compiler.compile_state(raw, layout_reference=True, builtin_layout=True))
                response = await client.post('/krea2_character_sheet_designer/layout-image/preview', json={'state_json': '{}'})
                self.assertEqual(response.status, 400)


if __name__ == '__main__':
    unittest.main()
