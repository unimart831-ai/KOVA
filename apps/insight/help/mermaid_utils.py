"""Sanitize Mermaid flowchart diagrams for Mermaid 10.x."""

from __future__ import annotations

import re

# Label text that must be wrapped in double quotes for Mermaid 10 flowcharts.
_SPECIAL_LABEL_CHARS = re.compile(r'[&/→—·?:|<>()]')

# Parallelogram nodes: id[/label/] — inner slashes break parsing.
_PARALLELOGRAM_NODE = re.compile(r'(\b[\w]+)\[/([^\]]+)\]')

# Square, rounded, cylinder, and stadium node labels: id[label], id(label), id[(label)], id([label]).
_BRACKET_NODE = re.compile(
    r'(\b[\w]+)(\[\[|\[\(|\[|\(\()([^"\]\)]+)(\]\]|\]\)|\)|\)\])'
)

# Diamond decision nodes: id{label}
_DIAMOND_NODE = re.compile(r'(\b[\w]+)\{([^}"\}]+)\}')

# Edge labels: -->|label| or -.->|label|
_EDGE_LABEL = re.compile(r'(\|)([^"|]+\|)')


def _escape_label(label: str) -> str:
    return label.replace('"', "#quot;")


def _needs_quotes(label: str) -> bool:
    stripped = label.strip()
    if stripped.startswith('"') and stripped.endswith('"'):
        return False
    return bool(_SPECIAL_LABEL_CHARS.search(label) or " / " in label)


def _quote_label(label: str) -> str:
    stripped = label.strip()
    if stripped.startswith('"') and stripped.endswith('"'):
        return label
    return f'"{_escape_label(label.strip())}"'


def sanitize_mermaid(diagram: str) -> str:
    """Return diagram text safe for Mermaid 10.x rendering."""
    text = diagram.strip()

    def _parallelogram_to_quoted(match: re.Match[str]) -> str:
        node_id, label = match.group(1), match.group(2)
        if not label.startswith("/"):
            label = f"/{label}"
        return f"{node_id}[{_quote_label(label)}]"

    text = _PARALLELOGRAM_NODE.sub(_parallelogram_to_quoted, text)

    def _quote_bracket_node(match: re.Match[str]) -> str:
        node_id, open_br, label, close_br = match.groups()
        if _needs_quotes(label):
            return f"{node_id}{open_br}{_quote_label(label)}{close_br}"
        return match.group(0)

    text = _BRACKET_NODE.sub(_quote_bracket_node, text)

    def _quote_diamond_node(match: re.Match[str]) -> str:
        node_id, label = match.group(1), match.group(2)
        if _needs_quotes(label):
            return f"{node_id}{{{_quote_label(label)}}}"
        return match.group(0)

    text = _DIAMOND_NODE.sub(_quote_diamond_node, text)

    def _quote_edge_label(match: re.Match[str]) -> str:
        label = match.group(2)[:-1]  # drop trailing |
        if _needs_quotes(label):
            return f'|{_quote_label(label)}|'
        return match.group(0)

    text = _EDGE_LABEL.sub(_quote_edge_label, text)

    return text
