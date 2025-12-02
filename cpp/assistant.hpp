#pragma once

#include <string>
#include <map>
#include <vector>
#include <unordered_map>
#include <functional>
#include <mutex>
#include <atomic>
#include <chrono>


struct Command {
    std::string name;
    std::map<std::string, std::string> args;
    std::string rawText;
};


class CommandDispatcher {
public:
    using Handler = std::function<void(const Command&)>;

    void registerHandler(const std::string& name, Handler handler);
    void dispatch(const Command& cmd) const;

private:
    std::unordered_map<std::string, Handler> handlers_;
};


class TextBuffer {
public:
    explicit TextBuffer(std::size_t maxChars = 2000);

    void add(const std::string& text);
    std::string tail(std::size_t nChars) const;
    void clear();

private:
    std::size_t maxChars_;
    mutable std::mutex mutex_;
    std::string buffer_;
};

class KeywordDetector {
public:
    using Patterns = std::vector<std::string>;
    using Map = std::unordered_map<std::string, Patterns>;

    explicit KeywordDetector(Map patterns);

    std::string detectIntent(const std::string& text) const;

private:
    static std::string toLower(const std::string& s);
    static bool contains(const std::string& text, const std::string& pattern);

    Map patterns_;
};

std::string toLowerCopy(const std::string& s);

class Assistant {
public:
    Assistant(KeywordDetector detector,
              CommandDispatcher& dispatcher,
              std::size_t bufferMaxChars = 2000,
              double detectIntervalSec = 0.7,
              bool llmEnabled = true);

    void onSttChunk(const std::string& chunk);
    void stop();
    bool shouldStop() const;

private:
    void detectAndRun();
    std::vector<Command> parseCommandsWithLLM(const std::string& transcript);

    TextBuffer buffer_;
    KeywordDetector detector_;
    CommandDispatcher& dispatcher_;

    double detectInterval_;
    bool llmEnabled_;

    std::atomic<bool> stopFlag_;
    std::chrono::steady_clock::time_point lastDetect_;
    std::string lastExecutedTail_;
};
