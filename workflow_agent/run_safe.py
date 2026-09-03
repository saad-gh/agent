"""
Subprocess Execution Runner for Agent-Generated Python Functions.
Executes approved functions in a isolated process pool with a strict timeout.
"""
import concurrent.futures
import datetime
import json
import logging
import math
import re
import uuid
from typing import Dict, Any, Optional

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


import datetime
import json
import logging
import math
import multiprocessing
import re
import uuid
from typing import Dict, Any, Optional

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


def _proc_target(source: str, func_name: str, kwargs: dict, queue: multiprocessing.Queue):
    """
    Subprocess worker target that compiles, runs function, and puts result into queue.
    """
    import inspect
    try:
        local_scope = {}
        global_scope = SAFE_GLOBALS.copy()

        compiled_code = compile(source, f"<generated_func_{func_name}>", 'exec')
        exec(compiled_code, global_scope, local_scope)

        possible_names = [func_name, func_name.replace('-', '_'), 'run', 'main']
        fn = None
        for name in possible_names:
            candidate = local_scope.get(name) or global_scope.get(name)
            if callable(candidate):
                fn = candidate
                break

        if not fn:
            queue.put({"status": "error", "error": f"No entrypoint function found for '{func_name}'"})
            return

        sig = inspect.signature(fn)
        if len(sig.parameters) > 0:
            res = fn(kwargs if kwargs is not None else {})
        else:
            res = fn()

        if not isinstance(res, dict):
            res = {"result": res}
        if "status" not in res:
            res["status"] = "success"

        queue.put(res)
    except Exception as e:
        queue.put({"status": "error", "error": str(e)})


def run_generated_function(slug: str, kwargs: Optional[dict] = None, timeout: int = 5) -> Dict[str, Any]:
    """
    Look up an approved GeneratedFunction by slug and execute it safely in a terminated subprocess.

    Args:
        slug: Unique slug of the GeneratedFunction
        kwargs: Keyword arguments dict to pass to the function
        timeout: Execution timeout in seconds (default 5s)

    Returns:
        Dict result returned by function, or error dict if unapproved/timeout/failed
    """
    kwargs = kwargs or {}

    try:
        from .models import GeneratedFunction
        func = GeneratedFunction.objects.filter(slug=slug, is_approved=True).first()
    except Exception as e:
        return {"status": "error", "error": f"Database error querying GeneratedFunction: {e}"}

    if not func:
        return {"status": "error", "error": f"GeneratedFunction '{slug}' not found or not approved by human"}

    # 1. AST Security Validation
    is_valid, err = validate_source(func.source)
    if not is_valid:
        return {"status": "error", "error": f"AST security validation failed for '{slug}': {err}"}

    # 2. Subprocess Execution with Process Termination on Timeout
    queue = multiprocessing.Queue()
    proc = multiprocessing.Process(
        target=_proc_target,
        args=(func.source, slug, kwargs, queue)
    )
    proc.start()
    proc.join(timeout=timeout)

    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=1)
        if proc.is_alive():
            proc.kill()
        logger.error(f"GeneratedFunction '{slug}' execution timed out after {timeout} seconds")
        return {"status": "error", "error": f"Function execution timed out ({timeout}s)"}

    if not queue.empty():
        return queue.get()

    return {"status": "error", "error": f"Function execution terminated without output"}
