"""Static integrity and role checks for the sole user-supplied GUI template.

This is not a live frontend import, graphToPrompt export, or GPU validation.
"""
from pathlib import Path
import hashlib
import json
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from krea2_character_sheet.compiler import compile_state
from krea2_character_sheet.node import Krea2LayoutImageSheetDesigner
from tools.build_workflows import TEMPLATE, TEMPLATE_SHA256
from tools.workflow_graph import flatten_connections, graphs, promoted_values, validate_recursive


# Identity Edit 1.2.5 / 86f886da and the checked ComfyUI port contracts.
INPUT_PORTS = {
    57: [('vae_name', 'COMBO')],
    56: [('clip_name', 'COMBO')],
    82: [('width', 'INT'), ('height', 'INT')],
    55: [('unet_name', 'COMBO')],
    84: [('clip', 'CLIP'), ('image', 'IMAGE'), ('image_b', 'IMAGE'), ('prompt', 'STRING')],
    85: [('clip', 'CLIP'), ('image', 'IMAGE'), ('image_b', 'IMAGE')],
    73: [('pixels', 'IMAGE'), ('vae', 'VAE')],
    92: [('pixels', 'IMAGE'), ('vae', 'VAE')],
    71: [('model', 'MODEL'), ('lora_name', 'COMBO')],
    79: [('model', 'MODEL'), ('source_latent', 'LATENT'), ('source_latent_b', 'LATENT'),
         ('ref_boost_mask', 'MASK'), ('vae', 'VAE'), ('source_image', 'IMAGE'),
         ('source_image_b', 'IMAGE'), ('target_latent', 'LATENT')],
    53: [('model', 'MODEL'), ('positive', 'CONDITIONING'), ('negative', 'CONDITIONING'),
         ('latent_image', 'LATENT'), ('seed', 'INT'), ('steps', 'INT'), ('cfg', 'FLOAT')],
    54: [('samples', 'LATENT'), ('vae', 'VAE')],
}
NODE_TYPES = {57: 'VAELoader', 56: 'CLIPLoader', 82: 'EmptySD3LatentImage', 55: 'UNETLoader',
              84: 'Krea2EditGroundedEncode', 85: 'Krea2EditGroundedEncode', 73: 'VAEEncode',
              92: 'VAEEncode', 71: 'LoraLoaderModelOnly', 79: 'Krea2EditModelPatch',
              53: 'KSampler', 54: 'VAEDecode'}


