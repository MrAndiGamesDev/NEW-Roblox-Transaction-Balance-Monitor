import requests
import time
import json
import os
import threading
import asyncio
import tkinter as tk
from io import BytesIO
from PIL import Image, ImageTk
from loguru import logger
from tkinter import messagebox, scrolledtext, ttk
from datetime import datetime

# Global variables for GUI elements
monitoring_event = None
window = None
progress_label = None
progress_var = None
start_button = None
stop_button = None
save_button = None
discord_webhook_input = None
roblox_cookie_input = None
emoji_id_input = None
emoji_name_input = None
timer_input = None
roblox_transaction_balance_input = None
roblox_transaction_balance_label = None
roblox_cookie_label = None
log_output = None

# Load configuration from the JSON file
APP_DIR = os.path.join(os.path.expanduser("~"), ".roblox_transaction")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

# Rate limiting for API calls
RATE_LIMIT = 1.0  # seconds between API calls
last_api_call = 0

def rate_limited_request(*args, **kwargs):
    """Make a rate-limited request to prevent too many API calls."""
    global last_api_call
    current_time = time.time()
    sleep_time = RATE_LIMIT - (current_time - last_api_call)
    if sleep_time > 0:
        time.sleep(sleep_time)
    last_api_call = time.time()
    return requests.request(*args, **kwargs)

def sanitize_input(text):
    """Sanitize user input to prevent injection."""
    if not isinstance(text, str):
        return ""
    # Remove any non-printable characters
    return ''.join(char for char in text if char.isprintable())

def validate_webhook_url(url):
    """Validate Discord webhook URL format."""
    if not url.startswith(('http://', 'https://')):
        return False
    if 'discord.com/api/webhooks/' not in url:
        return False
    return True

def validate_emoji_id(emoji_id):
    """Validate Discord emoji ID format."""
    return emoji_id.isdigit()

def validate_roblosecurity(cookie):
    """Clean and validate the .ROBLOSECURITY cookie format."""
    if not cookie:
        return False, "Cookie is empty"
    
    # Remove any whitespace
    cookie = cookie.strip()
    
    # Check if it's a full cookie URL format and extract just the value
    if cookie.startswith('_|WARNING:-DO-NOT-SHARE-THIS'):
        return True, cookie
    
    # If it's not in the correct format, log an error
    logger.error("Cookie format is incorrect. It should start with '_|WARNING:-DO-NOT-SHARE-THIS'")
    return False, "Invalid cookie format. Please make sure you copied the entire cookie value."

def safe_file_write(file_path, content):
    """Safely write content to a file."""
    try:
        temp_path = file_path + '.tmp'
        with open(temp_path, 'w') as f:
            json.dump(content, f)
        os.replace(temp_path, file_path)
    except Exception as e:
        logger.error(f"Error writing file {file_path}: {e}")
        raise

def save_config_to_file(config):
    """Save the configuration to the JSON file with validation."""
    # Sanitize inputs
    sanitized_config = {
        "DISCORD_WEBHOOK_URL": sanitize_input(config["DISCORD_WEBHOOK_URL"]),
        "ROBLOSECURITY": sanitize_input(config["ROBLOSECURITY"]),
        "DISCORD_EMOJI_ID": sanitize_input(config["DISCORD_EMOJI_ID"]),
        "DISCORD_EMOJI_NAME": sanitize_input(config["DISCORD_EMOJI_NAME"]),
        "CHECK_INTERVAL": sanitize_input(config["CHECK_INTERVAL"]),
        "TOTAL_CHECKS_TYPE": sanitize_input(config["TOTAL_CHECKS_TYPE"])
    }
    
    if not os.path.exists(APP_DIR):
        os.makedirs(APP_DIR, mode=0o700)  # Secure permissions
        logger.info(f"Created application directory at {APP_DIR}")
    
    safe_file_write(CONFIG_FILE, sanitized_config)

# Default config loaded
config = {
    "DISCORD_WEBHOOK_URL": "",
    "ROBLOSECURITY": "",
    "DISCORD_EMOJI_ID": "",
    "DISCORD_EMOJI_NAME": "",  
    "CHECK_INTERVAL": "60",  # Default check interval of 60 seconds
    "TOTAL_CHECKS_TYPE": "Day"
}

