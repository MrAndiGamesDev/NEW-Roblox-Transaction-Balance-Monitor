import requests
import time
import json
import os
import threading
import asyncio
import sys
import platform
import random
import io
import tkinter as tk
import webbrowser
from io import BytesIO
from PIL import Image, ImageTk
from loguru import logger
from tkinter import messagebox, scrolledtext, ttk
from datetime import datetime
import traceback

# Global variables for GUI elements
monitoring_event = None
window = None
progress_label = None
progress_var = None
start_button = None
stop_button = None
save_button = None
roblox_transaction_balance_input = None
discord_webhook_input = None
roblox_cookie_input = None
emoji_id_input = None
emoji_name_input = None
timer_input = None
roblox_transaction_balance_label = None
roblox_cookie_label = None
log_output = None
credits_window = None
credits_button = None

# Global variables for downtime tracking
DOWNTIME_THRESHOLD = 3  # Number of consecutive failed checks before declaring downtime
CURRENT_DOWNTIME_STREAK = 0
TOTAL_DOWNTIME_DURATION = 0
LAST_SUCCESSFUL_CHECK = None
IS_IN_DOWNTIME = False

# Add a global variable to track last downtime notification time to prevent spam
LAST_DOWNTIME_NOTIFICATION_TIME = None
DOWNTIME_NOTIFICATION_COOLDOWN = 15 * 60  # 15 minutes cooldown between repeated notifications

# Global variables for Roblox account status tracking
LAST_ACCOUNT_STATUS = None
LAST_ACCOUNT_STATUS_CHECK_TIME = None
ACCOUNT_STATUS_CHECK_COOLDOWN = 15 * 60 # 15 minutes cooldown between status change notifications

# Load configuration from the JSON file
APP_DIR = os.path.join(os.path.expanduser("~"), ".roblox_transaction")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

# Default emoji
DEFAULT_EMOJI = "bell"

ALERT_EMOJI = "warning"

DETECTION_EMOJI = "exclamation"

CLOCK_EMOJI = "hourglass"

COMPUTER_EMOJI = "desktop"

ENDPOINT_EMOJI = "link"

ACTIVE_EMOJI = "white_check_mark"

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
    # List of possible Discord webhook domains
    discord_domains = [
        'https://discord.com/api/webhooks/',
        'https://discordapp.com/api/webhooks/',
        'https://canary.discord.com/api/webhooks/',
        'https://ptb.discord.com/api/webhooks/'
    ]
    
    # Check URL starts with http or https
    if not url.startswith(('http://', 'https://')):
        return False
    
    # Check if URL contains any of the valid Discord webhook domains
    return any(domain in url for domain in discord_domains)

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

# Add a list of valid check types for validation
VALID_CHECK_TYPES = ["Day", "Week", "Month", "Year"]

