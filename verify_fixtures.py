#!/usr/bin/env python3
"""
Quick fixture verification
Verifies that simple-python and spring-boot fixtures exist and are structured correctly.
"""

import sys
from pathlib import Path

fixtures_path = Path("jarvis-tests/fixtures/repositories")

print("Verifying fixtures...")

# Check simple-python
simple_python = fixtures_path / "simple-python"
if simple_python.exists():
    print(f"✅ simple-python exists: {simple_python}")
    main_py = simple_python / "main.py"
    if main_py.exists():
        print(f"  ✅ main.py exists")
    else:
        print(f"  ❌ main.py missing")
else:
    print(f"❌ simple-python not found")

# Check spring-boot (if it exists)
spring_boot = fixtures_path / "spring-boot"
if spring_boot.exists():
    print(f"✅ spring-boot exists: {spring_boot}")
else:
    print(f"⚠️  spring-boot not found (optional)")

print("\nFixture verification complete.")
