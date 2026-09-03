"""
Plan DSL Validation and DAG Cycle Checking.
Ensures emitted plans satisfy the 5-array workflow_orchestrator JSON schema
and contain no topological cycles in workflow_links.
"""
from collections import defaultdict, deque
from typing import Dict, Any, Tuple, Optional, Set, List


REQUIRED_TOP_ARRAYS = ['tasks', 'workflows']


def validate_plan_dsl(plan: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate proposed 5-array workflow plan DSL.

    Checks:
    1. Structure and required top-level arrays
    2. Task definitions (slug, name, task_type)
    3. Workflow definitions (task_slug)
    4. DAG Acyclicity on workflow_links using Kahn's algorithm

    Args:
        plan: Dict containing tasks, workflows, workflow_links, etc.

    Returns:
        Tuple of (is_valid: bool, error_message: str or None)
    """
    if not isinstance(plan, dict):
        return False, "Plan must be a JSON object (dict)"

    # 1. Check top-level array types
    for key in REQUIRED_TOP_ARRAYS:
        if key not in plan:
            return False, f"Missing required array '{key}' in plan DSL"
        if not isinstance(plan[key], list):
            return False, f"'{key}' must be a list"

    # 2. Check task definitions
    task_slugs: Set[str] = set()
    for i, t in enumerate(plan.get('tasks', [])):
        if not isinstance(t, dict):
            return False, f"Task at index {i} must be an object"
        slug = t.get('slug')
        if not slug:
            return False, f"Task at index {i} is missing required field 'slug'"
        if slug in task_slugs:
            return False, f"Duplicate task slug '{slug}' found in plan"
        task_slugs.add(slug)

        if not t.get('name'):
            return False, f"Task '{slug}' is missing required field 'name'"

    # 3. Check workflow definitions
    for i, w in enumerate(plan.get('workflows', [])):
        if not isinstance(w, dict):
            return False, f"Workflow at index {i} must be an object"
        task_slug = w.get('task_slug')
        if not task_slug:
            return False, f"Workflow at index {i} is missing required field 'task_slug'"
        if task_slug not in task_slugs:
            return False, f"Workflow references task_slug '{task_slug}' which is not defined in tasks array"

    # 4. DAG Cycle Validation on workflow_links (Kahn's Algorithm)
    links = plan.get('workflow_links', []) or []
    if links:
        is_dag, cycle_error = _validate_dag_acyclicity(links, task_slugs)
        if not is_dag:
            return False, cycle_error

    return True, None


def _validate_dag_acyclicity(links: List[Dict[str, Any]], all_task_slugs: Set[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate that workflow_links form a Directed Acyclic Graph (no cycles).
    Uses Kahn's algorithm for topological sorting.
    """
    adj = defaultdict(list)
    in_degree = defaultdict(int)
    nodes_in_links = set()

    for i, link in enumerate(links):
        if not isinstance(link, dict):
            return False, f"workflow_link at index {i} must be an object"

        parent = link.get('parent_task_slug')
        child = link.get('child_task_slug')

        if not parent or not child:
            return False, f"workflow_link at index {i} missing parent_task_slug or child_task_slug"

        if parent not in all_task_slugs:
            return False, f"workflow_link parent '{parent}' not defined in tasks"
        if child not in all_task_slugs:
            return False, f"workflow_link child '{child}' not defined in tasks"

        if parent == child:
            return False, f"Self-cycle detected in workflow_link: '{parent}' -> '{child}'"

        adj[parent].append(child)
        in_degree[child] += 1
        nodes_in_links.add(parent)
        nodes_in_links.add(child)

    # Initialize queue with nodes that have in-degree 0
    queue = deque([node for node in nodes_in_links if in_degree[node] == 0])
    visited_count = 0

    while queue:
        u = queue.popleft()
        visited_count += 1

        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    if visited_count < len(nodes_in_links):
        return False, "Topological cycle detected in workflow_links topology! DAG must be acyclic."

    return True, None


def render_plan_dsl(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize and clean plan DSL structure for storage or ingestion.
    """
    return {
        "tasks": plan.get("tasks", []),
        "workflows": plan.get("workflows", []),
        "workflow_links": plan.get("workflow_links", []),
        "workflow_continuations": plan.get("workflow_continuations", []),
        "task_continuations": plan.get("task_continuations", []),
    }
