"""Dependency-free graph validation against the pinned author workflow contract."""
from pathlib import Path
import hashlib
import json
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from krea2_character_sheet.compiler import compile_state
from tools.build_workflows import build


def validate(path, optional):
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


def run():
    return [validate(ROOT/'workflows'/name,optional) for optional,name in [(False,'Krea2_Character_Sheet_Designer.json'),(True,'Krea2_Layout_Reference_Designer_Experimental.json')]]

if __name__=='__main__':
    print(json.dumps(run(),indent=2))
