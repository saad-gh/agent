"""
Whitelisted Tool Registry and Handler Dispatcher for Agentic Planner.
"""
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


TOOL_DEFINITIONS = [
    {
        "name": "list_services",
        "description": "List all available SaaS services/integrations configured in the platform.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_service_resources",
        "description": "List all API resources/endpoints for a specific SaaS service.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Name or slug of the service (e.g., 'shopify', 'xero')"}
            },
            "required": ["service_name"]
        }
    },
    {
        "name": "read_api_docs",
        "description": "Read documentation content for a specific SaaS service API endpoint.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Name of the service"},
                "query": {"type": "string", "description": "Search term or endpoint path"}
            },
            "required": ["service_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for public API documentation or endpoint specifications.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for API docs"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "web_fetch",
        "description": "Fetch and extract text content from a public API documentation URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Absolute URL to fetch"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "ingest_docs",
        "description": "Ingest fetched API documentation into the system corpus for a service.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Target service name"},
                "source_url": {"type": "string", "description": "URL documentation was sourced from"},
                "content": {"type": "string", "description": "Parsed documentation text or OpenAPI spec"}
            },
            "required": ["service_name", "content"]
        }
    },
    {
        "name": "recall_context",
        "description": "Recall past conversation messages, decisions, or documentation snippets via vector search.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query string for semantic context search"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "define_jinja_helper",
        "description": "Define a custom Jinja2 template helper function (creates a draft for human approval).",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the Jinja function"},
                "source": {"type": "string", "description": "Python source code defining the function"}
            },
            "required": ["name", "source"]
        }
    },
    {
        "name": "define_python_function",
        "description": "Define a custom Python function for a python task (creates a draft for human approval).",
        "parameters": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Unique slug for the function"},
                "source": {"type": "string", "description": "Python function source code"},
                "signature": {"type": "object", "description": "Optional parameters and types signature"}
            },
            "required": ["slug", "source"]
        }
    },
    {
        "name": "ask_question",
        "description": "Ask the human user a clarifying question before finalizing the workflow plan.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question text to ask the user"},
                "options": {"type": "array", "items": {"type": "string"}, "description": "Optional list of multiple choice options"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "declare_manual_step",
        "description": "Declare a step that must be performed manually by a human in a SaaS UI.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Instructions for the human operator"}
            },
            "required": ["description"]
        }
    },
    {
        "name": "search_suppliers",
        "description": "Search and compare qualified component or product suppliers for procurement.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string", "description": "Name or specifications of the item/product"},
                "quantity": {"type": "integer", "description": "Required unit quantity"}
            },
            "required": ["item_name", "quantity"]
        }
    },
    {
        "name": "get_quote",
        "description": "Request a formal price quotation and apply allowed negotiation discount from a supplier.",
        "parameters": {
            "type": "object",
            "properties": {
                "supplier_id": {"type": "string", "description": "Supplier ID (e.g., 'sup-001')"},
                "item_name": {"type": "string", "description": "Name of the item"},
                "quantity": {"type": "integer", "description": "Quantity requested"},
                "target_discount_pct": {"type": "number", "description": "Negotiation discount percentage requested (max 15%)"}
            },
            "required": ["supplier_id", "quantity"]
        }
    },
    {
        "name": "check_governance_policy",
        "description": "Check whether a proposed transaction or action is within delegated spending authority limits.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action name (e.g. 'purchase', 'negotiate')"},
                "amount": {"type": "number", "description": "Total monetary amount in USD"}
            },
            "required": ["action", "amount"]
        }
    },
    {
        "name": "finalize_plan",
        "description": "Finalize and submit the proposed 5-array declarative workflow plan JSON.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan": {
                    "type": "object",
                    "properties": {
                        "tasks": {"type": "array", "items": {"type": "object"}},
                        "workflows": {"type": "array", "items": {"type": "object"}},
                        "workflow_links": {"type": "array", "items": {"type": "object"}},
                        "workflow_continuations": {"type": "array", "items": {"type": "object"}},
                        "task_continuations": {"type": "array", "items": {"type": "object"}}
                    },
                    "required": ["tasks", "workflows"]
                }
            },
            "required": ["plan"]
        }
    }
]


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Return copy of the whitelisted tool definitions list."""
    return [dict(t) for t in TOOL_DEFINITIONS]


def dispatch_tool(name: str, args: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    Dispatch tool call to appropriate handler.
    """
    handler = _TOOL_HANDLERS.get(name)
    if not handler:
        return {"status": "error", "error": f"Unknown tool: {name}"}

    try:
        return handler(args, context)
    except Exception as e:
        logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Tool Handler Functions
