# System Architecture & Technical Specifications

## Platform Overview
The platform provides a bounded, rule-governed environment where AI agents act on behalf of users within explicit permissions. It separates the **Agent Planning Layer** (`workflow_agent`) from the **Durable Execution Substrate** (`workflow_orchestrator`).

---

## 1. System Architecture Diagram

```
                                  +-----------------------+
                                  |     User / Client     |
                                  +-----------+-----------+
                                              |
                                              v
                                  +-----------------------+
                                  |     Agent API         |
                                  |  (views.py / URLs)    |
                                  +-----------+-----------+
                                              |
                                              v
                                  +-----------------------+
                                  |    Agent / Planner    |
                                  |   (agent_loop.py)     |
                                  +-----------+-----------+
                                              |
                     +------------------------+------------------------+
                     |                        |                        |
                     v                        v                        v
         +-----------------------+  +-------------------+  +-----------------------+
         | Model Abstraction     |  | Tool Registry     |  | Governance Engine     |
         | (llm_client.py)       |  | (tools.py)        |  | (governance.py)       |
         +-----------+-----------+  +---------+---------+  +-----------+-----------+
                     |                        |                        |
                     +------------------------+------------------------+
                                              |
                                              v
                                  +-----------------------+
                                  | Declarative Plan DSL  |
                                  | (5-Array JSON / dsl)  |
                                  +-----------+-----------+
                                              |
                                              v
                                  +-----------------------+
                                  | Materialization Engine|
                                  | (_materialize_plan)   |
                                  +-----------+-----------+
                                              |
                                              v
                                  +-----------------------+
                                  | Workflow Orchestrator |
                                  | (traverser / graph)   |
                                  +-----------+-----------+
                                              |
                     +------------------------+------------------------+
                     |                        |                        |
                     v                        v                        v
         +-----------------------+  +-------------------+  +-----------------------+
         | Executable Tasks      |  | Gatekeepers &     |  | Checkpoint & Resume   |
         | (HTTP/Python Executors|  | Continuations     |  | Engine                |
         +-----------+-----------+  +---------+---------+  +-----------+-----------+
                     |                        |                        |
                     +------------------------+------------------------+
                                              |
                                              v
                                  +-----------------------+
                                  | Telemetry & Audit Logs|
                                  | (AiUsage / Egress)    |
                                  +-----------------------+
```

---

## 2. Key Architecture Components

### A. Agent & Planning Layer (`workflow_agent`)
* **Agent Loop (`agent_loop.py`):** Manages `AgentRun` state transitions (`planning`, `awaiting_input`, `succeeded`, `failed`) and maintains an append-only `AgentMessage` transcript.
* **Self-Referential Topology (`planner_topology.py`):** Expresses the planner loop itself as an orchestrated 2-node graph (`llm-plan` ⇄ `execute-tool`).
* **Provider-Agnostic LLM Abstraction (`llm_client.py`):** Unified interface for OpenAI, Anthropic, Google Gemini, and Mock providers. Model preferences are configured per reasoning tier (`plan`, `extract`, `transform`, `summarize`).
* **Governance Engine (`governance.py`):** Enforces organizational authority policies (delegated monetary limits, allowed action whitelists, discount caps). Evaluates LLM proposals before execution.
* **AST Security Sanitizer (`sanitize.py` & `run_safe.py`):** Enforces an AST allowlist on agent-generated Python functions, executing them in isolated subprocess pools with process termination on timeout.
* **SSRF Guard (`search.py`):** Validates outbound HTTP fetch URLs against private, loopback, and link-local IP address spaces (`127.0.0.1`, `10.x`, `172.16.x`, `192.168.x`, `169.254.x`).

### B. Durable Execution Substrate (`workflow_orchestrator`)
* **DAG Traversal Engine (`traverser.py`):** Asynchronous DAG traverser executing root nodes and propagating fanned-out state down task edges.
* **Declarative Continuations (`TaskContinuation`):** Jinja2-conditioned self-loops for exponential backoff retries, rate-limiting, and pagination.
* **Pre-Execution Gatekeepers (`WorkflowContinuation`):** Pre-task gatekeepers that evaluate conditions prior to node execution and signal `skip` or `escalate`.
* **Checkpoint & Resume (`Checkpoint`):** Pickles execution context when paused or requiring human approval, allowing resumption via `resume_run()`.
* **Mock Response Infrastructure (`mock_server.py`):** Canned HTTP scenario runner (`AiohttpMocker` and `ScenarioBuilder`) for deterministic testing and demo execution.
* **Auditability & Observability:** Logs execution events via `TelemetryLogger`, token usage via `AiUsageLog`, and network byte transfer via `DataEgressLog`.
