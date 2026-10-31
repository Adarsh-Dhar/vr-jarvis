"""
Test Registry
Stores all test definitions and metadata
"""

from pathlib import Path
from typing import Dict, List, Optional
import yaml
import json
import sys
sys.path.insert(0, str(Path(__file__).parent))


class TestRegistry:
    """Central registry for all JARVIS tests"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.tests: Dict[str, Dict] = {}
        self.tests_by_category: Dict[str, List[str]] = {}
        self.tests_by_tool: Dict[str, List[str]] = {}
        self.tests_by_severity: Dict[str, List[str]] = {}
        self.tests_by_layer: Dict[int, List[str]] = {}
        self.tests_by_test_type: Dict[str, List[str]] = {}
        
    def load_test_definitions(self):
        """Load all test definitions from YAML and Python files"""
        # Load YAML test definitions
        yaml_tests_path = self.test_root / 'tests'
        for yaml_file in yaml_tests_path.rglob('*.yaml'):
            self._load_yaml_test(yaml_file)
        
        # Load Python test files
        python_tests_path = self.test_root / 'tests'
        for py_file in python_tests_path.rglob('test_*.py'):
            self._load_python_test(py_file)
    
    def _load_yaml_test(self, yaml_file: Path):
        """Load a test definition from YAML file"""
        with open(yaml_file, 'r') as f:
            test_def = yaml.safe_load(f)
        
        test_id = test_def.get('test_id')
        if test_id:
            self.tests[test_id] = test_def
            self._index_test(test_id, test_def)
    
    def _load_python_test(self, py_file: Path):
        """Load test metadata from Python test file"""
        # Parse Python file to extract test metadata
        # For now, create a basic entry
        test_id = py_file.stem
        self.tests[test_id] = {
            'test_id': test_id,
            'name': test_id.replace('_', ' ').title(),
            'category': py_file.parent.name,
            'file': str(py_file),
            'type': 'python'
        }
        self._index_test(test_id, self.tests[test_id])
    
    def _index_test(self, test_id: str, test_def: Dict):
        """Index test by category, tool, severity, layer, and test_type"""
        category = test_def.get('category', 'unknown')
        if category not in self.tests_by_category:
            self.tests_by_category[category] = []
        self.tests_by_category[category].append(test_id)

        tool = test_def.get('tool')
        if tool:
            if tool not in self.tests_by_tool:
                self.tests_by_tool[tool] = []
            self.tests_by_tool[tool].append(test_id)

        severity = test_def.get('severity', 'medium')
        if severity not in self.tests_by_severity:
            self.tests_by_severity[severity] = []
        self.tests_by_severity[severity].append(test_id)

        # Index by layer
        layer = test_def.get('layer')
        if layer is not None:
            if layer not in self.tests_by_layer:
                self.tests_by_layer[layer] = []
            self.tests_by_layer[layer].append(test_id)

        # Index by test type
        test_type = test_def.get('test_type')
        if test_type:
            if test_type not in self.tests_by_test_type:
                self.tests_by_test_type[test_type] = []
            self.tests_by_test_type[test_type].append(test_id)
    
    def get_test(self, test_id: str) -> Optional[Dict]:
        """Get a test definition by ID"""
        return self.tests.get(test_id)
    
    def get_tests_by_category(self, category: str) -> List[str]:
        """Get all test IDs in a category"""
        return self.tests_by_category.get(category, [])
    
    def get_tests_by_tool(self, tool: str) -> List[str]:
        """Get all test IDs for a specific tool"""
        return self.tests_by_tool.get(tool, [])
    
    def get_tests_by_severity(self, severity: str) -> List[str]:
        """Get all test IDs with a specific severity"""
        return self.tests_by_severity.get(severity, [])
    
    def get_all_tests(self) -> Dict[str, Dict]:
        """Get all test definitions"""
        return self.tests
    
    def get_critical_tests(self) -> List[str]:
        """Get all critical tests"""
        return self.get_tests_by_severity('critical')
    
    def get_high_priority_tests(self) -> List[str]:
        """Get all high priority tests"""
        return self.get_tests_by_severity('high')

    def get_tests_by_layer(self, layer: int) -> List[str]:
        """Get all test IDs in a specific layer"""
        return self.tests_by_layer.get(layer, [])

    def get_tests_by_test_type(self, test_type: str) -> List[str]:
        """Get all test IDs of a specific test type"""
        return self.tests_by_test_type.get(test_type, [])
