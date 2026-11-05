"""Python AST helpers for advanced parsing."""
import ast
from typing import List, Dict, Tuple, Optional


def extract_class_ranges(text: str) -> Dict[str, Tuple[int, int]]:
    """Extract class name to line range mapping."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    
    class_ranges = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)
    
    return class_ranges


def extract_parameter_annotations(text: str) -> Dict[str, List[Dict]]:
    """Extract parameter type annotations from functions."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    
    annotations = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = []
            for arg in node.args.args:
                annotation = None
                if arg.annotation:
                    annotation = ast.unparse(arg.annotation)
                params.append({
                    'name': arg.arg,
                    'annotation': annotation
                })
            if params:
                qualname = node.name
                # Add class prefix if inside a class
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.ClassDef) and node in ast.walk(parent):
                        qualname = f"{parent.name}.{node.name}"
                        break
                annotations[qualname] = params
    
    return annotations


def extract_type_assignments_in_init(text: str) -> Dict[str, str]:
    """Extract self.x = Class() assignments in __init__ methods."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    
    type_assignments = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                    for stmt in item.body:
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if isinstance(target, ast.Attribute):
                                    if isinstance(target.value, ast.Name) and target.value.id == 'self':
                                        attr_name = target.attr
                                        if isinstance(stmt.value, ast.Call):
                                            if isinstance(stmt.value.func, ast.Name):
                                                type_assignments[f"{class_name}.{attr_name}"] = stmt.value.func.id
    
    return type_assignments


def extract_base_classes(text: str) -> Dict[str, List[str]]:
    """Extract base class expressions."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    
    base_classes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                try:
                    bases.append(ast.unparse(base))
                except:
                    bases.append('<unknown>')
            if bases:
                base_classes[node.name] = bases
    
    return base_classes
