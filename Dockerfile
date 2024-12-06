FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y python3-venv && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

COPY main.py /app/
COPY warning_handler.py /app/

#ENV BOT_TOKEN=<your_bot_token_here> # Or set it via docker run -e BOT_TOKEN=...
ENV PATH="/opt/venv/bin:$PATH"

CMD ["python", "main.py"]
