// main.cpp

#include <tgbot/tgbot.h>
#include <spdlog/spdlog.h>
#include <nlohmann/json.hpp>
#include <fstream>
#include <unordered_map>
#include <unordered_set>
#include <string>
#include <regex>
#include <uuid/uuid.h>
#include "roles.h"

// Aliases for convenience
using json = nlohmann::json;

// ------------------ Logging Setup ------------------

void setup_logging() {
    spdlog::set_pattern("[%Y-%m-%d %H:%M:%S] [%l] %v");
    spdlog::set_level(spdlog::level::info);
}

// ------------------ Role Management ------------------

std::unordered_map<std::string, std::unordered_set<int64_t>> ROLE_MAP = {
    {"writer", WRITER_IDS},
    {"mcqs_team", MCQS_TEAM_IDS},
    {"checker_team", CHECKER_TEAM_IDS},
    {"word_team", WORD_TEAM_IDS},
    {"design_team", DESIGN_TEAM_IDS},
    {"king_team", KING_TEAM_IDS},
    {"tara_team", TARA_TEAM_IDS},
    {"mind_map_form_creator", MIND_MAP_FORM_CREATOR_IDS}
};

std::unordered_map<std::string, std::string> ROLE_DISPLAY_NAMES = {
    {"writer", "Writer Team"},
    {"mcqs_team", "MCQs Team"},
    {"checker_team", "Editor Team"},
    {"word_team", "Digital Writers"},
    {"design_team", "Design Team"},
    {"king_team", "Admin Team"},
    {"tara_team", "Tara Team"},
    {"mind_map_form_creator", "Mind Map & Form Creation Team"}
};

// Define trigger to target roles mapping for Tara Team side commands
std::unordered_map<std::string, std::vector<std::string>> TRIGGER_TARGET_MAP = {
    {"-w", {"writer"}},
    {"-e", {"checker_team"}},
    {"-mcq", {"mcqs_team"}},
    {"-d", {"word_team"}},
    {"-de", {"design_team"}},
    {"-mf", {"mind_map_form_creator"}},
    {"-c", {"checker_team"}}
};

// Updated forwarding rules
std::unordered_map<std::string, std::vector<std::string>> SENDING_ROLE_TARGETS = {
    {"writer", {"mcqs_team", "checker_team", "tara_team"}},
    {"mcqs_team", {"design_team", "tara_team"}},
    {"checker_team", {"tara_team", "word_team"}},
    {"word_team", {"tara_team"}},
    {"design_team", {"tara_team", "king_team"}},
    {"king_team", {"tara_team"}},
    {"tara_team", {"writer", "mcqs_team", "checker_team", "word_team", "design_team", "king_team", "tara_team", "mind_map_form_creator"}},
    {"mind_map_form_creator", {"design_team", "tara_team"}}
};

// ------------------ Conversation States ------------------

enum ConversationState {
    TEAM_MESSAGE = 1,
    SPECIFIC_TEAM_MESSAGE,
    SPECIFIC_USER_MESSAGE,
    TARA_MESSAGE,
    CONFIRMATION,
    SELECT_ROLE
};

// ------------------ User Data Storage ------------------

std::unordered_map<std::string, int64_t> user_data_store;

const std::string USER_DATA_FILE = "user_data.json";

void load_user_data() {
    std::ifstream inFile(USER_DATA_FILE);
    if (inFile.is_open()) {
        try {
            json j;
            inFile >> j;
            for (auto& [k, v] : j.items()) {
                user_data_store[k] = v.get<int64_t>();
            }
            spdlog::info("Loaded existing user data from user_data.json.");
        } catch (const json::parse_error& e) {
            spdlog::error("Failed to parse user_data.json: {}", e.what());
        }
        inFile.close();
    } else {
        spdlog::warn("user_data.json does not exist. Starting with an empty data store.");
    }
}

