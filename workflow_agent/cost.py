"""
Cost estimation module for LLM token consumption.
Metadata-driven pricing (no hardcoded pricing tables).
"""
import logging

logger = logging.getLogger(__name__)


def estimate_cost(resource_or_service, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Estimate cost in USD for token usage based on pricing metadata.

    Reads pricing metadata from resource or service metadata:
    - input_price (or input_price_per_m): USD per 1M input tokens
    - output_price (or output_price_per_m): USD per 1M output tokens

    Args:
        resource_or_service: Resource or Service instance (or dict/object with metadata attribute)
        prompt_tokens: Number of input/prompt tokens
        completion_tokens: Number of output/completion tokens

    Returns:
        Float cost in USD (rounded to 6 decimal places)
    """
    if not resource_or_service:
        return 0.0

    metadata = {}
    if hasattr(resource_or_service, 'metadata') and isinstance(resource_or_service.metadata, dict):
        metadata = resource_or_service.metadata
    elif isinstance(resource_or_service, dict):
        metadata = resource_or_service

    # Fall back to parent service metadata if resource metadata doesn't specify pricing
    if hasattr(resource_or_service, 'service') and resource_or_service.service:
        service_meta = getattr(resource_or_service.service, 'metadata', {}) or {}
        if isinstance(service_meta, dict):
            metadata = {**service_meta, **metadata}

    input_price = float(
        metadata.get('input_price') or
        metadata.get('input_price_per_m') or
        metadata.get('input_cost_per_m') or
        0.0
    )

    output_price = float(
        metadata.get('output_price') or
        metadata.get('output_price_per_m') or
        metadata.get('output_cost_per_m') or
        0.0
    )

    input_cost = (prompt_tokens / 1_000_000.0) * input_price
    output_cost = (completion_tokens / 1_000_000.0) * output_price
    total_cost = round(input_cost + output_cost, 6)

    return total_cost
