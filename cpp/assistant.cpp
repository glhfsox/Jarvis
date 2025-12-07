#include "assistant.hpp"
#include "actions.hpp"

#include <cctype>
#include <cstdlib>
#include <iostream>
#include <signal.h>

#include <curl/curl.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;
using namespace std::chrono_literals;

// ---------- CommandDispatcher ----------

void CommandDispatcher::registerHandler(const std::string& name, Handler handler) {
    handlers_[name] = std::move(handler);
}

void CommandDispatcher::dispatch(const Command& cmd) const {
    auto it = handlers_.find(cmd.name);
    if (it == handlers_.end()) {
        std::cerr << "Jarvis: no handler for '" << cmd.name << "'\n";
        return;
    }
    it->second(cmd);
}

// ---------- TextBuffer ----------

TextBuffer::TextBuffer(std::size_t maxChars)
    : maxChars_(maxChars) {}

void TextBuffer::add(const std::string& text) {
    if (text.empty()) return;
    std::lock_guard<std::mutex> lock(mutex_);
    if (!buffer_.empty()) buffer_.push_back(' ');
    buffer_ += text;
    if (buffer_.size() > maxChars_) {
        buffer_.erase(0, buffer_.size() - maxChars_);
    }
}

std::string TextBuffer::tail(std::size_t nChars) const {
    std::lock_guard<std::mutex> lock(mutex_);
    if (nChars >= buffer_.size()) return buffer_;
    return buffer_.substr(buffer_.size() - nChars);
}

void TextBuffer::clear() {
    std::lock_guard<std::mutex> lock(mutex_);
    buffer_.clear();
}

// ---------- KeywordDetector ----------

KeywordDetector::KeywordDetector(Map patterns)
    : patterns_(std::move(patterns)) {}

std::string KeywordDetector::detectIntent(const std::string& text) const {
    std::string lowered = toLower(text);
    for (const auto& [intent, pats] : patterns_) {
        for (const auto& p : pats) {
            if (contains(lowered, p)) return intent;
        }
    }
    return {};
}

std::string KeywordDetector::toLower(const std::string& s) {
    std::string res;
    res.reserve(s.size());
    for (unsigned char c : s) res.push_back(static_cast<char>(std::tolower(c)));
    return res;
}

bool KeywordDetector::contains(const std::string& text, const std::string& pattern) {
    if (pattern.empty()) return false;
    return text.find(pattern) != std::string::npos;
}

// ---------- Utils ----------

std::string toLowerCopy(const std::string& s) {
    std::string res;
    res.reserve(s.size());
    for (unsigned char c : s) res.push_back(static_cast<char>(std::tolower(c)));
    return res;
}

static std::string trim_copy(std::string s) {
    auto is_space = [](unsigned char c) { return std::isspace(c); };
    while (!s.empty() && is_space((unsigned char)s.front())) s.erase(s.begin());
    while (!s.empty() && is_space((unsigned char)s.back())) s.pop_back();
    return s;
}

// ---------- LLM integration ----------

struct CurlBuffer {
    std::string data;
};

static size_t curlWriteCallback(char* ptr, size_t size, size_t nmemb, void* userdata) {
    auto* buf = static_cast<CurlBuffer*>(userdata);
    buf->data.append(ptr, size * nmemb);
    return size * nmemb;
}

