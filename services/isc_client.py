"""
ISCClient — HTTP client for the ISC Agent API.

Configurable request/response format to adapt to the actual API contract.
Supports retries with exponential backoff and timeout handling.
"""

import time
import json
import requests
from requests_ntlm import HttpNtlmAuth
from typing import Dict, List, Optional
from config.settings import (
    ISC_AGENT_URL,
    ISC_REQUEST_TEMPLATE,
    ISC_RESPONSE_FIELDS,
    ISC_TIMEOUT_SECONDS,
    ISC_MAX_RETRIES,
    ISC_VERIFY_SSL,
)


class ISCClient:
    """
    Client for querying line-down dates and revenue impact from the ISC Agent.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        request_template: Optional[dict] = None,
        response_fields: Optional[dict] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        verify_ssl: Optional[bool] = None,
    ):
        self.base_url = (base_url or ISC_AGENT_URL).rstrip("/")
        self.request_template = request_template or ISC_REQUEST_TEMPLATE
        self.response_fields = response_fields or ISC_RESPONSE_FIELDS
        self.timeout = timeout or ISC_TIMEOUT_SECONDS
        self.max_retries = max_retries or ISC_MAX_RETRIES
        self.verify_ssl = verify_ssl if verify_ssl is not None else ISC_VERIFY_SSL
        self.auth = None

    def set_auth(self, username: str, password: str):
        """Set NTLM auth credentials at runtime (not stored in config).
        
        Uses Windows Integrated Authentication (NTLM) for IIS servers.
        Format: username can be 'DOMAIN\\user' or 'user@domain.com' or just 'user'.
        """
        if username and password:
            # Use NTLM auth for IIS (Basic auth returns 401 on corporate IIS)
            self.auth = HttpNtlmAuth(username, password)

    def clear_auth(self):
        """Clear auth credentials from memory after use."""
        self.auth = None

    def query_parts(self, part_numbers: List[str]) -> Dict[str, dict]:
        """
        Query ISC Agent for line-down date and revenue impact.

        Args:
            part_numbers: List of unique part numbers to query.

        Returns:
            Dict keyed by part_number, each value is:
            {
                "line_down_date": str or None,
                "revenue_impact": float or 0.0,
            }
        """
        if not part_numbers:
            return {}

        # Build request body from template
        payload = self._build_payload(part_numbers)

        # Make request with retries
        response = self._make_request(payload)

        if response is None:
            print(f"  [WARN] ISC Agent request failed after {self.max_retries} retries")
            return {}

        # Parse response
        return self._parse_response(response, part_numbers)

    def _build_payload(self, part_numbers: List[str]) -> dict:
        """Build the JSON request body from the configured template."""
        # Deep copy template to avoid mutating the original
        payload = json.loads(json.dumps(self.request_template))

        # Replace placeholder with actual part numbers
        # Support nested placeholder replacement
        self._replace_placeholders(payload, {"{{PARTS}}": part_numbers})
        return payload

    def _replace_placeholders(self, obj: dict, replacements: dict):
        """Recursively replace string placeholders in a dict."""
        for key, value in obj.items():
            if isinstance(value, dict):
                self._replace_placeholders(value, replacements)
            elif isinstance(value, list):
                obj[key] = [
                    r.get(str(item), item) if isinstance(item, str) else item
                    for r, item in [(replacements, v) for v in value]
                ]
            elif isinstance(value, str) and value in replacements:
                obj[key] = replacements[value]

    def _make_request(self, payload: dict) -> Optional[dict]:
        """POST to ISC Agent with exponential backoff retries."""
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"  [ISC] Querying {len(payload.get('part_numbers', []))} parts (attempt {attempt})...")
                resp = requests.post(
                    self.base_url,
                    json=payload,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                    auth=self.auth,
                )

                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except (json.JSONDecodeError, ValueError):
                        print(f"  [WARN] ISC returned non-JSON: {resp.text[:200]}")
                        return None
                elif resp.status_code == 429:
                    # Rate limited — back off
                    wait_time = 2 ** attempt
                    print(f"  [WARN] Rate limited, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    if attempt < self.max_retries:
                        wait_time = 2 ** attempt
                        print(f"  [WARN] {last_error}, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    break

            except requests.exceptions.Timeout:
                last_error = "Request timed out"
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    print(f"  [WARN] Timeout, retrying in {wait_time}s...")
                    time.sleep(wait_time)
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {e}"
                break  # Don't retry connection errors

        print(f"  [ERROR] ISC Agent: {last_error}")
        return None

    def _parse_response(self, response: dict, expected_parts: List[str]) -> Dict[str, dict]:
        """Parse ISC Agent response using configured field mappings."""
        result = {}

        # Map our field names -> response field names
        field_map = {v: k for k, v in self.response_fields.items()}
        response_part_field = field_map.get("part_number", "part_number")
        response_ld_field = field_map.get("line_down_date", "line_down_date")
        response_rev_field = field_map.get("revenue_impact", "revenue_impact")

        # Handle both list and dict response formats
        items = response
        if isinstance(response, list):
            items = response
        elif isinstance(response, dict):
            # Try common wrapper keys
            for wrapper_key in ("data", "results", "response", "parts"):
                if wrapper_key in response:
                    items = response[wrapper_key]
                    break
            else:
                # Response is a flat dict — treat as single result
                items = [response]

        for item in items:
            if not isinstance(item, dict):
                continue

            part_num = str(item.get(response_part_field, "")).strip()
            if not part_num:
                continue

            line_down = item.get(response_ld_field)
            revenue = item.get(response_rev_field, 0)

            result[part_num] = {
                "line_down_date": str(line_down) if line_down else None,
                "revenue_impact": float(revenue) if revenue else 0.0,
            }

        return result
