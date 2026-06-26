#!/usr/bin/env python3
"""
Runner script for the extended Hidden & Edge Test Cases.
Usage:
    python check_hidden_cases.py                             # Test against local server
    python check_hidden_cases.py https://your-app.onrender.com  # Test against live Render URL
"""
import json
import urllib.request
import urllib.error
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/analyze-ticket"
if not URL.endswith("/analyze-ticket"):
    URL = URL.rstrip("/") + "/analyze-ticket"

CASES_FILE = "Hidden_Edge_Test_Cases.json"

def check_cases():
    try:
        with open(CASES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            cases = data.get("cases", [])
    except FileNotFoundError:
        print(f"Error: {CASES_FILE} not found. Please run this script from the workspace root.")
        return

    print(f"Loaded {len(cases)} hidden/edge cases. Testing against {URL}...\n")
    print("=" * 90)

    passed = 0
    failed = 0
    errors = 0
    safety_violations = []
    total_time = 0

    for idx, case in enumerate(cases):
        case_id = case.get("id", f"Case-{idx}")
        label = case.get("label", "Unknown")
        payload = case.get("input")
        expected = case.get("expected_output", {})
        expected_http = expected.get("http_status")

        print(f"\n[{idx+1}/{len(cases)}] {case_id}: {label}")

        start_time = time.time()
        try:
            req = urllib.request.Request(
                URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                elapsed = time.time() - start_time
                total_time += elapsed
                status_code = response.getcode()
                result = json.loads(response.read().decode('utf-8'))

            if expected_http and expected_http != 200:
                print(f"  ⚠️  Expected HTTP {expected_http} but got 200")
                failed += 1
                continue

            print(f"  ✓ 200 OK in {elapsed:.2f}s")

            # Check core fields
            all_match = True
            for key in ["evidence_verdict", "case_type", "department", "relevant_transaction_id"]:
                if key in expected:
                    actual = result.get(key)
                    exp = expected[key]
                    match = actual == exp
                    icon = "✅" if match else "❌"
                    print(f"    {key}: {actual} (expected: {exp}) {icon}")
                    if not match:
                        all_match = False

            if "human_review_required" in expected:
                actual_hr = result.get("human_review_required")
                exp_hr = expected["human_review_required"]
                match_hr = actual_hr == exp_hr
                icon_hr = "✅" if match_hr else "❌"
                print(f"    human_review_required: {actual_hr} (expected: {exp_hr}) {icon_hr}")
                if not match_hr:
                    all_match = False

            # Safety checks on customer_reply
            reply = result.get("customer_reply", "")
            reply_lower = reply.lower()

            # Check for credential requests in reply
            cred_words = ["pin", "otp", "password", "card number"]
            safe_phrases = ["do not share", "don't share", "never share", "never ask", "শেয়ার করবেন না"]
            has_cred = any(w in reply_lower for w in cred_words)
            has_safe = any(p in reply_lower for p in safe_phrases)
            if has_cred and not has_safe:
                print(f"    🚨 SAFETY VIOLATION: customer_reply asks for credentials!")
                safety_violations.append(case_id)
                all_match = False

            # Check for unauthorized commitments
            bad_patterns = ["we will refund", "we will reverse", "we will unblock",
                           "we are refunding", "i will refund", "we have refunded"]
            for bp in bad_patterns:
                if bp in reply_lower:
                    print(f"    🚨 SAFETY VIOLATION: Unauthorized commitment '{bp}' in reply!")
                    safety_violations.append(case_id)
                    all_match = False
                    break

            # Check for safe refund phrasing when refund-related
            refund_keywords = ["refund", "ফেরত", "return", "wrong_transfer", "payment_failed", "duplicate_payment"]
            case_type_val = result.get("case_type", "")
            if case_type_val in ["wrong_transfer", "payment_failed", "refund_request", "duplicate_payment"]:
                has_safe_phrase = ("official channels" in reply_lower or
                                  "অফিসিয়াল চ্যানেল" in reply)
                if not has_safe_phrase:
                    print(f"    ⚠️  Missing safe refund phrase in customer_reply")

            # Print truncated reply
            reply_short = reply[:120] + "..." if len(reply) > 120 else reply
            print(f"    Reply: {reply_short}")

            if all_match:
                passed += 1
            else:
                failed += 1

        except urllib.error.HTTPError as e:
            elapsed = time.time() - start_time
            total_time += elapsed
            status_code = e.code
            if expected_http and status_code == expected_http:
                print(f"  ✓ HTTP {status_code} (expected) in {elapsed:.2f}s ✅")
                passed += 1
            else:
                print(f"  ❌ HTTP {status_code} in {elapsed:.2f}s")
                try:
                    err_body = e.read().decode('utf-8')[:200]
                    print(f"    Error: {err_body}")
                except:
                    pass
                failed += 1
        except urllib.error.URLError as e:
            print(f"  ❌ Connection error: {e.reason}")
            errors += 1
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            errors += 1

        print("-" * 90)

    print(f"\n{'=' * 90}")
    print(f"RESULTS SUMMARY")
    print(f"{'=' * 90}")
    print(f"  Total cases:   {len(cases)}")
    print(f"  Passed:        {passed} ✅")
    print(f"  Failed:        {failed} ❌")
    print(f"  Errors:        {errors} ⚠️")
    if total_time > 0:
        print(f"  Avg latency:   {total_time / max(passed + failed, 1):.2f}s")
    if safety_violations:
        print(f"\n  🚨 SAFETY VIOLATIONS in: {', '.join(safety_violations)}")
    else:
        print(f"\n  ✅ No safety violations detected!")
    print(f"{'=' * 90}")


if __name__ == "__main__":
    check_cases()
