-- Primitive UI definitions for the main mod's optional localized-settings extension.
-- This module never detects/sets language, reads main-mod settings or changes model IDs.
local M = {}
local LANGUAGES = {'en', 'zh-cn', 'zh-tw', 'es', 'pt-br', 'fr', 'de', 'it', 'pl', 'cs', 'hu', 'tr', 'ru', 'uk', 'ja', 'ko', 'ar'}
local ERROR_CODES = {
    ['invalid selection'] = 'invalid_selection',
    ['model or effort unsupported'] = 'model_or_effort_unsupported',
    ['bridge rejected settings'] = 'bridge_rejected_settings',
    ['invalid bridge response'] = 'invalid_bridge_response',
    ['bridge unavailable'] = 'bridge_unavailable',
    ['status write failed'] = 'status_write_failed'
    ,['old bridge restart required'] = 'old_bridge_restart_required'
    ,['local bridge credential unavailable'] = 'local_bridge_credential_unavailable'
    ,['invalid local bridge configuration'] = 'invalid_local_bridge_configuration'
    ,['invalid local bridge credential'] = 'invalid_local_bridge_credential'
    ,['local bridge proof rejected'] = 'local_bridge_proof_rejected'
}
local ENGLISH = {
    title = 'Codex Bridge', intro = 'Apply saves for the next request. ',
    modelLabel = 'Model',
    modelDescription = 'New users use the CLI default. Legacy presets retain saved indices; availability depends on the account. Advanced: set model in the per-user config.json and select Custom model from config. Select Custom as Conversation provider.',
    effortLabel = 'Reasoning effort',
    effortDescription = 'New users use Auto (CLI default). Higher effort can be slower. Invalid model/effort combinations are rejected; the last applied selection stays active. Use Auto if unsure.',
    modelDefault = 'Codex default',
    modelRecommended = 'CLI default (recommended)', modelConfigured = 'Custom model from config.json',
    statusSharedHome = ' Legacy shared Codex home: use a dedicated home and sign in there once; see README.',
    statusPending = 'Last check: pending. Select Custom to use the bridge.',
    statusReady = 'Last check: {model} / {effort}.',
    statusError = 'Last check failed: {error}.',
    effort_low = 'Low', effort_medium = 'Medium', effort_high = 'High',
    effort_xhigh = 'Very high (xhigh)', effort_max = 'Maximum (max)', effort_ultra = 'Ultra',
    effort_auto = 'Auto (CLI default)',
    error_invalid_selection = 'Invalid selection',
    error_model_or_effort_unsupported = 'Model or effort unsupported',
    error_bridge_rejected_settings = 'Settings rejected by bridge',
    error_invalid_bridge_response = 'Invalid bridge response',
    error_bridge_unavailable = 'Bridge unavailable',
    error_status_write_failed = 'Status could not be saved',
    error_old_bridge_restart_required = 'Old bridge: stop it yourself and restart with updated files',
    error_local_bridge_credential_unavailable = 'Local credential unavailable; restart the owned bridge',
    error_invalid_local_bridge_configuration = 'Invalid per-user bridge configuration',
    error_invalid_local_bridge_credential = 'Invalid local bridge credential',
    error_local_bridge_proof_rejected = 'Local service proof rejected; no credential was sent'
}
local catalog = {en = ENGLISH}
local function placeholders(value)
    local found = {}
    for key in value:gmatch('{([A-Za-z_][A-Za-z0-9_]*)}') do found[key] = true end
    return found
end
local function samePlaceholders(a, b)
    local left, right = placeholders(a), placeholders(b)
    for key in pairs(left) do if not right[key] then return false end end
    for key in pairs(right) do if not left[key] then return false end end
    return true
