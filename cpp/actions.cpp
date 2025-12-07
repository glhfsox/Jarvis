#include "actions.hpp"
#include <algorithm>
#include <cstdlib>
#include <cstdio>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <array>
#include <limits.h>
#include <unistd.h>

//Helpers

static int run_cmd(const std::string& cmd) {
    std::cout << "Jarvis: run `" << cmd << "`\n";
    return std::system(cmd.c_str());
}

static bool have_cmd(const std::string& bin) {
    std::string probe = "command -v " + bin + " >/dev/null 2>&1";
    int rc = std::system(probe.c_str());
    return rc == 0;
}

static std::string cmd_path(const std::string& bin) {
    std::string path;
    std::string cmd = "command -v " + bin + " 2>/dev/null";
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) return {};
    char buf[512];
    if (fgets(buf, sizeof(buf), pipe)) {
        path = buf;
        if (!path.empty() && path.back() == '\n') path.pop_back();
    }
    pclose(pipe);
    return path;
}

std::string toLowerCopy(const std::string& s); // from assistant.cpp

static std::string shell_quote(const std::string& s) {
    std::string out = "'";
    for (char c : s) {
        if (c == '\'') out += "'\"'\"'";
        else out.push_back(c);
    }
    out.push_back('\'');
    return out;
}

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
        return "terminal";

    return raw;
}

static bool run_if_available(const std::string& bin, const std::string& cmd) {
    if (!have_cmd(bin)) return false;
    run_cmd(cmd);
    return true;
}

static void system_volume(const std::string& wpctlCmd,
                          const std::string& pactlCmd,
                          const std::string& amixerCmd) {
    if (run_if_available("wpctl", wpctlCmd)) return;
    if (run_if_available("pactl", pactlCmd)) return;
    if (run_if_available("amixer", amixerCmd)) return;
    std::cerr
        << "Jarvis: no volume control tools found (wpctl/pactl/amixer)\n"
        << "Jarvis: On Ubuntu, try:\n"
        << "  sudo apt install pulseaudio-utils   # for pactl\n"
        << "  sudo apt install alsa-utils         # for amixer\n";
}

static void adjust_brightness(const std::string& delta) {
    if (run_if_available("brightnessctl", "brightnessctl set " + delta)) return;
    if (delta == "+5%" && run_if_available("xbacklight", "xbacklight -inc 5")) return;
    if (delta == "5%-" && run_if_available("xbacklight", "xbacklight -dec 5")) return;
    std::cerr
        << "Jarvis: no brightness control tools found (brightnessctl/xbacklight)\n"
        << "Jarvis: On Ubuntu, install one of:\n"
        << "  sudo apt install brightnessctl\n"
        << "  sudo apt install xbacklight\n"
        << "Jarvis: If brightnessctl says 'Permission denied', add your user to the 'video' group\n";
}

static bool terminal_ok(const std::string& term) {
    if (!have_cmd(term)) return false;
    std::string check = term + " --version >/dev/null 2>&1";
    int rc = std::system(check.c_str());
    if (rc != 0) {
        std::cerr << "Jarvis: terminal '" << term << "' failed sanity check; skipping\n";
        return false;
    }
    return true;
}

static std::string find_terminal() {
    const char* envTerm = std::getenv("JARVIS_TERMINAL");
    if (envTerm && *envTerm) {
        std::string t(envTerm);
        if (terminal_ok(t)) return t;
        std::cerr << "Jarvis: JARVIS_TERMINAL='" << t << "' is not usable; falling back to auto-detect\n";
    }

    if (terminal_ok("gnome-terminal")) return "gnome-terminal";

    const char* candidates[] = {
        "x-terminal-emulator",
        "konsole",
        "kitty",
        "alacritty",
        "xfce4-terminal",
        "tilix",
        "xterm"
    };

    for (const char* cand : candidates) {
        if (terminal_ok(cand)) return cand;
    }

    return {};
}

static int launch_terminal(const std::string& optionalCmd = {}) {
    auto build_cmd = [&](const std::string& term) {
        if (optionalCmd.empty()) return term;
        std::string quotedCmd = shell_quote(optionalCmd + "; exec bash");
        if (term.find("gnome-terminal") != std::string::npos || term.find("xfce4-terminal") != std::string::npos || term.find("tilix") != std::string::npos) {
            return term + " -- bash -lc " + quotedCmd;
        }
        if (term.find("konsole") != std::string::npos) {
            return term + " -e bash -lc " + quotedCmd;
        }
        if (term.find("kitty") != std::string::npos || term.find("alacritty") != std::string::npos) {
            return term + " -e bash -lc " + quotedCmd;
        }
        return term + " -e bash -lc " + quotedCmd;
    };

    std::string term = find_terminal();
    if (term.empty()) {
        std::cerr << "Jarvis: no terminal emulator found (set JARVIS_TERMINAL env)\n";
        return -1;
    }

    auto try_launch = [&](const std::string& t) -> bool {
        std::string cmd = build_cmd(t);
        int rc = std::system(cmd.c_str());
        if (rc == 0) {
            std::cout << "Jarvis: run `" << cmd << "`\n";
            return true;
        }
        std::cerr << "Jarvis: terminal '" << t << "' failed to start (rc=" << rc << "), trying next\n";
        return false;
    };

    if (try_launch(term)) return 0;

    std::cerr << "Jarvis: no working terminal emulator could be launched\n";
    return -1;
}


