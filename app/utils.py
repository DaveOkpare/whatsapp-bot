import logging
import os
import urllib

import requests
import torch
import whisper
from dotenv import load_dotenv
from faster_whisper import WhisperModel
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


def refresh_api_token():
    """
    "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&
      client_id="APP-ID"&
      client_secret="APP-SECRET"&
      fb_exchange_token="SHORT-LIVED-USER-ACCESS-TOKEN"
    :return:
    """
    url = "https://graph.facebook.com/oauth/access_token?"
    params = dict(
        client_id="APP-ID",
        client_secret="APP-SECRET",
        fb_exchange_token="SHORT-LIVED-USER-ACCESS-TOKEN",
    )
    requests.get(url=url, params=params)


async def download_file(url_link, path):
    # Use requests to download file
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {FB_ACCESS_TOKEN}",
    }
    response = requests.get(url_link, headers=headers)

    # Write the downloaded file to disk
    if response.status_code == 200:
        with open(path, "wb") as f:
            f.write(response.content)

        return path


def send_message(text, recipient: str, messaging_provider: str):
    """Sends message to a phone number"""
    if messaging_provider == "twilio":
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            from_=f'whatsapp:{os.getenv("FROM_WHATSAPP")}',
            body=text,
            to=f"whatsapp:{recipient}",
        )

        sid = message.sid
        return sid

    elif messaging_provider == "whatsapp":
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


async def faster_transcribe_audio(audio):
    model_size = "large-v2"

    # Run on GPU with FP16
    # model = WhisperModel(model_size, device="cuda", compute_type="float16")

    # or run on GPU with INT8
    # model = WhisperModel(model_size, device="cuda", compute_type="int8_float16")
    # or run on CPU with INT8
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, info = model.transcribe(audio, beam_size=5)

    logging.info("Detected language '%s' with probability %f" % (info.language, info.language_probability))

    output = ""

    for segment in segments:
        logging.info("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
        output += segment.text

    return output


async def process_audio(url_link, recipient, messaging_provider, prompt=True):
    # Create path to store ogg and mp3 files in root directory
    ogg_path = os.path.join(os.getcwd(), "assets/audio_clip.ogg")
    mp3_path = os.path.join(os.getcwd(), "assets/audio_clip.mp3")

    if messaging_provider == "whatsapp":
        ogg_path = await download_file(url_link, ogg_path)
    else:
        # Add User-Agent headers to library downloading audio
        opener = urllib.request.build_opener()
        opener.addheaders = [("User-Agent", "Mozilla/6.0"),]  # noqa
        urllib.request.install_opener(opener)

        # Download Audio file and save it at ogg_path
        urllib.request.urlretrieve(url_link, ogg_path)

    # Convert ogg file to mp3
    # sound = AudioSegment.from_file(ogg_path)
    # sound.export(mp3_path, format="mp3")

    # Await mp3 audio to be transcribed to text
    response = await faster_transcribe_audio(ogg_path)

    if prompt:
        # Processes the prompt
        response = await process_text(response, recipient, messaging_provider)
    else:
        # Send transcribed audio
        send_message(response, recipient, messaging_provider)

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
            # {"role": "system", "content": "You are a knowledgeable developer."},
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


async def process_text(prompt, recipient, messaging_provider):
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
        send_message(text, recipient, messaging_provider)

    return response


async def get_download_link(audio_id, sender_id):
    url = f"https://graph.facebook.com/v16.0/{audio_id}/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {FB_ACCESS_TOKEN}",
    }
    response = requests.get(url=url, headers=headers)
    response = response.json()
    logging.info(response)
    media_url = response["url"]
    messaging_provider = "whatsapp"
    await process_audio(media_url, sender_id, messaging_provider)
