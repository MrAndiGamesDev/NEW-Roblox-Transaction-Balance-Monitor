import requests
import time
import json
import os
import threading
import tkinter as tk
from io import BytesIO
from PIL import Image, ImageTk
from loguru import logger
from tkinter import messagebox, scrolledtext, ttk
from datetime import datetime

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

icon_url = "https://raw.githubusercontent.com/MrAndiGamesDev/Roblox-Transaction-Application/refs/heads/main/Robux.png"  # Replace with actual URL

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
DEFAULT_CHECK_INTERVAL = 60  # Default check interval in seconds

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

    embed = {
        "title": "🔔Roblox Transaction Data Changed!",
        "description": f"The transaction data has been updated",
        "fields": [{"name": key, "value": f"From <:{EMOJI_NAME}:{EMOJI_ID}> {abbreviate_number(old)} To <:{EMOJI_NAME}:{EMOJI_ID}> {abbreviate_number(new)}", "inline": False} for key, (old, new) in changes.items()],
        "color": 0x00ff00,
        "footer": {
            "text": f"Roblox Transaction Has Fetched"
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

    embed = {
        "title": "🔔Robux Balance Changed!",
        "description": f"The Robux balance has changed",
        "fields": [
            {"name": "Before", "value": f"<:{EMOJI_NAME}:{EMOJI_ID}> {abbreviate_number(last_robux)}", "inline": True},
            {"name": "After", "value": f"<:{EMOJI_NAME}:{EMOJI_ID}> {abbreviate_number(robux)}", "inline": True}
        ],
        "color": 0x00ff00 if robux > last_robux else 0xff0000,
        "footer": {
            "text": f"Robux Balance Has Fetched"
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
    try:
        last_transaction_data = load_last_transaction_data()
        response = requests.get(TRANSACTION_API_URL, cookies=COOKIES, timeout=10)

        if response.status_code == 200:
            transaction_data = response.json()
            changes = {key: (last_transaction_data.get(key, 0), value) for key, value in transaction_data.items() if value != last_transaction_data.get(key, 0)}
            if changes:
                send_discord_notification_for_transactions(changes)
                save_last_transaction_data(transaction_data)
        else:
            logger.error(f"Failed to fetch transaction data. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while checking transactions: {str(e)}")
    except Exception as e:
        logger.error(f"Error checking transactions: {str(e)}")

def check_robux():
    """Check the Robux balance and send a notification if it has changed.""" 
    try:
        last_robux = load_last_robux()
        response = requests.get(CURRENCY_API_URL, cookies=COOKIES, timeout=10)

        if response.status_code == 200:
            robux = response.json().get("robux", 0)
            if robux != last_robux:
                send_discord_notification_for_robux(robux, last_robux)
                save_last_robux(robux)
        else:
            logger.error(f"Failed to fetch Robux balance. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while checking Robux: {str(e)}")
    except Exception as e:
        logger.error(f"Error checking Robux: {str(e)}")

def validate_config():
    """Validate the configuration values."""
    if not config["DISCORD_WEBHOOK_URL"]:
        return False, "Discord Webhook URL is required"
    if not config["ROBLOSECURITY"]:
        return False, "Roblox Security Cookie is required"
    if not config["DISCORD_EMOJI_ID"]:
        return False, "Discord Emoji ID is required"
    
    # Test Roblox cookie
    try:
        test_response = requests.get("https://users.roblox.com/v1/users/authenticated", 
                                   cookies={'.ROBLOSECURITY': config["ROBLOSECURITY"]},
                                   timeout=10)
        if test_response.status_code != 200:
            return False, "Invalid Roblox security cookie"
    except:
        return False, "Could not connect to Roblox API"
    
    return True, "Configuration is valid"

def main_loop():
    """Start the transaction and Robux balance checks on intervals."""
    while monitoring_event.is_set():
        try:
            check_transactions()
            check_robux()
            
            # Get the current check interval
            try:
                check_interval = int(timer_input.get())
                if check_interval < 10:  # Minimum 10 seconds
                    check_interval = 10
                    timer_input.delete(0, tk.END)
                    timer_input.insert(0, "10")
            except ValueError:
                check_interval = DEFAULT_CHECK_INTERVAL
                timer_input.delete(0, tk.END)
                timer_input.insert(0, str(DEFAULT_CHECK_INTERVAL))
            
            # Update progress bar
            for i in range(check_interval):
                if not monitoring_event.is_set():
                    break
                progress_var.set((i + 1) / check_interval * 100)
                time_left = check_interval - i - 1
                progress_label.config(text=f"Next check in {time_left} seconds")
                time.sleep(1)
                window.update()
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
            time.sleep(5)  # Wait before retrying

def start_monitoring():
    """Start monitoring transactions and Robux."""
    if monitoring_event.is_set():
        logger.warning("Monitoring is already running")
        return
        
    # Validate configuration before starting
    is_valid, message = validate_config()
    if not is_valid:
        logger.error(f"Invalid configuration: {message}")
        messagebox.showerror("Configuration Error", message)
        return
    
    try:
        progress_label.config(text="Starting monitoring...")
        monitoring_event.set()
        
        # Run the main loop in a separate thread
        monitoring_thread = threading.Thread(target=main_loop, daemon=True)
        monitoring_thread.start()
        logger.info("Monitoring started.")
        
        # Enable/disable buttons
        start_button.config(state='disabled')
        stop_button.config(state='normal')
    except Exception as e:
        monitoring_event.clear()
        error_msg = f"Failed to start monitoring: {str(e)}"
        logger.error(error_msg)
        messagebox.showerror("Error", error_msg)
        progress_label.config(text="Monitoring inactive")
        progress_var.set(0)

def stop_monitoring():
    """Stop monitoring transactions and Robux."""
    try:
        monitoring_event.clear()
        progress_var.set(0)
        progress_label.config(text="Monitoring inactive")
        logger.info("Monitoring stopped.")
        
        # Enable/disable buttons
        start_button.config(state='normal')
        stop_button.config(state='disabled')
    except Exception as e:
        error_msg = f"Error stopping monitoring: {str(e)}"
        logger.error(error_msg)
        messagebox.showerror("Error", error_msg)

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

class GUILogHandler:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.configure(state='normal')
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Color coding for different message types
        if "ERROR" in message:
            self.text_widget.tag_config("error", foreground="red")
            self.text_widget.insert('end', f"{timestamp} | ", "timestamp")
            self.text_widget.insert('end', f"{message}\n", "error")
        elif "INFO" in message:
            self.text_widget.tag_config("info", foreground="#00ff00")
            self.text_widget.insert('end', f"{timestamp} | ", "timestamp")
            self.text_widget.insert('end', f"{message}\n", "info")
        else:
            self.text_widget.tag_config("default", foreground="white")
            self.text_widget.insert('end', f"{timestamp} | ", "timestamp")
            self.text_widget.insert('end', f"{message}\n", "default")
        
        self.text_widget.tag_config("timestamp", foreground="#ADD8E6")  # Light blue for timestamps
        self.text_widget.see('end')
        self.text_widget.configure(state='disabled')

    def flush(self):
        pass

if __name__ == "__main__":
    logger.info("Starting Roblox Transaction & Robux Monitoring application...")
    # Run GUI in a separate thread
    try:
        window = tk.Tk()
        response = requests.get(icon_url)
        response.raise_for_status()  # Raise an error for failed requests

        # Load the icon image
        img_data = BytesIO(response.content)
        icon = Image.open(img_data)
        icon = ImageTk.PhotoImage(icon)

        # Set the icon and window title
        window.iconphoto(False, icon)
        window.resizable(False, False)
        window.title("Roblox Transaction & Robux Monitoring")

        # Set the background color of the window
        window.config(bg="#1d2636")
        window.geometry("800x700")  # Increased height for progress bar

        # Create main frame
        main_frame = tk.Frame(window, bg="#1d2636")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create left frame for inputs
        left_frame = tk.Frame(main_frame, bg="#1d2636")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Input fields for configuration
        discord_webhook_label = tk.Label(left_frame, text="DISCORD WEBHOOK URL", bg="#1d2636", fg="white", font=("Arial", 10))
        discord_webhook_label.pack(pady=(5, 0))
        discord_webhook_input = tk.Entry(left_frame, width=40, show="*")
        discord_webhook_input.insert(0, config["DISCORD_WEBHOOK_URL"])
        apply_styles(discord_webhook_input)
        discord_webhook_input.pack(pady=5)

        # Input fields for configuration
        roblox_cookie_label = tk.Label(left_frame, text=".ROBLOSECURITY", bg="#1d2636", fg="white", font=("Arial", 10))
        roblox_cookie_label.pack(pady=(5, 0))
        roblox_cookie_input = tk.Entry(left_frame, width=40, show="*")
        roblox_cookie_input.insert(0, config["ROBLOSECURITY"])
        apply_styles(roblox_cookie_input)
        roblox_cookie_input.pack(pady=5)

        # Input fields for configuration
        emoji_id_label = tk.Label(left_frame, text="Emoji ID", bg="#1d2636", fg="white", font=("Arial", 10))
        emoji_id_label.pack(pady=(5, 0))
        emoji_id_input = tk.Entry(left_frame, width=40)
        emoji_id_input.insert(0, config["DISCORD_EMOJI_ID"])
        apply_styles(emoji_id_input)
        emoji_id_input.pack(pady=5)

        # Add timer input field
        timer_label = tk.Label(left_frame, text="Check Interval (seconds)", bg="#1d2636", fg="white", font=("Arial", 10))
        timer_label.pack(pady=(5, 0))
        timer_input = tk.Entry(left_frame, width=40)
        timer_input.insert(0, str(DEFAULT_CHECK_INTERVAL))
        apply_styles(timer_input)
        timer_input.pack(pady=5)

        # Buttons
        def save_config():
            """Save the configuration.""" 
            try:
                config["DISCORD_WEBHOOK_URL"] = discord_webhook_input.get()
                config["ROBLOSECURITY"] = roblox_cookie_input.get()
                config["DISCORD_EMOJI_ID"] = emoji_id_input.get()
                save_config_to_file(config)
                logger.info("Configuration saved successfully")
                messagebox.showinfo("Success", "Configuration Saved Successfully!")
            except Exception as e:
                error_msg = f"Error saving configuration: {str(e)}"
                logger.error(error_msg)
                messagebox.showerror("Error", error_msg)

        save_button = tk.Button(left_frame, text="Save Config", command=save_config)
        apply_button_styles(save_button)
        save_button.pack(pady=10)

        start_button = tk.Button(left_frame, text="Start", command=start_monitoring)
        apply_button_styles(start_button)
        start_button.pack(pady=10)

        stop_button = tk.Button(left_frame, text="Stop", command=stop_monitoring)
        apply_button_styles(stop_button)
        stop_button.pack(pady=10)
        stop_button.config(state='disabled')  # Initially disabled

        # Create progress frame
        progress_frame = tk.Frame(window, bg="#1d2636")
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Progress bar style
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Custom.Horizontal.TProgressbar",
                       troughcolor='#1a1a1a',
                       background='#4CAF50',
                       darkcolor='#4CAF50',
                       lightcolor='#4CAF50',
                       bordercolor='#1a1a1a')

        # Progress variables
        progress_var = tk.DoubleVar()
        progress_label = tk.Label(progress_frame, 
                                text="Monitoring inactive", 
                                bg="#1d2636", 
                                fg="white", 
                                font=("Arial", 10))
        progress_label.pack(side=tk.TOP, pady=(0, 5))

        progress_bar = ttk.Progressbar(progress_frame,
                                     style="Custom.Horizontal.TProgressbar",
                                     variable=progress_var,
                                     mode='determinate',
                                     length=780)
        progress_bar.pack(fill=tk.X)

        # Create right frame for log output
        right_frame = tk.Frame(main_frame, bg="#1d2636")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # Create log header frame
        log_header = tk.Frame(right_frame, bg="#2e3b4e")
        log_header.pack(fill=tk.X, pady=(0, 5))

        # Add "Log Output" label
        log_label = tk.Label(log_header, text="Log Output", bg="#2e3b4e", fg="white", font=("Arial", 12, "bold"))
        log_label.pack(side=tk.LEFT, padx=5, pady=5)

        def clear_logs():
            """Clear the log output text widget."""
            log_output.configure(state='normal')
            log_output.delete(1.0, tk.END)
            log_output.configure(state='disabled')
            logger.info("Log output cleared")

        # Add clear button
        clear_button = tk.Button(log_header, text="Clear Logs", command=clear_logs)
        apply_button_styles(clear_button)
        clear_button.pack(side=tk.RIGHT, padx=5, pady=5)

        # Add log output text widget with improved styling
        log_output = scrolledtext.ScrolledText(
            right_frame, 
            height=30, 
            bg="#1a1a1a",
            fg="white", 
            font=("Consolas", 10),
            padx=10,
            pady=10,
            wrap=tk.WORD
        )
        log_output.pack(fill=tk.BOTH, expand=True)
        log_output.configure(state='disabled')

        # Create and configure GUI log handler
        gui_handler = GUILogHandler(log_output)
        logger.add(gui_handler.write, format="{message}")

        # Log initial message
        logger.info("Application started - Waiting for configuration...")

        # Flag to control the loop
        monitoring_event = threading.Event()

        # Start the GUI
        window.protocol("WM_DELETE_WINDOW", window.quit)
        window.mainloop()
    except Exception as e:
        logger.error(f"Error starting the GUI thread: {e}")
        messagebox.showerror("Error", f"Error starting the GUI thread: {e}")
