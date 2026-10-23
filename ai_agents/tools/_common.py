def record_evidence(tool_context, node_ids):
    '''Append node ids to state['evidence'] without duplicates. Reassigns so ADK sees the change.'''
    seen = list(tool_context.state.get('evidence', []))
    for node_id in node_ids:
        if node_id not in seen:
            seen.append(node_id)
    tool_context.state['evidence'] = seen
