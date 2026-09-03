"""
LLM Executor for workflow_agent.
Subclasses BaseExecutor from workflow_orchestrator.executors.
"""
import logging
from asgiref.sync import sync_to_async
from workflow_orchestrator.executors import BaseExecutor
from workflow_orchestrator.execution_context import ExecutionContext

from . import llm_client
from .cost import estimate_cost

logger = logging.getLogger(__name__)


class LLMExecutor(BaseExecutor):
    """
    Executor for 'llm' task_type nodes.
    Performs provider-agnostic inference, logs usage, and estimates cost.
    """

    async def execute(self, context: ExecutionContext, node):
        attributes = await self.get_and_render_attributes(context, node)

        # 1. Resolve model Resource
        model_resource = await self._resolve_model_resource(context, node, attributes)

        # 2. Resolve Credential
        cred_obj = await sync_to_async(node.workflow.get_primary_credential)() if hasattr(node, 'workflow') and node.workflow else None

        # 3. Build messages list
        messages = self._build_messages(context, node, attributes)

        # 4. Resolve Tools & Response Format
        tools = self._resolve_tools(attributes)
        response_format = attributes.get('response_format')

        # 5. Execute LLM completion
        llm_result = await llm_client.complete(
            model_resource=model_resource,
            messages=messages,
            response_format=response_format,
            tools=tools,
            credential=cred_obj
        )

        prompt_tokens = llm_result.get('prompt_tokens', 0)
        completion_tokens = llm_result.get('completion_tokens', 0)

        # 6. Estimate Cost
        cost = estimate_cost(model_resource, prompt_tokens, completion_tokens)

        # 7. Log AI Usage to DB
        await self._log_ai_usage(context, node, model_resource, cred_obj, messages, llm_result)

        # 8. Return standardized task result
        return {
            "status": "success",
            "content": llm_result.get("content", ""),
            "tool_calls": llm_result.get("tool_calls", []),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "stop_reason": llm_result.get("stop_reason", "end_turn"),
            "cost": cost,
            # Format first tool call for task continuation conditions
            "tool": llm_result["tool_calls"][0]["name"] if llm_result.get("tool_calls") else None,
            "tool_args": llm_result["tool_calls"][0]["args"] if llm_result.get("tool_calls") else {},
        }

    @sync_to_async
    def _resolve_model_resource(self, context: ExecutionContext, node, attributes: dict):
        """
        Resolve the model Resource using node.task.resource, ModelPreference, or attribute override.
        """
        # A. Direct resource on task
        if hasattr(node.task, 'resource') and node.task.resource:
            return node.task.resource

        # B. Check ModelPreference by reasoning_tier
        reasoning_tier = attributes.get('reasoning_tier') or 'plan'
        if context.org_id:
            from .models import ModelPreference
            pref = ModelPreference.objects.filter(
                organization_id=context.org_id,
                reasoning_tier=reasoning_tier
            ).select_related('resource', 'resource__service').first()
            if pref and pref.resource:
                return pref.resource

        # C. Check Resource model by attribute resource_id/resource_name
        resource_id = attributes.get('model_resource_id') or attributes.get('resource_id')
        if resource_id:
            from workflow_orchestrator.conf import get_resource_model
            Resource = get_resource_model()
            res = Resource.objects.filter(pk=resource_id).select_related('service').first()
            if res:
                return res

        # D. Return default fallback config dict
        return {
            "name": attributes.get("model", "default-llm-model"),
            "metadata": {
                "provider": attributes.get("provider", "mock"),
                "model_id": attributes.get("model", "default-llm-model"),
                "temperature": attributes.get("temperature", 0.0),
                "max_tokens": attributes.get("max_tokens", 4096),
                "input_price": attributes.get("input_price", 0.0),
                "output_price": attributes.get("output_price", 0.0),
            }
        }

    def _build_messages(self, context: ExecutionContext, node, attributes: dict) -> list:
        """
        Build message history from context parameters and task attributes.
        """
        messages = []

        # System prompt if set in attributes
        system_prompt = attributes.get('system_prompt')
        if system_prompt:
            messages.append({'role': 'system', 'content': str(system_prompt)})

        # Check messages in task_params or context results
        task_params = context.get_task_params(node.slug)
        history = task_params.get('messages') or attributes.get('messages') or []

        if isinstance(history, list):
            for msg in history:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    messages.append(msg)

        # If no history provided, use prompt from attributes or parent payload
        if not history and attributes.get('prompt'):
            messages.append({'role': 'user', 'content': str(attributes['prompt'])})

        return messages

    def _resolve_tools(self, attributes: dict) -> list:
        """
        Resolve tools if task attributes request tools.
        """
        if not attributes.get('tools'):
            return []

        try:
            from .tools import get_tool_definitions
            return get_tool_definitions()
        except ImportError:
            return []

    @sync_to_async(thread_sensitive=True)
    def _log_ai_usage(self, context: ExecutionContext, node, model_resource, credential, messages, llm_result):
        """
        Log token usage to AiUsageLog table.
        """
        try:
            from .models import AiUsageLog
            from workflow_orchestrator.conf import get_service_model

            service_id = None
            if hasattr(model_resource, 'service_id') and model_resource.service_id:
                service_id = model_resource.service_id
            elif hasattr(model_resource, 'service') and model_resource.service:
                service_id = model_resource.service.id
            else:
                Service = get_service_model()
                srv = Service.objects.filter(name__iexact='llm').first()
                if srv:
                    service_id = srv.id

            if not service_id:
                # If no service available, skip DB log
                return

            user_prompt = messages[-1].get('content', '') if messages else ''
            model_name = getattr(model_resource, 'name', '') or llm_result.get('ai_model', 'llm-model')

            agent_run_id = getattr(context, 'agent_run_id', None) or context.get_task_params(node.slug).get('agent_run_id')

            AiUsageLog.objects.create(
                organization_id=context.org_id,
                service_id=service_id,
                credential_id=credential.id if credential else None,
                agent_run_id=agent_run_id,
                ai_model=str(model_name)[:100],
                prompt_tokens=llm_result.get('prompt_tokens', 0),
                completion_tokens=llm_result.get('completion_tokens', 0),
                user_prompt=str(user_prompt)[:1000],
                success=True
            )
        except Exception as e:
            logger.warning(f"Could not log AiUsageLog: {e}")


class GeneratedPythonExecutor(BaseExecutor):
    """
    Executor for 'generated_python' task_type nodes.
    Executes approved GeneratedFunction by slug in a safe subprocess pool.
    """

    async def execute(self, context: ExecutionContext, node):
        attributes = await self.get_and_render_attributes(context, node)
        func_slug = attributes.get('func_slug') or attributes.get('function_slug') or node.task.slug
        kwargs = attributes.get('kwargs') or attributes.get('function_kwargs') or {}

        from .run_safe import run_generated_function
        timeout = int(attributes.get('timeout', 5))

        res = await sync_to_async(run_generated_function, thread_sensitive=False)(
            slug=func_slug, kwargs=kwargs, timeout=timeout
        )
        return res
