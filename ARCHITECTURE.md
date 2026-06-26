# QueueStorm Investigator — Architecture Overview
> 90-Second Presentation Guide for Hackathon Judges

---

## What It Solves

**QueueStorm Investigator** is an AI-powered copilot for customer support agents at a digital finance platform (e.g., bKash). It automatically reads a customer complaint and their recent transaction history, investigates what actually happened, classifies the ticket, and drafts a safe, compliant reply — all in under 30 seconds.

**Input:** A complaint ticket (English/Bangla/Banglish) + a list of recent transactions  
**Output:** A fully structured JSON analysis: classification, evidence verdict, department routing, agent summary, customer reply

---

## High-Level System Flow

```mermaid
flowchart TD
    A([Client / Test Harness]) -->|POST /analyze-ticket| B[FastAPI — main.py]
    B -->|Validates schema| C{Pydantic Schema\nschemas.py}
    C -->|NaN/Inf rejected| ERR1([400 Bad Request])
    C -->|Valid| D{Safety Pre-Check\nsafety.py}
    D -->|Injection detected| E([Safe Fallback Response\nhuman_review=true])
    D -->|Clean| F[Prompt Builder\nprompt_builder.py]
    F -->|System prompt + User message| G[LLM Client\nllm_client.py]
    G -->|Primary Key + llama-3.3-70b| H{Groq API}
    H -->|Success| I[Raw LLM JSON]
    H -->|429 / Timeout| J[Key Rotation\nFallback Key + 70b]
    J -->|Still fails| K[Model Fallback\nFallback Key + llama-4-scout-17b]
    K --> I
    I -->|Unstructured JSON| L[Post-Process Safety\nsafety.py]
    L --> M[AnalyzeTicketResponse\nschemas.py]
    M -->|JSON| A
```

---

## Module-by-Module Breakdown

### 1. `app/schemas.py` — Schema Validation Gate
The very first thing that runs. Uses **Pydantic** to enforce strict input contracts:
- `NaN`/`Infinity` in transaction `amount` fields are **rejected** at parse time (`allow_inf_nan: False`)
- All enum fields (`type`, `status`, `channel`, `language`) use `Literal` typing — invalid values return a clean `400`
- The `reasoning` field in the response is schema-captured but **excluded from the final output** to keep the API clean

### 2. `app/safety.py` — Pre-Processing (Injection Shield)
Runs **before** the LLM sees anything:
- Scans complaint text for injection keywords: `"ignore previous instructions"`, `"system prompt"`, `"override"`, etc.
- If detected → immediately returns a **hard-coded safe fallback** with `human_review_required: true`, bypassing LLM entirely

### 3. `app/prompt_builder.py` — Context Assembly
Builds the complete prompt sent to the LLM:
- Auto-detects language (English / Bangla via Unicode range `U+0980–U+09FF` / Mixed) and injects language directive
- Injects **Chain-of-Thought instructions**: read transactions → match by amount/time/type → determine verdict → classify → route → draft reply
- Includes **hard routing rules** and **safety constraints** directly in the system prompt
- Serializes the full transaction history as JSON entries

### 4. `app/llm_client.py` — Resilient Groq API Client
Implements a **3-tier fallback chain** to handle rate limits and timeouts:

```mermaid
flowchart LR
    A[Attempt 1] -->|Primary Key + llama-3.3-70b| G1{Groq}
    G1 -->|429 / Timeout| B[Attempt 2]
    B -->|Fallback Key + llama-3.3-70b| G2{Groq}
    G2 -->|Still fails| C[Attempt 3]
    C -->|Fallback Key + llama-4-scout-17b| G3{Groq}
    G3 --> D([Parsed JSON Response])
    G1 -->|Success| D
```

- All calls use `temperature: 0.0` for deterministic, consistent outputs
- `response_format: json_object` enforces structured JSON from the LLM
- Aggressively strips markdown code fences before parsing

### 5. `app/safety.py` — Post-Processing (6-Layer Safety Stack)

This is the most complex and critical component. It runs **after** the LLM responds and applies 6 sequential layers of correction:

