#!/usr/bin/env python3
"""
Batch Verified Spec Generator
Generates verified specs for multiple tools from a configuration file.
"""

import sys
import yaml
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))
from verified_spec_generator import VerifiedSpecGenerator


class BatchVerifiedGenerator:
    """Batch generates verified test specs"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.generator = VerifiedSpecGenerator(test_root)

    def load_config(self, config_file: Path) -> Dict:
        """Load batch configuration"""
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)

    def generate_from_config(self, config: Dict):
        """Generate all specs from configuration"""
        tools = config.get('tools', [])
        
        results = {
            'generated': [],
            'failed': []
        }
        
        for tool_config in tools:
            tool_name = tool_config['tool']
            archetype = tool_config['archetype']
            fixture = tool_config.get('fixture', 'simple-python')
            manifest_file = tool_config.get('manifest')
            
            try:
                # Load manifest if provided
                manifest = {}
                if manifest_file:
                    manifest_path = Path(__file__).parent / 'manifests' / manifest_file
                    if manifest_path.exists():
                        with open(manifest_path, 'r') as f:
                            manifest = yaml.safe_load(f)
                
                # Generate spec
                if archetype == 'read_search':
                    spec = self.generator.generate_read_search_spec(tool_name, fixture, manifest)
                    self.generator.save_spec(spec, 'read_search')
                elif archetype == 'analysis':
                    spec = self.generator.generate_analysis_spec(tool_name, fixture, manifest)
                    self.generator.save_spec(spec, 'analysis')
                elif archetype == 'modify':
                    spec = self.generator.generate_modify_spec(tool_name, fixture, manifest)
                    self.generator.save_spec(spec, 'modify')
                elif archetype == 'execute':
                    spec = self.generator.generate_execute_spec(tool_name, fixture, manifest)
                    self.generator.save_spec(spec, 'execute')
                elif archetype == 'integration':
                    spec = self.generator.generate_integration_spec(tool_name, fixture, manifest)
                    self.generator.save_spec(spec, 'integration')
                
                results['generated'].append(tool_name)
                print(f"✅ Generated: {tool_name}")
                
            except Exception as e:
                results['failed'].append({'tool': tool_name, 'error': str(e)})
                print(f"❌ Failed: {tool_name} - {e}")
        
        return results

    def generate_variants(self, base_spec: Dict) -> List[Dict]:
        """
        Auto-generate T02, T04, T08, T12 variants from T01 base spec.
        These variants need no tool-specific expected results.
        """
        variants = []
        
        # T02: Invalid input
        t02 = base_spec.copy()
        t02['test_id'] = t02['test_id'].replace('T01', 'T02')
        t02['name'] = t02['name'].replace('Happy Path', 'Invalid Input')
        t02['test_type'] = 'T02'
        t02['description'] = 'Invalid input - should fail gracefully'
        t02['input'] = {'invalid_field': 'invalid_value'}
        t02['expected'] = {'status': 'error'}
        t02['checks'] = [{'type': 'equals', 'field': 'status', 'value': 'error'}]
        variants.append(t02)
        
        # T04: Empty result
        t04 = base_spec.copy()
        t04['test_id'] = t04['test_id'].replace('T01', 'T04')
        t04['name'] = t04['name'].replace('Happy Path', 'Empty Result')
        t04['test_type'] = 'T04'
        t04['description'] = 'Empty result boundary case'
        t04['input'] = base_spec['input'].copy()
        t04['input']['target'] = 'non_existent_function'
        t04['expected'] = {'status': 'ok', 'results': []}
        variants.append(t04)
        
        # T08: Malformed input
        t08 = base_spec.copy()
        t08['test_id'] = t08['test_id'].replace('T01', 'T08')
        t08['name'] = t08['name'].replace('Happy Path', 'Malformed Input')
        t08['test_type'] = 'T08'
        t08['description'] = 'Malformed input - should fail gracefully'
        t08['input'] = {'malformed': True}
        t08['expected'] = {'status': 'error'}
        t08['checks'] = [{'type': 'equals', 'field': 'status', 'value': 'error'}]
        variants.append(t08)
        
        # T12: Security/path escape
        t12 = base_spec.copy()
        t12['test_id'] = t12['test_id'].replace('T01', 'T12')
        t12['name'] = t12['name'].replace('Happy Path', 'Security Check')
        t12['test_type'] = 'T12'
        t12['description'] = 'Security - path traversal and permission check'
        t12['input'] = {'target': '../../../etc/passwd'}
        t12['expected'] = {'status': 'error'}
        t12['must_not'] = ['escape_sandbox', 'read_sensitive_files']
        t12['checks'] = [
            {'type': 'equals', 'field': 'status', 'value': 'error'},
            {'type': 'sandbox_check', 'did_not_escape': True}
        ]
        variants.append(t12)
        
        return variants


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Batch generate verified test specs')
    parser.add_argument('--test-root', type=str, default='..',
                        help='Path to test root directory')
    parser.add_argument('--config', type=str,
                        help='Path to batch configuration file')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    batch_gen = BatchVerifiedGenerator(test_root)

    if args.config:
        config_path = Path(args.config)
        config = batch_gen.load_config(config_path)
        results = batch_gen.generate_from_config(config)
        
        print(f"\n{'='*60}")
        print(f"Batch Generation Results")
        print(f"{'='*60}")
        print(f"Generated: {len(results['generated'])}")
        print(f"Failed: {len(results['failed'])}")
        
        if results['failed']:
            print("\nFailed tools:")
            for failure in results['failed']:
                print(f"  - {failure['tool']}: {failure['error']}")
    else:
        print("Error: Must specify --config")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
