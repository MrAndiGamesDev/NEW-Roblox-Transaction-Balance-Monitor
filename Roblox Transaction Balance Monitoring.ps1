Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Windows.Forms

# Configuration Path
$ConfigPath = "$env:USERPROFILE\.roblox_transaction\config.json"
$LogPath = "$env:USERPROFILE\.roblox_transaction\logs"

# Ensure directories exist
if (!(Test-Path -Path "$env:USERPROFILE\.roblox_transaction")) {
    New-Item -ItemType Directory -Path "$env:USERPROFILE\.roblox_transaction"
}
if (!(Test-Path -Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath
}

# Default Configuration
$global:Config = @{
    DiscordWebhookUrl = ""
    RobloxCookie = ""
    EmojiId = ""
    EmojiName = "Robux"
    CheckInterval = 60
    TotalChecksType = "Day"
}

# XAML for the main window
$xamlContent = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Roblox Transaction Monitor" Height="600" Width="800"
        Background="#FF2D2D30">
    <Grid Margin="20">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>

        <StackPanel Grid.Row="0" Margin="0,0,0,20">
            <TextBlock Text="Roblox Transaction Monitor" 
                       Foreground="White" 
                       FontSize="24" 
                       HorizontalAlignment="Center" 
                       Margin="0,0,0,10"/>
        </StackPanel>

        <Grid Grid.Row="1">
            <Grid.ColumnDefinitions>
                <ColumnDefinition Width="*"/>
                <ColumnDefinition Width="*"/>
            </Grid.ColumnDefinitions>

            <StackPanel Grid.Column="0" Margin="10">
                <TextBlock Text="Configuration" Foreground="White" FontSize="18" Margin="0,0,0,10"/>
                
                <TextBlock Text="Discord Webhook URL" Foreground="White" Margin="0,5"/>
                <TextBox x:Name="txtWebhookUrl" Background="#FF3F3F46" Foreground="White" Margin="0,5" Height="30"/>
                
                <TextBlock Text="Roblox Security Cookie" Foreground="White" Margin="0,5"/>
                <TextBox x:Name="txtRobloxCookie" Background="#FF3F3F46" Foreground="White" Margin="0,5" Height="30"/>
                
                <TextBlock Text="Check Interval (seconds)" Foreground="White" Margin="0,5"/>
                <TextBox x:Name="txtCheckInterval" Background="#FF3F3F46" Foreground="White" Margin="0,5" Height="30" Text="60"/>
                
                <Button x:Name="btnSaveConfig" Content="Save Configuration" 
                        Background="#FF4CAF50" 
                        Foreground="White" 
                        Margin="0,20,0,0" 
                        Height="40"/>
            </StackPanel>

            <StackPanel Grid.Column="1" Margin="10">
                <TextBlock Text="Monitoring Status" Foreground="White" FontSize="18" Margin="0,0,0,10"/>
                
                <TextBlock Text="Current Balance:" Foreground="White"/>
                <TextBlock x:Name="lblCurrentBalance" Text="N/A" Foreground="#FF4CAF50" FontSize="24" Margin="0,5"/>
                
                <TextBlock Text="Last Checked:" Foreground="White" Margin="0,10,0,5"/>
                <TextBlock x:Name="lblLastChecked" Text="Never" Foreground="White"/>
                
                <StackPanel Orientation="Horizontal" Margin="0,20,0,0">
                    <Button x:Name="btnStartMonitoring" Content="Start Monitoring" 
                            Background="#FF4CAF50" 
                            Foreground="White" 
                            Width="150" 
                            Height="40" 
                            Margin="0,0,10,0"/>
                    <Button x:Name="btnStopMonitoring" Content="Stop Monitoring" 
                            Background="#FFFF0000" 
                            Foreground="White" 
                            Width="150" 
                            Height="40"/>
                </StackPanel>
            </StackPanel>
        </Grid>

        <TextBox Grid.Row="2" 
                 x:Name="txtLog" 
                 Background="#FF1E1E1E" 
                 Foreground="White" 
                 Height="100" 
                 IsReadOnly="True" 
                 TextWrapping="Wrap" 
                 VerticalScrollBarVisibility="Auto"/>
    </Grid>
</Window>
"@

# Load XAML
$reader = (New-Object System.Xml.XmlNodeReader([xml]$xamlContent))
$window = [Windows.Markup.XamlReader]::Load($reader)

# Find controls
$txtWebhookUrl = $window.FindName("txtWebhookUrl")
$txtRobloxCookie = $window.FindName("txtRobloxCookie")
$txtCheckInterval = $window.FindName("txtCheckInterval")
$btnSaveConfig = $window.FindName("btnSaveConfig")
$lblCurrentBalance = $window.FindName("lblCurrentBalance")
$lblLastChecked = $window.FindName("lblLastChecked")
$btnStartMonitoring = $window.FindName("btnStartMonitoring")
$btnStopMonitoring = $window.FindName("btnStopMonitoring")
$txtLog = $window.FindName("txtLog")

# Logging function
function Write-Log {
    param([string]$Message)
    $window.Dispatcher.Invoke([Action]{
        $txtLog.AppendText("$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $Message`n")
        $txtLog.ScrollToEnd()
    })
}

# Import Configuration
function Import-Configuration {
    try {
        if (Test-Path -Path $ConfigPath) {
            $loadedConfig = Get-Content -Raw -Path $ConfigPath | ConvertFrom-Json
            $global:Config = $loadedConfig

            # Update UI with loaded config
            $window.Dispatcher.Invoke([Action]{
                $txtWebhookUrl.Text = $global:Config.DiscordWebhookUrl
                $txtRobloxCookie.Text = $global:Config.RobloxCookie
                $txtCheckInterval.Text = $global:Config.CheckInterval
            })

            Write-Log "Configuration loaded successfully"
        }
        else {
            Write-Log "No existing configuration found"
        }
    }
    catch {
        Write-Log "Error loading configuration: $_"
    }
}

# Save Configuration
$btnSaveConfig.Add_Click({
    try {
        $global:Config.DiscordWebhookUrl = $txtWebhookUrl.Text
        $global:Config.RobloxCookie = $txtRobloxCookie.Text
        $global:Config.CheckInterval = [int]$txtCheckInterval.Text

        $global:Config | ConvertTo-Json | Set-Content -Path $ConfigPath
        Write-Log "Configuration saved successfully"
    }
    catch {
        Write-Log "Error saving configuration: $_"
    }
})

# Monitoring Variables
$global:MonitoringRunspace = $null
$global:MonitoringPowerShell = $null

# Discord Notification Function
function Send-DiscordNotification {
    param(
        [string]$WebhookUrl,
        [string]$Message,
        [int]$Balance,
        [int]$PreviousBalance
    )

    $payload = @{
        content = $Message
        embeds = @(
            @{
                title = "Robux Balance Update"
                description = "Your Robux balance has changed"
                color = if ($Balance -gt $PreviousBalance) { 3066993 } else { 15158332 }
                fields = @(
                    @{
                        name = "Previous Balance"
                        value = $PreviousBalance
                        inline = $true
                    },
                    @{
                        name = "Current Balance"
                        value = $Balance
                        inline = $true
                    }
                )
            }
        )
    }

    try {
        Invoke-RestMethod -Uri $WebhookUrl -Method Post -Body ($payload | ConvertTo-Json -Depth 10) -ContentType "application/json"
    }
    catch {
        Write-Log "Failed to send Discord notification: $_"
    }
}

# Start Monitoring
$btnStartMonitoring.Add_Click({
    # Stop any existing monitoring
    if ($global:MonitoringRunspace) {
        $global:MonitoringPowerShell.Stop()
        $global:MonitoringRunspace.Close()
    }

    # Reset UI
    $lblCurrentBalance.Text = "Checking..."
    $lblLastChecked.Text = "Initializing..."

    # Create a new runspace for monitoring
    $global:MonitoringRunspace = [runspacefactory]::CreateRunspace()
    $global:MonitoringRunspace.Open()
    $global:MonitoringRunspace.SessionStateProxy.SetVariable("Config", $global:Config)
    $global:MonitoringRunspace.SessionStateProxy.SetVariable("window", $window)
    $global:MonitoringRunspace.SessionStateProxy.SetVariable("lblCurrentBalance", $lblCurrentBalance)
    $global:MonitoringRunspace.SessionStateProxy.SetVariable("lblLastChecked", $lblLastChecked)

    $global:MonitoringPowerShell = [powershell]::Create().AddScript({
        # Roblox API functions
        function Get-RobloxUserId {
            param([string]$Cookie)
            $headers = @{ Cookie = ".ROBLOSECURITY=$Cookie" }
            try {
                $response = Invoke-RestMethod -Uri "https://users.roblox.com/v1/users/authenticated" -Headers $headers
                return $response.id
            }
            catch {
                throw "Failed to get Roblox User ID: $_"
            }
        }

        function Get-RobloxBalance {
            param([string]$Cookie, [int]$UserId)
            $headers = @{ Cookie = ".ROBLOSECURITY=$Cookie" }

            try {
                $balanceResponse = Invoke-RestMethod -Uri "https://economy.roblox.com/v1/users/$UserId/currency" -Headers $headers
                return $balanceResponse.robux
            }
            catch {
                throw "Failed to get Robux balance: $_"
            }
        }

        # Main monitoring logic
        try {
            $userId = Get-RobloxUserId -Cookie $Config.RobloxCookie
            $previousBalance = 0

            while ($true) {
                try {
                    $currentBalance = Get-RobloxBalance -Cookie $Config.RobloxCookie -UserId $userId

                    # Update UI
                    $window.Dispatcher.Invoke([Action]{
                        $lblCurrentBalance.Text = "$currentBalance Robux"
                        $lblLastChecked.Text = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
                    })

                    # Send Discord notification if balance changed
                    if ($currentBalance -ne $previousBalance) {
                        if ($Config.DiscordWebhookUrl) {
                            Send-DiscordNotification -WebhookUrl $Config.DiscordWebhookUrl -Balance $currentBalance -PreviousBalance $previousBalance
                        }
                        $previousBalance = $currentBalance
                    }

                    # Wait before next check
                    Start-Sleep -Seconds $Config.CheckInterval
                }
                catch {
                    $window.Dispatcher.Invoke([Action]{
                        $lblCurrentBalance.Text = "Error"
                        $lblLastChecked.Text = "Check failed"
                    })
                    Write-Log "Monitoring error: $_"
                    Start-Sleep -Seconds 30
                }
            }
        }
        catch {
            Write-Log "Initialization error: $_"
        }
    })

    $global:MonitoringPowerShell.Runspace = $global:MonitoringRunspace
    $global:MonitoringPowerShell.BeginInvoke()

    Write-Log "Monitoring started"
})

# Stop Monitoring
$btnStopMonitoring.Add_Click({
    if ($global:MonitoringRunspace) {
        $global:MonitoringPowerShell.Stop()
        $global:MonitoringRunspace.Close()
        $global:MonitoringRunspace = $null

        # Reset UI
        $lblCurrentBalance.Text = "N/A"
        $lblLastChecked.Text = "Never"

        Write-Log "Monitoring stopped"
    }
})

# Import initial configuration
Import-Configuration
# Show the window
$window.ShowDialog() | Out-Null
