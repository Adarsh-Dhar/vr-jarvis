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
