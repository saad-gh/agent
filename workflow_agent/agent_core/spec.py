"""
Standardized API Specification Schema, Validation, and Storage Helpers.

Acts as the contract between Agent A (Endpoint Specialist) and Agent B (Workflow Architect).
Agent A normalizes raw docs -> API Spec (YAML/JSON) -> saves to storage -> updates Service.api_spec_path.
Agent B reads Service.api_spec_path -> validates schema -> materializes DAG Workflows.
"""
import json
import logging
from typing import Dict, Any, Tuple, Optional
import json

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

from .storage import get_storage

logger = logging.getLogger(__name__)


REQUIRED_SPEC_FIELDS = ['service', 'version', 'endpoints']
REQUIRED_ENDPOINT_FIELDS = ['slug', 'method', 'path']


def validate_api_spec(spec: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate standardized API spec schema.

    Checks:
    1. Top-level object structure & required fields (service, version, endpoints).
    2. Endpoints array items (slug, method, path).
    """
    if not isinstance(spec, dict):
        return False, "API Spec must be a dictionary/object"

    for field in REQUIRED_SPEC_FIELDS:
        if field not in spec:
            return False, f"Missing required top-level field '{field}' in API Spec"

    endpoints = spec.get('endpoints')
    if not isinstance(endpoints, list):
        return False, "'endpoints' must be a list of endpoint definitions"

    for i, ep in enumerate(endpoints):
        if not isinstance(ep, dict):
            return False, f"Endpoint at index {i} must be an object"
        for ef in REQUIRED_ENDPOINT_FIELDS:
            if not ep.get(ef):
                return False, f"Endpoint at index {i} missing required field '{ef}'"

    return True, None


def parse_spec_content(content: str) -> Dict[str, Any]:
    """Parse YAML or JSON spec string into dict."""
    content = content.strip()
    if content.startswith('{') or content.startswith('['):
        return json.loads(content)

    if _HAS_YAML:
        return yaml.safe_load(content)

    # Fallback json loader if pyyaml not installed
    return json.loads(content)


def dump_spec_content(spec_data: Dict[str, Any], fmt: str = 'yaml') -> str:
    """Format spec data dict into YAML or JSON string."""
    if fmt.lower() == 'yaml' and _HAS_YAML:
        return yaml.dump(spec_data, sort_keys=False)
    return json.dumps(spec_data, indent=2)


def load_spec_for_service(service: Any) -> Dict[str, Any]:
    """
    Load and validate API spec for a Service instance via service.api_spec_path.
    """
    path = getattr(service, 'api_spec_path', '')
    if not path:
        raise ValueError(f"Service '{service.name}' has no api_spec_path configured")

    storage = get_storage(path)
    content = storage.read(path)
    spec_data = parse_spec_content(content)

    is_valid, err = validate_api_spec(spec_data)
    if not is_valid:
        raise ValueError(f"Invalid API Spec for service '{service.name}': {err}")

    return spec_data


def save_spec_for_service(
    service: Any,
    spec_data: Dict[str, Any],
    path: Optional[str] = None,
    fmt: str = 'yaml'
) -> str:
    """
    Validate, format, write to storage, and set service.api_spec_path.

    Returns:
        The updated api_spec_path string.
    """
    is_valid, err = validate_api_spec(spec_data)
    if not is_valid:
        raise ValueError(f"Cannot save invalid API Spec: {err}")

    target_path = path or service.api_spec_path or f"specs/{service.name.lower()}-v{spec_data.get('version', '1')}.yaml"
    content = dump_spec_content(spec_data, fmt=fmt)

    storage = get_storage(target_path)
    storage.write(target_path, content)

    service.api_spec_path = target_path
    if hasattr(service, 'save'):
        service.save(update_fields=['api_spec_path'])

    return target_path
