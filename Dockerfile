# Use an official Python runtime as the base image
FROM python:3.9-slim

# Install system dependencies required for Tesseract OCR and PDF processing
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    tesseract-ocr \
    tesseract-ocr-ara \
    poppler-utils \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables to prevent Python from writing pyc files and to buffer outputs
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Specify the command to run your application
CMD ["python", "main.py"]
