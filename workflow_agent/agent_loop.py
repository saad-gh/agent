"""
Agent Planner Loop Controller.
Manages AgentRun lifecycle, creates messages, and triggers workflow_orchestrator
traverser execution for planner workflow runs.
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from asgiref.sync import sync_to_async

from .models import AgentRun, AgentMessage
from .planner_topology import ensure_planner_workflow_for_org

logger = logging.getLogger(__name__)


def start_agent_plan(organization_id: int, prompt: str, model: str = "") -> AgentRun:
    """
    Start a new agent planning run for an organization synchronously/async.

    Args:
        organization_id: ID of the organization
        prompt: User's goal/instruction string
        model: Optional model override string

    Returns:
        Created and executed AgentRun instance
    """
    from workflow_orchestrator.conf import get_organization_model
    Organization = get_organization_model()

    org = Organization.objects.get(id=organization_id)

    # 1. Ensure 2-node planner workflow graph exists
    wf_plan, wf_tool = ensure_planner_workflow_for_org(org)

    # 2. Create AgentRun record
    agent_run = AgentRun.objects.create(
        organization_id=org.id,
        prompt=prompt,
        model=model or "",
        status=AgentRun.STATUS_PLANNING
    )

    # 3. Add initial user message
    AgentMessage.objects.create(
        agent_run=agent_run,
        role=AgentMessage.ROLE_USER,
        content=prompt,
        sequence=1
    )

    # 4. Trigger workflow run via asyncio
    asyncio.run(_run_planner_traversal(org.id, wf_plan.id, agent_run))

    agent_run.refresh_from_db()
    return agent_run


def resume_agent_plan(agent_run_id: int, user_input: Optional[str] = None) -> AgentRun:
    """
    Resume an agent planning run (e.g. after answering ask_question or providing manual input).

    Args:
        agent_run_id: ID of the AgentRun
        user_input: Optional answer or input string from user

    Returns:
        Updated AgentRun instance
    """
    agent_run = AgentRun.objects.get(id=agent_run_id)

    if user_input:
        seq = agent_run.messages.count() + 1
        AgentMessage.objects.create(
            agent_run=agent_run,
            role=AgentMessage.ROLE_USER,
            content=user_input,
            sequence=seq
        )
        agent_run.status = AgentRun.STATUS_PLANNING
        agent_run.save(update_fields=['status'])

    from workflow_orchestrator.models import Workflow, Task
    wf_plan = Workflow.objects.filter(
        organization_id=agent_run.organization_id,
        task__slug='llm-plan'
    ).first()

    if not wf_plan:
        from workflow_orchestrator.conf import get_organization_model
        Organization = get_organization_model()
        org = Organization.objects.get(id=agent_run.organization_id)
        wf_plan, _ = ensure_planner_workflow_for_org(org)

    asyncio.run(_run_planner_traversal(agent_run.organization_id, wf_plan.id, agent_run))

    agent_run.refresh_from_db()
    return agent_run


async def _run_planner_traversal(organization_id: int, workflow_id: int, agent_run: AgentRun):
    """
    Execute traverser traversal for planner workflow with populated context messages.
    """
    from workflow_orchestrator.traverser import WorkflowTraverser
    from workflow_orchestrator.graph import WorkflowGraph
    from workflow_orchestrator.execution_context import ExecutionContext
    from workflow_orchestrator.telemetry import TelemetryLogger
    from workflow_orchestrator.conf import get_organization_model

    Organization = get_organization_model()
    org = await Organization.objects.aget(id=organization_id)

    import uuid
    run_id = str(uuid.uuid4())
    context = ExecutionContext(run_id, organization_id)
    setattr(context, 'agent_run_id', agent_run.id)

    # Reconstruct message history from AgentMessage DB records
    msgs = await sync_to_async(list)(agent_run.messages.all().order_by('sequence'))
    messages_payload = []
    for msg in msgs:
        m_dict = {'role': msg.role, 'content': msg.content}
        if msg.tool_name:
            m_dict['name'] = msg.tool_name
        if msg.tool_args:
            m_dict['tool_calls'] = [{'name': msg.tool_name, 'args': msg.tool_args}]
        messages_payload.append(m_dict)

    # Set task_params for llm-plan node
    context.update_task_params('llm-plan', {
        'messages': messages_payload,
        'agent_run_id': agent_run.id
    })

    graph = WorkflowGraph(org)
    await graph.build(workflow_id=workflow_id)

    logger = TelemetryLogger(run_id, organization_id)
    traverser = WorkflowTraverser(graph, context, logger)

    root_nodes = graph.get_root_nodes()
    await asyncio.gather(*(traverser.traverse(node) for node in root_nodes))
