import re
from typing import Dict, Any
from datetime import datetime

# Normalize Bengali digits to English
def normalize_bengali_digits(text: str) -> str:
    bn_to_en = {
        '০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
        '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'
    }
    for bn, en in bn_to_en.items():
        text = text.replace(bn, en)
    return text

def contains_bengali(text: str) -> bool:
    return bool(re.search(r'[\u0980-\u09FF]', text))

def detect_language(request_dict: Dict[str, Any]) -> str:
    lang = request_dict.get("language")
    if lang in ["bn", "en"]:
        return lang
    complaint = request_dict.get("complaint", "")
    if contains_bengali(complaint):
        return "bn"
    return "en"

# Pre-processing prompt injection check
def check_prompt_injection(complaint: str) -> bool:
    """
    Returns True if prompt injection is detected in the complaint text.
    """
    lower_complaint = complaint.lower()
    injection_patterns = [
        "ignore previous instructions",
        "you are now",
        "disregard the above",
        "forget your rules",
        "system prompt",
        "override"
    ]
    for pattern in injection_patterns:
        if pattern in lower_complaint:
            return True
    return False

def get_safe_fallback_response(ticket_id: str) -> Dict[str, Any]:
    """
    Returns a safe, generic response when prompt injection is detected.
    """
    return {
        "ticket_id": ticket_id,
        "relevant_transaction_id": None,
        "evidence_verdict": "insufficient_data",
        "case_type": "other",
        "severity": "low",
        "department": "customer_support",
        "agent_summary": "Complaint contains suspicious or adversarial formatting. Flagged for standard manual review.",
        "recommended_next_action": "Review the customer's request manually and respond through standard support channels.",
        "customer_reply": "Thank you for reaching out. A support agent will review your request shortly. Please do not share your PIN or OTP with anyone.",
        "human_review_required": True,
        "confidence": 1.0,
        "reason_codes": ["prompt_injection_detected", "fallback_safety_triggered"]
    }