# ---------------------------------------------------------------------------

def _handle_list_services(args: dict, context: Any) -> dict:
    from workflow_orchestrator.conf import get_service_model
    Service = get_service_model()
    services = list(Service.objects.filter(is_active=True).values('id', 'name', 'metadata'))
    return {"status": "success", "services": services}


def _handle_get_service_resources(args: dict, context: Any) -> dict:
    service_name = args.get('service_name', '')
    from workflow_orchestrator.conf import get_service_model, get_resource_model
    Service = get_service_model()
    Resource = get_resource_model()

    srv = Service.objects.filter(name__iexact=service_name).first()
    if not srv:
        return {"status": "error", "error": f"Service '{service_name}' not found"}

    resources = list(Resource.objects.filter(service=srv).values('id', 'name', 'url', 'metadata'))
    return {"status": "success", "service": srv.name, "resources": resources}


def _handle_read_api_docs(args: dict, context: Any) -> dict:
    service_name = args.get('service_name', '')
    query = args.get('query', '')
    from .models import ApiDocumentation
    from workflow_orchestrator.conf import get_service_model
    Service = get_service_model()

    srv = Service.objects.filter(name__iexact=service_name).first()
    if not srv:
        return {"status": "error", "error": f"Service '{service_name}' not found"}

    docs = ApiDocumentation.objects.filter(service=srv, is_latest=True).first()
    if not docs:
        return {"status": "error", "error": f"No API documentation found for service '{service_name}'"}

    content = docs.content or json.dumps(docs.metadata)
    if query and query.lower() not in content.lower():
        # Truncate content or filter if query specified
        content_preview = content[:2000]
    else:
        content_preview = content[:4000]

    return {
        "status": "success",
        "service": srv.name,
        "version": docs.version,
        "doc_type": docs.doc_type,
        "content": content_preview,
        "verified": docs.verified
    }


def _handle_web_search(args: dict, context: Any) -> dict:
    query = args.get('query', '')
    try:
        from .search import search_api_docs
        return search_api_docs(query)
    except ImportError:
        # Fallback placeholder if search module not active yet
        return {
            "status": "success",
            "query": query,
            "results": [
                {"title": f"API Docs for {query}", "url": f"https://api-docs.example.com/{query}", "snippet": f"Official documentation endpoint for {query}"}
            ]
        }


def _handle_web_fetch(args: dict, context: Any) -> dict:
    url = args.get('url', '')
    try:
        from .search import fetch_url_safe
        return fetch_url_safe(url)
    except ImportError:
        return {"status": "success", "url": url, "content": f"Fetched content preview for {url}"}


def _handle_ingest_docs(args: dict, context: Any) -> dict:
    service_name = args.get('service_name', '')
    content = args.get('content', '')
    source_url = args.get('source_url', '')

    from .models import ApiDocumentation
    from workflow_orchestrator.conf import get_service_model
    Service = get_service_model()

    srv, _ = Service.objects.get_or_create(name=service_name.lower())
    doc, created = ApiDocumentation.objects.get_or_create(
        service=srv,
        version='v1',
        defaults={
            'name': f"{service_name} API Docs",
            'doc_source': 'web_fetch',
            'verified': False,
            'source_url': source_url,
            'content': content[:50000],
            'processing_status': 'processed'
        }
    )
    if not created:
        doc.content = content[:50000]
        doc.source_url = source_url
        doc.save()

    return {"status": "success", "doc_id": doc.id, "service": srv.name, "created": created}


def _handle_recall_context(args: dict, context: Any) -> dict:
    query = args.get('query', '')
    try:
        from .retrieval import recall_context_items
        return recall_context_items(query, context)
    except ImportError:
        return {"status": "success", "query": query, "recalled": []}


