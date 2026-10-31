#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_registry import TestRegistry

test_root = Path(__file__).parent.parent
registry = TestRegistry(test_root)
registry.load_test_definitions()

print(f'Total tests: {len(registry.get_all_tests())}')
print(f'Tests by layer:')
for layer in sorted(registry.tests_by_layer.keys()):
    print(f'  Layer {layer}: {len(registry.tests_by_layer[layer])}')
print(f'Tests by test_type:')
for test_type in sorted(registry.tests_by_test_type.keys()):
    print(f'  {test_type}: {len(registry.tests_by_test_type[test_type])}')
