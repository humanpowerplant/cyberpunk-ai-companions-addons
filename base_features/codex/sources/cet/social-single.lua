-- A single companion remark may invite one V reply. It never starts another NPC turn.
local M = {}
function M.new(env)
    local C, pending = {}, nil
    local function finish(reason)
        local old = pending
        pending = nil
        if old and env.ended then pcall(env.ended, old.request, reason) end
    end
    function C.offer(heard)
        if pending or type(heard) ~= 'table' or type(heard.request) ~= 'table' then return false end
        if env.onHeard then pcall(env.onHeard, heard) end
        pending = {heard = heard, request = heard.request, started = false}
        if env.enabled and not env.enabled() then finish('done'); return false end
        return true
    end
    function C.update(blocked)
        if not pending then return false end
        if blocked then C.cancel('manual-or-world-priority'); return false end
        if not pending.started then
            local ok, accepted = pcall(env.interject, pending.heard)
            if not ok or accepted ~= true then finish('not-needed'); return false end
            pending.started = true
        end
        local ok, status = pcall(env.status)
        if not ok or status ~= 'busy' then finish(ok and status == 'done' and 'done' or 'not-needed') end
        return pending ~= nil
    end
    function C.cancel(reason)
        if not pending then return end
        if pending.started and env.cancel then pcall(env.cancel, reason or 'interrupted') end
        finish(reason or 'interrupted')
    end
    function C.active() return pending ~= nil end
    return C
end
return M