def _handle_define_jinja_helper(args: dict, context: Any) -> dict:
    name = args.get('name', '')
    source = args.get('source', '')
    if not name or not source:
        return {"status": "error", "error": "name and source are required"}

    source_hash = hashlib.sha256(source.encode()).hexdigest()
    from .models import JinjaHelper

    helper, created = JinjaHelper.objects.update_or_create(
        name=name,
        defaults={
            'source': source,
            'source_hash': source_hash,
            'is_approved': False  # Requires human approval
        }
    )
    return {
        "status": "success",
        "helper_id": helper.id,
        "name": helper.name,
        "is_approved": False,
        "message": f"JinjaHelper '{name}' defined as DRAFT. Requires human approval before execution."
    }


def _handle_define_python_function(args: dict, context: Any) -> dict:
    slug = args.get('slug', '')
    source = args.get('source', '')
    signature = args.get('signature', {})
    if not slug or not source:
        return {"status": "error", "error": "slug and source are required"}

    source_hash = hashlib.sha256(source.encode()).hexdigest()
    from .models import GeneratedFunction

    func, created = GeneratedFunction.objects.update_or_create(
        slug=slug,
        defaults={
            'source': source,
            'source_hash': source_hash,
            'signature': signature,
            'is_approved': False  # Requires human approval
        }
    )
    return {
        "status": "success",
        "function_id": func.id,
        "slug": func.slug,
        "is_approved": False,
        "message": f"GeneratedFunction '{slug}' defined as DRAFT. Requires human approval before execution."
    }


def _handle_ask_question(args: dict, context: Any) -> dict:
    question = args.get('question', '')
    options = args.get('options', [])

    org_id = getattr(context, 'org_id', None)
    run_id = getattr(context, 'agent_run_id', None) or (context.get_task_params('llm-plan').get('agent_run_id') if context else None)

    if run_id:
        from .models import AgentRun, AgentMessage
        run = AgentRun.objects.filter(id=run_id).first()
        if run:
            run.status = AgentRun.STATUS_AWAITING_INPUT
            run.save(update_fields=['status'])

            seq = run.messages.count() + 1
            AgentMessage.objects.create(
                agent_run=run,
                role='assistant',
                tool_name='ask_question',
                tool_args=args,
                content=question,
                sequence=seq
            )

    return {
        "status": "awaiting_input",
        "question": question,
        "options": options,
        "message": "Planner paused to ask human question."
    }


def _handle_declare_manual_step(args: dict, context: Any) -> dict:
    description = args.get('description', '')
    org_id = getattr(context, 'org_id', None)
    run_id = getattr(context, 'agent_run_id', None) or (context.get_task_params('llm-plan').get('agent_run_id') if context else None)

    from .models import ManualStep
    from workflow_orchestrator.conf import get_organization_model
    Organization = get_organization_model()

    org = None
    if org_id:
        org = Organization.objects.filter(id=org_id).first()
    if not org:
        org = Organization.objects.first()
    if not org:
        org = Organization.objects.create(name="Default ManualStep Org")

    step = ManualStep.objects.create(
        organization=org,
        agent_run_id=run_id,
        description=description,
        status='pending'
    )
    return {
        "status": "success",
        "step_id": step.id,
        "description": description,
        "message": f"ManualStep #{step.id} declared for human operator."
    }


def _handle_search_suppliers(args: dict, context: Any) -> dict:
    item_name = args.get('item_name', 'Industrial Sensors')
    quantity = int(args.get('quantity', 100))

    suppliers = [
        {
            "supplier_id": "sup-001",
            "name": "Apex Industrial Components",
            "unit_price_usd": 45.00,
            "total_price_usd": 45.00 * quantity,
            "lead_time_days": 3,
            "rating": 4.8
        },
        {
            "supplier_id": "sup-002",
            "name": "Global Tech Logistics",
            "unit_price_usd": 120.00,
            "total_price_usd": 120.00 * quantity,
            "lead_time_days": 2,
            "rating": 4.9
        },
        {
            "supplier_id": "sup-003",
            "name": "Gulf Precision Electronics",
            "unit_price_usd": 42.50,
            "total_price_usd": 42.50 * quantity,
            "lead_time_days": 5,
            "rating": 4.6
        }
    ]
    return {
        "status": "success",
        "item_name": item_name,
        "quantity": quantity,
        "suppliers": suppliers
    }


