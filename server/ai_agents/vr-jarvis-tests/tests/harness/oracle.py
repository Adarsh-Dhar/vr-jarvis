'''Independent oracle built on networkx. It shares no code with the tools under test.'''
import networkx as nx


class Oracle:
    def __init__(self, graph):
        self.graph = graph
        self.ids = [n['id'] for n in graph['nodes']]
        self.all = nx.DiGraph()
        self.calls = nx.DiGraph()
        self.confirmed = nx.DiGraph()
        for i in self.ids:
            for g in (self.all, self.calls, self.confirmed):
                g.add_node(i)
        self.edge_set = set()
        for e in graph['edges']:
            self.all.add_edge(e['src'], e['dst'])
            self.edge_set.add((e['src'], e['dst']))
            if e['type'] == 'calls':
                self.calls.add_edge(e['src'], e['dst'])
            if e['kind'] == 'confirmed':
                self.confirmed.add_edge(e['src'], e['dst'])

    @staticmethod
    def _reach(g, node, depth):
        lengths = nx.single_source_shortest_path_length(g, node, cutoff=depth)
        lengths.pop(node, None)
        return lengths

    def callers(self, node, depth=1):
        return self._reach(self.calls.reverse(copy=False), node, depth)

    def callees(self, node, depth=1):
        return self._reach(self.calls, node, depth)

    def dependents(self, node, depth=4):
        return self._reach(self.all.reverse(copy=False), node, depth)

    def dependents_split(self, node, depth=4):
        '''(confirmed, unresolved): confirmed when some chain of only confirmed edges reaches the node.'''
        allr = set(self.dependents(node, depth))
        conf = set(self._reach(self.confirmed.reverse(copy=False), node, depth))
        return conf & allr, allr - conf

    def shortest(self, src, dst):
        try:
            return nx.shortest_path_length(self.all, src, dst)
        except nx.NetworkXNoPath:
            return None

    def has_edge(self, a, b):
        return (a, b) in self.edge_set

    def tests_for(self, node):
        return [t['id'] for t in self.graph['tests'] if node in t['covers']]

    def untested(self):
        covered = {n for t in self.graph['tests'] for n in t['covers']}
        return {i for i in self.ids if i not in covered}

    def edge_kind(self, a, b, edge_type='calls'):
        return {e['kind'] for e in self.graph['edges']
                if e['src'] == a and e['dst'] == b and e['type'] == edge_type}
