"""
Agent Core Plan DSL Materialization Engine.

Converts validated 5-array JSON workflow plans into concrete Task, Workflow,
WorkflowContinuation, and TaskContinuation database records in workflow_orchestrator.
"""
from workflow_agent.views import _materialize_plan_dsl

__all__ = ['_materialize_plan_dsl']