end
function M.load()
    -- Only the authored catalog gets a larger bound. settings-map/status retain init.lua's 16 KiB limit.
    local file = io.open('ui-catalog.json', 'r')
    if not file then return false end
    local raw = file:read(262145)
    file:close()
    if not raw or #raw > 262144 then return false end
    local ok, value = pcall(json.decode, raw)
    if not ok or type(value) ~= 'table' or value.version ~= 1 or type(value.locales) ~= 'table' then return false end
    local accepted = {en = ENGLISH}
    for _, code in ipairs(LANGUAGES) do
        local source, values = value.locales[code], {}
        if type(source) == 'table' then
            for key, english in pairs(ENGLISH) do
                local translated = source[key]
                if type(translated) == 'string' and #translated > 0 and #translated <= 2048
                    and not translated:find('%z') and samePlaceholders(english, translated) then
                    values[key] = translated
                end
            end
            accepted[code] = values
        end
    end
    catalog = accepted
    return true
end
local function text(code, key, args)
    local values = catalog[code]
    local value = values and values[key] or ENGLISH[key] or key
    if type(args) ~= 'table' then return value end
    return (value:gsub('{([A-Za-z_][A-Za-z0-9_]*)}', function(name)
        local item = rawget(args, name)
        return type(item) == 'string' and item or '{' .. name .. '}'
    end))
end
local function modelLabel(mapping, code, id)
    if type(id) == 'string' and #id <= 100 and id:match('^[A-Za-z0-9_.-]+$') then return id == 'codex-default' and text(code, 'modelDefault') or id end
    for _, model in ipairs(mapping.models) do
        if model.id == id then return model.id == 'codex-default' and text(code, 'modelDefault') or model.label end
    end
    return '?'
end
local function effortLabel(mapping, code, id)
    for _, effort in ipairs(mapping.efforts) do if effort == id then return text(code, 'effort_' .. effort) end end
    return '?'
end
local function errorCode(status)
    if type(status.errorCode) == 'string' then
        for _, code in pairs(ERROR_CODES) do if code == status.errorCode then return code end end
    end
    return ERROR_CODES[status.message] or 'bridge_unavailable'
end
local function description(mapping, code, status)
    local detail
    if type(status) ~= 'table' or status.version ~= 1 then detail = text(code, 'statusPending')
    elseif status.state == 'applied' or status.state == 'ready' then
        detail = text(code, 'statusReady', {model = modelLabel(mapping, code, status.model),
            effort = effortLabel(mapping, code, status.reasoningEffort)})
    elseif status.state == 'error' then
        detail = text(code, 'statusError', {error = text(code, 'error_' .. errorCode(status))})
    else detail = text(code, 'statusPending') end
    if type(status) == 'table' and status.warning == 'legacy_shared_codex_home' then detail = detail .. text(code, 'statusSharedHome') end
    return text(code, 'intro') .. detail
end
local function localizedSection(mapping, code, status)
    local models, efforts = {}, {}
    for index, model in ipairs(mapping.models) do
        models[index] = index == 11 and text(code, 'modelRecommended') or model.id == 'config-model' and text(code, 'modelConfigured') or model.id == 'codex-default' and text(code, 'modelDefault') or model.label
    end
    for index, effort in ipairs(mapping.efforts) do efforts[index] = effortLabel(mapping, code, effort) end
    return {title = text(code, 'title'), description = description(mapping, code, status), items = {
        model = {label = text(code, 'modelLabel'), description = text(code, 'modelDescription'), elements = models},
        reasoning = {label = text(code, 'effortLabel'), description = text(code, 'effortDescription'), elements = efforts}
    }}
end
function M.definition(mapping, status)
    local base, localizations = localizedSection(mapping, 'en', status), {}
    for _, code in ipairs(LANGUAGES) do localizations[code] = localizedSection(mapping, code, status) end
    return {title = base.title, description = base.description, remarkCap = false, items = {
        {id = 'model', label = base.items.model.label, kind = 'select', default = mapping.defaults.model,
            elements = base.items.model.elements, description = base.items.model.description},
        {id = 'reasoning', label = base.items.reasoning.label, kind = 'select', default = mapping.defaults.reasoning,
            elements = base.items.reasoning.elements, description = base.items.reasoning.description}
    }, localizations = localizations}
end
return M

