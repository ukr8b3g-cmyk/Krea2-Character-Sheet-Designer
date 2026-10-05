import unittest
import copy
import hashlib
import json
from tools.build_workflows import ROOT, build
from tools.validate_workflows import run, validate_layout_graph
from tools.workflow_graph import flatten_connections, object_link, rebuild, validate_recursive

class WorkflowContracts(unittest.TestCase):
    def test_both_graphs(self):
        self.assertEqual([r['status'] for r in run()],['static_pass','static_pass'])

    def test_basic_workflow_is_byte_identical(self):
        raw = (ROOT/'workflows/Krea2_Character_Sheet_Designer.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '1d36950416ebbaa9f6db677209a1ee1c4474ab8fb6643830664a3cbe94606a12')
        self.assertEqual(raw, (json.dumps(build(False), ensure_ascii=False, indent=2)+'\n').encode())

    def test_builtin_layout_sources_cross_subgraph_boundary(self):
        flat = validate_layout_graph(build(True))
        self.assertEqual(flat['203:84']['inputs']['image'], ('200', 3))
        self.assertEqual(flat['203:84']['inputs']['image_b'], ('72', 0))
        self.assertEqual(flat['203:53']['inputs']['latent_image'], ('203:82', 0))
        self.assertEqual(flat['203:79']['inputs']['target_latent'], ('203:82', 0))

    def test_reference_swap_is_rejected_after_valid_link_rebuild(self):
        workflow = build(True)
        # A graph can have perfect reciprocal links and still condition on the
        # wrong image. The flattened semantic checks must catch that mistake.
        workflow['links'][0][1:3] = [72, 0]
        workflow['links'][5][1:3] = [200, 3]
        rebuild(workflow)
        validate_recursive(workflow)
        with self.assertRaisesRegex(AssertionError, 'A must be built-in layout'):
            validate_layout_graph(workflow)

    def test_missing_negative_b_and_stale_boundary_are_rejected(self):
        workflow = build(True)
        graph = workflow['definitions']['subgraphs'][0]
        graph['links'] = [link for link in graph['links'] if link['id'] != 44]
        rebuild(graph)
        validate_recursive(workflow)
        with self.assertRaises((AssertionError, KeyError)):
            validate_layout_graph(workflow)
        graph['inputs'][-1]['linkIds'].append(9999)
        with self.assertRaisesRegex(AssertionError, 'Stale boundary'):
            validate_recursive(workflow)

    def test_promoted_control_changes_reach_leaf_nodes(self):
        workflow = build(True)
        host = next(node for node in workflow['nodes'] if node['id'] == 203)
        overrides = {'seed': 123, 'steps': 15, 'cfg': 1.5,
                     'unet_name': 'selected_model.safetensors',
                     'lora_name': 'selected_lora.safetensors',
                     'clip_name': 'selected_clip.safetensors',
                     'vae_name': 'selected_vae.safetensors'}
        host['widgets_values_named'].update(overrides)
        flat = flatten_connections(workflow)
        for name, nid in (('seed', 53), ('steps', 53), ('cfg', 53), ('unet_name', 55),
                          ('lora_name', 71), ('clip_name', 56), ('vae_name', 57)):
            self.assertEqual(flat[f'203:{nid}']['inputs'][name], overrides[name])

    def test_nested_subgraph_resolution(self):
        workflow = build(True)
        inner = workflow['definitions']['subgraphs'][0]
        host = next(node for node in workflow['nodes'] if node['id'] == 203)
        nested_host = copy.deepcopy(host)
        nested_host['id'] = 300
        wrapper = {
            'id': 'nested-layout-test', 'nodes': [nested_host],
            'inputNode': {'id': -10}, 'outputNode': {'id': -20},
            'inputs': copy.deepcopy(inner['inputs']), 'outputs': copy.deepcopy(inner['outputs']),
            'state': {'lastNodeId': 300, 'lastLinkId': 0},
            'links': [object_link(slot + 1, -10, slot, 300, slot, port['type'])
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

if __name__=='__main__':unittest.main()
