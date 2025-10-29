@echo off
setlocal
set "url=https://raw.githubusercontent.com/MrAndiGamesDev/NEW-Roblox-Transaction-Balance-Monitor/main/requirements.txt"
set "out=requirements.txt"
powershell -NoProfile -Command "Invoke-WebRequest -Uri '%url%' -OutFile '%out%'"
echo Download complete: %out%
pip install -r %out%
pause
endlocal