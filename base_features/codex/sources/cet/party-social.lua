-- The bounded mailbox for V's optional interjection. Pure under injected env.
-- Never submits a regular conversation or simulates an actual player input.
local M = {GENERATION_WAIT = 15, PLAY_WAIT = 20, MAX_RESPONSE_BYTES = 16000}
local function clip(value, limit)
    local text = tostring(value or ''):gsub('[%z\1-\8\11\12\14-\31]', '')
    if #text <= limit then return text end
    text = text:sub(1, limit)
    local at = #text
    while at > 0 and text:byte(at) >= 128 and text:byte(at) < 192 do at = at - 1 end
    local lead = text:byte(at) or 0
    local size = lead >= 240 and 4 or lead >= 224 and 3 or lead >= 192 and 2 or 1
    return at + size - 1 > #text and text:sub(1, at - 1) or text
end
M.clip = clip
local function token(value)
    return type(value) == 'string' and #value > 0 and #value <= 128 and not value:find('[^%w_.:%-]')
end
local function asked(text, single)
    local named = text:find('%f[%a]V%f[%A]') or text:find('Ｖ', 1, true)
    local question = text:find('?', 1, true) or text:find('？', 1, true) or text:find('どう', 1, true)
        or text:find('教え', 1, true) or text:find('思う', 1, true) or text:find('だろ', 1, true)
        or text:find('ですか', 1, true) or text:find('か。', 1, true) or text:find('か$', 1)
    if not question then
        for _, word in ipairs({'何', 'いつ', 'どこ', '誰', 'なぜ', 'いくら'}) do
            if text:find(word, 1, true) then question = true; break end
        end
    end
    if not question then
        local lower = text:lower()
        for _, word in ipairs({'what', 'when', 'where', 'who', 'why', 'how'}) do
            if lower:find('%f[%a]' .. word .. '%f[%A]') then question = true; break end
        end
    end
    return (named ~= nil or single == true) and question ~= nil
end
function M.new(env)
    local C, pending, serial, lastHeard, attempted = {}, nil, 0, -1000000, {}
    local counts, order = {}, {}
    local function now() return env.now() end
    local function allowed()
        if not env.allowed then return true end
        local ok, value = pcall(env.allowed)
        return ok and value == true
    end
    local function ack(status, reason)
        if pending then pcall(env.write, 'social-v-ack.json', {version = 1, id = pending.id, roundId = pending.roundId,
            status = status, reason = reason, at = math.floor(now() * 1000)}) end
    end
    local function stop(reason)
        if pending then
            ack('cancelled', reason)
            if pending.shown and env.hideCaption then pcall(env.hideCaption) end
        end
        pending = nil
    end
    function C.begin(args)
        if pending or not allowed() or type(args) ~= 'table' or not token(args.roundId) then return false end
        local settings = env.settings()
        if settings.socialVReplies == 'off' or (counts[args.roundId] or 0) >= settings.socialMaxVReplies then return false end
        if now() - lastHeard < settings.socialVCooldown then return false end
        if args.roundDeadline and now() >= args.roundDeadline then return false end
        local trigger = args.trigger
        if type(trigger) ~= 'table' or type(trigger.text) ~= 'string' or not trigger.text:find('%S') then return false end
        local participants = args.participants or {}
        local single = args.single == true and #participants == 2
            and ((participants[1].key == 'player-v' and participants[2].key == trigger.key)
                or (participants[2].key == 'player-v' and participants[1].key == trigger.key))
        if settings.socialVReplies == 'asked' and not asked(trigger.text, single) then return false end
        local identity = args.roundId .. '/' .. tostring(args.n)
        if attempted[identity] then return false end
        attempted[identity] = true
        serial = serial + 1
        local id = 'sv-' .. math.floor(now() * 1000) .. '-' .. serial
        local boundary = env.boundary and env.boundary() or {}
        pending = {id = id, roundId = args.roundId, deadline = math.min(now() + M.GENERATION_WAIT, args.roundDeadline or math.huge),
            roundDeadline = args.roundDeadline, slot = settings.socialMemorySlot, phase = 'generating'}
        local request = {version = 1, id = id, roundId = args.roundId, issuedAt = math.floor(now() * 1000),
            expiresAt = math.floor(pending.deadline * 1000), worldToken = boundary.worldToken, worldGeneration = boundary.worldGeneration or boundary.generation,
            participants = args.participants, trigger = {speakerKey = trigger.key, name = trigger.name, text = clip(trigger.text, 1200)},
            lines = args.lines}
        local ok, accepted = pcall(env.write, 'social-v-request.json', request)
        if not ok or accepted == false then pending = nil; return false end
        return true
    end
    function C.poll()
        if not pending then return 'skipped' end
        if not allowed() then stop('gameplay-priority'); return 'skipped' end
        local settings = env.settings()
        if settings.socialVReplies == 'off' or settings.socialMemorySlot ~= pending.slot then stop('settings-changed'); return 'skipped' end
        if now() > pending.deadline then stop('timeout'); return 'skipped' end
        local ok, response = pcall(env.read, 'social-v-response.json', M.MAX_RESPONSE_BYTES)
        if not ok or type(response) ~= 'table' or response.version ~= 1 or response.id ~= pending.id or response.roundId ~= pending.roundId then return 'busy' end
        if type(response.expiresAt) ~= 'number' or response.expiresAt < now() * 1000 then stop('expired'); return 'skipped' end
        if response.respond == false or response.status == 'cancelled' or response.status == 'failed' then stop(response.reason or 'not-needed'); return 'skipped' end
        if response.status == 'ready' and pending.phase == 'generating' then
            if type(response.text) ~= 'string' or #response.text > 1200 or not response.text:find('%S') then stop('invalid-text'); return 'skipped' end
            local shown, accepted = pcall(env.showCaption, response.text, pending.id)
            if not shown or accepted ~= true then stop('caption-not-shown'); return 'skipped' end
            pending.text, pending.shown, pending.phase = response.text, true, 'playing'
            pending.deadline = math.min(now() + M.PLAY_WAIT, pending.roundDeadline or math.huge)
            ack('started')
        elseif response.status == 'done' and pending.phase == 'playing' then
            if response.text ~= nil and response.text ~= pending.text then stop('changed-text'); return 'skipped' end
            local text, roundId = pending.text, pending.roundId
            ack('heard')
            if env.hideCaption then pcall(env.hideCaption) end
            counts[roundId], lastHeard = (counts[roundId] or 0) + 1, now()
            pending = nil
            return 'done', text
        end
        return 'busy'
    end
    function C.cancel(reason) stop(reason or 'interrupted') end
    function C.active() return pending ~= nil end
    function C.roundStarted(id)
        if not counts[id] then
            counts[id] = 0; order[#order + 1] = id
            while #order > 32 do
                local expired = table.remove(order, 1); counts[expired] = nil
                for key in pairs(attempted) do if key:sub(1, #expired + 1) == expired .. '/' then attempted[key] = nil end end
            end
        end
    end
    function C.snapshot() return {pending = pending and pending.id, phase = pending and pending.phase, lastHeard = lastHeard} end
    return C
end
return M
