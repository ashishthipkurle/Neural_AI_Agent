from twilio.rest import Client
import yaml
import os

# Load settings
with open('agent/config/settings.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Correct path: voice_calls -> twilio
account_sid = config['voice_calls']['twilio']['account_sid']
auth_token = config['voice_calls']['twilio']['auth_token']
client = Client(account_sid, auth_token)

# metadata from log: SID: CA24e24f2f1f818ebbc939ab5a84f36004
sid = "CA24e24f2f1f818ebbc939ab5a84f36004"

try:
    print(f"Fetching status for call: {sid}")
    call = client.calls(sid).fetch()
    print(f"Call SID: {call.sid}")
    print(f"Status: {call.status}")
    print(f"To: {call.to}")
    # Handle 'from' attribute safely
    try:
        print(f"From: {call.from_}")
    except AttributeError:
        print(f"From: {getattr(call, '_from', 'N/A')}")
    
    print(f"Duration: {call.duration}")
    print(f"Price: {call.price}")
    print(f"Direction: {call.direction}")
    print(f"Answered By: {call.answered_by}")
    print(f"Start Time: {call.start_time}")
    print(f"End Time: {call.end_time}")
    
    # Check for errors - this is critical
    # Note: Twilio API returns None or null for error_code if success
    print(f"Error Code: {call.error_code}")
    print(f"Error Message: {call.error_message}")
    
except Exception as e:
    print(f"Error fetching call: {e}")
