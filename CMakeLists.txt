cmake_minimum_required(VERSION 3.5)
project(TelegramBotCpp)

set(CMAKE_CXX_STANDARD 14)

find_package(TgBot REQUIRED)
find_package(nlohmann_json REQUIRED)
find_package(spdlog REQUIRED)
find_package(Boost REQUIRED COMPONENTS system)

include_directories(${TGBOT_INCLUDE_DIRS})

add_executable(TelegramBotCpp main.cpp)

target_link_libraries(TelegramBotCpp 
    TgBot::TgBot 
    nlohmann_json::nlohmann_json 
    spdlog::spdlog 
    Boost::system
)
