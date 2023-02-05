import logging
import os
from typing import Union, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Response, File, Request, status
from fastapi.exceptions import RequestValidationError
from twilio.rest import Client
from fastapi.responses import JSONResponse

load_dotenv()

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)
app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}


@app.post("/message")
async def chat(From: str = Form(...), Body: Optional[str] = Form(None), MediaUrl0: Optional[Any] = Form(None)):
    msg = f"Hi {From}, you said: {Body}, with {MediaUrl0}"
    print(msg)
    return Response(content=str(msg), media_type="application/xml")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
    logging.error(f"{request}: {exc_str}")
    content = {'status_code': 10422, 'message': exc_str, 'data': None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
