-- Conservative fallback for a story/control transition with no attach notification.
-- It keeps primitive observations only; it never retains or manipulates game objects.
local M = {WAIT_SECONDS = 120, SETTLE_SECONDS = 3, PROBE_SECONDS = 0.5, MAX_SAMPLE_GAP = 2}
function M.new(options)
    options = options or {}
    local C, since, playerId, waitId, lastProbe, lastAt = {}, nil, nil, nil, nil, nil
    local wait = options.waitSeconds or M.WAIT_SECONDS
    local settle = options.settleSeconds or M.SETTLE_SECONDS
    function C.reset() since, playerId, waitId, lastProbe, lastAt = nil, nil, nil, nil, nil end
    function C.due(now)
        if type(now) ~= 'number' or now ~= now then return false end
        if lastProbe and now >= lastProbe and now - lastProbe < M.PROBE_SECONDS then return false end
        lastProbe = now
        return true
    end
    function C.update(input)
        input = input or {}
        local now = input.now
        if type(now) ~= 'number' or now ~= now or input.suspended ~= true or type(input.waitId) ~= 'number'
            or input.fastTravel == true or input.dead == true then C.reset();return false end
        local safe = input.sessionReady == true and input.worldReady == true and input.attached == true
            and input.dead == false and input.combat == false and input.tier == 1
            and input.dialogue == false and input.choices == false and input.call == false
            and input.vehicle == false and input.replacer == false and input.observationError ~= true
            and type(input.playerId) == 'string' and #input.playerId > 0 and #input.playerId <= 128
        if not safe then since, playerId, waitId, lastAt = nil, nil, nil, nil;return false end
        if playerId ~= input.playerId or waitId ~= input.waitId or not lastAt or now < lastAt or now - lastAt > M.MAX_SAMPLE_GAP then
            since, playerId, waitId = now, input.playerId, input.waitId
        end
        lastAt = now
        local attachedAt = input.attachedAt
        local observedWait = type(attachedAt) == 'number' and attachedAt <= now and now - attachedAt >= wait
        if now - since >= settle and (observedWait or now - since >= wait) then return true end
        return false
    end
    return C
end
return M
