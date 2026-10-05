"""Build two standalone GUI workflows; no network, models, or user image bytes.

The upstream JSON remains unchanged. Static payload candidates are intentionally
not distributed as live Frontend graphToPrompt results.
"""
from pathlib import Path
import copy
import hashlib
import json
import sys
import uuid
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from krea2_character_sheet.compiler import compile_state
from tools.workflow_graph import object_link, rebuild
SOURCE = ROOT / 'tools/upstream/krea2_identity_edit.json'
LAYOUT_SOURCE = ROOT / 'tools/upstream/krea2_designer_subgraph.json'
LAYOUT_SOURCE_SHA256 = '2054a784eea21ebce5342f14fbed87efc99a79aec63d22575d0bb4b5d79a0b03'
AUTHOR_SHA = '86f886dac23013d88996e3a2e99093ba44d322fb'
SOURCE_BLOB = 'a707d8d27cb8504f8a63ab38babe3855ac797c59'
STATE = {'schema_version': 1, 'views': ['face_front','face_left','body_front','body_left','body_back'], 'size': {'mode': 'manual','body_height':672,'manual_width':1696,'manual_height':768}}


def build(layout_reference=False):
    if layout_reference:
        return build_layout_image()
    raw = SOURCE.read_bytes()
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == SOURCE_BLOB
    source = json.loads(raw)
    keep = {29,53,54,55,56,57,71,72,73,79,82,84,85}
    if layout_reference: keep |= {90,92}
    nodes = {n['id']: copy.deepcopy(n) for n in source['nodes'] if n['id'] in keep}
    links = [copy.deepcopy(l) for l in source['links'] if l[1] in keep and l[3] in keep]
    state_json = json.dumps(STATE,separators=(',', ':'))
    compiled = compile_state(state_json,layout_reference=layout_reference)
    node_type = 'Krea2LayoutReferenceSheetDesigner' if layout_reference else 'Krea2CharacterSheetDesigner'
    title = 'Krea2 Layout Reference Sheet Designer (Experimental)' if layout_reference else 'Krea2 Character Sheet Designer'
    nodes[200] = {'id':200,'type':node_type,'pos':[25,80],'size':[870,930],'flags':{},'order':0,'mode':0,'inputs':[],
        'outputs':[{'name':name,'type':typ,'links':None} for name,typ in [('prompt','STRING'),('width','INT'),('height','INT')]],
        'properties':{'Node name for S&R':node_type},'widgets_values':[state_json]}
    nodes[82]['inputs'] = [{'name':name,'type':'INT','widget':{'name':name},'link':None} for name in ('width','height')]
    nodes[82]['widgets_values'] = [compiled['width'],compiled['height'],1]
    nodes[84]['inputs'].append({'name':'prompt','type':'STRING','widget':{'name':'prompt'},'link':None})
    nodes[84]['widgets_values'] = [compiled['prompt'],768,'']
    next_link=max(l[0] for l in links)+1
    for out,dst,port,typ in [(0,84,3,'STRING'),(1,82,0,'INT'),(2,82,1,'INT')]:
        links.append([next_link,200,out,dst,port,typ]);next_link+=1
    # Rebuild both ends. No stale links survive branch removal or conversion.
    for node in nodes.values():
        node['mode']=0
        for port in node['inputs']:port['link']=None
        for port in node['outputs']:port['links']=None
    for lid,src,slot,dst,port,typ in links:
        nodes[src]['outputs'][slot]['links']=(nodes[src]['outputs'][slot]['links'] or [])+[lid]
        nodes[dst]['inputs'][port]['link']=lid
    positions={55:[950,80],56:[950,230],57:[950,400],71:[1270,80],72:[950,570],73:[1520,690],79:[1920,80],82:[1270,290],84:[1580,80],85:[1580,470],53:[2400,80],54:[2780,80],29:[3100,80],90:[950,1130],92:[1520,1260]}
    for nid,pos in positions.items():
        if nid in nodes:nodes[nid]['pos']=pos
    nodes[84]['size']=[310,330]
    nodes[29]['size']=[680,810]
    nodes[29]['widgets_values']=['Krea2_Designer_LayoutRef' if layout_reference else 'Krea2_Designer']
    nodes[53]['widgets_values']=[1088049369132323,'fixed',10,1,'euler','simple',1]
    nodes[71]['widgets_values']=['SELECT_IDENTITY_EDIT_V1_2.safetensors',1]
    nodes[71]['title']='Required: Identity Edit v1.2 LoRA / strength 1.0'
    nodes[82]['title']='Designer output dimensions / shared target latent'
    nodes[79]['widgets_values']=[4,1,'fit']
    nodes[79]['title']='Identity Edit / identity boost 4 / fit'
    nodes[84]['title']='Positive / prompt supplied by Designer'
    nodes[85]['title']='Negative / blank / same reference order'
    nodes[85]['widgets_values']=['',768,'']
    if layout_reference:
        nodes[72]['title']='Image 1: LAYOUT EXAMPLE / experimental'
        nodes[72]['widgets_values']=['SELECT_LAYOUT_EXAMPLE.png','image']
        nodes[90]['title']='Image 2: CHARACTER IDENTITY / required'
        nodes[90]['widgets_values']=['SELECT_CHARACTER_REFERENCE.png','image']
        roles='Image 1 = レイアウト例、Image 2 = 人物リファレンス。作者のscene-first / subject-second順序。\n2枚とも外観へ影響し、レイアウト専用分離は保証されません。人物が写る例から顔や服が混ざる場合は標準版を使用。\nUIマネキンは自動接続しません。選択したビューに合うレイアウト例を手動で選択。\nref_boost=4は最後の参照（人物）、ref_boost_a=1は最初の参照（レイアウト）。'
    else:
        nodes[72]['title']='CHARACTER IDENTITY reference / required'
        nodes[72]['widgets_values']=['SELECT_CHARACTER_REFERENCE.png','image']
        roles='人物リファレンスは必須。構図はDesignerの文章のみで指示します。\nUIのマネキン画像は表示専用で、生成へ接続されません。\n画像1枚はVAE外観経路、画像を読むGroundedEncode、pixel pathへ接続済み。'
    note = {'id':201,'type':'Note','pos':[25,1070],'size':[870,310],'flags':{},'order':0,'mode':0,'inputs':[],'outputs':[],'properties':{},'title':title+' / 使い方','widgets_values':[
        roles+'\n\nモデル・LoRA・参照画像の仮名を手元のファイルへ変更して実行。\n初期1696×768・5ビュー・10 steps / CFG 1 / euler / simple。\n同じlatentをKSamplerとtarget_latentへ接続。高解像度は自動縮小しません。まず約1MP〜2MP以下から確認。\nUIは7ビュー・8部位入力・Auto/Manual・日本語/英語対応。顔と全身のprofileは画面左向き。\n静的検証のみ。実ComfyUIの読込、Queue、GPU品質は未検証。\n専用ノード lbouaraba/comfyui-krea2edit と Identity Edit v1.2 LoRAが別途必要。Krea社公式のsheet workflowではありません。']}
    nodes[201]=note
    license_note=copy.deepcopy(note);license_note.update(id=202,pos=[25,1420],size=[870,220],flags={'collapsed':True},title='Upstream Apache-2.0 license / workflow provenance',widgets_values=[
        f'Workflow derived from lbouaraba/comfyui-krea2edit {AUTHOR_SHA}. Modified 2026-10-05: Designer node, dynamic dimensions/prompt, role-labelled references, fixed seed, notes.\n\n'+(ROOT/'tools/upstream/LICENSE-IdentityEdit').read_text()]);nodes[202]=license_note
    pending=dict(nodes);ordered=[]
    while pending:
        ready=[nid for nid in pending if not any(l[3]==nid and l[1] in pending for l in links)]
        assert ready,'Cycle'
        for nid in ready:ordered.append(pending.pop(nid))
    for order,node in enumerate(ordered):node['order']=order
    return {'id':str(uuid.uuid5(uuid.NAMESPACE_URL,'https://github.com/ukr8b3g-cmyk/Krea2-Character-Sheet-Designer#'+node_type)),
        'revision':0,'last_node_id':max(nodes),'last_link_id':max(l[0] for l in links),'nodes':ordered,'links':links,'groups':[],
        'config':{},'extra':{'ds':{'scale':0.65,'offset':[70,30]},'krea2_designer_provenance':{
            'source_commit':AUTHOR_SHA,'source_workflow_blob':SOURCE_BLOB,'identity_edit_version_checked':'1.2.5',
            'variant':'layout_reference_experimental' if layout_reference else 'identity_only',
            'layout_reference_isolation':'prompt_guidance_only' if layout_reference else 'not_used',
            'validation':'static only; real ComfyUI/GPU not run'}},'version':0.4}


