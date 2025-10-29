@ECHO OFF
setlocal

set "URL=https://raw.githubusercontent.com/MrAndiGamesDev/NEW-Roblox-Transaction-Balance-Monitor/main/requirements.txt"
set "OUT=requirements.txt"

powershell -NoProfile -Command "Invoke-WebRequest -Uri '%URL%' -OutFile '%OUT%'"
echo Download complete: %OUT%

pip install -r "%OUT%"

pause
endlocal