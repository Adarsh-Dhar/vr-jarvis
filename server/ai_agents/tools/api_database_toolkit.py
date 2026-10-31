"""
Specialist Toolkit A - API and Database Intelligence
Important for understanding full-stack applications.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import ast
import re
import subprocess
from google.adk.tools import ToolContext
from ._safe import safe


# API Intelligence Tools

@safe
def discover_api_endpoints(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Find application endpoints."""
    try:
        from .repository_tools import search_code
        
        # Search for common endpoint patterns
        endpoint_patterns = [
            '@app.route',
            '@api.route',
            '@bp.route',
            'router.get',
            'router.post',
            'router.put',
            'router.delete',
            'app.get',
            'app.post',
            'GET',
            'POST',
            'PUT',
            'DELETE'
        ]
        
        endpoints = []
        for pattern in endpoint_patterns:
            search_result = search_code(tool_context, directory=repository_path, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    endpoints.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'endpoints': endpoints,
            'count': len(endpoints)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_api_schema(
    schema_path: str,
    tool_context: ToolContext,
    schema_type: str = 'openapi'
) -> dict:
    """Read OpenAPI, GraphQL and other API schemas."""
    try:
        path = Path(schema_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'Schema file not found: {schema_path}'
            }
        
        content = path.read_text(encoding='utf-8')
        
        if schema_type == 'openapi':
            try:
                schema = json.loads(content)
                return {
                    'status': 'ok',
                    'schema_path': str(path),
                    'schema_type': schema_type,
                    'schema': schema
                }
            except json.JSONDecodeError:
                return {
                    'status': 'error',
                    'error': 'Invalid JSON schema'
                }
        
        # For other schema types, provide basic information
        schema_info = {
            'file_size': path.stat().st_size,
            'line_count': len(content.splitlines()),
            'preview': content[:500] + '...' if len(content) > 500 else content
        }
        
        return {
            'status': 'ok',
            'schema_path': str(path),
            'schema_type': schema_type,
            'schema_info': schema_info,
            'note': f'Full {schema_type} schema parsing requires specific integration. Basic file information provided.'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_api_contract(
    endpoint: str,
    tool_context: ToolContext
) -> dict:
    """Analyze API contract (request/response)."""
    try:
        from .repository_tools import search_code
        
        # Search for endpoint definition and related code
        endpoint_matches = []
        
        # Search for the endpoint pattern
        search_result = search_code(tool_context, query=endpoint)
        if search_result.get('status') == 'ok':
            endpoint_matches = search_result['matches']
        
        # Look for request/response handling patterns
        request_patterns = ['request.json', 'request.body', 'req.body', 'request.get_json']
        response_patterns = ['return jsonify', 'response.json', 'res.json', 'HttpResponse']
        
        request_handlers = []
        response_handlers = []
        
        for pattern in request_patterns:
            result = search_code(tool_context, query=pattern)
            if result.get('status') == 'ok':
                request_handlers.extend(result['matches'])
        
        for pattern in response_patterns:
            result = search_code(tool_context, query=pattern)
            if result.get('status') == 'ok':
                response_handlers.extend(result['matches'])
        
        return {
            'status': 'ok',
            'endpoint': endpoint,
            'endpoint_matches': endpoint_matches,
            'request_handlers': request_handlers[:5],  # Limit to 5 for brevity
            'response_handlers': response_handlers[:5],
            'note': 'Full contract analysis requires runtime integration or schema inspection'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_api_call(
    endpoint: str,
    tool_context: ToolContext
) -> dict:
    """Trace an API call through the application."""
    try:
        from .repository_tools import search_code
        
        # Search for endpoint definition
        endpoint_def = search_code(tool_context, query=endpoint)
        
        # Search for middleware and interceptor patterns
        middleware_patterns = ['@app.before_request', '@app.after_request', 'middleware', 'interceptor']
        middleware_matches = []
        
        for pattern in middleware_patterns:
            result = search_code(tool_context, query=pattern)
            if result.get('status') == 'ok':
                middleware_matches.extend(result['matches'])
        
        # Search for database calls in the context
        db_patterns = ['db.session', 'Model.query', 'SELECT', 'INSERT', 'UPDATE', 'DELETE']
        db_matches = []
        
        for pattern in db_patterns:
            result = search_code(tool_context, query=pattern)
            if result.get('status') == 'ok':
                db_matches.extend(result['matches'])
        
        return {
            'status': 'ok',
            'endpoint': endpoint,
            'endpoint_definition': endpoint_def.get('matches', []) if endpoint_def.get('status') == 'ok' else [],
            'middleware_components': middleware_matches[:5],
            'database_operations': db_matches[:5],
            'trace_path': [
                'request_received',
                'middleware_processing',
                'route_handler',
                'business_logic',
                'database_operations',
                'response_generation'
            ],
            'note': 'Detailed call tracing requires runtime instrumentation'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_api_security(
    endpoint: str,
    tool_context: ToolContext
) -> dict:
    """Analyze API security (auth, rate limiting, etc.)."""
    try:
        from .repository_tools import search_code
        
        # Search for security-related patterns
        security_patterns = {
            'authentication': ['@login_required', 'authenticate', 'jwt', 'oauth', 'auth', 'login'],
            'authorization': ['@permission_required', 'authorize', 'role', 'permission', 'access'],
            'rate_limiting': ['rate_limit', 'throttle', 'limiter', 'ratelimit'],
            'csrf_protection': ['csrf', 'csrf_token', 'protect_csrf'],
            'input_validation': ['validate', 'schema', 'validator', 'sanitize'],
            'cors': ['cors', 'cross_origin', 'CORS']
        }
        
        security_findings = {}
        
        for security_type, patterns in security_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            security_findings[security_type] = matches[:5]  # Limit to 5 per type
        
        # Check for endpoint-specific security
        endpoint_security = search_code(tool_context, query=endpoint)
        
        return {
            'status': 'ok',
            'endpoint': endpoint,
            'security_findings': security_findings,
            'endpoint_security': endpoint_security.get('matches', []) if endpoint_security.get('status') == 'ok' else [],
            'recommendations': [
                'Ensure authentication is properly implemented',
                'Check for rate limiting on public endpoints',
                'Validate input data',
                'Use HTTPS in production',
                'Implement proper error handling without exposing sensitive information'
            ],
            'note': 'Full security analysis requires framework adapter integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_http_routes(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Inspect HTTP routes."""
    try:
        from .repository_tools import search_code
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for route definitions across different frameworks
        route_patterns = {
            'flask': ['@app.route', '@bp.route', 'Blueprint.route'],
            'fastapi': ['@app.get', '@app.post', '@app.put', '@app.delete', '@app.patch'],
            'django': ['path(', 'url(', 'urlpatterns'],
            'express': ['app.get', 'app.post', 'app.put', 'app.delete', 'router.'],
            'spring': ['@RequestMapping', '@GetMapping', '@PostMapping', '@PutMapping', '@DeleteMapping']
        }
        
        routes = []
        
        for framework, patterns in route_patterns.items():
            for pattern in patterns:
                result = search_code(tool_context, directory=repository_path, query=pattern)
                if result.get('status') == 'ok':
                    for match in result['matches']:
                        routes.append({
                            'framework': framework,
                            'pattern': pattern,
                            'file': match['file'],
                            'line': match['line'],
                            'snippet': match['snippet']
                        })
        
        # Parse Python files for more detailed route information
        python_routes = []
        for py_file in path.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        for decorator in node.decorator_list:
                            if isinstance(decorator, ast.Call):
                                if hasattr(decorator.func, 'id') and 'route' in decorator.func.id.lower():
                                    python_routes.append({
                                        'file': str(py_file.relative_to(path)),
                                        'function': node.name,
                                        'line': node.lineno
                                    })
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'total_routes': len(routes),
            'routes': routes[:20],  # Limit to 20 for brevity
            'python_routes': python_routes[:20],
            'frameworks_detected': list(set(r['framework'] for r in routes)),
            'note': 'Detailed route inspection requires framework adapter integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_request_lifecycle(
    endpoint: str,
    tool_context: ToolContext
) -> dict:
    """Trace request lifecycle."""
    try:
        from .repository_tools import search_code
        
        # Search for lifecycle components
        lifecycle_stages = {
            'request_reception': ['request', 'req', 'Request'],
            'middleware_processing': ['middleware', 'before_request', 'after_request'],
            'routing': ['route', 'router', 'urlpatterns'],
            'controller': ['controller', 'view', 'handler'],
            'service_layer': ['service', 'business', 'logic'],
            'data_access': ['db.session', 'query', 'repository', 'dao'],
            'response': ['response', 'res', 'Response', 'jsonify'],
            'error_handling': ['exception', 'error', 'Error', 'try:', 'except']
        }
        
        lifecycle_findings = {}
        
        for stage, patterns in lifecycle_stages.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            lifecycle_findings[stage] = matches[:3]  # Limit to 3 per stage
        
        return {
            'status': 'ok',
            'endpoint': endpoint,
            'lifecycle_stages': lifecycle_findings,
            'typical_flow': [
                '1. Request received by server',
                '2. Middleware chain processes request',
                '3. Router matches endpoint',
                '4. Controller/handler executes',
                '5. Service layer processes business logic',
                '6. Data access layer queries database',
                '7. Response is constructed',
                '8. Middleware processes response',
                '9. Response sent to client'
            ],
            'note': 'Detailed lifecycle tracing requires runtime instrumentation'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_middleware(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Inspect middleware."""
    try:
        from .repository_tools import search_code
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for middleware patterns
        middleware_patterns = {
            'flask': ['@app.before_request', '@app.after_request', '@app.teardown_request'],
            'express': ['app.use(', 'middleware', 'express.json'],
            'django': ['MIDDLEWARE', 'middleware_classes'],
            'fastapi': ['@app.middleware', 'Middleware'],
            'general': ['middleware', 'interceptor', 'filter']
        }
        
        middleware_components = []
        
        for framework, patterns in middleware_patterns.items():
            for pattern in patterns:
                result = search_code(tool_context, directory=repository_path, query=pattern)
                if result.get('status') == 'ok':
                    for match in result['matches']:
                        middleware_components.append({
                            'framework': framework,
                            'pattern': pattern,
                            'file': match['file'],
                            'line': match['line'],
                            'snippet': match['snippet']
                        })
        
        # Parse Python files for middleware classes
        python_middleware = []
        for py_file in path.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if 'middleware' in node.name.lower() or 'Middleware' in node.name:
                            python_middleware.append({
                                'file': str(py_file.relative_to(path)),
                                'class': node.name,
                                'line': node.lineno
                            })
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'middleware_components': middleware_components[:15],
            'python_middleware_classes': python_middleware[:10],
            'middleware_types': [
                'authentication',
                'authorization',
                'logging',
                'cors',
                'compression',
                'session',
                'csrf_protection',
                'rate_limiting'
            ],
            'note': 'Detailed middleware inspection requires framework adapter integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_authentication(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Inspect authentication."""
    try:
        from .repository_tools import search_code
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for authentication patterns
        auth_patterns = {
            'decorators': ['@login_required', '@auth_required', '@authenticate', '@jwt_required'],
            'methods': ['authenticate', 'login', 'logout', 'signin', 'signout'],
            'tokens': ['jwt', 'token', 'bearer', 'oauth', 'session'],
            'libraries': ['flask_login', 'flask_jwt', 'passport', 'authlib', 'jwt'],
            'config': ['SECRET_KEY', 'JWT_SECRET', 'AUTH_CONFIG', 'authentication']
        }
        
        auth_findings = {}
        
        for auth_type, patterns in auth_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, directory=repository_path, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            auth_findings[auth_type] = matches[:5]
        
        # Parse Python files for auth-related classes
        auth_classes = []
        for py_file in path.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if any(keyword in node.name.lower() for keyword in ['auth', 'user', 'login', 'token']):
                            auth_classes.append({
                                'file': str(py_file.relative_to(path)),
                                'class': node.name,
                                'line': node.lineno
                            })
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'auth_findings': auth_findings,
            'auth_classes': auth_classes[:10],
            'auth_strategies_detected': [
                'session_based',
                'token_based',
                'oauth',
                'jwt',
                'basic_auth',
                'api_key'
            ],
            'note': 'Detailed authentication inspection requires framework adapter integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_authorization(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Inspect authorization."""
    try:
        from .repository_tools import search_code
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for authorization patterns
        authz_patterns = {
            'decorators': ['@permission_required', '@roles_required', '@authorize', '@has_permission'],
            'checks': ['check_permission', 'has_permission', 'is_authorized', 'can_access'],
            'roles': ['role', 'permission', 'privilege', 'access_level'],
            'models': ['Role', 'Permission', 'UserRole', 'AccessControl'],
            'libraries': ['flask_principal', 'casbin', 'acl', 'rbac']
        }
        
        authz_findings = {}
        
        for authz_type, patterns in authz_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, directory=repository_path, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            authz_findings[authz_type] = matches[:5]
        
        # Parse Python files for authorization classes
        authz_classes = []
        for py_file in path.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if any(keyword in node.name.lower() for keyword in ['role', 'permission', 'access', 'privilege']):
                            authz_classes.append({
                                'file': str(py_file.relative_to(path)),
                                'class': node.name,
                                'line': node.lineno
                            })
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'authz_findings': authz_findings,
            'authz_classes': authz_classes[:10],
            'authorization_models': [
                'rbac',  # Role-Based Access Control
                'abac',  # Attribute-Based Access Control
                'acl',   # Access Control List
                'cbac'   # Capability-Based Access Control
            ],
            'note': 'Detailed authorization inspection requires framework adapter integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Database Intelligence Tools

@safe
def discover_database_schema(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Discover database schema."""
    try:
        from .repository_tools import search_code
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for ORM model definitions
        orm_patterns = {
            'sqlalchemy': [r'class.*\(.*Base\)', r'class.*\(.*db.Model\)', 'Column(', 'Integer(', 'String('],
            'django': ['class.*models.Model', 'models.CharField', 'models.IntegerField', 'models.ForeignKey'],
            'peewee': ['class.*Model', 'CharField', 'IntegerField', 'ForeignKeyField'],
            'sqlalchemy_core': ['Table(', 'Column(', 'MetaData(']
        }
        
        schema_findings = {}
        
        for orm_type, patterns in orm_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, directory=repository_path, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            schema_findings[orm_type] = matches[:5]
        
        # Parse Python files for model classes
        model_classes = []
        for py_file in path.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if it's a model class
                        for base in node.bases:
                            base_name = base.id if isinstance(base, ast.Name) else str(base)
                            if 'Model' in base_name or 'Base' in base_name:
                                model_classes.append({
                                    'file': str(py_file.relative_to(path)),
                                    'class': node.name,
                                    'line': node.lineno,
                                    'base': base_name
                                })
                                break
            except Exception:
                pass
        
        # Look for migration files
        migration_files = []
        for migration_dir in ['migrations', 'alembic/versions', 'db/migrate']:
            mig_path = path / migration_dir
            if mig_path.exists():
                for mig_file in mig_path.rglob('*.py'):
                    migration_files.append(str(mig_file.relative_to(path)))
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'schema_findings': schema_findings,
            'model_classes': model_classes[:20],
            'migration_files': migration_files[:10],
            'orm_frameworks_detected': list(schema_findings.keys()),
            'note': 'Full schema discovery requires ORM adapter integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_database_connection(
    connection_string: str,
    tool_context: ToolContext
) -> dict:
    """Inspect database connection configuration."""
    try:
        from .repository_tools import search_code
        
        # Parse connection string to extract database type (without exposing full string)
        db_type = 'unknown'
        if 'postgresql' in connection_string.lower() or 'postgres' in connection_string.lower():
            db_type = 'postgresql'
        elif 'mysql' in connection_string.lower():
            db_type = 'mysql'
        elif 'sqlite' in connection_string.lower():
            db_type = 'sqlite'
        elif 'mongodb' in connection_string.lower():
            db_type = 'mongodb'
        elif 'oracle' in connection_string.lower():
            db_type = 'oracle'
        elif 'sqlserver' in connection_string.lower() or 'mssql' in connection_string.lower():
            db_type = 'sqlserver'
        
        # Search for database configuration in codebase
        config_patterns = ['DATABASE_URL', 'DB_CONNECTION', 'SQLALCHEMY_DATABASE_URI', 'MONGO_URI', 'connection_string']
        config_findings = []
        
        for pattern in config_patterns:
            result = search_code(tool_context, query=pattern)
            if result.get('status') == 'ok':
                config_findings.extend(result['matches'])
        
        # Search for connection pool configuration
        pool_patterns = ['pool_size', 'max_connections', 'connection_pool', 'POOL']
        pool_findings = []
        
        for pattern in pool_patterns:
            result = search_code(tool_context, query=pattern)
            if result.get('status') == 'ok':
                pool_findings.extend(result['matches'])
        
        return {
            'status': 'ok',
            'database_type': db_type,
            'connection_string': '***masked***',
            'config_findings': config_findings[:5],
            'pool_configuration': pool_findings[:5],
            'common_parameters': [
                'host',
                'port',
                'database',
                'username',
                'password',
                'pool_size',
                'max_overflow',
                'pool_timeout',
                'pool_recycle'
            ],
            'note': 'Detailed connection inspection requires database driver integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_database_queries(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze database queries."""
    try:
        from .repository_tools import search_code
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for SQL query patterns
        sql_patterns = {
            'select': ['SELECT', 'select()', 'Model.query', 'db.session.query'],
            'insert': ['INSERT', 'insert()', 'add(', 'create('],
            'update': ['UPDATE', 'update()', 'Model.update'],
            'delete': ['DELETE', 'delete()', 'remove(', 'drop('],
            'join': ['JOIN', 'join(', 'joinedload('],
            'aggregate': ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'GROUP BY', 'group_by']
        }
        
        query_findings = {}
        
        for query_type, patterns in sql_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, directory=repository_path, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            query_findings[query_type] = matches[:5]
        
        # Parse Python files for query functions
        query_functions = []
        for py_file in path.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Check if function contains query-related keywords
                        func_content = ast.unparse(node) if hasattr(ast, 'unparse') else ''
                        if any(keyword in func_content.lower() for keyword in ['query', 'select', 'filter', 'execute']):
                            query_functions.append({
                                'file': str(py_file.relative_to(path)),
                                'function': node.name,
                                'line': node.lineno
                            })
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'query_findings': query_findings,
            'query_functions': query_functions[:20],
            'query_types_detected': list(query_findings.keys()),
            'optimization_suggestions': [
                'Use indexes on frequently queried columns',
                'Avoid SELECT * when possible',
                'Use JOINs instead of subqueries when appropriate',
                'Consider pagination for large result sets',
                'Use query caching for frequently accessed data'
            ],
            'note': 'Detailed query analysis requires SQL parser integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_database_operation(
    query_id: str,
    tool_context: ToolContext
) -> dict:
    """Trace a database operation."""
    try:
        from .repository_tools import search_code
        
        # Search for the query pattern
        query_matches = []
        result = search_code(tool_context, query=query_id)
        if result.get('status') == 'ok':
            query_matches = result['matches']
        
        # Search for transaction-related code
        transaction_patterns = ['commit(', 'rollback(', 'begin(', 'transaction', 'db.session']
        transaction_matches = []
        
        for pattern in transaction_patterns:
            result = search_code(tool_context, query=pattern)
            if result.get('status') == 'ok':
                transaction_matches.extend(result['matches'])
        
        # Search for error handling
        error_patterns = ['except', 'Error', 'IntegrityError', 'OperationalError']
        error_matches = []
        
        for pattern in error_patterns:
            result = search_code(tool_context, query=pattern)
            if result.get('status') == 'ok':
                error_matches.extend(result['matches'])
        
        return {
            'status': 'ok',
            'query_id': query_id,
            'query_matches': query_matches[:5],
            'transaction_operations': transaction_matches[:5],
            'error_handling': error_matches[:5],
            'operation_lifecycle': [
                'query_construction',
                'query_execution',
                'result_processing',
                'transaction_commit_or_rollback',
                'connection_cleanup'
            ],
            'note': 'Detailed operation tracing requires runtime instrumentation'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_database_performance(
    connection_string: str,
    tool_context: ToolContext
) -> dict:
    """Analyze database performance."""
    try:
        from .repository_tools import search_code
        
        # Parse connection string to extract database type
        db_type = 'unknown'
        if 'postgresql' in connection_string.lower() or 'postgres' in connection_string.lower():
            db_type = 'postgresql'
        elif 'mysql' in connection_string.lower():
            db_type = 'mysql'
        elif 'sqlite' in connection_string.lower():
            db_type = 'sqlite'
        elif 'mongodb' in connection_string.lower():
            db_type = 'mongodb'
        
        # Search for performance-related patterns
        performance_patterns = {
            'slow_queries': ['slow', 'timeout', 'performance', 'optimize'],
            'indexes': ['Index(', 'index=True', 'create_index', 'add_index'],
            'n_plus_one': ['for.*in.*query', 'lazy loading', 'select_related', 'prefetch'],
            'caching': ['cache', 'Cache', 'redis', 'memcached'],
            'connection_pool': ['pool_size', 'max_connections', 'connection_pool']
        }
        
        performance_findings = {}
        
        for perf_type, patterns in performance_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            performance_findings[perf_type] = matches[:5]
        
        return {
            'status': 'ok',
            'database_type': db_type,
            'connection_string': '***masked***',
            'performance_findings': performance_findings,
            'metrics_to_monitor': [
                'query_execution_time',
                'slow_query_log',
                'connection_pool_usage',
                'cache_hit_ratio',
                'index_usage',
                'table_size',
                'lock_wait_time'
            ],
            'optimization_techniques': [
                'Add appropriate indexes',
                'Use query caching',
                'Optimize connection pool size',
                'Use pagination',
                'Avoid N+1 queries',
                'Use database-specific optimizations'
            ],
            'note': 'Detailed performance analysis requires database integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_database_schema(
    connection_string: str,
    tool_context: ToolContext
) -> dict:
    """Inspect database schema."""
    try:
        from .repository_tools import search_code
        
        # Parse connection string to extract database type
        db_type = 'unknown'
        if 'postgresql' in connection_string.lower() or 'postgres' in connection_string.lower():
            db_type = 'postgresql'
        elif 'mysql' in connection_string.lower():
            db_type = 'mysql'
        elif 'sqlite' in connection_string.lower():
            db_type = 'sqlite'
        elif 'mongodb' in connection_string.lower():
            db_type = 'mongodb'
        
        # Search for schema definitions
        schema_patterns = {
            'tables': ['class.*Model', 'Table(', 'CREATE TABLE'],
            'columns': ['Column(', 'CharField', 'IntegerField', 'String'],
            'relationships': ['ForeignKey', 'relationship', 'ForeignKeyField'],
            'constraints': ['UniqueConstraint', 'CheckConstraint', 'Index(']
        }
        
        schema_findings = {}
        
        for schema_type, patterns in schema_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            schema_findings[schema_type] = matches[:5]
        
        return {
            'status': 'ok',
            'database_type': db_type,
            'connection_string': '***masked***',
            'schema_findings': schema_findings,
            'schema_components': [
                'tables',
                'columns',
                'primary_keys',
                'foreign_keys',
                'indexes',
                'constraints',
                'views',
                'stored_procedures',
                'triggers'
            ],
            'note': 'Detailed schema inspection requires database driver integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_tables(
    connection_string: str,
    tool_context: ToolContext
) -> dict:
    """Inspect database tables."""
    try:
        from .repository_tools import search_code
        
        # Parse connection string to extract database type
        db_type = 'unknown'
        if 'postgresql' in connection_string.lower() or 'postgres' in connection_string.lower():
            db_type = 'postgresql'
        elif 'mysql' in connection_string.lower():
            db_type = 'mysql'
        elif 'sqlite' in connection_string.lower():
            db_type = 'sqlite'
        elif 'mongodb' in connection_string.lower():
            db_type = 'mongodb'
        
        # Search for table definitions
        table_patterns = {
            'sqlalchemy': [r'class.*\(.*Model\)', r'class.*\(.*Base\)'],
            'django': ['class.*models.Model'],
            'peewee': ['class.*Model'],
            'raw_sql': ['CREATE TABLE', 'create table']
        }
        
        table_findings = {}
        
        for framework, patterns in table_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            table_findings[framework] = matches[:5]
        
        # Parse Python files for table classes
        table_classes = []
        cwd = Path.cwd()
        for py_file in cwd.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if it's a table/model class
                        for base in node.bases:
                            base_name = base.id if isinstance(base, ast.Name) else str(base)
                            if 'Model' in base_name or 'Base' in base_name:
                                table_classes.append({
                                    'file': str(py_file.relative_to(cwd)),
                                    'table': node.name,
                                    'line': node.lineno
                                })
                                break
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'database_type': db_type,
            'connection_string': '***masked***',
            'table_findings': table_findings,
            'table_classes': table_classes[:20],
            'table_information': [
                'table_name',
                'columns',
                'primary_key',
                'foreign_keys',
                'indexes',
                'row_count',
                'table_size'
            ],
            'note': 'Detailed table inspection requires database driver integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_columns(
    connection_string: str,
    table: str,
    tool_context: ToolContext
) -> dict:
    """Inspect table columns."""
    try:
        from .repository_tools import search_code
        
        # Parse connection string to extract database type
        db_type = 'unknown'
        if 'postgresql' in connection_string.lower() or 'postgres' in connection_string.lower():
            db_type = 'postgresql'
        elif 'mysql' in connection_string.lower():
            db_type = 'mysql'
        elif 'sqlite' in connection_string.lower():
            db_type = 'sqlite'
        elif 'mongodb' in connection_string.lower():
            db_type = 'mongodb'
        
        # Search for the table definition
        table_matches = []
        result = search_code(tool_context, query=table)
        if result.get('status') == 'ok':
            table_matches = result['matches']
        
        # Search for column definitions
        column_patterns = {
            'integer': ['Integer', 'IntegerField', 'int', 'INT'],
            'string': ['String', 'CharField', 'VARCHAR', 'TEXT'],
            'boolean': ['Boolean', 'BooleanField', 'bool', 'BOOLEAN'],
            'datetime': ['DateTime', 'DateField', 'timestamp', 'TIMESTAMP'],
            'float': ['Float', 'FloatField', 'decimal', 'DECIMAL'],
            'foreign_key': ['ForeignKey', 'ForeignKeyField', 'REFERENCES']
        }
        
        column_findings = {}
        
        for col_type, patterns in column_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            column_findings[col_type] = matches[:3]
        
        # Parse Python files for the specific table
        table_columns = []
        cwd = Path.cwd()
        for py_file in cwd.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == table:
                        # Extract column definitions from class body
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if isinstance(target, ast.Name):
                                        table_columns.append({
                                            'name': target.id,
                                            'line': item.lineno
                                        })
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'database_type': db_type,
            'connection_string': '***masked***',
            'table': table,
            'table_matches': table_matches[:5],
            'column_findings': column_findings,
            'table_columns': table_columns[:20],
            'column_properties': [
                'name',
                'data_type',
                'nullable',
                'default_value',
                'primary_key',
                'unique',
                'index',
                'foreign_key'
            ],
            'note': 'Detailed column inspection requires database driver integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_indexes(
    connection_string: str,
    table: str,
    tool_context: ToolContext
) -> dict:
    """Inspect table indexes."""
    try:
        from .repository_tools import search_code
        
        # Parse connection string to extract database type
        db_type = 'unknown'
        if 'postgresql' in connection_string.lower() or 'postgres' in connection_string.lower():
            db_type = 'postgresql'
        elif 'mysql' in connection_string.lower():
            db_type = 'mysql'
        elif 'sqlite' in connection_string.lower():
            db_type = 'sqlite'
        elif 'mongodb' in connection_string.lower():
            db_type = 'mongodb'
        
        # Search for index definitions
        index_patterns = {
            'sqlalchemy': ['Index(', 'index=True', 'create_index'],
            'django': ['Index', 'db_index=True'],
            'raw_sql': ['CREATE INDEX', 'create index', 'ADD INDEX']
        }
        
        index_findings = {}
        
        for framework, patterns in index_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            index_findings[framework] = matches[:5]
        
        # Search for indexes on the specific table
        table_index_matches = []
        result = search_code(tool_context, query=table)
        if result.get('status') == 'ok':
            table_index_matches = [m for m in result['matches'] if 'index' in m['snippet'].lower()]
        
        return {
            'status': 'ok',
            'database_type': db_type,
            'connection_string': '***masked***',
            'table': table,
            'index_findings': index_findings,
            'table_index_matches': table_index_matches[:5],
            'index_types': [
                'btree',  # Default for most databases
                'hash',   # For equality comparisons
                'gin',    # PostgreSQL for array/json
                'gist',   # PostgreSQL for geometric data
                'unique', # Enforces uniqueness
                'composite' # Multi-column
            ],
            'index_optimization_tips': [
                'Index columns used in WHERE clauses',
                'Index columns used in JOIN conditions',
                'Index columns used in ORDER BY',
                'Avoid over-indexing (impacts write performance)',
                'Consider composite indexes for multi-column queries'
            ],
            'note': 'Detailed index inspection requires database driver integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_foreign_keys(
    connection_string: str,
    table: str,
    tool_context: ToolContext
) -> dict:
    """Inspect foreign keys."""
    try:
        from .repository_tools import search_code
        
        # Parse connection string to extract database type
        db_type = 'unknown'
        if 'postgresql' in connection_string.lower() or 'postgres' in connection_string.lower():
            db_type = 'postgresql'
        elif 'mysql' in connection_string.lower():
            db_type = 'mysql'
        elif 'sqlite' in connection_string.lower():
            db_type = 'sqlite'
        elif 'mongodb' in connection_string.lower():
            db_type = 'mongodb'
        
        # Search for foreign key definitions
        fk_patterns = {
            'sqlalchemy': ['ForeignKey(', 'relationship('],
            'django': ['ForeignKey', 'models.ForeignKey'],
            'peewee': ['ForeignKeyField'],
            'raw_sql': ['FOREIGN KEY', 'REFERENCES']
        }
        
        fk_findings = {}
        
        for framework, patterns in fk_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            fk_findings[framework] = matches[:5]
        
        # Search for foreign keys on the specific table
        table_fk_matches = []
        result = search_code(tool_context, query=table)
        if result.get('status') == 'ok':
            table_fk_matches = [m for m in result['matches'] if 'foreign' in m['snippet'].lower() or 'fk' in m['snippet'].lower()]
        
        return {
            'status': 'ok',
            'database_type': db_type,
            'connection_string': '***masked***',
            'table': table,
            'fk_findings': fk_findings,
            'table_fk_matches': table_fk_matches[:5],
            'foreign_key_properties': [
                'column_name',
                'referenced_table',
                'referenced_column',
                'on_delete_behavior',  # CASCADE, SET NULL, RESTRICT, etc.
                'on_update_behavior',
                'constraint_name'
            ],
            'on_delete_options': [
                'CASCADE',  # Delete child records when parent is deleted
                'SET_NULL', # Set foreign key to NULL
                'SET_DEFAULT', # Set to default value
                'RESTRICT', # Prevent deletion if child records exist
                'NO_ACTION', # Similar to RESTRICT
                'PROTECT'   # Django equivalent of RESTRICT
            ],
            'note': 'Detailed foreign key inspection requires database driver integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_sql_queries(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Inspect SQL queries."""
    try:
        from .repository_tools import search_code
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for SQL query patterns
        sql_patterns = {
            'raw_sql': ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP'],
            'orm_queries': ['Model.query', 'filter(', 'all(', 'first(', 'get('],
            'exec_sql': ['execute(', 'executemany(', 'cursor.execute'],
            'joins': ['join(', 'outerjoin(', 'select_from(']
        }
        
        query_findings = {}
        
        for query_type, patterns in sql_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, directory=repository_path, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            query_findings[query_type] = matches[:5]
        
        # Parse Python files for SQL strings
        sql_strings = []
        for py_file in path.rglob('*.py'):
            try:
                content = py_file.read_text(encoding='utf-8')
                # Find multi-line SQL strings
                sql_pattern = r'("""[\s\S]*?SELECT[\s\S]*?"""|\'\'\'[\s\S]*?SELECT[\s\S]*?\'\'\')'
                matches = re.findall(sql_pattern, content, re.IGNORECASE)
                for match in matches:
                    sql_strings.append({
                        'file': str(py_file.relative_to(path)),
                        'sql': match[:100] + '...' if len(match) > 100 else match
                    })
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'query_findings': query_findings,
            'sql_strings': sql_strings[:10],
            'query_categories': [
                'DQL',  # Data Query Language (SELECT)
                'DML',  # Data Manipulation Language (INSERT, UPDATE, DELETE)
                'DDL',  # Data Definition Language (CREATE, ALTER, DROP)
                'DCL',  # Data Control Language (GRANT, REVOKE)
                'TCL'   # Transaction Control Language (COMMIT, ROLLBACK)
            ],
            'note': 'Detailed SQL query inspection requires SQL parser integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def explain_query_plan(
    query: str,
    connection_string: str,
    tool_context: ToolContext
) -> dict:
    """Explain query execution plan."""
    try:
        from .repository_tools import search_code
        
        # Parse connection string to extract database type
        db_type = 'unknown'
        if 'postgresql' in connection_string.lower() or 'postgres' in connection_string.lower():
            db_type = 'postgresql'
        elif 'mysql' in connection_string.lower():
            db_type = 'mysql'
        elif 'sqlite' in connection_string.lower():
            db_type = 'sqlite'
        elif 'mongodb' in connection_string.lower():
            db_type = 'mongodb'
        
        # Parse the query to extract key components
        query_upper = query.upper()
        query_type = 'unknown'
        if 'SELECT' in query_upper:
            query_type = 'SELECT'
        elif 'INSERT' in query_upper:
            query_type = 'INSERT'
        elif 'UPDATE' in query_upper:
            query_type = 'UPDATE'
        elif 'DELETE' in query_upper:
            query_type = 'DELETE'
        
        # Extract tables mentioned in query
        table_pattern = r'(?:FROM|JOIN|INTO|UPDATE)\s+(\w+)'
        tables = re.findall(table_pattern, query_upper)
        
        # Extract WHERE clauses
        where_clauses = []
        if 'WHERE' in query_upper:
            where_match = re.search(r'WHERE\s+(.*?)(?:GROUP BY|ORDER BY|LIMIT|;$)', query_upper, re.IGNORECASE)
            if where_match:
                where_clauses.append(where_match.group(1)[:100])
        
        # Search for similar queries in codebase
        similar_queries = []
        for table in tables[:3]:  # Limit to first 3 tables
            result = search_code(tool_context, query=table)
            if result.get('status') == 'ok':
                similar_queries.extend(result['matches'][:3])
        
        return {
            'status': 'ok',
            'database_type': db_type,
            'connection_string': '***masked***',
            'query_type': query_type,
            'tables_mentioned': list(set(tables)),
            'where_clauses': where_clauses,
            'similar_queries': similar_queries[:5],
            'execution_plan_components': [
                'scan_type',  # Sequential scan, index scan, etc.
                'filter_conditions',
                'join_strategy',  # Nested loop, hash join, merge join
                'sort_operation',
                'aggregation',
                'estimated_cost',
                'actual_time'
            ],
            'optimization_suggestions': [
                'Use appropriate indexes',
                'Avoid SELECT *',
                'Use LIMIT for large result sets',
                'Optimize JOIN order',
                'Use EXISTS instead of IN for subqueries'
            ],
            'note': 'Detailed query plan explanation requires database driver integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_orm_models(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Inspect ORM models."""
    try:
        from .repository_tools import search_code
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for ORM model patterns
        orm_patterns = {
            'sqlalchemy': [r'class.*\(.*Base\)', r'class.*\(.*db.Model\)', 'Column(', 'Integer(', 'String('],
            'django': ['class.*models.Model', 'models.CharField', 'models.IntegerField', 'models.ForeignKey'],
            'peewee': ['class.*Model', 'CharField', 'IntegerField', 'ForeignKeyField'],
            'sqlalchemy_core': ['Table(', 'Column(', 'MetaData(']
        }
        
        orm_findings = {}
        
        for orm_type, patterns in orm_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, directory=repository_path, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            orm_findings[orm_type] = matches[:5]
        
        # Parse Python files for model classes with detailed information
        model_details = []
        for py_file in path.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if it's a model class
                        for base in node.bases:
                            base_name = base.id if isinstance(base, ast.Name) else str(base)
                            if 'Model' in base_name or 'Base' in base_name:
                                # Extract class attributes (columns)
                                attributes = []
                                for item in node.body:
                                    if isinstance(item, ast.Assign):
                                        for target in item.targets:
                                            if isinstance(target, ast.Name):
                                                attributes.append(target.id)
                                
                                model_details.append({
                                    'file': str(py_file.relative_to(path)),
                                    'class': node.name,
                                    'base': base_name,
                                    'line': node.lineno,
                                    'attributes': attributes[:10]
                                })
                                break
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'orm_findings': orm_findings,
            'model_details': model_details[:20],
            'orm_frameworks_detected': list(orm_findings.keys()),
            'model_components': [
                'class_definition',
                'table_name',
                'columns',
                'primary_key',
                'relationships',
                'indexes',
                'constraints',
                'methods'
            ],
            'note': 'Detailed ORM model inspection requires framework adapter integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_orm_relationships(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Inspect ORM relationships."""
    try:
        from .repository_tools import search_code
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for relationship patterns
        relationship_patterns = {
            'sqlalchemy': ['relationship(', 'back_populates', 'backref', 'ForeignKey('],
            'django': ['ForeignKey', 'ManyToManyField', 'OneToOneField', 'related_name'],
            'peewee': ['ForeignKeyField', 'ManyToManyField'],
            'general': ['foreign_key', 'relationship', 'belongs_to', 'has_many', 'has_one']
        }
        
        relationship_findings = {}
        
        for rel_type, patterns in relationship_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, directory=repository_path, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            relationship_findings[rel_type] = matches[:5]
        
        # Parse Python files for relationship definitions
        relationship_details = []
        for py_file in path.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if it's a model class
                        for base in node.bases:
                            base_name = base.id if isinstance(base, ast.Name) else str(base)
                            if 'Model' in base_name or 'Base' in base_name:
                                # Extract relationship attributes
                                for item in node.body:
                                    if isinstance(item, ast.Assign):
                                        for target in item.targets:
                                            if isinstance(target, ast.Name):
                                                attr_name = target.id.lower()
                                                if any(keyword in attr_name for keyword in ['relationship', 'foreign', 'related', 'parent', 'child']):
                                                    relationship_details.append({
                                                        'file': str(py_file.relative_to(path)),
                                                        'class': node.name,
                                                        'relationship': target.id,
                                                        'line': item.lineno
                                                    })
                                break
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'relationship_findings': relationship_findings,
            'relationship_details': relationship_details[:20],
            'relationship_types': [
                'one_to_one',      # 1:1
                'one_to_many',     # 1:N
                'many_to_one',     # N:1
                'many_to_many',    # N:N
                'self_referential' # Recursive
            ],
            'relationship_properties': [
                'foreign_key',
                'back_reference',
                'cascade_options',
                'lazy_loading',
                'eager_loading'
            ],
            'note': 'Detailed relationship inspection requires framework adapter integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_transaction(
    transaction_id: str,
    tool_context: ToolContext
) -> dict:
    """Trace database transaction."""
    try:
        from .repository_tools import search_code
        
        # Search for transaction-related patterns
        transaction_patterns = {
            'begin': ['begin(', 'start_transaction', 'BEGIN', 'start transaction'],
            'commit': ['commit(', 'COMMIT', 'db.session.commit'],
            'rollback': ['rollback(', 'ROLLBACK', 'db.session.rollback'],
            'savepoint': ['savepoint', 'SAVEPOINT', 'begin_nested'],
            'isolation': ['isolation_level', 'SERIALIZABLE', 'REPEATABLE_READ', 'READ_COMMITTED']
        }
        
        transaction_findings = {}
        
        for tx_type, patterns in transaction_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            transaction_findings[tx_type] = matches[:5]
        
        # Search for the specific transaction ID if it's a reference in code
        tx_matches = []
        result = search_code(tool_context, query=transaction_id)
        if result.get('status') == 'ok':
            tx_matches = result['matches']
        
        return {
            'status': 'ok',
            'transaction_id': transaction_id,
            'transaction_findings': transaction_findings,
            'transaction_matches': tx_matches[:5],
            'transaction_lifecycle': [
                'transaction_begin',
                'execute_queries',
                'check_constraints',
                'validate_data',
                'commit_or_rollback',
                'release_locks'
            ],
            'isolation_levels': [
                'READ_UNCOMMITTED',
                'READ_COMMITTED',
                'REPEATABLE_READ',
                'SERIALIZABLE'
            ],
            'acid_properties': [
                'Atomicity',    # All or nothing
                'Consistency',  # Valid state
                'Isolation',    # Concurrent transactions
                'Durability'    # Persisted commits
            ],
            'note': 'Detailed transaction tracing requires runtime instrumentation'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_migrations(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Trace database migrations."""
    try:
        from .repository_tools import search_code
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for migration patterns
        migration_patterns = {
            'alembic': ['alembic', 'upgrade(', 'downgrade(', 'revision('],
            'django': ['migrations', 'CreateModel', 'RemoveField', 'AddField', 'RunPython'],
            'flask_migrate': ['migrate', 'upgrade', 'downgrade'],
            'south': ['South', 'migrate'],
            'flyway': ['flyway', 'V__', 'R__']
        }
        
        migration_findings = {}
        
        for mig_type, patterns in migration_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, directory=repository_path, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            migration_findings[mig_type] = matches[:5]
        
        # Look for migration directories
        migration_dirs = []
        for mig_dir in ['migrations', 'alembic', 'alembic/versions', 'db/migrate', 'db/migrations']:
            mig_path = path / mig_dir
            if mig_path.exists():
                migration_files = list(mig_path.rglob('*.py'))
                migration_dirs.append({
                    'directory': mig_dir,
                    'file_count': len(migration_files),
                    'files': [str(f.relative_to(path)) for f in migration_files[:10]]
                })
        
        # Parse migration files for operations
        migration_operations = []
        for mig_dir in migration_dirs:
            dir_path = path / mig_dir['directory']
            if dir_path.exists():
                for mig_file in dir_path.rglob('*.py'):
                    try:
                        content = mig_file.read_text(encoding='utf-8')
                        # Look for common migration operations
                        if 'upgrade' in content.lower() or 'downgrade' in content.lower():
                            migration_operations.append({
                                'file': str(mig_file.relative_to(path)),
                                'operations': content[:200] + '...' if len(content) > 200 else content
                            })
                    except Exception:
                        pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'migration_findings': migration_findings,
            'migration_directories': migration_dirs,
            'migration_operations': migration_operations[:10],
            'migration_frameworks_detected': list(migration_findings.keys()),
            'migration_operations_types': [
                'create_table',
                'drop_table',
                'add_column',
                'remove_column',
                'alter_column',
                'add_index',
                'remove_index',
                'add_foreign_key',
                'run_python',
                'run_sql'
            ],
            'note': 'Detailed migration tracing requires migration tool integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def map_api_to_database(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Map API endpoints to database operations."""
    try:
        from .repository_tools import search_code
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for API endpoints
        endpoint_patterns = ['@app.route', '@api.route', '@bp.route', 'router.get', 'router.post', 'app.get', 'app.post']
        endpoint_matches = []

        for pattern in endpoint_patterns:
            result = search_code(tool_context, directory=repository_path, query=pattern)
            if result.get('status') == 'ok':
                endpoint_matches.extend(result['matches'])
        
        # Search for database operations
        db_patterns = ['db.session', 'Model.query', 'SELECT', 'INSERT', 'UPDATE', 'DELETE']
        db_matches = []
        
        for pattern in db_patterns:
            result = search_code(tool_context, query=pattern)
            if result.get('status') == 'ok':
                db_matches.extend(result['matches'])
        
        # Parse Python files to find relationships between endpoints and models
        mappings = []
        for py_file in path.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                file_endpoints = []
                file_models = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Check for route decorators
                        for decorator in node.decorator_list:
                            if isinstance(decorator, ast.Call):
                                if hasattr(decorator.func, 'id') and 'route' in decorator.func.id.lower():
                                    file_endpoints.append({
                                        'function': node.name,
                                        'line': node.lineno
                                    })
                    elif isinstance(node, ast.ClassDef):
                        # Check for model classes
                        for base in node.bases:
                            base_name = base.id if isinstance(base, ast.Name) else str(base)
                            if 'Model' in base_name or 'Base' in base_name:
                                file_models.append({
                                    'class': node.name,
                                    'line': node.lineno
                                })
                
                if file_endpoints and file_models:
                    mappings.append({
                        'file': str(py_file.relative_to(path)),
                        'endpoints': file_endpoints,
                        'models': file_models
                    })
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'endpoint_matches': endpoint_matches[:10],
            'database_operations': db_matches[:10],
            'endpoint_model_mappings': mappings[:15],
            'common_mapping_patterns': [
                'GET /users -> User.query.all()',
                'GET /users/{id} -> User.query.get(id)',
                'POST /users -> User.create(data)',
                'PUT /users/{id} -> User.update(id, data)',
                'DELETE /users/{id} -> User.delete(id)'
            ],
            'note': 'Detailed API-to-database mapping requires runtime tracing'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_database_schema(
    connection_string: str,
    tool_context: ToolContext
) -> dict:
    """Visualize database schema."""
    try:
        from .repository_tools import search_code
        
        # Parse connection string to extract database type
        db_type = 'unknown'
        if 'postgresql' in connection_string.lower() or 'postgres' in connection_string.lower():
            db_type = 'postgresql'
        elif 'mysql' in connection_string.lower():
            db_type = 'mysql'
        elif 'sqlite' in connection_string.lower():
            db_type = 'sqlite'
        elif 'mongodb' in connection_string.lower():
            db_type = 'mongodb'
        
        # Search for schema components
        schema_patterns = {
            'tables': ['class.*Model', 'Table(', 'CREATE TABLE'],
            'relationships': ['ForeignKey', 'relationship', 'ForeignKeyField'],
            'indexes': ['Index(', 'index=True', 'create_index']
        }
        
        schema_findings = {}
        
        for schema_type, patterns in schema_patterns.items():
            matches = []
            for pattern in patterns:
                result = search_code(tool_context, query=pattern)
                if result.get('status') == 'ok':
                    matches.extend(result['matches'])
            schema_findings[schema_type] = matches[:5]
        
        # Parse Python files to build a schema representation
        schema_representation = []
        cwd = Path.cwd()
        for py_file in cwd.rglob('*.py'):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if it's a model class
                        for base in node.bases:
                            base_name = base.id if isinstance(base, ast.Name) else str(base)
                            if 'Model' in base_name or 'Base' in base_name:
                                # Extract columns
                                columns = []
                                for item in node.body:
                                    if isinstance(item, ast.Assign):
                                        for target in item.targets:
                                            if isinstance(target, ast.Name):
                                                columns.append(target.id)
                                
                                schema_representation.append({
                                    'table': node.name,
                                    'columns': columns[:10],
                                    'file': str(py_file.relative_to(cwd))
                                })
                                break
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'database_type': db_type,
            'connection_string': '***masked***',
            'schema_findings': schema_findings,
            'schema_representation': schema_representation[:20],
            'visualization_formats': [
                'mermaid',  # Markdown-based diagrams
                'plantuml', # PlantUML diagrams
                'graphviz', # DOT/Graphviz
                'erd',      # Entity Relationship Diagram
                'json'      # JSON representation
            ],
            'schema_diagram_example': {
                'type': 'mermaid',
                'content': 'erDiagram\n    TABLE1 ||--o{ TABLE2 : "relationship"\n    TABLE1 {\n        id PK\n        name string\n    }'
            },
            'note': 'Detailed schema visualization requires database driver integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
