import os

from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()


def send_message():
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    client = Client(account_sid, auth_token)

    message = client.messages.create(
        from_=f'whatsapp:{os.environ["FROM_WHATSAPP"]}',
        body='That is good my guy',
        to=f'whatsapp:{os.environ["TO_WHATSAPP"]}',
        media_url=["https://demo.twilio.com/owl.png"]
    )

    sid = message.sid
    return sid


if __name__ == '__main__':
    import requests
    response = requests.post(url="http://7fd9-102-134-115-161.ngrok.io/message", data={"From": "David"})
    print(response.content)
