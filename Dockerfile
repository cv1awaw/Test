# Use an official Ubuntu as a parent image
FROM ubuntu:20.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update and install necessary packages
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libboost-all-dev \
    libssl-dev \
    libcurl4-openssl-dev \
    libjsoncpp-dev \
    libspdlog-dev \
    uuid-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy CMakeLists.txt and source files
COPY CMakeLists.txt main.cpp roles.h ./
COPY utils/ ./utils/
COPY user_data.json muted_users.json ./

# Clone and install TgBot-Cpp
RUN git clone https://github.com/reo7sp/tgbot-cpp.git && \
    cd tgbot-cpp && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make && \
    make install && \
    cd ../.. && \
    rm -rf tgbot-cpp

# Build your C++ application
RUN mkdir build && \
    cd build && \
    cmake .. && \
    make && \
    cd ..

# Expose the port if your bot uses one (Telegram bots typically don't require this)
# EXPOSE 8443

# Set environment variable for BOT_TOKEN
# It's better to pass this as an environment variable during deployment
ENV BOT_TOKEN=YOUR_BOT_TOKEN_HERE

# Define the default command to run your bot
CMD ["./build/TelegramBotCpp"]
