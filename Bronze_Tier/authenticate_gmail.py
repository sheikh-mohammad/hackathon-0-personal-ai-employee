#!/usr/bin/env python3
"""
Script to authenticate with Gmail API and create token.json file
This script will guide you through the OAuth flow to create the required token.json file.
"""

import os
import pickle
from pathlib import Path

from google.auth.transport.requests import Request  # type: ignore
from google.oauth2.credentials import Credentials  # type: ignore
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
from googleapiclient.discovery import build  # type: ignore

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate():
    """Authenticate with Gmail API and save credentials to token.json"""
    creds = None

    # Check if token.json already exists
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Could not refresh expired credentials: {e}")
                # If refresh fails, delete the token file and start fresh
                if os.path.exists('token.json'):
                    os.remove('token.json')
                creds = None

        if not creds:
            # Load client credentials from credentials.json
            if not os.path.exists('credentials.json'):
                print("Error: credentials.json file not found!")
                print("Please make sure you have downloaded the credentials file from Google Cloud Console.")
                return False

            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    print("Authentication successful! token.json has been created.")
    print("You can now run the Gmail Watcher.")

    # Test the connection
    try:
        service = build('gmail', 'v1', credentials=creds)
        # Try a simple API call to verify everything works
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        print(f"Successfully connected to Gmail API. Found {len(labels)} labels.")
        return True
    except Exception as e:
        print(f"Error testing Gmail API connection: {e}")
        return False

if __name__ == '__main__':
    authenticate()