void save_user_data() {
    std::ofstream outFile(USER_DATA_FILE);
    if (outFile.is_open()) {
        json j;
        for (const auto& [k, v] : user_data_store) {
            j[k] = v;
        }
        outFile << j.dump(4);
        spdlog::info("Saved user data to user_data.json.");
        outFile.close();
    } else {
        spdlog::error("Failed to open user_data.json for writing.");
    }
}

std::vector<std::string> get_user_roles(int64_t user_id) {
    std::vector<std::string> roles;
    for (const auto& [role, ids] : ROLE_MAP) {
        if (ids.find(user_id) != ids.end()) {
            roles.push_back(role);
        }
    }
    return roles;
}

// ------------------ Mute Users Management ------------------

std::unordered_set<int64_t> muted_users;

const std::string MUTED_USERS_FILE = "muted_users.json";

void load_muted_users() {
    std::ifstream inFile(MUTED_USERS_FILE);
    if (inFile.is_open()) {
        try {
            json j;
            inFile >> j;
            for (const auto& uid : j) {
                muted_users.insert(uid.get<int64_t>());
            }
            spdlog::info("Loaded existing muted users from muted_users.json.");
        } catch (const json::parse_error& e) {
            spdlog::error("Failed to parse muted_users.json: {}", e.what());
        }
        inFile.close();
    } else {
        spdlog::warn("muted_users.json does not exist. Starting with an empty muted users set.");
    }
}

void save_muted_users() {
    std::ofstream outFile(MUTED_USERS_FILE);
    if (outFile.is_open()) {
        json j = json::array();
        for (const auto& uid : muted_users) {
            j.push_back(uid);
        }
        outFile << j.dump(4);
        spdlog::info("Saved muted users to muted_users.json.");
        outFile.close();
    } else {
        spdlog::error("Failed to open muted_users.json for writing.");
    }
}

// ------------------ Helper Functions ------------------

std::string get_display_name(const TgBot::User::Ptr& user) {
    if (!user->username.empty()) {
        return "@" + user->username;
    } else {
        std::string full_name = user->firstName;
        if (!user->lastName.empty()) {
            full_name += " " + user->lastName;
        }
        return full_name;
    }
}

std::string get_uuid() {
    uuid_t binuuid;
    uuid_generate(binuuid);
    char uuid_str[37];
    uuid_unparse_lower(binuuid, uuid_str);
    return std::string(uuid_str);
}

// ------------------ Bot Handlers ------------------

// Start Command Handler
void onStart(TgBot::Bot& bot, TgBot::Message::Ptr message) {
    if (message->from->username.empty()) {
        bot.getApi().sendMessage(message->chat->id, 
            "Please set a Telegram username in your profile to use specific commands like `-@username`.", 
            false, 0, nullptr, "Markdown");
        return;
    }

    std::string username_lower = message->from->username;
    std::transform(username_lower.begin(), username_lower.end(), username_lower.begin(), ::tolower);
    user_data_store[username_lower] = message->from->id;
    save_user_data();

    std::string display_name = get_display_name(message->from);
    std::string welcome_text = "Hello, " + display_name + "! Welcome to the Team Communication Bot.\n\n"
                               "Feel free to send messages using the available commands.";
    bot.getApi().sendMessage(message->chat->id, welcome_text, false, 0, nullptr, "Markdown");
}

