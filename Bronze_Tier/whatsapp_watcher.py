# whatsapp_watcher.py
from playwright.sync_api import sync_playwright
from base_watcher import BaseWatcher
from pathlib import Path
import json
import subprocess
from datetime import datetime
import logging
import time


class WhatsAppWatcher:
    def __init__(self, vault_path: str, session_path: str):
        self.vault_path = Path(vault_path)
        self.check_interval = 30  # seconds
        self.session_path = Path(session_path)
        self.inbox_path = Path(vault_path) / 'Inbox'
        self.inbox_path.mkdir(exist_ok=True)
        self.processed_messages = set()
        self.browser = None
        self.page = None

        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Keywords that indicate important messages
        self.keywords = ['urgent', 'asap', 'invoice', 'payment', 'help', 'emergency', 'critical']

    def start_browser(self):
        """Start the persistent browser context"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch_persistent_context(
            str(self.session_path),
            headless=False,  # Changed to False to keep browser visible
            viewport={'width': 1366, 'height': 768}
        )

        # Get or create a page
        self.page = self.browser.pages[0] if self.browser.pages else self.browser.new_page()

        # Navigate to WhatsApp Web
        self.page.goto('https://web.whatsapp.com', wait_until='networkidle')

        # Wait for WhatsApp to load
        try:
            self.page.wait_for_selector('[data-testid="chat-list"]', timeout=15000)
        except:
            # If chat list doesn't load, check if we're not logged in
            if self.page.query_selector('canvas') or self.page.query_selector('div[data-ref]'):
                self.logger.info("Please scan the QR code to log in to WhatsApp Web")
                input("Press Enter after scanning the QR code...")
                self.page.wait_for_selector('[data-testid="chat-list"]', timeout=15000)

        self.logger.info("WhatsApp Web loaded successfully. Browser will remain open for continuous monitoring.")

        # Process any existing unread messages on startup
        self.logger.info("Checking for existing unread messages...")
        initial_messages = self.check_for_updates(initial_check=True)
        for item in initial_messages:
            self.create_action_file(item)
        if initial_messages:
            self.logger.info(f"Processed {len(initial_messages)} existing unread messages on startup.")
        else:
            self.logger.info("No existing unread messages found.")

    def check_for_updates(self, initial_check=False) -> list:
        """Check WhatsApp Web for new unread messages with persistent browser"""
        messages = []

        if not self.page:
            self.logger.error("Browser page not available")
            return messages

        try:
            # Find all chat items
            chat_items = self.page.query_selector_all('[data-testid="conversation"]')

            for chat_item in chat_items:
                try:
                    # Check if chat has unread messages
                    unread_indicator = chat_item.query_selector('[data-testid="unread-count"]')
                    if unread_indicator:
                        # Get chat name
                        chat_name_elem = chat_item.query_selector('[title]') or chat_item.query_selector('div')
                        chat_name = chat_name_elem.get_attribute('title') or chat_name_elem.inner_text().strip() if chat_name_elem else "Unknown"

                        # Click on the chat to view messages
                        chat_item.click()

                        # Wait for messages to load
                        self.page.wait_for_selector('[data-testid="msg-container"]', timeout=5000)

                        # Get all message bubbles in the chat
                        message_bubbles = self.page.query_selector_all('[data-testid="msg"]')

                        for msg_bubble in message_bubbles:
                            # Check if message is from contact (not from me)
                            if msg_bubble.query_selector('[data-pre-plain-text]'):
                                sender_info = msg_bubble.get_attribute('data-pre-plain-text') or ""

                                # Extract message text
                                message_text_elem = msg_bubble.query_selector('span[dir="ltr"]')
                                if message_text_elem:
                                    message_text = message_text_elem.inner_text().strip()

                                    # Check if this message was already processed
                                    message_id = f"{chat_name}_{message_text[:50]}_{len(message_text)}"
                                    # For initial check, don't check if already processed to capture all unread messages
                                    should_process = True
                                    if not initial_check:
                                        should_process = message_id not in self.processed_messages

                                    if should_process:
                                        # Check if message contains important keywords
                                        is_important = any(kw in message_text.lower() for kw in self.keywords)

                                        message_data = {
                                            'chat_name': chat_name,
                                            'message_text': message_text,
                                            'sender_info': sender_info,
                                            'is_important': is_important,
                                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                        }

                                        messages.append(message_data)
                                        # Only add to processed set if not initial check
                                        if not initial_check:
                                            self.processed_messages.add(message_id)

                except Exception as e:
                    self.logger.error(f"Error processing chat: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error during message checking: {e}")
            # Browser might have closed, try to restart
            try:
                self.start_browser()
            except Exception as restart_error:
                self.logger.error(f"Failed to restart browser: {restart_error}")

        return messages

    def create_action_file(self, item) -> Path:
        """Create .md file in Inbox folder with the message"""
        # Create filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"WA_{timestamp}.md"
        filepath = self.inbox_path / filename

        # Create the message file with the required format
        message_content = f"""---
type: whatsapp_message
received: {item['timestamp']}
status: pending
priority: {'high' if item['is_important'] else 'unknown'}
---

## Message
{item['message_text']}

## Sender
{item['chat_name']}

## Additional Info
- From: {item['sender_info']}
- Important: {'Yes' if item['is_important'] else 'No'}
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(message_content)

        self.logger.info(f"Created message file: {filepath}")

        # Run claude code after creating the file
        try:
            result = subprocess.run(['ccr', 'code'], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.logger.info("Successfully executed 'ccr code' command")
            else:
                self.logger.error(f"Error executing 'ccr code': {result.stderr}")
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout executing 'ccr code' command")
        except Exception as e:
            self.logger.error(f"Exception executing 'ccr code': {e}")

        return filepath

    def run(self):
        """Main run loop that keeps the browser open continuously"""
        self.logger.info("Starting WhatsApp Watcher with persistent browser...")

        # Start the browser
        self.start_browser()

        self.logger.info(f"Started monitoring WhatsApp. Checking for new messages every {self.check_interval} seconds. Browser will remain open.")

        while True:
            try:
                items = self.check_for_updates(initial_check=False)
                for item in items:
                    self.create_action_file(item)

                # Wait for the check interval before next check
                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                self.logger.info("Stopping WhatsApp Watcher...")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(self.check_interval)  # Wait before retrying

        # Cleanup when exiting
        self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()


def main():
    """Main function to run the WhatsApp watcher"""
    import os

    # Get vault path from environment or use default
    vault_path = os.getenv('VAULT_PATH', '.')
    session_path = os.getenv('WHATSAPP_SESSION_PATH', './whatsapp_session')

    # Create session directory if it doesn't exist
    Path(session_path).mkdir(parents=True, exist_ok=True)

    # Create watcher instance
    watcher = WhatsAppWatcher(vault_path, session_path)

    # Run the watcher
    watcher.run()


if __name__ == "__main__":
    main()