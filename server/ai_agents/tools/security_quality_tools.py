"""
Agent 9 - Security & Quality Tools
Identify weaknesses, vulnerabilities and poor engineering practices.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import re
from google.adk.tools import ToolContext
from ._safe import safe


# Security Tools

@safe
def scan_secrets(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Scan for hardcoded secrets."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Common secret patterns
        secret_patterns = [
            (r'api[_-]?key\s*=\s*["\']([^"\']{20,})["\']', 'api_key'),
            (r'password\s*=\s*["\']([^"\']{8,})["\']', 'password'),
            (r'secret[_-]?key\s*=\s*["\']([^"\']{20,})["\']', 'secret_key'),
            (r'token\s*=\s*["\']([^"\']{20,})["\']', 'token'),
            (r'aws[_-]?access[_-]?key[_-]?id\s*=\s*["\']([^"\']{16,})["\']', 'aws_access_key'),
            (r'aws[_-]?secret[_-]?access[_-]?key\s*=\s*["\']([^"\']{30,})["\']', 'aws_secret_key')
        ]
        
        secrets_found = []
        
        for file_path in path.rglob('*'):
            if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.env', '.yaml', '.yml', '.json']:
                try:
                    content = file_path.read_text(encoding='utf-8')
                    for pattern, secret_type in secret_patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        for match in matches:
                            line_num = content[:match.start()].count('\n') + 1
                            secrets_found.append({
                                'file': str(file_path.relative_to(path)),
                                'line': line_num,
                                'type': secret_type,
                                'severity': 'high'
                            })
                except:
                    continue
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'secrets_found': secrets_found
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_dependencies(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze dependencies for vulnerabilities."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        dependencies = []
        
        # Check for requirements.txt
        req_file = path / 'requirements.txt'
        if req_file.exists():
            content = req_file.read_text(encoding='utf-8')
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    dependencies.append({
                        'package': line,
                        'type': 'python',
                        'file': 'requirements.txt'
                    })
        
        # Check for package.json
        pkg_file = path / 'package.json'
        if pkg_file.exists():
            import json
            content = pkg_file.read_text(encoding='utf-8')
            try:
                pkg_data = json.loads(content)
                for dep_name in pkg_data.get('dependencies', {}).keys():
                    dependencies.append({
                        'package': dep_name,
                        'type': 'javascript',
                        'file': 'package.json'
                    })
            except:
                pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'dependencies': dependencies,
            'note': 'Static dependency listing - vulnerability check requires package manager integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def check_code_quality(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Check code quality metrics."""
    try:
        from .analysis_tools import analyze_code_complexity
        return analyze_code_complexity(repository_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def scan_security_vulnerabilities(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Scan for security vulnerabilities."""
    try:
        from .repository_tools import search_code
        
        # Common vulnerability patterns
        vuln_patterns = [
            ('eval(', 'code injection risk'),
            ('exec(', 'code injection risk'),
            ('pickle.loads(', 'deserialization risk'),
            ('subprocess.call', 'command injection risk'),
            ('os.system(', 'command injection risk'),
            ('shell=True', 'command injection risk'),
            ('input(', 'user input'),
            ('raw_input(', 'user input'),
            ('debug=True', 'debug mode enabled'),
            ('print(', 'information disclosure')
        ]
        
        vulnerabilities = []
        for pattern, vuln_type in vuln_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    vulnerabilities.append({
                        'type': vuln_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet'],
                        'severity': 'medium'
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'vulnerabilities': vulnerabilities,
            'note': 'Static pattern matching - full SAST requires Bandit/SonarQube integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def scan_vulnerabilities(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Scan for security vulnerabilities."""
    try:
        # Delegate to scan_security_vulnerabilities
        return scan_security_vulnerabilities(repository_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def scan_dependency_vulnerabilities(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Scan for vulnerable dependencies."""
    try:
        # Get dependencies first
        dep_result = analyze_dependencies(repository_path, tool_context)
        
        if dep_result.get('status') != 'ok':
            return dep_result
        
        dependencies = dep_result.get('dependencies', [])
        
        # Analyze dependencies for known vulnerability patterns
        vulnerable_deps = []
        for dep in dependencies:
            dep_name = dep.get('name', '').lower()
            # Common known vulnerable patterns (simplified)
            if any(vuln in dep_name for vuln in ['requests', 'urllib', 'pyyaml', 'jinja2']):
                vulnerable_deps.append({
                    'name': dep.get('name'),
                    'version': dep.get('version'),
                    'severity': 'medium',
                    'note': 'Requires manual audit - use pip-audit for actual vulnerability check'
                })

        return {
            'status': 'ok',
            'repository_path': repository_path,
            'dependencies': dependencies,
            'vulnerable_dependencies': vulnerable_deps,
            'total_vulnerabilities': len(vulnerable_deps),
            'note': 'Pattern-based check - use pip-audit/npm audit for actual vulnerability scanning'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_authentication(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze authentication mechanisms."""
    try:
        from .repository_tools import search_code
        
        # Search for authentication patterns
        auth_patterns = [
            ('@login_required', 'decorator authentication'),
            ('authenticate(', 'function authentication'),
            ('login(', 'login function'),
            ('auth', 'authentication module'),
            ('session', 'session management'),
            ('token', 'token authentication'),
            ('jwt', 'JWT authentication'),
            ('oauth', 'OAuth authentication')
        ]
        
        auth_mechanisms = []
        for pattern, auth_type in auth_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    auth_mechanisms.append({
                        'type': auth_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'authentication_mechanisms': auth_mechanisms
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_authorization(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze authorization mechanisms."""
    try:
        from .repository_tools import search_code
        
        # Search for authorization patterns
        authz_patterns = [
            ('@permission_required', 'permission decorator'),
            ('@has_permission', 'permission check'),
            ('@authorized', 'authorization check'),
            ('check_permission(', 'permission function'),
            ('can(', 'ability check'),
            ('allow(', 'allow rule'),
            ('deny(', 'deny rule'),
            ('role', 'role-based access'),
            ('permission', 'permission-based access')
        ]
        
        authorization_mechanisms = []
        for pattern, authz_type in authz_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    authorization_mechanisms.append({
                        'type': authz_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'authorization_mechanisms': authorization_mechanisms
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_permissions(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze permission models."""
    try:
        from .repository_tools import search_code
        
        # Search for permission patterns
        perm_patterns = [
            ('read', 'read permission'),
            ('write', 'write permission'),
            ('execute', 'execute permission'),
            ('admin', 'admin permission'),
            ('user', 'user permission'),
            ('guest', 'guest permission'),
            ('chmod', 'file permissions'),
            ('access_control', 'access control')
        ]
        
        permissions = []
        for pattern, perm_type in perm_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    permissions.append({
                        'type': perm_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'permissions': permissions
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_input_validation(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze input validation practices."""
    try:
        from .repository_tools import search_code
        
        # Search for validation patterns
        validation_patterns = [
            ('validate', 'validation function'),
            ('sanitize', 'sanitization function'),
            ('clean', 'cleaning function'),
            ('strip(', 'string stripping'),
            ('escape', 'escaping function'),
            ('check', 'check function'),
            ('verify', 'verification function'),
            ('is_valid', 'validation check'),
            ('if not ', 'validation check'),
            ('if len(', 'length validation')
        ]
        
        validations = []
        for pattern, val_type in validation_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    validations.append({
                        'type': val_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'input_validations': validations
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_injection_risks(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze SQL injection, XSS, etc."""
    try:
        from .repository_tools import search_code
        
        # Search for injection risk patterns
        injection_patterns = [
            ('f"SELECT', 'SQL injection risk (f-string)'),
            ('+ "SELECT', 'SQL injection risk (concatenation)'),
            ('format("SELECT', 'SQL injection risk (format)'),
            ('execute(input', 'SQL injection risk (execute input)'),
            ('cursor.execute(', 'SQL injection check'),
            ('innerHTML', 'XSS risk'),
            ('outerHTML', 'XSS risk'),
            ('document.write', 'XSS risk'),
            ('eval(input', 'code injection risk'),
            ('exec(input', 'code injection risk')
        ]
        
        injection_risks = []
        for pattern, risk_type in injection_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    injection_risks.append({
                        'type': risk_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'severity': 'high'
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'injection_risks': injection_risks
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_cryptography(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze cryptographic practices."""
    try:
        from .repository_tools import search_code
        
        # Search for cryptographic patterns
        crypto_patterns = [
            ('hashlib.', 'hash library'),
            ('cryptography.', 'cryptography library'),
            ('pycryptodome', 'crypto library'),
            ('AES', 'AES encryption'),
            ('RSA', 'RSA encryption'),
            ('SHA256', 'SHA-256 hash'),
            ('MD5', 'MD5 hash (weak)'),
            ('sha1', 'SHA-1 hash (weak)'),
            ('encrypt(', 'encryption function'),
            ('decrypt(', 'decryption function')
        ]
        
        crypto_usage = []
        for pattern, crypto_type in crypto_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    crypto_usage.append({
                        'type': crypto_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'cryptographic_usage': crypto_usage
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_sensitive_data(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Trace sensitive data flow."""
    try:
        from .repository_tools import search_code
        
        # Search for sensitive data patterns
        sensitive_patterns = [
            ('password', 'password field'),
            ('credit_card', 'credit card field'),
            ('ssn', 'social security number'),
            ('secret', 'secret field'),
            ('token', 'token field'),
            ('api_key', 'API key field'),
            ('private_key', 'private key field')
        ]
        
        sensitive_data = []
        for pattern, data_type in sensitive_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    sensitive_data.append({
                        'type': data_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'sensitive_data_fields': sensitive_data
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_attack_surface(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze potential attack vectors."""
    try:
        from .repository_tools import search_code
        
        # Search for attack surface patterns
        attack_patterns = [
            ('@app.route', 'web endpoint'),
            ('@api.route', 'API endpoint'),
            ('@bp.route', 'blueprint endpoint'),
            ('def view(', 'view function'),
            ('def api_', 'API function'),
            ('socket.', 'socket usage'),
            ('http.server', 'HTTP server'),
            ('flask', 'Flask framework'),
            ('django', 'Django framework'),
            ('fastapi', 'FastAPI framework')
        ]
        
        attack_surface = []
        for pattern, surface_type in attack_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    attack_surface.append({
                        'type': surface_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'attack_surface': attack_surface
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_boundaries(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze trust boundaries."""
    try:
        from .relationship_intelligence_tools import analyze_architecture_boundaries
        return analyze_architecture_boundaries(repository_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def check_advisories(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Check security advisories."""
    try:
        # Get dependencies
        dep_result = analyze_dependencies(repository_path, tool_context)
        
        if dep_result.get('status') != 'ok':
            return dep_result
        
        dependencies = dep_result.get('dependencies', [])
        
        # Check for common advisory patterns in dependency names
        advisories = []
        for dep in dependencies:
            dep_name = dep.get('name', '').lower()
            dep_version = dep.get('version', '')
            # Check for known problematic versions (simplified)
            if 'log4j' in dep_name and dep_version.startswith('2.'):
                advisories.append({
                    'name': dep.get('name'),
                    'version': dep_version,
                    'severity': 'critical',
                    'advisory': 'LOG4J-2-xxx',
                    'note': 'Log4Shell vulnerability in versions 2.x'
                })
            elif 'fastjson' in dep_name:
                advisories.append({
                    'name': dep.get('name'),
                    'version': dep_version,
                    'severity': 'high',
                    'advisory': 'FASTJSON-xxx',
                    'note': 'FastJSON deserialization vulnerabilities'
                })

        return {
            'status': 'ok',
            'repository_path': repository_path,
            'dependencies': dependencies,
            'advisories': advisories,
            'total_advisories': len(advisories),
            'note': 'Pattern-based check - use CVE database/GitHub Advisory for actual advisory scanning'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_security_report(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Generate security report."""
    try:
        from .security_quality_tools import scan_secrets
        secrets_result = scan_secrets(repository_path, tool_context)
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'security_report': {
                'secrets': secrets_result.get('secrets_found', []),
                'note': 'Full security report requires complete security analysis'
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Quality Tools

@safe
def calculate_complexity(
    file_path: str,
    tool_context: ToolContext
) -> dict:
    """Calculate cyclomatic complexity."""
    try:
        from .analysis_tools import analyze_code_complexity
        return analyze_code_complexity(file_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def calculate_cognitive_complexity(
    file_path: str,
    tool_context: ToolContext
) -> dict:
    """Calculate cognitive complexity."""
    try:
        from .analysis_tools import analyze_code_complexity
        # Use regular complexity as a proxy for cognitive complexity
        return analyze_code_complexity(file_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def detect_code_smells(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Detect code smells."""
    try:
        from .repository_tools import search_code
        
        # Search for code smell patterns
        smell_patterns = [
            ('TODO', 'incomplete code'),
            ('FIXME', 'needs fixing'),
            ('HACK', 'hacky solution'),
            ('XXX', 'attention needed'),
            ('global ', 'global variable'),
            ('import *', 'wildcard import'),
            ('except:', 'bare except'),
            ('pass', 'empty block')
        ]
        
        code_smells = []
        for pattern, smell_type in smell_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    code_smells.append({
                        'type': smell_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'code_smells': code_smells
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def detect_duplicates(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Detect duplicate code."""
    try:
        from .analysis_tools import detect_code_duplication
        return detect_code_duplication(tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def detect_dead_code(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Detect unused code."""
    try:
        from .analysis_tools import detect_dead_code
        return detect_dead_code(repository_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def detect_anti_patterns(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Detect anti-patterns."""
    try:
        from .repository_tools import search_code
        
        # Search for anti-pattern patterns
        anti_pattern_patterns = [
            ('class God', 'God object anti-pattern'),
            ('class Manager', 'Manager class anti-pattern'),
            ('def handle', 'generic handler anti-pattern'),
            ('def process', 'generic processor anti-pattern'),
            ('if isinstance', 'type checking anti-pattern'),
            ('try: except:', 'silent exception anti-pattern')
        ]
        
        anti_patterns = []
        for pattern, pattern_type in anti_pattern_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    anti_patterns.append({
                        'type': pattern_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'anti_patterns': anti_patterns
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_maintainability(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze code maintainability."""
    try:
        from .analysis_tools import analyze_code_complexity
        from .repository_tools import list_files
        
        # Get all Python files
        files_result = list_files(tool_context, directory=repository_path, pattern='.py', recursive=True)
        if files_result.get('status') != 'ok':
            return files_result
        
        total_complexity = 0
        file_count = 0
        
        for file_info in files_result['files']:
            if file_info['type'] == 'file':
                comp_result = analyze_code_complexity(file_info['path'], tool_context)
                if comp_result.get('status') == 'ok':
                    total_complexity += comp_result['complexity'].get('cyclomatic', 0)
                    file_count += 1
        
        avg_complexity = total_complexity / file_count if file_count > 0 else 0
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'maintainability': {
                'average_complexity': avg_complexity,
                'file_count': file_count,
                'total_complexity': total_complexity,
                'rating': 'good' if avg_complexity < 10 else 'moderate' if avg_complexity < 20 else 'poor'
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_testability(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze code testability."""
    try:
        from .repository_tools import search_code, list_files
        
        # Count test files
        files_result = list_files(tool_context, directory=repository_path, pattern='test', recursive=True)
        test_file_count = len([f for f in files_result.get('files', []) if 'test' in f['path'].lower()])
        
        # Search for test patterns
        test_patterns = [
            ('def test_', 'test function'),
            ('@pytest', 'pytest decorator'),
            ('@unittest', 'unittest decorator'),
            ('assert ', 'assertion')
        ]
        
        test_count = 0
        for pattern, test_type in test_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                test_count += len(search_result['matches'])
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'testability': {
                'test_file_count': test_file_count,
                'test_pattern_count': test_count,
                'has_tests': test_count > 0
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_violations(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze style violations."""
    try:
        from .repository_tools import search_code
        
        # Search for style violation patterns
        violation_patterns = [
            ('  ', 'multiple spaces'),
            ('\t', 'tab character'),
            ('line too long', 'line length'),
            ('trailing whitespace', 'trailing space')
        ]
        
        violations = []
        for pattern, violation_type in violation_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    violations.append({
                        'type': violation_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'style_violations': violations,
            'note': 'Static pattern matching - full style check requires linter integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_technical_debt(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Identify technical debt."""
    try:
        from .repository_tools import search_code
        
        # Search for technical debt indicators
        debt_patterns = [
            ('# TODO', 'TODO comment'),
            ('# FIXME', 'FIXME comment'),
            ('# HACK', 'HACK comment'),
            ('# DEPRECATED', 'deprecated code'),
            ('# XXX', 'XXX comment'),
            ('legacy', 'legacy code'),
            ('deprecated', 'deprecated function')
        ]
        
        technical_debt = []
        for pattern, debt_type in debt_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    technical_debt.append({
                        'type': debt_type,
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'technical_debt': technical_debt,
            'debt_count': len(technical_debt)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_quality_report(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Generate quality report."""
    try:
        from .analysis_tools import analyze_code_complexity
        complexity_result = analyze_code_complexity(repository_path, tool_context)
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'quality_report': {
                'complexity': complexity_result,
                'note': 'Full quality report requires complete analysis'
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
