# Employer Presentation Guide & 2–3 Minute Demo Video Script

**Role:** Agentic AI Platform Developer  
**Project:** Bounded Agentic AI Platform Demonstrator (`workflow-agent` + `workflow-orchestrator`)

---

## 1. Top 7 Things to Show on Screen During Demo

1. **User Prompt & Intent Definition:** Bounded goal ("Find best supplier for 100 units of sensors, negotiate within rules, purchase if within $5,000 limit").
2. **Agent Reasoning & Tool Use:** Dynamic tool dispatch (`search_suppliers`, `get_quote`, `check_governance_policy`).
3. **Declarative Plan Generation (5-Array JSON):** Clean boundary separating intelligence from execution.
4. **DAG Cycle Validation:** Topological validation (Kahn's algorithm) ensuring non-cyclical DAG topology.
5. **Bounded Delegation & Governance Escalation:**
   - **Case A ($4,050 quote):** Authorized automatically.
   - **Case B ($12,000 quote):** Escalates -> Platform halts execution and creates human approval request.
6. **Human-in-the-Loop Approval:** Approval via API (`approve_manual_step_view`) triggering checkpoint resume.
7. **Durable Execution & Transient 429 Retry Recovery:**
   - Task hits simulated `429 Rate Limited`.
   - `TaskContinuation` triggers exponential backoff retry.
   - Task succeeds on attempt 2 (`200 OK`).

---

## 2. 2–3 Minute Video Script (Word-for-Word Walkthrough)

### [0:00 – 0:30] Introduction & Architecture Principle
> *"Hi! In this demonstration, I'm showcasing an Agentic AI Platform engineered for bounded, rule-based autonomous delegation.*  
> *Rather than a simple LLM wrapper, this platform separates the **Intelligence & Planning Layer** from a **Durable Execution Substrate**.*  
> *Let's run our zero-infrastructure CLI demonstrator using `python demo.py`."*

### [0:30 – 1:15] Agent Reasoning, Tool Calls & Declarative Plan
> *"Here, a business user prompts the agent to find sensors, negotiate pricing, and execute a purchase if within a $5,000 delegated limit.*  
> *The agent dynamically selects tools: searching suppliers, obtaining a discounted quote of $4,050 from Apex Industrial, and validating governance.*  
> *Notice that instead of directly making arbitrary API calls, the agent emits a **declarative 5-array workflow plan in JSON**.*  
> *Our engine validates the schema and checks for DAG topological cycles using Kahn's algorithm before materializing real database records."*

### [1:15 – 2:00] Bounded Delegation, Governance & Escalation
> *"Now let's observe governance in action. The LLM proposes actions, but the **platform policy engine decides whether execution is authorized**.*  
> *For our $4,050 quote, the engine confirms $4,050 is within the $5,000 limit and authorizes automatic execution.*  
> *If a supplier quote costs $12,000, the governance guard halts execution, creates a durable `ManualStep` record, and pauses the run.*  
> *Once the human principal approves via our API, execution seamlessly resumes from the saved checkpoint."*

### [2:00 – 2:45] Durable Execution, Retry Recovery & Auditability
> *"Under the hood, task execution is handled by our task-based `workflow-orchestrator` engine.*  
> *When the purchase endpoint experiences a transient `429 Rate Limit`, our declarative `TaskContinuation` evaluates the response and automatically executes exponential backoff retry, recovering to a `200 OK` on attempt 2.*  
> *Finally, every reasoning turn, tool call, token cost, and HTTP byte egress is persisted in `AiUsageLog` and `TelemetryLogger` for complete enterprise auditability."*

---

## 3. Key Architectural Points to Explain Verbally

1. **LLM as Planner, Engine as Authority:** The LLM NEVER acts as the security boundary. Policy engines and gatekeepers validate permissions deterministically.
2. **Declarative Plan Intermediate Representation (IR):** The 5-array JSON DSL decouples LLM generation from execution, enabling inspection, cycle detection, and human approval before execution.
3. **Task-Based DAG Orchestration:** The execution layer uses lightweight directed acyclic graphs with Jinja-driven continuations for loops, retries, and pagination.
4. **Self-Referential Planner Topology:** The planner loop itself is constructed as a 2-node orchestrated workflow (`llm-plan` ⇄ `execute-tool`).

---

## 4. Key Code Locations for Technical Interview Inspection

| Feature | Primary File / Class | Key Lines / Functions |
| :--- | :--- | :--- |
| **DAG Traversal Engine** | `workflow_orchestrator/traverser.py` | `WorkflowTraverser.traverse()`, `_handle_continuations()` |
| **LLM Provider Abstraction** | `workflow_agent/llm_client.py` | `complete()`, `_openai_complete()`, `_anthropic_complete()` |
| **Plan DSL & Cycle Validation** | `workflow_agent/dsl.py` | `validate_plan_dsl()`, `_validate_dag_acyclicity()` |
| **AST Code Sanitizer** | `workflow_agent/sanitize.py` | `validate_source()` |
| **Governance Engine** | `workflow_agent/governance.py` | `evaluate_action_policy()`, `guard_transaction_callable()` |
| **Deterministic Mock Server** | `workflow_orchestrator/mock_server.py` | `AiohttpMocker`, `ScenarioBuilder.rate_limited_then_success()` |
| **SSRF Protection Gate** | `workflow_agent/search.py` | `is_ip_allowed()`, `fetch_url_safe()` |
| **CLI Demo Runner** | `workflow_agent/management/commands/demo.py` | `Command.handle()` |
