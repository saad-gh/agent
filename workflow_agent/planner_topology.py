"""
Standard Planner Loop Workflow Topology.
Expresses the agent planner's while(true) inference-and-tool loop
using workflow_orchestrator TaskNode, TaskContinuation, and Workflow models.
"""
import logging
from typing import Tuple, Any
from workflow_orchestrator.models import Task, Attribute, TaskAttribute, Workflow, TaskContinuation

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are an AI workflow architect. Your goal is to analyze the user's prompt and generate a complete, valid 5-array workflow plan in declarative JSON.
You can call tools to list services, read API documentation, web search, or declare manual steps/helpers.
When you have assembled the required tasks and topology, call the tool 'finalize_plan' with the complete plan dict.
Never ask vague questions; finalize the plan as soon as sufficient information is gathered."""


def ensure_planner_workflow_for_org(organization) -> Tuple:
    """
    Build or ensure the standard 2-node planner loop workflow for organization.

    Nodes:
    1. llm-plan (task_type=llm): Inference node with tools enabled and reasoning_tier=plan.
    2. execute-tool (task_type=python): Runs workflow_agent.tools.execute_tool_callable.

    Loop continuations:
    - llm-plan -> execute-tool (if result.tool is present and != 'finalize_plan')
    - execute-tool -> llm-plan (true)
    """
    # 1. Create or get tasks
    task_plan, _ = Task.objects.update_or_create(
        slug="llm-plan",
        defaults={
            "name": "Agent LLM Planner Inference",
            "task_type": "llm",
            "max_iterations": 30,
            "description": "Planner inference turn that produces tool calls or final plan"
        }
    )
    _set_task_attribute(task_plan, "reasoning_tier", "plan")
    _set_task_attribute(task_plan, "tools", True)
    _set_task_attribute(task_plan, "system_prompt", PLANNER_SYSTEM_PROMPT)

    task_tool, _ = Task.objects.update_or_create(
        slug="execute-tool",
        defaults={
            "name": "Agent Execute Tool Dispatcher",
            "task_type": "python",
            "max_iterations": 30,
            "description": "Executes requested agent tool call and appends result to message history"
        }
    )
    _set_task_attribute(task_tool, "python_callable", "workflow_agent.tools.execute_tool_callable")

    # 2. Create workflows bound to organization
    wf_plan, _ = Workflow.objects.get_or_create(
        organization=organization,
        task=task_plan,
        defaults={"priority_override": 1}
    )

    wf_tool, _ = Workflow.objects.get_or_create(
        organization=organization,
        task=task_tool,
        defaults={"priority_override": 1}
    )

    # 3. DAG Link: execute-tool runs after llm-plan
    wf_tool.mapped_by.add(wf_plan)

    # 4. Loop continuations
    # llm-plan -> execute-tool when tool call requested and not finalize_plan
    TaskContinuation.objects.update_or_create(
        primary_task=task_plan,
        continuation_task=task_tool,
        defaults={
            "priority": 1,
            "condition": "{{ result.tool is defined and result.tool is not none and result.tool != 'finalize_plan' }}"
        }
    )

    # execute-tool -> llm-plan (loop back to next inference turn)
    TaskContinuation.objects.update_or_create(
        primary_task=task_tool,
        continuation_task=task_plan,
        defaults={
            "priority": 1,
            "condition": "true"
        }
    )

    return wf_plan, wf_tool


def _set_task_attribute(task_obj: Task, name: str, value: Any):
    """Helper to set a TaskAttribute on a Task instance."""
    attr_obj, _ = Attribute.objects.get_or_create(name=name, value=value)
    TaskAttribute.objects.get_or_create(task=task_obj, attribute=attr_obj)
