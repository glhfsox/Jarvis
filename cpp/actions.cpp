#include "actions.hpp"
#include <algorithm>
#include <cstdlib>
#include <cstdio>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <array>
#include <cstdint>
#include <fstream>
#include <limits.h>
#include <unistd.h>
#include <signal.h>
#include <nlohmann/json.hpp>

struct ContextMemory {
    std::string last_app;
    std::string last_url;
    std::string last_window_id;
    pid_t last_app_pid = -1;
    uint64_t seq_counter = 0;
    uint64_t last_app_seq = 0;
    uint64_t last_window_seq = 0;
};

static ContextMemory g_ctx;

struct RuntimeConfig {
    std::string default_browser = "firefox";
    std::string default_terminal = "gnome-terminal";
    int volume_step = 5;
    int brightness_step = 5;
};

static RuntimeConfig load_config() {
    RuntimeConfig cfg;
    const char* envPath = std::getenv("JARVIS_CONFIG");
    std::string path = envPath ? envPath : "jarvis.config.json";
    std::ifstream f(path);
    if (!f.is_open()) {
        return cfg;
    }

    try {
        nlohmann::json j;
        f >> j;
        if (j.contains("default_browser") && j["default_browser"].is_string()) {
            cfg.default_browser = j["default_browser"].get<std::string>();
        }
        if (j.contains("default_terminal") && j["default_terminal"].is_string()) {
            cfg.default_terminal = j["default_terminal"].get<std::string>();
        }
        if (j.contains("volume_step_percent") && j["volume_step_percent"].is_number_integer()) {
            cfg.volume_step = j["volume_step_percent"].get<int>();
        }
        if (j.contains("brightness_step_percent") && j["brightness_step_percent"].is_number_integer()) {
            cfg.brightness_step = j["brightness_step_percent"].get<int>();
        }
    } catch (const std::exception& e) {
        std::cerr << "Jarvis: failed to load config '" << path << "': " << e.what() << "\n";
    }
    return cfg;
}

static RuntimeConfig g_cfg = load_config();

//Helpers

std::string toLowerCopy(const std::string& s); // from assistant.cpp
static std::string find_window_id_by_title(const std::string& query);

static int run_cmd(const std::string& cmd) {
    std::cout << "Jarvis: run `" << cmd << "`\n";
    return std::system(cmd.c_str());
}

static pid_t spawn_and_get_pid(const std::string& cmd) {
    // start the command in background and echo its pid
    std::string shCmd = cmd + " & echo $!";
    FILE* pipe = popen(shCmd.c_str(), "r");
    if (!pipe) return -1;

    char buf[64];
    if (!fgets(buf, sizeof(buf), pipe)) {
        pclose(pipe);
        return -1;
    }
    pclose(pipe);
    long pid = std::strtol(buf, nullptr, 10);
    if (pid <= 0) return -1;
    return static_cast<pid_t>(pid);
}

static void remember_last_app(const std::string& app, pid_t pid) {
    g_ctx.last_app = app;
    g_ctx.last_app_pid = pid;
    g_ctx.seq_counter++;
    g_ctx.last_app_seq = g_ctx.seq_counter;
}

static void remember_last_window(const std::string& wid) {
    g_ctx.last_window_id = wid;
    g_ctx.seq_counter++;
    g_ctx.last_window_seq = g_ctx.seq_counter;
}

static std::string app_to_window_query(const std::string& app) {
    std::string lower = toLowerCopy(app);
    if (lower == "google-chrome" || lower == "chrome") return "chrome";
    if (lower == "telegram-desktop" || lower == "telegram") return "telegram";
    if (lower == "code" || lower == "vscode" || lower.find("visual") != std::string::npos) return "visual studio code";
    if (lower.find("firefox") != std::string::npos) return "firefox";
    if (lower.find("discord") != std::string::npos) return "discord";
    if (lower.find("spotify") != std::string::npos) return "spotify";
    if (lower.find("steam") != std::string::npos) return "steam";
    if (lower.find("konsole") != std::string::npos) return "konsole";
    if (lower.find("terminal") != std::string::npos) return "terminal";
    return app;
}

