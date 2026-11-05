-- A passive in-game diagnostic. No conversation content or credentials are read here.
local M = {}
local ui = convaiUiLocale or dofile('ui-locale.lua')
local fonts = convaiUiFonts or dofile('ui-fonts.lua')
local service = convaiServiceStatus or dofile('service-status.lua')
local widgetName = 'AiNpcConversationStatusHud'
local ordinaryFont = 'base\\gameplay\\gui\\fonts\\raj\\raj.inkfontfamily'
local panel, title, detail, shownTitle, shownDetail, shownLanguage
local elapsed = 0
local noteUntil, noteLabel, noteCode

local function hudRoot()
    local ink = Game.GetInkSystem()
    local layer = ink and ink:GetLayer(CName.new('inkHUDLayer'))
    return layer and layer:GetVirtualWindow()
end

local function removePanel()
    local root = hudRoot()
    if root then root:RemoveChildByName(CName.new(widgetName)) end
end

local function margin(x, y)
    return inkMargin.new({left = x, top = y, right = 0, bottom = 0})
end

local function label(name, y)
    local widget = inkText.new()
    widget:SetName(CName.new(name))
    widget:SetAnchor(inkEAnchor.TopLeft)
    widget:SetMargin(margin(12, y))
    widget:SetFontSize(25)
    widget:SetInteractive(false)
    widget:SetTintColor(HDRColor.new({Red = 0.8, Green = 0.95, Blue = 1.0, Alpha = 1.0}))
    return widget
end

local function attach()
    local root = hudRoot()
    if not root then return false end
    root:RemoveChildByName(CName.new(widgetName))
    local container = inkCanvas.new()
    container:SetName(CName.new(widgetName))
    container:SetAnchor(inkEAnchor.TopLeft)
    container:SetAnchorPoint(Vector2.new({X = 0, Y = 0}))
    container:SetMargin(margin(55, 155))
    container:SetSize(Vector2.new({X = 670, Y = 75}))
    container:SetInteractive(false)

    local background = inkRectangle.new()
    background:SetAnchor(inkEAnchor.Fill)
    background:SetTintColor(HDRColor.new({Red = 0.025, Green = 0.07, Blue = 0.1, Alpha = 1.0}))
    background:SetOpacity(0.83)
    background:SetInteractive(false)
    background:Reparent(container, -1)
    local titleWidget, detailWidget = label('statusTitle', 4), label('statusDetail', 38)
    titleWidget:Reparent(container, -1)
    detailWidget:Reparent(container, -1)
    container:Reparent(root, -1)
    panel, title, detail = container, titleWidget, detailWidget
    return true
end

local function detach(nativeSafe)
    if panel and nativeSafe then pcall(removePanel) end
    panel, title, detail, shownTitle, shownDetail, shownLanguage = nil, nil, nil, nil, nil, nil
    elapsed = 0
end

function M.clear(nativeSafe)
    detach(nativeSafe)
    noteUntil, noteLabel, noteCode = nil, nil, nil
end

function M.visible()
    return panel ~= nil
end

function M.note(key, code)
    noteLabel, noteUntil = key, os.time() + 8
    noteCode = type(code) == 'string' and #code <= 32 and code:match('^[a-z][a-z0-9%-]*$') or nil
end

local function serviceLabel(now)
    local unavailable = service.unavailable(now)
    if unavailable then
        if unavailable.kind == 'starting' then return 'Service starting' end
        if unavailable.kind == 'stopped' then return 'Service offline' end
        return 'Service error'
    end
    return service.reach(now) == 'live' and 'Service ready' or 'Service starting'
end

local function conversationLabel(now, pending, speech, microphone, subtitles)
    if speech.requestId then
        if speech.state == 'playing' or speech.state == 'draining' then return 'Playing audio' end
        if speech.state == 'buffering' or speech.state == 'underrun' then return 'Audio buffering…' end
        return 'Starting audio…'
    end
    if microphone.state == 'starting' then return 'Preparing microphone…', microphone.started end
    if microphone.state == 'recording' then return 'Listening to V…', microphone.started end
    if pending then
        if pending.captionPreviewReady and subtitles.replyPreviewOwner == pending.requestId then
            return 'Text ready · waiting for voice…', pending.sentAt
        end
        local phase = service.turnPhase(pending.requestId, now)
        if phase == 'thinking' then return 'Generating the reply…', pending.sentAt end
        if phase == 'received' then return 'Preparing the reply…', pending.sentAt end
        if phase == 'ready' or phase == 'error' then return 'Receiving the reply…', pending.sentAt end
        return 'Waiting for the service to receive the request…', pending.sentAt
    end
    if microphone.state == 'reply' then return 'Processing voice input…', microphone.finishedAt end
    if noteUntil and now < noteUntil then return noteLabel, nil, noteCode end
    if subtitles.ownsUtterance() then
        return speech.state == 'playback-failed' and 'Audio failed' or 'Showing subtitles'
    end
    return 'Ready for conversation'
end

function M.update(show, delta, pending, speech, microphone, subtitles)
    if not show then
        detach(true)
        return
    end
    elapsed = elapsed + math.max(0, math.min(1, tonumber(delta) or 0))
    if elapsed < .2 then return end
    elapsed = 0
    if not panel and not attach() then return end
    local now = os.time()
    local language = ui.current()
    if language ~= shownLanguage then
        local mapped = fonts.family(language)
        local family = mapped or ordinaryFont
        local style = CName.new(language == 'ja' and 'Regular' or mapped and 'Semi-Bold' or 'Medium')
        for _, widget in ipairs({title, detail}) do
            widget:SetFontFamily(family, style)
            widget:SetLockFontInGame(true)
        end
        shownLanguage = language
    end
    local header = ui.t('AI Companions · {service}', {service = ui.t(serviceLabel(now))})
    local phase, started, code = conversationLabel(now, pending, speech, microphone, subtitles)
    local status = ui.t(phase)
    if type(started) == 'number' then
        status = ui.t('{state} · {seconds}s', {state = status, seconds = math.max(0, now - started)})
    end
    if code then status = status .. ' (' .. code .. ')' end
    if shownTitle ~= header then title:SetText(header); shownTitle = header end
    if shownDetail ~= status then detail:SetText(status); shownDetail = status end
end

return M