// Help Command Handler
void onHelp(TgBot::Bot& bot, TgBot::Message::Ptr message) {
    std::string help_text = 
        "📘 *Available Commands:*\n\n"
        "/start - Initialize interaction with the bot.\n"
        "/listusers - List all registered users (Tara Team only).\n"
        "/help - Show this help message.\n"
        "/refresh - Refresh your user information.\n"
        "/cancel - Cancel the current operation.\n\n"
        "*Message Sending Triggers:*\n"
        "`-team` - Send a message to your own role and Tara Team.\n"
        "`-t` - Send a message exclusively to the Tara Team.\n\n"
        "*Specific Commands for Tara Team:*\n"
        "`-@username` - Send a message to a specific user.\n"
        "`-w` - Send a message to the Writer Team.\n"
        "`-e` or `-c` - Send a message to the Editor Team.\n"
        "`-mcq` - Send a message to the MCQs Team.\n"
        "`-d` - Send a message to the Digital Writers.\n"
        "`-de` - Send a message to the Design Team.\n"
        "`-mf` - Send a message to the Mind Map & Form Creation Team.\n\n"
        "*Admin Commands (Tara Team only):*\n"
        "/mute [user_id] - Mute yourself or another user.\n"
        "/muteid <user_id> - Mute a specific user by their ID.\n"
        "/unmuteid <user_id> - Unmute a specific user by their ID.\n"
        "/listmuted - List all currently muted users.\n\n"
        "📌 *Notes:*\n"
        "- Only Tara Team members can use side commands and `-@username` command.\n"
        "- Use `/cancel` to cancel any ongoing operation.\n"
        "- If you have *no role*, you can send anonymous feedback to all teams.";
    
    bot.getApi().sendMessage(message->chat->id, help_text, false, 0, nullptr, "Markdown");
}

// Error Handler
void onError(TgBot::Bot& bot, TgBot::TgException& exception) {
    spdlog::error("Error: {}", exception.what());
}

// ------------------ Forwarding Functions ------------------

void forward_message(TgBot::Bot& bot, TgBot::Message::Ptr message, const std::vector<int64_t>& target_ids, const std::string& sender_role) {
    std::string sender_display_name = ROLE_DISPLAY_NAMES[sender_role];
    std::string username_display = get_display_name(message->from);

    std::string caption;
    if (message->document) {
        caption = "🔄 *This document was sent by **" + username_display + " (" + sender_display_name + ")**.*";
    } else if (message->text) {
        caption = "🔄 *This message was sent by **" + username_display + " (" + sender_display_name + ")**.*";
    } else {
        caption = "🔄 *This message was sent by **" + username_display + " (" + sender_display_name + ")**.*";
    }

    for (const auto& user_id : target_ids) {
        try {
            if (message->document) {
                bot.getApi().sendDocument(user_id, message->document->fileId, caption + (message->caption.empty() ? "" : "\n\n" + message->caption), "Markdown");
                spdlog::info("Forwarded document {} to {}", message->document->fileId, user_id);
            } else if (message->text) {
                bot.getApi().sendMessage(user_id, caption + "\n\n" + message->text, false, 0, nullptr, "Markdown");
                spdlog::info("Forwarded text message to {}", user_id);
            } else {
                bot.getApi().forwardMessage(user_id, message->chat->id, message->messageId);
                spdlog::info("Forwarded message {} to {}", message->messageId, user_id);
            }
        } catch (const std::exception& e) {
            spdlog::error("Failed to forward message or send role notification to {}: {}", user_id, e.what());
        }
    }
}

void forward_anonymous_message(TgBot::Bot& bot, TgBot::Message::Ptr message, const std::vector<int64_t>& target_ids) {
    for (const auto& user_id : target_ids) {
        try {
            if (message->document) {
                bot.getApi().sendDocument(user_id, message->document->fileId, "🔄 *Anonymous feedback.*" + (message->caption.empty() ? "" : "\n\n" + message->caption), "Markdown");
            } else if (message->text) {
                bot.getApi().sendMessage(user_id, "🔄 *Anonymous feedback.*\n\n" + message->text, false, 0, nullptr, "Markdown");
            } else {
                bot.getApi().forwardMessage(user_id, message->chat->id, message->messageId);
            }
        } catch (const std::exception& e) {
            spdlog::error("Failed to forward anonymous feedback to {}: {}", user_id, e.what());
        }
    }
}

// ------------------ Main Function ------------------

