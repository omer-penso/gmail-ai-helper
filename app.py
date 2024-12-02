import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from gpt4all import GPT4All
from tqdm import tqdm

# Load environment variables from .env file
load_dotenv()

# Initialize GPT4All model
gpt_model = GPT4All('Meta-Llama-3-8B-Instruct.Q4_0')


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

    # Initialize a list to store email data
    email_data = []

    # If no new messages, print a message
    if not messages:
        print("No new messages.")
    else:
        # Loop through the messages and fetch the subject and sender
        print(f"Processing {len(messages[:2])} messages...")
        for message in tqdm(messages[:2], desc="Processing Emails"): 
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg['payload']['headers']
            
            # Get the subject and sender from the headers
            subject = next(header['value'] for header in headers if header['name'] == 'Subject')
            sender = next(header['value'] for header in headers if header['name'] == 'From')
            
            # Store email data in a list
            email_data.append({"subject": subject, "sender": sender})

    # Process emails using GPT4All
    for email in tqdm(email_data, desc="Categorizing Emails"):
        subject = email["subject"]
        sender = email["sender"]

        # Define prompts
        category_prompt = f"Categorize this email by what you think fits the most (select just ONE!): Subject: '{subject}', Sender: '{sender}'. Categories: 'University', 'Work Search', 'Shopping', 'Meetings', 'Other'."
        priority_prompt = f"Rank this email by priority (select just ONE!): Subject: '{subject}', Sender: '{sender}'. Possible priorities: 'Urgent', 'Important', 'Normal'."
        response_prompt = f"Does this email require a response? Subject: '{subject}', Sender: '{sender}'. Answer 'Yes' or 'No'."

        # Use GPT4All to generate responses
        with gpt_model.chat_session() as session:
            category = session.generate(category_prompt).strip()
            priority = session.generate(priority_prompt).strip()
            requires_response = session.generate(response_prompt).strip()

        # Update email dictionary with GPT4All results
        email["category"] = category
        email["priority"] = priority
        email["requires_response"] = requires_response

    # Print categorized emails
    for email in email_data:
        print(f"Subject: {email['subject']}")
        print(f"Sender: {email['sender']}")
        print(f"Category: {email['category']}")
        print(f"Priority: {email['priority']}")
        print(f"Requires Response: {email['requires_response']}")
        print("-" * 40)
else:
    print("Error: CLIENT_SECRET_FILE is not set in .env file.")