# Default config loaded
config = {
    "DISCORD_WEBHOOK_URL": "",
    "ROBLOSECURITY": "",
    "DISCORD_EMOJI_ID": "",
    "DISCORD_EMOJI_NAME": "",  
    "CHECK_INTERVAL": "60",  # Default check interval of 60 seconds
    "TOTAL_CHECKS_TYPE": "Day"  # Configurable time frame for transaction checks
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
        "title": f":{DEFAULT_EMOJI}: Roblox Transaction Data Changed!",
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
        "title": f":{DEFAULT_EMOJI}: Robux Balance Changed!",
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
    if config["TOTAL_CHECKS_TYPE"] not in VALID_CHECK_TYPES:
        return False, f"Invalid TOTAL_CHECKS_TYPE. Must be one of: {', '.join(VALID_CHECK_TYPES)}"
    
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

def get_roblox_account_status():
    """
    Fetch and return the current Roblox account status.
    
    Returns:
        dict: A dictionary containing account status details
    """
    try:
        response = rate_limited_request(
            'GET', 
            f"https://users.roblox.com/v1/users/{USERID}", 
            cookies=COOKIES, 
            timeout=10
        )
        
        if response.status_code == 200:
            account_data = response.json()
            return {
                "is_banned": account_data.get("isBanned", False),
                "account_age": account_data.get("created", "Unknown"),
                "username": account_data.get("name", "Unknown")
            }
        elif response.status_code == 401:
            logger.error("Roblox security cookie has expired for account status check.")
            return {"error": "Authentication Failed"}
        else:
            logger.warning(f"Failed to fetch account status. Status code: {response.status_code}")
            return {"error": "Status Check Failed"}
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during account status check: {str(e)}")
        return {"error": "Network Error"}

def send_discord_notification_for_account_status(current_status, previous_status=None):
    """
    Send a Discord notification about Roblox account status changes.
    
    Args:
        current_status (dict): Current account status
        previous_status (dict, optional): Previous account status for comparison
    """
    global LAST_ACCOUNT_STATUS_CHECK_TIME
    
    current_time = datetime.now()
    
    # Check cooldown
    if (LAST_ACCOUNT_STATUS_CHECK_TIME is not None and 
        (current_time - LAST_ACCOUNT_STATUS_CHECK_TIME).total_seconds() < ACCOUNT_STATUS_CHECK_COOLDOWN):
        logger.info("Skipping account status notification due to cooldown")
        return
    
    if not validate_webhook_url(DISCORD_WEBHOOK_URL):
        logger.error("Invalid Discord webhook URL for account status notification")
        return

    # Construct embed for account status
    embed = {
        "title": f":{ALERT_EMOJI}: Roblox Account Status Update :{ALERT_EMOJI}:",
        "color": 0xff0000 if current_status.get("is_banned", False) else 0x00ff00,
        "fields": [
            {
                "name": "Username",
                "value": current_status.get("username", "Unknown"),
                "inline": True
            },
            {
                "name": "Account Created",
                "value": current_status.get("account_age", "Unknown"),
                "inline": True
            },
            {
                "name": "Status",
                "value": "🚫 BANNED" if current_status.get("is_banned", False) else f":{ACTIVE_EMOJI}: ACTIVE",
                "inline": False
            }
        ],
        "footer": {
            "text": "Roblox Account Status Monitor"
        }
    }

    # Add previous status comparison if available
    if previous_status and previous_status != current_status:
        embed["description"] = "Account status has changed!"

    payload = {"embeds": [embed]}

    try:
        response = rate_limited_request('POST', DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        
        # Update last notification time
        LAST_ACCOUNT_STATUS_CHECK_TIME = current_time
        
        logger.info("Account status webhook notification sent successfully")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending account status notification: {e}")

def check_roblox_account_status():
    """
    Check and potentially notify about Roblox account status.
    
    Compares current status with last known status and sends notifications if changed.
    """
    global LAST_ACCOUNT_STATUS
    
    try:
        current_status = get_roblox_account_status()
        
        # Check for errors in status retrieval
        if current_status.get("error"):
            logger.warning(f"Account status check failed: {current_status['error']}")
            return
        
        # Compare with last known status
        if LAST_ACCOUNT_STATUS is None or current_status != LAST_ACCOUNT_STATUS:
            send_discord_notification_for_account_status(current_status, LAST_ACCOUNT_STATUS)
            LAST_ACCOUNT_STATUS = current_status
    
    except Exception as e:
        logger.error(f"Unexpected error in account status check: {e}")

def send_comprehensive_api_downtime_webhook(failure_details):
    """
    Send a comprehensive webhook notification about Roblox API downtime.
    
    Args:
        failure_details (dict): Detailed information about the API failure
    """
    global LAST_DOWNTIME_NOTIFICATION_TIME
    
    current_time = datetime.now()
    
    # Check if we're within the cooldown period
    if (LAST_DOWNTIME_NOTIFICATION_TIME is not None and 
        (current_time - LAST_DOWNTIME_NOTIFICATION_TIME).total_seconds() < DOWNTIME_NOTIFICATION_COOLDOWN):
        logger.info("Skipping downtime notification due to cooldown period")
        return
    
    if not validate_webhook_url(DISCORD_WEBHOOK_URL):
        logger.error("Invalid Discord webhook URL for downtime notification")
        return

    # Construct a detailed embed with system and network information
    embed = {
        "title": f":{ALERT_EMOJI}: Roblox API Connectivity Failure :{ALERT_EMOJI}",
        "description": "Critical API Monitoring Alert: Roblox Services Unreachable",
        "color": 0xff0000,  # Red color for critical alert
        "fields": [
            {
                "name": f":{DETECTION_EMOJI}: Failure Details",
                "value": failure_details.get('error_message', 'Unknown connectivity issue'),
                "inline": False
            },
            {
                "name": f":{CLOCK_EMOJI}: Timestamp",
                "value": current_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "inline": True
            },
            {
                "name": f":{COMPUTER_EMOJI}: System Info",
                "value": f"OS: {platform.system()} {platform.release()}\n"
                         f"Python: {platform.python_version()}",
                "inline": True
            },
            {
                "name": f":{ENDPOINT_EMOJI}: Endpoints Checked",
                "value": "\n".join(failure_details.get('endpoints_checked', [])),
                "inline": False
            }
        ],
        "footer": {
            "text": "Roblox Transaction Monitor - Automatic API Health Check"
        }
    }

    payload = {"embeds": [embed]}

    try:
        response = rate_limited_request('POST', DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        
        # Update last notification time
        LAST_DOWNTIME_NOTIFICATION_TIME = current_time
        
        logger.info("Comprehensive API downtime webhook notification sent successfully")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending comprehensive downtime notification: {e}")

def check_roblox_api_status():
    """
    Check the overall Roblox API connectivity and status.
    
    Returns:
        bool: True if API is accessible, False otherwise
    """
    global CURRENT_DOWNTIME_STREAK, TOTAL_DOWNTIME_DURATION, LAST_SUCCESSFUL_CHECK, IS_IN_DOWNTIME
    
    try:
        # Check multiple critical Roblox API endpoints
        api_endpoints = [
            "https://users.roblox.com/v1/users/authenticated",
            f"{ROBLOX_ECONOMY_API}/v2/users/{USERID}/transaction-totals?timeFrame={DATE_TYPE}&transactionType=summary",
            f"{ROBLOX_ECONOMY_API}/v1/users/{USERID}/currency"
        ]
        
        failed_endpoints = []
        for endpoint in api_endpoints:
            try:
                response = rate_limited_request('GET', endpoint, cookies=COOKIES, timeout=10)
                
                if response.status_code != 200:
                    failed_endpoints.append(f"{endpoint} - Status: {response.status_code}")
                    raise requests.exceptions.RequestException(f"Non-200 status code from {endpoint}")
            except requests.exceptions.RequestException as endpoint_error:
                failed_endpoints.append(f"{endpoint} - Error: {str(endpoint_error)}")
        
        current_time = datetime.now()
        
        # Reset downtime tracking if previously in downtime
        if IS_IN_DOWNTIME:
            downtime_duration = (current_time - LAST_SUCCESSFUL_CHECK).total_seconds()
            TOTAL_DOWNTIME_DURATION += downtime_duration
            
            send_discord_notification_for_downtime(
                status="RECOVERED", 
                duration=downtime_duration
            )
        
        # Reset tracking variables
        CURRENT_DOWNTIME_STREAK = 0
        IS_IN_DOWNTIME = False
        LAST_SUCCESSFUL_CHECK = current_time
        
        return True
    
    except requests.exceptions.RequestException as e:
        logger.warning(f"Roblox API Connectivity Issue: {e}")
        
        CURRENT_DOWNTIME_STREAK += 1
        current_time = datetime.now()
        
        # Send comprehensive webhook on first detection or every X consecutive failures
        if CURRENT_DOWNTIME_STREAK == 1 or CURRENT_DOWNTIME_STREAK % DOWNTIME_THRESHOLD == 0:
            send_comprehensive_api_downtime_webhook({
                'error_message': str(e),
                'endpoints_checked': api_endpoints
            })
        
        if CURRENT_DOWNTIME_STREAK >= DOWNTIME_THRESHOLD and not IS_IN_DOWNTIME:
            IS_IN_DOWNTIME = True
            LAST_SUCCESSFUL_CHECK = current_time
            
            send_discord_notification_for_downtime(
                status="STARTED", 
                reason=str(e)
            )
        
        return False

def send_discord_notification_for_downtime(status, duration=None, reason=None):
    """
    Send a Discord notification about Roblox API downtime.
    
    Args:
        status (str): 'STARTED' or 'RECOVERED'
        duration (float, optional): Downtime duration in seconds
        reason (str, optional): Reason for downtime
    """
    if not validate_webhook_url(DISCORD_WEBHOOK_URL):
        logger.error("Invalid Discord webhook URL for downtime notification")
        return

    embed = {
        "title": f":{DEFAULT_EMOJI}: Roblox API Connectivity Alert",
        "description": f"Roblox API Downtime Status: **{status}**",
        "color": 0xff0000 if status == "STARTED" else 0x00ff00,
        "fields": []
    }

    if status == "STARTED":
        embed["fields"].append({
            "name": "Downtime Detected",
            "value": f"Reason: {reason or 'Unknown connectivity issue'}",
            "inline": False
        })
    
    if status == "RECOVERED" and duration is not None:
        embed["fields"].append({
            "name": "Downtime Duration",
            "value": f"{duration:.2f} seconds",
            "inline": False
        })

    payload = {"embeds": [embed]}

    try:
        response = rate_limited_request('POST', DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        logger.info(f"Downtime {status} notification sent successfully")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending downtime notification: {e}")

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
        
        # Validate critical global variables before starting
        if USERID is None:
            error_msg = "Failed to retrieve authenticated user ID. Check your Roblox cookie."
            logger.error(error_msg)
            messagebox.showerror("Authentication Error", error_msg)
            return
        
        if not DISCORD_WEBHOOK_URL:
            error_msg = "Discord Webhook URL is not configured. Please set it in the configuration."
            logger.error(error_msg)
            messagebox.showerror("Configuration Error", error_msg)
            return
        
        # Flag to control the loop
        monitoring_event = threading.Event()
        monitoring_event.set()
        
        # Wrap thread creation with additional error handling
        def monitor_thread_wrapper():
            try:
                main_loop()
            except Exception as e:
                logger.exception(f"Unexpected error in monitoring thread: {e}")
                window.after(0, lambda: messagebox.showerror("Monitoring Error", 
                    f"An unexpected error occurred:\n{str(e)}\n\n"
                    "Please check the logs for more details."))
                
                # Ensure UI is reset
                window.after(0, lambda: progress_label.config(text="Monitoring inactive"))
                window.after(0, lambda: progress_var.set(0))
                window.after(0, lambda: start_button.config(state='normal'))
                window.after(0, lambda: stop_button.config(state='disabled'))
        
        # Run the main loop in a separate thread
        monitoring_thread = threading.Thread(target=monitor_thread_wrapper, daemon=True)
        monitoring_thread.start()
        logger.info("Monitoring started.")
        
        # Enable/disable buttons
        start_button.config(state='disabled')
        stop_button.config(state='normal')
    except Exception as e:
        # Comprehensive error logging and user notification
        error_details = f"Failed to start monitoring: {str(e)}\n\n" \
                        f"Error Type: {type(e).__name__}\n" \
                        f"Full Traceback: {traceback.format_exc()}"
        
        logger.exception(error_details)
        
        # Reset UI state
        if monitoring_event:
            monitoring_event.clear()
        
        messagebox.showerror(
            "Critical Error", 
            f"An unexpected error occurred:\n\n{error_details}\n\n"
            "Please check the application logs and ensure all configurations are correct."
        )
        
        progress_label.config(text="Monitoring inactive")
        progress_var.set(0)
        start_button.config(state='normal')
        stop_button.config(state='disabled')

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
        # First, check overall API status
        api_status = check_roblox_api_status()
        
        if api_status:
            # Proceed with normal checks if API is accessible
            check_transactions()
            check_robux()
            check_roblox_account_status()
        else:
            logger.warning("Skipping transaction and Robux checks due to API connectivity issues")
        
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
    """Show a tutorial GUI for the specified field."""
    tutorials = {
        "Webhook": {
            "title": "Discord Webhook Tutorial",
            "links": [
                ("Discord Webhook Guide", "https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks"),
                ("Create Webhook Tutorial", "https://www.youtube.com/watch?v=zVgfmtqrBRs")
            ]
        },
        "Cookie": {
            "title": "Roblox Security Cookie Tutorial",
            "links": [
                ("Roblox Cookie Retrieval Guide", "https://github.com/cookiesolomon/roblox-cookie-tutorial"),
                ("Detailed Cookie Tutorial", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")  # Replace with actual tutorial
            ]
        },
        "Emoji": {
            "title": "Discord Emoji ID Tutorial",
            "links": [
                ("Discord Emoji Guide", "https://support.discord.com/hc/en-us/articles/360039381066-Custom-Emotes-and-Stickers"),
                ("Emoji ID Tutorial", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")  # Replace with actual tutorial
            ]
        }
    }
    
    # If no tutorial exists, show a default message
    if field_name not in tutorials:
        messagebox.showinfo("Tutorial", "No tutorial available for this field.")
        return

    # Create the main window
    tutorial_window = tk.Toplevel()
    tutorial_window.title(tutorials[field_name]["title"])
    tutorial_window.geometry("400x300")
    tutorial_window.resizable(False, False)

    # Create a frame
    frame = tk.Frame(tutorial_window, padx=20, pady=20)
    frame.pack(fill=tk.BOTH, expand=True)

    # Title Label
    title_label = tk.Label(frame, text=tutorials[field_name]["title"], font=("Helvetica", 16, "bold"))
    title_label.pack(pady=(0, 20))

    # Create clickable links
    for link_text, link_url in tutorials[field_name]["links"]:
        link_label = tk.Label(frame, text=link_text, fg="blue", cursor="hand2", font=("Helvetica", 12, "underline"))
        link_label.pack(pady=5)
        link_label.bind("<Button-1>", lambda e, url=link_url: webbrowser.open(url))

    # Close button
    close_button = tk.Button(frame, text="Close", command=tutorial_window.destroy)
    close_button.pack(pady=(20, 0))

    # Make the window modal
    tutorial_window.grab_set()
    tutorial_window.focus_set()

def randomizednumber(a=None, b=None):
    """
    Mimic Python's math.random() function with support for float ranges
    
    Python behavior:
    - No args: returns float between 0 and 1
    - One int arg n: returns int between 1 and n
    - Two args a, b: returns int between a and b (inclusive)
    """
    if a is None:
        return random.random()  # Returns float between 0 and 1
    elif b is None:
        # Single argument case: treat as max for integer
        return random.randint(1, int(a))
    else:
        # Two arguments: handle both integer and float cases
        if isinstance(a, float) or isinstance(b, float):
            # If either argument is a float, use uniform distribution
            return a + (b - a) * random.random()
        else:
            # Integer range case
            return random.randint(a, b)

async def show_splash_screen():
    """Create a splash screen with simulated loading."""
    try:
        # Create temporary root window
        root = tk.Tk()
        root.withdraw()

        # Create splash screen
        splash = tk.Toplevel(root)
        splash.title("Roblox Transaction Monitor")
        splash.overrideredirect(True)  # Remove window decorations
        
        # Calculate center position
        width = 500
        height = 310
        screen_width = splash.winfo_screenwidth()
        screen_height = splash.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        splash.geometry(f"{width}x{height}+{x}+{y}")
        
        # Configure splash screen appearance
        splash.configure(bg="#1d2636")
        splash_frame = tk.Frame(splash, bg="#1d2636", bd=2, relief="solid")  # Lighter background
        splash_frame.place(relx=0.5, rely=0.5, anchor="center", width=width, height=height)
        
        # Add application name
        title_label = tk.Label(
            splash_frame, 
            text="Roblox Transaction & Robux Monitoring", 
            font=("Arial", 18, "bold"),
            bg="#1d2636",  # Matching background
            fg="white"
        )
        title_label.pack(pady=(30, 15))
        
        # Add loading text
        status_label = tk.Label(
            splash_frame,
            text="Initializing...",
            font=("Arial", 12),
            bg="#1d2636",  # Matching background
            fg="white"
        )
        status_label.pack(pady=(0, 15))
        
        # Configure progress bar style
        style = ttk.Style()
        style.configure(
            "Splash.Horizontal.TProgressbar",
            troughcolor='#1a1a1a',
            background='#1d2636',
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
            length=400,
            mode="determinate"
        )
        progress_bar.pack(pady=15)
        
        # Update the window to ensure everything is drawn
        splash.update()
        
        try:
            # Load logo after setting up other UI elements
            logo_response = rate_limited_request('GET', icon_url)
            logo_response.raise_for_status()
            
            # Process logo image
            logo_image = Image.open(io.BytesIO(logo_response.content))
            
            # Convert image to RGBA if it's not already
            if logo_image.mode != 'RGBA':
                logo_image = logo_image.convert('RGBA')
            
            # Resize image
            logo_image = logo_image.resize((75, 75), Image.LANCZOS)
            
            # Create logo label with transparent background
            logo_photo = ImageTk.PhotoImage(logo_image)
            logo_label = tk.Label(
                splash_frame, 
                image=logo_photo, 
                bg="#1d2636"  # Matching background color
            )
            logo_label.image = logo_photo  # Keep a reference to prevent garbage collection
            logo_label.pack(pady=(10, 10), before=title_label)

            # Update the window again
            splash.update()
        except Exception as e:
            logger.warning(f"Failed to load splash screen logo: {e}")
        
        def update_progress(text, value):
            status_label.config(text=text)
            progress_var.set(value)
            splash.update()
        
        # Simulate loading steps
        loading_steps = [
            ("Starting application...", 2),
            ("Initializing core components...", 5),
            ("Loading dependencies...", 7),
            ("Checking configuration...", 10),
            ("Verifying system requirements...", 12),
            ("Ensuring compatibility...", 14),
            ("Loading resources...", 18),
            ("Optimizing performance settings...", 22),
            ("Setting up virtual environment...", 25),
            ("Preparing interface...", 28),
            ("Loading UI components...", 30),
            ("Setting up user preferences...", 33),
            ("Connecting to Roblox...", 35),
            ("Establishing secure connection...", 38),
            ("Verifying network status...", 40),
            ("Authenticating user...", 45),
            ("Validating credentials...", 50),
            ("Retrieving user data...", 55),
            ("Loading assets...", 58),
            ("Applying updates...", 59),
            ("Almost there...", 60),
            ("Caching essential data...", 62),
            ("Finalizing user session...", 65),
            ("Configuring environment...", 70),
            ("Syncing cloud data...", 75),
            ("Setting up game configurations...", 78),
            ("Checking for new content...", 80),
            ("Downloading additional assets...", 81),
            ("Compiling shaders...", 82),
            ("Initializing game engine...", 83),
            ("Loading game scripts...", 84),
            ("Verifying file integrity...", 86),
            ("Final optimizations...", 88),
            ("Preloading textures and models...", 90),
            ("Applying last-minute fixes...", 92),
            ("Finalizing rendering settings...", 94),
            ("Finalizing...", 95),
            ("Cleaning up temporary files...", 97),
            ("Preparing launch sequence...", 98),
            ("Almost done!", 99),
            ("Ready to launch!", 100)
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
                        
                        logger.info(f"Roblox API response status code: {test_response.status_code}")
                        if test_response.status_code != 200:
                            logger.warning("Roblox API connectivity test failed")
                    except Exception as e:
                        logger.error(f"Roblox API connectivity error: {e}")
                
                # Small delay to simulate work
                random_delay = randomizednumber(0.25, 0.5)
                await asyncio.sleep(random_delay)
            
            # Close splash screen
            splash.destroy()
            root.destroy()
        
        # Run initialization
        await initialize_app()
        
        return True
    except Exception as e:
        logger.warning(f"Failed to load splash screen logo: {e}")

def show_popup_for_unsupported_os(title, message):
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    messagebox.showerror(title, message)

def detect_operating_system():
    supported_operating_systems = ["Windows", "Darwin"]
    is_supported = False
    current_os = platform.system()
    
    os_msg = {
        "Windows": (
            "Windows Operating System",
            "You are currently running on Windows:\n\n"
            "1. This application was primarily designed for Linux.\n"
            "2. Windows support is limited or not available.\n"
            "3. Some features may not work as expected."
        ),
        "Linux": (
            "Linux Operating System",
            "You are currently running on Linux:\n\n"
            "1. Roblox recently added anti-hypervision protection.\n"
            "2. Linux support has been discontinued.\n"
            "3. Roblox does not support Linux due to exploitability."
        ),
        "Darwin": (
            "macOS Operating System",
            "You are currently running on MacOS:\n\n"
            "1. This application was primarily designed for Linux.\n"
            "2. macOS support is limited or not available.\n"
            "3. Some features may not work as expected."
        )
    }
    
    # Iterate through supported operating systems
    for supported_os in supported_operating_systems:
        if current_os == supported_os:
            is_supported = True
            break
    
    # If no supported OS is found, handle unsupported OS
    if not is_supported:
        try:
            # Determine which tutorial message to show based on the current OS
            title, message = os_msg.get(current_os, ("Unsupported OS", f"Your operating system ({current_os}) is not supported."))
            
            # Show error message
            show_popup_for_unsupported_os(title, message)
            
            # Log the unsupported OS
            logger.error(f"Unsupported operating system detected: {current_os}")
            
            # Attempt to exit the application
            try:
                sys.exit(1)
            except:
                os._exit(1)
        
        except Exception as e:
            logger.error(f"Error handling unsupported OS: {e}")
            
            # Fallback exit
            try:
                sys.exit(1)
            except:
                os._exit(1)
    
    return is_supported

def show_tutorial(field_name):
    """Show a tutorial popup for the specified field."""
    tutorials = {
        "Webhook": (
            "Discord Webhook Tutorial",
            "To get your Discord Webhook URL:\n\n"
            "1. Open Discord and go to your server\n"
            "2. Right-click on a channel and select 'Edit Channel'\n"
            "3. Click on 'Integrations'\n"
            "4. Click on 'Create Webhook'\n"
            "5. Click 'Copy Webhook URL'\n"
            "6. Paste the URL here"
        ),
        "Cookie": (
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
        "Emoji": (
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
    global discord_webhook_input, roblox_cookie_input, emoji_id_input, emoji_name_input, timer_input, roblox_transaction_balance_label
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
            emoji_name_input, timer_input
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
        total_checks_type = "Year"

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
        window.geometry("700x700")
        
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

        # Add total checks transaction/balance field
        roblox_transaction_balance_label = tk.Label(left_frame, text="Total Checks (Transaction/Balance) Like (Day Month Year)", bg="#1d2636", fg="white", font=("Arial", 10))
        roblox_transaction_balance_label.pack(pady=(5, 0))

        global roblox_transaction_balance_input
        roblox_transaction_balance_input = tk.Entry(left_frame, width=40)
        roblox_transaction_balance_input.insert(0, str(config["TOTAL_CHECKS_TYPE"]))
        apply_styles(roblox_transaction_balance_input)
        roblox_transaction_balance_input.pack(pady=5)
        
        # Add timer input field
        timer_label = tk.Label(left_frame, text="Check Interval (seconds)", bg="#1d2636", fg="white", font=("Arial", 10))
        timer_label.pack(pady=(5, 0))

        global timer_input
        timer_input = tk.Entry(left_frame, width=40)
        timer_input.insert(0, str(config["CHECK_INTERVAL"]))
        apply_styles(timer_input)
        timer_input.pack(pady=5)

        # Add credits button
        def show_credits_gui():
            """
            Display a credits window with information about the application and its contributors.
            """
            global credits_window
            
            # Prevent multiple credit windows
            if hasattr(globals(), 'credits_window') and credits_window is not None and credits_window.winfo_exists():
                credits_window.lift()
                return
            
            response = rate_limited_request('GET', icon_url)
            response.raise_for_status()  # Raise an error for failed requests

            # Load the icon image
            img_data = BytesIO(response.content)
            icon = Image.open(img_data)
            icon = ImageTk.PhotoImage(icon)

            credits_window = tk.Toplevel(window)
            credits_window.title("Credits")
            
            credits_window.geometry("500x600")
            credits_window.config(bg="#1d2636")
            credits_window.resizable(False, False)

            # Set the icon and window title
            credits_window.iconphoto(False, icon)

            # Create a frame for scrolling
            credits_frame = tk.Frame(credits_window, bg="#1d2636")
            credits_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # Create a canvas with scrollbar
            canvas = tk.Canvas(credits_frame, bg="#1d2636", highlightthickness=0)
            scrollbar = tk.Scrollbar(credits_frame, orient=tk.VERTICAL, command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg="#1d2636")
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Credits title
            title_label = tk.Label(
                scrollable_frame, 
                text="Credits List", 
                font=("Arial", 16, "bold"), 
                fg="white", 
                bg="#1d2636"
            )
            title_label.pack(pady=(0, 20))

            # Center the credit sections by using a frame
            credit_section_frame = tk.Frame(scrollable_frame, bg="#1d2636")
            credit_section_frame.pack(pady=10)

            # Credit sections
            credits_data = [
                ("Application Developer", "MrAndiGamesDev (MrAndi Scripted)"),
                ("Inspiration", "Komas19")
            ]
            
            for section, content in credits_data:
                section_label = tk.Label(
                    credit_section_frame, 
                    text=section, 
                    font=("Arial", 12, "bold"), 
                    fg="#4CAF50", 
                    bg="#1d2636"
                )
                section_label.pack(pady=(10, 5))
                
                content_label = tk.Label(
                    credit_section_frame, 
                    text=content, 
                    font=("Arial", 10), 
                    fg="white", 
                    bg="#1d2636"
                )
                content_label.pack()

            # Close button
            close_button = tk.Button(
                scrollable_frame, 
                text="Close", 
                command=credits_window.destroy, 
                bg="#2196F3", 
                fg="white", 
                font=("Arial", 10, "bold")
            )
            close_button.pack(pady=20)

        credits_button = tk.Button(left_frame, text="Credits", command=show_credits_gui)
        apply_button_styles(credits_button)
        credits_button.pack(pady=10)

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

        # Add clear button
        clear_button = tk.Button(log_header, text="Clear Logs", command=clear_logs)
        apply_button_styles(clear_button)
        clear_button.pack(side=tk.RIGHT, padx=5, pady=5)

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

        # Create and configure GUI log handler
        gui_handler = GUILogHandler(log_output)
        logger.add(gui_handler, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

        # Configure buttons and initial state
        save_button.config(state='normal')
        start_button.config(state='normal')
        stop_button.config(state='disabled')

        def on_close():
            """Handle window closure."""
            global monitoring_event
            # Ensure monitoring_event exists and is not set
            if monitoring_event is not None and not monitoring_event.is_set():
                monitoring_event.set()  # Stop monitoring
            window.destroy()

        # Start the main event loop
        window.protocol("WM_DELETE_WINDOW", on_close)
        window.mainloop()

        return True
    except Exception as e:
        logger.error(f"Error initializing GUI: {e}")
        messagebox.showerror("Initialization Error", str(e))

def check_operating_system():
    # First, check the operating system
    os_check_result = detect_operating_system()
    # Only proceed with GUI initialization if OS is supported
    if os_check_result:
        # Run the GUI initialization
        asyncio.run(Initialize_gui())
    else:
        logger.error("Unsupported operating system. Application cannot start.")

if __name__ == "__main__":
    check_operating_system()
