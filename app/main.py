from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

from app.schemas import AnalyzeTicketRequest, AnalyzeTicketResponse
from app.prompt_builder import build_prompt
from app.llm_client import call_llm_with_fallback
from app.safety import check_prompt_injection, get_safe_fallback_response, post_process_safety

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="QueueStorm Investigator", version="1.0.0")

# Exception Handlers for Robustness
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a clean 400 response for malformed JSON instead of crashing."""
    return JSONResponse(
        status_code=400,
        content={"detail": "Malformed input or missing required fields", "errors": exc.errors()}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Return a clean 500 response for any other unhandled errors."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error. Analysis generation failed."}
    )

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/analyze-ticket", response_model=AnalyzeTicketResponse)
async def analyze_ticket(request: AnalyzeTicketRequest):
    ticket_id = request.ticket_id
    
    # 1. Pre-process check for prompt injection
    if check_prompt_injection(request.complaint):
        logger.info(f"Prompt injection detected for ticket {ticket_id}")
        safe_resp = get_safe_fallback_response(ticket_id)
        return AnalyzeTicketResponse(**safe_resp)
        
    # 2. Build LLM prompt
    request_dict = request.model_dump()
    user_message = build_prompt(request_dict)
    
    # 3. Call LLM with fallback
    try:
        raw_llm_response = await call_llm_with_fallback(user_message)
    except Exception as e:
        logger.error(f"LLM call failed for ticket {ticket_id}: {e}")
        # Return a 500 error if all fallbacks fail
        raise e
        
    # 4. Post-process safety checks and overrides
    safe_dict = post_process_safety(raw_llm_response, request_dict)
    
    # Ensure ticket_id echoes the input precisely
    safe_dict["ticket_id"] = ticket_id
    
    # 5. Validate and return
    return AnalyzeTicketResponse(**safe_dict)
