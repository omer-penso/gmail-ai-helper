import os
import redis
import json
import hashlib
import matplotlib.pyplot as plt
import collections
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

# Connect to Redis with error handling
try:
    redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
    # Test the connection by pinging Redis
    redis_client.ping()
    print("Connected to Redis successfully.")
except redis.ConnectionError as e:
    print(f"Error: Could not connect to Redis. Details: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")

# Function to generate a cache key based on subject and sender
def generate_cache_key(subject, sender):
    key = f"email:{subject}:{sender}"
    return hashlib.sha256(key.encode()).hexdigest()

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
        iteration_length = 15
        print(f"Processing {len(messages[:iteration_length])} messages...")
        for message in tqdm(messages[:iteration_length], desc="Processing Emails"): 
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

        # Generate cache key
        cache_key = generate_cache_key(subject, sender)
        cached_data = redis_client.get(cache_key)

        if cached_data:
            print(f"Using cached data for: {subject}")
            cached_response = json.loads(cached_data)
            email["category"] = cached_response["category"]
            email["priority"] = cached_response["priority"]
            email["requires_response"] = cached_response["requires_response"]
        else:
            # Define prompts
            category_prompt = f"""Categorize this email by what you think fits the most (select just ONE!): Subject: '{subject}', Sender: '{sender}'. 
                                Categories: 'University', 'Work Search', 'Shopping', 'Meetings', 'Other'
                                IMPORTANT - write only the category, DONT write any expexplanations."""
            priority_prompt = f"""Rank this email by priority (select just ONE!): Subject: '{subject}', Sender: '{sender}'. Possible priorities: 'Urgent', 'Important', 'Normal'
                                IMPORTANT - write only the priority, DONT write any expexplanations."""
            response_prompt = f"Does this email require a response? Subject: '{subject}', Sender: '{sender}'. Answer 'Yes' or 'No'."

            # Use GPT4All to generate responses
            with gpt_model.chat_session() as session:
                category = session.generate(category_prompt).strip('"')
                priority = session.generate(priority_prompt).strip('"')
                requires_response = session.generate(response_prompt).strip('"')

            # Update email dictionary with GPT4All results
            email["category"] = category
            email["priority"] = priority
            email["requires_response"] = requires_response

            # Cache the response in Redis for 4 hours (14400 seconds)
            response_data = {
                "category": category,
                "priority": priority,
                "requires_response": requires_response
            }
            redis_client.setex(cache_key, 14400, json.dumps(response_data))

    # Print categorized emails
    for email in email_data:
        print(f"Subject: {email['subject']}")
        print(f"Sender: {email['sender']}")
        print(f"Category: {email['category']}")
        print(f"Priority: {email['priority']}")
        print(f"Requires Response: {email['requires_response']}")
        print("-" * 40)

    def plot_category_distribution(email_data):
        categories = [email['category'] for email in email_data]
        category_counts = {category: categories.count(category) for category in set(categories)}

        plt.figure(figsize=(7, 7))
        plt.pie(category_counts.values(), labels=category_counts.keys(), autopct='%1.1f%%', startangle=90)
        plt.title('Email Categories Distribution')
        plt.show()

    def response_needed_analysis(email_data):
        requires_response = [email['requires_response'] for email in email_data]
        response_count = collections.Counter(requires_response)

        labels = ['Requires Response', 'Does Not Require Response']
        sizes = [response_count.get('Yes', 0), response_count.get('No', 0)]

        plt.figure(figsize=(7, 7))
        plt.bar(labels, sizes, color=['#ff6666', '#66b3ff'])
        plt.title('Response Needed Analysis')
        plt.xlabel('Response Required')
        plt.ylabel('Count')
        plt.show()

    def calculate_omer_percentage_subject(email_data):
        total_emails = len(email_data)
        omer_emails = sum(1 for email in email_data if 'omer' in email['subject'].lower())  
        omer_percentage = (omer_emails / total_emails) * 100 if total_emails > 0 else 0 
        return omer_percentage


    def plot_omer_percentage_pie(email_data):
        omer_percentage = calculate_omer_percentage_subject(email_data)
        other_percentage = 100 - omer_percentage 

        labels = ['With', 'Without']
        sizes = [omer_percentage, other_percentage]
        colors = ['#ff9999','#66b3ff']

        plt.figure(figsize=(7,7))
        plt.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
        plt.title('Percentage of Emails with "Omer" in Subject')
        plt.axis('equal')  
        plt.show()

    # Call the functions to plot the charts
    plot_category_distribution(email_data)
    response_needed_analysis(email_data)
    plot_omer_percentage_pie(email_data)

else:
    print("Error: CLIENT_SECRET_FILE is not set in .env file.")
