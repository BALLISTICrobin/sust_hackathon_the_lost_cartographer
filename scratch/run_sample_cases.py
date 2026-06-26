import json
import urllib.request
import urllib.error
import sys

# Windows compatibility
sys.stdout.reconfigure(encoding='utf-8')

URL = "http://127.0.0.1:8000/analyze-ticket"

def run_cases():
    try:
        with open("SUST_Preli_Sample_Cases.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            cases = data.get("cases", [])
    except Exception as e:
        print(f"Error reading SUST_Preli_Sample_Cases.json: {e}")
        return

    outputs = []
    print(f"Loaded {len(cases)} cases. Running against {URL}...")

    for idx, case_wrapper in enumerate(cases):
        payload = case_wrapper.get("input")
        ticket_id = payload.get("ticket_id")
        print(f"[{idx+1}/{len(cases)}] Sending request for ticket {ticket_id}...")

        try:
            req = urllib.request.Request(
                URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                status_code = response.getcode()
                response_body = response.read().decode('utf-8')
                
            if status_code == 200:
                result = json.loads(response_body)
                outputs.append(result)
                print(f"  ✓ Success")
            else:
                print(f"  ❌ Error HTTP {status_code}: {response_body}")
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            print(f"  ❌ HTTP Error {e.code}: {err_msg}")
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")

    try:
        with open("QueueStorm_Preli_Sample_Cases.json", "w", encoding="utf-8") as f:
            json.dump(outputs, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved {len(outputs)} outputs to QueueStorm_Preli_Sample_Cases.json")
    except Exception as e:
        print(f"Error writing output file: {e}")

if __name__ == "__main__":
    run_cases()
