import os
import sys
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

def main():
    # Retrieve Twilio credentials from environment variables
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_FROM_NUMBER')
    to_number = '9665090586'
    phrase = 'kay karalas lavdyaa'

    # Check that all required credentials are present
    missing = []
    if not account_sid:
        missing.append('TWILIO_ACCOUNT_SID')
    if not auth_token:
        missing.append('TWILIO_AUTH_TOKEN')
    if not from_number:
        missing.append('TWILIO_FROM_NUMBER')
    if missing:
        sys.stderr.write(f"Missing required environment variables: {', '.join(missing)}\n")
        sys.exit(1)

    # Initialize Twilio client
    client = Client(account_sid, auth_token)

    # Build TwiML that says the exact phrase
    response = VoiceResponse()
    response.say(phrase, voice='alice')

    try:
        call = client.calls.create(
            to=to_number,
            from_=from_number,
            twiml=response
        )
        print(f"Call initiated, SID: {call.sid}")
    except Exception as e:
        sys.stderr.write(f"Failed to create call: {e}\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
