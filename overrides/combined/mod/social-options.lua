-- Shared validation for the social-dialogue options. No I/O or game calls.
local M = {}
M.defaults = {socialMemory = true, socialRelations = false, socialVReplies = 'off', socialVVoice = false, socialVVoiceEngine = 'same',
    socialMaxVReplies = 1, socialVCooldown = 60, socialRoundSeconds = 90, socialVPersonality = 'balanced',
    socialVPronoun = 'ore', socialVDetail = 'balanced', socialMemorySlot = 'v1'}
M.choices = {socialVReplies = {'off', 'asked', 'contextual'}, socialVVoiceEngine = {'same', 'v-setting'}, socialMaxVReplies = {1, 2}, socialVCooldown = {30, 60, 120},
    socialRoundSeconds = {60, 90, 120}, socialVPersonality = {'balanced', 'casual', 'sarcastic', 'cautious', 'custom'},
    socialVPronoun = {'ore', 'watashi', 'atashi', 'jibun'}, socialVDetail = {'rough', 'balanced', 'precise'},
    socialMemorySlot = {'v1', 'v2', 'v3', 'v4'}}
function M.has(key) return M.defaults[key] ~= nil end
function M.valid(key, value)
    local fallback = M.defaults[key]
    if fallback == nil then return false end
    if type(fallback) == 'boolean' then return type(value) == 'boolean' end
    for _, choice in ipairs(M.choices[key] or {}) do if value == choice then return true end end
    return false
end
function M.read(settings)
    local result = {}
    for key, fallback in pairs(M.defaults) do
        if M.valid(key, settings and settings[key]) then result[key] = settings[key] else result[key] = fallback end
    end
    return result
end
function M.index(key, value)
    if not M.valid(key, value) then value = M.defaults[key] end
    for index, choice in ipairs(M.choices[key] or {}) do if value == choice then return index end end
    return 1
end
return M