def build_layout_image():
    """Adapt the supplied subgraph workflow, with built-in layout first.

    The sanitized source retains its subgraph IDs, promoted controls, named
    widget values, preview exposure and sampling settings. Only the second
    reference branch and the Designer's generated layout output are added.
    """
    raw = LAYOUT_SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == LAYOUT_SOURCE_SHA256
    workflow = json.loads(raw)
    nodes = {node['id']: node for node in workflow['nodes']}
    graph, = workflow['definitions']['subgraphs']
    inner = {node['id']: node for node in graph['nodes']}
    designer, host = nodes[200], nodes[203]
    state_json = designer['widgets_values'][0]
    compiled = compile_state(state_json, layout_reference=True, builtin_layout=True)
    node_type = 'Krea2LayoutImageSheetDesigner'
    designer['type'] = node_type
    designer['title'] = 'Krea2 Layout Image Sheet Designer (Experimental)'
    designer['properties']['Node name for S&R'] = node_type
    # This is a new node contract; the old three-output type remains compatible.
    designer['properties'].pop('ver', None)
    designer['outputs'].append({'name': 'layout_image', 'type': 'IMAGE', 'links': None})
    designer['pos'] = [25, 80]
    graph['name'] = 'Krea2 Identity Edit / built-in layout + character'
    graph['inputs'][0]['label'] = 'Image 1: built-in layout'
    graph['inputs'].append({
        'id': str(uuid.uuid5(uuid.NAMESPACE_URL, graph['id'] + '#image_b')),
        'name': 'image_b', 'type': 'IMAGE', 'label': 'Image 2: character identity',
        'linkIds': [], 'pos': [866, 645]})
    graph['inputNode']['bounding'][3] += 20
    # Explicitly expose every supplied promoted control, in boundary order.
    # Matching names and preserving both value formats avoids silent shifts.
    existing = {port['name']: port for port in host['inputs']}
    host['inputs'] = []
    for port in graph['inputs']:
        entry = copy.deepcopy(existing.get(port['name'], {}))
        entry.update(name=port['name'], type=port['type'], link=None)
        if port['type'] != 'IMAGE':
            entry['widget'] = {'name': port['name']}
        if 'label' in port:
            entry['label'] = port['label']
        host['inputs'].append(entry)
    host['title'] = graph['name']
    host['pos'], host['size'] = [950, 80], [600, 780]
    host['widgets_values'][0] = compiled['prompt']
    host['widgets_values_named']['prompt'] = compiled['prompt']
    inner[84]['widgets_values'][0] = compiled['prompt']
    inner[84]['widgets_values_named']['prompt'] = compiled['prompt']
    inner[84]['title'] = 'Positive / image 1 layout, image 2 character'
    inner[85]['title'] = 'Negative / blank / same layout-first order'
    inner[73]['title'] = 'Image 1: built-in layout / VAE'
    identity_vae = copy.deepcopy(inner[73])
    identity_vae.update(id=92, title='Image 2: character identity / VAE', pos=[1520, 920])
    graph['nodes'].append(identity_vae)
    image_b_slot = len(graph['inputs']) - 1
    graph['links'].extend([
        object_link(43, -10, image_b_slot, 84, 2, 'IMAGE'),
        object_link(44, -10, image_b_slot, 85, 2, 'IMAGE'),
        object_link(45, -10, image_b_slot, 92, 0, 'IMAGE'),
        object_link(46, -10, image_b_slot, 79, 6, 'IMAGE'),
        object_link(47, 57, 0, 92, 1, 'VAE'),
        object_link(48, 92, 0, 79, 2, 'LATENT'),
    ])
    # Replace the former single-image source with the generated layout and add
    # the character exclusively to B, including both raw-pixel and latent paths.
    workflow['links'][0] = [31, 200, 3, 203, 0, 'IMAGE']
    workflow['links'].extend([
        [43, 72, 0, 203, image_b_slot, 'IMAGE'],
        [44, 200, 3, 204, 0, 'IMAGE'],
    ])
    nodes[72]['title'] = 'Image 2: CHARACTER IDENTITY / required'
    nodes[72]['pos'], nodes[72]['size'] = [25, 1130], [430, 550]
    nodes[29]['widgets_values'] = ['Krea2_Designer_LayoutImage']
    nodes[29]['widgets_values_named'] = {'filename_prefix': 'Krea2_Designer_LayoutImage'}
    nodes[29]['pos'] = [1640, 80]
    workflow['nodes'].append({
        'id': 204, 'type': 'PreviewImage', 'pos': [950, 940], 'size': [600, 340],
        'flags': {}, 'order': 0, 'mode': 0, 'inputs': [{'name': 'images', 'type': 'IMAGE', 'link': None}],
        'outputs': [], 'properties': {'Node name for S&R': 'PreviewImage'},
        'title': 'Image 1: generated layout / actual model input', 'widgets_values': []})
    nodes[201].update(pos=[25, 1740], size=[870, 360],
        title='Krea2 Layout Image Sheet Designer / 使い方', widgets_values=[
            'Image 1 = Designer内蔵のlayout_image、Image 2 = 人物リファレンス（必須）。\n'
            '選択ビュー・Auto/Manual・出力寸法から白背景のレイアウト画像を生成して接続します。外部レイアウト画像は不要です。\n'
            'positive / negative / VAE / pixel pathの全経路でレイアウト→人物の順序です。\n'
            'ref_boost=4は最後の参照（人物）、ref_boost_a=1は最初の参照（レイアウト）。\n'
            'サブグラフ表面でseed / steps / CFG / VAE / CLIP / diffusion model / LoRAを選択できます。\n'
            'モデル・LoRA・人物画像の仮名を手元のファイルへ変更して実行。int8-convrotは提供workflowの選択を維持。重みは同梱しません。\n'
            '初期1696×768・5ビュー・10 steps / CFG 1 / euler / simple / denoise 1 / fixed seed。\n'
            '同じlatentをKSamplerとtarget_latentへ接続。高解像度は自動縮小しません。まず約1MP〜2MP以下から確認。\n'
            '白背景・枠線なし・profileは画面左向き。内蔵マネキンの外観が混ざる可能性があり、厳密な配置・人物保持は保証しません。\n'
            '静的検証のみ。実ComfyUIの読込、Queue、GPU品質は未検証。\n'
            '専用ノード lbouaraba/comfyui-krea2edit と Identity Edit v1.2 LoRAが別途必要。Krea社公式workflowではありません。'])
    nodes[201].pop('widgets_values_named', None)
    nodes[202]['pos'] = [25, 2150]
    nodes[202]['widgets_values'][0] = (
        'Modified 2026-10-05 from the supplied subgraph workflow: built-in layout output, '
        'layout-first / identity-second branches, promoted controls, sanitized filenames.\n\n'
        + nodes[202]['widgets_values'][0])
    nodes[202].pop('widgets_values_named', None)
    workflow['id'] = str(uuid.uuid5(uuid.NAMESPACE_URL,
        'https://github.com/ukr8b3g-cmyk/Krea2-Character-Sheet-Designer#' + node_type))
    workflow['extra']['ds'] = {'scale': 0.55, 'offset': [70, 30]}
    workflow['extra']['krea2_designer_provenance'].update(
        variant='builtin_layout_image_experimental',
        layout_reference_isolation='prompt_guidance_only',
        layout_source='Designer layout_image output / shared selected-view geometry',
        sanitized_source_sha256=LAYOUT_SOURCE_SHA256,
        validation='recursive static graph and boundary flattening only; real ComfyUI/GPU not run')
    rebuild(graph)
    rebuild(workflow)
    return workflow

if __name__=='__main__':
    for optional,name in [(False,'Krea2_Character_Sheet_Designer.json'),(True,'Krea2_Layout_Reference_Designer_Experimental.json')]:
        result=build(optional);path=ROOT/'workflows'/name;path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(name,len(result['nodes']),'nodes',len(result['links']),'links')
