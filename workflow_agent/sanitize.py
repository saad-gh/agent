"""
AST Allowlist Sanitizer for Agent-Generated Code.
Validates python source code before compilation or execution.
"""
import ast
import logging
from typing import Tuple, Optional, Set

logger = logging.getLogger(__name__)

ALLOWED_MODULES: Set[str] = {
    'json', 're', 'datetime', 'math', 'uuid',
    'xml', 'xml.etree.ElementTree', 'typing',
    'collections', 'functools', 'string', 'decimal'
}

FORBIDDEN_NAMES: Set[str] = {
    'eval', 'exec', 'open', '__import__', 'globals', 'locals',
    'compile', 'getattr', 'setattr', 'delattr', 'input',
    '__builtins__', '__subclasses__', '__class__', '__code__',
    '__globals__', '__import__'
}


def validate_source(source: str) -> Tuple[bool, Optional[str]]:
    """
    Validate python source code against AST security allowlist.

    Checks:
    1. Parse syntax
    2. Disallow forbidden imports (only json, re, datetime, math, uuid, etc. allowed)
    3. Disallow forbidden names and calls (eval, exec, open, __import__)
    4. Disallow dunder attribute access (__subclasses__, __globals__)

    Args:
        source: Python source code string

    Returns:
        Tuple of (is_valid: bool, error_message: str or None)
    """
    if not source or not source.strip():
        return False, "Source code cannot be empty"

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return False, f"Syntax error in source code: {e}"

    for node in ast.walk(tree):
        # 1. Check Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_base = alias.name.split('.')[0]
                if alias.name not in ALLOWED_MODULES and mod_base not in ALLOWED_MODULES:
                    return False, f"Forbidden import: '{alias.name}'. Only standard data modules allowed."

        elif isinstance(node, ast.ImportFrom):
            mod_name = node.module or ''
            mod_base = mod_name.split('.')[0]
            if mod_name not in ALLOWED_MODULES and mod_base not in ALLOWED_MODULES:
                return False, f"Forbidden import from: '{mod_name}'. Only standard data modules allowed."

        # 2. Check Forbidden Names
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                return False, f"Forbidden identifier: '{node.id}'"

        # 3. Check Dunder Attribute Access
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith('__') and node.attr.endswith('__'):
                return False, f"Forbidden dunder attribute access: '{node.attr}'"

        # 4. Check Call Expressions
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_NAMES:
                    return False, f"Forbidden function call: '{node.func.id}'"

    return True, None
