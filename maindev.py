import requests
import time
import json
import os
import threading
import sys
import platform
import io
import webbrowser
import ctypes
import traceback
from io import BytesIO
from PIL import Image, ImageQt
from loguru import logger
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QProgressBar, QMessageBox,
    QFrame, QScrollArea, QDialog, QDialogButtonBox, QStyle
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QPixmap, QIcon, QFont, QPalette, QColor, QTextCursor, QDesktopServices
from ctypes import wintypes

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
EMOJI_NAME = config["DISCORD_EMOJI_NAME"]
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
        try:
            data = response.json()
            user_id = data.get("id")
            if user_id is not None:
                logger.info(f"Successfully fetched authenticated user ID: {user_id}")
                return user_id
            else:
                logger.error("User ID not found in response JSON")
                return None
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None
    else:
        logger.error(f"Failed to fetch authenticated user ID. Status: {response.status_code}, Response: {response.text}")
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
        try:
            with open(ROBUX_FILE, "r") as file:
                return json.load(file).get("robux", 0)
        except Exception as e:
            pass
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
    progress_label.setText("Authentication Error - Update Cookie")
    progress_var.setValue(0)
    start_button.setEnabled(False)
    stop_button.setEnabled(False)
    
    # Highlight the cookie input field
    roblox_cookie_input.setStyleSheet("background-color: #4a1919; color: white;")
    roblox_cookie_label.setStyleSheet("color: #ff6b6b;")
    
    # Enable save button
    save_button.setEnabled(True)
    
    QMessageBox.critical(
        window, 
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
        "title": f":{ALERT_EMOJI}: Roblox API Connectivity Failure :{ALERT_EMOJI}:",
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
            QMessageBox.critical(window, "Configuration Error", message)
            return
        
        # Validate critical global variables before starting
        if USERID is None:
            error_msg = "Failed to retrieve authenticated user ID. Check your Roblox cookie."
            logger.error(error_msg)
            QMessageBox.critical(window, "Authentication Error", error_msg)
            return
        
        if not DISCORD_WEBHOOK_URL:
            error_msg = "Discord Webhook URL is not configured. Please set it in the configuration."
            logger.error(error_msg)
            QMessageBox.critical(window, "Configuration Error", error_msg)
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
                window.show_error_signal.emit(
                    "Monitoring Error", 
                    f"An unexpected error occurred:\n{str(e)}\n\n"
                    "Please check the logs for more details."
                )
                
                # Ensure UI is reset
                window.update_progress_signal.emit(0)
                window.update_status_signal.emit("Monitoring inactive")
                window.update_buttons_signal.emit(False, True)
        
        # Run the main loop in a separate thread
        monitoring_thread = threading.Thread(target=monitor_thread_wrapper, daemon=True)
        monitoring_thread.start()
        logger.info("Monitoring started.")
        
        # Enable/disable buttons
        start_button.setEnabled(False)
        stop_button.setEnabled(True)
    except Exception as e:
        # Comprehensive error logging and user notification
        error_details = f"Failed to start monitoring: {str(e)}\n\n" \
                        f"Error Type: {type(e).__name__}\n" \
                        f"Full Traceback: {traceback.format_exc()}"
        
        logger.exception(error_details)
        
        # Reset UI state
        if monitoring_event:
            monitoring_event.clear()
        
        QMessageBox.critical(
            window, 
            "Critical Error", 
            f"An unexpected error occurred:\n\n{error_details}\n\n"
            "Please check the application logs and ensure all configurations are correct."
        )
        
        progress_label.setText("Monitoring inactive")
        progress_var.setValue(0)
        start_button.setEnabled(True)
        stop_button.setEnabled(False)

def stop_monitoring():
    """Stop monitoring transactions and Robux."""
    global monitoring_event, progress_label, progress_var, start_button, stop_button
    
    try:
        monitoring_event.clear()
        progress_var.setValue(0)
        progress_label.setText("Monitoring inactive")
        logger.info("Monitoring stopped.")
        
        # Enable/disable buttons
        start_button.setEnabled(True)
        stop_button.setEnabled(False)
    except Exception as e:
        error_msg = f"Error stopping monitoring: {str(e)}"
        logger.error(error_msg)
        QMessageBox.critical(window, "Error", error_msg)

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
            check_interval = int(timer_input.text())
            if check_interval < 10:  # Minimum 10 seconds
                check_interval = 10
                timer_input.setText("10")
        except ValueError:
            check_interval = 60  # Default check interval
            timer_input.setText("60")
        
        # Update progress bar using QTimer on the main GUI thread
        def schedule_progress_update(current_second):
            if not monitoring_event.is_set():
                return
            
            progress = (current_second + 1) / check_interval * 100
            time_left = check_interval - current_second - 1
            
            window.update_progress_signal.emit(progress)
            window.update_status_signal.emit(f"Next check in {time_left} seconds")
            
            if current_second + 1 < check_interval and monitoring_event.is_set():
                QTimer.singleShot(1000, lambda: schedule_progress_update(current_second + 1))
            elif monitoring_event.is_set():
                main_loop()
        
        QTimer.singleShot(0, lambda: schedule_progress_update(0))
        
    except Exception as e:
        logger.error(f"Error in monitoring loop: {str(e)}")
        if monitoring_event.is_set():
            QTimer.singleShot(5000, main_loop)  # Retry after 5 seconds

class MainWindow(QMainWindow):
    show_error_signal = Signal(str, str)
    update_progress_signal = Signal(int)          # changed to int (0-100)
    update_status_signal = Signal(str)
    update_buttons_signal = Signal(bool, bool)

    def __init__(self):
        super().__init__()
        self._progress_max = 0
        self._progress_value = 0
        self.init_ui()
        self.connect_signals()
        self.apply_dark_title_bar()

    def connect_signals(self):
        self.show_error_signal.connect(self.show_error_dialog)
        self.update_progress_signal.connect(self.update_progress)
        self.update_status_signal.connect(self.update_status)
        self.update_buttons_signal.connect(self.update_buttons)

    def apply_dark_title_bar(self):
        """Apply dark mode to the native Windows title bar using ctypes."""
        if platform.system() == "Windows":
            try:
                # Windows 10/11 dark title bar constants
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                hwnd = self.winId().__int__()
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value)
                )
            except Exception as e:
                logger.warning(f"Failed to apply dark title bar: {e}")

    def get_app_icon(self) -> QIcon:
        try:
            response = rate_limited_request('GET', icon_url)
            response.raise_for_status()
            img_data = BytesIO(response.content)
            icon = Image.open(img_data)
            qt_icon = QIcon(QPixmap.fromImage(ImageQt.ImageQt(icon)))
            self.setWindowIcon(qt_icon)
        except Exception as e:
            logger.warning(f"Failed to load application icon: {e}")

    def init_ui(self):
        self.setWindowTitle("Roblox Transaction & Robux Monitor")
        self.setFixedSize(900, 800)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
            }
            QLineEdit {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 1px solid #60a5fa;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 10pt;
                font-weight: 600;
            }
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #60a5fa;
            }
            QPushButton:pressed {
                background-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)

        # Load icon
        self.get_app_icon()

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(24)

        # Left frame
        left_frame = QVBoxLayout()
        left_frame.setSpacing(16)
        main_layout.addLayout(left_frame, 1)

        # Header
        header_label = QLabel("⚙️ Configuration")
        header_label.setStyleSheet("color: #60a5fa; font-size: 14pt; font-weight: bold;")
        left_frame.addWidget(header_label)

        # Discord Webhook URL
        discord_webhook_label = QLabel("Discord Webhook URL")
        left_frame.addWidget(discord_webhook_label)

        global discord_webhook_input
        discord_webhook_input = QLineEdit()
        discord_webhook_input.setText(config["DISCORD_WEBHOOK_URL"])
        discord_webhook_input.setEchoMode(QLineEdit.Password)
        left_frame.addWidget(discord_webhook_input)

        # Roblox Security Cookie
        roblox_cookie_label = QLabel(".ROBLOSECURITY")
        left_frame.addWidget(roblox_cookie_label)

        global roblox_cookie_input
        roblox_cookie_input = QLineEdit()
        roblox_cookie_input.setText(config["ROBLOSECURITY"])
        roblox_cookie_input.setEchoMode(QLineEdit.Password)
        left_frame.addWidget(roblox_cookie_input)

        # Emoji settings (horizontal layout)
        emoji_layout = QHBoxLayout()
        emoji_layout.setSpacing(12)

        emoji_id_layout = QVBoxLayout()
        emoji_id_label = QLabel("Emoji ID")
        emoji_id_layout.addWidget(emoji_id_label)
        global emoji_id_input
        emoji_id_input = QLineEdit()
        emoji_id_input.setText(config["DISCORD_EMOJI_ID"])
        emoji_id_layout.addWidget(emoji_id_input)
        emoji_layout.addLayout(emoji_id_layout)

        emoji_name_layout = QVBoxLayout()
        emoji_name_label = QLabel("Emoji Name")
        emoji_name_layout.addWidget(emoji_name_label)
        global emoji_name_input
        emoji_name_input = QLineEdit()
        emoji_name_input.setText(config.get("DISCORD_EMOJI_NAME", ""))
        emoji_name_layout.addWidget(emoji_name_input)
        emoji_layout.addLayout(emoji_name_layout)

        left_frame.addLayout(emoji_layout)

        # Check Interval
        timer_label = QLabel("Check Interval (seconds)")
        left_frame.addWidget(timer_label)

        global timer_input
        timer_input = QLineEdit()
        timer_input.setText(config["CHECK_INTERVAL"])
        left_frame.addWidget(timer_input)

        # Total Checks Type
        roblox_transaction_balance_label = QLabel("Total Checks Type (Day/Week/Month/Year)")
        left_frame.addWidget(roblox_transaction_balance_label)

        global roblox_transaction_balance_input
        roblox_transaction_balance_input = QLineEdit()
        roblox_transaction_balance_input.setText(config["TOTAL_CHECKS_TYPE"])
        left_frame.addWidget(roblox_transaction_balance_input)

        # Buttons
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(12)

        global save_button
        save_button = QPushButton("💾 Save Configuration")
        save_button.clicked.connect(save_config)
        buttons_layout.addWidget(save_button)

        global start_button
        start_button = QPushButton("▶️ Start Monitoring")
        start_button.clicked.connect(start_monitoring)
        buttons_layout.addWidget(start_button)

        global stop_button
        stop_button = QPushButton("⏹️ Stop Monitoring")
        stop_button.clicked.connect(stop_monitoring)
        stop_button.setEnabled(False)
        buttons_layout.addWidget(stop_button)

        global credits_button
        credits_button = QPushButton("ℹ️ Credits")
        credits_button.clicked.connect(self.show_credits)
        buttons_layout.addWidget(credits_button)

        left_frame.addLayout(buttons_layout)

        # Right frame
        right_frame = QVBoxLayout()
        right_frame.setSpacing(16)
        main_layout.addLayout(right_frame, 2)

        # Log header
        log_header = QHBoxLayout()
        log_header.setSpacing(12)

        log_label = QLabel("📋 Log Output")
        log_label.setStyleSheet("color: #60a5fa; font-size: 14pt; font-weight: bold;")
        log_header.addWidget(log_label)

        log_header.addStretch()

        clear_button = QPushButton("🗑️ Clear")
        clear_button.setMaximumWidth(80)
        clear_button.clicked.connect(self.clear_logs)
        log_header.addWidget(clear_button)

        right_frame.addLayout(log_header)

        # Log output
        global log_output
        log_output = QTextEdit()
        log_output.setReadOnly(True)
        log_output.setStyleSheet("""
            QTextEdit {
                background-color: #0b1220;
                color: #e2e8f0;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        right_frame.addWidget(log_output)

        # Status section
        status_layout = QVBoxLayout()
        status_layout.setSpacing(8)

        status_header = QLabel("📊 Status")
        status_header.setStyleSheet("color: #60a5fa; font-size: 14pt; font-weight: bold;")
        status_layout.addWidget(status_header)

        global progress_label
        progress_label = QLabel("Monitoring inactive")
        progress_label.setStyleSheet("color: #cbd5e1; font-size: 11pt;")
        status_layout.addWidget(progress_label)

        global progress_var
        progress_var = QProgressBar()
        progress_var.setRange(0, 100)
        progress_var.setTextVisible(True)
        progress_var.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                text-align: center;
                color: #e2e8f0;
                font-size: 10pt;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 6px;
            }
        """)
        status_layout.addWidget(progress_var)

        right_frame.addLayout(status_layout)

        # Logger handler
        self.gui_handler = GUILogHandler(log_output)
        logger.add(self.gui_handler, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

    def show_credits(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Credits")
        dialog.setFixedSize(500, 400)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
            }
            QLabel {
                color: #e2e8f0;
            }
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #60a5fa;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title_label = QLabel("Credits")
        title_label.setStyleSheet("color: #60a5fa; font-size: 18pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #334155;
                border-radius: 8px;
                background-color: #0f172a;
            }
            QScrollBar:vertical {
                background-color: #0f172a;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #3b82f6;
                border-radius: 6px;
                min-height: 20px;
            }
        """)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(16, 16, 16, 16)
        scroll_layout.setSpacing(12)

        credits_data = [
            ("Application Developer", "MrAndiGamesDev (MrAndi Scripted)"),
            ("Inspiration", "Komas19")
        ]

        for section, content in credits_data:
            section_label = QLabel(section)
            section_label.setStyleSheet("color: #60a5fa; font-size: 12pt; font-weight: bold;")
            scroll_layout.addWidget(section_label)

            content_label = QLabel(content)
            content_label.setStyleSheet("color: #e2e8f0; font-size: 11pt;")
            content_label.setWordWrap(True)
            scroll_layout.addWidget(content_label)

            spacer = QWidget()
            spacer.setFixedHeight(8)
            scroll_layout.addWidget(spacer)

        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.exec()

    def clear_logs(self):
        log_output.clear()
        logger.info("Log output cleared")

    def show_error_dialog(self, title, message):
        QMessageBox.critical(self, title, message)

    def update_progress(self, value):
        # value is now 0-100
        progress_var.setValue(value)
        progress_var.setFormat(f"{value}%")

    def update_status(self, text):
        progress_label.setText(text)

    def update_buttons(self, start_enabled, stop_enabled):
        start_button.setEnabled(start_enabled)
        stop_button.setEnabled(stop_enabled)

    def closeEvent(self, event):
        global monitoring_event
        if monitoring_event is not None and not monitoring_event.is_set():
            monitoring_event.set()  # Stop monitoring
        event.accept()

class GUILogHandler:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        cursor = QTextCursor(self.text_widget.document())
        cursor.movePosition(QTextCursor.End)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Color coding for different message types
        if "ERROR" in message:
            self.text_widget.setTextColor(QColor("red"))
        elif "INFO" in message:
            self.text_widget.setTextColor(QColor("#00ff00"))
        else:
            self.text_widget.setTextColor(QColor("white"))
        
        cursor.insertText(f"{timestamp} | {message}\n")
        self.text_widget.setTextCursor(cursor)
        self.text_widget.ensureCursorVisible()

    def flush(self):
        pass

def save_config():
    """Save the configuration with validation and tutorials."""
    global discord_webhook_input, roblox_cookie_input, emoji_id_input, emoji_name_input, timer_input
    global start_button, progress_label, roblox_cookie_label, save_button, window

    try:
        # Get input values safely
        webhook_url = discord_webhook_input.text().strip()
        roblosecurity = roblox_cookie_input.text().strip()
        emoji_id = emoji_id_input.text().strip()
        emoji_name = emoji_name_input.text().strip()  
        interval = timer_input.text().strip()
        
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
            QMessageBox.critical(window, "Configuration Validation Failed", error_message)
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
            roblox_cookie_input.setStyleSheet("background-color: #2e3b4e; color: white; border: none; padding: 5px;")
            roblox_cookie_label.setStyleSheet("color: white; font-size: 10pt;")
        
        # Re-enable start button and update progress label if config is valid
        is_valid, validation_message = validate_config()
        if is_valid:
            if start_button:
                start_button.setEnabled(True)
            if save_button:
                save_button.setEnabled(True)
            if progress_label:
                progress_label.setText("Monitoring inactive")
            logger.info("Configuration saved and validated successfully")
            QMessageBox.information(window, "Success", "Configuration Saved Successfully!")
        else:
            logger.warning(f"Configuration saved but validation failed: {validation_message}")
            QMessageBox.warning(window, "Partial Success", f"Configuration saved, but: {validation_message}")

    except Exception as e:
        error_msg = f"Unexpected error saving configuration: {str(e)}"
        logger.error(error_msg)
        QMessageBox.critical(window, "Unexpected Error", error_msg)

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
            "1. This application was primarily designed for Windows.\n"
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
            QMessageBox.critical(None, title, message)
            
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

def check_os_support_and_run():
    # First, check the operating system
    os_check_result = detect_operating_system()
    # Only proceed with GUI initialization if OS is supported
    if os_check_result:
        # Run the GUI initialization
        app = QApplication(sys.argv)
        global window
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    else:
        logger.error("Unsupported operating system. Application cannot start.")

if __name__ == "__main__":
    check_os_support_and_run()