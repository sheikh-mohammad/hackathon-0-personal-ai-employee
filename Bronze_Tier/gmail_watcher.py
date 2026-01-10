# gmail_watcher.py
import time
import logging
from pathlib import Path
from datetime import datetime

# Import Google API libraries with error handling
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google.auth.exceptions import RefreshError
except ImportError as e:
    print(f"Google API libraries not installed. Please install: pip install google-api-python-client google-auth")
    raise e

from base_watcher import BaseWatcher


class GmailWatcher(BaseWatcher):
    def __init__(self, vault_path: str, credentials_path: str, check_interval: int = 120):
        super().__init__(vault_path, check_interval)
        self.inbox_path = self.vault_path / 'Inbox'
        self.inbox_path.mkdir(exist_ok=True)  # Create Inbox directory if it doesn't exist

        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Load credentials and build service
        try:
            self.creds = Credentials.from_authorized_user_file(credentials_path)
            self.service = build('gmail', 'v1', credentials=self.creds)
        except FileNotFoundError:
            self.logger.error(f"Credentials file not found: {credentials_path}")
            raise
        except RefreshError:
            self.logger.error("Credentials have expired or are invalid. Please re-authenticate.")
            raise

        # Track processed email IDs to prevent duplicates
        self.processed_ids = set()

    def check_for_updates(self) -> list:
        """Check for new unread important emails"""
        try:
            results = self.service.users().messages().list(
                userId='me',
                q='is:unread is:important',
                maxResults=10  # Limit to avoid overwhelming the system
            ).execute()

            messages = results.get('messages', [])
            new_messages = []

            for message in messages:
                if message['id'] not in self.processed_ids:
                    # Get full message details to check if it's really new
                    msg_details = self.service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='minimal'  # Use minimal format for efficiency
                    ).execute()

                    # Add to new messages if it passes all checks
                    new_messages.append({
                        'id': message['id'],
                        'details': msg_details
                    })

            self.logger.info(f"Found {len(new_messages)} new unread important emails")
            return new_messages

        except Exception as e:
            self.logger.error(f"Error checking for email updates: {e}")
            return []

    def create_action_file(self, message_data) -> Path:
        """Create markdown file in Inbox with YAML frontmatter"""
        try:
            message_id = message_data['id']
            msg = message_data['details']

            # Extract headers
            headers = {}
            if 'payload' in msg and 'headers' in msg['payload']:
                headers = {h['name']: h['value'] for h in msg['payload']['headers']}

            # Determine priority based on content
            priority = self._determine_priority(headers, msg.get('snippet', ''))

            # Get email snippet (or body if available)
            snippet = msg.get('snippet', '')

            # Create markdown content with YAML frontmatter
            content = f"""---
type: email
from: {headers.get('From', 'Unknown').replace(':', ';').strip()}
subject: {headers.get('Subject', 'No Subject').replace(':', ';').strip()}
received: {datetime.now().isoformat()}
priority: {priority}
status: pending
---

## Email Snippet
{snippet}

## Suggested Actions
- [ ] Review content and determine appropriate response
- [ ] Take necessary action based on email content
- [ ] Archive or mark as read after processing
"""

            # Create filename with email ID to ensure uniqueness
            filename = f"EMAIL_{message_id}.md"
            filepath = self.inbox_path / filename

            # Write content to file
            filepath.write_text(content, encoding='utf-8')

            # Add to processed IDs to prevent duplicate processing
            self.processed_ids.add(message_id)

            self.logger.info(f"Created action file: {filepath}")
            return filepath

        except Exception as e:
            self.logger.error(f"Error creating action file for message {message_data.get('id', 'unknown')}: {e}")
            raise

    def _determine_priority(self, headers: dict, snippet: str) -> str:
        """Determine email priority based on content"""
        subject = headers.get('Subject', '').lower()
        sender = headers.get('From', '').lower()
        snippet_lower = snippet.lower()

        # Check for high priority indicators
        high_priority_keywords = [
            'urgent', 'asap', 'important', 'deadline', 'invoice',
            'payment', 'money', 'billing', 'due', 'critical'
        ]

        # Combine all text for keyword checking
        all_text = f"{subject} {sender} {snippet_lower}"

        for keyword in high_priority_keywords:
            if keyword in all_text:
                return 'high'

        return 'normal'

    def run(self):
        """Override run method with better error handling"""
        self.logger.info(f'Starting {self.__class__.__name__}')
        while True:
            try:
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)
            except KeyboardInterrupt:
                self.logger.info("Gmail Watcher stopped by user")
                break
            except Exception as e:
                self.logger.error(f'Unexpected error in {self.__class__.__name__}: {e}')
                # Wait before retrying to avoid rapid error loops
                time.sleep(self.check_interval)

            # Sleep for the check interval before next check
            time.sleep(self.check_interval)


if __name__ == "__main__":
    # Example usage - adjust paths as needed
    VAULT_PATH = "."  # Current directory as vault
    CREDENTIALS_PATH = "credentials.json"  # Path to Gmail API credentials

    try:
        watcher = GmailWatcher(VAULT_PATH, CREDENTIALS_PATH)
        watcher.run()
    except Exception as e:
        print(f"Failed to start Gmail Watcher: {e}")
        print("Make sure you have valid Gmail API credentials in credentials.json")