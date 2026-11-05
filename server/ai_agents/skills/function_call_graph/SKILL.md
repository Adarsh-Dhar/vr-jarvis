# Function Call Graph Skill

## Overview
This skill builds and analyzes function call graphs with semantic resolution capabilities, including import resolution, inheritance tracking, and polymorphic dispatch detection.

## Capabilities
- `resolve_calls`: Resolve function calls with semantic analysis
- `callers`: Find callers of a function
- `callees`: Find callees of a function
- `trace_chain`: Trace call chains
- `visualize`: Visualize call graphs

## Tools Used
- `find_callers`: Find callers of a function
- `find_callees`: Find callees of a function
- `trace_call_chain`: Trace call chains
- `build_call_graph`: Build call graph
- `visualize_call_graph`: Visualize call graph

## Permissions Required
- `repository.read`: Read access to repository files
- `graph.read`: Read access to graph data

## Resolution Features
- Import and alias resolution
- Self and inheritance resolution
- Typed receiver and polymorphic dispatch
- Ambiguous and external call classification

## Status
- Current status: `implemented`
- Tests: Required but not yet written
- Note: Status will change to `validated` after ground-truth tests pass in M10
