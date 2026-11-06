# Function Call Graph Skill

## Overview
This skill builds and analyzes function call graphs with evidence-based semantic
resolution. Every call site is recorded with its source location, resolution
status and the evidence behind the decision.

## Resolution semantics (must be respected when reporting)
- `static_resolved`: exact target proven statically -> confirmed `calls` edge.
- `polymorphic`: target set proven, dispatch target not -> `may_call` edges only.
- `ambiguous`: multiple candidates, cannot be distinguished -> `may_call` edges only.
- `unresolved` / `dynamic` / `external`: NO internal edge is created. Report the
  call site and its classification; never invent a destination.

When citing relationships, always state the resolution status, the call-site
id (`file:line:col`) and the resolution method. Possible targets must be
described as possible, never as confirmed.

## Capabilities
- `resolve_calls`: Resolve function calls with semantic analysis
- `callers`: Find callers of a function (confirmed and possible separated)
- `callees`: Find callees of a function (confirmed and possible separated)
- `trace_chain`: Trace call chains preserving per-edge confidence
- `visualize`: Visualize call graphs in VR (confirmed=solid, possible=dashed,
  ambiguous=dotted)

## Tools Used
- `find_callers`: confirmed/possible callers of a function
- `find_callees`: confirmed/possible callees of a function
- `get_call_sites`: recorded call sites owned by a function
- `explain_call_resolution`: evidence-backed explanation of one call site
- `trace_call_chain`: trace call chains
- `build_call_graph`: call-graph subgraph for a scope
- `visualize_call_graph`: emit `show_graph` to the VR scene

## Supported languages
- `python`: full semantic resolution (imports, aliases, relative imports,
  `self`/`cls`, inheritance, `super()`, receiver type inference, dynamic and
  external classification).
- Other languages with tree-sitter grammars (javascript, typescript, go, rust,
  java, csharp, cpp) are indexed structurally; their call sites are recorded as
  `unresolved` with `no_semantic_resolver` until a language resolver exists.

## Permissions Required
- `repository.read`: Read access to repository files
- `graph.read`: Read access to graph data

## Status
- Current status: `implemented` (Python semantic resolution; schema v3)
