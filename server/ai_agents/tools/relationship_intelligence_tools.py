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
        
        # Handle scope: '.' means whole repository
        if scope == '.' or scope == 'repo':
            # Return all nodes and edges
            filtered_nodes = graph.get('nodes', [])
            filtered_edges = graph.get('edges', [])
        else:
            # Check if scope is a node ID
            if '/' not in scope and '.' in scope:
                # It's likely a node ID (e.g., "routes.account.deleteAccount")
                node = resolve_symbol(scope)
                if node:
                    # Return this node and its direct connections
                    filtered_nodes = [node]
                    node_id = node.get('id')
                    for edge in graph.get('edges', []):
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
                
                for edge in graph.get('edges', []):
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


@safe
def find_callers(function_id: str, tool_context: ToolContext, depth: int = 1) -> dict:
    """Find functions calling a selected function using the graph index."""
    try:
        from .navigation_tools import get_call_hierarchy

        # Get incoming calls (callers) - only call edges
        call_result = get_call_hierarchy(function_id, tool_context, direction='incoming')

        if call_result.get('status') != 'ok':
            return call_result

        callers = call_result.get('incoming_calls', [])

        # If depth > 1, get indirect callers
        if depth > 1:
            indirect_callers = []
            direct_caller_ids = [c.get('from', '') for c in callers]

            for caller in callers:
                caller_id = caller.get('from', '')
                if caller_id and caller_id not in direct_caller_ids:
                    # Recursively get callers of this caller
                    sub_result = find_callers(caller_id, tool_context, depth=depth-1)
                    if sub_result.get('status') == 'ok':
                        indirect_callers.extend(sub_result.get('callers', []))

            return {
                'status': 'ok',
                'function_id': function_id,
                'callers': callers,
                'indirect_callers': indirect_callers,
                'depth': depth
            }

        return {
            'status': 'ok',
            'function_id': function_id,
            'callers': callers,
            'depth': depth
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_callees(function_id: str, tool_context: ToolContext) -> dict:
    """Find functions called by a selected function using the graph index."""
    try:
        from .navigation_tools import get_call_hierarchy
        return get_call_hierarchy(function_id, tool_context, direction='outgoing')
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_call_chain(
    function_id: str,
    tool_context: ToolContext,
    depth: int = 3
) -> dict:
    """Trace the complete call chain using the graph index."""
    try:
        from .navigation_tools import get_call_hierarchy, _load_graph_index, resolve_symbol
        
        # Get the call hierarchy for the function
        call_result = get_call_hierarchy(function_id, tool_context, direction='outgoing')
        
        if call_result.get('status') != 'ok':
            return call_result
        
        # Build call chains by recursively following outgoing calls
        chains = []
        visited = set()
        
        def build_chain(current_id, current_chain, current_depth):
            if current_depth > depth or current_id in visited:
                return
            visited.add(current_id)
            
            node = resolve_symbol(current_id)
            if node:
                current_chain.append({
                    'id': current_id,
                    'name': node.get('name'),
                    'file': node.get('file')
                })
            
            graph = _load_graph_index()
            for edge in graph.get('edges', []):
                if edge.get('src') == current_id:
                    next_id = edge.get('dst')
                    build_chain(next_id, current_chain.copy(), current_depth + 1)
        
        # Start building chains from the initial function
        node = resolve_symbol(function_id)
        if node:
            initial_chain = [{
                'id': function_id,
                'name': node.get('name'),
                'file': node.get('file')
            }]
            build_chain(function_id, initial_chain, 0)
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'chains': chains,
            'depth': depth
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
    """Find functions indirectly calling a selected function using the graph index."""
    try:
        from .navigation_tools import get_call_hierarchy, _load_graph_index, resolve_symbol
        
        # Get direct callers (incoming calls)
        call_result = get_call_hierarchy(function_id, tool_context, direction='incoming')
        
        if call_result.get('status') != 'ok':
            return call_result
        
        direct_callers = call_result.get('incoming_calls', [])
        indirect_callers = []
        
        # For each direct caller, find their callers
        for caller in direct_callers:
            caller_id = caller.get('from', '')
            if not caller_id:
                continue
            
            caller_result = get_call_hierarchy(caller_id, tool_context, direction='incoming')
            if caller_result.get('status') == 'ok':
                for indirect_caller in caller_result.get('incoming_calls', []):
                    indirect_callers.append({
                        'function_id': function_id,
                        'indirect_caller': indirect_caller.get('from'),
                        'via': caller_id,
                        'file': indirect_caller.get('file'),
                        'line': indirect_caller.get('line')
                    })
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'direct_callers': direct_callers,
            'indirect_callers': indirect_callers
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
    """Build module dependency graphs from repository analysis using the graph index."""
    try:
        from .navigation_tools import _load_graph_index
        
        # Load the graph index
        graph = _load_graph_index()
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        # Build dependency graph from edges
        dependency_nodes = []
        dependency_edges = []
        
        # Group nodes by file to create module-level dependencies
        file_to_nodes = {}
        for node in nodes:
            file_path = node.get('file', '')
            if file_path:
                if file_path not in file_to_nodes:
                    file_to_nodes[file_path] = []
                file_to_nodes[file_path].append(node)
        
        # Create module nodes
        for file_path, file_nodes in file_to_nodes.items():
            dependency_nodes.append({
                'id': f'module.{file_path}',
                'name': file_path,
                'type': 'module',
                'file': file_path
            })
        
        # Create dependency edges based on imports
        for edge in edges:
            if edge.get('type') == 'imports':
                src_node = next((n for n in nodes if n.get('id') == edge.get('src')), None)
                dst_node = next((n for n in nodes if n.get('id') == edge.get('dst')), None)
                
                if src_node and dst_node:
                    src_file = src_node.get('file', '')
                    dst_file = dst_node.get('file', '')
                    
                    if src_file and dst_file and src_file != dst_file:
                        dependency_edges.append({
                            'src': f'module.{src_file}',
                            'dst': f'module.{dst_file}',
                            'type': 'dependency',
                            'kind': 'confirmed'
                        })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'nodes': dependency_nodes,
            'edges': dependency_edges,
            'nodes_count': len(dependency_nodes),
            'edges_count': len(dependency_edges),
            'note': 'Dependency graph built from graph index imports'
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
    """Estimate which components are affected by a change using the graph index."""
    try:
        from .navigation_tools import get_call_hierarchy, _load_graph_index, resolve_symbol
        
        # Get references to the element from the graph index
        graph = _load_graph_index()
        
        affected_components = []
        node = resolve_symbol(element_id)
        
        if node:
            symbol_id = node.get('id')
            symbol_name = node.get('name')
            
            # Find all incoming edges (callers)
            for edge in graph.get('edges', []):
                if edge.get('dst') == symbol_id:
                    src_node = resolve_symbol(edge.get('src'))
                    affected_components.append({
                        'component': edge.get('src'),
                        'name': src_node.get('name') if src_node else None,
                        'file': src_node.get('file') if src_node else None,
                        'line': edge.get('line'),
                        'impact_type': 'caller'
                    })
            
            # Find all outgoing edges (callees)
            for edge in graph.get('edges', []):
                if edge.get('src') == symbol_id:
                    dst_node = resolve_symbol(edge.get('dst'))
                    affected_components.append({
                        'component': edge.get('dst'),
                        'name': dst_node.get('name') if dst_node else None,
                        'file': dst_node.get('file') if dst_node else None,
                        'line': edge.get('line'),
                        'impact_type': 'callee'
                    })
        
        # Calculate impact score
        impact_score = len(affected_components)
        impact_level = 'low' if impact_score < 5 else 'medium' if impact_score < 15 else 'high'
        
        return {
            'status': 'ok',
            'element_id': element_id,
            'affected_components': affected_components,
            'impact_score': impact_score,
            'impact_level': impact_level
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
    """Find paths connecting two code elements using the graph index."""
    try:
        from .navigation_tools import get_call_hierarchy, _load_graph_index, resolve_symbol
        
        graph = _load_graph_index()
        paths = []
        
        # Check if there's a direct call
        for edge in graph.get('edges', []):
            if edge.get('src') == from_id and edge.get('dst') == to_id:
                paths.append({
                    'path': [from_id, to_id],
                    'type': 'direct_call',
                    'kind': edge.get('kind')
                })
        
        # If no direct path, try indirect (depth 2)
        if not paths:
            for edge1 in graph.get('edges', []):
                if edge1.get('src') == from_id:
                    intermediate = edge1.get('dst')
                    for edge2 in graph.get('edges', []):
                        if edge2.get('src') == intermediate and edge2.get('dst') == to_id:
                            paths.append({
                                'path': [from_id, intermediate, to_id],
                                'type': 'indirect_call',
                                'kind': edge2.get('kind')
                            })
        
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
    """Find components depending on a selected component using the graph index."""
    try:
        from .navigation_tools import _load_graph_index, resolve_symbol
        
        graph = _load_graph_index()
        dependents = []
        
        # Find all nodes that reference this component
        node = resolve_symbol(component_id)
        if node:
            symbol_id = node.get('id')
            
            # Find incoming edges (things that depend on this)
            for edge in graph.get('edges', []):
                if edge.get('dst') == symbol_id:
                    src_node = resolve_symbol(edge.get('src'))
                    dependents.append({
                        'component': edge.get('src'),
                        'name': src_node.get('name') if src_node else None,
                        'file': src_node.get('file') if src_node else None,
                        'line': edge.get('line'),
                        'type': 'dependency'
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
