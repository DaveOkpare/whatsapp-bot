import os
import urllib.request

import requests
import torch
import whisper
from dotenv import load_dotenv
from pydub import AudioSegment
from revChatGPT.V1 import Chatbot as Chatbot_ONE, Error
from revChatGPT.V2 import Chatbot as Chatbot_TWO
from twilio.rest import Client

load_dotenv()

CHATBOT_VERSION = os.getenv("CHATBOT_VERSION", "OPENAI")
MESSAGING_PROVIDER = os.getenv("MESSAGING_PROVIDER", "whatsapp")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FB_BASE_URL = os.environ["FB_BASE_URL"]
FB_VERSION = os.environ["FB_VERSION"]
FB_PHONE_NUMBER_ID = os.environ["FB_PHONE_NUMBER_ID"]
FB_ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]


def send_message(text, recipient: str):
    """Sends message to a phone number"""
    if MESSAGING_PROVIDER == "twilio":
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            from_=f'whatsapp:{os.getenv("FROM_WHATSAPP")}',
            body=text,
            to=f"whatsapp:+2347015593286",
        )

        sid = message.sid
        return sid

    elif MESSAGING_PROVIDER == "whatsapp":
        url = f"{FB_BASE_URL}/{FB_VERSION}/{FB_PHONE_NUMBER_ID}/messages"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {FB_ACCESS_TOKEN}",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {
                "preview_url": True,
                "body": text,
            },
        }

        response = requests.post(url=url, headers=headers, json=payload)
        return response.json()


async def transcribe_audio(audio):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model("base", device=device)
    audio = whisper.load_audio(audio)
    result = model.transcribe(audio, fp16=False)
    return result["text"]


async def process_audio(url_link, recipient, prompt=True):
    # Create path to store ogg and mp3 files in root directory
    ogg_path = os.path.join(os.getcwd(), "assets/audio_clip.ogg")
    mp3_path = os.path.join(os.getcwd(), "assets/audio_clip.mp3")

    # Add User-Agent headers to library downloading audio
    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "Mozilla/6.0")]  # noqa
    urllib.request.install_opener(opener)

    # Download Audio file and save it at ogg_path
    urllib.request.urlretrieve(url_link, ogg_path)

    # Convert ogg file to mp3
    sound = AudioSegment.from_file(ogg_path)
    sound.export(mp3_path, format="mp3")

    # Await mp3 audio to be transcribed to text
    response = await transcribe_audio(mp3_path)

    if prompt:
        # Processes the prompt
        response = await process_text(response, recipient)
    else:
        # Send transcribed audio
        send_message(response, recipient)

    # Deletes files from root directory after use
    [os.remove(path) for path in (mp3_path, ogg_path)]

    return response


def openai_mirror(prompt):
    # Note: you need to be using OpenAI Python v0.27.0 for the code below to work
    import openai

    openai.api_key = os.getenv("OPENAI_KEY")

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a knowledgeable developer."},
            {"role": "user", "content": prompt},
        ],
    )
    return response["choices"][0]["message"]["content"]


async def revchat_mirror(prompt):
    response = ""
    try:
        chatbot = Chatbot_ONE(
            config={
                "email": os.environ["OPENAI_EMAIL"],
                "password": os.environ["OPENAI_PASSWORD"],
            }
        )

        # Stores message response from chatbot
        for data in chatbot.ask(prompt):
            response = data["message"]
        return response
    except Error:
        chatbot = Chatbot_TWO(api_key=os.environ["OPENAI_KEY"])

        async for line in chatbot.ask(prompt):  # noqa
            response += line["choices"][0]["text"].replace("<|im_end|>", "")
        return response


async def process_text(prompt, recipient):
    # Initializes the chatbot
    if CHATBOT_VERSION == "revchat":
        response = revchat_mirror(prompt)
    else:
        response = openai_mirror(prompt)

    # CONTEXT: WhatsApp allows a maximum of 1600 characters in a single message.
    # Break long text messages into 1600 and send WhatsApp message.
    message_width = 1600
    import textwrap

    messages = textwrap.wrap(
        response, message_width, break_long_words=False, replace_whitespace=False
    )

    for text in messages:
        send_message(text, recipient)

    return response
