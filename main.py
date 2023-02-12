import logging
import os
import urllib.request
from typing import Any, Optional

import whisper
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Response, Request, BackgroundTasks, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydub import AudioSegment
from twilio.rest import Client

load_dotenv()

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)
app = FastAPI()


def transcribe_audio(audio):
    model = whisper.load_model("base")
    result = model.transcribe(audio, fp16=False)
    return result


def process_audio(url_link):
    urllib.request.urlretrieve(url_link, "audio_clip.ogg")
    sound = AudioSegment.from_file("audio_clip.ogg")
    sound.export("audio_clip.mp3", format="mp3")
    transcribe_audio("/Users/RichesofGod/PycharmProjects/AI/chatbot/steve.mp3")


async def process_text():
    pass


@app.post("/message")
async def chat(background_tasks: BackgroundTasks,
               From: str = Form(...),
               Body: Optional[str] = Form(None),
               MediaUrl0: Optional[Any] = Form(None),
               ):
    if MediaUrl0:
        msg = f"Hi {From}, you said: {Body}, with {MediaUrl0}"
    else:
        msg = f"Hi {From}, you said: {Body}"
    print(msg)
    string = type(MediaUrl0)
    print(string)
    return Response(content=str(msg), media_type="application/xml")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
    logging.error(f"{request}: {exc_str}")
    content = {'status_code': 10422, 'message': exc_str, 'data': None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


if __name__ == '__main__':
    url = "https://s3-external-1.amazonaws.com/media.twiliocdn.com/AC958a78d85d98af58c96069af329a3f94" \
          "/30f5b7ee12382cbd269b5a8ff4787166 "
    print(process_audio(url))
