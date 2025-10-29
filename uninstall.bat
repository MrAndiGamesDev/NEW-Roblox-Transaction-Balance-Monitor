@ECHO OFF
set "URL=https://raw.githubusercontent.com/MrAndiGamesDev/NEW-Roblox-Transaction-Balance-Monitor/main/requirements.txt"
set "OUT=requirements.txt"
if exist "%OUT%" (
    echo Found existing %OUT%, skipping download.
) else (
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%URL%' -OutFile '%OUT%'"
    echo Download complete: %OUT%
)
pip uninstall -r %OUT% -y
pause