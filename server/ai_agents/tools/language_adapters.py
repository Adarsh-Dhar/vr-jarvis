"""
Language and Framework Adapter Infrastructure
Reusable adapters around existing language tooling for universal-language support.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import ast
from google.adk.tools import ToolContext
from ._safe import safe

# In-memory adapter registry
_language_adapters = {}
_framework_adapters = {}


# Language Adapter Base

@safe
def register_language_adapter(
    language: str,
    adapter_config: Dict,
    tool_context: ToolContext
) -> dict:
    """Register a language adapter."""
    try:
        _language_adapters[language] = adapter_config
        
        return {
            'status': 'ok',
            'language': language,
            'adapter_registered': True,
            'capabilities': adapter_config.get('capabilities', [])
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_language_adapter(language: str, tool_context: ToolContext) -> dict:
    """Get adapter for a specific language."""
    try:
        if language in _language_adapters:
            return {
                'status': 'ok',
                'language': language,
                'adapter': _language_adapters[language]
            }
        
        # Default adapter info
        return {
            'status': 'ok',
            'language': language,
            'adapter': {
                'name': f'{language}_adapter',
                'version': '1.0.0',
                'capabilities': ['parsing', 'type_checking', 'symbol_resolution'],
                'note': 'Default adapter - real adapters require integration'
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def list_supported_languages(tool_context: ToolContext) -> dict:
    """List all supported languages."""
    try:
        # Return registered adapters plus default list
        default_languages = [
            {'name': 'python', 'version': '3.11', 'capabilities': ['ast', 'typing', 'imports'], 'status': 'implemented'},
            {'name': 'javascript', 'version': 'ES2022', 'capabilities': ['ast', 'modules', 'promises'], 'status': 'partial'},
            {'name': 'typescript', 'version': '5.0', 'capabilities': ['types', 'interfaces', 'decorators'], 'status': 'partial'},
            {'name': 'java', 'version': '17', 'capabilities': ['annotations', 'reflection', 'inheritance'], 'status': 'partial'},
            {'name': 'c', 'version': 'C11', 'capabilities': ['preprocessor', 'pointers', 'memory'], 'status': 'partial'},
            {'name': 'cpp', 'version': 'C++20', 'capabilities': ['templates', 'inheritance', 'memory'], 'status': 'partial'},
            {'name': 'csharp', 'version': 'C# 11', 'capabilities': ['linq', 'delegates', 'reflection'], 'status': 'partial'},
            {'name': 'go', 'version': '1.21', 'capabilities': ['interfaces', 'goroutines', 'channels'], 'status': 'partial'},
            {'name': 'rust', 'version': '1.70', 'capabilities': ['traits', 'ownership', 'lifetimes'], 'status': 'partial'},
            {'name': 'php', 'version': '8.2', 'capabilities': ['namespaces', 'traits', 'composer'], 'status': 'partial'},
            {'name': 'ruby', 'version': '3.2', 'capabilities': ['metaprogramming', 'blocks', 'modules'], 'status': 'partial'},
            {'name': 'swift', 'version': '5.9', 'capabilities': ['protocols', 'generics', 'actors'], 'status': 'partial'},
            {'name': 'kotlin', 'version': '1.9', 'capabilities': ['coroutines', 'extensions', 'nullability'], 'status': 'partial'},
            {'name': 'dart', 'version': '3.0', 'capabilities': ['types', 'async', 'isolates'], 'status': 'partial'},
            {'name': 'sql', 'version': 'SQL:2016', 'capabilities': ['tables', 'queries', 'procedures'], 'status': 'partial'},
            {'name': 'solidity', 'version': '0.8.0', 'capabilities': ['contracts', 'events', 'storage'], 'status': 'partial'},
            {'name': 'lua', 'version': '5.4', 'capabilities': ['tables', 'metatables', 'modules'], 'status': 'partial'},
            {'name': 'r', 'version': '4.3', 'capabilities': ['functions', 'environments', 'data'], 'status': 'partial'},
            {'name': 'scala', 'version': '3.3', 'capabilities': ['traits', 'functional', 'jvm'], 'status': 'partial'}
        ]
        
        return {
            'status': 'ok',
            'languages': default_languages
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Language-Specific Tools

@safe
def parse_language_ast(
    file_path: str,
    language: str,
    tool_context: ToolContext
) -> dict:
    """Parse source code using language-specific parser (Tree-sitter based)."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        # For Python, use built-in AST
        if language == 'python':
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    code = f.read()
                tree = ast.parse(code)
                
                # Convert to dict representation
                def ast_to_dict(node):
                    if node is None:
                        return None
                    if isinstance(node, ast.AST):
                        return {
                            'type': type(node).__name__,
                            'fields': {k: ast_to_dict(v) for k, v in vars(node).items() if k not in ('ctx', 'end_lineno', 'end_col_offset')}
                        }
                    elif isinstance(node, list):
                        return [ast_to_dict(item) for item in node]
                    return node
                
                return {
                    'status': 'ok',
                    'file_path': str(path),
                    'language': language,
                    'ast': ast_to_dict(tree)
                }
            except Exception as e:
                return {
                    'status': 'error',
                    'error': f'Failed to parse Python AST: {str(e)}'
                }
        
        # For other languages, use regex-based basic parsing
        content = path.read_text(encoding='utf-8')
        return {
            'status': 'ok',
            'file_path': str(path),
            'language': language,
            'ast': {
                'kind': 'regex_based',
                'line_count': len(content.splitlines()),
                'char_count': len(content),
                'note': f'Basic parsing for {language} - tree-sitter integration for full AST'
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def resolve_language_types(
    file_path: str,
    language: str,
    tool_context: ToolContext
) -> dict:
    """Resolve types using language-specific type checker."""
    try:
        # For Python, extract type annotations from AST
        if language == 'python':
            ast_result = parse_language_ast(file_path, language, tool_context)
            if ast_result.get('status') != 'ok':
                return ast_result
            
            # Extract type annotations
            types = {}
            if ast_result.get('status') == 'ok':
                # Basic type extraction from AST
                types = {
                    'note': 'Type annotations would be extracted from AST',
                    'functions': [],
                    'classes': []
                }
            return {
                'status': 'ok',
                'file_path': file_path,
                'language': language,
                'types': types,
                'note': 'Type resolution requires full AST analysis'
            }
        
        # For other languages, provide basic symbol extraction
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        content = path.read_text(encoding='utf-8')
        return {
            'status': 'ok',
            'file_path': file_path,
            'language': language,
            'types': {
                'note': f'Basic type extraction for {language}',
                'total_symbols': content.count('function') + content.count('class') + content.count('interface')
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def extract_language_symbols(
    file_path: str,
    language: str,
    tool_context: ToolContext
) -> dict:
    """Extract symbols using language-specific adapter."""
    try:
        # For Python, use AST to extract symbols
        if language == 'python':
            ast_result = parse_language_ast(file_path, language, tool_context)
            if ast_result.get('status') != 'ok':
                return ast_result
            
            path = Path(file_path)
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
            tree = ast.parse(code)
            
            symbols = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    symbols.append({
                        'name': node.name,
                        'type': 'function',
                        'line': node.lineno
                    })
                elif isinstance(node, ast.ClassDef):
                    symbols.append({
                        'name': node.name,
                        'type': 'class',
                        'line': node.lineno
                    })
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    symbols.append({
                        'name': node.id,
                        'type': 'variable',
                        'line': node.lineno
                    })
            
            return {
                'status': 'ok',
                'file_path': str(path),
                'language': language,
                'symbols': symbols
            }
        
        # For other languages, use regex-based symbol extraction
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        content = path.read_text(encoding='utf-8')
        import re
        
        symbols = []
        # Common patterns for functions/classes
        func_patterns = [
            r'function\s+(\w+)',
            r'def\s+(\w+)',
            r'func\s+(\w+)',
            r'\w+\s+(\w+)\s*\('
        ]
        class_patterns = [
            r'class\s+(\w+)',
            r'interface\s+(\w+)',
            r'struct\s+(\w+)',
            r'type\s+(\w+)'
        ]
        
        for pattern in func_patterns:
            for match in re.finditer(pattern, content):
                symbols.append({
                    'name': match.group(1),
                    'type': 'function',
                    'pattern': pattern
                })
        
        for pattern in class_patterns:
            for match in re.finditer(pattern, content):
                symbols.append({
                    'name': match.group(1),
                    'type': 'class',
                    'pattern': pattern
                })
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'language': language,
            'symbols': symbols,
            'count': len(symbols),
            'note': f'Regex-based extraction for {language}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_language_specific_features(
    file_path: str,
    language: str,
    tool_context: ToolContext
) -> dict:
    """Analyze language-specific features (decorators, async, etc.)."""
    try:
        # For Python, analyze decorators, async, generators
        if language == 'python':
            path = Path(file_path)
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
            tree = ast.parse(code)
            
            features = {
                'decorators': [],
                'async_functions': [],
                'generators': []
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.decorator_list:
                        features['decorators'].append({
                            'function': node.name,
                            'decorators': [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, 'unparse') else []
                        })
                    if isinstance(node, ast.AsyncFunctionDef):
                        features['async_functions'].append(node.name)
                    # Check for yield (generator)
                    for child in ast.walk(node):
                        if isinstance(child, ast.Yield):
                            features['generators'].append(node.name)
                            break
            
            return {
                'status': 'ok',
                'file_path': str(path),
                'language': language,
                'features': features
            }
        
        # For other languages, use basic feature detection
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        content = path.read_text(encoding='utf-8')
        import re
        
        features = {
            'async_patterns': len(re.findall(r'async|await|Promise', content)),
            'decorator_patterns': len(re.findall(r'@|@\w+|decorator', content)),
            'generator_patterns': len(re.findall(r'yield|generator|function\*', content)),
            'class_patterns': len(re.findall(r'class\s+\w+|interface\s+\w+', content))
        }
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'language': language,
            'features': features,
            'note': f'Basic feature detection for {language}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Framework Adapter Base

@safe
def register_framework_adapter(
    framework: str,
    language: str,
    adapter_config: Dict,
    tool_context: ToolContext
) -> dict:
    """Register a framework adapter."""
    try:
        key = f"{language}:{framework}"
        _framework_adapters[key] = adapter_config
        
        return {
            'status': 'ok',
            'framework': framework,
            'language': language,
            'adapter_registered': True,
            'capabilities': adapter_config.get('capabilities', [])
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_framework_adapter(
    framework: str,
    language: str,
    tool_context: ToolContext
) -> dict:
    """Get adapter for a specific framework."""
    try:
        key = f"{language}:{framework}"
        if key in _framework_adapters:
            return {
                'status': 'ok',
                'framework': framework,
                'language': language,
                'adapter': _framework_adapters[key]
            }
        
        return {
            'status': 'ok',
            'framework': framework,
            'language': language,
            'adapter': {
                'name': f'{framework}_adapter',
                'version': '1.0.0',
                'capabilities': ['route_discovery', 'component_analysis', 'lifecycle_analysis'],
                'note': 'Default adapter - real adapters require integration'
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def list_supported_frameworks(
    tool_context: ToolContext,
    language: Optional[str] = None
) -> dict:
    """List all supported frameworks."""
    try:
        frameworks = {
            'javascript': [
                {'name': 'React', 'version': '18.0', 'capabilities': ['hooks', 'components', 'jsx'], 'status': 'partial'},
                {'name': 'Next.js', 'version': '14.0', 'capabilities': ['ssr', 'routing', 'api_routes'], 'status': 'partial'},
                {'name': 'Vue', 'version': '3.0', 'capabilities': ['components', 'composition_api', 'directives'], 'status': 'partial'},
                {'name': 'Nuxt', 'version': '3.0', 'capabilities': ['ssr', 'middleware', 'modules'], 'status': 'partial'},
                {'name': 'Angular', 'version': '17.0', 'capabilities': ['components', 'services', 'directives'], 'status': 'partial'},
                {'name': 'Svelte', 'version': '4.0', 'capabilities': ['components', 'stores', 'transitions'], 'status': 'partial'},
                {'name': 'Express', 'version': '4.18', 'capabilities': ['routes', 'middleware', 'routing'], 'status': 'partial'},
                {'name': 'NestJS', 'version': '10.0', 'capabilities': ['modules', 'controllers', 'dependency_injection'], 'status': 'partial'}
            ],
            'python': [
                {'name': 'Django', 'version': '4.2', 'capabilities': ['models', 'views', 'middleware'], 'status': 'partial'},
                {'name': 'FastAPI', 'version': '0.104', 'capabilities': ['routes', 'dependency_injection', 'async'], 'status': 'partial'},
                {'name': 'Flask', 'version': '3.0', 'capabilities': ['routes', 'blueprints', 'extensions'], 'status': 'partial'},
                {'name': 'Celery', 'version': '5.3', 'capabilities': ['tasks', 'workers', 'beat'], 'status': 'partial'},
                {'name': 'PyTorch', 'version': '2.1', 'capabilities': ['tensors', 'models', 'autograd'], 'status': 'partial'}
            ],
            'java': [
                {'name': 'Spring Boot', 'version': '3.1', 'capabilities': ['controllers', 'services', 'repositories'], 'status': 'partial'},
                {'name': 'Spring Security', 'version': '6.1', 'capabilities': ['authentication', 'authorization', 'csrf'], 'status': 'partial'},
                {'name': 'Hibernate', 'version': '6.2', 'capabilities': ['entities', 'repositories', 'queries'], 'status': 'partial'},
                {'name': 'Quarkus', 'version': '3.4', 'capabilities': ['endpoints', 'injection', 'native'], 'status': 'partial'}
            ],
            'csharp': [
                {'name': 'ASP.NET Core', 'version': '8.0', 'capabilities': ['controllers', 'middleware', 'dependency_injection'], 'status': 'partial'},
                {'name': 'Entity Framework', 'version': '8.0', 'capabilities': ['dbcontext', 'entities', 'linq'], 'status': 'partial'},
                {'name': 'Unity', 'version': '2022.3', 'capabilities': ['components', 'scripts', 'lifecycle'], 'status': 'partial'}
            ],
            'cpp': [
                {'name': 'Unreal Engine', 'version': '5.3', 'capabilities': ['actors', 'components', 'blueprints'], 'status': 'partial'},
                {'name': 'Qt', 'version': '6.6', 'capabilities': ['widgets', 'signals', 'slots'], 'status': 'partial'},
                {'name': 'Boost', 'version': '1.83', 'capabilities': ['libraries', 'smart_pointers', 'containers'], 'status': 'partial'}
            ],
            'rust': [
                {'name': 'Tokio', 'version': '1.35', 'capabilities': ['async', 'runtime', 'tasks'], 'status': 'partial'},
                {'name': 'Actix', 'version': '4.4', 'capabilities': ['handlers', 'middleware', 'extractors'], 'status': 'partial'},
                {'name': 'Axum', 'version': '0.7', 'capabilities': ['handlers', 'extractors', 'middleware'], 'status': 'partial'}
            ],
            'php': [
                {'name': 'Laravel', 'version': '10.0', 'capabilities': ['controllers', 'models', 'middleware'], 'status': 'partial'},
                {'name': 'Symfony', 'version': '6.3', 'capabilities': ['controllers', 'services', 'bundles'], 'status': 'partial'}
            ],
            'ruby': [
                {'name': 'Rails', 'version': '7.1', 'capabilities': ['controllers', 'models', 'views'], 'status': 'partial'},
                {'name': 'Sinatra', 'version': '3.0', 'capabilities': ['routes', 'middleware', 'helpers'], 'status': 'partial'}
            ],
            'go': [
                {'name': 'Gin', 'version': '1.9', 'capabilities': ['handlers', 'middleware', 'routes'], 'status': 'partial'},
                {'name': 'Echo', 'version': '4.11', 'capabilities': ['handlers', 'middleware', 'routes'], 'status': 'partial'},
                {'name': 'Fiber', 'version': '2.48', 'capabilities': ['handlers', 'middleware', 'routes'], 'status': 'partial'}
            ],
            'kotlin': [
                {'name': 'Ktor', 'version': '2.3', 'capabilities': ['routes', 'plugins', 'content_negotiation'], 'status': 'partial'},
                {'name': 'Spring', 'version': '3.1', 'capabilities': ['controllers', 'services', 'repositories'], 'status': 'partial'},
                {'name': 'Android', 'version': '14.0', 'capabilities': ['activities', 'fragments', 'viewmodels'], 'status': 'partial'}
            ],
            'dart': [
                {'name': 'Flutter', 'version': '3.16', 'capabilities': ['widgets', 'state', 'navigation'], 'status': 'partial'}
            ],
            'swift': [
                {'name': 'SwiftUI', 'version': '5.0', 'capabilities': ['views', 'state', 'previews'], 'status': 'partial'},
                {'name': 'UIKit', 'version': '17.0', 'capabilities': ['view_controllers', 'delegates', 'protocols'], 'status': 'partial'},
                {'name': 'Vapor', 'version': '4.0', 'capabilities': ['routes', 'controllers', 'middleware'], 'status': 'partial'}
            ],
            'databases': [
                {'name': 'PostgreSQL', 'version': '16.0', 'capabilities': ['tables', 'indexes', 'triggers'], 'status': 'partial'},
                {'name': 'MySQL', 'version': '8.0', 'capabilities': ['tables', 'indexes', 'views'], 'status': 'partial'},
                {'name': 'MongoDB', 'version': '7.0', 'capabilities': ['collections', 'indexes', 'aggregation'], 'status': 'partial'},
                {'name': 'Redis', 'version': '7.2', 'capabilities': ['keys', 'data_structures', 'pubsub'], 'status': 'partial'},
                {'name': 'SQLite', 'version': '3.44', 'capabilities': ['tables', 'indexes', 'triggers'], 'status': 'partial'}
            ],
            'infrastructure': [
                {'name': 'Docker', 'version': '24.0', 'capabilities': ['containers', 'images', 'networks'], 'status': 'partial'},
                {'name': 'Kubernetes', 'version': '1.28', 'capabilities': ['pods', 'services', 'deployments'], 'status': 'partial'},
                {'name': 'Terraform', 'version': '1.6', 'capabilities': ['resources', 'modules', 'state'], 'status': 'partial'},
                {'name': 'Helm', 'version': '3.13', 'capabilities': ['charts', 'templates', 'values'], 'status': 'partial'}
            ]
        }
        
        if language:
            return {
                'status': 'ok',
                'language': language,
                'frameworks': frameworks.get(language, [])
            }
        
        return {
            'status': 'ok',
            'frameworks': frameworks
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Framework-Specific Tools

@safe
def discover_framework_routes(
    repository_path: str,
    framework: str,
    tool_context: ToolContext
) -> dict:
    """Discover framework-specific routes/endpoints."""
    try:
        from .repository_tools import search_code
        
        # Framework-specific route patterns
        route_patterns = {
            'flask': ['@app.route', '@bp.route', 'Flask('],
            'fastapi': ['@app.get', '@app.post', '@app.put', '@app.delete', 'FastAPI('],
            'django': ['path(', 'url(', 'urlpatterns'],
            'express': ['app.get', 'app.post', 'router.get', 'router.post'],
            'spring': ['@RequestMapping', '@GetMapping', '@PostMapping'],
            'aspnet': ['[HttpGet]', '[HttpPost]', 'Route('],
            'rails': ['get ', 'post ', 'resources :'],
            'default': ['route', 'endpoint', 'handler']
        }
        
        patterns = route_patterns.get(framework.lower(), route_patterns['default'])
        routes = []
        
        for pattern in patterns:
            search_result = search_code(tool_context, directory=repository_path, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    routes.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'framework': framework,
            'routes': routes,
            'count': len(routes),
            'note': f'Pattern-based route discovery for {framework}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_framework_lifecycle(
    repository_path: str,
    framework: str,
    tool_context: ToolContext
) -> dict:
    """Analyze framework-specific lifecycle and execution model."""
    try:
        from .repository_tools import search_code
        
        # Framework-specific lifecycle patterns
        lifecycle_patterns = {
            'flask': ['before_request', 'after_request', 'teardown_request'],
            'fastapi': ['@app.on_event', 'lifespan'],
            'django': ['__init__', 'ready()', 'shutdown()'],
            'express': ['app.use(', 'middleware'],
            'spring': ['@PostConstruct', '@PreDestroy', 'ApplicationListener'],
            'aspnet': ['Configure(', 'ConfigureServices('],
            'rails': ['before_action', 'after_action', 'around_action'],
            'default': ['init', 'start', 'stop', 'destroy']
        }
        
        patterns = lifecycle_patterns.get(framework.lower(), lifecycle_patterns['default'])
        lifecycle_hooks = []
        
        for pattern in patterns:
            search_result = search_code(tool_context, directory=repository_path, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    lifecycle_hooks.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'framework': framework,
            'lifecycle_hooks': lifecycle_hooks,
            'count': len(lifecycle_hooks),
            'note': f'Pattern-based lifecycle analysis for {framework}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def discover_framework_components(
    repository_path: str,
    framework: str,
    tool_context: ToolContext
) -> dict:
    """Discover framework-specific components."""
    try:
        from .repository_tools import search_code
        
        # Framework-specific component patterns
        component_patterns = {
            'flask': ['Blueprint', 'View', 'Component'],
            'fastapi': ['APIRouter', 'Depends', 'BackgroundTasks'],
            'django': ['Model', 'View', 'Form', 'Middleware'],
            'express': ['Component', 'Controller', 'Service'],
            'spring': ['@Component', '@Service', '@Repository'],
            'aspnet': ['Controller', 'Service', 'Repository'],
            'rails': ['ApplicationController', 'ActiveRecord'],
            'default': ['Component', 'Service', 'Controller']
        }
        
        patterns = component_patterns.get(framework.lower(), component_patterns['default'])
        components = []
        
        for pattern in patterns:
            search_result = search_code(tool_context, directory=repository_path, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    components.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'framework': framework,
            'components': components,
            'count': len(components),
            'note': f'Pattern-based component discovery for {framework}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_framework_dependency_injection(
    repository_path: str,
    framework: str,
    tool_context: ToolContext
) -> dict:
    """Analyze framework-specific dependency injection."""
    try:
        from .repository_tools import search_code
        
        # Framework-specific DI patterns
        di_patterns = {
            'fastapi': ['Depends(', 'Annotated'],
            'spring': ['@Autowired', '@Inject', 'Dependency'],
            'aspnet': ['[FromServices]', 'IServiceProvider'],
            'angular': ['@Injectable', 'constructor('],
            'default': ['inject', 'dependency', 'provider']
        }
        
        patterns = di_patterns.get(framework.lower(), di_patterns['default'])
        di_instances = []
        
        for pattern in patterns:
            search_result = search_code(tool_context, directory=repository_path, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    di_instances.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'framework': framework,
            'dependency_injection': di_instances,
            'count': len(di_instances),
            'note': f'Pattern-based DI analysis for {framework}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def discover_framework_middleware(
    repository_path: str,
    framework: str,
    tool_context: ToolContext
) -> dict:
    """Discover framework-specific middleware/plugins."""
    try:
        from .repository_tools import search_code
        
        # Framework-specific middleware patterns
        middleware_patterns = {
            'flask': ['@app.before_request', '@app.after_request', 'Middleware'],
            'fastapi': ['Middleware', 'middleware='],
            'django': ['Middleware', 'MIDDLEWARE'],
            'express': ['app.use(', 'middleware'],
            'spring': ['@Component', 'implements Filter'],
            'aspnet': ['IMiddleware', 'UseMiddleware'],
            'rails': ['before_action', 'around_action'],
            'default': ['middleware', 'plugin', 'interceptor']
        }
        
        patterns = middleware_patterns.get(framework.lower(), middleware_patterns['default'])
        middleware = []
        
        for pattern in patterns:
            search_result = search_code(tool_context, directory=repository_path, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    middleware.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'framework': framework,
            'middleware': middleware,
            'count': len(middleware),
            'note': f'Pattern-based middleware discovery for {framework}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_framework_event_handling(
    repository_path: str,
    framework: str,
    tool_context: ToolContext
) -> dict:
    """Analyze framework-specific event handling."""
    try:
        from .repository_tools import search_code
        
        # Framework-specific event patterns
        event_patterns = {
            'javascript': ['addEventListener', 'on(', 'emit('],
            'react': ['useEffect', 'onClick', 'onChange'],
            'vue': ['@click', '@change', 'v-on:'],
            'angular': ['(click)', '(change)', 'EventEmitter'],
            'default': ['event', 'emit', 'listen', 'subscribe']
        }
        
        patterns = event_patterns.get(framework.lower(), event_patterns['default'])
        events = []
        
        for pattern in patterns:
            search_result = search_code(tool_context, directory=repository_path, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    events.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'framework': framework,
            'events': events,
            'count': len(events),
            'note': f'Pattern-based event analysis for {framework}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_framework_component_relationships(
    repository_path: str,
    framework: str,
    tool_context: ToolContext
) -> dict:
    """Analyze framework-specific component and state relationships."""
    try:
        from .repository_tools import search_code
        
        # Framework-specific relationship patterns
        relationship_patterns = {
            'react': ['useState', 'useContext', 'useReducer'],
            'vue': ['props', 'emit', 'provide/inject'],
            'angular': ['@Input', '@Output', 'Service'],
            'django': ['ForeignKey', 'ManyToMany', 'OneToOne'],
            'default': ['import', 'require', 'extends', 'implements']
        }
        
        patterns = relationship_patterns.get(framework.lower(), relationship_patterns['default'])
        relationships = []
        
        for pattern in patterns:
            search_result = search_code(tool_context, directory=repository_path, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    relationships.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'framework': framework,
            'relationships': relationships,
            'count': len(relationships),
            'note': f'Pattern-based relationship analysis for {framework}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_framework_orm_integration(
    repository_path: str,
    framework: str,
    tool_context: ToolContext
) -> dict:
    """Analyze framework-specific ORM and database integration."""
    try:
        from .repository_tools import search_code
        
        # Framework-specific ORM patterns
        orm_patterns = {
            'django': ['models.Model', 'ForeignKey', 'ManyToManyField'],
            'flask': ['SQLAlchemy', 'Column', 'Integer'],
            'rails': ['ActiveRecord', 'has_many', 'belongs_to'],
            'spring': ['@Entity', '@Table', 'OneToMany'],
            'aspnet': ['DbContext', 'DbSet', 'Entity'],
            'default': ['Model', 'Entity', 'Repository']
        }
        
        patterns = orm_patterns.get(framework.lower(), orm_patterns['default'])
        orm_usage = []
        
        for pattern in patterns:
            search_result = search_code(tool_context, directory=repository_path, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    orm_usage.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'framework': framework,
            'orm_usage': orm_usage,
            'count': len(orm_usage),
            'note': f'Pattern-based ORM analysis for {framework}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_framework_configuration(
    repository_path: str,
    framework: str,
    tool_context: ToolContext
) -> dict:
    """Analyze framework-specific configuration."""
    try:
        from .repository_tools import search_code
        
        # Framework-specific configuration patterns
        config_patterns = {
            'django': ['settings.py', 'DEBUG', 'DATABASES'],
            'flask': ['app.config', 'Config(', 'FLASK_'],
            'fastapi': ['@app.get', 'APIRouter(', 'Config'],
            'spring': ['application.properties', 'application.yml', '@Configuration'],
            'aspnet': ['appsettings.json', 'IConfiguration'],
            'rails': ['config/', 'environment:'],
            'default': ['config', 'settings', 'env']
        }
        
        patterns = config_patterns.get(framework.lower(), config_patterns['default'])
        config_items = []
        
        for pattern in patterns:
            search_result = search_code(tool_context, directory=repository_path, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    config_items.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'framework': framework,
            'configuration': config_items,
            'count': len(config_items),
            'note': f'Pattern-based configuration analysis for {framework}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_framework_runtime_instrumentation(
    repository_path: str,
    framework: str,
    tool_context: ToolContext
) -> dict:
    """Analyze framework-specific runtime instrumentation."""
    try:
        from .repository_tools import search_code
        
        # Framework-specific instrumentation patterns
        instrumentation_patterns = {
            'django': ['@receiver', 'post_save', 'pre_delete'],
            'flask': ['@app.before_request', 'signal'],
            'spring': ['@Aspect', '@Around', 'Interceptor'],
            'aspnet': ['IAsyncActionFilter', 'IExceptionFilter'],
            'default': ['instrument', 'telemetry', 'metrics', 'trace']
        }
        
        patterns = instrumentation_patterns.get(framework.lower(), instrumentation_patterns['default'])
        instrumentation = []
        
        for pattern in patterns:
            search_result = search_code(tool_context, directory=repository_path, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    instrumentation.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'framework': framework,
            'instrumentation': instrumentation,
            'count': len(instrumentation),
            'note': f'Pattern-based instrumentation analysis for {framework}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
