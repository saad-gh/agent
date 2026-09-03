"""
Provider-agnostic LLM client module.
Dispatches inference to OpenAI, Anthropic, Google Gemini, or Mock provider.
Reads configuration and pricing from Resource/Service metadata.
"""
import json
import logging
import os
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)


async def complete(
    model_resource: Any = None,
    messages: Optional[List[Dict[str, Any]]] = None,
    response_format: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    credential: Any = None
) -> Dict[str, Any]:
    """
    Perform LLM inference using the specified model_resource configuration.

    Args:
        model_resource: Resource model instance (or dict) containing model metadata.
        messages: List of message dicts [{"role": "user|assistant|system", "content": "..."}]
        response_format: Dict specifying structured response format (e.g., {"type": "json_schema", ...})
        tools: List of tool definition dicts
        credential: Optional Credential instance containing API key or auth payload

    Returns:
        Dict with standardized keys:
        {
            "content": str,
            "tool_calls": [{"name": str, "args": dict}],
            "prompt_tokens": int,
            "completion_tokens": int,
            "stop_reason": str ("end_turn" | "tool_use" | "max_tokens")
        }
    """
    messages = messages or []

    # Extract metadata from model_resource or service
    meta = _extract_metadata(model_resource)
    provider = meta.get('provider', 'mock').lower()
    model_id = meta.get('model_id') or meta.get('model') or getattr(model_resource, 'name', 'mock-model')

    # Resolve API Key / auth
    api_key = _resolve_api_key(provider, credential, meta)

    # If mock explicitly selected, or mock_response present, or no API key, use mock
    if provider == 'mock' or meta.get('mock_response') or not api_key:
        return _mock_complete(meta, messages, tools, response_format)

    try:
        if provider == 'openai':
            return await _openai_complete(api_key, model_id, meta, messages, response_format, tools)
        elif provider == 'anthropic':
            return await _anthropic_complete(api_key, model_id, meta, messages, response_format, tools)
        elif provider in ('google', 'gemini'):
            return await _google_complete(api_key, model_id, meta, messages, response_format, tools)
        else:
            logger.warning(f"Unknown LLM provider '{provider}', falling back to mock")
            return _mock_complete(meta, messages, tools, response_format)
    except Exception as e:
        logger.error(f"LLM call to {provider}/{model_id} failed: {e}. Falling back to mock response.", exc_info=True)
        return _mock_complete(meta, messages, tools, response_format, error=str(e))


def _extract_metadata(model_resource: Any) -> Dict[str, Any]:
    """Extract merged metadata from model_resource and its service."""
    if not model_resource:
        return {}

    meta = {}
    if hasattr(model_resource, 'metadata') and isinstance(model_resource.metadata, dict):
        meta.update(model_resource.metadata)
    elif isinstance(model_resource, dict):
        meta.update(model_resource)

    if hasattr(model_resource, 'service') and model_resource.service:
        service_meta = getattr(model_resource.service, 'metadata', {}) or {}
        if isinstance(service_meta, dict):
            meta = {**service_meta, **meta}

    return meta


def _resolve_api_key(provider: str, credential: Any, meta: Dict[str, Any]) -> str:
    """Resolve API key from credential payload, metadata, or environment variables."""
    if credential:
        data = getattr(credential, 'data', {}) or {}
        if isinstance(data, dict):
            key = data.get('api_key') or data.get('access_token') or data.get('key')
            if key:
                return key

    if 'api_key' in meta:
        return meta['api_key']

    env_var_map = {
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'google': 'GOOGLE_API_KEY',
        'gemini': 'GOOGLE_API_KEY',
    }

    env_var = env_var_map.get(provider, '')
    return os.environ.get(env_var, '') if env_var else ''


def _mock_complete(
    meta: Dict[str, Any],
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    response_format: Optional[Dict[str, Any]] = None,
    error: str = None
) -> Dict[str, Any]:
    """Generate a canned or mock response for testing/development."""
    if meta.get('mock_response'):
        mock_resp = meta['mock_response']
        if isinstance(mock_resp, dict):
            return {
                "content": mock_resp.get("content", ""),
                "tool_calls": mock_resp.get("tool_calls", []),
                "prompt_tokens": mock_resp.get("prompt_tokens", 10),
                "completion_tokens": mock_resp.get("completion_tokens", 10),
                "stop_reason": mock_resp.get("stop_reason", "end_turn")
            }
        elif isinstance(mock_resp, str):
            return {
                "content": mock_resp,
                "tool_calls": [],
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "stop_reason": "end_turn"
            }

    # Default mock response for planner tool call or message
    last_msg = messages[-1].get('content', '') if messages else ''

    # Check if tools are provided and mock a finalize or tool call if requested
    tool_calls = []
    if tools and ("finalize" in last_msg.lower() or "plan" in last_msg.lower()):
        tool_calls = [{
            "name": "finalize_plan",
            "args": {
                "plan": {
                    "tasks": [],
                    "workflows": [],
                    "workflow_links": [],
                    "workflow_continuations": [],
                    "task_continuations": []
                }
            }
        }]
        stop_reason = "tool_use"
    else:
        stop_reason = "end_turn"

    content = f"Mock LLM response for: {last_msg[:50]}" if not error else f"Mock fallback due to error: {error}"

    return {
        "content": content,
        "tool_calls": tool_calls,
        "prompt_tokens": len(last_msg.split()) + 10,
        "completion_tokens": len(content.split()) + 5,
        "stop_reason": stop_reason
    }


