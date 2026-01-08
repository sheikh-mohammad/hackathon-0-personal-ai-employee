# WhatsApp AI Employee - Setup Instructions

## Prerequisites

1. Install Node.js (v14 or higher)
2. Install Python 3.7+
3. Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Setting up Playwright MCP (Multi-Connection Protocol)

1. Install Playwright browser extension and MCP server:
```bash
npm init -y
npx @playwright/mcp@latest --install
```

2. Start the Playwright MCP server:
```bash
npx @playwright/mcp@latest --extension
```

3. Launch Chrome browser with remote debugging enabled:
```bash
# On Windows
start chrome --remote-debugging-port=9222 --user-data-dir="C:/temp/chrome_dev_session"

# On macOS
open -n -a "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev_session"

# On Linux
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_dev_session
```

4. Manually log in to WhatsApp Web in the Chrome browser
5. The WhatsApp watcher script will connect to this browser session to monitor messages

## Running the WhatsApp Watcher

```bash
# Basic usage
python whatsapp_watcher.py .

# With custom session directory
python whatsapp_watcher.py . ./my_whatsapp_session
```

## Troubleshooting

- If the script cannot connect to the browser, make sure:
  1. Chrome is running with the `--remote-debugging-port=9222` flag
  2. The Playwright MCP server is running
  3. WhatsApp Web is logged in and accessible in the browser
  4. No firewall or security software is blocking the connection