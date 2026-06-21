import re
import time
import random
import logging
import requests
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("Chatbot.Browser")

class MessengerBrowser:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pw = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    def connect(self):
        """
        Connect to GPM Login / Chrome browser.
        Supports direct CDP connection or GPM API startup.
        """
        conn_config = self.config.get("connection", {})
        mode = conn_config.get("mode", "direct_cdp")
        
        cdp_address = None
        if mode == "gpm_api":
            cdp_address = self._start_gpm_profile()
        else:
            # Direct CDP
            port = self.config.get("gpm_debug_port") or conn_config.get("default_port", 9222)
            cdp_address = f"127.0.0.1:{port}"
            
        if not cdp_address:
            raise ValueError("Could not determine CDP address.")
            
        # Format connection URL
        if not cdp_address.startswith("http://") and not cdp_address.startswith("https://"):
            cdp_url = f"http://{cdp_address}"
        else:
            cdp_url = cdp_address
            
        logger.info(f"Connecting Playwright to browser at {cdp_url}...")
        self.pw = sync_playwright().start()
        
        # Connect over CDP with retries, with automatic force-reboot recovery if it fails
        try:
            self._connect_cdp(cdp_url)
        except Exception as e:
            if mode == "gpm_api":
                logger.warning(f"Initial connection to GPM profile failed: {e}. Attempting force-reboot recovery...")
                # Force-reboot the profile
                profile_id = self.config.get("gpm_profile_id", "").strip().strip('"').strip("'").strip()
                api_url = self.config.get("gpm_api_url", "http://127.0.0.1:9495").rstrip('/')
                
                # Call stop API
                logger.info(f"Sending stop command to GPM for profile: {profile_id}")
                requests.get(f"{api_url}/api/v1/profiles/stop/{profile_id}", timeout=10)
                
                # Kill any remaining chrome processes for this profile
                self._kill_profile_processes(profile_id)
                time.sleep(3.0)
                
                # Start profile again
                logger.info(f"Starting GPM profile again...")
                cdp_address = self._start_gpm_profile()
                if not cdp_address.startswith("http://") and not cdp_address.startswith("https://"):
                    cdp_url = f"http://{cdp_address}"
                else:
                    cdp_url = cdp_address
                    
                # Retry connection
                logger.info(f"Re-connecting Playwright to browser at {cdp_url}...")
                self._connect_cdp(cdp_url)
            else:
                raise e
            
    def _connect_cdp(self, cdp_url: str):
        """Connect to the browser via CDP, select contexts and find the Messenger tab."""
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Connecting to browser via CDP (attempt {attempt}/{max_attempts})...")
                self.browser = self.pw.chromium.connect_over_cdp(cdp_url)
                
                # Select active context
                if self.browser.contexts:
                    self.context = self.browser.contexts[0]
                else:
                    self.context = self.browser.new_context()
                    
                # Find or open messenger page
                self.page = self._find_messenger_page()
                if not self.page:
                    logger.info("Messenger.com is not open. Opening a new tab...")
                    self.page = self.context.new_page()
                    self.page.goto("https://www.messenger.com/", timeout=60000)
                    self.page.wait_for_load_state("domcontentloaded")
                    
                logger.info("Successfully connected to Messenger page.")
                return
            except Exception as e:
                if attempt == max_attempts:
                    logger.error(f"Failed to connect to browser over CDP after {max_attempts} attempts. Error: {e}")
                    raise e
                logger.warning(f"Browser not ready yet (Error: {e}). Retrying in 2.0 seconds...")
                time.sleep(2.0)
        
    def _kill_profile_processes(self, profile_id: str):
        """Find and terminate any orphaned Chrome processes belonging to this specific GPM Profile."""
        import subprocess
        logger.info(f"Checking for any orphaned GPM Chrome processes with user-data containing: {profile_id}...")
        try:
            # Safely target and force-terminate Chromium processes using the profile ID in their command line
            cmd = f"Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | Where-Object {{$_.CommandLine -like '*{profile_id}*'}} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"
            subprocess.run(["powershell", "-Command", cmd], capture_output=True, timeout=10)
            logger.info(f"Orphaned Chrome processes for profile {profile_id} terminated.")
        except Exception as ke:
            logger.warning(f"Error checking/killing profile Chrome processes: {ke}")

    def _start_gpm_profile(self) -> str:
        """Call GPM API to start the profile and return the remote debugging address."""
        api_url = self.config.get("gpm_api_url", "http://127.0.0.1:9495").rstrip('/')
        profile_id = self.config.get("gpm_profile_id")
        if not profile_id:
            raise ValueError("GPM Profile ID must be specified in config or .env when mode is gpm_api.")
            
        # Clean quotes from profile_id if present (strip spaces first so quotes at edge are matched)
        profile_id = profile_id.strip().strip('"').strip("'").strip()
            
        # Try GPM Login Global API path parameter style first: GET /api/v1/profiles/start/{id}
        url_path = f"{api_url}/api/v1/profiles/start/{profile_id}"
        logger.info(f"Starting GPM profile via v1 path API: {profile_id} via {url_path}")
        
        try:
            response = requests.get(url_path, timeout=15)
            if response.status_code == 404:
                raise requests.exceptions.HTTPError("404 Path Parameter Not Supported")
                
            response.raise_for_status()
            res_json = response.json()
            
            # Auto-handle ProfileInUse (common in GPM)
            if not res_json.get("success") and res_json.get("message") == "ProfileInUse":
                logger.warning(f"Profile {profile_id} is already in use. Attempting to stop and clean up...")
                url_stop = f"{api_url}/api/v1/profiles/stop/{profile_id}"
                requests.get(url_stop, timeout=10)
                
                # Force-terminate processes to unlock user-data-dir
                self._kill_profile_processes(profile_id)
                time.sleep(3.0)
                
                # Retry start
                logger.info(f"Retrying start GPM profile via v1 path API: {profile_id}")
                response = requests.get(url_path, timeout=15)
                response.raise_for_status()
                res_json = response.json()
                
            if not res_json.get("success"):
                raise Exception(f"GPM start profile error: {res_json.get('message', 'Unknown')}")
                
            data = res_json.get("data")
            port = None
            if isinstance(data, dict):
                port = data.get("remote_debugging_port") or data.get("port")
                
            if not port:
                # Try finding in root or other fields
                cdp = res_json.get("seleniumRemoteDebugAddress") or (isinstance(data, dict) and data.get("seleniumRemoteDebugAddress"))
                if cdp:
                    logger.info(f"GPM Profile started. CDP Address: {cdp}")
                    return cdp
                raise Exception(f"No port or debug address found in GPM response: {res_json}")
                
            cdp_address = f"127.0.0.1:{port}"
            logger.info(f"GPM Profile started. CDP Address: {cdp_address}")
            return cdp_address
            
        except Exception as e:
            logger.warning(f"Failed to start GPM profile via v1 path API. Error: {e}. Trying query parameter fallback `/api/v1/profiles/start?id=...`")
            
            # Fallback to query parameter v1 API
            url_query = f"{api_url}/api/v1/profiles/start?id={profile_id}"
            try:
                response = requests.get(url_query, timeout=15)
                if response.status_code == 404:
                    raise requests.exceptions.HTTPError("404 Query Parameter Not Supported")
                    
                response.raise_for_status()
                res_json = response.json()
                
                is_success = res_json.get("status") or res_json.get("success")
                if not is_success:
                    raise Exception(f"GPM start profile error: {res_json.get('message', 'Unknown')}")
                    
                cdp_address = res_json.get("seleniumRemoteDebugAddress")
                if not cdp_address:
                    data = res_json.get("data")
                    if isinstance(data, dict):
                        cdp_address = data.get("seleniumRemoteDebugAddress") or data.get("debug_port") or data.get("port")
                
                if not cdp_address:
                    cdp_address = res_json.get("debug_port") or res_json.get("port")
                    
                if not cdp_address:
                    raise Exception(f"No debugging port found in GPM API response: {res_json}")
                    
                logger.info(f"GPM Profile started via query API. CDP Address: {cdp_address}")
                return cdp_address
                
            except Exception as e2:
                logger.warning(f"Failed to start GPM profile via v1 query API. Error: {e2}. Trying API v3 fallback...")
                
                # Fallback to API v3
                url_v3 = f"{api_url}/api/v3/profiles/start?profileId={profile_id}"
                try:
                    response = requests.get(url_v3, timeout=15)
                    response.raise_for_status()
                    res_json = response.json()
                    
                    if not res_json.get("success"):
                        raise Exception(f"GPM start profile error (v3): {res_json.get('message', 'Unknown')}")
                        
                    cdp_address = None
                    data = res_json.get("data")
                    if isinstance(data, dict):
                        cdp_address = data.get("seleniumRemoteDebugAddress") or data.get("debug_port") or data.get("port")
                    
                    if not cdp_address:
                        raise Exception(f"No debugging port found in GPM API response: {res_json}")
                        
                    logger.info(f"GPM Profile started via v3. CDP Address: {cdp_address}")
                    return cdp_address
                except Exception as e3:
                    logger.error(f"Error starting profile via GPM API (v3): {e3}")
                    raise e3
            
    def _find_messenger_page(self) -> Optional[Page]:
        """Look for an open page containing 'messenger.com'."""
        for p in self.context.pages:
            if "messenger.com" in p.url:
                logger.info(f"Found existing Messenger page: {p.url}")
                return p
        return None

    def get_unread_threads(self) -> List[Dict[str, Any]]:
        """
        Scans the sidebar for unread chats.
        Returns a list of dicts: [{"thread_id": "...", "name": "...", "element_selector": "..."}]
        """
        self.page.bring_to_front()
        
        # We run a JavaScript function on the page to find unread threads.
        # This function scans all thread links (a[href*='/t/']) and uses accessibility details
        # or visual indicators (like bold text or blue dots) to determine unread status.
        js_code = r"""
        () => {
            const threads = Array.from(document.querySelectorAll("a[href*='/t/']"));
            const result = [];
            
            threads.forEach((t) => {
                const href = t.getAttribute("href") || "";
                // Extract thread ID
                const match = href.match(/\/t\/([^\\/\\?]+)/);
                if (!match) return;
                const threadId = match[1];
                
                // Get display name (usually the first text or span in the thread)
                // We'll traverse spans to find text
                const spans = Array.from(t.querySelectorAll("span"));
                let name = "";
                if (spans.length > 0) {
                    // Filter out short spans or icon container spans
                    const textSpans = spans.filter(s => s.innerText && s.innerText.trim().length > 0);
                    if (textSpans.length > 0) {
                        name = textSpans[0].innerText.trim();
                    }
                }
                
                // Check if it is unread.
                // Heuristic 1: Check if there's a blue badge dot.
                // In Messenger, unread threads have a blue badge or dot. Let's check for small blue circles.
                let isUnread = false;
                
                // Heuristic 2: Check for spans containing unread indicators
                // Often, unread chat previews have font weight bold. Let's inspect style.
                for (const span of spans) {
                    const style = window.getComputedStyle(span);
                    const isBold = style.fontWeight === "bold" || parseInt(style.fontWeight) >= 600;
                    
                    // The message preview snippet is bolded ONLY if unread.
                    // The sender name is usually semi-bold, so we check if the second text element (the snippet) is bold.
                    // Or we just check if any span that isn't the title has bold text.
                    const text = span.innerText || "";
                    if (isBold && text.length > 0 && text !== name) {
                        isUnread = true;
                    }
                }
                
                // Heuristic 3: Check for elements representing badges
                // Elements that have aria-label="Mark as read" or "Chưa đọc" or have a blue dot shape.
                const unreadIndicator = t.querySelector("[aria-label*='unread']"), 
                      unreadIndicatorVi = t.querySelector("[aria-label*='Chưa đọc']"),
                      unreadIndicatorVi2 = t.querySelector("[aria-label*='chưa đọc']");
                      
                if (unreadIndicator || unreadIndicatorVi || unreadIndicatorVi2) {
                    isUnread = true;
                }
                
                // Alternate: look for small divs with background-color blue
                const divs = Array.from(t.querySelectorAll("div"));
                for (const d of divs) {
                    const bg = window.getComputedStyle(d).backgroundColor;
                    // Blue colors like rgb(0, 132, 255), rgb(45, 136, 255), etc.
                    if (bg.includes("rgb(0,") || bg.includes("rgb(10,") || bg.includes("rgb(45,")) {
                        const rect = d.getBoundingClientRect();
                        // Small dot check
                        if (rect.width > 0 && rect.width < 20 && rect.height > 0 && rect.height < 20) {
                            isUnread = true;
                        }
                    }
                }
                
                if (isUnread) {
                    result.push({
                        thread_id: threadId,
                        name: name,
                        href: href
                    });
                }
            });
            return result;
        }
        """
        try:
            return self.page.evaluate(js_code)
        except Exception as e:
            logger.error(f"Error evaluating findUnreadThreads: {e}")
            return []

    def select_thread(self, thread_id: str):
        """Click on the thread in the sidebar to open the chat window."""
        self.page.bring_to_front()
        selector = f"a[href*='/t/{thread_id}']"
        logger.info(f"Opening chat thread: {thread_id}")
        
        # Click the link
        try:
            self.page.click(selector, timeout=5000)
            time.sleep(1.0) # Wait for page to load chat messages
        except Exception as e:
            logger.warning(f"Could not click thread link {selector} in sidebar. Direct navigating to URL instead...")
            # Fallback: direct navigation to the thread URL
            self.page.goto(f"https://www.messenger.com/t/{thread_id}/", timeout=10000)
            
        self.page.wait_for_load_state("domcontentloaded")
        # Wait a moment for dynamic messages to render
        time.sleep(1.5)

    def get_recipient_name(self) -> str:
        """Extract current recipient name from the chat header or document title."""
        # Method 1: Try document title which is usually "Name | Messenger"
        title = self.page.title()
        if title and "|" in title:
            name = title.split("|")[0].strip()
            if name and name != "Messenger" and name != "Tin nhắn":
                return name
                
        # Method 2: Try scraping from the chat header
        # The top header of the chat role="main" usually contains the user name in a bold span
        try:
            # Look for role="main" header
            header_spans = self.page.locator("div[role='main']").locator("span").all_inner_texts()
            # The first non-empty text in the header is usually the name
            for txt in header_spans:
                if txt.strip() and len(txt.strip()) > 1 and txt.strip() != "Hoạt động":
                    return txt.strip()
        except Exception as e:
            logger.debug(f"Could not extract name from main header: {e}")
            
        return "Unknown User"

    def get_chat_history(self) -> List[Dict[str, Any]]:
        """
        Scrapes the last 20 messages from the active chat window.
        Uses visual position relative to the chat container to distinguish 'me' vs 'them'.
        
        Returns:
            List of message dicts: [{"sender": "me"|"them", "text": "...", "sender_name": "..."}]
        """
        self.page.bring_to_front()
        recipient_name = self.get_recipient_name()
        
        js_code = r"""
        (recipientName) => {
            const main = document.querySelector("div[role='main']");
            if (!main) return [];
            
            const mainRect = main.getBoundingClientRect();
            const mainCenterX = mainRect.left + mainRect.width / 2;
            
            // Find all message bubbles containing text
            // Messenger messages are usually inside div[dir='auto'] inside divs representing messages.
            const textNodes = Array.from(main.querySelectorAll("div[dir='auto']"));
            
            const messages = [];
            textNodes.forEach((node) => {
                // Ensure the node actually contains text and isn't a timestamp or layout text
                const text = node.innerText || "";
                if (!text.trim()) return;
                
                // Let's filter out non-message elements. 
                // Message text is usually nested inside containers representing bubbles.
                // We'll get its bounding box to check alignment.
                const rect = node.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;
                
                // Heuristic: If it's aligned to the right (center of bubble is right of center of main window), it's from 'me'.
                const bubbleCenter = rect.left + rect.width / 2;
                const sender = (bubbleCenter > mainCenterX) ? "me" : "them";
                const sender_name = (sender === "me") ? "Me" : recipientName;
                
                messages.push({
                    sender: sender,
                    sender_name: sender_name,
                    text: text.trim(),
                    y_pos: rect.top // we'll sort messages by vertical position
                });
            });
            
            // Sort messages vertically (from oldest to newest)
            messages.sort((a, b) => a.y_pos - b.y_pos);
            
            // Deduplicate: Playwright sometimes grabs the same message text from nested div[dir='auto']
            const deduped = [];
            let lastText = "";
            let lastSender = "";
            messages.forEach((m) => {
                // If it has identical text and sender, and is very close vertically, skip
                if (m.text === lastText && m.sender === lastSender) {
                    return;
                }
                deduped.push({
                    sender: m.sender,
                    sender_name: m.sender_name,
                    text: m.text
                });
                lastText = m.text;
                lastSender = m.sender;
            });
            
            return deduped;
        }
        """
        try:
            return self.page.evaluate(js_code, recipient_name)
        except Exception as e:
            logger.error(f"Error scraping chat history: {e}")
            return []

    def send_message(self, text: str):
        """Simulate human-like typing and send a message."""
        self.page.bring_to_front()
        
        # Common selectors for the Messenger input box
        input_selectors = [
            "div[role='textbox']",
            "div[aria-label='Tin nhắn']",
            "div[aria-label='Message']",
            "div[contenteditable='true']"
        ]
        
        input_element = None
        for selector in input_selectors:
            try:
                if self.page.locator(selector).first.is_visible():
                    input_element = self.page.locator(selector).first
                    logger.debug(f"Found input box using selector: {selector}")
                    break
            except Exception:
                continue
                
        if not input_element:
            raise Exception("Could not find message input textbox on the page.")
            
        # Click and focus
        input_element.click()
        input_element.focus()
        
        # Simulate dynamic human typing
        # Instead of instantly pasting, we'll write character by character with small random delays
        logger.info("Simulating gõ phím...")
        for char in text:
            input_element.type(char)
            # Random delay between 20ms and 80ms per character to look human-like
            time.sleep(random.uniform(0.02, 0.08))
            
        # Press Enter to send
        logger.info("Sending message (pressing Enter)...")
        self.page.keyboard.press("Enter")
        time.sleep(1.0) # wait a second for send to complete

    def close(self):
        """Close browser resources."""
        if self.browser:
            self.browser.close()
        if self.pw:
            self.pw.stop()
        logger.info("Browser connection closed.")
