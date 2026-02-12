from twilio.rest import Client
import yaml
import os
from datetime import datetime, timedelta

# Load settings
with open('agent/config/settings.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Correct path: voice_calls -> twilio
account_sid = config['voice_calls']['twilio']['account_sid']
auth_token = config['voice_calls']['twilio']['auth_token']
client = Client(account_sid, auth_token)

print("Checking recent alerts (last 1 hour)...")
try:
    alerts = client.monitor.v1.alerts.list(limit=5)
    for alert in alerts:
        print(f"--- Alert {alert.sid} ---")
        print(f"Date: {alert.date_created}")
        print(f"Level: {alert.log_level}")
        print(f"Error Code: {alert.error_code}")
        print(f"Alert Text: {alert.alert_text}")
        print(f"More Info: {alert.more_info}")
        print(f"Resource SID: {alert.resource_sid}")
        print("-----------------------")
        
    if not alerts:
        print("No recent alerts found.")
        
except Exception as e:
    print(f"Error fetching alerts: {e}")
