"""Authoritative delegation contract.

TOOLSETS in toolsets.py remains the source of truth for tools an agent can
execute directly. This module only records delegated routes that TOOLSETS
cannot express: tools/pipelines an agent may reference in instructions but
must reach through a named child pipeline rather than binding directly.
"""

# Tools an agent may mention/delegate but must NOT bind directly. The value
# is the pipeline (ADK agent name in the live tree) that must contain a
# descendant specialist which directly owns the tool.
DELEGATED_TOOL_ROUTES = {
    "jarvis_orchestrator": {
        "start_runtime_trace": "testing_verification_pipeline",
        "get_runtime_trace": "testing_verification_pipeline",
        "stop_runtime_trace": "testing_verification_pipeline",
    },
}

# Optional explicit route metadata for non-tool delegation.
DELEGATED_PIPELINE_ROUTES = {
    "jarvis_orchestrator": {
        "runtime_trace": "testing_verification_pipeline",
    },
}
