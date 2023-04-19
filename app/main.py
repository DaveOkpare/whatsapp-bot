import logging
import os
from typing import Any, Optional, List

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Response, Request, BackgroundTasks, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests

from utils import process_audio, process_text, get_download_link

app = FastAPI()

load_dotenv()

# setup loggers
logging.config.fileConfig("logging.conf", disable_existing_loggers=False)

# get root logger
logger = logging.getLogger(
    __name__
)  # the __name__ resolve to "main" since we are at the root of the project.
# This will get the root logger since no logger in the configuration has this name.


class WebhookRequestData(BaseModel):
    object: str = ""
    entry: List = []


@app.post("/message")
async def chat(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: Optional[str] = Form(None),
    MediaUrl0: Optional[Any] = Form(None),
):
    """Twilio Webhook"""
    messaging_provider = "twilio"
    if MediaUrl0:
        print(MediaUrl0)
        msg = f"New Audio Message from {From}"
        background_tasks.add_task(process_audio, MediaUrl0, From, messaging_provider)
    else:
        print(Body)
        msg = f"New Message from {From}"
        background_tasks.add_task(process_text, Body, From, messaging_provider)
    return Response(content=msg, media_type="application/xml")


@app.router.get("/api/webhook")
async def verify(request: Request):
    """
    On webook verification VERIFY_TOKEN has to match the token at the
    configuration and send back "hub.challenge" as success.
    """
    if request.query_params.get("hub.mode") == "subscribe" and request.query_params.get(
        "hub.challenge"
    ):
        if not request.query_params.get("hub.verify_token") == os.getenv(
            "VERIFY_TOKEN"
        ):
            return Response(content="Verification token mismatch", status_code=403)
        return Response(content=request.query_params["hub.challenge"])

    return Response(content="Required arguments haven't passed.", status_code=400)


@app.post("/api/webhook")
async def webhook(background_tasks: BackgroundTasks, data: WebhookRequestData):
    """
    Messages handler.
    """
    logging.info(data)
    messaging_provider = "whatsapp"
    if data.object == "whatsapp_business_account":
        for entry in data.entry:
            messaging_events = [
                event.get("value")
                for event in entry.get("changes", [])
                if event.get("value")
            ]
            for event in messaging_events:
                message = event.get("messages")[0]
                sender_id = message["from"]
                phone_number_id = event.get("metadata")["phone_number_id"]

                if message.get("text"):
                    message = message["text"]["body"]
                    background_tasks.add_task(
                        process_text, message, sender_id, messaging_provider
                    )

                elif message.get("audio"):
                    audio_id = message["audio"]["id"]
                    background_tasks.add_task(get_download_link, audio_id, sender_id)
    return Response(content="Received a message", media_type="application/json")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """This method logs error messages in console."""
    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    logging.error(f"{request}: {exc_str}")
    content = {"status_code": 10422, "message": exc_str, "data": None}
    return JSONResponse(
        content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


@app.get("/david")
async def david(request: Request):
    # Extract the IP address from the request headers
    ip_address = request.headers.get("X-Forwarded-For", request.client.host)

    # Make a request to the geolocation API
    response = requests.get(f"https://ipinfo.io/{ip_address}")

    # Parse the JSON response to retrieve the country and location data
    data = response.json()
    country = data.get("country")
    loc = data.get("loc")

    # Return the location data as a JSON response
    return {"ip_address": ip_address, "country": country, "location": loc}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=os.getenv("PORT", default=5000),
        log_level="info",
    )
