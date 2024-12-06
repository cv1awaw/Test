FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install venv and any dependencies for building if needed
RUN apt-get update && apt-get install -y python3-venv && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# Copy the application code
COPY main.py /app/
COPY warnings.py /app/

# If you have Tara_access.txt or other files, copy them as well
# COPY Tara_access.txt /app/

# Set environment variable for PATH
ENV PATH="/opt/venv/bin:$PATH"

# Set the BOT_TOKEN environment variable externally (e.g., docker run -e BOT_TOKEN=YOURTOKEN)
# or you could set it here ENV BOT_TOKEN=YOURTOKEN (not recommended for security)

# Run the bot
CMD ["python", "main.py"]