int main() {
    setup_logging();
    load_user_data();
    load_muted_users();

    const char* token_env = std::getenv("BOT_TOKEN");
    if (!token_env) {
        spdlog::error("BOT_TOKEN is not set in environment variables.");
        return 1;
    }

    std::string token = token_env;

    TgBot::Bot bot(token);

    // Start Command
    bot.getEvents().onCommand("start", [&bot](TgBot::Message::Ptr message) {
        onStart(bot, message);
    });

    // Help Command
    bot.getEvents().onCommand("help", [&bot](TgBot::Message::Ptr message) {
        onHelp(bot, message);
    });

    // TODO: Implement other command handlers (listusers, mute, etc.)

    // General Message Handler
    bot.getEvents().onAnyMessage([&bot](TgBot::Message::Ptr message) {
        try {
            if (message->text.empty() && !message->document) {
                return;
            }

            spdlog::info("Received message from {}: {}", message->from->id, message->text);

            // Check if user is muted
            if (muted_users.find(message->from->id) != muted_users.end()) {
                bot.getApi().sendMessage(message->chat->id, "You have been muted and cannot send messages through this bot.");
                return;
            }

            // Update user data
            if (!message->from->username.empty()) {
                std::string username_lower = message->from->username;
                std::transform(username_lower.begin(), username_lower.end(), username_lower.begin(), ::tolower);
                if (user_data_store.find(username_lower) == user_data_store.end() || 
                    user_data_store[username_lower] != message->from->id) {
                    user_data_store[username_lower] = message->from->id;
                    save_user_data();
                }
            }

            // Determine user roles
            std::vector<std::string> roles = get_user_roles(message->from->id);

            if (roles.empty()) {
                // Handle anonymous feedback
                std::string confirmation_text = "You have no roles. Do you want to send this as *anonymous feedback* to all teams?";
                std::string uuid_str = get_uuid();
                std::string callback_confirm = "confirm_no_role:" + uuid_str;
                std::string callback_cancel = "cancel:" + uuid_str;

                // Store confirmation data
                // In C++, you need to manage user data context differently
                // For simplicity, this example does not implement full state management

                TgBot::InlineKeyboardButton::Ptr confirmButton(new TgBot::InlineKeyboardButton);
                confirmButton->text = "✅ Send feedback";
                confirmButton->callbackData = callback_confirm;

                TgBot::InlineKeyboardButton::Ptr cancelButton(new TgBot::InlineKeyboardButton);
                cancelButton->text = "❌ Cancel";
                cancelButton->callbackData = callback_cancel;

                std::vector<TgBot::InlineKeyboardButton::Ptr> row;
                row.push_back(confirmButton);
                row.push_back(cancelButton);

                TgBot::InlineKeyboardMarkup::Ptr keyboard(new TgBot::InlineKeyboardMarkup);
                keyboard->inlineKeyboard.push_back(row);

                bot.getApi().sendMessage(message->chat->id, confirmation_text, false, 0, keyboard, "Markdown");
                return;
            }

            // Handle role selection if multiple roles
            if (roles.size() > 1) {
                // Send role selection keyboard
                std::vector<TgBot::InlineKeyboardButton::Ptr> buttons;
                for (const auto& role : roles) {
                    TgBot::InlineKeyboardButton::Ptr button(new TgBot::InlineKeyboardButton);
                    button->text = ROLE_DISPLAY_NAMES[role];
                    button->callbackData = "role:" + role;
                    buttons.push_back(button);
                }

                // Cancel button
                TgBot::InlineKeyboardButton::Ptr cancelButton(new TgBot::InlineKeyboardButton);
                cancelButton->text = "❌ Cancel";
                cancelButton->callbackData = "cancel_role_selection";
                buttons.push_back(cancelButton);

                std::vector<TgBot::InlineKeyboardButton::Ptr> row = buttons;
                std::vector<TgBot::InlineKeyboardRow::Ptr> keyboard_rows;
                TgBot::InlineKeyboardRow::Ptr keyboard_row(new TgBot::InlineKeyboardRow);
                for (const auto& btn : row) {
                    keyboard_row->push_back(btn);
                }
                keyboard_rows.push_back(keyboard_row);
                TgBot::InlineKeyboardMarkup::Ptr keyboard(new TgBot::InlineKeyboardMarkup);
                keyboard->inlineKeyboard = keyboard_rows;

                bot.getApi().sendMessage(message->chat->id, 
                    "You have multiple roles. Please choose which role you want to use to send this message:",
                    false, 0, keyboard, "Markdown");
                return;
            }

            // If single role, proceed to send message
            if (roles.size() == 1) {
                std::string sender_role = roles[0];
                // Determine target roles based on SENDING_ROLE_TARGETS
                std::vector<std::string> target_roles = SENDING_ROLE_TARGETS[sender_role];
                std::unordered_set<int64_t> target_ids_set;
                for (const auto& role : target_roles) {
                    for (const auto& id : ROLE_MAP[role]) {
                        if (id != message->from->id) { // Exclude sender
                            target_ids_set.insert(id);
                        }
                    }
                }

                std::vector<int64_t> target_ids(target_ids_set.begin(), target_ids_set.end());

                // Forward or process the message accordingly
                forward_message(bot, message, target_ids, sender_role);

                std::string sender_display_name = ROLE_DISPLAY_NAMES[sender_role];
                std::string confirmation_text;
                if (message->document) {
                    confirmation_text = "✅ *Your PDF `" + message->document->fileName + "` has been sent from **" + sender_display_name + "** to the respective teams.*";
                } else if (message->text) {
                    confirmation_text = "✅ *Your message has been sent from **" + sender_display_name + "** to the respective teams.*";
                } else {
                    confirmation_text = "✅ *Your message has been sent from **" + sender_display_name + "** to the respective teams.*";
                }

                bot.getApi().sendMessage(message->chat->id, confirmation_text, false, 0, nullptr, "Markdown");
            }

        } catch (const std::exception& e) {
            spdlog::error("Exception in onAnyMessage: {}", e.what());
        }
    });

    // Handle callback queries (e.g., role selection, confirmations)
    bot.getEvents().onCallbackQuery([&bot](TgBot::CallbackQuery::Ptr query) {
        try {
            std::string data = query->data;

            // Handle role selection
            if (data.find("role:") == 0) {
                std::string selected_role = data.substr(5);
                // You need to implement state management to handle following messages
                // For simplicity, this example assumes immediate message handling

                std::string prompt = "Write your message for the " + ROLE_DISPLAY_NAMES[selected_role] + ".";
                bot.getApi().sendMessage(query->message->chat->id, prompt, false, 0, nullptr, "Markdown");
                return;
            }

            // Handle cancellation
            if (data == "cancel_role_selection") {
                bot.getApi().sendMessage(query->message->chat->id, "Operation cancelled.");
                return;
            }

            // Handle anonymous feedback confirmation
            if (data.find("confirm_no_role:") == 0) {
                std::string confirmation_uuid = data.substr(17);
                // Retrieve the message and sender info based on UUID
                // Implement your storage mechanism for confirmation data
                // This example does not implement it
                bot.getApi().sendMessage(query->message->chat->id, "✅ *Your anonymous feedback has been sent to all teams.*", false, 0, nullptr, "Markdown");
                // Additionally, send the real info to the special user
                // You need to implement this part based on your requirements
                return;
            }

            if (data.find("cancel:") == 0) {
                // Handle generic cancellation
                bot.getApi().sendMessage(query->message->chat->id, "Operation cancelled.");
                return;
            }

        } catch (const std::exception& e) {
            spdlog::error("Exception in onCallbackQuery: {}", e.what());
        }
    });

    // Handle errors
    bot.getEvents().onAnyError([&bot](TgBot::TgException& e) {
        spdlog::error("Bot error: {}", e.what());
    });

    try {
        spdlog::info("Bot started.");
        TgBot::TgLongPoll longPoll(bot);
        while (true) {
            longPoll.start();
        }
    } catch (TgBot::TgException& e) {
        spdlog::error("Bot exception: {}", e.what());
    }

    return 0;
}