static std::string buildPrompt(const std::string& transcript) {
    std::string prompt;

    prompt += "You are a command parser for a LOCAL voice assistant.\n";
    prompt += "I will give you a transcript of the last few seconds of the user's speech (in English or Russian).\n\n";

    prompt += "Your task:\n";
    prompt += "1) Extract ALL executable commands that appear in the text.\n";
    prompt += "2) Return ONLY JSON. Never add explanations, comments, or extra text.\n\n";

    prompt += "VALID JSON OUTPUT FORMS:\n";
    prompt += "- If there are NO commands -> return: null\n";
    prompt += "- If there is ONE command -> return a single object OR an array with one object\n";
    prompt += "- If there are MULTIPLE commands -> return a JSON array of objects\n\n";

    prompt += "Each command object must have the structure:\n";
    prompt += R"({"name": "<command_name>", "args": {...}, "raw_text": "<original_text_fragment>"})";
    prompt += "\n\n";

    prompt += "ALLOWED COMMANDS:\n";
    prompt += "  - open_url(url: string)\n";
    prompt += "  - open_app(name: string)\n";
    prompt += "  - close_app(name: string)\n";
    prompt += "  - open_terminal(command: optional string)\n";
    prompt += "  - media_play_pause()\n";
    prompt += "  - media_next()\n";
    prompt += "  - media_prev()\n";
    prompt += "  - media_volume_up()\n";
    prompt += "  - media_volume_down()\n";
    prompt += "  - media_seek_forward()\n";
    prompt += "  - media_seek_backward()\n";
    prompt += "  - media_volume_mute()\n";
    prompt += "  - media_volume_unmute()\n";
    prompt += "  - system_volume_up()\n";
    prompt += "  - system_volume_down()\n";
    prompt += "  - system_volume_mute()\n";
    prompt += "  - system_volume_unmute()\n";
    prompt += "  - system_brightness_up()\n";
    prompt += "  - system_brightness_down()\n";
    prompt += "  - wifi_on()\n";
    prompt += "  - wifi_off()\n";
    prompt += "  - bluetooth_on()\n";
    prompt += "  - bluetooth_off()\n";
    prompt += "  - system_lock()\n";
    prompt += "  - system_shutdown()\n";
    prompt += "  - system_reboot()\n";
    prompt += "  - window_focus(name?: string, id?: string)  # prefer id if provided\n";
    prompt += "  - window_close(name?: string, id?: string)  # prefer id if provided\n";
    prompt += "  - window_inspect(name?: string)             # list windows, optionally highlight best match\n\n";

    prompt += "Examples of valid output:\n";
    prompt += R"({"name": "open_url", "args": {"url": "https://youtube.com"}, "raw_text": "open youtube"})";
    prompt += "\n";
    prompt += R"([{"name": "open_url", "args": {"url": "https://youtube.com"}, "raw_text": "open youtube"},)"
              R"({"name": "open_url", "args": {"url": "https://chatgpt.com"}, "raw_text": "and chatgpt"}])";
    prompt += "\n\n";

    prompt += "Rules:\n";
    prompt += "- ALWAYS return valid JSON only (null, object, or array).\n";
    prompt += "- Do NOT invent URLs; use only those explicitly mentioned.\n";
    prompt += "- Convert phrases like 'youtube dot com' -> 'youtube.com'.\n";
    prompt += "- Preserve the original user phrase in raw_text.\n\n";

    prompt += "Here is the transcript:\n\"\"\"" + transcript + "\"\"\"";

    return prompt;
}

std::vector<Command> Assistant::parseCommandsWithLLM(const std::string& transcript) {
    std::vector<Command> result;

    const char* apiKey = std::getenv("OPENAI_API_KEY");
    if (!apiKey || std::string(apiKey).empty()) {
        std::cerr << "Jarvis: OPENAI_API_KEY is not set\n";
        return result;
    }

    static bool curlInitialized = false;
    if (!curlInitialized) {
        if (curl_global_init(CURL_GLOBAL_DEFAULT) != 0) {
            std::cerr << "Jarvis: curl_global_init failed\n";
            return result;
        }
        curlInitialized = true;
    }

    CURL* curl = curl_easy_init();
    if (!curl) {
        std::cerr << "Jarvis: curl_easy_init failed\n";
        return result;
    }

    std::string prompt = buildPrompt(transcript);

    json body;
    body["model"] = "gpt-4.1-mini";
    body["messages"] = json::array({
        json{{"role", "system"}, {"content", "You parse voice commands and return ONLY JSON."}},
        json{{"role", "user"}, {"content", prompt}}
    });
    body["max_tokens"] = 256;
    body["temperature"] = 0.0;

    std::string bodyStr = body.dump();

    struct curl_slist* headers = nullptr;
    std::string authHeader = std::string("Authorization: Bearer ") + apiKey;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    headers = curl_slist_append(headers, authHeader.c_str());

    CurlBuffer responseBuf;

    curl_easy_setopt(curl, CURLOPT_URL, "https://api.openai.com/v1/chat/completions");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POST, 1L);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(bodyStr.size()));
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, bodyStr.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curlWriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &responseBuf);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);

    CURLcode res = curl_easy_perform(curl);
    if (res != CURLE_OK) {
        std::cerr << "Jarvis: curl_easy_perform failed: " << curl_easy_strerror(res) << "\n";
        curl_slist_free_all(headers);
        curl_easy_cleanup(curl);
        return result;
    }

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    try {
        json j = json::parse(responseBuf.data);
        if (!j.contains("choices") || j["choices"].empty()) {
            std::cerr << "Jarvis: unexpected LLM response\n";
            return result;
        }
        std::string content = j["choices"][0]["message"]["content"].get<std::string>();

        std::string trimmed = trim_copy(content);
        if (trimmed == "null") return result;

        json parsed = json::parse(trimmed);

        auto push_from_json = [&](const json& cmdJson) {
            Command cmd;
            cmd.name = cmdJson.value("name", "");
            cmd.rawText = cmdJson.value("raw_text", transcript);
            if (cmd.name.empty()) return;

            if (cmdJson.contains("args") && cmdJson["args"].is_object()) {
                for (auto it = cmdJson["args"].begin(); it != cmdJson["args"].end(); ++it) {
                    if (it.value().is_string()) {
                        cmd.args[it.key()] = it.value().get<std::string>();
                    } else {
                        cmd.args[it.key()] = it.value().dump();
                    }
                }
            }
            result.push_back(std::move(cmd));
        };

        if (parsed.is_array()) {
            for (const auto& item : parsed) {
                if (item.is_object()) push_from_json(item);
            }
        } else if (parsed.is_object()) {
            push_from_json(parsed);
        }
    } catch (const std::exception& e) {
        std::cerr << "Jarvis: LLM parse error: " << e.what() << "\n";
    }

    return result;
}