// window helpers

struct WindowInfo {
    std::string id;
    std::string title;
};

static std::vector<WindowInfo> list_windows() {
    std::vector<WindowInfo> res;
    FILE* pipe = popen("wmctrl -l", "r");
    if (!pipe) {
        std::cerr
            << "Jarvis: wmctrl not available\n"
            << "Jarvis: On Ubuntu, install it with:\n"
            << "  sudo apt install wmctrl\n";
        return res;
    }

    char buf[2048];
    while (fgets(buf, sizeof(buf), pipe)) {
        std::string line(buf);
        if (line.size() < 3) continue;
        std::istringstream iss(line);
        std::string wid, desktop;
        if (!(iss >> wid >> desktop)) continue;
        std::string title;
        std::getline(iss, title);
        if (!title.empty() && title[0] == ' ') {
            title.erase(0, title.find_first_not_of(" \t"));
        }
        res.push_back({wid, title});
    }

    pclose(pipe);
    return res;
}

static std::string find_window_id_by_title(const std::string& query) {
    std::string qLower = toLowerCopy(query);
    for (const auto& w : list_windows()) {
        std::string tLower = toLowerCopy(w.title);
        if (tLower.find(qLower) != std::string::npos) {
            return w.id;
        }
    }
    return {};
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

    if (!have_cmd("firefox")) {
        std::cerr
            << "Jarvis: firefox browser not found\n"
            << "Jarvis: On Ubuntu, install it with:\n"
            << "  sudo apt install firefox\n";
        return -1;
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
    if (app == "terminal") {
        auto cmdIt = cmd.args.find("command");
        std::string termCmd = (cmdIt != cmd.args.end()) ? cmdIt->second : "";
        launch_terminal(termCmd);
        return;
    }

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

static void handleOpenTerminal(const Command& cmd) {
    auto it = cmd.args.find("command");
    std::string termCmd = (it != cmd.args.end()) ? it->second : "";
    launch_terminal(termCmd);
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
static void handleOpenVSCodeQuick(const Command& cmd)    { wrapOpenApp(cmd, "code"); }
// playerctl

static void handleMediaSimple(const std::string& subcmd) {
    if (!have_cmd("playerctl")) {
        std::cerr
            << "Jarvis: playerctl not found (media controls disabled)\n"
            << "Jarvis: On Ubuntu, install it with:\n"
            << "  sudo apt install playerctl\n";
        return;
    }
    run_cmd("playerctl " + subcmd);
}

static void handleMediaPlayPause(const Command&)  { handleMediaSimple("play-pause"); }
static void handleMediaNext(const Command&)       { handleMediaSimple("next"); }
static void handleMediaPrev(const Command&)       { handleMediaSimple("previous"); }
static void handleMediaVolUp(const Command&)      { handleMediaSimple("volume 0.05+"); }
static void handleMediaVolDown(const Command&)    { handleMediaSimple("volume 0.05-"); }
static void handleMediaSeekForward(const Command&) { run_cmd("playerctl position 10+"); }
static void handleMediaSeekBackward(const Command&) { run_cmd("playerctl position 10-"); }
static void handleMediaMute(const Command&)       {
    system_volume(
        "wpctl set-mute @DEFAULT_AUDIO_SINK@ 1",
        "pactl set-sink-mute @DEFAULT_SINK@ 1",
        "amixer -q -D pulse sset Master mute"
    );
}
static void handleMediaUnmute(const Command&)     {
    system_volume(
        "wpctl set-mute @DEFAULT_AUDIO_SINK@ 0",
        "pactl set-sink-mute @DEFAULT_SINK@ 0",
        "amixer -q -D pulse sset Master unmute"
    );
}

// system controls

static void handleSystemVolUp(const Command&)   {
    system_volume(
        "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+",
        "pactl set-sink-volume @DEFAULT_SINK@ +5%",
        "amixer -q -D pulse sset Master 5%+"
    );
}
static void handleSystemVolDown(const Command&) {
    system_volume(
        "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-",
        "pactl set-sink-volume @DEFAULT_SINK@ -5%",
        "amixer -q -D pulse sset Master 5%-"
    );
}
static void handleSystemVolMute(const Command&) {
    system_volume(
        "wpctl set-mute @DEFAULT_AUDIO_SINK@ 1",
        "pactl set-sink-mute @DEFAULT_SINK@ 1",
        "amixer -q -D pulse sset Master mute"
    );
}
static void handleSystemVolUnmute(const Command&) {
    system_volume(
        "wpctl set-mute @DEFAULT_AUDIO_SINK@ 0",
        "pactl set-sink-mute @DEFAULT_SINK@ 0",
        "amixer -q -D pulse sset Master unmute"
    );
}

static void handleSystemBrightnessUp(const Command&)   { adjust_brightness("+5%"); }
static void handleSystemBrightnessDown(const Command&) { adjust_brightness("5%-"); }

static void handleWifiOn(const Command&)  {
    if (!have_cmd("nmcli")) {
        std::cerr
            << "Jarvis: nmcli (NetworkManager CLI) not found\n"
            << "Jarvis: On Ubuntu, install it with:\n"
            << "  sudo apt install network-manager\n";
        return;
    }
    run_cmd("nmcli radio wifi on");
}
static void handleWifiOff(const Command&) {
    if (!have_cmd("nmcli")) {
        std::cerr
            << "Jarvis: nmcli (NetworkManager CLI) not found\n"
            << "Jarvis: On Ubuntu, install it with:\n"
            << "  sudo apt install network-manager\n";
        return;
    }
    run_cmd("nmcli radio wifi off");
}

static void handleBluetoothOn(const Command&)  {
    if (!have_cmd("bluetoothctl")) {
        std::cerr
            << "Jarvis: bluetoothctl not found\n"
            << "Jarvis: On Ubuntu, install it with:\n"
            << "  sudo apt install bluez\n";
        return;
    }
    run_cmd("bluetoothctl power on");
}
static void handleBluetoothOff(const Command&) {
    if (!have_cmd("bluetoothctl")) {
        std::cerr
            << "Jarvis: bluetoothctl not found\n"
            << "Jarvis: On Ubuntu, install it with:\n"
            << "  sudo apt install bluez\n";
        return;
    }
    run_cmd("bluetoothctl power off");
}

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
    std::string wid = find_window_id_by_title(title);
    if (wid.empty()) {
        std::cerr << "Jarvis: window_focus: no window matching '" << title << "'\n";
        return;
    }
    run_cmd("wmctrl -i -a '" + wid + "'");
}

static void handleWindowClose(const Command& cmd) {
    auto it = cmd.args.find("name");
    if (it == cmd.args.end()) {
        std::cerr << "Jarvis: window_close: missing name\n";
        return;
    }
    std::string title = it->second;
    std::string wid = find_window_id_by_title(title);
    if (wid.empty()) {
        std::cerr << "Jarvis: window_close: no window matching '" << title << "'\n";
        return;
    }
    run_cmd("wmctrl -i -c '" + wid + "'");
}

// registration api

void register_basic_actions(CommandDispatcher& disp) {
    disp.registerHandler("open_url",  handleOpenUrl);
    disp.registerHandler("open_app",  handleOpenApp);
    disp.registerHandler("close_app", handleCloseApp);
    disp.registerHandler("open_terminal", handleOpenTerminal);

    disp.registerHandler("open_spotify",  handleOpenSpotifyQuick);
    disp.registerHandler("open_browser",  handleOpenBrowserQuick);
    disp.registerHandler("open_telegram", handleOpenTelegramQuick);
    disp.registerHandler("open_discord",  handleOpenDiscordQuick);
    disp.registerHandler("open_steam",    handleOpenSteamQuick);
    disp.registerHandler("open_vscode",   handleOpenVSCodeQuick);
}

void register_media_actions(CommandDispatcher& disp) {
    disp.registerHandler("media_play_pause",   handleMediaPlayPause);
    disp.registerHandler("media_next",         handleMediaNext);
    disp.registerHandler("media_prev",         handleMediaPrev);
    disp.registerHandler("media_volume_up",    handleMediaVolUp);
    disp.registerHandler("media_volume_down",  handleMediaVolDown);
    disp.registerHandler("media_volume_mute",   handleMediaMute);
    disp.registerHandler("media_volume_unmute", handleMediaUnmute);
    disp.registerHandler("media_seek_forward",  handleMediaSeekForward);
    disp.registerHandler("media_seek_backward", handleMediaSeekBackward);
}

void register_system_actions(CommandDispatcher& disp) {
    disp.registerHandler("system_volume_up",     handleSystemVolUp);
    disp.registerHandler("system_volume_down",   handleSystemVolDown);
    disp.registerHandler("system_volume_mute",   handleSystemVolMute);
    disp.registerHandler("system_volume_unmute", handleSystemVolUnmute);

    disp.registerHandler("system_brightness_up",   handleSystemBrightnessUp);
    disp.registerHandler("system_brightness_down", handleSystemBrightnessDown);

    disp.registerHandler("wifi_on",  handleWifiOn);
    disp.registerHandler("wifi_off", handleWifiOff);

    disp.registerHandler("bluetooth_on",  handleBluetoothOn);
    disp.registerHandler("bluetooth_off", handleBluetoothOff);

    disp.registerHandler("system_lock",     handleSystemLock);
    disp.registerHandler("system_shutdown", handleSystemShutdown);
    disp.registerHandler("system_reboot",   handleSystemReboot);
}

void register_window_actions(CommandDispatcher& disp) {
    disp.registerHandler("window_focus", handleWindowFocus);
    disp.registerHandler("window_close", handleWindowClose);
}
