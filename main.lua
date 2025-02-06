local obs = obslua

-- Settings
local user_id = "3362493084"  -- Replace with your target User ID
local roblox_cookie = ""  -- Replace with your actual Roblox cookie

local robux_balance = "Fetching..."  -- Default Robux balance text
local TextSource = "RobuxText"

local is_fetching = false  -- Flag to control fetch state

local random_interval = {150, 300}  -- Fetch interval in seconds (randomized within range)
local update_interval = random_interval[math.random(1, #random_interval)]

-- Function to log messages
local function log_message(level, message)
    if level == "Info" then
        print(message)
    elseif level == "Error" then
        error(message)
    end
end

-- Function to abbreviate numbers (with added support for Robux)
local function abbreviate_number(num: number)
    -- Ensure that num is a valid number
    if type(num) ~= "number" then
        return "Invalid number"
    end

    -- Updated suffixes and thresholds, including 'OB' for Roblox API
    local suffixes = {"", "K", "M", "B", "T", "Q", "OB"}
    local thresholds = {1000, 1000000, 1000000000, 1000000000000, 1000000000000000, 1000000000000000000}

    local abs_num = math.abs(num)
    
    -- Check for each threshold to apply the correct suffix
    for i = #thresholds, 1, -1 do
        if abs_num >= thresholds[i] then
            return string.format("%.2f%s", num / thresholds[i], suffixes[i + 1])
        end
    end
    
    return tostring(num)
end

-- Function to fetch authenticated user
local function fetch_authenticated_user()
    local users_roblox_url = "https://users.roblox.com"
    local url = users_roblox_url .. "/v1/users/authenticated"

    local temp_file = os.tmpname()
    local command = string.format('curl -s -H "Cookie: .ROBLOSECURITY=%s" "%s" > "%s"', roblox_cookie, url, temp_file)
    
    os.execute(command)
    
    local file = io.open(temp_file, "r")
    local result = file and file:read("*a") or ""

    if file then file:close() end
    os.remove(temp_file)
    
    log_message("Info", "Authenticated User Response: " .. result)
    return result
end

-- Function to fetch the Robux balance
local function fetch_robux_balance()
    local roblox_economy_url = "https://economy.roblox.com"
    local url = string.format(roblox_economy_url .. "/v1/users/%s/currency", user_id)

    local temp_file = os.tmpname()
    local command = string.format('curl -s -H "Cookie: .ROBLOSECURITY=%s" "%s" > "%s"', roblox_cookie, url, temp_file)
    
    os.execute(command)
    
    local file = io.open(temp_file, "r")
    local result = file and file:read("*a") or ""

    if file then file:close() end
    os.remove(temp_file)
    
    log_message("Info", "Response: " .. result)
    
    local balance = result:match('"robux":(%d+)')
    robux_balance = balance and "Robux: " .. abbreviate_number(tonumber(balance)) or "Failed to fetch Robux"
end

-- Function to update the text source in OBS
local function update_text()
    if is_fetching then
        fetch_robux_balance()
        local source = obs.obs_get_source_by_name(TextSource)
        if source then
            local settings = obs.obs_data_create()
            obs.obs_data_set_string(settings, "text", robux_balance)
            obs.obs_source_update(source, settings)
            obs.obs_data_release(settings)
            obs.obs_source_release(source)
        end
    end
end

-- OBS Script Load
function script_load(settings)
    obs.timer_add(update_text, update_interval * 1000)
end

-- OBS Script Unload
function script_unload()
    obs.timer_remove(update_text)
end

-- Start Fetching Robux Balance
function start_fetching()
    is_fetching = true
    robux_balance = "Fetching..."
    log_message("Info", "Fetching started...")
end

-- Stop Fetching Robux Balance
function stop_fetching()
    is_fetching = false
    robux_balance = "Stopped"
    log_message("Info", "Fetching stopped.")
end

-- OBS Script Properties
function script_properties()
    local props = obs.obs_properties_create()
    obs.obs_properties_add_button(props, "start_button", "Start Fetching", start_fetching)
    obs.obs_properties_add_button(props, "stop_button", "Stop Fetching", stop_fetching)
    return props
end
