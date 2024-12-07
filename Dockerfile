# Dockerfile

# Use the official lightweight Python image.
FROM python:3.10-slim

# Set environment variables to prevent Python from writing pyc files and to buffer stdout and stderr.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY main.py .

# Expose any ports if necessary (not required for Telegram bots)
# EXPOSE 8443

# Define environment variable for BOT_TOKEN
# It's safer to pass it during runtime rather than hardcoding.

# Run the bot
CMD ["python", "main.py"]