icon_url = "https://raw.githubusercontent.com/MrAndiGamesDev/Roblox-Transaction-Application/refs/heads/main/Robux.png"  # Replace with actual URL

if not os.path.exists(CONFIG_FILE):
    save_config_to_file(config)
    logger.info(f"Config file '{CONFIG_FILE}' created with default values.")
else:
    try:
        with open(CONFIG_FILE, "r") as file:
            loaded_config = json.load(file)
            
        # Ensure all default keys are present
        for key, default_value in config.items():
            if key not in loaded_config:
                loaded_config[key] = default_value
                logger.warning(f"Missing key '{key}' in config. Using default value: {default_value}")
        
        config = loaded_config
        save_config_to_file(config)  # Update config file with any missing keys
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in config file {CONFIG_FILE}. Using default configuration.")
    except Exception as e:
        logger.error(f"Error loading config file: {e}. Using default configuration.")

# Discord webhook URL
DISCORD_WEBHOOK_URL = config["DISCORD_WEBHOOK_URL"]

# API endpoint and authentication
ALIVE_TIME = 3600

MONITORING_ROBUX = False

DATE_TYPE = config["TOTAL_CHECKS_TYPE"]

EMOJI_NAME = config.get("DISCORD_EMOJI_NAME", "Robux")
EMOJI_ID = config["DISCORD_EMOJI_ID"]

COOKIES = {
    '.ROBLOSECURITY': config["ROBLOSECURITY"]
}

# Fetch the authenticated user's ID
def get_authenticated_user_id():
    """Fetch the authenticated user's ID from Roblox API.""" 
    roblox_users_url = "https://users.roblox.com"
    response = rate_limited_request('GET', f"{roblox_users_url}/v1/users/authenticated", cookies=COOKIES)
    if response.status_code == 200:
        return response.json().get("id")
    else:
        logger.error("Failed to fetch authenticated user ID.")
        return None

USERID = get_authenticated_user_id()

ROBLOX_ECONOMY_API = "https://economy.roblox.com"
TRANSACTION_API_URL = f"{ROBLOX_ECONOMY_API}/v2/users/{USERID}/transaction-totals?timeFrame={DATE_TYPE}&transactionType=summary"
CURRENCY_API_URL = f"{ROBLOX_ECONOMY_API}/v1/users/{USERID}/currency"

FOLDERNAME = os.path.join(APP_DIR, "transaction_info")

if not os.path.exists(FOLDERNAME):
    os.makedirs(FOLDERNAME)
    logger.info(f"Created transaction info directory at {FOLDERNAME}")
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
    safe_file_write(TRANSACTION_DATA_FILE, data)

def save_last_robux(robux):
    """Save the current Robux balance to a separate file.""" 
    safe_file_write(ROBUX_FILE, {"robux": robux})

