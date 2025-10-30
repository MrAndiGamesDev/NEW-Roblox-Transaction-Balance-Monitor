#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
#  Roblox Transaction & Robux Monitor – CLI (Input Censoring)
#  Author: MrAndiGamesDev (Refactored by AI Becuase i dont know much about python)
# ─────────────────────────────────────────────────────────────────────────────
import os
import json
import time
import signal
import threading
import requests
from datetime import datetime
from getpass import getpass  # <-- Hides input
from typing import Dict, Any, Optional

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────────────────────
class Configuration:
    APP_DIR = os.path.join(os.path.expanduser("~"), ".roblox_transaction_history")
    CONFIG_FILE = os.path.join(APP_DIR, "config.json")
    STORAGE_DIR = os.path.join(APP_DIR, "transaction_info")

    DEFAULT_CONFIG = {
        "DISCORD_WEBHOOK_URL": "",
        "ROBLOSECURITY": "",
        "DISCORD_EMOJI_ID": "",
        "DISCORD_EMOJI_NAME": "robux",
        "CHECK_INTERVAL": "60",
        "TOTAL_CHECKS_TYPE": "Day"
    }

# Convenience aliases for backward compatibility
APP_DIR = Configuration.APP_DIR
CONFIG_FILE = Configuration.CONFIG_FILE
STORAGE_DIR = Configuration.STORAGE_DIR
DEFAULT_CONFIG = Configuration.DEFAULT_CONFIG

# ─────────────────────────────────────────────────────────────────────────────
#  Terminal Colors
# ─────────────────────────────────────────────────────────────────────────────
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

# ─────────────────────────────────────────────────────────────────────────────
#  Censoring Utility
# ─────────────────────────────────────────────────────────────────────────────
def censor(text: str, show_start: int = 20, show_end: int = 10) -> str:
    if not text:
        return ""
    if len(text) <= show_start + show_end:
        return "*" * len(text)
    return text[:show_start] + "..." + text[-show_end:]

def censor_webhook(url: str) -> str:
    return censor(url, show_start=20, show_end=10) if url else ""

def censor_cookie(cookie: str) -> str:
    return censor(cookie, show_start=30, show_end=10) if cookie else ""

# ─────────────────────────────────────────────────────────────────────────────
#  Utilities
# ─────────────────────────────────────────────────────────────────────────────
def rate_limited_request(*args, **kwargs):
    global _last_call
    now = time.time()
    sleep = 1.0 - (now - _last_call)
    if sleep > 0:
        time.sleep(sleep)
    _last_call = time.time()
    return requests.request(*args, **kwargs)
_last_call = 0

