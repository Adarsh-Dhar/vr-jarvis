#!/usr/bin/env python3
"""
Replace all Path.cwd() and os.getcwd() uses with repo_root() or resolve_in_repo().
This implements Phase A1 of the JARVIS patch list.
"""

import re
from pathlib import Path
from typing import Tuple

# Mapping of files to their Path.cwd() counts (from the patch list)
FILE_COUNTS = {
    'software_engineering_tools.py': 30,
    'testing_verification_tools.py': 13,
    'repository_tools.py': 11,
    'repository_intelligence_tools.py': 11,
    'analysis_tools.py': 8,
    'navigation_tools.py': 2,
    'code_understanding_tools.py': 1,
    '_common.py': 1,
}

TOOLS_DIR = Path(__file__).parent.parent / 'server' / 'ai_agents' / 'tools'


def replace_in_file(filepath: Path) -> Tuple[int, int]:
    """Replace Path.cwd() and os.getcwd() in a file.
    
    Returns:
        (path_cwd_count, os_getcwd_count) - number of replacements made
    """
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return 0, 0
    
    content = filepath.read_text(encoding='utf-8')
    original_content = content
    
    path_cwd_count = 0
    os_getcwd_count = 0
    
    # Pattern 1: Path.cwd() / path -> resolve_in_repo(path)
    # This is for cases where we're joining a path
    content = re.sub(
        r'Path\.cwd\(\)\s*/\s*([a-zA-Z_][a-zA-Z0-9_]*)',
        r'resolve_in_repo(\1)',
        content
    )
    
    # Pattern 2: Path.cwd() / path_expression -> resolve_in_repo(path_expression)
    # More complex path expressions
    content = re.sub(
        r'Path\.cwd\(\)\s*/\s*([^/\n]+)',
        r'resolve_in_repo(\1)',
        content
    )
    
    # Pattern 3: cwd = Path.cwd() or cwd=str(Path.cwd()) -> cwd = repo_root()
    content = re.sub(
        r'cwd\s*=\s*Path\.cwd\(\)',
        r'cwd = repo_root()',
        content
    )
    content = re.sub(
        r'cwd\s*=\s*str\(Path\.cwd\(\)\)',
        r'cwd = str(repo_root())',
        content
    )
    
    # Pattern 4: standalone Path.cwd() in conditions or comparisons
    # e.g., if not path.is_absolute(): path = Path.cwd() / path
    # This is handled by patterns 1-2, but we need to handle the case where
    # it's just Path.cwd() by itself (like in subprocess cwd parameter)
    content = re.sub(
        r'cwd\s*=\s*str\(Path\.cwd\(\)\)',
        r'cwd = str(repo_root())',
        content
    )
    
    # Pattern 5: os.getcwd() -> repo_root()
    content = re.sub(
        r'os\.getcwd\(\)',
        r'repo_root()',
        content
    )
    
    # Count how many we replaced
    path_cwd_count = original_content.count('Path.cwd()') - content.count('Path.cwd()')
    os_getcwd_count = original_content.count('os.getcwd()') - content.count('os.getcwd()')
    
    # Count the resolve_in_repo additions
    resolve_in_repo_added = content.count('resolve_in_repo(')
    
    if content != original_content:
        filepath.write_text(content, encoding='utf-8')
        print(f"Updated {filepath.name}: {path_cwd_count} Path.cwd(), {os_getcwd_count} os.getcwd(), {resolve_in_repo_added} resolve_in_repo() added")
    
    return path_cwd_count, os_getcwd_count


def main():
    """Run the replacement on all tool files."""
    total_path_cwd = 0
    total_os_getcwd = 0
    
    for filename, expected_count in FILE_COUNTS.items():
        filepath = TOOLS_DIR / filename
        path_cwd, os_getcwd = replace_in_file(filepath)
        total_path_cwd += path_cwd
        total_os_getcwd += os_getcwd
    
    print(f"\nTotal replacements: {total_path_cwd} Path.cwd(), {total_os_getcwd} os.getcwd()")
    print(f"Expected total: 109")
    print(f"Actual total: {total_path_cwd + total_os_getcwd}")
    
    # Check if we need to add the import
    for filename in FILE_COUNTS.keys():
        filepath = TOOLS_DIR / filename
        if filepath.exists():
            content = filepath.read_text(encoding='utf-8')
            if 'resolve_in_repo' in content or 'repo_root' in content:
                # Check if _common is imported
                if 'from ._common import' not in content and 'from . import _common' not in content:
                    # Add the import at the top after other imports
                    lines = content.split('\n')
                    import_idx = 0
                    for i, line in enumerate(lines):
                        if line.startswith('from ') or line.startswith('import '):
                            import_idx = i + 1
                        elif import_idx > 0 and not (line.startswith('from ') or line.startswith('import ') or line.strip() == ''):
                            break
                    
                    # Insert the import
                    lines.insert(import_idx, 'from ._common import repo_root, resolve_in_repo')
                    filepath.write_text('\n'.join(lines), encoding='utf-8')
                    print(f"Added import to {filename}")


if __name__ == '__main__':
    main()
