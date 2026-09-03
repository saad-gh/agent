"""
Jinja Helpers Loader for DB-Stored Approved Helpers.
Serves as the callback for settings.TASK_JINJA_HELPERS_LOADER.
"""
import datetime
import json
import logging
import math
import re
import uuid
from typing import Dict, Any

from .sanitize import validate_source

logger = logging.getLogger(__name__)

SAFE_BUILTINS = {
    'abs': abs, 'all': all, 'any': any, 'bool': bool, 'dict': dict,
    'enumerate': enumerate, 'float': float, 'format': format,
    'int': int, 'isinstance': isinstance, 'len': len, 'list': list,
    'max': max, 'min': min, 'range': range, 'round': round,
    'set': set, 'sorted': sorted, 'str': str, 'sum': sum,
    'tuple': tuple, 'zip': zip, 'True': True, 'False': False, 'None': None
}

SAFE_GLOBALS = {
    '__builtins__': SAFE_BUILTINS,
    'json': json,
    're': re,
    'datetime': datetime,
    'math': math,
    'uuid': uuid,
}


def load_approved_helpers() -> Dict[str, Any]:
    """
    Load all approved JinjaHelper records from DB and compile them safely.
    Callback for settings.TASK_JINJA_HELPERS_LOADER.

    Returns:
        Dict of {helper_name: callable_function}
    """
    try:
        from .models import JinjaHelper
        approved_helpers = JinjaHelper.objects.filter(is_approved=True)
    except Exception as e:
        logger.warning(f"Could not query JinjaHelper table: {e}")
        return {}

    globals_dict = {}

    for helper in approved_helpers:
        is_valid, err = validate_source(helper.source)
        if not is_valid:
            logger.warning(f"Approved JinjaHelper '{helper.name}' failed AST security check: {err}")
            continue

        try:
            local_scope = {}
            global_scope = SAFE_GLOBALS.copy()
            compiled_code = compile(helper.source, f"<jinja_helper_{helper.name}>", 'exec')
            exec(compiled_code, global_scope, local_scope)

            fn = local_scope.get(helper.name) or global_scope.get(helper.name)
            if callable(fn):
                globals_dict[helper.name] = fn
            else:
                logger.warning(f"JinjaHelper '{helper.name}' source did not define callable '{helper.name}'")
        except Exception as e:
            logger.error(f"Error compiling approved JinjaHelper '{helper.name}': {e}", exc_info=True)

    return globals_dict
