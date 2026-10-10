"""One action map for MCP discovery and dispatch; namespace checks remain in each service."""
OVERRIDES = {
    'air_receive_builder_handoff': 'receive', 'air_revoke_builder_receipt': 'receive',
    'air_package_publish': 'publish', 'air_package_revoke': 'publish',
    'air_capacity_publish': 'capacity', 'air_admission_review': 'review',
    'air_admission_revoke_review': 'review', 'air_closure_review': 'review',
    'air_closure_revoke_review': 'review', 'air_admission_admit': 'admit',
    'air_admission_release': 'admit', 'air_renewal_renew': 'admit', 'air_closure_close': 'admit',
    'air_admission_activate': 'activate', 'air_closure_propose': 'activate',
    # These are owned pure-calculation jobs, not permission to write architecture or execute a system.
    'air_submit_job': 'read', 'air_cancel_job': 'read',
}


def actions(principal, policy):
    from air.access import ACTIONS
    candidates = {'*'} if policy.document is None else {
        namespace for action, grants in policy.document['subjects'].get(principal['subject'], {}).items()
        if action in ACTIONS for namespace in grants}
    return [action for action in ACTIONS if any(policy.allows(principal, action, namespace) for namespace in candidates)]


def allowed_tools(grants):
    from air.mcp import TOOLS
    return {name: tool for name, tool in TOOLS.items() if name in ('air_whoami', 'air_capabilities') or
            OVERRIDES.get(name, 'read' if tool[4] else 'write') in grants}
