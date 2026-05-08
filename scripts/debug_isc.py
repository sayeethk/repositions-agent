"""
Debug script: Test ISC Agent API connection and inspect raw response.
"""

import json
import requests
import getpass
from config.settings import (
    ISC_AGENT_URL,
    ISC_REQUEST_TEMPLATE,
    ISC_VERIFY_SSL,
    ISC_TIMEOUT_SECONDS,
)

print("=== ISC Agent Debug ===")
print(f"URL: {ISC_AGENT_URL}")
print(f"SSL Verify: {ISC_VERIFY_SSL}")
print(f"Timeout: {ISC_TIMEOUT_SECONDS}s")
print()

# Prompt for credentials
username = input("ISC Username: ").strip()
password = getpass.getpass("ISC Password: ").strip()

# Test with one part number first
test_parts = ["019-02185-0000"]

# Build payload
payload = json.loads(json.dumps(ISC_REQUEST_TEMPLATE))

# Replace placeholder
def replace_placeholders(obj, replacements):
    for key, value in obj.items():
        if isinstance(value, dict):
            replace_placeholders(value, replacements)
        elif isinstance(value, str) and value in replacements:
            obj[key] = replacements[value]

replace_placeholders(payload, {"{{PARTS}}": test_parts})

print(f"\nRequest Payload: {json.dumps(payload, indent=2)}")
print()

try:
    resp = requests.post(
        ISC_AGENT_URL.rstrip("/"),
        json=payload,
        timeout=ISC_TIMEOUT_SECONDS,
        verify=ISC_VERIFY_SSL,
        auth=(username, password) if username and password else None,
    )

    print(f"Status Code: {resp.status_code}")
    print(f"Headers: {dict(resp.headers)}")
    print()
    print("=== Raw Response ===")
    print(resp.text[:2000])
    print()

    if resp.status_code == 200:
        try:
            data = resp.json()
            print("=== Parsed JSON ===")
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            print("[WARN] Response is not valid JSON")
    else:
        print(f"[ERROR] HTTP {resp.status_code}")

except requests.exceptions.RequestException as e:
    print(f"[ERROR] Request failed: {e}")