def abbreviate_number(num: int) -> str:
    abs_num = abs(num)
    for limit, suffix in [(1e15, "Q"), (1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if abs_num >= limit:
            return f"{num/limit:.2f}{suffix}"
    return str(num)

def safe_write(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

# ─────────────────────────────────────────────────────────────────────────────
#  Config Manager
# ─────────────────────────────────────────────────────────────────────────────
class Config:
    def __init__(self):
        os.makedirs(APP_DIR, exist_ok=True, mode=0o700)
        os.makedirs(STORAGE_DIR, exist_ok=True)
        self.data = DEFAULT_CONFIG.copy()
        self._load()

    def _load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    loaded = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    self.data[k] = loaded.get(k, v)
            except:
                print(f"{Colors.YELLOW}Warning: Invalid config, using defaults.{Colors.RESET}")
        self.save()

    def save(self):
        safe_write(CONFIG_FILE, self.data)

    def __getitem__(self, key): return self.data[key]
    def __setitem__(self, key, value): self.data[key] = value; self.save()

    def show_summary(self):
        print(f"{Colors.CYAN}Config Summary:{Colors.RESET}")
        print(f"  Webhook: {censor_webhook(self['DISCORD_WEBHOOK_URL'])}")
        print(f"  Cookie:  {censor_cookie(self['ROBLOSECURITY'])}")
        print(f"  Emoji:   {self['DISCORD_EMOJI_NAME']}:{self['DISCORD_EMOJI_ID']}")
        print(f"  Interval: {self['CHECK_INTERVAL']}s")
        print(f"  Timeframe: {self['TOTAL_CHECKS_TYPE']}\n")

# ─────────────────────────────────────────────────────────────────────────────
#  Storage
# ─────────────────────────────────────────────────────────────────────────────
class Storage:
    def __init__(self):
        self.trans_file = os.path.join(STORAGE_DIR, "last_transaction_data.json")
        self.robux_file = os.path.join(STORAGE_DIR, "last_robux.json")

    def load_transactions(self) -> dict:
        if not os.path.exists(self.trans_file):
            default = {k: 0 for k in [
                "salesTotal", "purchasesTotal", "affiliateSalesTotal", "groupPayoutsTotal",
                "currencyPurchasesTotal", "premiumStipendsTotal", "tradeSystemEarningsTotal",
                "tradeSystemCostsTotal", "premiumPayoutsTotal", "groupPremiumPayoutsTotal",
                "adSpendTotal", "developerExchangeTotal", "pendingRobuxTotal", "incomingRobuxTotal",
                "outgoingRobuxTotal", "individualToGroupTotal", "csAdjustmentTotal",
                "adsRevsharePayoutsTotal", "groupAdsRevsharePayoutsTotal", "subscriptionsRevshareTotal",
                "groupSubscriptionsRevshareTotal", "subscriptionsRevshareOutgoingTotal",
                "groupSubscriptionsRevshareOutgoingTotal", "publishingAdvanceRebatesTotal",
                "affiliatePayoutTotal"
            ]}
            self.save_transactions(default)
            return default
        with open(self.trans_file) as f:
            return json.load(f)

    def save_transactions(self, data: dict):
        safe_write(self.trans_file, data)

    def load_robux(self) -> int:
        if not os.path.exists(self.robux_file):
            return 0
        try:
            with open(self.robux_file) as f:
                return json.load(f).get("robux", 0)
        except:
            return 0

    def save_robux(self, robux: int):
        safe_write(self.robux_file, {"robux": robux})

# ─────────────────────────────────────────────────────────────────────────────
#  Roblox API
# ─────────────────────────────────────────────────────────────────────────────
class RobloxAPI:
    def __init__(self, cookie: str):
        self.cookies = {".ROBLOSECURITY": cookie}
        self.user_id = None

    def authenticate(self) -> bool:
        try:
            r = rate_limited_request("GET", "https://users.roblox.com/v1/users/authenticated", cookies=self.cookies, timeout=10)
            if r.status_code == 200:
                self.user_id = r.json().get("id")
                print(f"{Colors.CYAN}Authenticated as user ID: {self.user_id}{Colors.RESET}")
                return True
        except Exception as e:
            print(f"{Colors.RED}Auth failed: {e}{Colors.RESET}")
        return False

    def get_transaction_totals(self, timeframe: str) -> Optional[dict]:
        if not self.user_id: return None
        url = f"https://economy.roblox.com/v2/users/{self.user_id}/transaction-totals?timeFrame={timeframe}&transactionType=summary"
        r = rate_limited_request("GET", url, cookies=self.cookies, timeout=10)
        return r.json() if r.status_code == 200 else None

    def get_robux(self) -> Optional[int]:
        if not self.user_id: return None
        r = rate_limited_request("GET", f"https://economy.roblox.com/v1/users/{self.user_id}/currency", cookies=self.cookies, timeout=10)
        return r.json().get("robux") if r.status_code == 200 else None

    def get_account_status(self) -> Optional[dict]:
        if not self.user_id: return None
        r = rate_limited_request("GET", f"https://users.roblox.com/v1/users/{self.user_id}", cookies=self.cookies, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "is_banned": data.get("isBanned", False),
                "username": data.get("name", "Unknown"),
                "created": data.get("created", "Unknown")
            }
        return None

# ─────────────────────────────────────────────────────────────────────────────
#  Discord Notifier
# ─────────────────────────────────────────────────────────────────────────────
class DiscordNotifier:
    def __init__(self, url: str, emoji_name: str, emoji_id: str):
        self.url = url
        self.emoji = f"<:{emoji_name}:{emoji_id}>"

    def send(self, embed: dict):
        if not self.url or "discord.com" not in self.url:
            return
        try:
            r = rate_limited_request("POST", self.url, json={"embeds": [embed]})
            r.raise_for_status()
        except:
            pass

    def transaction_change(self, changes: dict):
        fields = [
            {"name": k, "value": f"From {self.emoji} {abbreviate_number(old)} to {self.emoji} {abbreviate_number(new)}", "inline": False}
            for k, (old, new) in changes.items()
        ]
        self.send({
            "title": "Roblox Transaction Updated",
            "color": 0x00ff00,
            "fields": fields,
            "timestamp": datetime.utcnow().isoformat()
        })

    def robux_change(self, old: int, new: int):
        self.send({
            "title": "Robux Balance Changed",
            "color": 0x00ff00 if new > old else 0xff0000,
            "fields": [
                {"name": "Before", "value": f"{self.emoji} {abbreviate_number(old)}", "inline": True},
                {"name": "After", "value": f"{self.emoji} {abbreviate_number(new)}", "inline": True}
            ],
            "timestamp": datetime.utcnow().isoformat()
        })

    def account_status(self, status: dict, previous: dict = None):
        color = 0xff0000 if status.get("is_banned") else 0x00ff00
        desc = "Status changed!" if previous and previous != status else None
        self.send({
            "title": f"Account {'BANNED' if status.get('is_banned') else 'ACTIVE'}",
            "description": desc,
            "color": color,
            "fields": [
                {"name": "User", "value": status.get("username", "Unknown"), "inline": True},
                {"name": "Created", "value": status.get("created", "Unknown"), "inline": True}
            ],
            "timestamp": datetime.utcnow().isoformat()
        })

    def api_downtime(self, status: str, duration: float = None):
        color = 0xff0000 if status == "STARTED" else 0x00ff00
        fields = []
        if duration:
            fields.append({"name": "Duration", "value": f"{duration:.1f}s", "inline": False})
        self.send({
            "title": f"Roblox API {status}",
            "color": color,
            "fields": fields,
            "timestamp": datetime.utcnow().isoformat()
        })

# ─────────────────────────────────────────────────────────────────────────────
#  Monitor
# ─────────────────────────────────────────────────────────────────────────────
class Monitor:
    def __init__(self):
        self.config = Config()
        self.storage = Storage()
        self.api = RobloxAPI(self.config["ROBLOSECURITY"])
        self.notifier = DiscordNotifier(
            self.config["DISCORD_WEBHOOK_URL"],
            self.config["DISCORD_EMOJI_NAME"],
            self.config["DISCORD_EMOJI_ID"]
        )
        self.stop_event = threading.Event()
        self.last_status = None
        self.downtime_start = None

    def start(self):
        print(f"{Colors.BOLD}{Colors.MAGENTA}Roblox Transaction & Robux Monitor (CLI){Colors.RESET}\n")
        self.config.show_summary()

        if not self.api.authenticate():
            print(f"{Colors.RED}Cannot start: Invalid or expired .ROBLOSECURITY cookie.{Colors.RESET}")
            return

        print(f"{Colors.GREEN}Monitoring started. Press Ctrl+C to stop.{Colors.RESET}")
        signal.signal(signal.SIGINT, self._signal_handler)

        while not self.stop_event.is_set():
            try:
                if not self._check_api():
                    self._wait()
                    continue

                self._check_transactions()
                self._check_robux()
                self._check_account_status()

            except Exception as e:
                print(f"{Colors.RED}Error: {e}{Colors.RESET}")

            self._wait()

    def _check_api(self) -> bool:
        try:
            r = rate_limited_request("GET", "https://users.roblox.com/v1/users/authenticated", cookies=self.api.cookies, timeout=10)
            if r.status_code == 200:
                if self.downtime_start:
                    duration = time.time() - self.downtime_start
                    self.notifier.api_downtime("RECOVERED", duration)
                    print(f"{Colors.GREEN}API recovered after {duration:.1f}s{Colors.RESET}")
                    self.downtime_start = None
                return True
        except:
            pass

        if not self.downtime_start:
            self.downtime_start = time.time()
            self.notifier.api_downtime("STARTED")
            print(f"{Colors.RED}Roblox API unreachable. Retrying...{Colors.RESET}")
        return False

    def _check_transactions(self):
        data = self.api.get_transaction_totals(self.config["TOTAL_CHECKS_TYPE"])
        if not data: return
        last = self.storage.load_transactions()
        changes = {k: (last.get(k, 0), v) for k, v in data.items() if v != last.get(k, 0)}
        if changes:
            print(f"{Colors.YELLOW}Transaction changes detected:{Colors.RESET}")
            for k, (o, n) in changes.items():
                print(f"  {Colors.CYAN}{k}: {abbreviate_number(o)} to {abbreviate_number(n)}{Colors.RESET}")
            self.notifier.transaction_change(changes)
            self.storage.save_transactions(data)

    def _check_robux(self):
        robux = self.api.get_robux()
        if robux is None: return
        last = self.storage.load_robux()
        if robux != last:
            change = "Increased" if robux > last else "Decreased"
            print(f"{Colors.MAGENTA}Robux {change}: {abbreviate_number(last)} to {abbreviate_number(robux)}{Colors.RESET}")
            self.notifier.robux_change(last, robux)
            self.storage.save_robux(robux)

    def _check_account_status(self):
        status = self.api.get_account_status()
        if not status: return
        if self.last_status != status:
            banned = status.get("is_banned", False)
            print(f"{Colors.RED if banned else Colors.GREEN}Account {'BANNED' if banned else 'ACTIVE'}: {status['username']}{Colors.RESET}")
            self.notifier.account_status(status, self.last_status)
            self.last_status = status

    def _wait(self):
        interval = max(10, int(self.config["CHECK_INTERVAL"] or 60))
        for i in range(interval):
            if self.stop_event.is_set():
                break
            mins, secs = divmod(interval - i, 60)
            print(f"\r{Colors.BLUE}Next check in {mins:02d}:{secs:02d}{Colors.RESET}", end="", flush=True)
            time.sleep(1)
        print()

    def _signal_handler(self, signum, frame):
        print(f"\n{Colors.YELLOW}Shutting down gracefully...{Colors.RESET}")
        self.stop_event.set()

# ─────────────────────────────────────────────────────────────────────────────
#  Setup Wizard (First Run) – ALL INPUTS HIDDEN
# ─────────────────────────────────────────────────────────────────────────────
def setup_wizard():
    print(f"{Colors.BOLD}{Colors.CYAN}Roblox Monitor CLI - First Time Setup{Colors.RESET}\n")
    print("Enter the following details (input is hidden for security):\n")

    webhook = getpass(f"{Colors.YELLOW}Discord Webhook URL (Hidden):{Colors.RESET} ").strip()
    cookie = getpass(f"{Colors.YELLOW}.ROBLOSECURITY Cookie (Hidden):{Colors.RESET} ").strip()
    emoji_id = getpass(f"{Colors.YELLOW}Emoji ID (Hidden):{Colors.RESET} ").strip()
    emoji_name = input(f"{Colors.YELLOW}Emoji Name (default: robux):{Colors.RESET} ").strip() or "robux"
    interval = input(f"{Colors.YELLOW}Check Interval (seconds, default: 60):{Colors.RESET} ").strip() or "60"
    timeframe = input(f"{Colors.YELLOW}Timeframe (Day/Week/Month/Year, default: Day):{Colors.RESET} ").strip() or "Day"

    config = Config()
    if webhook: config["DISCORD_WEBHOOK_URL"] = webhook
    if cookie: config["ROBLOSECURITY"] = cookie
    if emoji_id: config["DISCORD_EMOJI_ID"] = emoji_id
    if emoji_name: config["DISCORD_EMOJI_NAME"] = emoji_name
    if interval: config["CHECK_INTERVAL"] = interval
    if timeframe: config["TOTAL_CHECKS_TYPE"] = timeframe

    print(f"\n{Colors.GREEN}Config saved securely to {CONFIG_FILE}{Colors.RESET}")

# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    config = Config()

    # First run?
    if not config["ROBLOSECURITY"]:
        setup_wizard()
        print(f"\n{Colors.CYAN}Edit config later: {CONFIG_FILE}{Colors.RESET}\n")
        return

    # Validate cookie format
    if not config["ROBLOSECURITY"].startswith("_|WARNING"):
        print(f"{Colors.RED}Invalid .ROBLOSECURITY cookie format. Must start with '_|WARNING' {Colors.RESET}")
        return

    monitor = Monitor()
    monitor.start()

if __name__ == "__main__":
    main()