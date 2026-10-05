"""Dependency-free graph validation against the pinned author workflow contract."""
from pathlib import Path
import hashlib
import json
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from krea2_character_sheet.compiler import compile_state
from tools.build_workflows import build, LAYOUT_SOURCE
from tools.workflow_graph import flatten_connections, graphs, validate_recursive


def validate(path, optional):
    if optional:
        return validate_layout(path)
    w=json.loads(path.read_text());source=json.loads((ROOT/'tools/upstream/krea2_identity_edit.json').read_text())
    original={n['id']:n for n in source['nodes']}
    assert str(uuid.UUID(w['id']))==w['id'] and w['version']==0.4
    assert w==build(optional),'Generated workflow drift'
    nodes={n['id']:n for n in w['nodes']};links={l[0]:l for l in w['links']}
    assert len(nodes)==len(w['nodes']) and len(links)==len(w['links'])
    assert w['last_node_id']==max(nodes) and w['last_link_id']==max(links)
    for lid,a,ai,b,bi,typ in w['links']:
        src,dst=nodes[a]['outputs'][ai],nodes[b]['inputs'][bi]
        assert src['type']==dst['type']==typ
        assert lid in src['links'] and dst['link']==lid
        assert nodes[a]['order']<nodes[b]['order']
    for n in nodes.values():
        assert n['mode']==0
        for i,p in enumerate(n['inputs']):
            if p.get('link') is not None:assert links[p['link']][3:5]==[n['id'],i]
        for i,p in enumerate(n['outputs']):
            for lid in p.get('links') or []:assert links[lid][1:3]==[n['id'],i]
        if n['id'] in original:
            baseline=original[n['id']]
            actual_ports=[(p['name'],p['type']) for p in n['inputs']]
            old_ports=[(p['name'],p['type']) for p in baseline['inputs']]
            if n['id']==84:old_ports.append(('prompt','STRING'))
            assert actual_ports==old_ports,(n['id'],'input contract')
            assert [(p['name'],p['type']) for p in n['outputs']]==[(p['name'],p['type']) for p in baseline['outputs']],(n['id'],'output contract')
            assert len(n['widgets_values'])==len(baseline['widgets_values'])
    keep=set(nodes)&set(original)
    expected=[l for l in source['links'] if l[1] in keep and l[3] in keep]
    assert [l for l in w['links'] if l[1]!=200]==expected
    assert nodes[200]['type']==('Krea2LayoutReferenceSheetDesigner' if optional else 'Krea2CharacterSheetDesigner')
    assert len(nodes[200]['widgets_values'])==1 and nodes[200]['inputs']==[]
    raw=nodes[200]['widgets_values'][0];compiled=compile_state(raw,layout_reference=optional)
    assert (compiled['width'],compiled['height'])==(1696,768)
    assert nodes[84]['widgets_values']==[compiled['prompt'],768,'']
    assert nodes[85]['widgets_values']==['',768,'']
    assert nodes[82]['widgets_values']==[1696,768,1]
    assert nodes[79]['widgets_values']==[4,1,'fit']
    assert nodes[53]['widgets_values']==[1088049369132323,'fixed',10,1,'euler','simple',1]
    assert nodes[71]['widgets_values']==['SELECT_IDENTITY_EDIT_V1_2.safetensors',1]
    assert nodes[56]['widgets_values'][1]=='krea2'
    assert len([n for n in nodes.values() if n['type']=='LoadImage'])==(2 if optional else 1)
    assert nodes[82]['outputs'][0]['links']==[24,27]
    assert nodes[53]['inputs'][3]['link']==24 and nodes[79]['inputs'][7]['link']==27
    for nid in (84,85):
        assert links[nodes[nid]['inputs'][1]['link']][1]==72
        if optional:assert links[nodes[nid]['inputs'][2]['link']][1]==90
        else:assert nodes[nid]['inputs'][2]['link'] is None
    assert links[nodes[79]['inputs'][5]['link']][1]==72
    if optional:
        assert links[nodes[79]['inputs'][6]['link']][1]==90
        assert links[nodes[79]['inputs'][2]['link']][1]==92
        assert nodes[72]['widgets_values'][0]=='SELECT_LAYOUT_EXAMPLE.png'
        assert nodes[90]['widgets_values'][0]=='SELECT_CHARACTER_REFERENCE.png'
    else:
        assert nodes[79]['inputs'][2]['link'] is None and nodes[79]['inputs'][6]['link'] is None
        assert nodes[72]['widgets_values'][0]=='SELECT_CHARACTER_REFERENCE.png'
    assert (ROOT/'tools/upstream/LICENSE-IdentityEdit').read_text() in nodes[202]['widgets_values'][0]
    assert not any('mannequin-atlas' in str(n) for n in nodes.values())
    return {'file':path.name,'nodes':len(nodes),'links':len(links),'status':'static_pass','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def validate_layout_graph(workflow):
    """Check all serialized graphs and actual sources beyond the host boundary."""
    validate_recursive(workflow)
    source = json.loads(LAYOUT_SOURCE.read_text())
    source_nodes = {node['id']: node for node in source['nodes']}
    nodes = {node['id']: node for node in workflow['nodes']}
    graph, = workflow['definitions']['subgraphs']
    source_graph, = source['definitions']['subgraphs']
    inner = {node['id']: node for node in graph['nodes']}
    baseline = {node['id']: node for node in source_graph['nodes']}
    assert graph['id'] == source_graph['id'], 'Supplied subgraph replaced'
    assert set(inner) == set(baseline) | {92}
    assert nodes[203]['type'] == graph['id']
    assert nodes[203]['properties']['previewExposures'] == source_nodes[203]['properties']['previewExposures']
    assert nodes[200]['type'] == 'Krea2LayoutImageSheetDesigner'
    assert [(p['name'], p['type']) for p in nodes[200]['outputs']] == [
        ('prompt', 'STRING'), ('width', 'INT'), ('height', 'INT'), ('layout_image', 'IMAGE')]
    assert nodes[200]['inputs'] == [] and len(nodes[200]['widgets_values']) == 1
    assert nodes[200]['widgets_values'] == source_nodes[200]['widgets_values']
    compiled = compile_state(nodes[200]['widgets_values'][0], layout_reference=True, builtin_layout=True)
    assert (compiled['width'], compiled['height']) == (1696, 768)
    assert inner[84]['widgets_values'] == [compiled['prompt'], 768, '']
    assert inner[84]['widgets_values_named']['prompt'] == compiled['prompt']
    promoted = source_nodes[203]['widgets_values_named'].copy()
    promoted['prompt'] = compiled['prompt']
    assert nodes[203]['widgets_values_named'] == promoted
    assert nodes[203]['widgets_values'] == list(promoted.values())
    assert [p['name'] for p in graph['inputs']] == [p['name'] for p in source_graph['inputs']] + ['image_b']
    for node_id in (53, 55, 56, 57, 71, 79, 82, 85):
        assert inner[node_id]['widgets_values'] == baseline[node_id]['widgets_values'], (node_id, 'Default changed')
        assert inner[node_id]['widgets_values_named'] == baseline[node_id]['widgets_values_named']
    images = [node for g in graphs(workflow) for node in g['nodes'] if node['type'] == 'LoadImage']
    assert len(images) == 1 and images[0]['id'] == 72, 'External layout image must not be required'
    assert images[0]['widgets_values'] == ['SELECT_CHARACTER_REFERENCE.png', 'image']
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
    assert flat['204']['inputs']['images'] == layout, 'Preview must show actual model input'
    assert flat['29']['inputs']['images'] == ('203:54', 0)
    assert (ROOT/'tools/upstream/LICENSE-IdentityEdit').read_text() in nodes[202]['widgets_values'][0]
    return flat


def validate_layout(path):
    workflow = json.loads(path.read_text())
    assert str(uuid.UUID(workflow['id'])) == workflow['id'] and workflow['version'] == 0.4
    assert workflow == build(True), 'Generated workflow drift'
    flat = validate_layout_graph(workflow)
    return {'file': path.name, 'nodes': len(workflow['nodes']), 'links': len(workflow['links']),
            'subgraphs': len(workflow['definitions']['subgraphs']), 'flattened_nodes': len(flat),
            'validation_scope': 'recursive static links, promoted controls and flattened source paths; not live graphToPrompt',
            'status': 'static_pass', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def run():
    return [validate(ROOT/'workflows'/name,optional) for optional,name in [(False,'Krea2_Character_Sheet_Designer.json'),(True,'Krea2_Layout_Reference_Designer_Experimental.json')]]

if __name__=='__main__':
    print(json.dumps(run(),indent=2))
