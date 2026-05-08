"""
ISCChatClient — Selenium-based browser automation for the ISC Agent chat UI.

Automates Chrome to:
1. Navigate to ISC Agent URL
2. Paste part numbers into chat input
3. Send query and wait for AI response
4. Parse response table for line-down dates and revenue impact
"""

import csv
import os
import re
import time
from typing import Dict, List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from config.settings import ISC_AGENT_URL


class ISCChatClient:
    """
    Automates the ISC Agent chat interface via Selenium + Chrome.
    """

    def __init__(self, url: Optional[str] = None):
        self.url = (url or ISC_AGENT_URL).rstrip("/")
        self.driver = None
        self.wait = None
        # Set up download directory
        self.download_dir = os.path.abspath("./downloads")
        os.makedirs(self.download_dir, exist_ok=True)

    def launch(self) -> bool:
        """Launch Chrome and navigate to ISC Agent."""
        try:
            options = Options()
            # Do NOT use headless - user may need to handle login/CAPTCHA
            # options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1280,960")
            # Configure auto-download to our directory
            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            }
            options.add_experimental_option("prefs", prefs)

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.wait = WebDriverWait(self.driver, 30)

            print(f"  [ISC] Launching Chrome, navigating to {self.url}...")
            self.driver.get(self.url)

            # Wait for chat input to appear (indicates page is ready)
            # Try common selectors for chat input elements
            input_selectors = [
                "textarea",
                "input[type='text']",
                "input[type='search']",
                "[role='textbox']",
                ".chat-input",
                ".input-box",
            ]

            input_found = False
            for selector in input_selectors:
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    input_found = True
                    print(f"  [OK] ISC Agent loaded (found input: {selector})")
                    break
                except:
                    continue

            if not input_found:
                print("  [WARN] Could not locate chat input. Page may need manual login.")
                print("  [INFO] Please wait for the page to fully load, then press Enter to continue...")
                input()

            return True

        except Exception as e:
            print(f"  [ERROR] Failed to launch ISC Agent: {e}")
            return False

    def query_parts(self, part_numbers: List[str]) -> Dict[str, dict]:
        """
        Query ISC Agent for all part numbers in a single chat message.

        Pastes all part numbers, sends query, parses response table.
        """
        if not self.driver:
            print("  [ERROR] Browser not launched. Call launch() first.")
            return {}

        if not part_numbers:
            return {}

        # Build query message - Column format (one part per line)
        parts_text = "\n".join(part_numbers)
        query = (
            f"Query open sales orders for these parts and provide a downloadable CSV file.\n"
            f"The CSV must include these exact columns:\n"
            f"Part, Customer Name, Linedown Date, Revenue Impact (USD), Open PO Qty\n\n"
            f"Parts:\n{parts_text}\n\n"
            f"Requirements:\n"
            f"- One row per open sales order\n"
            f"- Linedown Date = Requested Delivery Date from the order\n"
            f"- Revenue Impact = Order value in USD\n"
            f"- Open PO Qty = Open quantity on the order\n"
            f"- If a part has NO open orders, include it with 0 values\n"
            f"- Provide the result as a downloadable CSV file\n"
        )

        print(f"  [ISC] Sending query for {len(part_numbers)} parts...")

        # Clear previous downloads
        for f in os.listdir(self.download_dir):
            if f.endswith('.csv'):
                os.remove(os.path.join(self.download_dir, f))

        # Type query into chat input
        self._send_query(query)

        # Wait for response
        response_text = self._wait_for_response()

        # Check for CSV download (ISC Agent often provides data as downloadable CSV)
        csv_data = self._check_csv_download()
        if csv_data:
            print(f"  [OK] Found CSV download with {len(csv_data)} rows")
            return self._parse_csv_data(csv_data, part_numbers)

        if not response_text:
            print("  [WARN] No response received from ISC Agent")
            return {}

        # Parse text response
        return self._parse_response(response_text, part_numbers)

    def _send_query(self, query: str):
        """Type query into chat input and send.
        
        Uses JavaScript to set value instead of send_keys to avoid triggering
        early sends on newline characters.
        """
        # Find the chat input element
        input_selectors = [
            "textarea",
            "input[type='text']",
            "input[type='search']",
            "[role='textbox']",
        ]

        input_elem = None
        for selector in input_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed() and elem.is_enabled():
                        input_elem = elem
                        break
                if input_elem:
                    break
            except:
                continue

        if not input_elem:
            print("  [ERROR] Could not find chat input element")
            return

        # Use JavaScript to set the value - avoids triggering on-newline send events
        self.driver.execute_script(
            "arguments[0].value = arguments[1];",
            input_elem,
            query
        )
        
        # Dispatch input event to notify the framework
        self.driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
            input_elem
        )
        
        time.sleep(0.5)

        # Send by pressing Enter (Keys.ENTER, not newline char)
        input_elem.send_keys(Keys.ENTER)

        # Also try clicking send button if exists
        send_selectors = [
            "button[type='submit']",
            ".send-button",
            "[aria-label='Send']",
        ]
        for selector in send_selectors:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                if btn.is_displayed():
                    btn.click()
                    break
            except:
                continue

    def _wait_for_response(self, timeout: int = 120) -> Optional[str]:
        """Wait for AI response and extract text.
        
        Strategy: Extract text from .message-body elements within .message assistant divs.
        ISC Agent HTML structure:
        <div class="message assistant">
          <div class="message-role"><span>AGENT</span></div>
          <div class="message-body">...actual response...</div>
        </div>
        """
        print(f"  [ISC] Waiting for ISC Agent response (up to {timeout}s)...")

        start_time = time.time()
        last_response_length = 0

        while time.time() - start_time < timeout:
            try:
                # Extract text from assistant message bodies only
                assistant_bodies = self.driver.find_elements(
                    By.CSS_SELECTOR, ".message.assistant .message-body"
                )
                
                response_text = ""
                for elem in assistant_bodies:
                    if elem.is_displayed():
                        text = elem.text.strip()
                        if text and len(text) > 50:
                            response_text += text + "\n"
                
                response_text = response_text.strip()
                response_len = len(response_text)

                # Save page source for debugging (first iteration only)
                if last_response_length == 0:
                    page_source = self.driver.page_source
                    with open("./debug_isc_page.html", "w", encoding="utf-8") as f:
                        f.write(page_source)
                    print(f"  [DEBUG] Saved page source to ./debug_isc_page.html ({len(page_source)} chars)")

                # Check if response contains a table (look for tab-separated data with part numbers)
                has_table = bool(re.search(r'\d+-\d+\t', response_text))
                
                # Wait for substantial response that's stable (not growing)
                # Track stability: how many consecutive checks showed same length
                if response_len == last_response_length and last_response_length > 300:
                    # Response is stable - track how long
                    if not hasattr(self, '_stable_start'):
                        self._stable_start = time.time()
                    stable_duration = time.time() - self._stable_start
                    
                    # Accept after 30s of stability (ISC Agent takes a long time for tool calls)
                    if stable_duration > 30:
                        print(f"  [OK] Response received ({response_len} chars) - stable for {stable_duration:.0f}s")
                        return response_text
                    elif stable_duration > 5:
                        print(f"  [ISC] stable... {elapsed}s elapsed, {remaining}s remaining ({response_len} chars, stable: {stable_duration:.0f}s)")
                else:
                    # Response changed - reset stability counter
                    if hasattr(self, '_stable_start'):
                        del self._stable_start
                
                last_response_length = response_len
                elapsed = int(time.time() - start_time)
                remaining = timeout - elapsed
                print(f"  [ISC] waiting... {elapsed}s elapsed, {remaining}s remaining ({response_len} chars)")
                time.sleep(5)

            except Exception as e:
                print(f"  [WARN] Error waiting for response: {e}")
                time.sleep(5)

        print("  [WARN] Timeout waiting for ISC Agent response")
        # On timeout, return whatever we have if it's substantial
        if last_response_length > 300:
            print(f"  [OK] Using partial response ({last_response_length} chars) after timeout")
            # Return the last response we got
            assistant_bodies = self.driver.find_elements(
                By.CSS_SELECTOR, ".message.assistant .message-body"
            )
            partial = ""
            for elem in assistant_bodies:
                if elem.is_displayed():
                    text = elem.text.strip()
                    if text and len(text) > 50:
                        partial += text + "\n"
            if partial.strip():
                return partial.strip()
        return None

    def _check_csv_download(self, wait_time: int = 15) -> List[dict]:
        """Check if ISC Agent provided a downloadable CSV file.
        
        Checks both our download directory and user's Downloads folder.
        """
        print(f"  [ISC] Checking for CSV download (up to {wait_time}s)...")
        
        # Check multiple possible download locations
        download_dirs = [
            self.download_dir,  # ./downloads/
            os.path.expanduser("~/Downloads"),  # User's Downloads
        ]
        
        start_time = time.time()
        while time.time() - start_time < wait_time:
            for dl_dir in download_dirs:
                if not os.path.exists(dl_dir):
                    continue
                csv_files = [f for f in os.listdir(dl_dir) if f.endswith('.csv')]
                if csv_files:
                    # Sort by modification time (newest first)
                    csv_files.sort(key=lambda f: os.path.getmtime(os.path.join(dl_dir, f)), reverse=True)
                    csv_path = os.path.join(dl_dir, csv_files[0])
                    # Only use files created after we started the query
                    if os.path.getmtime(csv_path) > start_time - 5:
                        print(f"  [OK] Found CSV: {csv_files[0]} (in {dl_dir})")
                        
                        # Parse CSV
                        data = []
                        try:
                            with open(csv_path, 'r', encoding='utf-8') as f:
                                reader = csv.DictReader(f)
                                for row in reader:
                                    data.append(row)
                        except Exception as e:
                            print(f"  [WARN] Error reading CSV: {e}")
                            continue
                        
                        if data:
                            return data
            
            time.sleep(1)
        
        return []

    def _parse_csv_data(self, csv_data: List[dict], expected_parts: List[str]) -> Dict[str, dict]:
        """Parse CSV data from ISC Agent download.
        
        Expected CSV format:
        Part,CustomerCode,RequestedDeliveryDate,EstimatedShipDate,OpenQuantity,OpenValueUSD,Status
        3060735-1,0000318198,2026-05-11,2026-05-11,0.0,0.0000,Future
        897476-8,0000311356,2026-09-14,2026-09-14,3.0,12296.1000,Future
        """
        result = {}
        
        for row in csv_data:
            part_num = row.get('Part', '').strip()
            if not part_num:
                continue
            
            # Get line-down date (use EstimatedShipDate or RequestedDeliveryDate)
            line_down = row.get('EstimatedShipDate', '').strip()
            if not line_down:
                line_down = row.get('RequestedDeliveryDate', '').strip()
            
            # Get revenue impact
            revenue_str = row.get('OpenValueUSD', '0').strip()
            try:
                revenue = float(revenue_str) if revenue_str else 0.0
            except ValueError:
                revenue = 0.0
            
            # Aggregate by part number (some parts have multiple orders)
            if part_num in result:
                existing = result[part_num]
                # Sum revenue
                existing['revenue_impact'] += revenue
                # Keep earliest line-down date
                if line_down and (not existing['line_down_date'] or line_down < existing['line_down_date']):
                    existing['line_down_date'] = line_down
            else:
                result[part_num] = {
                    "line_down_date": line_down if line_down else None,
                    "revenue_impact": revenue,
                }
        
        # Mark any remaining expected parts that weren't found
        for part in expected_parts:
            if part not in result:
                result[part] = {
                    "line_down_date": None,
                    "revenue_impact": 0.0,
                }
        
        parsed_count = sum(1 for d in result.values() if d['line_down_date'] or d['revenue_impact'] > 0)
        print(f"  [OK] Parsed {len(result)} parts from CSV ({parsed_count} with data)")
        for part, data in result.items():
            ld = data['line_down_date'] or "No line-down"
            rev = data['revenue_impact']
            print(f"    {part}: {ld}, ${rev:,.2f}")
        
        return result

    def _parse_response(self, response_text: str, expected_parts: List[str]) -> Dict[str, dict]:
        """Parse ISC Agent response to extract line-down dates and revenue.
        
        ISC Agent table format (Maricopa):
        Part\tLine Down Date Range\tTotal Open Qty\tRevenue Impact\tCustomer(s)
        897476-8\tSep 12, 2022 - Sep 14, 2026\t50 units\t$207,490\tPT Dirgantara Indonesia
        3060735-1\tMay 11, 2026\t0 units\t$0\tStandard Aero
        
        Parts with NO Open Sales Orders (21 parts):
        3060735-5, 3060735-8, ...
        """
        result = {}

        # Save raw response for debugging
        with open("./debug_isc_response.txt", "w", encoding="utf-8") as f:
            f.write(response_text)
        print(f"  [DEBUG] Saved raw response to ./debug_isc_response.txt ({len(response_text)} chars)")

        # Split response into lines for easier parsing
        lines = response_text.split('\n')
        
        # Look for table section - detect header with "Part" and "Line Down"
        in_table = False
        in_no_orders = False
        
        for i, line in enumerate(lines):
            original = line
            line = line.strip()
            if not line:
                continue
                
            # Detect table header
            if 'Part' in line and 'Line Down' in line and 'Revenue Impact' in line:
                in_table = True
                in_no_orders = False
                print(f"  [DEBUG] Found table header at line {i}: {line[:80]}")
                continue
            
            # Detect "Parts with NO Open Sales Orders" section
            if 'NO Open Sales Orders' in line or 'Parts with NO' in line:
                in_table = False
                in_no_orders = True
                print(f"  [DEBUG] Found 'No Open Orders' section at line {i}")
                continue
            
            # Parse table rows (tab-separated)
            if in_table:
                tab_parts = line.split('\t')
                if len(tab_parts) >= 4:
                    part_num = tab_parts[0].strip()
                    # Match part numbers like 897476-8 or 3060735-1
                    if re.match(r'\d+-\d+', part_num):
                        line_down = tab_parts[1].strip()
                        # revenue is column 3 (0-indexed)
                        revenue_str = tab_parts[3].strip().replace('$', '').replace(',', '')
                        
                        try:
                            revenue = float(revenue_str) if revenue_str and revenue_str != '0' else 0.0
                        except ValueError:
                            revenue = 0.0
                        
                        # Handle date ranges - extract the earliest date
                        if ' - ' in line_down:
                            # "Sep 12, 2022 - Sep 14, 2026" -> use the range as-is
                            pass
                        
                        result[part_num] = {
                            "line_down_date": line_down if line_down and line_down.upper() not in ('N/A', 'NONE') else None,
                            "revenue_impact": revenue,
                        }
                        print(f"  [DEBUG] Parsed row: {part_num} -> {line_down}, ${revenue:,.2f}")
                        continue
                else:
                    # Non-tab line in table section - might be end of table
                    if not re.match(r'\d+-\d+', line):
                        in_table = False
            
            # Parse "No Open Orders" parts (comma-separated)
            if in_no_orders:
                # Lines like: "3060735-5, 3060735-8, 3060735-6, ..."
                for part in line.split(','):
                    part = part.strip()
                    if re.match(r'\d+-\d+', part):
                        if part not in result:
                            result[part] = {
                                "line_down_date": None,
                                "revenue_impact": 0.0,
                            }
                            print(f"  [DEBUG] Parsed no-order part: {part}")
                # Check if we've left the no-orders section
                if not re.match(r'\d+-\d+', line):
                    in_no_orders = False

        # Mark any remaining expected parts that weren't found
        for part in expected_parts:
            if part not in result:
                result[part] = {
                    "line_down_date": None,
                    "revenue_impact": 0.0,
                }

        parsed_count = sum(1 for d in result.values() if d['line_down_date'] or d['revenue_impact'] > 0)
        print(f"  [OK] Parsed {len(result)} parts ({parsed_count} with data)")
        for part, data in result.items():
            ld = data['line_down_date'] or "No line-down"
            rev = data['revenue_impact']
            print(f"    {part}: {ld}, ${rev:,.2f}")

        return result

    def close(self):
        """Close the browser."""
        if self.driver:
            print("  [ISC] Closing browser...")
            self.driver.quit()
            self.driver = None
            self.wait = None
