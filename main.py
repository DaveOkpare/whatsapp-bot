import logging
import os
import urllib.request
from typing import Any, Optional

import requests
import torch
import whisper  # noqa
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Response, Request, BackgroundTasks, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydub import AudioSegment
from revChatGPT.V1 import Chatbot as Version1
from revChatGPT.V2 import Chatbot as Version2
from twilio.rest import Client

load_dotenv()

MESSAGING_PROVIDER = os.environ["MESSAGING_PROVIDER"]
FB_BASE_URL = os.environ["FB_BASE_URL"]
FB_VERSION = os.environ["FB_VERSION"]
FB_PHONE_NUMBER_ID = os.environ["FB_PHONE_NUMBER_ID"]
FB_ACCESS_TOKEN = os.environ["FB_ACCESS_TOKEN"]
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
CHATBOT_VERSION = os.getenv("CHATBOT_VERSION", "Version1")
app = FastAPI()


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
    opener.addheaders = [("User-Agent", "Mozilla/6.0")]
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


async def process_text(prompt, recipient):
    response = ""

    if CHATBOT_VERSION == "Version1":
        # Initializes the chatbot
        chatbot = Version1(
            config={
                "email": os.environ["OPENAI_EMAIL"],
                "password": os.environ["OPENAI_PASSWORD"],
            }
        )

        # Stores message response from chatbot
        for data in chatbot.ask(prompt):
            response = data["message"]

    if CHATBOT_VERSION == "Version2":
        # Initializes the chatbot
        chatbot = Version2(
            email=os.environ["OPENAI_EMAIL"],
            password=os.environ["OPENAI_PASSWORD"]
        )

        # Store the message response
        async for line in chatbot.ask(prompt):  # noqa
            response += line["choices"][0]["text"].replace("<|im_end|>", "")

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


def send_message(text, recipient):
    """Sends message to a phone number"""
    if MESSAGING_PROVIDER == "twilio":
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            from_=f'whatsapp:{os.environ["FROM_WHATSAPP"]}',
            body=text,
            to=f"{recipient}",
            # media_url=["https://demo.twilio.com/owl.png"]
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


@app.post("/message")
async def chat(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: Optional[str] = Form(None),
    MediaUrl0: Optional[Any] = Form(None),
):
    """Twilio Webhook"""
    if MediaUrl0:
        print(MediaUrl0)
        msg = f"New Audio Message from {From}"
        background_tasks.add_task(process_audio, MediaUrl0, From)
    else:
        print(Body)
        msg = f"New Message from {From}"
        background_tasks.add_task(process_text, Body, From)
    return Response(content=msg, media_type="application/xml")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """This method logs error messages in console."""
    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    logging.error(f"{request}: {exc_str}")
    content = {"status_code": 10422, "message": exc_str, "data": None}
    return JSONResponse(
        content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )
