import logging
import os
from typing import Any, Optional, List

import uvicorn
from fastapi import FastAPI, Form, Response, Request, BackgroundTasks, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .utils import process_audio, process_text

app = FastAPI()


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
    if MediaUrl0:
        print(MediaUrl0)
        msg = f"New Audio Message from {From}"
        background_tasks.add_task(process_audio, MediaUrl0, From)
    else:
        print(Body)
        msg = f"New Message from {From}"
        background_tasks.add_task(process_text, Body, From)
    return Response(content=msg, media_type="application/xml")


@app.post("/webhook")
async def webhook(background_tasks: BackgroundTasks, data: WebhookRequestData):
    if data.object == "page":
        for entry in data.entry:
            messaging_events = [
                event for event in entry.get("messaging", []) if event.get("message")
            ]
            for event in messaging_events:
                message = event.get("message")
                sender_id = event["sender"]["id"]
                background_tasks.add_task(process_text, message, sender_id)

    # message = payload["data"]
    # body = message["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
    # from_ = message["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    # msg = f"New Message from {from_}"
    # background_tasks.add_task(process_text, body, from_)
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


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=os.getenv("PORT", default=5000),
        log_level="info",
    )