def send_discord_notification_for_transactions(changes):
    """Send a notification to the Discord webhook for transaction data changes with rate limiting."""
    if not validate_webhook_url(DISCORD_WEBHOOK_URL):
        logger.error("Invalid Discord webhook URL")
        return

    embed = {
        "title": "🔔Roblox Transaction Data Changed!",
        "description": "The transaction data has been updated",
        "fields": [{"name": key, "value": f"From <:{EMOJI_NAME}:{EMOJI_ID}> {abbreviate_number(old)} To <:{EMOJI_NAME}:{EMOJI_ID}> {abbreviate_number(new)}", "inline": False} for key, (old, new) in changes.items()],
        "color": 0x00ff00,
        "footer": {
            "text": f"Roblox Transaction Has Fetched"
        }
    }

    payload = {"embeds": [embed]}

    try:
        response = rate_limited_request('POST', DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Discord notification for transactions: {e}")

def send_discord_notification_for_robux(robux, last_robux):
    """Send a notification to the Discord webhook for Robux balance changes with rate limiting."""
    if not validate_webhook_url(DISCORD_WEBHOOK_URL):
        logger.error("Invalid Discord webhook URL")
        return

    embed = {
        "title": "🔔Robux Balance Changed!",
        "description": "The Robux balance has changed",
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
        response = rate_limited_request('POST', DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        logger.info("Discord Webhook Has Successfully Sent To Discord!")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Discord notification for Robux balance: {e}")

def check_transactions():
    """Check the transaction data and send Discord notifications if anything has changed.""" 
    try:
        last_transaction_data = load_last_transaction_data()
        response = rate_limited_request('GET', TRANSACTION_API_URL, cookies=COOKIES, timeout=10)

        if response.status_code == 401:
            logger.error("Roblox security cookie has expired. Please update your .ROBLOSECURITY cookie.")
            handle_auth_error()
            return
        elif response.status_code == 200:
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
        response = rate_limited_request('GET', CURRENCY_API_URL, cookies=COOKIES, timeout=10)

        if response.status_code == 401:
            logger.error("Roblox security cookie has expired. Please update your .ROBLOSECURITY cookie.")
            handle_auth_error()
            return
        elif response.status_code == 200:
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
        return False, "Emoji ID is required"
    if not config["DISCORD_EMOJI_NAME"]:
        return False, "Emoji Name is required"
    if not config["CHECK_INTERVAL"]:
        return False, "Check Interval is required"
    
    # Test Roblox cookie
    try:
        logger.info("Testing Roblox cookie authentication...")
        test_response = rate_limited_request(
            'GET', 
            "https://users.roblox.com/v1/users/authenticated", 
            cookies={'.ROBLOSECURITY': config["ROBLOSECURITY"]},
            timeout=10
        )
        
        logger.info(f"Roblox API response status code: {test_response.status_code}")
        if test_response.status_code == 401:
            response_text = test_response.text
            logger.error(f"Authentication failed. Response: {response_text}")
            return False, "Invalid or expired Roblox security cookie. Please update your .ROBLOSECURITY cookie."
        elif test_response.status_code != 200:
            response_text = test_response.text
            logger.error(f"Unexpected status code. Response: {response_text}")
            return False, f"Invalid Roblox security cookie. Status code: {test_response.status_code}"
            
        # Try to parse the response to ensure it's valid
        response_data = test_response.json()
        logger.info(f"Successfully authenticated as user ID: {response_data.get('id')}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during authentication: {str(e)}")
        return False, f"Could not connect to Roblox API: {str(e)}"
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response from Roblox API: {str(e)}")
        return False, "Invalid response from Roblox API"
    except Exception as e:
        logger.error(f"Unexpected error during authentication: {str(e)}")
        return False, f"Error during authentication: {str(e)}"
    
    return True, "Configuration is valid"

def handle_auth_error():
    """Handle authentication error by stopping monitoring and updating UI."""
    global monitoring_event, progress_label, progress_var, start_button, stop_button, roblox_cookie_input, roblox_cookie_label, save_button
    
    monitoring_event.clear()  # Stop monitoring
    progress_label.config(text="Authentication Error - Update Cookie")
    progress_var.set(0)
    start_button.config(state='disabled')
    stop_button.config(state='disabled')
    
    # Highlight the cookie input field
    roblox_cookie_input.config(bg="#4a1919")  # Dark red background
    roblox_cookie_label.config(fg="#ff6b6b")  # Light red text
    
    # Enable save button
    save_button.config(state='normal')
    
    messagebox.showerror(
        "Authentication Error", 
        "Your Roblox security cookie has expired.\n\n"
        "1. Go to Roblox.com and log in\n"
        "2. Press F12 to open Developer Tools\n"
        "3. Go to Application > Cookies > .ROBLOSECURITY\n"
        "4. Copy the cookie value and paste it here\n"
        "5. Click Save Config and try again"
    )

def start_monitoring():
    """Start monitoring transactions and Robux."""
    global monitoring_event, window, progress_var, progress_label
    logger.info("Starting Roblox Transaction & Robux Monitoring application...")
    try:
        # Validate configuration before starting
        is_valid, message = validate_config()
        if not is_valid:
            logger.error(f"Invalid configuration: {message}")
            messagebox.showerror("Configuration Error", message)
            return
        
        # Flag to control the loop
        monitoring_event = threading.Event()
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
    global monitoring_event, progress_label, progress_var, start_button, stop_button
    
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

def main_loop():
    """Start the transaction and Robux balance checks on intervals."""
    global monitoring_event, progress_label, progress_var, timer_input, window
    
    if not monitoring_event.is_set():
        return

    try:
        check_transactions()
        check_robux()
        
        # Get the current check interval
        try:
            check_interval = int(timer_input.get())
            if check_interval < 10:  # Minimum 10 seconds
                check_interval = 10
                window.after(0, lambda: timer_input.delete(0, tk.END))
                window.after(0, lambda: timer_input.insert(0, "10"))
        except ValueError:
            check_interval = 60  # Default check interval
            window.after(0, lambda: timer_input.delete(0, tk.END))
            window.after(0, lambda: timer_input.insert(0, str(60)))
        
        # Update progress bar using after method
        def update_progress(current_second):
            if not monitoring_event.is_set():
                return
            
            progress = (current_second + 1) / check_interval * 100
            time_left = check_interval - current_second - 1
            
            window.after(0, lambda: progress_var.set(progress))
            window.after(0, lambda: progress_label.config(text=f"Next check in {time_left} seconds"))
            
            if current_second + 1 < check_interval and monitoring_event.is_set():
                window.after(1000, lambda: update_progress(current_second + 1))
            elif monitoring_event.is_set():
                window.after(0, main_loop)
        
        update_progress(0)
        
    except Exception as e:
        logger.error(f"Error in monitoring loop: {str(e)}")
        if monitoring_event.is_set():
            window.after(5000, main_loop)  # Retry after 5 seconds

def apply_styles(widget):
    """Apply common styles to widgets.""" 
    widget.config(
        font=("Arial", 12),
        bg="#2e3b4e",
        fg="white",
        relief="flat",
        bd=2,
        highlightthickness=0,
        insertbackground='white'  # Make cursor white
    )
    
    # If it's an Entry widget, bind focus events
    if isinstance(widget, tk.Entry):
        widget.config(selectbackground="#4a76a8", selectforeground="white")  # Selection colors

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
    entry.config(fg="white")  # Always set to white when focused

def on_focus_out(entry, placeholder):
    """Set placeholder text when the entry field is not focused and empty.""" 
    if not entry.get():
        entry.insert(0, placeholder)
        entry.config(fg="grey")
    else:
        entry.config(fg="white")  # Keep text white if there's content

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

def show_tutorial(field_name):
    """Show a tutorial popup for the specified field."""
    tutorials = {
        "webhook": (
            "Discord Webhook Tutorial",
            "To get your Discord Webhook URL:\n\n"
            "1. Open Discord and go to your server\n"
            "2. Right-click on a channel and select 'Edit Channel'\n"
            "3. Click on 'Integrations'\n"
            "4. Click on 'Create Webhook'\n"
            "5. Click 'Copy Webhook URL'\n"
            "6. Paste the URL here"
        ),
        "cookie": (
            "Roblox Security Cookie Tutorial",
            "To get your .ROBLOSECURITY cookie:\n\n"
            "1. Go to Roblox.com and log in\n"
            "2. Press F12 to open Developer Tools\n"
            "3. Go to 'Application' tab\n"
            "4. Click 'Cookies' in the left sidebar\n"
            "5. Click on 'https://www.roblox.com'\n"
            "6. Find '.ROBLOSECURITY' and copy its value\n"
            "7. Paste it here"
        ),
        "emoji": (
            "Discord Emoji ID Tutorial",
            "To get your Discord Emoji ID:\n\n"
            "1. In Discord, type '\\' followed by your emoji name\n"
            "2. The emoji ID will appear in the format <:name:ID>\n"
            "3. Copy only the numbers or copy the emoji link (ID) part\n"
            "4. Paste the ID here"
        )
    }
    
    title, message = tutorials.get(field_name, ("Tutorial", "Please fill in this field."))
    messagebox.showinfo(title, message)

def save_config():
    """Save the configuration with validation and tutorials."""
    global discord_webhook_input, roblox_cookie_input, emoji_id_input, emoji_name_input, timer_input, roblox_transaction_balance_input
    global start_button, progress_label, roblox_cookie_label, save_button, window

    try:
        # Check if window is initialized
        if window is None:
            logger.error("Application window is not initialized")
            messagebox.showerror(
                "Configuration Error", 
                "Application is not fully initialized. Please restart the application."
            )
            return

        # Comprehensive check for input fields
        input_fields = [
            discord_webhook_input, roblox_cookie_input, emoji_id_input, 
            emoji_name_input, timer_input, roblox_transaction_balance_input
        ]
        
        # Check if any of the input fields are None
        if any(field is None for field in input_fields):
            logger.error("Some configuration input fields are not fully initialized")
            messagebox.showerror(
                "Configuration Error", 
                "Application is not fully initialized. Please restart the application."
            )
            return

        # Get input values safely
        webhook_url = discord_webhook_input.get().strip()
        roblosecurity = roblox_cookie_input.get().strip()
        emoji_id = emoji_id_input.get().strip()
        emoji_name = emoji_name_input.get().strip()  
        interval = timer_input.get().strip()
        
        # Default to "Year" if transaction balance input is empty or not set
        total_checks_type = roblox_transaction_balance_input.get().strip() or "Year"

        # Comprehensive input validation
        validation_errors = []

        # Webhook URL validation
        if not webhook_url:
            validation_errors.append("Discord Webhook URL is required")
        elif not validate_webhook_url(webhook_url):
            validation_errors.append("Invalid Discord webhook URL format")

        # Roblox Security Cookie validation
        if not roblosecurity:
            validation_errors.append("Roblox Security Cookie is required")
        else:
            is_valid_cookie, cookie_message = validate_roblosecurity(roblosecurity)
            if not is_valid_cookie:
                validation_errors.append(cookie_message)

        # Emoji ID validation
        if not emoji_id:
            validation_errors.append("Emoji ID is required")
        elif not validate_emoji_id(emoji_id):
            validation_errors.append("Invalid Discord emoji ID format")

        # Emoji Name validation
        if not emoji_name:
            validation_errors.append("Emoji Name is required")

        # Check Interval validation
        if not interval:
            validation_errors.append("Check Interval is required")
        else:
            try:
                interval_value = int(interval)
                if interval_value < 10:
                    validation_errors.append("Check Interval must be at least 10 seconds")
            except ValueError:
                validation_errors.append("Check Interval must be a valid number")

        # If there are validation errors, show them and return
        if validation_errors:
            error_message = "Please correct the following errors:\n\n" + "\n".join(f"• {error}" for error in validation_errors)
            logger.warning(f"Configuration validation failed: {error_message}")
            messagebox.showerror("Configuration Validation Failed", error_message)
            return

        # If we've passed all validations, update the config
        config.update({
            "DISCORD_WEBHOOK_URL": webhook_url,
            "ROBLOSECURITY": roblosecurity,
            "DISCORD_EMOJI_ID": emoji_id,
            "DISCORD_EMOJI_NAME": emoji_name,
            "CHECK_INTERVAL": interval,
            "TOTAL_CHECKS_TYPE": total_checks_type
        })

        # Save configuration
        save_config_to_file(config)
        
        # Reset UI styles for cookie input
        if roblox_cookie_input and roblox_cookie_label:
            roblox_cookie_input.config(bg="#2e3b4e")
            roblox_cookie_label.config(fg="white")
        
        # Re-enable start button and update progress label if config is valid
        is_valid, validation_message = validate_config()
        if is_valid:
            if start_button:
                start_button.config(state='normal')
            if save_button:
                save_button.config(state='normal')
            if progress_label:
                progress_label.config(text="Monitoring inactive")
            logger.info("Configuration saved and validated successfully")
            messagebox.showinfo("Success", "Configuration Saved Successfully!")
        else:
            logger.warning(f"Configuration saved but validation failed: {validation_message}")
            messagebox.showwarning("Partial Success", f"Configuration saved, but: {validation_message}")

    except Exception as e:
        error_msg = f"Unexpected error saving configuration: {str(e)}"
        logger.error(error_msg)
        messagebox.showerror("Unexpected Error", error_msg)

async def show_splash_screen():
    """Create a splash screen with simulated loading."""
    # Create temporary root window
    root = tk.Tk()
    root.withdraw()
    
    # Create splash screen
    splash = tk.Toplevel(root)
    splash.title("Roblox Transaction Monitor")
    splash.overrideredirect(True)  # Remove window decorations
    
    # Calculate center position
    width = 400
    height = 200
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    splash.geometry(f"{width}x{height}+{x}+{y}")
    
    # Configure splash screen appearance
    splash.configure(bg="#1d2636")
    splash_frame = tk.Frame(splash, bg="#2e3b4e", bd=2, relief="solid")
    splash_frame.place(relx=0.5, rely=0.5, anchor="center", width=380, height=180)
    
    # Add application name
    title_label = tk.Label(
        splash_frame, 
        text="Roblox Transaction\nMonitoring", 
        font=("Arial", 16, "bold"),
        bg="#2e3b4e",
        fg="white"
    )
    title_label.pack(pady=(20, 10))
    
    # Add loading text
    status_label = tk.Label(
        splash_frame,
        text="Initializing...",
        font=("Arial", 10),
        bg="#2e3b4e",
        fg="white"
    )
    status_label.pack(pady=(0, 10))
    
    # Configure progress bar style
    style = ttk.Style()
    style.configure(
        "Splash.Horizontal.TProgressbar",
        troughcolor='#1a1a1a',
        background='#4CAF50',
        darkcolor='#4CAF50',
        lightcolor='#4CAF50',
        bordercolor='#1a1a1a'
    )
    
    # Add progress bar
    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(
        splash_frame,
        style="Splash.Horizontal.TProgressbar",
        variable=progress_var,
        length=300,
        mode="determinate"
    )
    progress_bar.pack(pady=10)
    
    def update_progress(text, value):
        status_label.config(text=text)
        progress_var.set(value)
        splash.update()
    
    # Simulate loading steps
    loading_steps = [
        ("Starting application...", 10),
        ("Checking configuration...", 20),
        ("Loading resources...", 30),
        ("Preparing interface...", 50),
        ("Connecting to Roblox...", 70),
        ("Validating credentials...", 90),
        ("Finalizing...", 100)
    ]
    
    # Perform actual initialization tasks
    async def initialize_app():
        nonlocal splash, root
        
        # Perform initialization tasks with progress updates
        for text, progress in loading_steps:
            update_progress(text, progress)
            
            # Simulate some async work
            if progress == 30:
                # Load application icon
                try:
                    response = rate_limited_request('GET', icon_url)
                    response.raise_for_status()
                except Exception as e:
                    logger.warning(f"Failed to load application icon: {e}")
            
            elif progress == 50:
                # Validate configuration
                try:
                    is_valid, message = validate_config()
                    if not is_valid:
                        logger.warning(f"Configuration validation warning: {message}")
                except Exception as e:
                    logger.error(f"Configuration validation error: {e}")
            
            elif progress == 70:
                # Test Roblox API connectivity
                try:
                    test_response = rate_limited_request(
                        'GET', 
                        "https://users.roblox.com/v1/users/authenticated", 
                        cookies={'.ROBLOSECURITY': config["ROBLOSECURITY"]},
                        timeout=10
                    )
                    if test_response.status_code != 200:
                        logger.warning("Roblox API connectivity test failed")
                except Exception as e:
                    logger.error(f"Roblox API connectivity error: {e}")
            
            # Small delay to simulate work
            await asyncio.sleep(0.3)
        
        # Close splash screen
        splash.destroy()
        root.destroy()
    
    # Run initialization
    await initialize_app()
    
    return True

async def Initialize_gui():
    # Remove the existing splash screen code and replace with the new approach
    logger.info("Starting Roblox Transaction & Robux Monitoring application...")
    
    try:
        # Show splash screen and wait for initialization
        await show_splash_screen()
        
        # Create main window
        global window
        window = tk.Tk()
        response = rate_limited_request('GET', icon_url)
        response.raise_for_status()  # Raise an error for failed requests

        # Load the icon image
        img_data = BytesIO(response.content)
        icon = Image.open(img_data)
        icon = ImageTk.PhotoImage(icon)

        # Set the icon and window title
        window.iconphoto(False, icon)
        window.resizable(False, False)
        window.title("Roblox Transaction & Robux Monitoring")
        window.config(bg="#1d2636")
        window.geometry("800x700")
        
        # Create main frame
        main_frame = tk.Frame(window, bg="#1d2636")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create left frame for inputs
        left_frame = tk.Frame(main_frame, bg="#1d2636")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Input fields for configuration
        discord_webhook_label = tk.Label(left_frame, text="DISCORD WEBHOOK URL", bg="#1d2636", fg="white", font=("Arial", 10))
        discord_webhook_label.pack(pady=(5, 0))

        global discord_webhook_input
        discord_webhook_input = tk.Entry(left_frame, width=40, show="*")
        discord_webhook_input.insert(0, config["DISCORD_WEBHOOK_URL"])
        apply_styles(discord_webhook_input)
        discord_webhook_input.pack(pady=5)

        # Input fields for configuration
        roblox_cookie_label = tk.Label(left_frame, text=".ROBLOSECURITY", bg="#1d2636", fg="white", font=("Arial", 10))
        roblox_cookie_label.pack(pady=(5, 0))

        global roblox_cookie_input
        roblox_cookie_input = tk.Entry(left_frame, width=40, show="*")
        roblox_cookie_input.insert(0, config["ROBLOSECURITY"])
        apply_styles(roblox_cookie_input)
        roblox_cookie_input.pack(pady=5)

        # Input fields for configuration
        emoji_id_label = tk.Label(left_frame, text="Emoji ID", bg="#1d2636", fg="white", font=("Arial", 10))
        emoji_id_label.pack(pady=(5, 0))

        global emoji_id_input
        emoji_id_input = tk.Entry(left_frame, width=40)
        emoji_id_input.insert(0, config["DISCORD_EMOJI_ID"])
        apply_styles(emoji_id_input)
        emoji_id_input.pack(pady=5)

        # Input fields for configuration
        emoji_name_label = tk.Label(left_frame, text="Emoji Name", bg="#1d2636", fg="white", font=("Arial", 10))
        emoji_name_label.pack(pady=(5, 0))

        global emoji_name_input
        emoji_name_input = tk.Entry(left_frame, width=40)
        emoji_name_input.insert(0, config.get("DISCORD_EMOJI_NAME", ""))
        apply_styles(emoji_name_input)
        emoji_name_input.pack(pady=5)

        # Add timer input field
        timer_label = tk.Label(left_frame, text="Check Interval (seconds)", bg="#1d2636", fg="white", font=("Arial", 10))
        timer_label.pack(pady=(5, 0))

        global timer_input
        timer_input = tk.Entry(left_frame, width=40)
        timer_input.insert(0, str(config["CHECK_INTERVAL"]))
        apply_styles(timer_input)
        timer_input.pack(pady=5)

        # Add total checks transaction/balance field
        roblox_transaction_balance_label = tk.Label(left_frame, text="Total Checks (Transaction/Balance) Like (Day Month Year)", bg="#1d2636", fg="white", font=("Arial", 10))
        roblox_transaction_balance_label.pack(pady=(5, 0))

        global roblox_transaction_balance_input
        roblox_transaction_balance_input = tk.Entry(left_frame, width=40)
        roblox_transaction_balance_input.insert(0, str(config["TOTAL_CHECKS_TYPE"]))
        apply_styles(roblox_transaction_balance_input)
        roblox_transaction_balance_input.pack(pady=5)

        # Buttons
        save_button = tk.Button(left_frame, text="Save Config", command=save_config)
        apply_button_styles(save_button)
        save_button.pack(pady=10)

        global start_button
        start_button = tk.Button(left_frame, text="Start", command=start_monitoring)
        apply_button_styles(start_button)
        start_button.pack(pady=10)

        global stop_button
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
            bordercolor='#1a1a1a'
        )

        # Progress variables
        global progress_var
        progress_var = tk.DoubleVar()
        global progress_label
        progress_label = tk.Label(
            progress_frame, 
            text="Monitoring inactive", 
            bg="#1d2636", 
            fg="white", 
            font=("Arial", 10)
        )
        progress_label.pack(side=tk.TOP, pady=(0, 5))

        progress_bar = ttk.Progressbar(progress_frame,
            style="Custom.Horizontal.TProgressbar",
            variable=progress_var,
            mode='determinate',
            length=780
        )
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

        def update_log_output():
            """Manually trigger a refresh of the log output."""
            try:
                # Retrieve the current log contents from the text widget
                log_output.configure(state='normal')
                current_logs = log_output.get(1.0, tk.END)
                
                # If logs are empty or minimal, add a refresh message
                if not current_logs.strip():
                    log_output.insert(tk.END, "No logs available.\n")
                
                # Scroll to the end
                log_output.see(tk.END)
                log_output.configure(state='disabled')
                
                logger.info("Log output manually updated")
            except Exception as e:
                logger.error(f"Error updating log output: {e}")
                
                # Show error in log output
                log_output.configure(state='normal')
                log_output.insert(tk.END, f"\nError updating logs: {e}\n")
                log_output.see(tk.END)
                log_output.configure(state='disabled')

        # Add clear button
        clear_button = tk.Button(log_header, text="Clear Logs", command=clear_logs)
        apply_button_styles(clear_button)
        clear_button.pack(side=tk.RIGHT, padx=5, pady=5)

        # Add refresh button
        refresh_button = tk.Button(log_header, text="Refresh Logs", command=update_log_output)
        apply_button_styles(refresh_button)
        refresh_button.pack(side=tk.RIGHT, padx=5, pady=5)

        # Add log output text widget with improved styling
        global log_output
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

        # Add bottom right update logs button
        bottom_log_frame = tk.Frame(right_frame, bg="#1d2636")
        bottom_log_frame.pack(fill=tk.X, pady=(5,0))

        def update_logs_button_action():
            """Action for updating logs from the current log output."""
            try:
                # Retrieve the current log contents
                log_output.configure(state='normal')
                current_logs = log_output.get(1.0, tk.END)
                log_output.configure(state='disabled')
                
                # If logs are empty or minimal, add a refresh message
                if not current_logs.strip():
                    current_logs = "No logs available.\n"
                
                # Create a new log viewer window
                def create_log_viewer_window(logs):
                    log_viewer = tk.Toplevel(window)
                    log_viewer.title("Log Viewer")
                    response = rate_limited_request('GET', icon_url)
                    response.raise_for_status()  # Raise an error for failed requests

                    # Load the icon image
                    img_data = BytesIO(response.content)
                    icon = Image.open(img_data)
                    icon = ImageTk.PhotoImage(icon)

                    # Set the icon and window title
                    log_viewer.iconphoto(False, icon)
                    log_viewer.geometry("600x400")
                    log_viewer.config(bg="#1d2636")

                    log_text = scrolledtext.ScrolledText(
                        log_viewer, 
                        wrap=tk.WORD, 
                        font=("Consolas", 10),
                        bg="#1a1a1a", 
                        fg="white"
                    )
                    log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                    log_text.insert(tk.END, logs)
                    log_text.configure(state='disabled')

                create_log_viewer_window(current_logs)
                
                logger.info("Log output manually updated and displayed in a new window")
            except Exception as e:
                logger.error(f"Error updating logs: {e}")
                
                # Show error in a message box
                messagebox.showerror("Error", f"Could not update logs: {e}")

        bottom_update_logs_button = tk.Button(
            bottom_log_frame, 
            text="Update Logs", 
            command=update_logs_button_action
        )
        apply_button_styles(bottom_update_logs_button)
        bottom_update_logs_button.pack(side=tk.RIGHT, padx=5)

        # Create and configure GUI log handler
        gui_handler = GUILogHandler(log_output)
        logger.add(gui_handler, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

        # Configure buttons and initial state
        save_button.config(state='normal')
        start_button.config(state='normal')
        stop_button.config(state='disabled')

        # Start the main event loop
        window.mainloop()

        return True
    except Exception as e:
        logger.error(f"Error initializing GUI: {e}")
        messagebox.showerror("Initialization Error", str(e))

if __name__ == "__main__":
    asyncio.run(Initialize_gui())
