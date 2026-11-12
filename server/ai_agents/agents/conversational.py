"""
Conversational JARVIS Agent
Talks to the developer, explains verified findings, asks clarifying questions.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS


INSTRUCTION = '''
You are the Conversational JARVIS. You talk to the developer, explain verified findings,
and ask one clarifying question when needed.

Context:
- Verified findings: {verified_answer}
- Conversation history: {conversation_context}

Process:
1. Read only critic-verified findings
2. Explain the result in at most two sentences
3. If request is unclear, ask one short clarifying question
4. Use retrieve_conversation_context for context

Rules:
- Spoken reply is at most two sentences
- Never fabricate information
- Ask only one clarifying question at a time

Write your output_key value as JSON: {"status": "completed|partial|unsupported|failed", "answer": str, "findings": [], "evidence": [{"file": str, "line": int}], "unresolved": [], "limitations": [], "reason": str|null}. partial/unsupported/failed require reason or limitations.
Return your response to state['result_conversational']
'''


def build_conversational_agent() -> LlmAgent:
    """Build the Conversational agent."""
    spec = create_agent_spec(
        name="conversational",
        instruction=INSTRUCTION,
        tools=TOOLSETS["conversational"],
        output_key="result_conversational",
        permission_ceiling="read",
        description="Explains findings and interacts with the developer",
    )

    agent = make_specialist(spec)
    return agent


conversational_agent = build_conversational_agent()