// ---------- Assistant ----------

Assistant::Assistant(KeywordDetector detector,
                     CommandDispatcher& dispatcher,
                     std::size_t bufferMaxChars,
                     double detectIntervalSec,
                     bool llmEnabled)
    : buffer_(bufferMaxChars),
      detector_(std::move(detector)),
      dispatcher_(dispatcher),
      detectInterval_(detectIntervalSec),
      llmEnabled_(llmEnabled),
      stopFlag_(false),
      lastDetect_(std::chrono::steady_clock::now()) {}

void Assistant::onSttChunk(const std::string& chunk) {
    buffer_.add(chunk);
    auto now = std::chrono::steady_clock::now();
    auto elapsed = std::chrono::duration<double>(now - lastDetect_).count();
    if (elapsed >= detectInterval_) {
        lastDetect_ = now;
        detectAndRun();
    }
}

void Assistant::stop() {
    stopFlag_.store(true);
}

bool Assistant::shouldStop() const {
    return stopFlag_.load();
}

void Assistant::detectAndRun() {
    std::string tail = buffer_.tail(250);
    if (tail.find_first_not_of(" \t\n\r") == std::string::npos) return;

    std::string lower = toLowerCopy(tail);

    bool wants_spotify_url =
        (lower.find("spotify.com") != std::string::npos) ||
        (lower.find("spotify") != std::string::npos &&
         lower.find("dot com") != std::string::npos);

    std::string quickIntent = detector_.detectIntent(tail);
    if (wants_spotify_url && quickIntent == "open_spotify") {
        quickIntent.clear(); // let LLM treat it as URL
    }

    std::vector<Command> cmds;

    if (!quickIntent.empty()) {
        Command c;
        c.name = quickIntent;
        c.rawText = tail;
        cmds.push_back(std::move(c));
    } else if (llmEnabled_) {
        cmds = parseCommandsWithLLM(tail);
    }

    if (cmds.empty()) return;

    if (lastExecutedTail_ == tail) return;
    lastExecutedTail_ = tail;

    for (const auto& c : cmds) {
        dispatcher_.dispatch(c);
    }

    buffer_.clear();
}

// ---------- main() ----------

static std::atomic<bool> gStop(false);

static void handleSigInt(int) {
    gStop.store(true);
}

int main() {
    //making it global to avoid errors with signal.h
    ::signal(SIGINT, handleSigInt);

    KeywordDetector::Map patterns = {
    { "open_spotify",  { "open spotify", "spotify", "спотифай", "включи спотифай" } },
    { "open_browser",  { "open browser", "open firefox", "открой браузер", "открой хром" } },
    { "open_telegram", { "open telegram", "открой телеграм", "телега" } },
    { "open_discord",  { "open discord", "открой дискорд" } },
    { "open_steam",    { "open steam", "открой стим" } },

    { "open_terminal", {
    "open terminal",
    "terminal",
    "new terminal",
    "new terminal window",
    "открой терминал",
    "новое окно терминала",
    "open console",
    "open command line"
    }},


    { "open_vscode", {
        "open vs code",
        "open vscode",
        "open visual studio code",
        "new vs code window",
        "открой вс код",
        "открой визуал студио код",
        "открой вс",
      }},
};

    KeywordDetector detector(std::move(patterns));
    CommandDispatcher dispatcher;

    register_basic_actions(dispatcher);
    register_media_actions(dispatcher);
    register_system_actions(dispatcher);
    register_window_actions(dispatcher);
    
    Assistant assistant(std::move(detector), dispatcher, 2000, 0.7, true);

    std::cerr << "Jarvis: waiting for STT text on stdin (Ctrl+C to stop)\n";

    std::string line;
    while (!gStop.load() && std::getline(std::cin, line)) {
        if (line.empty()) continue;
        assistant.onSttChunk(line);
    }

    assistant.stop();
    std::cerr << "Jarvis: stopped\n";
    return 0;
}
