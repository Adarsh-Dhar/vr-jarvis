"""
Agent 5 - Relationship Intelligence Tools
Discover how everything in the software is connected.
"""

from typing import Optional, List, Dict, Any
from google.adk.tools import ToolContext
from ._safe import safe


@safe
def build_call_graph(scope: str, tool_context: ToolContext) -> dict:
    """Construct function call graphs from the graph index.
    
    Args:
        scope: The analysis scope. Use '.' for the whole repository, a folder path, a file path, or a node id.
    """
    try:
        from .navigation_tools import _load_graph_index, resolve_symbol
        from ._common import repo_root
        from pathlib import Path
        
        # Load the graph index
        graph = _load_graph_index()
        
        # Filter nodes and edges by scope
        filtered_nodes = []
        filtered_edges = []
        
        # Only call-graph relationships belong in a call graph.
        CALL_EDGE_TYPES = {'calls', 'may_call'}
        all_edges = [e for e in graph.get('edges', []) if e.get('type') in CALL_EDGE_TYPES]

        # Handle scope: '.' means whole repository
        if scope == '.' or scope == 'repo':
            # Function-level nodes only (plus file/module context is noise here)
            filtered_nodes = [n for n in graph.get('nodes', [])
                              if n.get('level') in ('function', 'class') or n.get('kind') in ('function', 'method', 'object')]
            node_ids = {n.get('id') for n in filtered_nodes}
            filtered_edges = [e for e in all_edges
                              if e.get('src') in node_ids and e.get('dst') in node_ids]
        else:
            # Check if scope is a node ID
            if '/' not in scope and '.' in scope:
                # It's likely a node ID (e.g., "routes.account.deleteAccount")
                node = resolve_symbol(scope)
                if node:
                    # Return this node and its direct call connections
                    filtered_nodes = [node]
                    node_id = node.get('id')
                    for edge in all_edges:
                        if edge.get('src') == node_id or edge.get('dst') == node_id:
                            filtered_edges.append(edge)
                            # Add connected nodes
                            connected_id = edge.get('dst') if edge.get('src') == node_id else edge.get('src')
                            connected_node = resolve_symbol(connected_id)
                            if connected_node and connected_node not in filtered_nodes:
                                filtered_nodes.append(connected_node)
            else:
                # Scope is a folder or file path
                scope_path = Path(scope)
                for node in graph.get('nodes', []):
                    node_file = node.get('file', '')
                    # Check if node is in scope
                    if scope_path.is_dir():
                        # Check if node file is under this directory
                        if node_file.startswith(scope):
                            filtered_nodes.append(node)
                    elif scope_path.is_file():
                        # Check if node file matches exactly
                        if node_file == scope:
                            filtered_nodes.append(node)
                    else:
                        # Scope might be a folder name (not a path)
                        # Check if node file starts with the scope name
                        if node_file.startswith(scope + '/') or node_file.startswith(scope + '\\'):
                            filtered_nodes.append(node)
                        # Also check if the file path contains the scope as a directory
                        elif '/' + scope + '/' in node_file or '\\' + scope + '\\' in node_file:
                            filtered_nodes.append(node)
                
                # Get edges between filtered nodes and their connections
                node_ids = {n.get('id') for n in filtered_nodes}
                connected_node_ids = set()
                
                for edge in all_edges:
                    src_id = edge.get('src')
                    dst_id = edge.get('dst')
                    
                    # Include edge if either endpoint is in the filtered nodes
                    if src_id in node_ids or dst_id in node_ids:
                        filtered_edges.append(edge)
                        # Track connected nodes that aren't already in the set
                        if src_id not in node_ids:
                            connected_node_ids.add(src_id)
                        if dst_id not in node_ids:
                            connected_node_ids.add(dst_id)
                
                # Add connected nodes to the result
                for node in graph.get('nodes', []):
                    if node.get('id') in connected_node_ids:
                        filtered_nodes.append(node)

        # Attach recorded call-site records for the included edges so callers can
        # report source evidence without a second lookup.
        call_sites = {c.get('id'): c for c in graph.get('call_sites', []) if isinstance(c, dict)}
        for edge in filtered_edges:
            csid = edge.get('callsite_id')
            if csid and csid in call_sites:
                edge['call_site'] = call_sites[csid]

        return {
            'status': 'ok',
            'scope': scope,
            'call_graph': {
                'nodes': filtered_nodes,
                'edges': filtered_edges
            },
            'node_count': len(filtered_nodes),
            'edge_count': len(filtered_edges)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def _split_call_results(entries):
    """Split caller/callee entries into confirmed vs possible groups."""
    confirmed, possible = [], []
    for e in entries:
        res = e.get('resolution', '')
        kind = e.get('kind', '')
        if res == 'static_resolved' or kind == 'confirmed':
            confirmed.append(e)
        else:
            possible.append(e)
    return confirmed, possible


@safe
def find_callers(function_id: str, tool_context: ToolContext, depth: int = 1,
                 include_possible: bool = False) -> dict:
    """Find functions calling a selected function using CodeGraph.

    Confirmed callers (static_resolved) are reported separately from possible
    callers (polymorphic/ambiguous may_call edges) so the agent never presents
    uncertain relationships as fact.
    """
    try:
        from .. import codegraph

        graph = codegraph.load_current_graph()
        node = graph.get(function_id)
        if node is None:
            resolved = graph.resolve(function_id)
            if resolved['status'] == 'ambiguous':
                return {
                    'status': 'ambiguous',
                    'function_id': function_id,
                    'message': f'"{function_id}" matches {len(resolved["candidates"])} symbols; disambiguate with a full id',
                    'candidates': [c['id'] for c in resolved['candidates'][:20]],
                }
            return {'status': 'not_found', 'error': f'Symbol not found: {function_id}'}
        function_id = node['id']

        callers = graph.callers(function_id, depth=depth,
                                include_possible=include_possible,
                                include_ambiguous=include_possible)
        confirmed, possible = _split_call_results(callers)

        return {
            'status': 'ok',
            'function_id': function_id,
            'confirmed_callers': confirmed,
            'possible_callers': possible if include_possible else [],
            'depth': depth
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_callees(function_id: str, tool_context: ToolContext,
                 include_possible: bool = False) -> dict:
    """Find functions called by a selected function using CodeGraph.

    Confirmed callees are separated from possible callees (may_call edges).
    """
    try:
        from .. import codegraph

        graph = codegraph.load_current_graph()
        node = graph.get(function_id)
        if node is None:
            resolved = graph.resolve(function_id)
            if resolved['status'] == 'ambiguous':
                return {
                    'status': 'ambiguous',
                    'function_id': function_id,
                    'message': f'"{function_id}" matches {len(resolved["candidates"])} symbols; disambiguate with a full id',
                    'candidates': [c['id'] for c in resolved['candidates'][:20]],
                }
            return {'status': 'not_found', 'error': f'Symbol not found: {function_id}'}
        function_id = node['id']

        callees = graph.callees(function_id, depth=1,
                                include_possible=include_possible,
                                include_ambiguous=include_possible)
        confirmed, possible = _split_call_results(callees)

        return {
            'status': 'ok',
            'function_id': function_id,
            'confirmed_callees': confirmed,
            'possible_callees': possible if include_possible else [],
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_call_sites(function_id: str, tool_context: ToolContext) -> dict:
    """List recorded call sites owned by a function, with resolution status."""
    try:
        from .. import codegraph

        graph = codegraph.load_current_graph()
        node = graph.get(function_id)
        if node is None:
            resolved = graph.resolve(function_id)
            if resolved['status'] == 'ambiguous':
                return {
                    'status': 'ambiguous',
                    'function_id': function_id,
                    'candidates': [c['id'] for c in resolved['candidates'][:20]],
                }
            return {'status': 'not_found', 'error': f'Symbol not found: {function_id}'}
        function_id = node['id']

        sites = [c for c in getattr(graph, '_call_sites', {}).values()
                 if c.get('caller_node_id') == function_id or c.get('caller_id') == function_id]
        sites.sort(key=lambda c: (c.get('file', ''), c.get('line', 0), c.get('column', 0)))

        return {
            'status': 'ok',
            'function_id': function_id,
            'call_sites': sites,
            'count': len(sites),
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def explain_call_resolution(callsite_id: str, tool_context: ToolContext) -> dict:
    """Explain why a call site resolves the way it does, from recorded evidence.

    The answer comes from resolver-recorded evidence (resolution method,
    reason, candidates, source span) — never an invented explanation.
    """
    try:
        from .. import codegraph

        graph = codegraph.load_current_graph()
        site = graph.call_site(callsite_id)
        if site is None:
            # allow lookup by "file:line" prefix
            matches = [c for c in getattr(graph, '_call_sites', {}).values()
                       if c.get('id', '').startswith(callsite_id) or
                       f"{c.get('file')}:{c.get('line')}" == callsite_id]
            if len(matches) == 1:
                site = matches[0]
            elif len(matches) > 1:
                return {
                    'status': 'ambiguous',
                    'callsite_id': callsite_id,
                    'candidates': [m['id'] for m in matches],
                }
        if site is None:
            return {'status': 'error', 'error': f'Call site not found: {callsite_id}'}

        # attach target/candidate node details
        def _node(sid):
            n = graph._nodes.get(sid)
            return {'id': sid, 'name': n.get('name') if n else None,
                    'file': n.get('file') if n else None} if n else {'id': sid}

        return {
            'status': 'ok',
            'call_site': site,
            'caller': _node(site.get('caller_node_id') or ''),
            'targets': [_node(t) for t in site.get('targets', [])],
            'candidates': [_node(c) for c in site.get('candidates', [])],
            'edges': graph.candidates(callsite_id),
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_call_chain(
    function_id: str,
    tool_context: ToolContext,
    depth: int = 3,
    include_possible: bool = False
) -> dict:
    """Trace call chains from a function using CodeGraph.

    Uses path-local visited sets so recursion, cycles and diamond-shaped call
    graphs produce every distinct path (bounded by ``depth``). Each step carries
    the call-site id, source line and resolution status of the edge taken.
    """
    try:
        from .. import codegraph

        graph = codegraph.load_current_graph()
        start = graph.get(function_id)
        if start is None:
            resolved = graph.resolve(function_id)
            if resolved['status'] == 'ambiguous':
                return {
                    'status': 'ambiguous',
                    'function_id': function_id,
                    'candidates': [c['id'] for c in resolved['candidates'][:20]],
                }
            return {'status': 'not_found', 'error': f'Symbol not found: {function_id}'}
        start_id = start['id']

        MAX_CHAINS = 200
        MAX_CHAIN_LEN = depth + 1
        chains = []
        truncated = False

        def node_entry(nid):
            n = graph._nodes.get(nid, {})
            return {'id': nid, 'name': n.get('name'), 'file': n.get('file')}

        def walk(current_id, path, visited, d):
            nonlocal truncated
            if len(chains) >= MAX_CHAINS:
                truncated = True
                return
            if d > depth:
                chains.append(list(path))
                return
            callees = graph.callees(current_id, depth=1,
                                    include_possible=include_possible,
                                    include_ambiguous=include_possible)
            if not callees:
                chains.append(list(path))
                return
            for callee in callees:
                nxt = callee['to']
                step = dict(node_entry(nxt))
                step['via'] = {
                    'callsite_id': callee.get('callsite_id'),
                    'line': callee.get('line'),
                    'resolution': callee.get('resolution'),
                    'kind': callee.get('kind'),
                    'confidence': callee.get('confidence'),
                }
                if nxt in visited:
                    # cycle: record the edge but do not recurse
                    cyc = list(path) + [step]
                    chains.append(cyc)
                    continue
                if len(path) + 1 >= MAX_CHAIN_LEN:
                    chains.append(list(path) + [step])
                    continue
                walk(nxt, path + [step], visited | {nxt}, d + 1)

        walk(start_id, [node_entry(start_id)], {start_id}, 0)

        return {
            'status': 'ok',
            'function_id': start_id,
            'chains': chains,
            'depth': depth,
            'include_possible': include_possible,
            'truncated': truncated,
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_indirect_callers(
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Find functions indirectly calling a selected function using CodeGraph."""
    try:
        from .. import codegraph

        graph = codegraph.load_current_graph()

        # Get direct callers (depth=1)
        direct_callers = graph.callers(function_id, depth=1)

        # Get indirect callers (depth=2)
        indirect_callers = graph.callers(function_id, depth=2)

        # Filter out direct callers from indirect list
        direct_caller_ids = {c['from'] for c in direct_callers}
        indirect_only = [c for c in indirect_callers if c['from'] not in direct_caller_ids]

        return {
            'status': 'ok',
            'function_id': function_id,
            'direct_callers': direct_callers,
            'indirect_callers': indirect_only
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def build_dependency_graph(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Build module dependency graphs using CodeGraph."""
    try:
        from .. import codegraph

        graph = codegraph.load_current_graph()

        # Get only module and file nodes
        dependency_nodes = []
        for node_id, node in graph._nodes.items():
            if node.get('level') in ('module', 'file'):
                dependency_nodes.append(node)

        # Get import edges between modules and files
        dependency_edges = []
        for edge in graph._raw_data.get('edges', []):
            if edge.get('type') == 'imports':
                src_id = edge.get('src')
                dst_id = edge.get('dst')
                # Only include edges between module/file nodes
                if (src_id in graph._nodes and graph._nodes[src_id].get('level') in ('module', 'file') and
                    dst_id in graph._nodes and graph._nodes[dst_id].get('level') in ('module', 'file')):
                    dependency_edges.append(edge)

        return {
            'status': 'ok',
            'repository_path': repository_path,
            'nodes': dependency_nodes,
            'edges': dependency_edges,
            'nodes_count': len(dependency_nodes),
            'edges_count': len(dependency_edges)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_downstream_dependencies(
    module_id: str,
    tool_context: ToolContext
) -> dict:
    """Find modules depending on a selected module."""
    try:
        from .repository_tools import search_code
        from .navigation_tools import get_imports
        from .repository_tools import list_files
        
        # Search for imports of this module
        import_patterns = [
            f'import {module_id}',
            f'from {module_id} import',
            f'from {module_id}.'
        ]
        
        downstream_modules = []
        for pattern in import_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    file_path = match['file']
                    # Extract module name from file path
                    module_parts = file_path.replace('/', '.').replace('\\', '.').replace('.py', '')
                    module_name = module_parts.split('.')[-1] if '.' in module_parts else module_parts
                    
                    if module_name not in [m['module'] for m in downstream_modules]:
                        downstream_modules.append({
                            'module': module_name,
                            'file': file_path,
                            'line': match['line'],
                            'import_type': pattern
                        })
        
        return {
            'status': 'ok',
            'module_id': module_id,
            'downstream_dependencies': downstream_modules
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_shared_dependencies(
    module_ids: List[str],
    tool_context: ToolContext
) -> dict:
    """Find dependencies shared by multiple modules."""
    try:
        from .navigation_tools import get_imports
        from .repository_tools import list_files
        
        all_dependencies = {}
        
        for module_id in module_ids:
            deps = set()
            # Find files in this module
            files_result = list_files(tool_context, directory=module_id, recursive=True)
            if files_result.get('status') == 'ok':
                for file_info in files_result['files']:
                    if file_info['type'] == 'file' and file_info['path'].endswith('.py'):
                        imports_result = get_imports(file_info['path'], tool_context)
                        if imports_result.get('status') == 'ok':
                            for imp in imports_result['imports']:
                                deps.add(imp['module'])
            
            all_dependencies[module_id] = deps
        
        # Find shared dependencies
        if len(all_dependencies) >= 2:
            shared = set.intersection(*all_dependencies.values())
        else:
            shared = set()
        
        shared_list = [{'module': dep, 'used_by': [mid for mid, deps in all_dependencies.items() if dep in deps]} for dep in shared]
        
        return {
            'status': 'ok',
            'module_ids': module_ids,
            'shared_dependencies': shared_list,
            'all_dependencies': {mid: list(deps) for mid, deps in all_dependencies.items()}
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def build_reference_graph(scope: str, tool_context: ToolContext) -> dict:
    """Construct reference relationships."""
    try:
        from .analysis_tools import extract_symbols, resolve_references
        from .repository_tools import list_files
        
        # Get all Python files in scope
        files_result = list_files(tool_context, directory=scope, pattern='.py', recursive=True)
        if files_result.get('status') != 'ok':
            return files_result
        
        reference_graph = {
            'nodes': [],
            'edges': []
        }
        
        for file_info in files_result['files']:
            if file_info['type'] == 'file':
                file_path = file_info['path']
                
                # Extract symbols
                symbols_result = extract_symbols(file_path, tool_context)
                if symbols_result.get('status') == 'ok':
                    for symbol in symbols_result['symbols']:
                        reference_graph['nodes'].append({
                            'id': f"{file_path}:{symbol['name']}",
                            'name': symbol['name'],
                            'file': file_path,
                            'line': symbol['line'],
                            'type': symbol['type']
                        })
                
                # Resolve references
                refs_result = resolve_references(file_path, tool_context)
                if refs_result.get('status') == 'ok':
                    for ref in refs_result['references']:
                        reference_graph['edges'].append({
                            'from': f"{file_path}:line_{ref['line']}",
                            'to': ref.get('to'),
                            'type': ref.get('type'),
                            'line': ref['line']
                        })
        
        return {
            'status': 'ok',
            'scope': scope,
            'reference_graph': reference_graph,
            'node_count': len(reference_graph['nodes']),
            'edge_count': len(reference_graph['edges'])
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def build_class_relationship_graph(scope: str, tool_context: ToolContext) -> dict:
    """Map inheritance and composition."""
    try:
        from .navigation_tools import get_type_hierarchy
        return get_type_hierarchy(scope, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_interface_implementations(interface_id: str, tool_context: ToolContext) -> dict:
    """Find implementations of an interface."""
    try:
        from .analysis_tools import extract_symbols
        from .repository_tools import list_files, search_code
        
        # Search for classes that inherit from or implement the interface
        implementations = []
        
        # Search for inheritance patterns
        inheritance_patterns = [
            f'class {interface_id}',
            f'(.*{interface_id}.*)',  # Base class
            f'implements {interface_id}'
        ]
        
        files_result = list_files(tool_context, directory='.', pattern='.py', recursive=True)
        if files_result.get('status') == 'ok':
            for file_info in files_result['files']:
                if file_info['type'] == 'file':
                    file_path = file_info['path']
                    
                    # Extract symbols to find classes
                    symbols_result = extract_symbols(file_path, tool_context)
                    if symbols_result.get('status') == 'ok':
                        for symbol in symbols_result['symbols']:
                            if symbol['type'] == 'class':
                                # Check if this class implements the interface
                                search_result = search_code(tool_context, query=f'class {symbol["name"]}')
                                if search_result.get('status') == 'ok':
                                    for match in search_result['matches']:
                                        if interface_id in match['snippet']:
                                            implementations.append({
                                                'class': symbol['name'],
                                                'file': file_path,
                                                'line': symbol['line'],
                                                'interface': interface_id
                                            })
        
        return {
            'status': 'ok',
            'interface_id': interface_id,
            'implementations': implementations
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_cross_module_relationships(
    module_id: str,
    tool_context: ToolContext
) -> dict:
    """Follow relationships between modules.
    
    Args:
        module_id: The module identifier. Use '.' for the whole repository, a folder path, a file path, or a node id.
    """
    try:
        from ._common import repo_root
        if module_id == "." or module_id == "repo":
            module_id = str(repo_root())
        from .navigation_tools import get_imports
        from .repository_tools import list_files
        
        # Get files in the module
        files_result = list_files(tool_context, directory=module_id, recursive=True)
        if files_result.get('status') != 'ok':
            return files_result
        
        relationships = []
        
        for file_info in files_result['files']:
            if file_info['type'] == 'file' and file_info['path'].endswith('.py'):
                imports_result = get_imports(file_info['path'], tool_context)
                if imports_result.get('status') == 'ok':
                    for imp in imports_result['imports']:
                        # Determine if this is cross-module
                        module_name = imp['module']
                        if module_name and not module_name.startswith('.'):
                            relationships.append({
                                'from_module': module_id,
                                'to_module': module_name.split('.')[0],
                                'file': file_info['path'],
                                'import': module_name
                            })
        
        return {
            'status': 'ok',
            'module_id': module_id,
            'cross_module_relationships': relationships
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_cross_service_relationships(
    service_id: str,
    tool_context: ToolContext
) -> dict:
    """Follow relationships between services."""
    try:
        from .repository_tools import search_code
        
        # Search for cross-service relationship patterns
        service_patterns = [
            'requests.',
            'http.',
            'grpc.',
            'redis.',
            'kafka.',
            'rabbitmq.',
            'sqs.',
            'publish(',
            'subscribe(',
            'emit(',
            'on(',
            'client.',
            'service.',
            'api.'
        ]
        
        relationships = []
        for pattern in service_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    relationships.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'service_id': service_id,
            'cross_service_relationships': relationships,
            'count': len(relationships),
            'note': 'Pattern-based analysis - full cross-service tracing requires runtime tracing'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_circular_dependencies(scope: str, tool_context: ToolContext) -> dict:
    """Detect dependency cycles.
    
    Args:
        scope: The analysis scope. Use '.' for the whole repository, a folder path, a file path, or a node id.
    """
    try:
        from ._common import repo_root
        if scope == "." or scope == "repo":
            scope = str(repo_root())
        from .navigation_tools import get_imports
        from .repository_tools import list_files
        
        # Build dependency graph
        dependency_graph = {}
        
        files_result = list_files(tool_context, directory=scope, pattern='.py', recursive=True)
        if files_result.get('status') != 'ok':
            return files_result
        
        for file_info in files_result['files']:
            if file_info['type'] == 'file':
                file_path = file_info['path']
                module_name = file_path.replace('/', '.').replace('\\', '.').replace('.py', '')
                
                imports_result = get_imports(file_path, tool_context)
                if imports_result.get('status') == 'ok':
                    dependencies = [imp['module'].split('.')[0] for imp in imports_result['imports'] if imp['module']]
                    dependency_graph[module_name] = dependencies
        
        # Detect cycles using DFS
        def has_cycle(graph, node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(graph, neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        cycles = []
        visited = set()
        
        for node in dependency_graph:
            if node not in visited:
                rec_stack = set()
                if has_cycle(dependency_graph, node, visited, rec_stack):
                    cycles.append({
                        'cycle': list(rec_stack),
                        'module': node
                    })
        
        return {
            'status': 'ok',
            'scope': scope,
            'circular_dependencies': cycles,
            'cycle_count': len(cycles)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_architecture_boundaries(scope: str, tool_context: ToolContext) -> dict:
    """Identify architectural boundaries.
    
    Args:
        scope: The analysis scope. Use '.' for the whole repository, a folder path, a file path, or a node id.
    """
    try:
        from ._common import repo_root
        if scope == "." or scope == "repo":
            scope = str(repo_root())
        from .repository_tools import list_files
        
        # Analyze directory structure to identify architectural layers
        files_result = list_files(tool_context, directory=scope, recursive=True)
        if files_result.get('status') != 'ok':
            return files_result
        
        boundaries = {}
        
        for file_info in files_result['files']:
            if file_info['type'] == 'directory':
                dir_name = file_info['path']
                
                # Infer architectural layer from directory name
                layer = 'unknown'
                if 'api' in dir_name.lower() or 'controller' in dir_name.lower() or 'handler' in dir_name.lower():
                    layer = 'api_layer'
                elif 'service' in dir_name.lower() or 'business' in dir_name.lower():
                    layer = 'service_layer'
                elif 'model' in dir_name.lower() or 'entity' in dir_name.lower() or 'domain' in dir_name.lower():
                    layer = 'domain_layer'
                elif 'repository' in dir_name.lower() or 'dao' in dir_name.lower() or 'db' in dir_name.lower():
                    layer = 'data_layer'
                elif 'util' in dir_name.lower() or 'helper' in dir_name.lower() or 'common' in dir_name.lower():
                    layer = 'utility_layer'
                elif 'test' in dir_name.lower() or 'spec' in dir_name.lower():
                    layer = 'test_layer'
                
                if layer != 'unknown':
                    if layer not in boundaries:
                        boundaries[layer] = []
                    boundaries[layer].append(dir_name)
        
        return {
            'status': 'ok',
            'scope': scope,
            'architectural_boundaries': boundaries,
            'layers_identified': list(boundaries.keys())
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def calculate_change_impact(
    element_id: str,
    tool_context: ToolContext
) -> dict:
    """Estimate which components are affected by a change using CodeGraph.

    Returns direct and indirect dependents through calls and imports,
    including possible call relationships and associated tests.

    Relationship types:
        - calls: Confirmed caller relationship
        - may_call: Possible caller relationship (reported separately)
        - imports: Module/file dependency
        - Containment: Excluded from dependent traversal
    """
    try:
        from .. import codegraph
        from .graph_tools import get_dependents, find_tests_for_node

        graph = codegraph.load_current_graph()

        # Resolve the element
        node = graph.get(element_id)
        if not node:
            return {
                'status': 'not_found',
                'element_id': element_id,
                'message': 'Element not found in graph'
            }

        symbol_id = node['id']

        # Get direct confirmed callers (calls only, depth=1, include_possible=False)
        direct_callers = graph.callers(symbol_id, depth=1, include_possible=False)
        direct_caller_ids = {c['from'] for c in direct_callers}

        # Get direct possible callers (may_call edges at depth=1)
        all_depth1 = graph.callers(symbol_id, depth=1, include_possible=True)
        possible_callers = [c for c in all_depth1 if c.get('kind') == 'possible' or c.get('resolution') != 'static_resolved']
        possible_caller_ids = {c['from'] for c in possible_callers}

        # Get indirect call dependents (calls and may_call, depth up to 6, excluding both direct groups)
        dependents_result = get_dependents(symbol_id, tool_context, max_depth=6, edge_types=['calls', 'may_call'])
        if dependents_result.get('status') != 'ok':
            return dependents_result

        # Filter indirect dependents: exclude direct confirmed and direct possible
        excluded_ids = direct_caller_ids | possible_caller_ids | {symbol_id}
        indirect_dependents = [d for d in dependents_result['dependents']
                             if d['id'] not in excluded_ids]

        # Mark may_call edges as uncertain in indirect dependents
        for dep in indirect_dependents:
            if dep.get('edge_type') == 'may_call':
                dep['uncertain'] = True

        # Get import-dependent modules/files separately (imports only, depth up to 6)
        import_dependents_result = get_dependents(symbol_id, tool_context, max_depth=6, edge_types=['imports'])
        import_dependents = []
        if import_dependents_result.get('status') == 'ok':
            import_dependents = [d for d in import_dependents_result['dependents']
                                if d['edge_type'] == 'imports' and d['id'] != symbol_id]

        # Calculate total affected nodes using deduplicated ID set
        all_affected_ids = (direct_caller_ids |
                            possible_caller_ids |
                            {d['id'] for d in indirect_dependents} |
                            {d['id'] for d in import_dependents} |
                            {symbol_id})

        # Get covering tests for all affected nodes
        covering_tests = graph.covering_tests(list(all_affected_ids))

        # Check if the element itself is tested
        element_tested = any(symbol_id in test.get('covers', []) for test in covering_tests)

        # Calculate risk level based on indirect dependent count and test coverage
        risk_level = 'low'
        if len(indirect_dependents) > 10 or not element_tested:
            risk_level = 'high'
        elif len(indirect_dependents) > 3:
            risk_level = 'medium'

        return {
            'status': 'ok',
            'element_id': element_id,
            'direct_callers': direct_callers,
            'indirect_dependents': indirect_dependents,
            'possible_callers': possible_callers,
            'import_dependents': import_dependents,
            'direct_count': len(direct_callers),
            'indirect_count': len(indirect_dependents),
            'possible_count': len(possible_callers),
            'import_count': len(import_dependents),
            'total_affected': len(all_affected_ids) - 1,  # Exclude the element itself
            'covering_tests': covering_tests,
            'untested': not element_tested,
            'risk_level': risk_level
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_all_paths_between_symbols(
    from_id: str,
    to_id: str,
    tool_context: ToolContext
) -> dict:
    """Find paths connecting two code elements using CodeGraph."""
    try:
        from .. import codegraph

        graph = codegraph.load_current_graph()
        paths = []

        # BFS to find all paths up to depth 3
        from collections import deque

        queue = deque([(from_id, [from_id])])
        visited = set()

        while queue:
            current, path = queue.popleft()

            if current == to_id:
                paths.append({
                    'path': path,
                    'type': 'call_chain'
                })
                continue

            if len(path) > 3:  # Limit depth
                continue

            if current in visited:
                continue
            visited.add(current)

            # Get outgoing calls
            callees = graph.callees(current, depth=1)
            for callee in callees:
                next_id = callee['to']
                queue.append((next_id, path + [next_id]))

        return {
            'status': 'ok',
            'from_id': from_id,
            'to_id': to_id,
            'paths': paths,
            'path_count': len(paths)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_dependents(component_id: str, tool_context: ToolContext) -> dict:
    """Find components depending on a selected component using CodeGraph."""
    try:
        from .. import codegraph

        graph = codegraph.load_current_graph()

        # Resolve the component ID
        node = graph.get(component_id)
        if not node:
            return {
                'status': 'not_found',
                'component_id': component_id,
                'message': 'Component not found in graph'
            }

        symbol_id = node['id']

        # Get incoming edges (callers and dependents)
        dependents = []

        # Add callers (via calls edges)
        callers = graph.callers(symbol_id, depth=1)
        for caller in callers:
            caller_node = graph.get(caller['from'])
            dependents.append({
                'component': caller['from'],
                'name': caller_node['name'] if caller_node else None,
                'file': caller.get('file'),
                'line': caller.get('line'),
                'type': 'call',
                'kind': caller.get('kind')
            })

        # Add dependencies (via imports edges)
        for edge in graph._inn.get(symbol_id, []):
            if edge['type'] == 'imports':
                dep_node = graph.get(edge['src'])
                dependents.append({
                    'component': edge['src'],
                    'name': dep_node['name'] if dep_node else None,
                    'file': edge.get('file'),
                    'line': edge.get('line'),
                    'type': 'import',
                    'kind': edge.get('kind')
                })

        return {
            'status': 'ok',
            'component_id': component_id,
            'dependents': dependents,
            'dependent_count': len(dependents)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