```mermaid
flowchart TD
    LLM[Raw LLM Response] --> L0
    L0["Layer 0: Programmatic Case Type Override
    keyword + user_type + channel signals"]
    L0 --> L1
    L1["Layer 1: Evidence Verdict Validation
    evaluate_evidence as fallback oracle"]
    L1 --> L1a{LLM tx_id exists\nin history?}
    L1a -->|Yes + prog agrees| V1[Trust prog verdict]
    L1a -->|Yes + prog disagrees| V2[Trust LLM verdict]
    L1a -->|No / hallucinated| V3[Use prog result or insufficient_data]
    V1 & V2 & V3 --> L1b
    L1b["Layer 1b: Transaction Type Guard
    case_type vs tx.type mismatch → null"]
    L1b --> L2
    L2["Layer 2: Credential Request Check
    is_credential_request on complaint + reply"]
    L2 -->|PIN/OTP detected| F2[Route to fraud_risk\nSanitize reply]
    L2 -->|Clean| L3
    L3["Layer 3: Unauthorized Commitment Check
    we will refund / we will reverse etc."]
    L3 -->|Promise detected| F3[Replace with safe phrasing]
    L3 -->|Clean| L4
    L4["Layer 4: Third-Party Redirect Check
    Unknown phone numbers / external URLs"]
    L4 -->|Redirect detected| F4[Replace customer reply]
    L4 -->|Clean| L5
    L5["Layer 5: Hard human_review_required = true
    Always set — conservative escalation guarantee"]
    L5 --> L6
    L6["Layer 6: Programmatic Routing Map Override
    ROUTING_MAP enforces case_type to department"]
    L6 --> OUT([Safe, Validated Response])
```

---

## Case-Type Routing Reference

| `case_type` | `department` | Evidence Trigger | Severity |
|---|---|---|---|
| `phishing_or_social_engineering` | `fraud_risk` | PIN/OTP/scam keywords | `critical` |
| `wrong_transfer` | `dispute_resolution` | Tx to non-established recipient | `high` |
| `payment_failed` | `payments_ops` | Failed/pending tx matching amount | `medium` |
| `duplicate_payment` | `payments_ops` | Two identical txs within 60s | `high` |
| `merchant_settlement_delay` | `merchant_operations` | Settlement tx + delay claim | `medium` |
| `agent_cash_in_issue` | `agent_operations` | Cash-in/out tx + agent context | `medium` |
| `refund_request` | `customer_support` | Payment tx + product/delivery keywords | `low–medium` |
| `other` | `customer_support` | Vague / no matching tx | `low` |

---

## Evidence Verdict Decision Logic

```mermaid
flowchart TD
    S([Start: complaint + transactions]) --> E1{Any transactions\nprovided?}
    E1 -->|No| R1[insufficient_data]
    E1 -->|Yes| E2{Explicit tx_id\nin complaint text?}
    E2 -->|Yes, type matches| E3{wrong_transfer?\nEstablished recipient?}
    E3 -->|Yes — known contact| R2[inconsistent]
    E3 -->|No — new contact| R3[consistent]
    E2 -->|No| E4{Amount mentioned\nmatches 1 tx?}
    E4 -->|Yes, single match| E5{wrong_transfer?\nPrior txs to same counterparty?}
    E5 -->|Yes| R2
    E5 -->|No| R3
    E4 -->|Multiple matches| E6{Same amount + same counterparty\nwithin 60s + duplicate keyword?}
    E6 -->|Yes| R4[consistent — duplicate payment]
    E6 -->|No| R1
    E4 -->|No match| R1
```

---

## Multilingual Support

The system handles complaints in three languages transparently:

| Language | Detection Method | Response Language |
|---|---|---|
| **English** | Default / no Bengali Unicode | English |
| **Bangla** | Unicode range U+0980–U+09FF | বাংলা |
| **Banglish** | `language: "mixed"` field | Mixed Bangla+English |

Bengali numerals (e.g., `১২০০`) are normalized to ASCII (`1200`) before all programmatic comparisons.

---

## Deployment Architecture

```mermaid
flowchart LR
    subgraph Render["Render Cloud"]
        API["FastAPI\nuvicorn :8000"]
    end
    subgraph External["External Services"]
        GROQ["Groq Cloud\nLLaMA 3.3 70B / LLaMA 4 Scout"]
        KA["keep_alive.py\nPing every 14 min"]
    end
    KA -->|GET /health| API
    Client -->|POST /analyze-ticket| API
    API -->|HTTPS| GROQ
    GROQ -->|JSON response| API
```

- **Docker:** Multi-stage build for a minimal, reproducible container
- **keep_alive.py:** Pings `/health` every 14 minutes to prevent Render free-tier cold starts
- **Environment Variables:** `GROQ_API_KEY` + `GROQ_FALLBACK_API_KEY` — zero secrets in code

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **LLM for classification, Python for verification** | LLMs excel at understanding intent; Python is deterministic for amount/date matching |
| **`evaluate_evidence` as validation fallback** | Prevents LLM hallucinating a non-existent transaction ID |
| **`human_review_required` always `true`** | Conservative copilot — never acts autonomously, always escalates |
| **Temperature 0.0** | Eliminates randomness for consistent, auditable outputs |
| **3-tier key+model fallback** | Doubles throughput capacity on Groq free tier, avoids downtime |
| **Pydantic `Literal` enums** | Catches invalid LLM enum outputs at the schema boundary, not at runtime |

---

## Live Endpoint

```
POST  https://sust-hackathon-preli-the-lost.onrender.com/analyze-ticket
GET   https://sust-hackathon-preli-the-lost.onrender.com/health
```
