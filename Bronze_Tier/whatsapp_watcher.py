# whatsapp_watcher.py
from playwright.sync_api import sync_playwright
from base_watcher import BaseWatcher
from pathlib import Path
from datetime import datetime
import time
import logging


class WhatsAppWatcher(BaseWatcher):
    def __init__(self, vault_path: str, check_interval: int = 30):
        super().__init__(vault_path, check_interval)
        self.inbox = self.vault_path / 'Inbox'
        self.inbox.mkdir(exist_ok=True)
        self.logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(level=logging.INFO)

        # Path to your Chrome Default profile
        self.chrome_profile_path = r"C:\Users\Sheikh Mohammad\AppData\Local\Google\Chrome\User Data\Default"

    def check_for_updates(self) -> list:
        messages = []
        try:
            with sync_playwright() as p:
                # Launch Chrome using your Default profile
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=self.chrome_profile_path,
                    headless=False,
                    viewport={'width': 1280, 'height': 800},
                    args=[
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor',
                        '--no-sandbox',
                    ]
                )

                # Get or create page
                page = browser.pages[0] if browser.pages else browser.new_page()

                # Open WhatsApp Web
                page.goto('https://web.whatsapp.com')
                page.wait_for_load_state('networkidle')

                # Wait for main chat list container
                try:
                    page.wait_for_selector('div[aria-label="Chat list"]', timeout=15000)
                    self.logger.info("WhatsApp Web loaded successfully")
                except:
                    self.logger.warning("WhatsApp Web may still be loading or authentication required")
                    page.wait_for_timeout(15000)

                # Get chat rows
                chat_elements = page.query_selector_all('div[role="row"]')

                for chat in chat_elements:
                    try:
                        # Get contact name
                        title_element = chat.query_selector('div[aria-label] span, span[title], span[dir="auto"]')
                        contact_name = title_element.inner_text() if title_element else "Unknown Contact"

                        # Get last message preview
                        message_element = chat.query_selector('div[title] span, .selectable-text span')
                        message_preview = message_element.inner_text() if message_element else ""

                        # Check unread indicators
                        unread_elements = chat.query_selector_all('.unread, .P68oI, [data-icon="muted"]')
                        has_unread = len(unread_elements) > 0

                        # Badge check
                        badge_elements = chat.query_selector_all('span[role="button"] span, .P68oI span')
                        has_badge = any(b.inner_text().strip().isdigit() and int(b.inner_text()) > 0 for b in badge_elements)

                        if has_unread or has_badge:
                            messages.append({
                                'contact': contact_name,
                                'message': message_preview,
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'priority': self._determine_priority(message_preview)
                            })
                    except Exception as e:
                        self.logger.error(f"Error processing chat: {e}")
                        continue

                # Close browser after scraping
                browser.close()
                self.logger.info("Closed browser context")

        except Exception as e:
            self.logger.error(f"Error checking WhatsApp updates: {e}")

        return messages

    def _determine_priority(self, message_text: str) -> str:
        message_lower = message_text.lower()
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
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"WA_{timestamp}.md"
        filepath = self.inbox / filename
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
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(message_content)
        self.logger.info(f"Created message file: {filepath}")
        return filepath

    def run(self):
        self.logger.info(f'Starting {self.__class__.__name__}')
        while True:
            try:
                messages = self.check_for_updates()
                for message in messages:
                    self.create_action_file(message)
                    self.logger.info(f"Processed message from {message['contact']}: {message['message'][:50]}...")
            except Exception as e:
                self.logger.error(f'Error in run loop: {e}')
            time.sleep(self.check_interval)


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python whatsapp_watcher.py <vault_path>")
        sys.exit(1)

    vault_path = sys.argv[1]
    watcher = WhatsAppWatcher(vault_path)
    watcher.run()


if __name__ == "__main__":
    main()
