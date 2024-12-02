import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Load environment variables from .env file
load_dotenv()

# Get the path to your credentials.json file
client_secret_file = os.getenv("CLIENT_SECRET_FILE")

# If the client secret file is provided, proceed
if client_secret_file:
    creds = None
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']  # Read-only access to Gmail inbox

    # Check if token.json exists to use stored credentials
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If no valid credentials, go through OAuth2 flow to get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Use OAuth2 flow to authenticate and get credentials
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for future use in token.json
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    # Connect to the Gmail API
    service = build('gmail', 'v1', credentials=creds)

    # Fetch messages from inbox
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], q="newer_than:1d").execute()
    messages = results.get('messages', [])

    # If no new messages, print a message
    if not messages:
        print("No new messages.")
    else:
        print("New messages:")
        # Loop through the messages and fetch the subject and sender
        for message in messages[:15]:  
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg['payload']['headers']
            
            # Get the subject and sender from the headers
            subject = next(header['value'] for header in headers if header['name'] == 'Subject')
            sender = next(header['value'] for header in headers if header['name'] == 'From')
            
            print(f"Subject: {subject}")
            print(f"Sender: {sender}")
else:
    print("Error: CLIENT_SECRET_FILE is not set in .env file.")
