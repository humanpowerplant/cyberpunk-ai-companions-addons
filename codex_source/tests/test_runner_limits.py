"""Real disposable Python children, never Codex/login/models or existing services."""
import dataclasses
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "payload/game/red4ext/plugins/AiNpcCodexBridge"))
import bridge


class RunnerLimitTests(unittest.TestCase):
    def test_cancelled_or_expired_auth_check_never_starts_generation(self):
        for mode, expected in (("already-cancelled", "request_cancelled"),
                               ("cancel-during-auth", "request_cancelled"),
                               ("deadline-during-auth", "codex_timeout")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="codex-runner-fixture-") as directory:
                config=dataclasses.replace(bridge.Config(),codex_home="isolated",timeout_seconds=5)
                config.state_directory=Path(directory)
                cancel=threading.Event()
                if mode=="already-cancelled": cancel.set()
                def auth(_config):
                    if mode=="cancel-during-auth": cancel.set()
                    return True
                clock=[0,20] if mode=="deadline-during-auth" else [0,0]
                with patch.object(bridge,"check_chatgpt_auth",side_effect=auth) as check, \
                     patch.object(bridge.subprocess,"Popen") as launch, \
                     patch.object(bridge.time,"monotonic",side_effect=clock):
                    with self.assertRaises(bridge.BridgeError) as error:
                        bridge.CodexRunner(config).run([{"role":"user","content":"fixture"}],[],cancel,lambda _:None)
                    self.assertEqual(error.exception.code,expected)
                    launch.assert_not_called()
                    if mode=="already-cancelled": check.assert_not_called()

    def invoke(self, script, *, cancel=None, text="synthetic dialogue", output_limit=100000, timeout=3):
        with tempfile.TemporaryDirectory(prefix="codex-runner-fixture-") as directory:
            config = dataclasses.replace(bridge.Config(), codex_home="isolated", timeout_seconds=timeout, max_output_chars=output_limit)
            config.state_directory = Path(directory)
            args = [sys.executable, "-u", "-c", script]
            with patch.object(bridge, "check_chatgpt_auth", return_value=True), patch.object(bridge, "cli_arguments", return_value=args):
                return bridge.CodexRunner(config).run([{"role":"user","content":text}], [], cancel or threading.Event(), lambda _: None)

    def test_successful_synthetic_stdout_is_parsed_without_a_model(self):
        event = {"type":"item.completed", "item":{"type":"agent_message","text":"合成テストです。"}}
        script = "import sys,json;sys.stdin.read();print(" + repr(json.dumps(event,ensure_ascii=True)) + ")"
        self.assertEqual(self.invoke(script)["text"], "合成テストです。")

    def test_child_not_reading_stdin_still_cancels_with_large_input(self):
        cancel = threading.Event(); timer = threading.Timer(.2, cancel.set); timer.start(); started=time.monotonic()
        try:
            with self.assertRaises(bridge.BridgeError) as error:
                self.invoke("import time;time.sleep(60)", cancel=cancel, text="x"*250000)
            self.assertEqual(error.exception.code,"request_cancelled")
            self.assertLess(time.monotonic()-started,5)
        finally: timer.cancel()

    def test_output_size_limit_and_unknown_tool_event_abort_child(self):
        cases = [({"type":"item.completed", "item":{"type":"agent_message","text":"x"*2000}}, "codex_output_limit"),
                 ({"type":"item.started", "item":{"type":"command_execution","command":"synthetic-not-executed"}}, "unexpected_item_command_execution")]
        for event, code in cases:
            script="import sys,json,time;sys.stdin.read();print("+repr(json.dumps(event))+",flush=True);time.sleep(60)"
            with self.assertRaises(bridge.BridgeError) as error:
                self.invoke(script,output_limit=1024)
            self.assertEqual(error.exception.code,code)


if __name__ == '__main__': unittest.main(verbosity=2)