def _handle_get_quote(args: dict, context: Any) -> dict:
    supplier_id = args.get('supplier_id', 'sup-001')
    item_name = args.get('item_name', 'Industrial Sensors')
    quantity = int(args.get('quantity', 100))
    discount_pct = float(args.get('target_discount_pct', 0.0))

    base_unit_price = 45.00 if supplier_id == 'sup-001' else (120.00 if supplier_id == 'sup-002' else 42.50)
    discounted_unit_price = base_unit_price * (1.0 - (discount_pct / 100.0))
    total_price = round(discounted_unit_price * quantity, 2)

    return {
        "status": "success",
        "quote_id": f"QT-{supplier_id.upper()}-8821",
        "supplier_id": supplier_id,
        "item_name": item_name,
        "quantity": quantity,
        "unit_price_usd": round(discounted_unit_price, 2),
        "discount_applied_pct": discount_pct,
        "total_price_usd": total_price,
        "valid_until": "2026-10-01"
    }


def _handle_check_governance_policy(args: dict, context: Any) -> dict:
    org_id = getattr(context, 'org_id', 1)
    action = args.get('action', 'purchase')
    amount = float(args.get('amount', 0.0))

    from .governance import evaluate_action_policy
    decision = evaluate_action_policy(org_id, action, amount, args)
    return {
        "status": "success",
        "decision": decision.to_dict()
    }


def _handle_finalize_plan(args: dict, context: Any) -> dict:
    plan = args.get('plan', {})
    from .dsl import validate_plan_dsl
    is_valid, error = validate_plan_dsl(plan)

    if not is_valid:
        return {"status": "error", "error": f"Plan DSL validation failed: {error}"}

    run_id = getattr(context, 'agent_run_id', None) or (context.get_task_params('llm-plan').get('agent_run_id') if context else None)
    if run_id:
        from .models import AgentRun
        run = AgentRun.objects.filter(id=run_id).first()
        if run:
            run.plan_json = plan
            run.status = AgentRun.STATUS_SUCCEEDED
            run.save(update_fields=['plan_json', 'status'])

    return {
        "status": "finalized",
        "plan": plan,
        "message": "Plan DSL successfully validated and finalized!"
    }


_TOOL_HANDLERS = {
    "list_services": _handle_list_services,
    "get_service_resources": _handle_get_service_resources,
    "read_api_docs": _handle_read_api_docs,
    "web_search": _handle_web_search,
    "web_fetch": _handle_web_fetch,
    "ingest_docs": _handle_ingest_docs,
    "recall_context": _handle_recall_context,
    "define_jinja_helper": _handle_define_jinja_helper,
    "define_python_function": _handle_define_python_function,
    "ask_question": _handle_ask_question,
    "declare_manual_step": _handle_declare_manual_step,
    "search_suppliers": _handle_search_suppliers,
    "get_quote": _handle_get_quote,
    "check_governance_policy": _handle_check_governance_policy,
    "finalize_plan": _handle_finalize_plan,
}


def execute_tool_callable(ctx=None, **kwargs):
    """
    Python task entrypoint for tool execution in planner loop task.
    Called by PythonExecutor for the 'execute-tool' node.
    """
    if isinstance(ctx, dict):
        fn_kwargs = ctx.get('kwargs', {})
        context = ctx.get('context')
    else:
        fn_kwargs = kwargs
        context = None

    # Retrieve last tool call from context
    last_llm_result = context.get_result('llm-plan') if context else {}
    if not isinstance(last_llm_result, dict):
        last_llm_result = {}

    tool_calls = last_llm_result.get('tool_calls', [])
    if not tool_calls and last_llm_result.get('tool'):
        tool_calls = [{'name': last_llm_result['tool'], 'args': last_llm_result.get('tool_args', {})}]

    if not tool_calls:
        return {"status": "error", "error": "No tool call found in llm-plan result"}

    first_call = tool_calls[0]
    tool_name = first_call.get('name')
    tool_args = first_call.get('args', {})

    result = dispatch_tool(tool_name, tool_args, context)

    # Append to transcript in task_params for next llm-plan iteration
    if context:
        task_params = context.get_task_params('llm-plan')
        messages = task_params.get('messages', [])
        messages.append({
            'role': 'assistant',
            'content': last_llm_result.get('content', ''),
            'tool_calls': tool_calls
        })
        messages.append({
            'role': 'tool',
            'name': tool_name,
            'content': json.dumps(result)
        })
        context.update_task_params('llm-plan', {'messages': messages})

    return result
