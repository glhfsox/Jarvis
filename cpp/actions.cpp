#include "actions.hpp"
#include <cstdlib>
#include <iostream>

//Helpers

static int run_cmd(const std::string& cmd) {
    std::cout << "Jarvis: run `" << cmd << "`\n";
    return std::system(cmd.c_str());
}

std::string toLowerCopy(const std::string& s); // from assistant.cpp

static std::string normalize_app_name(const std::string& raw) {
    std::string s = toLowerCopy(raw);

    auto contains = [&](const std::string& needle) {
        return s.find(needle) != std::string::npos;
    };

    if (contains("spot") || contains("спот")) return "spotify";


    if (contains("telegram") || contains("телеграм") || contains("tg")|| contains("телега") )
        return "telegram-desktop";

    if (contains("discord") || contains("дискорд") || contains("дс"))
        return "discord";

    if (contains("steam") || contains("стим"))
        return "steam";

    
    if (contains("firefox") || contains("браузер") || contains("mozilla") || contains("файерфокс"))
        return "firefox";

    if (contains("chrome") || contains("хром") || contains("google chrome"))
        return "google-chrome";

    if (contains("visual studio code") || contains("vs code") || contains("vscode") || contains("вс") || contains("вскод"))
        return "code";

    if (contains("gnome terminal") || contains("gnome-terminal") || contains("terminal") || contains("терминал"))
        return "gnome-terminal";

    return raw;
}


static int open_url_system(const std::string& rawUrl) {
    if (rawUrl.empty()) return -1;
    std::string url = rawUrl;

    // small convenience: "gmail" -> Gmail web
    if (url == "gmail") url = "https://mail.google.com";

    std::string lower = toLowerCopy(url);
    if (lower.rfind("http://", 0) != 0 && lower.rfind("https://", 0) != 0) {
        url = "https://" + url;
    }

    return run_cmd("firefox '" + url + "' &");
}

static int launch_app(const std::string& appExec) {
    if (appExec.empty()) return -1;
    return run_cmd(appExec);
}

static int close_app_system(const std::string& appExec) {
    if (appExec.empty()) return -1;
    return run_cmd("pkill -f '" + appExec + "'");
}

// basic open_url / open_app / close_app

static void handleOpenUrl(const Command& cmd) {
    auto it = cmd.args.find("url");
    if (it == cmd.args.end()) {
        std::cerr << "Jarvis: open_url: missing url\n";
        return;
    }
    open_url_system(it->second);
}

static void handleOpenApp(const Command& cmd) {
    auto it = cmd.args.find("name");
    if (it == cmd.args.end()) {
        std::cerr << "Jarvis: open_app: missing name\n";
        return;
    }
    std::string app = normalize_app_name(it->second);
    int rc = launch_app(app);
    if (rc != 0 && app == "spotify") {
        std::cerr << "Jarvis: spotify not found, opening web player\n";
        open_url_system("https://open.spotify.com/");
    }
}

static void handleCloseApp(const Command& cmd) {
    auto it = cmd.args.find("name");
    if (it == cmd.args.end()) {
        std::cerr << "Jarvis: close_app: missing name\n";
        return;
    }
    std::string app = normalize_app_name(it->second);
    close_app_system(app);
}

// Quick aliases for keywords

static void wrapOpenApp(const Command& cmd, const std::string& appName) {
    Command c;
    c.name = "open_app";
    c.args["name"] = appName;
    c.rawText = cmd.rawText;
    handleOpenApp(c);
}

static void handleOpenSpotifyQuick(const Command& cmd)   { wrapOpenApp(cmd, "spotify"); }
static void handleOpenBrowserQuick(const Command& cmd)   { wrapOpenApp(cmd, "firefox"); }
static void handleOpenTelegramQuick(const Command& cmd)  { wrapOpenApp(cmd, "telegram-desktop"); }
static void handleOpenDiscordQuick(const Command& cmd)   { wrapOpenApp(cmd, "discord"); }
static void handleOpenSteamQuick(const Command& cmd)     { wrapOpenApp(cmd, "steam"); }
static void handleOpenTerminalQuick(const Command& cmd)  { wrapOpenApp(cmd, "/usr/bin/gnome-terminal"); }
static void handleOpenVSCodeQuick(const Command& cmd)    { wrapOpenApp(cmd, "code"); }
// playerctl

static void handleMediaSimple(const std::string& subcmd) {
    run_cmd("playerctl " + subcmd);
}

static void handleMediaPlayPause(const Command&)  { handleMediaSimple("play-pause"); }
static void handleMediaNext(const Command&)       { handleMediaSimple("next"); }
static void handleMediaPrev(const Command&)       { handleMediaSimple("previous"); }
static void handleMediaVolUp(const Command&)      { handleMediaSimple("volume 0.05+"); }
static void handleMediaVolDown(const Command&)    { handleMediaSimple("volume 0.05-"); }

static void handleSystemLock(const Command&) {
    run_cmd("loginctl lock-session");
}

static void handleSystemShutdown(const Command&) {
    run_cmd("systemctl poweroff");
}

static void handleSystemReboot(const Command&) {
    run_cmd("systemctl reboot");
}

//  (wmctrl)

static void handleWindowFocus(const Command& cmd) {
    auto it = cmd.args.find("name");
    if (it == cmd.args.end()) {
        std::cerr << "Jarvis: window_focus: missing name\n";
        return;
    }
    std::string title = it->second;
    run_cmd("wmctrl -a '" + title + "'");
}

static void handleWindowClose(const Command& cmd) {
    auto it = cmd.args.find("name");
    if (it == cmd.args.end()) {
        std::cerr << "Jarvis: window_close: missing name\n";
        return;
    }
    std::string title = it->second;
    run_cmd("wmctrl -c '" + title + "'");
}

// registration api

void register_basic_actions(CommandDispatcher& disp) {
    disp.registerHandler("open_url",  handleOpenUrl);
    disp.registerHandler("open_app",  handleOpenApp);
    disp.registerHandler("close_app", handleCloseApp);

    disp.registerHandler("open_spotify",  handleOpenSpotifyQuick);
    disp.registerHandler("open_browser",  handleOpenBrowserQuick);
    disp.registerHandler("open_telegram", handleOpenTelegramQuick);
    disp.registerHandler("open_discord",  handleOpenDiscordQuick);
    disp.registerHandler("open_steam",    handleOpenSteamQuick);
    disp.registerHandler("open_terminal", handleOpenTerminalQuick);
    disp.registerHandler("open_vscode",   handleOpenVSCodeQuick);
}

void register_media_actions(CommandDispatcher& disp) {
    disp.registerHandler("media_play_pause",   handleMediaPlayPause);
    disp.registerHandler("media_next",         handleMediaNext);
    disp.registerHandler("media_prev",         handleMediaPrev);
    disp.registerHandler("media_volume_up",    handleMediaVolUp);
    disp.registerHandler("media_volume_down",  handleMediaVolDown);
}

void register_system_actions(CommandDispatcher& disp) {
    disp.registerHandler("system_lock",     handleSystemLock);
    disp.registerHandler("system_shutdown", handleSystemShutdown);
    disp.registerHandler("system_reboot",   handleSystemReboot);
}

void register_window_actions(CommandDispatcher& disp) {
    disp.registerHandler("window_focus", handleWindowFocus);
    disp.registerHandler("window_close", handleWindowClose);
}
