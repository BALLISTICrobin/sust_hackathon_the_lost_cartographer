# QueueStorm Investigator

An AI-powered internal copilot for support agents to automate complaint classification, evidence gathering, and response drafting for a digital finance platform.

## Features
- **Evidence-Based Reasoning**: Cross-references customer complaints against transaction history to determine if claims are consistent.
- **Auto-Routing**: Classifies complaints into 8 categories and routes them to 6 specific departments based on strict business logic.
- **Robust Safety Guardrails**: Hardcoded pre-processing (to block prompt injection) and post-processing (to sanitize LLM outputs from credentials or unauthorized refund promises).
- **Multilingual Support**: Supports English, Bangla, and Banglish.
- **High Reliability**: Stateless architecture with API key rotation and model fallback chains.

---

## Setup & Installation

1. **Clone the repository** and navigate to the root directory.
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and insert your Groq API keys:
   ```bash
   cp .env.example .env
   ```
   *Note: Two API keys are recommended to enable key rotation for higher rate limits.*

## Running the API

Start the FastAPI server using Uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. You can view the interactive Swagger documentation at `http://localhost:8000/docs`.

---

## Testing

Run the automated test suite (including the 10 provided sample cases and edge cases):

```bash
python -m pytest tests/test_sample_cases.py -v
```

---

## AI Usage & Prompt Engineering

The system uses a **Chain of Thought (CoT)** prompt engineering strategy to enforce strict reasoning before classification. The LLM is instructed to:
1. Find the relevant transaction by matching amount, time, and counterparty.
2. Determine `evidence_verdict` (consistent/inconsistent).
3. Classify `case_type`.
4. Route to the correct `department`.
5. Draft a safe `customer_reply`.

We inject the full JSON schema into the prompt and use the LLM's native JSON mode to guarantee structured output.

## Safety Logic & Guardrails

To prevent critical safety failures (-15 point penalty), we implemented a multi-layered guardrail system:
1. **Pre-processing (Prompt Injection)**: Checks the incoming complaint for adversarial phrases (e.g., "ignore previous instructions"). If found, the LLM is bypassed entirely, and a safe generic response is returned.
2. **Post-processing (Credentials & Commitments)**: Scans the generated `customer_reply` and `recommended_next_action` for PIN, OTP, password, or credit card numbers. If detected, the field is forcibly rewritten. It also sanitizes unauthorized commitments like "we will refund".
3. **Hard Overrides**: If the model determines a case is high/critical severity, involves fraud, or lacks evidence, `human_review_required` is deterministically set to `True` via Python logic, overriding the LLM's discretion.

## Limitations

- **Statelessness**: The API does not maintain conversation history. Follow-up messages from the same user require the full transaction context to be resent.
- **Latency Spikes**: While the primary model is fast (~1-3s), falling back to secondary models during heavy rate-limiting may push p95 latency closer to 10s.
- **Hallucinated Transactions**: The LLM relies entirely on the provided `transaction_history` array. If an upstream system fails to provide complete history, the model will default to `insufficient_data`.

---

## MODELS

This project utilizes the following models via the **Groq Cloud API** to maximize throughput while minimizing latency:

| Model | Role | Hosted On | Why it was chosen | Estimated Cost |
|---|---|---|---|---|
| `llama-3.3-70b-versatile` | **Primary** | Groq | 70B parameter intelligence is crucial for accurate evidence reasoning and following strict safety/routing rules. Groq provides blazing fast inference for this large model. | $0.00 (Free Tier) |
| `meta-llama/llama-4-scout-17b-16e-instruct` | **Fallback** | Groq | If the primary model hits its 12K Tokens-Per-Minute limit during judge testing, this 17B model absorbs the burst traffic with its higher 30K TPM limit. | $0.00 (Free Tier) |

**Fallback Chain Strategy**: 
1. The system attempts inference with `llama-3.3-70b-versatile` using the Primary API Key.
2. If rate-limited (429), it rotates to the Fallback API Key using the same 70B model.
3. If both keys hit their TPM limits, it dynamically switches to `meta-llama/llama-4-scout-17b-16e-instruct` to guarantee a successful response within the 30s timeout window.
