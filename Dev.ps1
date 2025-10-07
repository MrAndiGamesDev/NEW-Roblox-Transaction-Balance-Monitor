<#
 CREDITS
  - ChrisTitusTech (For the code base)
  - Modified by MrAndiGamesDev
#>

# Function to fetch the latest release tag from the GitHub API

$RepoOwner = "MrAndiGamesDev"
$RepoName = "NEW-Roblox-Transaction-Balance-Monitor"
$ExecutableScriptName = "main.py"

function Get-LatestRelease {
    try {
        $releases = Invoke-RestMethod -Uri "https://api.github.com/repos/$RepoOwner/$RepoName/releases"
        $latestRelease = $releases | Where-Object {$_.prerelease -eq $true} | Select-Object -First 1
        return $latestRelease.tag_name
    } catch {
        Write-Host "Error fetching release data: $_" -ForegroundColor Red
        return $latestRelease.tag_name
    }
}

# Function to redirect to the latest pre-release version
function RedirectToLatestPreRelease {
    $latestRelease = Get-LatestRelease
    
    if ($latestRelease) {
        $url = "https://github.com/$RepoOwner/$RepoName/releases/download/$latestRelease/$ExecutableScriptName"
    } else {
        Write-Host 'No pre-release version found. This is most likely because the latest release is a full release and no newer pre-release exists.'
        Write-Host "Using latest Full Release"
        $url = "https://github.com/$RepoOwner/$RepoName/releases/latest/download/$ExecutableScriptName"
    }

    # Download the latest Python script
    $scriptPath = "$env:TEMP\$ExecutableScriptName"
    Invoke-WebRequest -Uri $url -OutFile $scriptPath

    $IsNotAnAdmin = (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))

    # Elevate Shell if necessary
    if ($IsNotAnAdmin) {
        Write-Output "$RepoName needs to be run as Administrator. Attempting to relaunch."
        $powershellcmd = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }
        $processCmd = if (Get-Command wt.exe -ErrorAction SilentlyContinue) { "wt.exe" } else { $powershellcmd }
        Start-Process $processCmd -ArgumentList "$powershellcmd -ExecutionPolicy Bypass -NoProfile -Command & `"$scriptPath`"" -Verb RunAs
    }
    else {
        # Launch the downloaded Python script
        Start-Process "python" -ArgumentList "$scriptPath"
    }
}

# Call the redirect function
RedirectToLatestPreRelease