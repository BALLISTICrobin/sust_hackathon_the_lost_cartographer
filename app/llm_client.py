import os
import httpx
import json
import logging
from dotenv import load_dotenv
from app.prompt_builder import SYSTEM_PROMPT

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Primary and fallback keys
KEYS = [
    os.getenv("GROQ_API_KEY"),
    os.getenv("GROQ_FALLBACK_API_KEY")
]
# Filter out None/empty keys
KEYS = [k for k in KEYS if k]

MODELS = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct"
]

def clean_json_response(raw_text: str) -> dict:
    """Aggressively strip markdown block tags to parse JSON."""
    raw_text = raw_text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    elif raw_text.startswith("```"):
        raw_text = raw_text[3:]
        
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
        
    raw_text = raw_text.strip()
    return json.loads(raw_text)

async def call_llm_with_fallback(user_message: str) -> dict:
    if not KEYS:
        raise ValueError("No Groq API keys configured")

    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Content-Type": "application/json"
    }

    last_exception = None
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        # Strategy: Try primary key with primary model. 
        # If rate limit/timeout, try fallback key with primary model.
        # If still fails, try fallback model.
        
        # Sequence of (key, model) to attempt
        attempts = []
        if len(KEYS) > 0:
            attempts.append((KEYS[0], MODELS[0]))
        if len(KEYS) > 1:
            attempts.append((KEYS[1], MODELS[0])) # Key rotation
            attempts.append((KEYS[1], MODELS[1])) # Model fallback
        else:
            attempts.append((KEYS[0], MODELS[1])) # Model fallback if only 1 key

        for key, model in attempts:
            try:
                headers["Authorization"] = f"Bearer {key}"
                payload["model"] = model
                
                response = await client.post(GROQ_URL, json=payload, headers=headers)
                response.raise_for_status()
                
                result_json = response.json()
                raw_content = result_json["choices"][0]["message"]["content"]
                
                return clean_json_response(raw_content)
                
            except httpx.TimeoutException as e:
                logger.warning(f"Timeout with model {model}: {e}")
                last_exception = e
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error {e.response.status_code} with model {model}: {e}")
                last_exception = e
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error with model {model}: {e}")
                last_exception = e
            except Exception as e:
                logger.warning(f"Unexpected error with model {model}: {e}")
                last_exception = e
                
    raise RuntimeError(f"All LLM fallback attempts failed. Last error: {last_exception}")
