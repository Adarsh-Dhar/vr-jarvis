"""
Ground Truth Engine
Compares results against known answers
"""

from pathlib import Path
from typing import Dict, List, Optional
import yaml
import sys
sys.path.insert(0, str(Path(__file__).parent))


class GroundTruthEngine:
    """Compares test results against expected ground truth"""
    
    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.expected_results_dir = test_root / 'expected-results'
    
    def load_expected_result(self, test_id: str, result_type: str) -> Optional[Dict]:
        """Load expected result for a test"""
        result_file = self.expected_results_dir / result_type / f'{test_id}.yaml'
        if not result_file.exists():
            return None
        
        with open(result_file, 'r') as f:
            return yaml.safe_load(f)
    
    def compare_result(self, test_id: str, actual: Dict, expected: Dict) -> Dict:
        """Compare actual result against expected result"""
        comparison = {
            'test_id': test_id,
            'matches': True,
            'differences': [],
            'correctness_score': 1.0
        }
        
        # Compare key fields
        for key in expected.keys():
            if key not in actual:
                comparison['matches'] = False
                comparison['differences'].append(f"Missing key: {key}")
            elif actual[key] != expected[key]:
                comparison['matches'] = False
                comparison['differences'].append(f"Mismatch on {key}: expected {expected[key]}, got {actual[key]}")
        
        # Calculate correctness score
        if comparison['differences']:
            comparison['correctness_score'] = 1.0 - (len(comparison['differences']) / len(expected))
        
        return comparison
    
    def validate_callers(self, actual_callers: List, expected_callers: List) -> Dict:
        """Validate caller discovery results"""
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
