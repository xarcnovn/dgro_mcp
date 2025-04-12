#!/usr/bin/env python3
"""
Gmail Manager for Business Finder Assistant

This module provides functions to interact with Gmail using the Gmail API.
It allows sending emails, retrieving unread emails, and replying to emails.
"""

import os
import base64
import pickle
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import re
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Load environment variables
load_dotenv()

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

def get_gmail_service():
    """
    Create a Gmail API service object.
    
    Returns:
        A Gmail API service object.
    """
    creds = None
    credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    
    # Check if token.pickle exists (stored credentials)
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If credentials don't exist or are invalid, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_file):
                raise FileNotFoundError(f"Credentials file '{credentials_file}' not found. Run setup_gmail_api.py first.")
            
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)

def send_email(to, subject, body, cc=None, bcc=None):
    """
    Send an email using Gmail API.
    
    Args:
        to (str): Recipient email address
        subject (str): Email subject
        body (str): Email body (HTML format supported)
        cc (str, optional): CC recipients
        bcc (str, optional): BCC recipients
        
    Returns:
        dict: Response from the Gmail API
    """
    try:
        service = get_gmail_service()
        
        # Create message
        message = MIMEMultipart()
        message['to'] = to
        message['subject'] = subject
        
        if cc:
            message['cc'] = cc
        if bcc:
            message['bcc'] = bcc
            
        # Add body as HTML
        message.attach(MIMEText(body, 'html'))
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Send message
        sent_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        print(f"Email sent successfully. Message ID: {sent_message['id']}")
        return {
            'success': True,
            'message_id': sent_message['id'],
            'status': 'Email sent successfully'
        }
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_unread_emails(max_results=10):
    """
    Retrieve unread emails from Gmail.
    
    Args:
        max_results (int): Maximum number of emails to retrieve
        
    Returns:
        list: List of unread email messages with sender, subject, snippet, and message ID
    """
    try:
        service = get_gmail_service()
        
        # Search for unread emails
        results = service.users().messages().list(
            userId='me',
            q='is:unread',
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        
        if not messages:
            print("No unread messages found.")
            return []
        
        unread_emails = []
        
        for message in messages:
            msg = service.users().messages().get(
                userId='me',
                id=message['id'],
                format='full'
            ).execute()
            
            # Extract headers
            headers = msg['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
            
            # Extract thread ID
            thread_id = msg['threadId']
            
            # Format date
            try:
                parsed_date = datetime.strptime(date.split(' +')[0].strip(), '%a, %d %b %Y %H:%M:%S')
                formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            except:
                formatted_date = date
            
            # Extract email body
            body = ""
            if 'parts' in msg['payload']:
                for part in msg['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
            elif 'body' in msg['payload'] and 'data' in msg['payload']['body']:
                body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')
            
            unread_emails.append({
                'id': message['id'],
                'thread_id': thread_id,
                'sender': sender,
                'subject': subject,
                'date': formatted_date,
                'snippet': msg['snippet'],
                'body': body
            })
        
        return unread_emails
        
    except Exception as e:
        print(f"Error retrieving unread emails: {str(e)}")
        return []

def reply_to_email(message_id, reply_body):
    """
    Reply to an email using Gmail API.
    
    Args:
        message_id (str): ID of the message to reply to
        reply_body (str): Body of the reply message
        
    Returns:
        dict: Response from the Gmail API
    """
    try:
        service = get_gmail_service()
        
        # Get the original message to extract headers
        original_message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='metadata',
            metadataHeaders=['Subject', 'From', 'To', 'Message-ID', 'References', 'In-Reply-To']
        ).execute()
        
        # Extract headers
        headers = original_message['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
        recipient = next((h['value'] for h in headers if h['name'].lower() == 'to'), '')
        message_id_header = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), '')
        references = next((h['value'] for h in headers if h['name'].lower() == 'references'), message_id_header)
        
        # Extract email address from sender
        sender_email = re.search(r'<(.+?)>', sender)
        if sender_email:
            sender_email = sender_email.group(1)
        else:
            sender_email = sender
        
        # Create reply message
        message = MIMEMultipart()
        message['to'] = sender_email
        
        # Check if subject already has Re: prefix
        if not subject.lower().startswith('re:'):
            message['subject'] = f"Re: {subject}"
        else:
            message['subject'] = subject
            
        # Set references and in-reply-to headers for proper threading
        if references:
            message['References'] = references
        message['In-Reply-To'] = message_id_header
        
        # Add body
        message.attach(MIMEText(reply_body, 'html'))
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Send message
        sent_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message, 'threadId': original_message['threadId']}
        ).execute()
        
        print(f"Reply sent successfully. Message ID: {sent_message['id']}")
        return {
            'success': True,
            'message_id': sent_message['id'],
            'status': 'Reply sent successfully'
        }
        
    except Exception as e:
        print(f"Error sending reply: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def mark_as_read(message_id):
    """
    Mark an email as read.
    
    Args:
        message_id (str): ID of the message to mark as read
        
    Returns:
        dict: Response from the Gmail API
    """
    try:
        service = get_gmail_service()
        
        # Remove UNREAD label
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        
        print(f"Message {message_id} marked as read.")
        return {
            'success': True,
            'status': 'Message marked as read'
        }
        
    except Exception as e:
        print(f"Error marking message as read: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_email_thread(thread_id):
    """
    Get all messages in an email thread.
    
    Args:
        thread_id (str): ID of the thread to retrieve
        
    Returns:
        list: List of messages in the thread
    """
    try:
        service = get_gmail_service()
        
        # Get thread
        thread = service.users().threads().get(
            userId='me',
            id=thread_id
        ).execute()
        
        messages = []
        
        for message in thread['messages']:
            # Extract headers
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
            
            # Format date
            try:
                parsed_date = datetime.strptime(date.split(' +')[0].strip(), '%a, %d %b %Y %H:%M:%S')
                formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            except:
                formatted_date = date
            
            # Extract email body
            body = ""
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
            elif 'body' in message['payload'] and 'data' in message['payload']['body']:
                body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
            
            messages.append({
                'id': message['id'],
                'sender': sender,
                'subject': subject,
                'date': formatted_date,
                'snippet': message['snippet'],
                'body': body,
                'is_unread': 'UNREAD' in message['labelIds'] if 'labelIds' in message else False
            })
        
        return messages
        
    except Exception as e:
        print(f"Error retrieving email thread: {str(e)}")
        return []

# Example usage
if __name__ == "__main__":
    try:
        # Test Gmail API connection
        service = get_gmail_service()
        print("Gmail API connection successful!")
        
        # Ask if user wants to test sending an email
        test_email = input("\nDo you want to send a test email to yourself? (y/n): ")
        if test_email.lower() == 'y':
            user_info = service.users().getProfile(userId='me').execute()
            email_address = user_info['emailAddress']
            
            print(f"\nSending test email to: {email_address}")
            result = send_email(
                to=email_address,
                subject="Test Email from Business Finder Assistant",
                body="""
                <h2>Gmail API Integration Test</h2>
                <p>This is a test email sent from your Business Finder Assistant using the Gmail API.</p>
                <p>If you're seeing this, your Gmail API integration is working correctly!</p>
                <p><strong>Next steps:</strong></p>
                <ul>
                    <li>Integrate this functionality with your agent</li>
                    <li>Test retrieving unread emails</li>
                    <li>Test replying to emails</li>
                </ul>
                """
            )
            
            if result['success']:
                print("Test email sent successfully!")
            else:
                print(f"Failed to send test email: {result.get('error', 'Unknown error')}")
        
        # Ask if user wants to check unread emails
        check_emails = input("\nDo you want to check for unread emails? (y/n): ")
        if check_emails.lower() == 'y':
            unread = get_unread_emails(max_results=5)
            if unread:
                print(f"\nFound {len(unread)} unread emails:")
                for i, email in enumerate(unread, 1):
                    print(f"\n{i}. From: {email['sender']}")
                    print(f"   Subject: {email['subject']}")
                    print(f"   Date: {email['date']}")
                    print(f"   Snippet: {email['snippet']}")
            else:
                print("\nNo unread emails found.")
                
    except Exception as e:
        print(f"Error: {str(e)}")
        print("\nIf this is your first time running this script, please run setup_gmail_api.py first to set up Gmail API access.") 