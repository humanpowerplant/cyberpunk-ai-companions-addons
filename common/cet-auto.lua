-- Installed as community/selector.lua inside AiNpcCyberpunkMod's CET sandbox.
-- Every shared shim uses this same selector. Selection is fixed for this Lua boot.
if type(convaiCommunitySelectorCache) == 'table' then return convaiCommunitySelectorCache end

local M = {}
local VERSION, LIMIT_BYTES, LIMIT_FILES = '0.4.6', 524288, 1024
local RELEASE_FAMILY = 'companion-addons-046-rc1'
local PAIRING = {codex = '1.2.2-rc.1', japanese = '1.0.4-rc.1'}
local PREFIX = '[AI Companions Community] '
local booted, failure, selected, compiled = false, nil, nil, nil
local loading = {}
local diagnostic = nil

local function fail(message) error(PREFIX .. message, 0) end
local function relative(value, source)
    if type(value) ~= 'string' or #value == 0 or #value > 240
        or value:find('[%z\1-\31\127\\:*?"<>|]') or value:sub(1, 1) == '/'
        or value:sub(-4) ~= '.lua' then return false end
    for piece in (value .. '/'):gmatch('(.-)/') do
        if piece == '' or piece == '.' or piece == '..' or piece:find('[. ]$') then return false end
        local stem = (piece:match('^[^.]+') or ''):upper()
        if stem == 'CON' or stem == 'PRN' or stem == 'AUX' or stem == 'NUL' or stem:match('^COM[1-9]$') or stem:match('^LPT[1-9]$') then return false end
    end
    return not source or value:sub(1, 10) == 'community/'
end
local function readFeature(id)
    local path = 'community/features/' .. id .. '.json'
    local file, problem, code = io.open(path, 'rb')
    if not file then
        if code ~= nil and code ~= 2 then fail('Cannot read ' .. path .. ': ' .. tostring(problem)) end
        return nil
    end
    local text = file:read(LIMIT_BYTES + 1)
    file:close()
    if type(text) ~= 'string' or #text == 0 or #text > LIMIT_BYTES then fail('Invalid or oversized feature descriptor: ' .. path) end
    local ok, doc = pcall(json.decode, text)
    if not ok or type(doc) ~= 'table' or doc.schema ~= 1 or doc.id ~= id or doc.upstreamRelease ~= VERSION then
        fail('Unsupported feature descriptor: ' .. path .. ' (requires schema 1, matching id and upstreamRelease ' .. VERSION .. ')')
    end
    return doc
end
local function recipe(rows, label)
    if type(rows) ~= 'table' then fail('Missing files array in ' .. label) end
    local result, aliases, count, highest = {}, {}, 0, 0
    for index in pairs(rows) do
        if type(index) ~= 'number' or index < 1 or index ~= math.floor(index) or index > LIMIT_FILES then
            fail('Invalid files array in ' .. label)
        end
        count = count + 1
        highest = math.max(highest, index)
    end
    if count ~= highest then fail('Sparse files array in ' .. label) end
    for _, row in ipairs(rows) do
        if type(row) ~= 'table' or not relative(row.path, false) or not relative(row.source, true) then
            fail('Unsafe Lua target or source in ' .. label)
        end
        if result[row.path] then fail('Duplicate Lua target ' .. row.path .. ' in ' .. label) end
        local alias = row.path:lower()
        if aliases[alias] and aliases[alias] ~= row.path then fail('Case-insensitive Lua target alias in ' .. label) end
        aliases[alias] = row.path
        result[row.path] = row.source
    end
    return result
end
local function mergeInto(target, collisions, rows)
    for path, source in pairs(rows) do
        for existing in pairs(target) do
            if existing ~= path and existing:lower() == path:lower() then fail('Case-insensitive Lua target alias: ' .. path) end
        end
        if target[path] and target[path] ~= source then collisions[path] = true end
        target[path] = source
    end
