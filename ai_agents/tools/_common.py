MAX_EVIDENCE = 500


def record_evidence(tool_context, node_ids):
    '''Append node ids to state['evidence'] without duplicates, keeping only the most recent MAX_EVIDENCE.
    Reassigns so ADK sees the change.'''
    seen = list(tool_context.state.get('evidence', []))
    for node_id in node_ids:
        if node_id in seen:
            seen.remove(node_id)
        seen.append(node_id)
    tool_context.state['evidence'] = seen[-MAX_EVIDENCE:]