def validate_layout_graph(workflow):
    """Validate topology, saved controls, runtime Designer ports and image roles."""
    validate_recursive(workflow)
    assert str(uuid.UUID(workflow['id'])) == workflow['id'] and workflow['version'] == 0.4
    nodes = {node['id']: node for node in workflow['nodes']}
    graph, = workflow['definitions']['subgraphs']
    inner = {node['id']: node for node in graph['nodes']}
    assert set(nodes) == {72, 200, 202, 203, 29}, 'Unexpected root template nodes'
    assert set(inner) == set(NODE_TYPES), 'Unexpected subgraph nodes'
    assert nodes[203]['type'] == graph['id']
    assert nodes[200]['type'] == 'Krea2LayoutImageSheetDesigner'
    assert [(p['name'], p['type']) for p in nodes[200]['outputs']] == list(zip(
        Krea2LayoutImageSheetDesigner.RETURN_NAMES, Krea2LayoutImageSheetDesigner.RETURN_TYPES))
    assert nodes[200]['inputs'] == [] and len(nodes[200]['widgets_values']) == 1
    for nid, ports in INPUT_PORTS.items():
        assert inner[nid]['type'] == NODE_TYPES[nid], (nid, 'Node type changed')
        assert [(p['name'], p['type']) for p in inner[nid]['inputs']] == ports, (nid, 'Input port contract')
    for g in graphs(workflow):
        for node in g['nodes']:
            if 'widgets_values_named' in node:
                assert list(node['widgets_values_named'].values()) == node['widgets_values'], 'Named/positional widget mismatch'
    compiled = compile_state(nodes[200]['widgets_values'][0], layout_reference=True, builtin_layout=True)
    assert (compiled['width'], compiled['height']) == (1696, 768)
    assert inner[84]['widgets_values'] == [compiled['prompt'], 768, '']
    assert inner[85]['widgets_values'] == ['', 768, '']
    assert inner[79]['widgets_values'] == [4, 1, 'fit']
    assert inner[71]['widgets_values'][1] == 1
    assert inner[53]['widgets_values'][1:] == ['fixed', 10, 1, 'euler', 'simple', 1]
    promoted = promoted_values(nodes[203], graph)
    assert promoted['prompt'] == compiled['prompt']
    assert [promoted[name] for name in ('width', 'height', 'seed', 'steps', 'cfg')] == [
        1696, 768, 1088049369132323, 10, 1]
    assert promoted['unet_name'] == r'krea2\krea2_turbo_int8_convrot.safetensors'
    assert promoted['lora_name'] == r'krea2\krea2_identity_edit_v1_2.safetensors'
    assert promoted['vae_name'] == 'qwen_image_vae.safetensors'
    assert promoted['clip_name'] == 'qwen3vl_4b_fp8_scaled.safetensors'
    images = [node for g in graphs(workflow) for node in g['nodes'] if node['type'] == 'LoadImage']
    assert len(images) == 1 and images[0]['id'] == 72, 'External layout image must not be required'
    flat = flatten_connections(workflow)
    layout, identity = ('200', 3), ('72', 0)
    for nid in ('203:84', '203:85'):
        assert flat[nid]['inputs']['image'] == layout, 'GroundedEncode A must be built-in layout'
        assert flat[nid]['inputs']['image_b'] == identity, 'GroundedEncode B must be character'
    assert flat['203:84']['inputs']['prompt'] == ('200', 0)
    assert flat['203:73']['inputs']['pixels'] == layout
    assert flat['203:92']['inputs']['pixels'] == identity
    patch = flat['203:79']['inputs']
    assert patch['source_latent'] == ('203:73', 0)
    assert patch['source_latent_b'] == ('203:92', 0)
    assert patch['source_image'] == layout and patch['source_image_b'] == identity
    assert patch['target_latent'] == flat['203:53']['inputs']['latent_image'] == ('203:82', 0)
    assert flat['203:82']['inputs']['width'] == ('200', 1)
    assert flat['203:82']['inputs']['height'] == ('200', 2)
    for node_id in ('203:73', '203:92', '203:79', '203:54'):
        assert flat[node_id]['inputs']['vae'] == ('203:57', 0)
    for name, nid in (('seed', 53), ('steps', 53), ('cfg', 53), ('vae_name', 57),
                      ('clip_name', 56), ('unet_name', 55), ('lora_name', 71)):
        assert flat[f'203:{nid}']['inputs'][name] == promoted[name], (name, 'Promoted control lost')
    assert flat['203:56']['inputs']['type'] == 'krea2'
    assert flat['29']['inputs']['images'] == ('203:54', 0)
    assert nodes[29]['outputs'] == [{'name': 'images', 'type': 'IMAGE', 'links': None}]
    assert nodes[203]['properties']['previewExposures'][0]['sourceNodeId'] == '53'
    assert (ROOT/'tools/upstream/LICENSE-IdentityEdit').read_text() in nodes[202]['widgets_values'][0]
    return flat


def validate(path=TEMPLATE):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == TEMPLATE_SHA256, 'User-supplied template bytes changed'
    workflow = json.loads(raw)
    flat = validate_layout_graph(workflow)
    return {'file': path.name, 'nodes': len(workflow['nodes']), 'links': len(workflow['links']),
            'subgraphs': 1, 'subgraph_nodes': 12, 'subgraph_links': 35,
            'flattened_leaf_nodes': len(flat),
            'executable_leaf_nodes': sum(node['type'] != 'Note' for node in flat.values()),
            'source_bytes_preserved': True,
            'validation_scope': 'recursive static links, saved promoted controls and flattened source paths; not live graphToPrompt',
            'status': 'static_pass', 'sha256': hashlib.sha256(raw).hexdigest()}


def run():
    assert sorted((ROOT/'workflows').rglob('*.json')) == [TEMPLATE], 'Exactly one distributed workflow is required'
    # Historical source files are referenced by immutable upstream links, not
    # shipped as additional importable templates elsewhere in the package.
    for path in ROOT.rglob('*.json'):
        if {'.git', 'node_modules', '.venv', '__pycache__'}.intersection(path.relative_to(ROOT).parts):
            continue
        if path == ROOT/'verification/workflow_results.json':
            # This report is an output, often truncated by shell redirection
            # before validation starts; it is not a distribution input.
            continue
        value = json.loads(path.read_text())
        if isinstance(value, dict) and 'nodes' in value and 'links' in value:
            assert path == TEMPLATE, 'Additional GUI workflow outside workflows/'
    return [validate()]


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
