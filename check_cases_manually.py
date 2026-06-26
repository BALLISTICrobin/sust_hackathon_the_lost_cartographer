import json
import urllib.request
import urllib.error
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

URL = "http://127.0.0.1:8000/analyze-ticket"

def check_cases():
    try:
        with open("SUST_Preli_Sample_Cases.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            cases = data.get("cases", [])
    except FileNotFoundError:
        print("Error: SUST_Preli_Sample_Cases.json not found. Please run this script from the workspace root.")
        return

    print(f"Loaded {len(cases)} sample cases. Checking against {URL}...\n")
    print("=" * 80)
    
    passed_count = 0

    for idx, case_wrapper in enumerate(cases):
        case_id = case_wrapper.get("id", f"Case-{idx}")
        label = case_wrapper.get("label", "Unknown")
        payload = case_wrapper.get("input")
        expected = case_wrapper.get("expected_output", {})
        
        print(f"[{idx+1}/{len(cases)}] Analyzing: {case_id} ({label})")
        
        start_time = time.time()
        try:
            req = urllib.request.Request(
                URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            # Timeout of 30 seconds
            with urllib.request.urlopen(req, timeout=30) as response:
                elapsed = time.time() - start_time
                status_code = response.getcode()
                response_body = response.read().decode('utf-8')
                
            if status_code == 200:
                result = json.loads(response_body)
                
                # Check key matching criteria
                verdict_match = result.get('evidence_verdict') == expected.get('evidence_verdict')
                case_type_match = result.get('case_type') == expected.get('case_type')
                
                print(f"  ✓ API returned 200 OK in {elapsed:.2f}s")
                print(f"  - Actual verdict: {result.get('evidence_verdict')} (Expected: {expected.get('evidence_verdict')}) -> {'✅' if verdict_match else '❌'}")
                print(f"  - Actual case_type: {result.get('case_type')} (Expected: {expected.get('case_type')}) -> {'✅' if case_type_match else '❌'}")
                print(f"  - Department routed to: {result.get('department')}")
                print(f"  - Customer Reply: {result.get('customer_reply')}")
                
                if verdict_match and case_type_match:
                    passed_count += 1
            else:
                print(f"  ❌ API returned HTTP {status_code}")
                print(f"  - Error: {response_body}")
                
        except urllib.error.HTTPError as e:
            elapsed = time.time() - start_time
            print(f"  ❌ API returned HTTP {e.code} in {elapsed:.2f}s")
            try:
                err_body = e.read().decode('utf-8')
                print(f"  - Error response: {err_body}")
            except Exception:
                pass
        except urllib.error.URLError as e:
            print(f"  ❌ Request failed: {e.reason}")
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            
        print("-" * 80)

    print(f"\nManual Check Complete! {passed_count}/{len(cases)} cases showed matching core logic.")

if __name__ == "__main__":
    check_cases()
