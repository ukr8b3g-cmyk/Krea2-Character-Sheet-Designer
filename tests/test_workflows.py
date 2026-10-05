import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.build_workflows import ROOT, TEMPLATE, TEMPLATE_SHA256, build
from tools.validate_workflows import run, validate, validate_layout_graph
from tools.workflow_graph import flatten_connections, object_link, rebuild, validate_recursive


class WorkflowContracts(unittest.TestCase):
    def test_only_one_distribution_template(self):
        self.assertEqual([r['status'] for r in run()], ['static_pass'])
        self.assertEqual(list((ROOT/'workflows').glob('*.json')), [TEMPLATE])
        self.assertFalse(list((ROOT/'tools/upstream').glob('*.json')))

    def test_supplied_workflow_is_byte_identical(self):
        self.assertEqual(hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(), TEMPLATE_SHA256)
        self.assertEqual(TEMPLATE.stat().st_size, 77129)
        self.assertEqual(json.loads(TEMPLATE.read_bytes()), build())

    def test_workflow_cli_is_read_only(self):
        before = {p.name: p.read_bytes() for p in (ROOT/'workflows').iterdir()}
        subprocess.run([sys.executable, str(ROOT/'tools/build_workflows.py')],
                       check=True, capture_output=True, cwd=ROOT)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (ROOT/'workflows').iterdir()})

    def test_byte_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary)/'changed.json'
            candidate.write_bytes(TEMPLATE.read_bytes()+b'\n')
            with self.assertRaisesRegex(AssertionError, 'bytes changed'):
                validate(candidate)

    def test_builtin_layout_sources_cross_subgraph_boundary(self):
        flat = validate_layout_graph(build())
        self.assertEqual(flat['203:84']['inputs']['image'], ('200', 3))
        self.assertEqual(flat['203:85']['inputs']['image_b'], ('72', 0))
        self.assertEqual(flat['203:53']['inputs']['latent_image'], ('203:82', 0))
        self.assertEqual(flat['203:79']['inputs']['target_latent'], ('203:82', 0))
        self.assertEqual(flat['29']['inputs']['images'], ('203:54', 0))

    def test_reference_swap_is_rejected_after_valid_link_rebuild(self):
        workflow = build()
        workflow['links'][0][1:3] = [72, 0]
        workflow['links'][5][1:3] = [200, 3]
        rebuild(workflow)
        validate_recursive(workflow)
        with self.assertRaisesRegex(AssertionError, 'A must be built-in layout'):
            validate_layout_graph(workflow)

    def test_missing_negative_b_and_stale_boundary_are_rejected(self):
        workflow = build()
        graph = workflow['definitions']['subgraphs'][0]
        graph['links'] = [link for link in graph['links'] if link['id'] != 46]
        rebuild(graph)
        validate_recursive(workflow)
        with self.assertRaises((AssertionError, KeyError)):
            validate_layout_graph(workflow)
        graph['inputs'][-1]['linkIds'].append(9999)
        with self.assertRaisesRegex(AssertionError, 'Stale boundary'):
            validate_recursive(workflow)

    def test_sparse_host_promoted_controls_reach_leaf_nodes(self):
        workflow = build()
        host = next(n for n in workflow['nodes'] if n['id'] == 203)
        self.assertNotIn('seed', [port['name'] for port in host['inputs']])
        self.assertNotIn('lora_name', [port['name'] for port in host['inputs']])
        host.pop('widgets_values_named')
        overrides = {'seed': 123, 'steps': 15, 'cfg': 1.5,
                     'unet_name': 'selected_model.safetensors',
                     'lora_name': 'selected_lora.safetensors',
                     'clip_name': 'selected_clip.safetensors',
                     'vae_name': 'selected_vae.safetensors'}
        names = [p['name'] for p in workflow['definitions']['subgraphs'][0]['inputs'] if p['type'] != 'IMAGE']
        for name, value in overrides.items():
            host['widgets_values'][names.index(name)] = value
        validate_recursive(workflow)
        flat = flatten_connections(workflow)
        for name, nid in (('seed', 53), ('steps', 53), ('cfg', 53), ('unet_name', 55),
                          ('lora_name', 71), ('clip_name', 56), ('vae_name', 57)):
            self.assertEqual(flat[f'203:{nid}']['inputs'][name], overrides[name])
        # Connected Designer controls override saved, promoted fallback values.
        self.assertEqual(flat['203:82']['inputs']['width'], ('200', 1))
        self.assertEqual(flat['203:84']['inputs']['prompt'], ('200', 0))

    def test_stale_named_promoted_metadata_is_rejected(self):
        workflow = build()
        host = next(n for n in workflow['nodes'] if n['id'] == 203)
        host['widgets_values_named']['seed'] = 1
        with self.assertRaisesRegex(AssertionError, 'named/positional mismatch'):
            validate_recursive(workflow)

    def test_missing_promoted_widget_is_rejected(self):
        workflow = build()
        host = next(n for n in workflow['nodes'] if n['id'] == 203)
        host['widgets_values'].pop()
        with self.assertRaisesRegex(AssertionError, 'widget count mismatch'):
            validate_recursive(workflow)

    def test_missing_nonwidget_host_port_is_rejected(self):
        workflow = build()
        host = next(n for n in workflow['nodes'] if n['id'] == 203)
        host['inputs'].pop()
        workflow['links'] = [link for link in workflow['links'] if link[0] != 43]
        rebuild(workflow)
        with self.assertRaisesRegex(AssertionError, 'Missing subgraph input'):
            validate_recursive(workflow)

    def test_boundary_link_order_does_not_change_meaning(self):
        workflow = build()
        workflow['definitions']['subgraphs'][0]['inputs'][0]['linkIds'].reverse()
        validate_recursive(workflow)
        validate_layout_graph(workflow)

    def test_nested_subgraph_resolution(self):
        workflow = build()
        inner = workflow['definitions']['subgraphs'][0]
        host = next(n for n in workflow['nodes'] if n['id'] == 203)
        nested_host = copy.deepcopy(host)
        nested_host['id'] = 300
        nested_host['inputs'] = [
            {'name': port['name'], 'type': port['type'], 'link': None}
            for port in inner['inputs']]
        wrapper = {
            'id': 'nested-layout-test', 'nodes': [nested_host],
            'inputNode': {'id': -10}, 'outputNode': {'id': -20},
            'inputs': copy.deepcopy(inner['inputs']), 'outputs': copy.deepcopy(inner['outputs']),
            'state': {'lastNodeId': 300, 'lastLinkId': 0},
            'links': [object_link(slot+1, -10, slot, 300, slot, port['type'])
                      for slot, port in enumerate(inner['inputs'])]
                     + [object_link(99, 300, 0, -20, 0, 'IMAGE')],
        }
        host['type'] = wrapper['id']
        workflow['definitions']['subgraphs'].append(wrapper)
        rebuild(wrapper)
        validate_recursive(workflow)
        flat = flatten_connections(workflow)
        self.assertEqual(flat['203:300:84']['inputs']['image'], ('200', 3))
        self.assertEqual(flat['203:300:85']['inputs']['image_b'], ('72', 0))
        self.assertEqual(flat['203:300:53']['inputs']['steps'], 10)
        self.assertEqual(flat['29']['inputs']['images'], ('203:300:54', 0))

    def test_graph_cycle_is_rejected(self):
        workflow = build()
        graph = workflow['definitions']['subgraphs'][0]
        # Turn MODEL loader -> LoRA -> patch into patch -> LoRA -> patch.
        link = next(link for link in graph['links'] if link['id'] == 1)
        link['origin_id'] = 79
        old = next(n for n in graph['nodes'] if n['id'] == 55)
        old['outputs'][0]['links'] = []
        patch = next(n for n in graph['nodes'] if n['id'] == 79)
        patch['outputs'][0]['links'].append(1)
        with self.assertRaisesRegex(AssertionError, 'Graph cycle'):
            validate_recursive(workflow)


if __name__ == '__main__':
    unittest.main()
