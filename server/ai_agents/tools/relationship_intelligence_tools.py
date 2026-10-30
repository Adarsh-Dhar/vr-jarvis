"""
Agent 5 - Relationship Intelligence Tools
Discover how everything in the software is connected.
"""

from typing import Optional, List, Dict, Any
from google.adk.tools import ToolContext
from ._safe import safe


@safe
def build_call_graph(scope: str, tool_context: ToolContext) -> dict:
    """Construct function call graphs."""
    try:
        from .analysis_tools import extract_symbols
        from .navigation_tools import get_call_hierarchy
        from .repository_tools import list_files
        
        # Get all Python files in scope
        files_result = list_files(tool_context, directory=scope, pattern='.py', recursive=True)
        if files_result.get('status') != 'ok':
            return files_result
        
        call_graph = {
            'nodes': [],
            'edges': []
        }
        
        for file_info in files_result['files']:
            if file_info['type'] == 'file':
                file_path = file_info['path']
                
                # Extract symbols from file
                symbols_result = extract_symbols(file_path, tool_context)
                if symbols_result.get('status') == 'ok':
                    for symbol in symbols_result['symbols']:
                        if symbol['type'] == 'function':
                            call_graph['nodes'].append({
                                'id': f"{file_path}:{symbol['name']}",
                                'name': symbol['name'],
                                'file': file_path,
                                'line': symbol['line'],
                                'type': 'function'
                            })
                            
                            # Get call hierarchy for this function
                            call_result = get_call_hierarchy(symbol['name'], tool_context)
                            if call_result.get('status') == 'ok':
                                for outgoing in call_result.get('outgoing_calls', []):
                                    call_graph['edges'].append({
                                        'from': f"{file_path}:{symbol['name']}",
                                        'to': outgoing.get('to'),
                                        'type': 'call'
                                    })
        
        return {
            'status': 'ok',
            'scope': scope,
            'call_graph': call_graph,
            'node_count': len(call_graph['nodes']),
            'edge_count': len(call_graph['edges'])
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_callers(function_id: str, tool_context: ToolContext) -> dict:
    """Find functions calling a selected function."""
    try:
        from .navigation_tools import find_callers as nav_find_callers
        return nav_find_callers(function_id, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_callees(function_id: str, tool_context: ToolContext) -> dict:
    """Find functions called by a selected function."""
    try:
        from .navigation_tools import get_call_hierarchy
        return get_call_hierarchy(function_id, tool_context)
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
    """Trace the complete call chain."""
    try:
        from .navigation_tools import get_call_hierarchy
        return get_call_hierarchy(function_id, tool_context)
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
    """Find functions indirectly calling a selected function."""
    try:
        from .navigation_tools import get_call_hierarchy
        
        # Get direct callers (incoming calls)
        call_result = get_call_hierarchy(function_id, tool_context, direction='incoming')
        
        if call_result.get('status') != 'ok':
            return call_result
        
        direct_callers = call_result.get('incoming_calls', [])
        indirect_callers = []
        
        # For each direct caller, find their callers
        for caller in direct_callers:
            caller_name = caller.get('from', '').replace('caller_at_', '')
            if caller_name.isdigit():
                # Try to extract function name from context
                continue
            
            caller_result = get_call_hierarchy(caller_name, tool_context, direction='incoming')
            if caller_result.get('status') == 'ok':
                for indirect_caller in caller_result.get('incoming_calls', []):
                    indirect_callers.append({
                        'function_id': function_id,
                        'indirect_caller': indirect_caller.get('from'),
                        'via': caller.get('from'),
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
    """Build module dependency graphs."""
    try:
        from .analysis_tools import analyze_dependencies
        return analyze_dependencies(repository_path, tool_context)
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
        from .analysis_tools import get_imports
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
        from .analysis_tools import get_imports
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
    """Follow relationships between modules."""
    try:
        from .analysis_tools import get_imports
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
        return {
            'status': 'not_implemented',
            'message': 'Cross-service relationship tracing requires runtime tracing',
            'service_id': service_id
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_circular_dependencies(scope: str, tool_context: ToolContext) -> dict:
    """Detect dependency cycles."""
    try:
        from .analysis_tools import get_imports
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
    """Identify architectural boundaries."""
    try:
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
    """Estimate which components are affected by a change."""
    try:
        from .navigation_tools import get_symbol_references, get_call_hierarchy
        from .repository_tools import search_code
        
        # Get references to the element
        ref_result = get_symbol_references(element_id, tool_context)
        
        # Get call hierarchy
        call_result = get_call_hierarchy(element_id, tool_context)
        
        affected_components = []
        
        if ref_result.get('status') == 'ok':
            for ref in ref_result['references']:
                affected_components.append({
                    'component': ref['file'],
                    'line': ref['line'],
                    'impact_type': 'reference'
                })
        
        if call_result.get('status') == 'ok':
            for caller in call_result.get('incoming_calls', []):
                affected_components.append({
                    'component': caller.get('file'),
                    'line': caller.get('line'),
                    'impact_type': 'caller'
                })
        
        # Search for imports of this element as a module
        import_patterns = [
            f'import {element_id}',
            f'from {element_id} import'
        ]
        for pattern in import_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    affected_components.append({
                        'component': match['file'],
                        'line': match['line'],
                        'impact_type': 'import'
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
    """Find paths connecting two code elements."""
    try:
        from .navigation_tools import get_call_hierarchy
        
        # Build a simple path using call hierarchy
        from_result = get_call_hierarchy(from_id, tool_context, direction='outgoing')
        to_result = get_call_hierarchy(to_id, tool_context, direction='incoming')
        
        paths = []
        
        # Check if there's a direct call
        if from_result.get('status') == 'ok':
            for outgoing in from_result.get('outgoing_calls', []):
                if to_id in outgoing.get('to', ''):
                    paths.append({
                        'path': [from_id, to_id],
                        'type': 'direct_call'
                    })
        
        # If no direct path, try indirect
        if not paths and from_result.get('status') == 'ok':
            for outgoing in from_result.get('outgoing_calls', []):
                intermediate = outgoing.get('to')
                # Check if intermediate calls to_id
                intermediate_result = get_call_hierarchy(intermediate, tool_context, direction='outgoing')
                if intermediate_result.get('status') == 'ok':
                    for next_out in intermediate_result.get('outgoing_calls', []):
                        if to_id in next_out.get('to', ''):
                            paths.append({
                                'path': [from_id, intermediate, to_id],
                                'type': 'indirect_call'
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
    """Find components depending on a selected component."""
    try:
        from .navigation_tools import get_symbol_references
        from .repository_tools import search_code
        
        dependents = []
        
        # Find references
        ref_result = get_symbol_references(component_id, tool_context)
        if ref_result.get('status') == 'ok':
            for ref in ref_result['references']:
                dependents.append({
                    'component': ref['file'],
                    'line': ref['line'],
                    'type': ref.get('type', 'reference')
                })
        
        # Find imports
        import_patterns = [
            f'import {component_id}',
            f'from {component_id} import'
        ]
        for pattern in import_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    if match['file'] not in [d['component'] for d in dependents]:
                        dependents.append({
                            'component': match['file'],
                            'line': match['line'],
                            'type': 'import'
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
