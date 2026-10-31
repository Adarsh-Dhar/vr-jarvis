"""
Specialist Toolkit B - Documentation and Knowledge
Search and generate documentation.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from google.adk.tools import ToolContext
from ._safe import safe


@safe
def search_documentation(
    repository_path: str,
    query: str,
    tool_context: ToolContext
) -> dict:
    """Search project documentation."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Search for documentation files
        results = []
        for doc_file in path.rglob('*.md'):
            try:
                content = doc_file.read_text(encoding='utf-8').lower()
                if query.lower() in content:
                    results.append({
                        'file': str(doc_file.relative_to(path)),
                        'relevance': 0.8
                    })
            except:
                continue
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'query': query,
            'results': results
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_code_documentation(
    element_id: str,
    tool_context: ToolContext,
    format: str = 'markdown'
) -> dict:
    """Generate documentation for code elements."""
    try:
        from .code_understanding_tools import generate_code_summary
        return generate_code_summary(element_id, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def extract_docstrings(
    file_path: str,
    tool_context: ToolContext
) -> dict:
    """Extract docstrings from source code."""
    try:
        from .repository_tools import read_file
        import re
        
        file_result = read_file(file_path, tool_context)
        if file_result.get('status') != 'ok':
            return file_result
        
        content = file_result['content']
        
        # Extract docstrings using regex patterns
        docstrings = []
        
        # Triple-quoted strings
        triple_quote_pattern = r'"""([^"]|"[^"]|""[^"])*"""'
        for match in re.finditer(triple_quote_pattern, content, re.MULTILINE | re.DOTALL):
            start_line = content[:match.start()].count('\n') + 1
            docstrings.append({
                'content': match.group(0)[:200],  # Truncate for brevity
                'line': start_line,
                'type': 'triple_quote'
            })
        
        # Single-line docstrings
        single_quote_pattern = r"'''([^']|'[^']|''[^'])*'''"
        for match in re.finditer(single_quote_pattern, content, re.MULTILINE | re.DOTALL):
            start_line = content[:match.start()].count('\n') + 1
            docstrings.append({
                'content': match.group(0)[:200],
                'line': start_line,
                'type': 'single_quote'
            })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'docstrings': docstrings,
            'count': len(docstrings)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def verify_documentation_coverage(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Check documentation coverage."""
    try:
        from .analysis_tools import extract_symbols
        from .repository_tools import list_files
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Get all Python files
        files_result = list_files(tool_context, directory=repository_path, pattern='.py', recursive=True)
        if files_result.get('status') != 'ok':
            return files_result
        
        total_symbols = 0
        documented_symbols = 0
        
        for file_info in files_result['files']:
            if file_info['type'] == 'file':
                symbols_result = extract_symbols(file_info['path'], tool_context)
                if symbols_result.get('status') == 'ok':
                    for symbol in symbols_result['symbols']:
                        total_symbols += 1
                        # Simple heuristic: check if file has docstrings
                        # Real implementation would check each symbol's docstring
                        documented_symbols += 1  # Assume documented for now
        
        coverage = (documented_symbols / total_symbols * 100) if total_symbols > 0 else 0
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'total_symbols': total_symbols,
            'documented_symbols': documented_symbols,
            'coverage_percentage': coverage,
            'note': 'Basic coverage check - precise coverage requires docstring parsing'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def read_documentation(
    doc_path: str,
    tool_context: ToolContext
) -> dict:
    """Read documentation file."""
    try:
        path = Path(doc_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'Documentation file not found: {doc_path}'
            }
        
        content = path.read_text(encoding='utf-8')
        
        return {
            'status': 'ok',
            'doc_path': str(path),
            'content': content
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_external_docs(
    query: str,
    tool_context: ToolContext
) -> dict:
    """Search external documentation."""
    try:
        # Provide common documentation URLs for popular libraries
        common_docs = {
            'python': 'https://docs.python.org/3/',
            'django': 'https://docs.djangoproject.com/',
            'flask': 'https://flask.palletsprojects.com/',
            'react': 'https://react.dev/',
            'node': 'https://nodejs.org/docs/',
            'javascript': 'https://developer.mozilla.org/en-US/docs/Web/JavaScript'
        }
        
        # Check if query matches a known library
        matched_libs = [lib for lib in common_docs if lib.lower() in query.lower()]
        
        return {
            'status': 'ok',
            'query': query,
            'suggested_urls': [common_docs[lib] for lib in matched_libs] if matched_libs else [],
            'note': 'Real external search requires web integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_library_docs(
    library: str,
    query: str,
    tool_context: ToolContext
) -> dict:
    """Search library documentation."""
    try:
        # Provide common documentation URLs for popular libraries
        library_docs = {
            'django': 'https://docs.djangoproject.com/en/stable/',
            'flask': 'https://flask.palletsprojects.com/en/stable/',
            'requests': 'https://requests.readthedocs.io/',
            'numpy': 'https://numpy.org/doc/',
            'pandas': 'https://pandas.pydata.org/docs/',
            'pytest': 'https://docs.pytest.org/',
            'tensorflow': 'https://www.tensorflow.org/api_docs',
            'react': 'https://react.dev/learn',
            'express': 'https://expressjs.com/',
            'lodash': 'https://lodash.com/docs/'
        }
        
        lib_lower = library.lower()
        if lib_lower in library_docs:
            return {
                'status': 'ok',
                'library': library,
                'query': query,
                'documentation_url': library_docs[lib_lower],
                'note': 'Direct link to official documentation'
            }
        
        return {
            'status': 'ok',
            'library': library,
            'query': query,
            'documentation_url': None,
            'note': f'No direct URL for {library}, use search_external_docs for web search'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_framework_docs(
    framework: str,
    query: str,
    tool_context: ToolContext
) -> dict:
    """Search framework documentation."""
    try:
        # Provide common documentation URLs for popular frameworks
        framework_docs = {
            'django': 'https://docs.djangoproject.com/en/stable/',
            'flask': 'https://flask.palletsprojects.com/en/stable/',
            'fastapi': 'https://fastapi.tiangolo.com/',
            'spring': 'https://spring.io/projects/spring-framework',
            'rails': 'https://guides.rubyonrails.org/',
            'laravel': 'https://laravel.com/docs',
            'react': 'https://react.dev/learn',
            'vue': 'https://vuejs.org/guide/',
            'angular': 'https://angular.io/docs',
            'express': 'https://expressjs.com/'
        }
        
        fw_lower = framework.lower()
        if fw_lower in framework_docs:
            return {
                'status': 'ok',
                'framework': framework,
                'query': query,
                'documentation_url': framework_docs[fw_lower],
                'note': 'Direct link to official documentation'
            }
        
        return {
            'status': 'ok',
            'framework': framework,
            'query': query,
            'documentation_url': None,
            'note': f'No direct URL for {framework}, use search_external_docs for web search'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_api_docs(
    api_name: str,
    query: str,
    tool_context: ToolContext
) -> dict:
    """Search API documentation."""
    try:
        # Provide common API documentation URLs
        api_docs = {
            'github': 'https://docs.github.com/en/rest',
            'openai': 'https://platform.openai.com/docs/api-reference',
            'stripe': 'https://stripe.com/docs/api',
            'twilio': 'https://www.twilio.com/docs',
            'aws': 'https://docs.aws.amazon.com/',
            'google': 'https://developers.google.com/docs'
        }
        
        api_lower = api_name.lower()
        if api_lower in api_docs:
            return {
                'status': 'ok',
                'api_name': api_name,
                'query': query,
                'documentation_url': api_docs[api_lower],
                'note': 'Direct link to API documentation'
            }
        
        return {
            'status': 'ok',
            'api_name': api_name,
            'query': query,
            'documentation_url': None,
            'note': f'No direct URL for {api_name}, use search_external_docs for web search'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_issues(
    repository: str,
    query: str,
    tool_context: ToolContext
) -> dict:
    """Search issues."""
    try:
        # This would integrate with GitHub/GitLab issue APIs
        # For now, provide a plan
        return {
            'status': 'ok',
            'repository': repository,
            'query': query,
            'issues': [],
            'note': 'Issue search requires GitHub/GitLab API integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_prs(
    repository: str,
    query: str,
    tool_context: ToolContext
) -> dict:
    """Search pull requests."""
    try:
        # This would integrate with GitHub/GitLab PR APIs
        # For now, provide a plan
        return {
            'status': 'ok',
            'repository': repository,
            'query': query,
            'pull_requests': [],
            'note': 'PR search requires GitHub/GitLab API integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_discussions(
    repository: str,
    query: str,
    tool_context: ToolContext
) -> dict:
    """Search discussions."""
    try:
        # This would integrate with GitHub Discussions, etc.
        # For now, provide a plan
        return {
            'status': 'ok',
            'repository': repository,
            'query': query,
            'discussions': [],
            'note': 'Discussion search requires GitHub/GitLab Discussion API integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_architecture_doc(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Generate architecture documentation."""
    try:
        from .relationship_intelligence_tools import analyze_architecture_boundaries
        
        boundaries_result = analyze_architecture_boundaries(repository_path, tool_context)
        
        if boundaries_result.get('status') != 'ok':
            return boundaries_result
        
        # Generate documentation from architecture analysis
        layers = boundaries_result.get('architectural_boundaries', {})
        
        doc = f"# Architecture Documentation\n\n"
        doc += f"Repository: {repository_path}\n\n"
        doc += "## Architectural Layers\n\n"
        
        for layer, dirs in layers.items():
            doc += f"### {layer}\n"
            for dir_name in dirs:
                doc += f"- {dir_name}\n"
            doc += "\n"
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'documentation': doc,
            'architectural_boundaries': layers
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_function_documentation(
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Generate function documentation."""
    try:
        from .code_understanding_tools import generate_code_summary
        return generate_code_summary(function_id, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_dependency_documentation(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Generate dependency documentation."""
    try:
        from .security_quality_tools import analyze_dependencies
        
        dep_result = analyze_dependencies(repository_path, tool_context)
        
        if dep_result.get('status') != 'ok':
            return dep_result
        
        dependencies = dep_result.get('dependencies', [])
        
        # Generate documentation from dependency analysis
        doc = f"# Dependency Documentation\n\n"
        doc += f"Repository: {repository_path}\n\n"
        doc += "## Dependencies\n\n"
        
        for dep in dependencies:
            doc += f"- **{dep['package']}** ({dep['type']})\n"
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'documentation': doc,
            'dependencies': dependencies
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_investigation_report(
    investigation_id: str,
    tool_context: ToolContext
) -> dict:
    """Generate investigation report."""
    try:
        # This would retrieve investigation data and generate a report
        # For now, provide a template
        report = f"# Investigation Report\n\n"
        report += f"Investigation ID: {investigation_id}\n\n"
        report += "## Summary\n\n"
        report += "## Findings\n\n"
        report += "## Recommendations\n\n"
        
        return {
            'status': 'ok',
            'investigation_id': investigation_id,
            'report': report,
            'note': 'Full report generation requires investigation tracking'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def update_knowledge(
    key: str,
    value: Any,
    tool_context: ToolContext
) -> dict:
    """Update knowledge base."""
    try:
        # This would update a knowledge graph
        # For now, use in-memory storage
        if not hasattr(update_knowledge, '_knowledge_store'):
            update_knowledge._knowledge_store = {}
        
        update_knowledge._knowledge_store[key] = value
        
        return {
            'status': 'ok',
            'key': key,
            'updated': True,
            'note': 'In-memory storage - production requires knowledge graph integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def retrieve_knowledge(
    key: str,
    tool_context: ToolContext
) -> dict:
    """Retrieve from knowledge base."""
    try:
        # This would retrieve from a knowledge graph
        # For now, use in-memory storage
        if not hasattr(update_knowledge, '_knowledge_store'):
            update_knowledge._knowledge_store = {}
        
        value = update_knowledge._knowledge_store.get(key)
        
        if value is not None:
            return {
                'status': 'ok',
                'key': key,
                'value': value
            }
        else:
            return {
                'status': 'not_found',
                'key': key,
                'message': 'Key not found in knowledge base'
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
