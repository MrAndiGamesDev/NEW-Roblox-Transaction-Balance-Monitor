import requests
import time
import json
import os
import threading
import pytz
import tkinter as tk
from datetime import datetime
from loguru import logger
from tkinter import messagebox
from alive_progress import alive_bar

# Load configuration from the JSON file
CONFIG_FILE = "config.json"

def save_config_to_file(config):
    """Save the configuration to the JSON file.""" 
    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file)

# Default config loaded
config = {
    "DISCORD_WEBHOOK_URL": "",
    "ROBLOSECURITY": "",
    "DISCORD_EMOJI_ID": ""
}

if not os.path.exists(CONFIG_FILE):
    save_config_to_file(config)
    logger.info(f"Config file '{CONFIG_FILE}' created with default values.")
else:
    with open(CONFIG_FILE, "r") as file:
        config = json.load(file)

# Discord webhook URL
DISCORD_WEBHOOK_URL = config["DISCORD_WEBHOOK_URL"]

# API endpoint and authentication
ALIVE_TIME = 3600
CHECK_EVERY = 60

MONITORING_ROBUX = False

DATE_TYPE = "Year"

EMOJI_NAME = "Robux"
EMOJI_ID = config["DISCORD_EMOJI_ID"]

COOKIES = {
    '.ROBLOSECURITY': config["ROBLOSECURITY"]
}

# Fetch the authenticated user's ID
def get_authenticated_user_id():
    """Fetch the authenticated user's ID from Roblox API.""" 
    roblox_users_url = "https://users.roblox.com"
    response = requests.get(f"{roblox_users_url}/v1/users/authenticated", cookies=COOKIES)
    if response.status_code == 200:
        return response.json().get("id")
    else:
        logger.error("Failed to fetch authenticated user ID.")
        return None

USERID = get_authenticated_user_id()

ROBLOX_ECONOMY_API = "https://economy.roblox.com"
TRANSACTION_API_URL = f"{ROBLOX_ECONOMY_API}/v2/users/{USERID}/transaction-totals?timeFrame={DATE_TYPE}&transactionType=summary"
CURRENCY_API_URL = f"{ROBLOX_ECONOMY_API}/v1/users/{USERID}/currency"

FOLDERNAME = "Roblox Transaction Info"

if not os.path.exists(FOLDERNAME):
    os.makedirs(FOLDERNAME)
    logger.info("Made the folder")

# File to store the last known data
TRANSACTION_DATA_FILE = os.path.join(FOLDERNAME, "last_transaction_data.json")
ROBUX_FILE = os.path.join(FOLDERNAME, "last_robux.json")

# Define the timezone (for example, 'US/Eastern' for Eastern Standard Time)
TIMEZONE = 'US/Eastern'

def abbreviate_number(num):
    """Convert a large number to a more readable abbreviated format, supporting negative values.""" 
    abs_num = abs(num)
    
    if abs_num >= 1_000_000_000_000_000:
        return f"{num / 1_000_000_000_000_000:.2f}Q"
    if abs_num >= 1_000_000_000_000:
        return f"{num / 1_000_000_000_000:.2f}T"
    elif abs_num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f}B"
    elif abs_num >= 1_000_000:
        return f"{num / 1_000_000:.2f}M"
    elif abs_num >= 1_000:
        return f"{num / 1_000:.2f}K"
    else:
        return str(num)

def get_current_time_in_timezone():
    """Get the current time in the defined timezone with AM/PM.""" 
    timezone = pytz.timezone(TIMEZONE)
    current_time = datetime.now(timezone)
    return current_time

def load_last_transaction_data():
    """Load the last known transaction data from a file. Initialize with defaults if the file doesn't exist.""" 
    if os.path.exists(TRANSACTION_DATA_FILE):
        with open(TRANSACTION_DATA_FILE, "r") as file:
            return json.load(file)
    else:
        default_data = {key: 0 for key in [
            "salesTotal",
            "purchasesTotal",
            "affiliateSalesTotal",
            "groupPayoutsTotal",
            "currencyPurchasesTotal",
            "premiumStipendsTotal",
            "tradeSystemEarningsTotal",
            "tradeSystemCostsTotal",
            "premiumPayoutsTotal",
            "groupPremiumPayoutsTotal",
            "adSpendTotal",
            "developerExchangeTotal",
            "pendingRobuxTotal",
            "incomingRobuxTotal",
            "outgoingRobuxTotal",
            "individualToGroupTotal",
            "csAdjustmentTotal",
            "adsRevsharePayoutsTotal",
            "groupAdsRevsharePayoutsTotal",
            "subscriptionsRevshareTotal",
            "groupSubscriptionsRevshareTotal",
            "subscriptionsRevshareOutgoingTotal",
            "groupSubscriptionsRevshareOutgoingTotal",
            "publishingAdvanceRebatesTotal",
            "affiliatePayoutTotal"
        ]}
        save_last_transaction_data(default_data)
        return default_data