end
local function compile(path, label)
    local called, chunk, problem = pcall(loadfile, path)
    if not called or type(chunk) ~= 'function' then
        fail('Cannot load ' .. label .. ' from ' .. path .. ': ' .. tostring(called and problem or chunk))
    end
    return chunk
end
local function build()
    local docs, ids, result, collisions = {}, {}, {}, {}
    for _, id in ipairs({'codex', 'japanese'}) do
        local doc = readFeature(id)
        if doc then
            docs[id], ids[#ids + 1] = doc, id
            mergeInto(result, collisions, recipe(doc.files, id))
            if doc.combinations ~= nil and type(doc.combinations) ~= 'table' then fail('Invalid combinations in ' .. id) end
            -- Validate all declared recipes as data, even when their feature set is absent.
            for key, rows in pairs(doc.combinations or {}) do
                if key ~= 'codex+japanese' then fail('Unknown feature combination in ' .. id) end
                recipe(rows, id .. ' combination ' .. key)
            end
        end
    end
    local combination = table.concat(ids, '+')
    for _, id in ipairs(ids) do
        local doc = docs[id]
        local compatible = doc.releaseFamily == RELEASE_FAMILY and doc.release == PAIRING[id] and type(doc.supportedPairing) == 'table'
        for peer, release in pairs(PAIRING) do
            if not doc.supportedPairing or doc.supportedPairing[peer] ~= release then compatible = false end
        end
        if not compatible then
            diagnostic = 'COMMUNITY_PAIRING_INCOMPATIBLE: Community add-ons disabled; update Japanese and Party/Codex packages to the same release family and Deploy with the newer shared loader winning. Original 0.4.6 Lua will run.'
            if type(print) == 'function' then print(PREFIX .. diagnostic) end
            return {}, {}
        end
    end
    if #ids > 1 then
        local overrides = {}
        for _, id in ipairs(ids) do
            local rows = docs[id].combinations and docs[id].combinations[combination]
            if rows then
                for path, source in pairs(recipe(rows, id .. ' combination ' .. combination)) do
                    if overrides[path] and overrides[path] ~= source then fail('Conflicting combination source for ' .. path) end
                    overrides[path] = source
                end
            end
        end
        for path, source in pairs(overrides) do
            for existing in pairs(result) do
                if existing ~= path and existing:lower() == path:lower() then fail('Case-insensitive Lua combination target alias: ' .. path) end
            end
            result[path], collisions[path] = source, nil
        end
    end
    for path in pairs(collisions) do fail('Unresolved feature collision for ' .. path .. ' (combination recipe required)') end
    local paths, chunks, bySource = {}, {}, {}
    for path in pairs(result) do paths[#paths + 1] = path end
    table.sort(paths)
    -- Compile every selected payload before executing any of them. Do not fall back silently.
    for _, path in ipairs(paths) do
        local source = result[path]
        if not bySource[source] then bySource[source] = compile(source, path) end
        chunks[path] = bySource[source]
    end
    return result, chunks
end
local function boot()
    if not booted then
        booted = true
        local ok, value, chunks = pcall(build)
        if ok then selected, compiled = value, chunks else failure = tostring(value) end
    end
    if failure then error(failure, 0) end
end
function M.load(path)
    if not relative(path, false) then fail('Unsafe requested Lua target') end
    boot()
    if loading[path] then fail('Circular Lua load for ' .. path) end
    local chunk = compiled[path]
    if not chunk then
        local pristine = 'community/pristine/' .. path
        chunk = compile(pristine, path .. ' pristine fallback')
        compiled[path] = chunk
    end
    loading[path] = true
    local ok, value = pcall(chunk)
    loading[path] = nil
    if not ok then fail('Execution failed for ' .. path .. ': ' .. tostring(value)) end
    return value
end
function M.status() boot();return {fallback = diagnostic ~= nil, diagnostic = diagnostic} end

convaiCommunitySelectorCache = M
return M
