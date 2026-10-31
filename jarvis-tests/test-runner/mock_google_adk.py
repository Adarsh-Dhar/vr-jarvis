"""
Mock google.adk.tools for testing
"""

import sys
from types import ModuleType

# Create mock modules
google_module = ModuleType('google')
google_adk_module = ModuleType('google.adk')
google_adk_tools_module = ModuleType('google.adk.tools')

# Create mock ToolContext class
class MockToolContext:
    """Mock ToolContext for testing"""
    def __init__(self):
        self.state = {}

# Add MockToolContext to the mock module
google_adk_tools_module.ToolContext = MockToolContext

# Build the module hierarchy
google_module.adk = google_adk_module
google_adk_module.tools = google_adk_tools_module

# Add to sys.modules
sys.modules['google'] = google_module
sys.modules['google.adk'] = google_adk_module
sys.modules['google.adk.tools'] = google_adk_tools_module

print("Mocked google.adk.tools for testing")
