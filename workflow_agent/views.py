"""
HTTP Views for Workflow Agent API.
Provides endpoints for starting runs, inspecting transcripts, submitting HITL answers,
and approving plans into materialized workflow_orchestrator Task and Workflow rows.
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction

from .models import AgentRun, AgentMessage, ManualStep
from .agent_loop import start_agent_plan, resume_agent_plan
from .dsl import validate_plan_dsl, render_plan_dsl

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def start_agent_run_view(request):
    """
    POST /agent/run/
    Start a new agent planning run for an organization.
    Body JSON: {"organization_id": 1, "prompt": "...", "model": "..."}
    """
    try:
        data = json.loads(request.body) if request.body else {}
        organization_id = data.get("organization_id")
        prompt = data.get("prompt")
        model = data.get("model", "")

        if not organization_id or not prompt:
            return JsonResponse({"error": "organization_id and prompt are required"}, status=400)

        run = start_agent_plan(organization_id, prompt, model)

        return JsonResponse({
            "agent_run_id": run.id,
            "organization_id": run.organization_id,
            "status": run.status,
            "prompt": run.prompt,
            "model": run.model,
            "created_at": run.created_at.isoformat()
        }, status=201)
    except Exception as e:
        logger.error(f"Error in start_agent_run_view: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_agent_run_view(request, run_id):
    """
    GET /agent/run/<run_id>/
    Get AgentRun status, proposed plan_json, message transcript, and pending manual steps.
    """
    try:
        run = AgentRun.objects.filter(id=run_id).first()
        if not run:
            return JsonResponse({"error": "AgentRun not found"}, status=404)

        msgs = list(run.messages.all().order_by('sequence').values(
            'sequence', 'role', 'tool_name', 'tool_args', 'content', 'token_usage'
        ))

        manual_steps = list(ManualStep.objects.filter(agent_run=run).values(
            'id', 'description', 'status', 'created_at'
        ))

        return JsonResponse({
            "agent_run_id": run.id,
            "organization_id": run.organization_id,
            "status": run.status,
            "prompt": run.prompt,
            "plan_json": run.plan_json,
            "model": run.model,
            "iteration_count": run.iteration_count,
            "messages": msgs,
            "manual_steps": manual_steps,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat()
        }, status=200)
    except Exception as e:
        logger.error(f"Error in get_agent_run_view: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def answer_agent_run_view(request, run_id):
    """
    POST /agent/run/<run_id>/message/
    Answer an ask_question or submit human input for an AgentRun.
    Body JSON: {"user_input": "..."}
    """
    try:
        run = AgentRun.objects.filter(id=run_id).first()
        if not run:
            return JsonResponse({"error": "AgentRun not found"}, status=404)

        data = json.loads(request.body) if request.body else {}
        user_input = data.get("user_input")

        if not user_input:
            return JsonResponse({"error": "user_input is required"}, status=400)

        updated_run = resume_agent_plan(run_id, user_input)

        return JsonResponse({
            "agent_run_id": updated_run.id,
            "status": updated_run.status,
            "message": "User answer submitted; planner resumed."
        }, status=200)
    except Exception as e:
        logger.error(f"Error in answer_agent_run_view: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def approve_agent_plan_view(request, run_id):
    """
    POST /agent/run/<run_id>/approve/
    Approve proposed plan_json and materialize real Task and Workflow DB rows in workflow_orchestrator.
    """
    try:
        run = AgentRun.objects.filter(id=run_id).first()
        if not run:
            return JsonResponse({"error": "AgentRun not found"}, status=404)

        if not run.plan_json or not isinstance(run.plan_json, dict):
            return JsonResponse({"error": "No valid plan_json available on this AgentRun to approve"}, status=400)

        is_valid, err = validate_plan_dsl(run.plan_json)
        if not is_valid:
            return JsonResponse({"error": f"Plan DSL validation failed: {err}"}, status=400)

        from workflow_orchestrator.conf import get_organization_model
        Organization = get_organization_model()
        org = Organization.objects.filter(id=run.organization_id).first()

        summary = _materialize_plan_dsl(run.plan_json, org)

        run.status = AgentRun.STATUS_SUCCEEDED
        run.save(update_fields=['status'])

        return JsonResponse({
            "status": "approved",
            "agent_run_id": run.id,
            "organization_id": run.organization_id,
            "materialized": summary
        }, status=200)
    except Exception as e:
        logger.error(f"Error in approve_agent_plan_view: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


def _materialize_plan_dsl(plan: dict, tenant) -> dict:
    """
    Materialize 5-array JSON plan into Task, Workflow, WorkflowContinuation, and TaskContinuation rows.
    Uses workflow_orchestrator models directly.
    """
    from workflow_orchestrator.models import (
        Task, Attribute, TaskAttribute, Workflow, WorkflowContinuation, TaskContinuation
    )

    tasks_by_slug = {}
    tasks_created = 0
    workflows_created = 0
    links_created = 0
    conts_created = 0

    with transaction.atomic():
        # 1. Materialize Tasks
        for tdef in plan.get('tasks', []):
            slug = tdef['slug']
            task, created = Task.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': tdef.get('name', slug),
                    'task_type': tdef.get('task_type', Task.TASK_TYPE_HTTP),
                    'max_iterations': tdef.get('max_iterations', 1000),
                    'description': tdef.get('description', '')
                }
            )
            if created:
                tasks_created += 1
            tasks_by_slug[slug] = task

            for attr_name, attr_val in tdef.get('attributes', {}).items():
                attr_obj = Attribute.objects.filter(name=attr_name, value=attr_val).first()
                if not attr_obj:
                    attr_obj = Attribute.objects.create(name=attr_name, value=attr_val)
                TaskAttribute.objects.get_or_create(task=task, attribute=attr_obj)

        # 2. Materialize Workflows
        workflows_by_slug = {}
        for wf_def in plan.get('workflows', []):
            task_slug = wf_def['task_slug']
            task = tasks_by_slug.get(task_slug)
            if not task:
                continue

            workflow, created = Workflow.objects.get_or_create(
                organization=tenant,
                task=task,
                defaults={'priority_override': wf_def.get('priority_override', 2)}
            )
            if created:
                workflows_created += 1
            workflows_by_slug[task_slug] = workflow

        # 3. Materialize Workflow Links (DAG Edges)
        for link in plan.get('workflow_links', []):
            parent_wf = workflows_by_slug.get(link['parent_task_slug'])
            child_wf = workflows_by_slug.get(link['child_task_slug'])
            if parent_wf and child_wf:
                child_wf.mapped_by.add(parent_wf)
                links_created += 1

        # 4. Materialize WorkflowContinuations (Gatekeepers)
        for cont in plan.get('workflow_continuations', []):
            wf_slug = cont['workflow_task_slug']
            gk_slug = cont.get('gatekeeper_task_slug', wf_slug)
            wf = workflows_by_slug.get(wf_slug)
            gk_task = tasks_by_slug.get(gk_slug)
            if wf and gk_task:
                WorkflowContinuation.objects.update_or_create(
                    workflow=wf,
                    task=gk_task,
                    defaults={'priority': cont.get('priority', 1), 'condition': cont.get('condition', 'true')}
                )
                conts_created += 1

        # 5. Materialize TaskContinuations (Retries / Loops)
        for tcont in plan.get('task_continuations', []):
            primary_task = tasks_by_slug.get(tcont['primary_task_slug'])
            continuation_task = tasks_by_slug.get(tcont['continuation_task_slug'])
            if primary_task and continuation_task:
                TaskContinuation.objects.update_or_create(
                    primary_task=primary_task,
                    continuation_task=continuation_task,
                    defaults={'priority': tcont.get('priority', 1), 'condition': tcont.get('condition', 'true')}
                )

    return {
        "tasks_created": tasks_created,
        "workflows_created": workflows_created,
        "links_created": links_created,
        "gatekeepers_created": conts_created
    }