def load_last_robux():
    """Load the last known Robux balance from a separate file.""" 
    if os.path.exists(ROBUX_FILE):
        with open(ROBUX_FILE, "r") as file:
            return json.load(file).get("robux", 0)
    else:
        return 0

def save_last_transaction_data(data):
    """Save the current transaction data to a file.""" 
    with open(TRANSACTION_DATA_FILE, "w") as file:
        json.dump(data, file)

def save_last_robux(robux):
    """Save the current Robux balance to a separate file.""" 
    with open(ROBUX_FILE, "w") as file:
        json.dump({"robux": robux}, file)

def send_discord_notification_for_transactions(changes):
    """Send a notification to the Discord webhook for transaction data changes with an embed.""" 
    current_time = get_current_time_in_timezone().strftime('%m/%d/%Y %I:%M:%S %p')  # AM/PM format added

    embed = {
        "title": "🔔Roblox Transaction Data Changed!",
        "description": f"The transaction data has been updated at {current_time}.",
        "fields": [{"name": key, "value": f"From <:{EMOJI_NAME}:{EMOJI_ID}> {abbreviate_number(old)} To <:{EMOJI_NAME}:{EMOJI_ID}> {abbreviate_number(new)}", "inline": False} for key, (old, new) in changes.items()],
        "color": 0x00ff00,
        "footer": {
            "text": f"Roblox Transaction Has Fetched at {current_time}"
        }
    }

    payload = {"embeds": [embed]}

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Discord notification for transactions: {e}")

def send_discord_notification_for_robux(robux, last_robux):
    """Send a notification to the Discord webhook for Robux balance changes with an embed.""" 
    current_time = get_current_time_in_timezone().strftime('%m/%d/%Y %I:%M:%S %p')  # AM/PM format added

    embed = {
        "title": "🔔Robux Balance Changed!",
        "description": f"The Robux balance has changed",
        "fields": [
            {"name": "Before", "value": f"<:{EMOJI_NAME}:{EMOJI_ID}> {abbreviate_number(last_robux)}", "inline": True},
            {"name": "After", "value": f"<:{EMOJI_NAME}:{EMOJI_ID}> {abbreviate_number(robux)}", "inline": True}
        ],
        "color": 0x00ff00 if robux > last_robux else 0xff0000,
        "footer": {
            "text": f"Robux Balance Has Fetched at {current_time}"
        }
    }

    payload = {"embeds": [embed]}

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        logger.info("Discord Webhook Has Successfully Sent To Discord!")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Discord notification for Robux balance: {e}")

def check_transactions():
    """Check the transaction data and send Discord notifications if anything has changed.""" 
    last_transaction_data = load_last_transaction_data()
    response = requests.get(TRANSACTION_API_URL, cookies=COOKIES)

    if response.status_code == 200:
        transaction_data = response.json()
        changes = {key: (last_transaction_data.get(key, 0), value) for key, value in transaction_data.items() if value != last_transaction_data.get(key, 0)}
        if changes:
            send_discord_notification_for_transactions(changes)
            save_last_transaction_data(transaction_data)

def check_robux():
    """Check the Robux balance and send a notification if it has changed.""" 
    last_robux = load_last_robux()
    response = requests.get(CURRENCY_API_URL, cookies=COOKIES)

    if response.status_code == 200:
        robux = response.json().get("robux", 0)
        if robux != last_robux:
            send_discord_notification_for_robux(robux, last_robux)
            save_last_robux(robux)

# Flag to control the loop
monitoring_event = threading.Event()

def main_loop():
    """Main loop that continuously checks transactions and Robux balance.""" 
    while monitoring_event.is_set():
        with alive_bar(2, title="Checking...") as bar:
            check_transactions()
            bar()
            check_robux()
            bar()
        time.sleep(CHECK_EVERY)

