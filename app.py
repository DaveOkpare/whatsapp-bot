import os

from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()


def send_message():
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    client = Client(account_sid, auth_token)

    message = client.messages.create(
        from_='whatsapp:+14155238886',
        body='That is good my guy',
        to='whatsapp:+2347015593286',
        media_url=["https://demo.twilio.com/owl.png"]
    )

    sid = message.sid
    return sid


if __name__ == '__main__':
    import requests
    response = requests.post(url="http://86a5-105-112-56-55.ngrok.io/message", data={"From": "David"})
    print(response.content)