async def _openai_complete(
    api_key: str,
    model_id: str,
    meta: Dict[str, Any],
    messages: List[Dict[str, Any]],
    response_format: Optional[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """Execute OpenAI Chat Completion API call via HTTP."""
    base_url = meta.get('base_url', 'https://api.openai.com/v1/chat/completions')
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    payload = {
        'model': model_id,
        'messages': messages,
        'temperature': float(meta.get('temperature', 0.0)),
        'max_tokens': int(meta.get('max_tokens', 4096)),
    }

    if tools:
        payload['tools'] = [{
            'type': 'function',
            'function': {
                'name': tool.get('name'),
                'description': tool.get('description', ''),
                'parameters': tool.get('parameters', {})
            }
        } for tool in tools]

    if response_format:
        payload['response_format'] = response_format

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(base_url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    choice = data['choices'][0]
    msg = choice['message']
    usage = data.get('usage', {})

    tool_calls = []
    if msg.get('tool_calls'):
        for tc in msg['tool_calls']:
            fn = tc.get('function', {})
            try:
                args = json.loads(fn.get('arguments', '{}'))
            except Exception:
                args = {}
            tool_calls.append({'name': fn.get('name'), 'args': args})

    return {
        'content': msg.get('content') or '',
        'tool_calls': tool_calls,
        'prompt_tokens': usage.get('prompt_tokens', 0),
        'completion_tokens': usage.get('completion_tokens', 0),
        'stop_reason': 'tool_use' if tool_calls else choice.get('finish_reason', 'end_turn')
    }


async def _anthropic_complete(
    api_key: str,
    model_id: str,
    meta: Dict[str, Any],
    messages: List[Dict[str, Any]],
    response_format: Optional[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """Execute Anthropic Messages API call via HTTP."""
    base_url = meta.get('base_url', 'https://api.anthropic.com/v1/messages')
    headers = {
        'x-api-key': api_key,
        'anthropic-version': meta.get('api_version', '2023-06-01'),
        'content-type': 'application/json',
    }

    # Extract system message if present
    system_prompt = ""
    filtered_messages = []
    for m in messages:
        if m.get('role') == 'system':
            system_prompt += m.get('content', '') + "\n"
        else:
            filtered_messages.append(m)

    payload = {
        'model': model_id,
        'messages': filtered_messages,
        'max_tokens': int(meta.get('max_tokens', 4096)),
        'temperature': float(meta.get('temperature', 0.0)),
    }
    if system_prompt:
        payload['system'] = system_prompt.strip()

    if tools:
        payload['tools'] = [{
            'name': tool.get('name'),
            'description': tool.get('description', ''),
            'input_schema': tool.get('parameters', {})
        } for tool in tools]

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(base_url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    content_text = ""
    tool_calls = []

    for block in data.get('content', []):
        if block.get('type') == 'text':
            content_text += block.get('text', '')
        elif block.get('type') == 'tool_use':
            tool_calls.append({
                'name': block.get('name'),
                'args': block.get('input', {})
            })

    usage = data.get('usage', {})

    return {
        'content': content_text,
        'tool_calls': tool_calls,
        'prompt_tokens': usage.get('input_tokens', 0),
        'completion_tokens': usage.get('output_tokens', 0),
        'stop_reason': 'tool_use' if tool_calls else data.get('stop_reason', 'end_turn')
    }


async def _google_complete(
    api_key: str,
    model_id: str,
    meta: Dict[str, Any],
    messages: List[Dict[str, Any]],
    response_format: Optional[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """Execute Google Gemini API call via HTTP."""
    model_name = model_id if model_id.startswith('models/') else f"models/{model_id}"
    base_url = meta.get('base_url', f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}")

    contents = []
    for m in messages:
        role = 'user' if m.get('role') in ('user', 'system') else 'model'
        contents.append({
            'role': role,
            'parts': [{'text': m.get('content', '')}]
        })

    payload = {'contents': contents}

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(base_url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    candidates = data.get('candidates', [])
    text = ""
    if candidates:
        parts = candidates[0].get('content', {}).get('parts', [])
        text = "".join(p.get('text', '') for p in parts)

    meta_usage = data.get('usageMetadata', {})

    return {
        'content': text,
        'tool_calls': [],
        'prompt_tokens': meta_usage.get('promptTokenCount', 0),
        'completion_tokens': meta_usage.get('candidatesTokenCount', 0),
        'stop_reason': 'end_turn'
    }
