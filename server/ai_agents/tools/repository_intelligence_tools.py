"""
Agent 3 - Repository Intelligence Tools
Understand everything available in your software projects.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from google.adk.tools import ToolContext
from ._safe import safe


@safe
def detect_languages(repository_path: str, tool_context: ToolContext) -> dict:
    """Identify all programming languages."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Simple language detection by file extension
        language_extensions = {
            'python': ['.py'],
            'javascript': ['.js', '.jsx'],
            'typescript': ['.ts', '.tsx'],
            'java': ['.java'],
            'c': ['.c', '.h'],
            'cpp': ['.cpp', '.hpp', '.cc', '.cxx'],
            'csharp': ['.cs'],
            'go': ['.go'],
            'rust': ['.rs'],
            'php': ['.php'],
            'ruby': ['.rb'],
            'swift': ['.swift'],
            'kotlin': ['.kt', '.kts'],
            'dart': ['.dart'],
            'sql': ['.sql'],
            'lua': ['.lua'],
            'r': ['.r', '.R'],
            'scala': ['.scala']
        }
        
        languages = {}
        total_files = 0
        
        for file_path in path.rglob('*'):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                for lang, exts in language_extensions.items():
                    if ext in exts:
                        languages[lang] = languages.get(lang, 0) + 1
                        total_files += 1
                        break
        
        # Calculate percentages
        result = {}
        for lang, count in languages.items():
            result[lang] = {
                'files': count,
                'percentage': count / total_files if total_files > 0 else 0
            }
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'languages': result
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def detect_frameworks(repository_path: str, tool_context: ToolContext) -> dict:
    """Identify frameworks and libraries."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Detect frameworks by looking for config files and dependencies
        frameworks = []
        
        # Check for Python frameworks
        if (path / 'requirements.txt').exists():
            frameworks.append({'name': 'Python project', 'evidence': 'requirements.txt'})
        if (path / 'setup.py').exists():
            frameworks.append({'name': 'Python package', 'evidence': 'setup.py'})
        if (path / 'pyproject.toml').exists():
            frameworks.append({'name': 'Python project', 'evidence': 'pyproject.toml'})
        
        # Check for Node.js frameworks
        if (path / 'package.json').exists():
            frameworks.append({'name': 'Node.js project', 'evidence': 'package.json'})
        
        # Check for Java frameworks
        if (path / 'pom.xml').exists():
            frameworks.append({'name': 'Maven project', 'evidence': 'pom.xml'})
        if (path / 'build.gradle').exists():
            frameworks.append({'name': 'Gradle project', 'evidence': 'build.gradle'})
        
        # Check for .NET frameworks
        if (path / '.csproj').exists():
            frameworks.append({'name': '.NET project', 'evidence': '.csproj'})
        
        # Check for Go
        if (path / 'go.mod').exists():
            frameworks.append({'name': 'Go module', 'evidence': 'go.mod'})
        
        # Check for Rust
        if (path / 'Cargo.toml').exists():
            frameworks.append({'name': 'Rust project', 'evidence': 'Cargo.toml'})
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'frameworks': frameworks
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_repository_structure(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze repository structure."""
    try:
        from .repository_tools import list_files
        return list_files(repository_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_entry_points(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Identify application entry points."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        entry_points = []
        
        # Common entry point files
        common_entries = [
            'main.py', 'app.py', 'index.js', 'index.ts', 'main.go', 'main.rs',
            'Main.java', 'Program.cs', 'startup.py'
        ]
        
        for entry in common_entries:
            if (path / entry).exists():
                entry_points.append({
                    'file': entry,
                    'type': 'entry_point'
                })
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'entry_points': entry_points
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def detect_build_system(repository_path: str, tool_context: ToolContext) -> dict:
    """Detect build system."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        build_systems = []
        
        if (path / 'Makefile').exists():
            build_systems.append('make')
        if (path / 'CMakeLists.txt').exists():
            build_systems.append('cmake')
        if (path / 'pom.xml').exists():
            build_systems.append('maven')
        if (path / 'build.gradle').exists():
            build_systems.append('gradle')
        if (path / 'package.json').exists():
            build_systems.append('npm')
        if (path / 'setup.py').exists() or (path / 'pyproject.toml').exists():
            build_systems.append('setuptools/pip')
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'build_systems': build_systems
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def detect_package_manager(repository_path: str, tool_context: ToolContext) -> dict:
    """Detect package manager."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        package_managers = []
        
        if (path / 'package.json').exists():
            package_managers.append('npm/yarn')
        if (path / 'requirements.txt').exists() or (path / 'setup.py').exists():
            package_managers.append('pip')
        if (path / 'pom.xml').exists():
            package_managers.append('maven')
        if (path / 'build.gradle').exists():
            package_managers.append('gradle')
        if (path / 'go.mod').exists():
            package_managers.append('go modules')
        if (path / 'Cargo.toml').exists():
            package_managers.append('cargo')
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'package_managers': package_managers
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def detect_project_type(repository_path: str, tool_context: ToolContext) -> dict:
    """Detect project type."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        project_type = 'unknown'
        
        if (path / 'package.json').exists():
            project_type = 'javascript/node'
        elif (path / 'requirements.txt').exists() or (path / 'setup.py').exists():
            project_type = 'python'
        elif (path / 'pom.xml').exists():
            project_type = 'java/maven'
        elif (path / 'build.gradle').exists():
            project_type = 'java/gradle'
        elif (path / 'go.mod').exists():
            project_type = 'go'
        elif (path / 'Cargo.toml').exists():
            project_type = 'rust'
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'project_type': project_type
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_monorepo(repository_path: str, tool_context: ToolContext) -> dict:
    """Analyze monorepo structure."""
    try:
        from .repository_tools import list_files
        return list_files(repository_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_project_configuration(repository_path: str, tool_context: ToolContext) -> dict:
    """Analyze project configuration."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        configs = []
        
        for config_file in path.glob('*.json'):
            configs.append(str(config_file))
        for config_file in path.glob('*.yaml'):
            configs.append(str(config_file))
        for config_file in path.glob('*.yml'):
            configs.append(str(config_file))
        for config_file in path.glob('*.toml'):
            configs.append(str(config_file))
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'configurations': configs
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_build_configuration(repository_path: str, tool_context: ToolContext) -> dict:
    """Analyze build configuration."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        build_configs = []
        
        if (path / 'Makefile').exists():
            build_configs.append('Makefile')
        if (path / 'CMakeLists.txt').exists():
            build_configs.append('CMakeLists.txt')
        if (path / 'pom.xml').exists():
            build_configs.append('pom.xml')
        if (path / 'build.gradle').exists():
            build_configs.append('build.gradle')
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'build_configurations': build_configs
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_environment_configuration(repository_path: str, tool_context: ToolContext) -> dict:
    """Analyze environment configuration."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        env_configs = []
        
        if (path / '.env').exists():
            env_configs.append('.env')
        if (path / '.env.example').exists():
            env_configs.append('.env.example')
        if (path / 'docker-compose.yml').exists():
            env_configs.append('docker-compose.yml')
        if (path / 'Dockerfile').exists():
            env_configs.append('Dockerfile')
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'environment_configurations': env_configs
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_dependencies_manifest(repository_path: str, tool_context: ToolContext) -> dict:
    """Analyze dependencies manifest."""
    try:
        from .analysis_tools import analyze_dependencies
        return analyze_dependencies(repository_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def resolve_dependency_versions(repository_path: str, tool_context: ToolContext) -> dict:
    """Resolve dependency versions."""
    try:
        from .analysis_tools import analyze_dependencies
        result = analyze_dependencies(repository_path, tool_context)
        return result
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_external_services(repository_path: str, tool_context: ToolContext) -> dict:
    """Identify external services."""
    try:
        from .repository_tools import search_code
        
        service_patterns = ['http://', 'https://', 'api.', 'aws.', 's3://', 'redis://', 'mongodb://']
        services = []
        
        for pattern in service_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    services.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line']
                    })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'external_services': services
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_generated_files(repository_path: str, tool_context: ToolContext) -> dict:
    """Identify generated files."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        generated_patterns = ['node_modules', '__pycache__', '.git', 'build', 'dist', '*.pyc']
        generated_files = []
        
        for pattern in generated_patterns:
            if '*' in pattern:
                for f in path.glob(pattern):
                    generated_files.append(str(f))
            else:
                if (path / pattern).exists():
                    generated_files.append(pattern)
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'generated_files': generated_files
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def index_repository(repository_path: str, tool_context: ToolContext) -> dict:
    """Index repository."""
    try:
        from .repository_tools import list_files
        return list_files(repository_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def incremental_index_repository(repository_path: str, tool_context: ToolContext) -> dict:
    """Incrementally index repository."""
    try:
        from .repository_tools import list_files
        return list_files(repository_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def detect_repository_changes(repository_path: str, tool_context: ToolContext) -> dict:
    """Detect repository changes."""
    try:
        from .git_tools import list_changed_nodes
        return list_changed_nodes(repository_path, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
