"""Test the read-only CET selector without executing actual game scripts."""
from pathlib import Path
import json, os, sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJit

reports = []
source = (ROOT / 'common/cet-auto.lua').read_text(encoding='utf-8-sig')
test = (ROOT / 'tests/cet-auto.test.lua').read_text(encoding='utf-8-sig')
for name, runtime in [('Lua 5.4', Lua54), ('LuaJIT 2.1 standard', LuaJit)]:
    lua = runtime(unpack_returned_tuples=True)
    syntax = lua.eval('function(s) local f,e=(loadstring or load)(s);return f~=nil,e end')
    for text in (source, test):
        ok, error = syntax(text)
        assert ok, (name, error)
    result = lua.execute(test)
    assert result['passed']
    reports.append({'runtime': name, 'passed': True, 'checks': result['checks'],
                    'inGameTested': False, 'liveWrites': False})
print(json.dumps(reports, ensure_ascii=False))
