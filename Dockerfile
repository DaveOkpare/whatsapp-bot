FROM tiangolo/uvicorn-gunicorn:python3.10

ENV PYTHONUNBUFFERED 1
EXPOSE 8000
WORKDIR /app
COPY ./requirements.txt /app/requirements.txt
COPY . .
RUN install --no-cache-dir -r /app/requirements.txt
CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8000", "src.main:app"]
