"""Static ComfyUI graph checks, including subgraph boundary resolution.

This is deliberately not a substitute for the frontend's live graphToPrompt.
Both root tuple links and subgraph object links are supported.
"""
import copy


def link_tuple(link):
    if isinstance(link, dict):
        return tuple(link[k] for k in (
            'id', 'origin_id', 'origin_slot', 'target_id', 'target_slot', 'type'))
    return tuple(link)


def object_link(lid, source, slot, target, port, kind):
    return dict(zip(('id', 'origin_id', 'origin_slot', 'target_id', 'target_slot', 'type'),
                    (lid, source, slot, target, port, kind)))


def graphs(workflow):
    yield workflow
    for graph in workflow.get('definitions', {}).get('subgraphs', []):
        yield from graphs(graph)


def rebuild(graph):
    """Synchronize link endpoints and topological order without changing links."""
    nodes = {node['id']: node for node in graph['nodes']}
    input_id = graph.get('inputNode', {}).get('id')
    output_id = graph.get('outputNode', {}).get('id')
    for node in nodes.values():
        for port in node.get('inputs', []):
            port['link'] = None
        for port in node.get('outputs', []):
            port['links'] = None
    for port in graph.get('inputs', []) + graph.get('outputs', []):
        port['linkIds'] = []
    links = [link_tuple(link) for link in graph['links']]
    for lid, source, slot, target, port, _ in links:
        if source == input_id:
            graph['inputs'][slot]['linkIds'].append(lid)
        else:
            output = nodes[source]['outputs'][slot]
            output['links'] = (output['links'] or []) + [lid]
        if target == output_id:
            graph['outputs'][port]['linkIds'].append(lid)
        else:
            nodes[target]['inputs'][port]['link'] = lid
    pending = dict(nodes)
    ordered = []
    while pending:
        ready = [nid for nid in pending if not any(
            target == nid and source in pending for _, source, _, target, _, _ in links)]
        assert ready, 'Graph cycle'
        for nid in ready:
            ordered.append(pending.pop(nid))
    for order, node in enumerate(ordered):
        node['order'] = order
    graph['nodes'] = ordered
    if 'state' in graph:
        graph['state']['lastNodeId'] = max(graph['state']['lastNodeId'], max(nodes))
        graph['state']['lastLinkId'] = max(link[0] for link in links)
    else:
        graph['last_node_id'] = max(nodes)
        graph['last_link_id'] = max(link[0] for link in links)


def validate_recursive(workflow):
    definitions = {graph['id']: graph for graph in graphs(workflow) if graph is not workflow}
    for graph in graphs(workflow):
        nodes = {node['id']: node for node in graph['nodes']}
        links = {link_tuple(link)[0]: link_tuple(link) for link in graph['links']}
        assert len(nodes) == len(graph['nodes']), 'Duplicate node ID'
        assert len(links) == len(graph['links']), 'Duplicate link ID'
        input_id = graph.get('inputNode', {}).get('id')
        output_id = graph.get('outputNode', {}).get('id')
        for lid, source, slot, target, port, kind in links.values():
            src = graph['inputs'][slot] if source == input_id else nodes[source]['outputs'][slot]
            dst = graph['outputs'][port] if target == output_id else nodes[target]['inputs'][port]
            assert src['type'] == dst['type'] == kind, (lid, 'Port type mismatch')
            assert lid in (src['linkIds'] if source == input_id else src['links'])
            assert lid in dst['linkIds'] if target == output_id else dst['link'] == lid
            if source != input_id and target != output_id:
                assert nodes[source]['order'] < nodes[target]['order'], 'Invalid execution order'
        for node in nodes.values():
            assert node['mode'] == 0
            for slot, port in enumerate(node.get('inputs', [])):
                if port.get('link') is not None:
                    assert links[port['link']][3:5] == (node['id'], slot)
            for slot, port in enumerate(node.get('outputs', [])):
                for lid in port.get('links') or []:
                    assert links[lid][1:3] == (node['id'], slot)
            if node['type'] in definitions:
                definition = definitions[node['type']]
                for kind in ('inputs', 'outputs'):
                    assert [(p['name'], p['type']) for p in node[kind]] == [
                        (p['name'], p['type']) for p in definition[kind]], 'Subgraph interface mismatch'
        for kind, boundary_id, endpoint in (('inputs', input_id, 1), ('outputs', output_id, 3)):
            for slot, port in enumerate(graph.get(kind, [])):
                expected = [lid for lid, link in links.items() if link[endpoint:endpoint + 2] == (boundary_id, slot)]
                assert port['linkIds'] == expected, 'Stale boundary links'


def flatten_connections(workflow):
    """Resolve saved connections and promoted constants through every boundary.

    Leaf output references are (execution-path, output-slot) tuples. This static
    representation is for assertions only, and is never distributed as an API
    prompt or claimed to be a live frontend export.
    """
    definitions = {graph['id']: graph for graph in graphs(workflow) if graph is not workflow}
    flat = {}

    class Context:
        def __init__(self, graph, prefix='', supplied=None, ancestry=()):
            assert graph['id'] not in ancestry, 'Recursive subgraph definition'
            self.graph, self.prefix = graph, prefix
            self.supplied = supplied or {}
            self.ancestry = ancestry + (graph['id'],)
            self.nodes = {node['id']: node for node in graph['nodes']}
            self.links = {link_tuple(link)[0]: link_tuple(link) for link in graph['links']}
            self.children = {}

        def input(self, node, port):
            if port.get('link') is not None:
                link = self.links[port['link']]
                return self.output(link[1], link[2])
            return node.get('widgets_values_named', {}).get(port['name'])

        def child(self, node):
            if node['id'] not in self.children:
                self.children[node['id']] = Context(
                    definitions[node['type']], self.prefix + str(node['id']) + ':',
                    {port['name']: self.input(node, port) for port in node['inputs']}, self.ancestry)
            return self.children[node['id']]

        def output(self, node_id, slot):
            if node_id == self.graph.get('inputNode', {}).get('id'):
                return self.supplied[self.graph['inputs'][slot]['name']]
            node = self.nodes[node_id]
            if node['type'] not in definitions:
                return (self.prefix + str(node_id), slot)
            child = self.child(node)
            ids = child.graph['outputs'][slot]['linkIds']
            assert len(ids) == 1, 'Subgraph output must have one source'
            link = child.links[ids[0]]
            return child.output(link[1], link[2])

        def collect(self):
            for node in self.nodes.values():
                if node['type'] in definitions:
                    self.child(node).collect()
                    continue
                inputs = copy.deepcopy(node.get('widgets_values_named', {}))
                for port in node.get('inputs', []):
                    value = self.input(node, port)
                    if value is not None:
                        inputs[port['name']] = value
                flat[self.prefix + str(node['id'])] = {'type': node['type'], 'inputs': inputs}

    Context(workflow).collect()
    return flat
