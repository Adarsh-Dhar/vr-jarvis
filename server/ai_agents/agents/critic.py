from google.adk.agents import LlmAgent

from ..config import MODEL
from ..tools.graph_tools import get_node, verify_citations

TEMPLATE = '''
You are the Grounding Critic. You check findings against evidence.

Findings to review: {findings}
Evidence: {evidence}

Process:
1. Collect every claim with its node ids
2. Call verify_citations on all node ids
3. Remove or downgrade unsupported claims
4. A claim marked confirmed may rely only on confirmed edges
5. Add no new claims

Return findings with verdict (pass, downgraded, rejected), answer (corrected text),
claims (list with confidence), and changes_made (list of notes).
'''


def make_critic(name: str, review_key: str) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=MODEL,
        include_contents='none',
        description='Checks that every claim in findings is backed by real graph evidence',
        instruction=TEMPLATE.replace('{findings}', '{' + review_key + '}'),
        tools=[verify_citations, get_node],
        output_key='verified_answer',
    )
