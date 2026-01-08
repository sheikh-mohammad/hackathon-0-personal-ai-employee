# WhatsApp Message Analyzer AI Employee

## How to Run the WhatsApp Watcher

### Prerequisites

1. **Install Python Dependencies**:
   ```bash
   pip install playwright
   ```

2. **Install Playwright Browsers**:
   ```bash
   playwright install chromium
   ```

### Setup

1. **Required Directories** (should be created automatically but ensure they exist):
   ```
   Bronze_Tier/
   ├── Inbox/              # New incoming WhatsApp messages
   ├── Needs_Action/       # Messages flagged for analysis
   ├── Done/               # Completed analyses
   └── whatsapp_session/   # WhatsApp Web session storage (created automatically)
   ```

2. **Initial WhatsApp Web Login**:
   - Run the script for the first time
   - A browser window will open showing WhatsApp Web
   - Scan the QR code with your phone to log in
   - Once logged in, the session will be saved for future use

### Running the Script

```bash
python whatsapp_watcher.py
```

### How It Works

1. The script monitors WhatsApp Web for unread messages using Playwright
2. When an unread message is detected, it creates a `.md` file in the `Inbox/` folder
3. The file contains the message content and metadata in the required format
4. The AI employee will then process these files according to the instructions in `CLAUDE.md`

### Expected File Format

The script creates files in the following format in the `Inbox/` folder:

```markdown
---
type: whatsapp_message
received: 2026-01-08 14:30:52
status: pending
priority: unknown
sender: Contact Name
---

## Message
[Customer's WhatsApp message text here]
```

### Important Notes

- The script needs to remain running to continuously monitor for new messages
- Make sure WhatsApp Web stays logged in on your computer
- The script will automatically create the required directory structure if it doesn't exist
- Session data is stored in the `whatsapp_session` folder to persist login between runs
- Only unread messages are captured and saved to the Inbox folder

### Troubleshooting

- If the script fails to detect messages, check that WhatsApp Web is properly loaded in the browser
- If you get selector errors, the script uses multiple fallback selectors to adapt to WhatsApp Web's changing layout
- Make sure you have the latest version of Chrome/Chromium installed for Playwright
- On first run, make sure to complete the WhatsApp Web login process by scanning the QR code