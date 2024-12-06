# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Set environment variable for BOT_TOKEN (ensure to set this in your Docker run or compose file)
# ENV BOT_TOKEN=your_bot_token_here

# Expose port if necessary (not required for polling)
# EXPOSE 8443

# Define the default command
CMD ["python", "main.py"]