def evaluate_evidence(complaint: str, transaction_history: list, case_type: str) -> tuple:
    """
    Programmatically determines (relevant_transaction_id, evidence_verdict).
    """
    if not transaction_history:
        return None, "insufficient_data"
        
    complaint_norm = normalize_bengali_digits(complaint.lower())
    
    # 1. First scan for explicit transaction ID in the complaint
    for tx in transaction_history:
        tx_id = tx.get("transaction_id")
        if tx_id and tx_id.lower() in complaint_norm:
            # Check for wrong_transfer established recipient pattern
            if case_type == "wrong_transfer":
                counterparty = tx.get("counterparty")
                prior_txs = [
                    t for t in transaction_history
                    if t.get("transaction_id") != tx_id
                    and t.get("counterparty") == counterparty
                    and t.get("status") == "completed"
                    and t.get("type") in ["transfer", "payment"]
                ]
                if prior_txs:
                    return tx_id, "inconsistent"
            return tx_id, "consistent"

    # 2. Extract potential amount values from complaint
    numbers = re.findall(r'\b\d+(?:\.\d+)?\b', complaint_norm)
    amounts = []
    for num in numbers:
        try:
            amounts.append(float(num))
        except ValueError:
            pass
            
    # Filter transaction history for matches
    matching_txs = []
    for tx in transaction_history:
        tx_amount = tx.get("amount")
        if tx_amount is not None:
            for amt in amounts:
                if abs(tx_amount - amt) < 0.01:
                    matching_txs.append(tx)
                    break
                    
    if not matching_txs:
        return None, "insufficient_data"
        
    if len(matching_txs) == 1:
        tx = matching_txs[0]
        tx_id = tx.get("transaction_id")
        
        # Check established recipient pattern
        if case_type == "wrong_transfer":
            counterparty = tx.get("counterparty")
            prior_txs = [
                t for t in transaction_history
                if t.get("transaction_id") != tx_id
                and t.get("counterparty") == counterparty
                and t.get("status") == "completed"
                and t.get("type") in ["transfer", "payment"]
            ]
            if prior_txs:
                return tx_id, "inconsistent"
                
        # Non-completed/pending/failed status matches customer reporting issue
        status = tx.get("status")
        if status in ["failed", "pending"]:
            return tx_id, "consistent"
        return tx_id, "consistent"
        
    # If multiple matching transactions exist:
    # Check if they are identical duplicate payments (same amount, counterparty, type, status) close in time
    first_tx = matching_txs[0]
    all_identical = True
    for tx in matching_txs[1:]:
        if (tx.get("amount") != first_tx.get("amount") or
            tx.get("counterparty") != first_tx.get("counterparty") or
            tx.get("type") != first_tx.get("type") or
            tx.get("status") != first_tx.get("status")):
            all_identical = False
            break
            
    if all_identical and len(matching_txs) >= 2:
        try:
            sorted_txs = sorted(matching_txs, key=lambda t: t.get("timestamp", ""))
            t1 = datetime.fromisoformat(sorted_txs[0].get("timestamp", "").replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(sorted_txs[-1].get("timestamp", "").replace("Z", "+00:00"))
            time_diff = (t2 - t1).total_seconds()
        except Exception:
            time_diff = 999999
            sorted_txs = matching_txs
            
        duplicate_keywords = ["twice", "double", "two times", "দ্বিগুণ", "দুইবার", "duplicate", "deducted twice"]
        has_dup_keyword = any(kw in complaint_norm for kw in duplicate_keywords)
        
        if time_diff <= 60 and has_dup_keyword:
            # Duplicate payment detected, point to the second transaction
            return sorted_txs[-1].get("transaction_id"), "consistent"
            
    # Ambiguous transactions
    return None, "insufficient_data"

def is_credential_request(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    
    cred_words = ["pin", "otp", "password", "card number", "card_number", "কার্ড নম্বর", "পাসওয়ার্ড", "ওটিপি", "পিন"]
    if not any(w in text_lower for w in cred_words):
        return False
        
    # Exclude safe warning phrases
    safe_phrases = [
        "do not share", "don't share", "never share", "no share", "never ask", "don't ask", "won't ask",
        "শেয়ার করবেন না", "জিজ্ঞেস করবে না", "চাইবে না", "বলবেন না"
    ]
    if any(p in text_lower for p in safe_phrases):
        return False
        
    return True

def get_safe_customer_reply(language: str) -> str:
    if language == "bn":
        return "আপনার অনুরোধটি পর্যালোচনা করা হচ্ছে। যেকোনো যোগ্য পরিমাণ অফিসিয়াল চ্যানেলের মাধ্যমে ফেরত দেওয়া হবে। অনুগ্রহ করে আপনার পিন বা ওটিপি কারো সাথে শেয়ার করবেন না।"
    else:
        return "Your request is under review. Any eligible amount will be returned through official channels. Please do not share your PIN or OTP with anyone."

def get_safe_next_action(language: str) -> str:
    if language == "bn":
        return "ম্যানুয়ালি টিকিট বিশদ পর্যালোচনা করুন এবং স্ট্যান্ডার্ড অপারেটিং পদ্ধতি অনুযায়ী সমাধান করুন।"
    else:
        return "Review the ticket details manually and resolve according to standard operational procedures."

def post_process_safety(response_dict: Dict[str, Any], request_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies safety checks, programmatic overrides, and hard review rules.
    """
    complaint = request_dict.get("complaint", "")
    transaction_history = request_dict.get("transaction_history", [])
    case_type = response_dict.get("case_type", "other")
    language = detect_language(request_dict)
    
    # 1. Programmatically determine relevant_transaction_id and evidence_verdict
    prog_tx_id, prog_verdict = evaluate_evidence(complaint, transaction_history, case_type)
    response_dict["relevant_transaction_id"] = prog_tx_id
    response_dict["evidence_verdict"] = prog_verdict

    customer_reply = response_dict.get("customer_reply", "")
    next_action = response_dict.get("recommended_next_action", "")
    
    # 2. Safety Rule Type 1: Credential Request Check
    if is_credential_request(customer_reply) or is_credential_request(next_action):
        response_dict["customer_reply"] = get_safe_customer_reply(language)
        response_dict["recommended_next_action"] = get_safe_next_action(language)
        
    # 3. Safety Rule Type 2: Unauthorized Commitment Check
    unauthorized_patterns = [
        r'we will refund', r'we will reverse', r'we will unblock',
        r'we are refunding', r'we are reversing', r'i will refund',
        r'i will reverse', r'i will unblock', r'we have refunded',
        r'we have reversed', r'we have unblocked', r'রিফান্ড করব',
        r'রিভার্স করব', r'আনব্লক করব', r'ফেরত দেব'
    ]
    has_unauthorized = False
    for pattern in unauthorized_patterns:
        if re.search(pattern, customer_reply, re.IGNORECASE) or re.search(pattern, next_action, re.IGNORECASE):
            has_unauthorized = True
            break
            
    if has_unauthorized:
        response_dict["customer_reply"] = get_safe_customer_reply(language)
        response_dict["recommended_next_action"] = get_safe_next_action(language)
        
    # 4. Safety Rule Type 3: Suspicious Third-Party Redirect Check
    # Match any phone numbers (except the official 16247 or 16245) or external links
    phone_pattern = re.compile(r'\b(?!16247|16245)\d{5,}\b')
    url_pattern = re.compile(r'https?://[^\s]+')
    
    has_redirect = (
        phone_pattern.search(customer_reply) or phone_pattern.search(next_action) or
        url_pattern.search(customer_reply) or url_pattern.search(next_action)
    )
    if has_redirect:
        response_dict["customer_reply"] = get_safe_customer_reply(language)
        response_dict["recommended_next_action"] = get_safe_next_action(language)

    # 5. Hard overrides for human_review_required
    severity = response_dict.get("severity", "low")
    evidence_verdict = response_dict.get("evidence_verdict", "consistent")
    confidence = response_dict.get("confidence", 1.0)
    
    if confidence is None:
        confidence = 1.0

    needs_review = False
    if severity in ["high", "critical"]:
        needs_review = True
    if case_type in ["wrong_transfer", "phishing_or_social_engineering", "duplicate_payment"]:
        needs_review = True
    if evidence_verdict in ["inconsistent", "insufficient_data"]:
        needs_review = True
    if confidence < 0.6:
        needs_review = True
        
    if needs_review:
        response_dict["human_review_required"] = True

    return response_dict
