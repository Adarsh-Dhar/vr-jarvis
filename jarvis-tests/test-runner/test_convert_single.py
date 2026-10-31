#!/usr/bin/env python3
"""
Test spec conversion on a single tool
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path('.').parent.parent / 'server'))
sys.path.insert(0, str(Path('.')))

from convert_specs import SpecConverter

def test_single_conversion():
    """Test conversion of a single spec"""
    test_root = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests')
    converter = SpecConverter(test_root)

    # Test with read_file tool
    test_id = 'CORE-read_file-T01'
    print(f"=== Converting {test_id} ===")
    converted = converter.convert_spec(test_id)

    if converted:
        print("\n=== Converted Spec ===")
        import yaml
        print(yaml.dump(converted, default_flow_style=False, sort_keys=False))
    else:
        print("Conversion failed")

if __name__ == '__main__':
    test_single_conversion()
