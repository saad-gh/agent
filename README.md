# Employer-Facing Agentic AI Platform Demonstrator

> **Bounded Agentic AI, Governance & Durable Execution Substrate**  
> A reproducible demonstrator of an enterprise platform where rule-bound AI agents plan, negotiate, and execute workflows under explicit delegated authority.

[![Tests](https://img.shields.io/badge/tests-131%20passing-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)]()
[![Django](https://img.shields.io/badge/django-4.2+-success.svg)]()
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)]()

---

## 1. What This Project Demonstrates

This demonstrator showcases an enterprise-grade agentic AI platform built for rule-governed execution. It solves the core challenge of deploying autonomous agents in business environments: **allowing AI agents to act autonomously within explicit user-defined rules while escalating to human principals for actions outside delegated authority.**

Key Capabilities Demonstrated:
- **Genuine Agentic Orchestration:** Multi-step tool use, reasoning, context recall, and declarative workflow generation.
- **Bounded Delegation:** Explicit monetary spending limits, action whitelists, and negotiation constraints enforced by a platform policy engine.
- **Human-in-the-Loop Escalation:** Automatic execution pause and checkpointing when an action exceeds authority, with seamless resumption upon human approval.
- **Declarative Intermediate Representation:** Agents emit structured 5-array JSON workflow plans validated for DAG topological acyclicity before execution.
- **Durable Task Execution:** Asynchronous DAG traversal engine supporting exponential backoff retries, rate limits, checkpointing, and pagination.
- **Multi-Model Abstraction:** Provider-agnostic client supporting OpenAI, Anthropic, Google Gemini, and offline Mock providers with tier-based routing.
- **Enterprise Auditability:** Full telemetry trail recording prompt history, tool calls, token consumption, cost estimation, and network egress byte sizes.

---

## 2. Why It Is Agentic (Beyond an LLM Wrapper)

Traditional LLM wrappers follow a simple `Prompt -> LLM -> Response` paradigm. In contrast, this platform enforces a strict separation between **Intelligence/Planning** and **Platform Governance/Execution**:

```
[ User Intent ]
       │
       ▼
[ Agent Planner ] ──(Tool Selection)──► [ Supplier Lookup / Quote Retrieval ]
       │                                            │
       ▼                                            ▼
[ Declarative 5-Array Plan ] ◄──────────────────────┘
       │
       ▼
[ Platform Governance Engine ] ──► (Validates Limits: LLM Is NOT the Authority)
       │
       ├──► Authorized (Within Limit) ──► [ Durable Workflow Orchestrator ]
       │                                            │
       └──► Over Limit (Escalation) ────────► [ Human Principal Approval ] ──► Resume
```

1. **The LLM is NOT the Security Authority:** The LLM proposes actions, but the platform governance engine validates authority. If an agent attempts a transaction above its delegated limit, the platform intercepts and escalates.
2. **Intermediate Plan IR:** The agent produces a 5-array JSON DSL representation of the workflow. The platform validates schema and DAG acyclicity using Kahn's algorithm before any mutation or transaction occurs.
3. **Durable State Persisted:** Execution runs on a task-based orchestrator that survives process crashes, API rate limits, and multi-day human approval delays.

---

## 3. System Architecture

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

See [docs/architecture.md](docs/architecture.md) for full component specifications.

---

## 4. Agent Lifecycle

1. **Initialization (`start_agent_plan`):** Accepts user prompt and initializes an `AgentRun` record in `planning` state.
2. **Planner Topology Execution (`planner_topology.py`):** The planner loop itself is constructed as an orchestrated 2-node workflow (`llm-plan` ⇄ `execute-tool`).
3. **Inference & Tool Selection:** `llm-plan` node executes inference using the provider abstraction. If tool calls are generated, state passes to `execute-tool`.
4. **Iterative Refinement:** `execute-tool` dispatches requested tools (`search_suppliers`, `get_quote`, `check_governance_policy`) and appends results to transcript.
5. **Plan Submission:** Once sufficient observations are gathered, the agent calls `finalize_plan` with the 5-array JSON workflow structure.

---

## 5. Tool-Use Lifecycle

```
Agent Inference ──► Request Tool ──► Whitelist Check ──► Dispatch Handler ──► Append Observation ──► Next Turn
```

- **Registry (`tools.py`):** Whitelisted tools defined with JSON Schema parameter definitions.
- **Dispatch (`dispatch_tool`):** Maps tool names to handler functions (`_handle_search_suppliers`, `_handle_get_quote`, `_handle_check_governance_policy`, `_handle_read_api_docs`, `_handle_web_search`).
- **Sandboxed Function Generation:** Code generated by agents is checked against an AST allowlist (`sanitize.py`) and executed in an isolated subprocess (`run_safe.py`).

---

## 6. Governance Boundary (Bounded Delegation)

The platform enforces explicit organizational policies via `governance.py`:
- **Delegated Spending Limit:** Maximum monetary amount an agent may authorize without human approval (e.g. $5,000.00 USD).
- **Allowed Action Whitelist:** Explicit list of permitted operations.
- **Discount & Negotiation Caps:** Maximum allowed negotiation discount (e.g. 15%).

```python
# Governance Evaluation Logic
decision = evaluate_action_policy(
    organization_id=org.id,
    action="purchase",
    amount=12000.00  # Proposed quote
)
# Returns: authorized=False, requires_approval=True
```

When an action exceeds delegated limits, the platform policy gatekeeper halts automatic execution, creates a `ManualStep` record, and pauses the workflow context.

---

## 7. Human-in-the-Loop Approval Flow

```
Agent Proposes Action Over Limit
             │
             ▼
   [ Governance Engine ] ──► Action > Delegated Limit
             │
             ▼
   [ Platform Action ] ──► Pause Workflow + Create Checkpoint & ManualStep
             │
             ▼
   [ Human Principal ] ──► Review Request & POST /agent/step/<id>/approve/
             │
             ▼
   [ Platform Resume ] ──► Resume Workflow from Checkpoint ──► Execution Complete
```

API Endpoints:
- `POST /agent/run/`: Start agent planning run.
- `GET /agent/run/<id>/`: Inspect run status, messages, plan JSON, and manual steps.
- `POST /agent/run/<id>/message/`: Answer clarifying questions.
- `POST /agent/run/<id>/approve/`: Approve proposed workflow plan and materialize DB rows.
- `POST /agent/step/<id>/approve/`: Human principal approval for escalated transactions.

---

## 8. Workflow Execution Substrate

Workflows are executed by `workflow_orchestrator`, a task-based DAG execution engine:
- **Task Types:** `http` (API requests), `python` (callable execution), `orm` (DB updates), `mutation` (state updates), `checkpoint` (durable pause).
- **DAG Graph Construction:** `WorkflowGraph` builds directed edges based on `Workflow.mapped_by`.
- **Async Traversal:** `WorkflowTraverser` traverses root nodes concurrently, fanning out parameters down child edges.

---

## 9. Failure & Retry Behavior (Transient Recovery)

Transient API failures (e.g., HTTP 429 Rate Limits or 5xx errors) are handled declaratively using `TaskContinuation`:

```
API Request ──► 429 Rate Limited ──► Continuation Condition Met ──► Exponential Backoff ──► Retry ──► 200 OK
```

- **Declarative Conditions:** `TaskContinuation` links tasks using Jinja2 conditions:
  `{{ result.status_code == 429 and (task_params._retry_count | int) < 3 }}`
- **Deterministic Mocking:** `mock_server.py` and `ScenarioBuilder.rate_limited_then_success()` allow testing and demonstrating retry recovery deterministically without depending on external API availability.

---

## 10. Multi-Model Provider Abstraction

The LLM client (`llm_client.py`) provides a provider-agnostic completion interface:
- **Supported Providers:** OpenAI (`gpt-4o`), Anthropic (`claude-3-5-sonnet`), Google Gemini (`gemini-1.5-pro`), and offline Mock provider.
- **Model Preference Routing (`ModelPreference`):** Configures primary model resources per reasoning tier (`plan`, `extract`, `transform`, `summarize`).
- **Graceful Fallback:** Automatically falls back to canned mock responses when API keys are absent or network errors occur.

---

## 11. Auditability & Observability

Every agent run and workflow execution produces an immutable audit trail:
- **`AgentMessage`:** Append-only message transcript recording prompt history and tool call parameters.
- **`AiUsageLog`:** Tracks prompt tokens, completion tokens, model name, and calculates estimated USD inference cost.
- **`DataEgressLog`:** Persists HTTP request and response body byte transfer sizes per organization and service.
- **`TelemetryLogger`:** Structured JSON logging for workflow lifecycle events (`NODE_STARTED`, `NODE_COMPLETED`, `NODE_PAUSED`, `NODE_CONTINUATION`).

---

## 12. Security Architecture

1. **SSRF Protection (`search.py`):** All outbound web fetch calls pass through `is_ip_allowed()` which blocks loopback (`127.0.0.1`), private (`10.x`, `172.16.x`, `192.168.x`), and link-local (`169.254.x`) IP addresses.
2. **AST Code Sanitizer (`sanitize.py`):** Code generated by agents is parsed into an AST and validated against a strict allowlist (forbidding `eval`, `exec`, `open`, `__import__`, or arbitrary dunder access).
3. **Subprocess Isolation (`run_safe.py`):** Approved generated Python functions execute in isolated subprocesses with process termination on timeout.
4. **Credential Isolation:** API keys and OAuth tokens are stored encrypted and resolved at runtime.

---

## 13. Running Locally

### Prerequisites
- Python 3.10+
- Virtual environment

### Installation
```bash
# Clone the repository
git clone https://github.com/your-username/workflow-agent.git
cd workflow-agent

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Configure environment variables
cp .env.example .env
```

---

## 14. Running the Deterministic Demo (Zero Infrastructure Required)

The repository includes a 100% reproducible, zero-infrastructure CLI demonstrator that requires no external database or API keys.

```bash
# Run the CLI demonstrator
python demo.py
```

### What the Demo Displays:
1. **User Goal:** Procurement of 100 Industrial Sensors within a $5,000 limit.
2. **Agent Reasoning:** Tool dispatch (`search_suppliers`, `get_quote`, `check_governance_policy`).
3. **Declarative Plan DSL:** 5-array workflow plan generation and Kahn's DAG cycle check.
4. **Governance Boundary:** Comparison of $4,050 quote (authorized) vs $12,000 quote (escalated).
5. **Human Approval:** Escalation creation, human principal approval, and checkpoint resumption.
6. **Durable Execution & Retry:** Execution of procurement task, transient 429 rate limit retry, and 200 OK recovery.
7. **Audit Trail:** Token counts, cost calculation ($0.00115 USD), egress payload sizes, and telemetry event logs.

For video recording walkthrough script, see [docs/demo-script.md](docs/demo-script.md).

---

## 15. Configuration / Environment Variables

Key variables supported in `.env` (see `.env.example`):

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `SECRET_KEY` | `dev-secret` | Django secret key |
| `USE_SQLITE` | `True` | Set `True` for zero-infra local development |
| `OPENAI_API_KEY` | `""` | OpenAI API key (optional; defaults to Mock) |
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key (optional) |
| `GOOGLE_API_KEY` | `""` | Google Gemini API key (optional) |
| `TAVILY_API_KEY` | `""` | Tavily web search API key (optional) |

---

## 16. Running Tests

Both test suites run locally using SQLite and `fakeredis`:

```bash
# Run all workflow_agent tests (34 tests)
USE_SQLITE=True python manage.py test workflow_agent.tests

# Run workflow_orchestrator test suite (97 tests)
python manage.py test workflow_orchestrator.tests --settings=tests.settings
```

**Total Test Coverage:** 131 tests passing cleanly.

---

## 17. Current Limitations

- **Single-Node Planner:** The planner operates sequentially turn-by-turn rather than multi-agent swarm decomposition.
- **In-Memory Mocking in Demo:** The zero-infra demo uses SQLite and `fakeredis` for standalone reproducibility. Production deployments should use PostgreSQL + Redis cluster.

---

## 18. Proposed GCC Data Sovereignty Architecture Extension

For deployment in GCC jurisdictions (UAE, KSA, Qatar, Oman, Kuwait, Bahrain), see our comprehensive proposal in [docs/gcc-data-sovereignty.md](docs/gcc-data-sovereignty.md):
- **Regional Sovereign Planes:** Physical data plane isolation per region (e.g. AWS me-central-1 UAE).
- **In-Region Model Routing:** Routing sensitive prompts to local open-weights frontier models (Qwen 2.5 72B, DeepSeek V3) self-hosted on regional GPUs.
- **Audit Locality & DLP:** Sovereign log stores with pre-flight cross-border egress DLP checks.
