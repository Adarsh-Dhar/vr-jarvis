"""Edge explanation endpoint for plain-language explanations."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any


@dataclass
class EdgeExplanation:
    """Plain-language explanation for a graph edge."""
    edge_id: str
    explanation: str
    rule: str
    source_span: Dict[str, int]
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class EdgeExplainer:
    """
    Generate plain-language explanations for graph edges.

    Provides endpoint functionality for VR to show why an edge exists.
    """

    def __init__(self):
        self._rule_templates = {
            'definition': 'This edge shows that {target} is defined at {source} on line {line}.',
            'use': 'This edge shows that {target} uses the value from {source} on line {line}.',
            'call': 'This edge represents a function call from {source} to {target}.',
            'return': 'This edge represents a return from {source} back to {target}.',
            'reaches': 'This edge shows that the value from {source} reaches {target}.',
            'next': 'This edge shows control flow from {source} to {target}.',
            'true': 'This edge is taken when the condition {source} evaluates to True.',
            'false': 'This edge is taken when the condition {source} evaluates to False.',
            'exception': 'This edge represents an exception raised at {source} propagating to {target}.'
        }

    def explain_edge(
        self,
        edge_id: str,
        edge: Dict[str, Any],
        nodes: Dict[str, Dict[str, Any]]
    ) -> EdgeExplanation:
        """
        Generate a plain-language explanation for an edge.

        Returns an EdgeExplanation with rule, source span, and confidence.
        """
        kind = edge.get('kind', 'unknown')
        source_id = edge.get('source')
        target_id = edge.get('target')

        source_node = nodes.get(source_id, {})
        target_node = nodes.get(target_id, {})

        # Select rule template
        rule = kind
        template = self._rule_templates.get(kind, 'This edge connects {source} to {target}.')

        # Fill in template
        source_label = source_node.get('label', source_id)
        target_label = target_node.get('label', target_id)
        source_line = source_node.get('start_line', 0)

        explanation = template.format(
            source=source_label,
            target=target_label,
            line=source_line
        )

        # Extract source span
        source_span = {
            'start_line': source_node.get('start_line', 0),
            'start_col': source_node.get('start_col', 0),
            'end_line': source_node.get('end_line', 0),
            'end_col': source_node.get('end_col', 0)
        }

        # Determine confidence
        confidence = 0.9 if edge.get('subkind') == 'must_reach' else 0.7

        return EdgeExplanation(
            edge_id=edge_id,
            explanation=explanation,
            rule=rule,
            source_span=source_span,
            confidence=confidence,
            metadata=edge.get('evidence', {})
        )
