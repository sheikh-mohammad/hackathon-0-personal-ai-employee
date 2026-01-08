# whatsapp_watcher.py
from playwright.sync_api import sync_playwright
from base_watcher import BaseWatcher
from pathlib import Path
import json
import time
from datetime import datetime
import logging


class WhatsAppWatcher(BaseWatcher):
    def __init__(self, vault_path: str, whatsapp_session_dir: str = './whatsapp_session', check_interval: int = 30):
        super().__init__(vault_path, check_interval)
        self.whatsapp_session_dir = Path(whatsapp_session_dir)  # Directory to store WhatsApp-specific session data
        self.inbox = self.vault_path / 'Inbox'
        self.inbox.mkdir(exist_ok=True)  # Create Inbox directory if it doesn't exist
        self.keywords = ['urgent', 'asap', 'invoice', 'payment', 'help', 'emergency', 'critical', 'problem', 'issue']

        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.__class__.__name__)

    def check_for_updates(self) -> list:
        """
        Check WhatsApp Web for new messages and return list of new messages
        """
        messages = []
        try:
            with sync_playwright() as p:
                # Connect to an existing browser instance via Playwright MCP
                # This assumes you have a Playwright MCP server running with the browser extension
                try:
                    # Attempt to connect to an existing browser (requires MCP server setup)
                    # Try common CDP endpoints where Chrome typically runs
                    cdp_endpoints = [
                        "ws://127.0.0.1:9222",  # Default Chrome DevTools Protocol endpoint
                        "http://127.0.0.1:9222",  # Alternative format
                    ]

                    browser = None
                    for endpoint in cdp_endpoints:
                        try:
                            browser = p.chromium.connect_over_cdp(endpoint)
                            self.logger.info(f"Successfully connected to browser at {endpoint}")
                            break
                        except Exception as e:
                            self.logger.debug(f"Failed to connect to {endpoint}: {e}")
                            continue

                    if browser is None:
                        raise Exception("Could not connect to any CDP endpoint")

                    # Get the first available context or create a new one
                    if browser.contexts:
                        # Look for an existing context that might have WhatsApp already loaded
                        context = browser.contexts[0]
                    else:
                        # Create a new context if none exists
                        context = browser.new_context(
                            viewport={'width': 1280, 'height': 800}
                        )
                    used_fallback = False  # Did not use fallback
                except Exception as e:
                    # Fallback: launch a new persistent context if MCP connection fails
                    self.logger.info(f"MCP connection failed ({e}), falling back to persistent context")
                    browser = p.chromium.launch_persistent_context(
                        self.whatsapp_session_dir,  # Use the WhatsApp session directory to maintain login
                        headless=False,  # Set to False so user can see and authenticate if needed
                        viewport={'width': 1280, 'height': 800},
                        # Additional args to ensure WhatsApp session is preserved
                        args=[
                            '--disable-web-security',
                            '--disable-features=VizDisplayCompositor',
                            '--no-sandbox',
                        ]
                    )
                    context = browser
                    used_fallback = True  # Used fallback

                # Get or create a new page
                if context.pages:
                    page = context.pages[0]
                else:
                    page = context.new_page()

                # Navigate to WhatsApp Web
                page.goto('https://web.whatsapp.com')

                # Wait for WhatsApp to load and check if user is already authenticated
                try:
                    # Wait for page to load
                    page.wait_for_load_state('networkidle')

                    # Check if QR code is present (indicating user needs to log in)
                    qr_selector = 'canvas, [data-ref], div[data-animate-new-messages="false"]'
                    try:
                        qr_element = page.wait_for_selector(qr_selector, timeout=5000)
                        # QR code is present, user needs to scan - this is an issue for automated checking
                        self.logger.warning("QR code detected - user needs to authenticate manually")
                        # Wait a bit longer in case authentication happens during this session
                        page.wait_for_timeout(10000)
                    except:
                        # No QR code found, user is likely already logged in
                        self.logger.info("No QR code detected - user appears to be logged in")

                    # Wait for the main chat list container
                    page.wait_for_selector('div[aria-label="Chat list"]', timeout=15000)
                    self.logger.info("WhatsApp Web loaded successfully with authenticated session")
                except:
                    self.logger.warning("WhatsApp Web may still be loading or authentication required")
                    # Wait a bit more for manual authentication if needed
                    page.wait_for_timeout(15000)

                # Find all chat elements that might contain unread messages
                # Using more general selectors that are likely to work
                chat_elements = page.query_selector_all('div[role="row"]')

                for chat_element in chat_elements:
                    try:
                        # Get the chat title (contact/group name)
                        title_element = chat_element.query_selector('div[aria-label] span, span[title], span[dir="auto"]')
                        if title_element:
                            contact_name = title_element.inner_text()
                        else:
                            contact_name = "Unknown Contact"

                        # Get the last message preview
                        message_element = chat_element.query_selector('div[title] span, .selectable-text span')
                        if message_element:
                            message_preview = message_element.inner_text()
                        else:
                            message_preview = ""

                        # Check if this chat has unread messages by looking for unread indicators
                        # Look for elements that indicate unread messages (usually has a different style or class)
                        unread_elements = chat_element.query_selector_all('.unread, .P68oI, [data-icon="muted"]')
                        has_unread = len(unread_elements) > 0

                        # Also check for any element with numeric content (unread count)
                        badge_elements = chat_element.query_selector_all('span[role="button"] span, .P68oI span')
                        has_badge = False
                        for badge in badge_elements:
                            text = badge.inner_text().strip()
                            if text.isdigit() and int(text) > 0:
                                has_badge = True
                                break

                        if has_unread or has_badge:
                            # This chat has unread messages
                            messages.append({
                                'contact': contact_name,
                                'message': message_preview,
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'priority': self._determine_priority(message_preview)
                            })
                    except Exception as e:
                        # More detailed error logging
                        self.logger.error(f"Error processing chat element: {e}")
                        continue

                # Alternative approach: look for unread indicators more broadly
                if not messages:
                    # Look for elements that indicate unread messages
                    unread_chats = page.query_selector_all('.unread, [data-icon="muted"], .P68oI')
                    for unread_chat in unread_chats:
                        try:
                            # Get the text content of the chat containing the unread indicator
                            parent = unread_chat.query_selector('..') or unread_chat  # Get parent element
                            chat_text = parent.inner_text() if parent else "Unread message detected"
                            messages.append({
                                'contact': 'Unknown Contact',
                                'message': chat_text,
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'priority': self._determine_priority(chat_text)
                            })
                        except Exception as e:
                            self.logger.error(f"Error processing unread chat: {e}")
                            continue

                # Close browser only if we used the fallback persistent context method
                # Don't close if we connected via CDP to an existing browser
                if 'used_fallback' in locals() and used_fallback:
                    try:
                        browser.close()
                        self.logger.info("Closed persistent browser context")
                    except Exception as e:
                        self.logger.error(f"Error closing browser: {e}")
                else:
                    # When using CDP connection, don't close the browser as it's managed externally
                    self.logger.info("Connected via CDP - not closing external browser")

        except Exception as e:
            self.logger.error(f"Error checking for WhatsApp updates: {e}")

        return messages

    def _determine_priority(self, message_text: str) -> str:
        """
        Determine message priority based on keywords
        """
        message_lower = message_text.lower()

        # High priority keywords
        high_priority = ['urgent', 'asap', 'emergency', 'immediate', 'critical', 'help', 'problem', 'issue', 'payment']
        medium_priority = ['soon', 'today', 'request', 'please', 'question', 'inquiry', 'details', 'meeting']

        for keyword in high_priority:
            if keyword in message_lower:
                return 'high'

        for keyword in medium_priority:
            if keyword in message_lower:
                return 'medium'

        return 'low'

    def create_action_file(self, message_data) -> Path:
        """
        Create .md file in Inbox folder with the message data
        """
        # Generate a unique filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"WA_{timestamp}.md"
        filepath = self.inbox / filename

        # Create the message file content in the format specified in CLAUDE.md
        message_content = f"""---
type: whatsapp_message
received: {message_data['timestamp']}
status: pending
priority: {message_data['priority']}
contact: {message_data['contact']}
---

## Message
{message_data['message']}
"""

        # Write the message to the file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(message_content)

        self.logger.info(f"Created message file: {filepath}")
        return filepath

    def run(self):
        """
        Override the base run method to create files in Inbox instead of Needs_Action
        """
        self.logger.info(f'Starting {self.__class__.__name__}')
        while True:
            try:
                messages = self.check_for_updates()
                for message in messages:
                    self.create_action_file(message)
                    self.logger.info(f"Processed message from {message['contact']}: {message['message'][:50]}...")
            except Exception as e:
                self.logger.error(f'Error in run loop: {e}')

            # Wait for the specified interval before checking again
            time.sleep(self.check_interval)


def main():
    """
    Main function to run the WhatsApp Watcher
    """
    import sys

    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python whatsapp_watcher.py <vault_path> [whatsapp_session_dir]")
        print("Example 1: python whatsapp_watcher.py ./                    # Use default session directory")
        print("Example 2: python whatsapp_watcher.py ./ ./my_whatsapp_session  # Use specific session directory")
        sys.exit(1)

    vault_path = sys.argv[1]
    whatsapp_session_dir = sys.argv[2] if len(sys.argv) == 3 else './whatsapp_session'

    watcher = WhatsAppWatcher(vault_path, whatsapp_session_dir)
    watcher.run()


if __name__ == "__main__":
    main()