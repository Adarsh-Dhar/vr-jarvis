"""
Ground Truth Engine (Improved)
Compares results against known answers using manifests, not just equality.
Reports TP, FP, FN per spec with precision and recall thresholds.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set
import yaml
import sys
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))


class GroundTruthEngine:
    """Compares test results against expected ground truth using manifests"""
    
    def __init__(self, test_root: Path):
        self.test_root = test_root
        # Fixtures are in jarvis-tests/fixtures, not test-runner/fixtures
        self.fixtures_dir = test_root.resolve().parent / 'fixtures' / 'repositories'
    
    def load_manifest(self, repository_name: str) -> Optional[Dict]:
        """Load ground truth manifest for a repository"""
        manifest_file = self.fixtures_dir / repository_name / 'ground-truth.yaml'
        if not manifest_file.exists():
            return None
        
        with open(manifest_file, 'r') as f:
            return yaml.safe_load(f)
    
    def compare_against_manifest(self, tool_output: Dict, manifest: Dict, 
                                tool_name: str, min_precision: float = 0.95, 
                                min_recall: float = 0.90) -> Dict:
        """
        Compare tool output against ground truth manifest.
        Returns TP, FP, FN with precision and recall.
        """
        result = {
            'tool': tool_name,
            'repository': manifest.get('repository', 'unknown'),
            'precision': 0.0,
            'recall': 0.0,
            'true_positives': [],
            'false_positives': [],
            'false_negatives': [],
            'f1_score': 0.0,
            'meets_thresholds': False
        }
        
        # Extract relevant data from manifest based on tool type
        if tool_name in ['find_callers', 'find_callees']:
            result = self._compare_relationship(tool_output, manifest, tool_name)
        elif tool_name in ['extract_symbols', 'list_files']:
            result = self._compare_symbols(tool_output, manifest, tool_name)
        else:
            # Generic comparison
            result = self._compare_generic(tool_output, manifest, tool_name)
        
        # Check thresholds
        result['meets_thresholds'] = (
            result['precision'] >= min_precision and 
            result['recall'] >= min_recall
        )
        
        return result
    
    def _compare_relationship(self, output: Dict, manifest: Dict, tool_name: str) -> Dict:
        """Compare relationship tool output against manifest"""
        result = {
            'precision': 0.0,
            'recall': 0.0,
            'true_positives': [],
            'false_positives': [],
            'false_negatives': [],
            'f1_score': 0.0
        }
        
        # Get expected relationships from manifest
        gt_functions = manifest.get('functions', {})
        gt_call_graph = manifest.get('call_graph', {}).get('edges', [])
        
        # Extract actual relationships from output
        actual_relationships = output.get('relationships', [])
        actual_set = set()
        for rel in actual_relationships:
            if rel.get('type') == 'direct':
                actual_set.add((rel.get('from'), rel.get('to')))
        
        # Build expected set from manifest
        expected_set = set()
        for edge in gt_call_graph:
            if edge.get('type') == 'direct':
                expected_set.add((edge.get('from'), edge.get('to')))
        
        # Calculate TP, FP, FN
        true_positives = actual_set & expected_set
        false_positives = actual_set - expected_set
        false_negatives = expected_set - actual_set
        
        result['true_positives'] = list(true_positives)
        result['false_positives'] = list(false_positives)
        result['false_negatives'] = list(false_negatives)
        
        # Calculate precision and recall
        if actual_set:
            result['precision'] = len(true_positives) / len(actual_set)
        if expected_set:
            result['recall'] = len(true_positives) / len(expected_set)
        
        # Calculate F1 score
        if result['precision'] + result['recall'] > 0:
            result['f1_score'] = 2 * (result['precision'] * result['recall']) / (result['precision'] + result['recall'])
        
        return result
    
    def _compare_symbols(self, output: Dict, manifest: Dict, tool_name: str) -> Dict:
        """Compare symbol tool output against manifest"""
        result = {
            'precision': 0.0,
            'recall': 0.0,
            'true_positives': [],
            'false_positives': [],
            'false_negatives': [],
            'f1_score': 0.0
        }
        
        # Get expected symbols from manifest
        gt_functions = manifest.get('functions', {})
        expected_symbols = set(gt_functions.keys())
        
        # Extract actual symbols from output
        actual_symbols = output.get('symbols', [])
        actual_set = set(s.get('name') if isinstance(s, dict) else str(s) for s in actual_symbols)
        
        # Calculate TP, FP, FN
        true_positives = actual_set & expected_symbols
        false_positives = actual_set - expected_symbols
        false_negatives = expected_symbols - actual_set
        
        result['true_positives'] = list(true_positives)
        result['false_positives'] = list(false_positives)
        result['false_negatives'] = list(false_negatives)
        
        # Calculate precision and recall
        if actual_set:
            result['precision'] = len(true_positives) / len(actual_set)
        if expected_symbols:
            result['recall'] = len(true_positives) / len(expected_symbols)
        
        # Calculate F1 score
        if result['precision'] + result['recall'] > 0:
            result['f1_score'] = 2 * (result['precision'] * result['recall']) / (result['precision'] + result['recall'])
        
        return result
    
    
    def _compare_generic(self, output: Dict, manifest: Dict, tool_name: str) -> Dict:
        """Generic comparison for other tools"""
        # For now, just check if status is ok
        result = {
            'precision': 1.0,
            'recall': 1.0,
            'true_positives': [],
            'false_positives': [],
            'false_negatives': [],
            'f1_score': 1.0
        }
        
        if output.get('status') != 'ok':
            result['precision'] = 0.0
            result['recall'] = 0.0
            result['f1_score'] = 0.0
        
        return result
    
    def validate_callers(self, actual_callers: List, expected_callers: List) -> Dict:
        """Validate caller discovery results (legacy method)"""
        actual_set = set(c.get('name') for c in actual_callers)
        expected_set = set(c.get('name') for c in expected_callers)
        
        # Calculate precision and recall
        true_positives = actual_set & expected_set
        false_positives = actual_set - expected_set
        false_negatives = expected_set - actual_set
        
        precision = len(true_positives) / len(actual_set) if actual_set else 0
        recall = len(true_positives) / len(expected_set) if expected_set else 0
        
        return {
            'precision': precision,
            'recall': recall,
            'true_positives': list(true_positives),
            'false_positives': list(false_positives),
            'false_negatives': list(false_negatives),
            'f1_score': 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        }