# Run the GUI in a separate thread
def apply_styles(widget):
    """Apply common styles to widgets.""" 
    widget.config(font=("Arial", 12), bg="#2e3b4e", fg="white", relief="flat", bd=2, highlightthickness=0)

def apply_button_styles(button):
    """Apply button styles with hover effect.""" 
    button.config(font=("Arial", 12, "bold"), bg="#4CAF50", fg="white", activebackground="#45a049", relief="flat", bd=2)
    
    def on_enter(event):
        button.config(bg="#45a049")  # Lighter green on hover
    
    def on_leave(event):
        button.config(bg="#4CAF50")  # Original green color
    
    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)

def on_focus_in(entry, placeholder):
    """Remove placeholder text when the entry field is focused.""" 
    if entry.get() == placeholder:
        entry.delete(0, tk.END)
        entry.config(fg="white")

def on_focus_out(entry, placeholder):
    """Set placeholder text when the entry field is not focused and empty.""" 
    if not entry.get():
        entry.insert(0, placeholder)
        entry.config(fg="grey")

if __name__ == "__main__":
    # Run GUI in a separate thread
    try:
        """Run the GUI in a separate thread with enhanced styles.""" 
        window = tk.Tk()
        window.title("Roblox Transaction & Robux Monitoring")

        # Set the background color of the window
        window.config(bg="#1d2636")
        window.geometry("400x400")

        # Input fields for configuration
        discord_webhook_input = tk.Entry(window, width=40)
        discord_webhook_input.insert(0, config["DISCORD_WEBHOOK_URL"])
        discord_webhook_input.bind("<FocusIn>", lambda event: on_focus_in(discord_webhook_input, "Enter DISCORD WEBHOOK URL Here"))
        discord_webhook_input.bind("<FocusOut>", lambda event: on_focus_out(discord_webhook_input, "Enter DISCORD WEBHOOK URL Here"))
        apply_styles(discord_webhook_input)
        discord_webhook_input.pack(pady=5)

        roblox_cookie_input = tk.Entry(window, width=40)
        roblox_cookie_input.insert(0, config["ROBLOSECURITY"])
        roblox_cookie_input.bind("<FocusIn>", lambda event: on_focus_in(roblox_cookie_input, "Enter ROBLOSECURITY Here"))
        roblox_cookie_input.bind("<FocusOut>", lambda event: on_focus_out(roblox_cookie_input, "Enter ROBLOSECURITY Here"))
        apply_styles(roblox_cookie_input)
        roblox_cookie_input.pack(pady=5)

        emoji_id_input = tk.Entry(window, width=40)
        emoji_id_input.insert(0, config["DISCORD_EMOJI_ID"])
        emoji_id_input.bind("<FocusIn>", lambda event: on_focus_in(emoji_id_input, "Enter Discord Emoji ID Here"))
        emoji_id_input.bind("<FocusOut>", lambda event: on_focus_out(emoji_id_input, "Enter Discord Emoji ID Here"))
        apply_styles(emoji_id_input)
        emoji_id_input.pack(pady=5)

        def save_config():
            """Save the configuration.""" 
            config["DISCORD_WEBHOOK_URL"] = discord_webhook_input.get()
            config["ROBLOSECURITY"] = roblox_cookie_input.get()
            config["DISCORD_EMOJI_ID"] = emoji_id_input.get()
            save_config_to_file(config)
            messagebox.showinfo("Success", "Configuration Saved Successfully!")

        save_button = tk.Button(window, text="Save Config", command=save_config)
        apply_button_styles(save_button)
        save_button.pack(pady=10)

        def start_monitoring():
            """Start monitoring transactions and Robux.""" 
            monitoring_event.set()
            threading.Thread(target=main_loop, daemon=True).start()

        def stop_monitoring():
            """Stop monitoring transactions and Robux.""" 
            monitoring_event.clear()

        start_button = tk.Button(window, text="Start", command=start_monitoring)
        apply_button_styles(start_button)
        start_button.pack(pady=10)

        stop_button = tk.Button(window, text="Stop", command=stop_monitoring)
        apply_button_styles(stop_button)
        stop_button.pack(pady=10)

        # Start the GUI
        window.protocol("WM_DELETE_WINDOW", window.quit)  # Close window properly
        window.mainloop()
    except Exception as e:
        logger.error(f"Error starting the GUI thread: {e}")
        messagebox.showerror("Error", f"Error starting the GUI thread: {e}")