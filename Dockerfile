# Dockerfile

FROM python:3.11-alpine

# Set the working directory
WORKDIR /app

# Install ca-certificates and update them for SSL verification
RUN apk update && apk add --no-cache ca-certificates
RUN update-ca-certificates

# Copy and install requirements
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code
COPY . .

# Use environment variable for BOT_TOKEN
# Removed hardcoded BOT_TOKEN for security
# Ensure BOT_TOKEN is provided at runtime

# Default command to run your bot
CMD ["python", "main.py"]
