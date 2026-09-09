"""
Agent Core Plan DSL Validation & DAG Cycle Checker.

Validates proposed 5-array workflow plans in declarative JSON format,
enforcing required top-level arrays and Kahn's algorithm topological DAG acyclicity.
"""
from workflow_agent.dsl import (
    REQUIRED_TOP_ARRAYS,
    validate_plan_dsl,
    _validate_dag_acyclicity,
    render_plan_dsl
)

__all__ = [
    'REQUIRED_TOP_ARRAYS',
    'validate_plan_dsl',
    '_validate_dag_acyclicity',
    'render_plan_dsl'
]
