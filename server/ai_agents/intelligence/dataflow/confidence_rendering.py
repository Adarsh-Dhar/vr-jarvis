"""Confidence rendering for graph visualization."""
from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Any


@dataclass
class EdgeStyle:
    """Visual style for graph edges based on confidence."""
    line_style: str  # 'solid', 'dashed', 'dotted'
    line_width: float
    color: str
    opacity: float


class ConfidenceRenderer:
    """
    Map confidence levels to visual styles for graph rendering.

    Styles:
    - must_reach: solid, thick, high opacity
    - may_reach: solid, medium, medium opacity
    - possible: dashed, thin, low opacity
    - unknown: dotted, thin, low opacity
    """

    def __init__(self):
        self._style_map = {
            'must_reach': EdgeStyle(
                line_style='solid',
                line_width=2.0,
                color='#00ff00',  # Green
                opacity=1.0
            ),
            'may_reach': EdgeStyle(
                line_style='solid',
                line_width=1.5,
                color='#0088ff',  # Blue
                opacity=0.8
            ),
            'possible': EdgeStyle(
                line_style='dashed',
                line_width=1.0,
                color='#ff8800',  # Orange
                opacity=0.6
            ),
            'unknown': EdgeStyle(
                line_style='dotted',
                line_width=0.5,
                color='#888888',  # Gray
                opacity=0.4
            )
        }

    def get_style(self, confidence: str) -> EdgeStyle:
        """Get the visual style for a confidence level."""
        return self._style_map.get(confidence, self._style_map['unknown'])

    def render_edges(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply confidence styling to a list of edges.

        Returns edges with added visual style metadata.
        """
        styled_edges = []

        for edge in edges:
            confidence = edge.get('subkind', 'unknown')  # subkind holds confidence
            style = self.get_style(confidence)

            styled_edge = edge.copy()
            styled_edge['visual_style'] = {
                'line_style': style.line_style,
                'line_width': style.line_width,
                'color': style.color,
                'opacity': style.opacity
            }
            styled_edges.append(styled_edge)

        return styled_edges
