-- Pure, in-memory fixtures. No game API calls and no writes to the game or source snapshots.
local file = assert(io.open('common/cet-auto.lua', 'rb'))
local selectorSource = file:read('*a');file:close()
local checks = 0
local function check(value, label) checks = checks + 1;assert(value, label) end
local function equal(a, b, label) check(a == b, label .. ': ' .. tostring(a) .. ' / ' .. tostring(b)) end
local function raises(fn, needle, label)
    local ok, problem = pcall(fn)
    check(not ok and tostring(problem):find(needle, 1, true), label .. ': ' .. tostring(problem))
end
local function row(path, source) return {path = path, source = source} end
local function descriptor(id, files, combinations)
    return {schema = 1, id = id, upstreamRelease = '0.4.6', release = id == 'codex' and '1.2.2-rc.2' or '1.0.4-rc.2', releaseFamily = 'companion-addons-046-rc2', supportedPairing = {codex='1.2.2-rc.2',japanese='1.0.4-rc.2'}, files = files or {}, combinations = combinations}
end
local function fixture()
    local files, documents, reads, compiles, executions = {}, {}, {}, {}, {}
    local env = setmetatable({}, {__index = _G})
    local function compile(text, name)
        local fn, problem
        if setfenv then fn, problem = loadstring(text, '@' .. name);if fn then setfenv(fn, env) end
        else fn, problem = load(text, '@' .. name, 't', env) end
        return fn, problem
    end
    env.io = {open = function(path)
        reads[path] = (reads[path] or 0) + 1
        local text = files[path]
        if text == nil then return nil, 'not found', 2 end
        local cursor = 1
        return {read = function(_, n)
            if n == '*a' then return text end
            local value = text:sub(cursor, cursor + n - 1);cursor = cursor + n
            return value
        end, close = function() end}
    end}
    env.json = {decode = function(text) return assert(documents[text], 'bad JSON') end}
    env.executed = function(path) executions[#executions + 1] = path end
    env.loadfile = function(path)
        compiles[path] = (compiles[path] or 0) + 1
        if not files[path] then return nil, 'not found' end
        return compile(files[path], path)
    end
    env.dofile = function(path)
        local fn, problem = env.loadfile(path);assert(fn, problem)
        return fn()
    end
    files['community/selector.lua'] = selectorSource
    files['community/pristine/init.lua'] = "executed('base');return {kind='base', addons={version='1.1'}}"
    local F = {files = files, documents = documents, reads = reads, compiles = compiles, executions = executions, env = env}
    function F.feature(id, doc)
        local token = id .. ':' .. tostring(#documents + 1)
        while documents[token] do token = token .. 'x' end
        documents[token] = doc
        files['community/features/' .. id .. '.json'] = token
    end
    function F.payload(path, kind) files[path] = "executed('" .. kind .. "');return {kind='" .. kind .. "',addons={version='1.1'}}" end
    function F.selector() return env.dofile('community/selector.lua') end
    return F
end

local base = fixture()
equal(base.selector().load('init.lua').kind, 'base', 'disabled features use pristine')
equal(base.selector().load('init.lua').addons.version, '1.1', 'GetMod export is returned')

local jp = fixture();jp.payload('community/payload/jp.lua', 'jp')
jp.feature('japanese', descriptor('japanese', {row('init.lua', 'community/payload/jp.lua')}))
equal(jp.selector().load('init.lua').kind, 'jp', 'Japanese only')
local codex = fixture();codex.payload('community/payload/codex.lua', 'codex')
codex.feature('codex', descriptor('codex', {row('init.lua', 'community/payload/codex.lua')}))
equal(codex.selector().load('init.lua').kind, 'codex', 'Codex only')

local both = fixture()
both.payload('community/payload/jp.lua', 'jp');both.payload('community/payload/codex.lua', 'codex');both.payload('community/payload/both.lua', 'both')
local combined = {['codex+japanese'] = {row('init.lua', 'community/payload/both.lua')}}
both.feature('codex', descriptor('codex', {row('init.lua', 'community/payload/codex.lua')}, combined))
both.feature('japanese', descriptor('japanese', {row('init.lua', 'community/payload/jp.lua')}, combined))
local selected = both.selector()
equal(selected.load('init.lua').kind, 'both', 'both select combination')
equal(#both.executions, 1, 'validation did not execute other variants')
equal(both.compiles['community/payload/jp.lua'], nil, 'unselected Japanese source not compiled')
both.files['community/features/codex.json'] = nil
equal(both.selector().load('init.lua').kind, 'both', 'feature choice cached for this boot')
equal(both.reads['community/features/codex.json'], 1, 'descriptor not reread mid-boot')

local disabled = fixture();disabled.payload('community/payload/jp.lua', 'jp')
disabled.feature('japanese', descriptor('japanese', {row('init.lua', 'community/payload/jp.lua')}, combined))
equal(disabled.selector().load('init.lua').kind, 'jp', 'one feature disabled selects remaining feature')

local same = fixture();same.payload('community/payload/shared.lua', 'shared')
for _, id in ipairs({'codex', 'japanese'}) do same.feature(id, descriptor(id, {row('init.lua', 'community/payload/shared.lua')})) end
equal(same.selector().load('init.lua').kind, 'shared', 'same source can be declared by both features')

local collision = fixture();collision.payload('community/payload/a.lua', 'a');collision.payload('community/payload/b.lua', 'b')
collision.feature('codex', descriptor('codex', {row('init.lua', 'community/payload/a.lua')}))
collision.feature('japanese', descriptor('japanese', {row('init.lua', 'community/payload/b.lua')}))
raises(function() collision.selector().load('init.lua') end, 'Unresolved feature collision', 'collision does not pick load order winner')
equal(#collision.executions, 0, 'collision never executes partial recipe')

local missing = fixture();missing.payload('community/payload/valid.lua', 'valid')
missing.feature('codex', descriptor('codex', {row('init.lua', 'community/payload/valid.lua'),row('later.lua', 'community/payload/missing.lua')}))
raises(function() missing.selector().load('init.lua') end, 'later.lua', 'all selected payloads checked before first execution')
equal(#missing.executions, 0, 'missing later module prevents initial side effects')
missing.files['community/features/codex.json'] = nil
raises(function() missing.selector().load('init.lua') end, 'later.lua', 'failed selection stays failed for boot')

local syntax = fixture();syntax.payload('community/payload/valid.lua', 'valid');syntax.files['community/payload/bad.lua'] = 'return {'
syntax.feature('codex', descriptor('codex', {row('init.lua', 'community/payload/valid.lua'),row('later.lua', 'community/payload/bad.lua')}))
raises(function() syntax.selector().load('init.lua') end, 'Cannot load later.lua', 'syntax failure detected before side effects')
equal(#syntax.executions, 0, 'syntax failure never executes first module')

local absent = fixture()
raises(function() absent.selector().load('new-feature.lua') end, 'pristine fallback', 'unselected new module fails only when requested')
equal(absent.selector().load('init.lua').kind, 'base', 'optional missing new module does not spoil pristine')

for _, bad in ipairs({'../init.lua','/init.lua',('C' .. ':/init.lua'),'a/../init.lua','a\\init.lua','a//init.lua','a/./init.lua','x.lua\0','x.lua ','CON.lua','a/NUL.foo.lua','a?.lua'}) do
    local f = fixture()
    raises(function() f.selector().load(bad) end, 'Unsafe requested Lua target', 'unsafe load rejected: ' .. bad)
end
for _, bad in ipairs({'../out.lua','outside.lua','community/../out.lua','community/a/../../out.lua',('community/' .. 'C' .. ':/out.lua')}) do
    local f = fixture();f.feature('codex', descriptor('codex', {row('init.lua', bad)}))
    raises(function() f.selector().load('init.lua') end, 'Unsafe Lua target or source', 'unsafe source rejected: ' .. bad)
end
local wrong = fixture();local badVersion = descriptor('codex');badVersion.upstreamRelease = '0.4.4';wrong.feature('codex', badVersion)
raises(function() wrong.selector().load('init.lua') end, 'Unsupported feature descriptor', 'version mismatch refused')
local malformed = fixture();malformed.files['community/features/codex.json'] = 'broken'
raises(function() malformed.selector().load('init.lua') end, 'Unsupported feature descriptor', 'malformed descriptor refuses quiet fallback')
local duplicate = fixture();duplicate.feature('codex', descriptor('codex', {row('init.lua','community/a.lua'),row('init.lua','community/a.lua')}))
raises(function() duplicate.selector().load('init.lua') end, 'Duplicate Lua target', 'duplicate target refused')
local sparse = fixture();sparse.feature('codex', descriptor('codex', {[1]=row('init.lua','community/a.lua'),[3]=row('late.lua','community/b.lua'),[5]=row('other.lua','community/c.lua')}))
raises(function() sparse.selector().load('init.lua') end, 'Sparse files array', 'sparse recipe cannot silently omit rows')
local disagree = fixture();disagree.payload('community/a.lua','a');disagree.payload('community/b.lua','b')
disagree.feature('codex', descriptor('codex', {}, {['codex+japanese']={row('init.lua','community/a.lua')}}))
disagree.feature('japanese', descriptor('japanese', {}, {['codex+japanese']={row('init.lua','community/b.lua')}}))
raises(function() disagree.selector().load('init.lua') end, 'Conflicting combination source', 'combination co-declarations must agree')

-- Payload remains in the same sandbox: its nested dofile and runtime io keep mainmod-relative paths.
local cwd = fixture()
cwd.files['runtime/root-context.txt'] = 'mainmod-root'
cwd.files['nested.lua'] = "return dofile('community/selector.lua').load('nested.lua')"
cwd.files['community/payload/entry.lua'] = "local file=assert(io.open('runtime/root-context.txt','rb'));local text=file:read(100);file:close();return {context=text,nested=dofile('nested.lua')}"
cwd.files['community/payload/nested.lua'] = "return {token='same-sandbox'}"
cwd.feature('codex', descriptor('codex', {row('init.lua','community/payload/entry.lua'),row('nested.lua','community/payload/nested.lua')}))
local exported = cwd.selector().load('init.lua')
equal(exported.context, 'mainmod-root', 'runtime io is mainmod-relative')
equal(exported.nested.token, 'same-sandbox', 'nested dofile is mainmod-relative')
local mixed = fixture();mixed.payload('community/payload/old.lua','old')
local old = descriptor('codex',{row('init.lua','community/payload/old.lua')})
old.releaseFamily = nil;old.release = '1.2.1-preview.3';old.supportedPairing = nil
mixed.feature('codex',old);mixed.feature('japanese',descriptor('japanese'))
equal(mixed.selector().load('init.lua').kind,'base','mixed generation uses pristine instead of old combination')
check(mixed.selector().status().fallback,'mixed generation status is explicit')
check(mixed.selector().status().diagnostic:find('COMMUNITY_PAIRING_INCOMPATIBLE',1,true),'mixed generation reason is available')
equal(mixed.compiles['community/payload/old.lua'],nil,'incompatible payload is never compiled or executed')
local alias=fixture();alias.feature('codex',descriptor('codex',{row('init.lua','community/a.lua'),row('INIT.lua','community/b.lua')}))
raises(function()alias.selector().load('init.lua')end,'Case-insensitive Lua target alias','Windows target alias refused')
return {passed = true, checks = checks}
