# Proposed Architectural Extension: GCC Data Sovereignty & Regional Multi-Tenant Data Planes

## Executive Context
This document outlines the proposed target architecture to evolve the Agentic AI Platform for deployment in the **Gulf Cooperation Council (GCC)** market (UAE, KSA, Qatar, Bahrain, Kuwait, Oman).

It explicitly distinguishes between **Implemented Today in MVP** and **Proposed Regional Architecture for Enterprise GCC Deployment**.

---

## 1. Implemented Today vs. Proposed Architecture

| Architectural Dimension | Implemented Today (MVP) | Proposed GCC Extension |
| :--- | :--- | :--- |
| **Tenant Model** | Logical tenant isolation via `Organization` ID FKs | Regional Tenant Assignment & Physical Data Plane Isolation |
| **Database** | Multi-tenant PostgreSQL with row-level tenant filtering | Regional Isolated PostgreSQL Instances (e.g. UAE Data Plane, KSA Data Plane) |
| **State & Caching** | Shared Redis instance with namespaced keys | Isolated In-Region Redis Clusters per Sovereign Zone |
| **LLM Model Routing** | Provider abstraction (OpenAI, Anthropic, Gemini, Mock) | Regional LLM Gateway with In-Region Self-Hosted Frontier Models (Qwen, DeepSeek, Llama 3) |
| **Audit Log Locality** | Centralized `AiUsageLog` and `DataEgressLog` tables | Local Sovereign Log Store with strict regional boundary enforcement |
| **Data Egress Control** | Outbound HTTP SSRF Gate (`is_ip_allowed`) | Pre-Flight DLP (Data Loss Prevention) Inspection & Cross-Border Block Filters |

---

## 2. Regional Data Plane Topology

```
                      +------------------------------------------+
                      |         Global Control Plane             |
                      |   - Tenant Identity & Auth Gateway       |
                      |   - Billing & Platform Metadata          |
                      +--------------------+---------------------+
                                           |
                   +-----------------------+-----------------------+
                   |                                               |
                   v                                               v
     +---------------------------+                   +---------------------------+
     |   UAE Sovereign Zone      |                   |   KSA Sovereign Zone      |
     |   (Dubai / Abu Dhabi)     |                   |   (Riyadh Region)         |
     |                           |                   |                           |
     |  +---------------------+  |                   |  +---------------------+  |
     |  | Regional Agent API  |  |                   |  | Regional Agent API  |  |
     |  +----------+----------+  |                   |  +----------+----------+  |
     |             |             |                   |             |             |
     |  +----------v----------+  |                   |  +----------v----------+  |
     |  | Regional Postgres   |  |                   |  | Regional Postgres   |  |
     |  | & Redis Storage     |  |                   |  | & Redis Storage     |  |
     |  +---------------------+  |                   |  +---------------------+  |
     |             |             |                   |             |             |
     |  +----------v----------+  |                   |  +----------v----------+  |
     |  | In-Region LLM       |  |                   |  | In-Region LLM       |  |
     |  | Inference Gateway   |  |                   |  | Inference Gateway   |  |
     |  | (Hosted Qwen/Llama) |  |                   |  | (Self-Hosted Model) |  |
     |  +---------------------+  |                   |  +---------------------+  |
     +---------------------------+                   +---------------------------+
```

---

## 3. Core Sovereignty Pillars

### A. Regional Data Planes & Tenant Assignment
- Each `Organization` is permanently assigned a `home_region` (e.g., `gcc-uae-1` or `gcc-ksa-1`) upon onboarding.
- All primary databases, Redis caches, worker queues, and execution context checkpoints reside strictly inside cloud data centers located within that sovereign jurisdiction (e.g. AWS me-central-1 in UAE or me-south-1 in KSA).

### B. Credential Isolation
- Integration credentials (`Credential` models) and API keys are stored encrypted using KMS keys managed within the customer's home region.
- Credentials never leave the regional worker pool.

### C. In-Region Model Routing Policies
- To comply with local data protection regulations (e.g. UAE CAPI / KSA NDMO regulations), prompts containing Customer Personally Identifiable Information (PII) or confidential procurement data must NOT be transmitted to foreign frontier LLM endpoints.
- The `llm_client.py` model abstraction routes requests to **in-region self-hosted open-weights models** (e.g., Qwen 2.5 72B, DeepSeek V3, or Llama 3.3 70B deployed on regional GPU instances) or sovereign cloud endpoints.

### D. Audit Log Locality
- All `AiUsageLog`, `DataEgressLog`, `TelemetryLogger` records, and Agent Transcripts remain localized in the regional database.
- Global control plane receives aggregated usage metrics (token counts, transaction totals) for billing purposes, stripping all prompt content and customer payloads.

### E. Cross-Border Egress DLP Enforcement
- Before executing any outbound HTTP task (`HttpExecutor`), a **Pre-Flight DLP Filter** inspects request parameters and headers to block unauthorized cross-border egress of protected sovereign data fields.