static bool close_window_by_title(const std::string& title) {
    if (title.empty()) return false;
    std::string wid = find_window_id_by_title(title);
    if (wid.empty()) return false;
    remember_last_window(wid);
    return run_cmd("wmctrl -i -c '" + wid + "'") == 0;
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

static std::string volume_delta(bool up) {
    int step = (g_cfg.volume_step > 0) ? g_cfg.volume_step : 5;
    return std::to_string(step) + "%"+ (up ? "+" : "-");
}

static std::string brightness_delta(bool up) {
    int step = (g_cfg.brightness_step > 0) ? g_cfg.brightness_step : 5;
    return up ? ("+" + std::to_string(step) + "%") : (std::to_string(step) + "%-");
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

    if (!g_cfg.default_terminal.empty()) {
        if (terminal_ok(g_cfg.default_terminal)) return g_cfg.default_terminal;
        std::cerr << "Jarvis: default_terminal='" << g_cfg.default_terminal << "' is not usable; falling back to auto-detect\n";
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
        std::cerr << "Jarvis: no terminal emulator found (set JARVIS_TERMINAL env or default_terminal in jarvis.config.json)\n";
        return -1;
    }

    auto try_launch = [&](const std::string& t) -> bool {
        std::string cmd = build_cmd(t);
        int rc = std::system(cmd.c_str());
        if (rc == 0) {
            remember_last_app(t, -1);
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

// basic window listing via wmctrl
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
    std::string best;
    for (const auto& w : list_windows()) {
        std::string tLower = toLowerCopy(w.title);
        if (tLower.find(qLower) != std::string::npos) {
            best = w.id;
        }
    }
    return best;
}

static void handleWindowInspect(const Command& cmd) {
    std::string query;
    auto it = cmd.args.find("name");
    if (it != cmd.args.end()) {
        query = it->second;
    }

    auto windows = list_windows();
    if (windows.empty()) {
        std::cerr << "Jarvis: no windows found via wmctrl\n";
        return;
    }

    std::cout << "Jarvis: open windows:\n";
    for (const auto& w : windows) {
        std::cout << "  id=" << w.id << " | " << w.title << "\n";
    }

    if (!query.empty()) {
        std::string qLower = toLowerCopy(query);
        std::string bestId;
        std::string bestTitle;
        for (const auto& w : windows) {
            std::string tLower = toLowerCopy(w.title);
            if (tLower.find(qLower) != std::string::npos) {
                bestId = w.id;
                bestTitle = w.title;
                break;
            }
        }
        if (!bestId.empty()) {
            remember_last_window(bestId);
            std::cout << "Jarvis: best match for '" << query << "': id=" << bestId
                      << " | " << bestTitle << "\n";
        } else {
            std::cout << "Jarvis: no window matching query '" << query << "'\n";
        }
    }
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

    std::string browser = g_cfg.default_browser.empty() ? "firefox" : g_cfg.default_browser;
    if (!have_cmd(browser)) {
        if (browser != "firefox" && have_cmd("firefox")) {
            browser = "firefox";
        } else {
            std::cerr
                << "Jarvis: browser '" << browser << "' not found (set default_browser in jarvis.config.json)\n";
            return -1;
        }
    }

    g_ctx.last_url = url;
    return run_cmd(browser + " '" + url + "' &");
}


static int launch_app(const std::string& appExec) {
    if (appExec.empty()) return -1;

    std::cout << "Jarvis: run `" << appExec << "`\n";
    pid_t pid = spawn_and_get_pid(appExec);
    if (pid > 0) {
        remember_last_app(appExec, pid);
        return 0;
    }

    // fallback if we couldn't get a pid
    int rc = std::system(appExec.c_str());
    if (rc == 0) {
        remember_last_app(appExec, -1);
    }
    return rc;
}



static int close_last_app_instance() {
    if (g_ctx.last_app.empty()) return -1;

    // prefer closing a single window matching the app title before killing processes
    if (close_window_by_title(app_to_window_query(g_ctx.last_app))) return 0;

    if (g_ctx.last_app_pid > 0) {
        if (::kill(g_ctx.last_app_pid, SIGTERM) == 0) {
            ::kill(g_ctx.last_app_pid, SIGKILL);
            return 0;
        }
    }

    if (g_ctx.last_app == "konsole") {
        return run_cmd("pkill -n konsole");
    }

    std::string cmdExact = "pkill -n -x '" + g_ctx.last_app + "'";
    if (std::system(cmdExact.c_str()) == 0) return 0;

    std::string cmd = "pkill -n -f '" + g_ctx.last_app + "'";
    if (std::system(cmd.c_str()) == 0) return 0;

    return -1;
}

static int close_app_system(const std::string& appExec) {
    if (appExec.empty()) return -1;
    std::string cmd =
        "pkill -x '" + appExec + "' || "
        "pkill -f '" + appExec + "'";
    return std::system(cmd.c_str());
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
        "wpctl set-volume @DEFAULT_AUDIO_SINK@ " + volume_delta(true),
        "pactl set-sink-volume @DEFAULT_SINK@ +" + std::to_string((g_cfg.volume_step > 0) ? g_cfg.volume_step : 5) + "%",
        "amixer -q -D pulse sset Master " + std::to_string((g_cfg.volume_step > 0) ? g_cfg.volume_step : 5) + "%+"
    );
}
static void handleSystemVolDown(const Command&) {
    system_volume(
        "wpctl set-volume @DEFAULT_AUDIO_SINK@ " + volume_delta(false),
        "pactl set-sink-volume @DEFAULT_SINK@ -" + std::to_string((g_cfg.volume_step > 0) ? g_cfg.volume_step : 5) + "%",
        "amixer -q -D pulse sset Master " + std::to_string((g_cfg.volume_step > 0) ? g_cfg.volume_step : 5) + "%-"
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

static void handleSystemBrightnessUp(const Command&)   { adjust_brightness(brightness_delta(true)); }
static void handleSystemBrightnessDown(const Command&) { adjust_brightness(brightness_delta(false)); }

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
    auto itId = cmd.args.find("id");
    if (itId != cmd.args.end() && !itId->second.empty()) {
        remember_last_window(itId->second);
        run_cmd("wmctrl -i -a '" + itId->second + "'");
        return;
    }

    auto it = cmd.args.find("name");
    if (it == cmd.args.end()) {
        std::cerr << "Jarvis: window_focus: missing name or id\n";
        return;
    }
    std::string title = it->second;
    std::string wid = find_window_id_by_title(title);
    if (wid.empty()) {
        std::cerr << "Jarvis: window_focus: no window matching '" << title << "'\n";
        return;
    }
    remember_last_window(wid);
    run_cmd("wmctrl -i -a '" + wid + "'");
}

static void handleWindowClose(const Command& cmd) {
    auto itId = cmd.args.find("id");
    if (itId != cmd.args.end() && !itId->second.empty()) {
        remember_last_window(itId->second);
        run_cmd("wmctrl -i -c '" + itId->second + "'");
        return;
    }

    auto it = cmd.args.find("name");
    if (it == cmd.args.end()) {
        std::cerr << "Jarvis: window_close: missing name or id\n";
        return;
    }
    std::string title = it->second;
    std::string wid = find_window_id_by_title(title);
    if (wid.empty()) {
        std::cerr << "Jarvis: window_close: no window matching '" << title << "'\n";
        return;
    }
    remember_last_window(wid);
    run_cmd("wmctrl -i -c '" + wid + "'");
}

static void handleWindowFocusLast(const Command&) {
    if (g_ctx.last_window_id.empty()) {
        std::cerr << "Jarvis: no last window remembered\n";
        return;
    }
    remember_last_window(g_ctx.last_window_id);
    run_cmd("wmctrl -i -a '" + g_ctx.last_window_id + "'");
}

static void handleWindowCloseLast(const Command&) {
    bool hasWindow = !g_ctx.last_window_id.empty();
    bool hasApp = !g_ctx.last_app.empty();

    if (!hasWindow && !hasApp) {
        std::cerr << "Jarvis: no last window or app instance remembered\n";
        return;
    }

    auto closeWindowById = [&]() -> bool {
        if (!hasWindow) return false;
        remember_last_window(g_ctx.last_window_id);
        return run_cmd("wmctrl -i -c '" + g_ctx.last_window_id + "'") == 0;
    };

    auto closeWindowByTitle = [&]() -> bool {
        if (!hasApp) return false;
        return close_window_by_title(app_to_window_query(g_ctx.last_app));
    };

    bool closed = false;

    bool windowIsNewer = hasWindow && g_ctx.last_window_seq >= g_ctx.last_app_seq;

    if (windowIsNewer) {
        closed = closeWindowById();
        if (!closed && hasApp) closed = closeWindowByTitle();
    } else if (hasApp) {
        // if the app was the last thing we interacted with, prefer its window match first
        closed = closeWindowByTitle();
        if (!closed && hasWindow) closed = closeWindowById();
    }

    if (!closed && hasApp) {
        closed = close_last_app_instance() == 0;
    }

    if (!closed) {
        std::cerr << "Jarvis: failed to close last window/app\n";
    }
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
    disp.registerHandler("window_focus",   handleWindowFocus);
    disp.registerHandler("window_close",   handleWindowClose);
    disp.registerHandler("window_inspect", handleWindowInspect);
    disp.registerHandler("window_focus_last",  handleWindowFocusLast);
    disp.registerHandler("window_close_last",  handleWindowCloseLast);
}
