-- Settings-only add-on. Uses AI Companions public API 1.1; no main-mod patches.
local handle, mapping, lastStatus
local clock, nextTry, tries = 0, 0, 0
local localization = dofile('ui-localization.lua')

local function readJson(path)
    local file = io.open(path, 'r')
    if not file then return nil end
    local raw = file:read(16385)
    file:close()
    if not raw or #raw > 16384 then return nil end
    local ok, value = pcall(json.decode, raw)
    return ok and type(value) == 'table' and value or nil
end

local function publish(status)
    return handle:settings(localization.definition(mapping, status))
end

local function refresh()
    if not handle then return end
    local status = readJson('runtime/status.json')
    local signature = status and table.concat({tostring(status.updated), tostring(status.state), tostring(status.model),
        tostring(status.reasoningEffort), tostring(status.errorCode), tostring(status.message)}, '|') or 'pending'
    if signature ~= lastStatus then
        lastStatus = signature
        publish(status)
    end
end

local function register()
    if handle or tries >= 15 then return end
    tries = tries + 1
    local main = GetMod('AiNpcCyberpunkMod')
    local api = main and main.addons
    if not api or not api.compatible('1.1') then return end
    mapping = readJson('settings-map.json')
    if not mapping or (mapping.version ~= 1 and mapping.version ~= 2) then
        print('[Codex Bridge] settings-map.json is missing or invalid')
        tries = 15
        return
    end
    localization.load()
    local reason
    handle, reason = api.register({id = 'codex-bridge', name = 'Codex Bridge', version = '1.2.2-rc.1', requires = '1.1'})
    if not handle then print('[Codex Bridge] Registration failed: ' .. tostring(reason)); return end
    refresh()
end

registerForEvent('onInit', register)
registerForEvent('onUpdate', function(delta)
    clock = clock + (tonumber(delta) or 0)
    if clock < nextTry then return end
    nextTry = clock + 2
    if not handle then register() else refresh() end
end)
