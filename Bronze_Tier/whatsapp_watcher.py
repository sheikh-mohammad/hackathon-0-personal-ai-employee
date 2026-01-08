# whatsapp_watcher.py
from playwright.sync_api import sync_playwright
from base_watcher import BaseWatcher
from pathlib import Path
import json
import time
from datetime import datetime
import logging


class WhatsAppWatcher(BaseWatcher):
    def __init__(self, vault_path: str, chrome_user_data_dir: str | None = None, check_interval: int = 30):
        super().__init__(vault_path, check_interval)
        self.chrome_user_data_dir = Path(chrome_user_data_dir) if chrome_user_data_dir else None
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
                # Prepare browser arguments
                args = [
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--no-sandbox'
                ]

                # Launch with existing profile if user data dir is specified
                if self.chrome_user_data_dir:
                    # Launch with existing Chrome profile - pass user data dir directly as first parameter
                    browser = p.chromium.launch_persistent_context(
                        self.chrome_user_data_dir,  # Pass user data dir directly as the first parameter
                        headless=False,  # Set to False so user can see and authenticate if needed
                        viewport={'width': 1280, 'height': 800},
                        args=args
                    )
                else:
                    # Fallback to the original method if no user data dir specified
                    browser = p.chromium.launch_persistent_context(
                        './whatsapp_session',  # Use a default session dir
                        headless=False,  # Set to False so user can see and authenticate if needed
                        viewport={'width': 1280, 'height': 800},
                        args=args
                    )

                page = browser.pages[0]

                # Navigate to WhatsApp Web
                page.goto('https://web.whatsapp.com')

                # Wait for WhatsApp to load and user to authenticate
                # First wait for the main app container
                try:
                    # Wait for QR code to disappear and chat list to appear
                    page.wait_for_load_state('networkidle')
                    # Wait for the main chat list container
                    page.wait_for_selector('div[aria-label="Chat list"]', timeout=30000)
                    self.logger.info("WhatsApp Web loaded successfully")
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

                browser.close()

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
        print("Usage: python whatsapp_watcher.py <vault_path> [chrome_user_data_dir]")
        print("Example 1: python whatsapp_watcher.py ./                    # Use default session")
        print("Example 2: python whatsapp_watcher.py ./ \"C:/Users/YourName/AppData/Local/Google/Chrome/User Data\"  # Use existing Chrome profile")
        sys.exit(1)

    vault_path = sys.argv[1]
    chrome_user_data_dir = sys.argv[2] if len(sys.argv) == 3 else None

    watcher = WhatsAppWatcher(vault_path, chrome_user_data_dir)
    watcher.run()


if __name__ == "__main__":
    main()