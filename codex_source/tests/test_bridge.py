import base64
import dataclasses
import http.client
import json
import threading
import time
import tempfile
import socket
import hmac
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "payload/game/red4ext/plugins/AiNpcCodexBridge"))
import bridge


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.cancelled = threading.Event()

    def run(self, messages, images, cancel, on_text):
        self.calls.append((messages, images))
        if messages[-1]["content"] == "wait":
            while not cancel.wait(0.01):
                pass
            self.cancelled.set()
            raise bridge.BridgeError("request_cancelled", 499)
        text = "接続できました。"
        on_text(text)
        return {"text": text, "elapsed_ms": 1, "usage": {"input_tokens": 5, "output_tokens": 4}}


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.runner = FakeRunner()
        self.config = dataclasses.replace(bridge.Config(), port=0, queue_wait_seconds=0)
        self.temporary = tempfile.TemporaryDirectory()
        self.config.state_directory = Path(self.temporary.name)
        self.server = bridge.BridgeServer(self.config, self.runner, settings_path=Path(self.temporary.name) / "selection.json")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.stopping.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def request(self, body, path="/v1/chat/completions", headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("POST", path, json.dumps(body), {"Content-Type": "application/json", "Authorization": "Bearer " + self.server.local_token, **(headers or {})})
        response = connection.getresponse()
        status, data = response.status, response.read().decode()
        connection.close()
        return status, data

    def test_json_and_stateless_messages(self):
        body = {"messages": [{"role": "system", "content": "enum only"}, {"role": "user", "content": "hello"}]}
        status, data = self.request(body)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["choices"][0]["message"]["content"], "接続できました。")
        self.request({"messages": [{"role": "user", "content": "new turn"}]})
        self.assertEqual(len(self.runner.calls[1][0]), 1)
        self.assertEqual(self.runner.calls[0][0][0]["content"], "enum only")

    def test_sse_shape(self):
        status, data = self.request({"messages": [{"role": "user", "content": "hello"}], "stream": True})
        self.assertEqual(status, 200)
        chunks = [line[6:] for line in data.splitlines() if line.startswith("data: ")]
        self.assertEqual(json.loads(chunks[0])["choices"][0]["delta"]["role"], "assistant")
        self.assertEqual(json.loads(chunks[1])["choices"][0]["delta"]["content"], "接続できました。")
        self.assertEqual(chunks[-1], "[DONE]")

    def test_tools_are_rejected(self):
        status, _ = self.request({"messages": [{"role": "user", "content": "hello"}], "tools": [{"type": "function"}]})
        self.assertEqual(status, 400)
        self.assertFalse(self.runner.calls)

    def test_non_loopback_host_is_rejected(self):
        status, _ = self.request({"messages": [{"role": "user", "content": "hello"}]}, headers={"Host": "attacker.example"})
        self.assertEqual(status, 403)
        self.assertFalse(self.runner.calls)

    def test_foreign_origin_is_rejected(self):
        status, _ = self.request({"messages": [{"role": "user", "content": "hello"}]}, headers={"Origin": "https://example.com"})
        self.assertEqual(status, 403)

    def test_external_image_is_rejected(self):
        status, data = self.request({"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "http://127.0.0.1/private"}}]}]})
        self.assertEqual(status, 400)
        self.assertIn("only_embedded_base64_images_supported", data)

    def test_embedded_image_is_preserved(self):
        fixture = b"\x89PNG\r\n\x1a\nsynthetic"
        url = "data:image/png;base64," + base64.b64encode(fixture).decode()
        messages, images = bridge.normalise_messages({"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}}, {"type": "text", "text": "何色？"}]}]}, self.config)
        self.assertEqual(images, [("png", fixture)])
        self.assertIn("何色？", messages[0]["content"])

    def test_bad_base64_image_is_rejected(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.normalise_messages({"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,invalid="}}]}]}, self.config)

    def test_busy_is_bounded(self):
        self.server.serial.acquire()
        try:
            status, data = self.request({"messages": [{"role": "user", "content": "hello"}]})
        finally:
            self.server.serial.release()
        self.assertEqual(status, 429)
        self.assertIn("bridge_busy", data)

    def test_disconnect_cancels_active_runner(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("POST", "/v1/chat/completions", json.dumps({"messages": [{"role": "user", "content": "wait"}], "stream": True}), {"Content-Type": "application/json", "Authorization": "Bearer " + self.server.local_token})
        response = connection.getresponse()
        response.readline()
        response.close()
        connection.close()
        self.assertTrue(self.runner.cancelled.wait(3))
        deadline = time.monotonic() + 3
        while self.server.serial.locked() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(self.server.serial.locked())

    def test_child_flags_exclude_context_and_tools(self):
        args = bridge.cli_arguments(self.config, bridge.ROOT / "empty", [])
        self.assertIn("--ephemeral", args)
        self.assertIn("--ignore-user-config", args)
        self.assertIn("project_doc_max_bytes=0", args)
        self.assertIn("memories.use_memories=false", args)
        self.assertIn("mcp_servers={}", args)
        self.assertIn("shell_tool", args)
        self.assertNotIn("OPENAI_API_KEY", bridge.child_environment())
        self.assertNotIn("CODEX_THREAD_ID", bridge.child_environment())

    def test_native_settings_apply_and_alias_stays_stable(self):
        status, data = self.request({"model": "gpt-6-luna", "reasoningEffort": "high"}, "/codex/settings")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["model"], "gpt-6-luna")
        self.assertEqual(self.server.request_config().reasoning_effort, "high")
        status, data = self.request({"model": "codex-default", "messages": [{"role": "user", "content": "hello"}]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["model"], "gpt-6-luna")

    def test_incompatible_reasoning_rejected_without_changing_selection(self):
        before = self.server.selection()
        status, data = self.request({"model": "gpt-6-luna", "reasoningEffort": "ultra"}, "/codex/settings")
        self.assertEqual(status, 422)
        self.assertIn("unsupported_reasoning_effort", data)
        self.assertEqual(self.server.selection()["model"], before["model"])
        self.assertFalse(self.server.settings_path.exists())

    def test_arbitrary_identifier_can_be_configured_but_not_shell_code(self):
        status, data = self.request({"model": "unlisted-model", "reasoningEffort": "low"}, "/codex/settings")
        self.assertEqual(status, 200)
        status, data = self.request({"model": "unlisted; command", "reasoningEffort": "low"}, "/codex/settings")
        self.assertEqual(status, 422)
        self.assertIn("unsupported_model", data)

    def test_local_bearer_required_for_completion_settings_and_shutdown(self):
        before = self.server.selection()
        for path, body in (("/v1/chat/completions", {"messages": [{"role": "user", "content": "hello"}]}),
                           ("/codex/settings", {"model": "codex-default", "reasoningEffort": "auto"}), ("/shutdown", {})):
            status, data = self.request(body, path, {"Authorization": "Bearer incorrect"})
            self.assertEqual(status, 401)
            self.assertIn("local_token_required", data)
        self.assertFalse(self.runner.calls)
        self.assertFalse(self.server.stopping.is_set())
        self.assertEqual(before, self.server.selection())

    def test_health_public_and_nonsecret_settings_private(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("GET", "/healthz")
        response = connection.getresponse()
        data = response.read().decode()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(data)["local_auth"], "bearer-v1")
        self.assertNotIn(self.server.local_token, data)
        self.assertNotIn("last_usage", data)
        connection.close()
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("GET", "/codex/settings")
        response = connection.getresponse()
        self.assertEqual(response.status, 401)
        response.read(); connection.close()

    def test_health_proves_token_possession_without_receiving_or_returning_token(self):
        nonce = "d" * 64
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("GET", "/healthz", headers={"X-AiNpc-Challenge": nonce})
        response = connection.getresponse(); raw = response.read().decode(); connection.close()
        self.assertEqual(response.status, 200)
        data = f"AiNpcCodexBridge/bearer-v1\n{self.server.server_port}\n{nonce}".encode("ascii")
        self.assertEqual(json.loads(raw)["local_auth_proof"], hmac.new(self.server.local_token.encode("ascii"), data, hashlib.sha256).hexdigest())
        self.assertNotIn(self.server.local_token, raw)

    def test_token_persists_without_auth_file_access(self):
        path = self.config.state_directory / "local-token.json"
        self.assertEqual(bridge.local_token(self.config.state_directory), self.server.local_token)
        self.assertEqual(len(json.loads(path.read_text())["token"]), 64)
        self.assertFalse((self.config.state_directory / "auth.json").exists())

    def test_rate_limit_is_before_runner(self):
        self.config.max_requests_per_minute = 1
        body = {"messages": [{"role": "user", "content": "hello"}]}
        self.assertEqual(self.request(body)[0], 200)
        status, data = self.request(body)
        self.assertEqual(status, 429)
        self.assertIn("bridge_rate_limit", data)
        self.assertEqual(len(self.runner.calls), 1)

    def test_connection_admission_is_bounded_before_headers(self):
        self.server.connection_slots.acquire()
        # Reserve every remaining slot, simulating slow clients before a request line.
        held = 1
        while self.server.connection_slots.acquire(blocking=False): held += 1
        try:
            connection = socket.create_connection(("127.0.0.1", self.server.server_port), timeout=2)
            self.assertIn(b"503 Service Unavailable", connection.recv(1024))
            connection.close()
        finally:
            for _ in range(held): self.server.connection_slots.release()

    def test_nonstring_image_url_is_cleanly_rejected(self):
        status, _ = self.request({"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": {"untrusted": "value"}}}]}]})
        self.assertEqual(status, 400)

    def test_nonstring_message_roles_return_a_bounded_client_error(self):
        for role in ([], {}, 42, None):
            with self.subTest(role=role):
                status, data = self.request({"messages": [{"role": role, "content": "fixture"}]})
                self.assertEqual(status, 400)
                self.assertIn("unsupported_message_role", data)
        self.assertFalse(self.runner.calls)

    def test_non_ascii_authorization_is_rejected_without_crashing_the_handler(self):
        status, data = self.request({"messages": [{"role": "user", "content": "fixture"}]},
                                    headers={"Authorization": "Bearer \u00e9"})
        self.assertEqual(status, 401)
        self.assertIn("local_token_required", data)
        self.assertFalse(self.runner.calls)

    def test_custom_home_keeps_the_shared_home_warning(self):
        for configured, expected in (("", "legacy-shared"), ("isolated", "dedicated"),
                                     (str(Path(self.temporary.name) / "custom-home"), "legacy-shared")):
            self.config.codex_home = configured
            connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
            connection.request("GET", "/healthz")
            response = connection.getresponse()
            self.assertEqual(json.loads(response.read())["instruction_home"], expected)
            connection.close()

    def test_invalid_saved_selection_fails_closed_without_rewriting_user_data(self):
        path = Path(self.temporary.name) / "invalid-selection.json"
        for raw in ("[]", "null", "{broken", " " * 16385):
            path.write_text(raw, encoding="utf-8")
            with self.assertRaises(bridge.BridgeError) as error:
                bridge.BridgeServer(self.config, self.runner, settings_path=path)
            self.assertEqual(error.exception.code, "invalid_saved_selection")
            self.assertEqual(path.read_text(encoding="utf-8"), raw)

    def test_auto_omits_model_and_effort_flags(self):
        args = bridge.cli_arguments(dataclasses.replace(self.config, model="", reasoning_effort="auto"), Path(self.temporary.name), [])
        self.assertNotIn("--model", args)
        self.assertFalse(any(item.startswith("model_reasoning_effort=") for item in args))

    def test_config_limits_reject_bool_numbers_and_oversized_limits(self):
        path = self.config.state_directory / "fixture-config.json"
        for values in ({"port": True}, {"max_connections": 1000}, {"max_request_bytes": -1}, {"max_text_chars": "1000"}, {"enable_images": "yes"}, {"max_images": 1.5}):
            path.write_text(json.dumps(values))
            with self.assertRaises(ValueError): bridge.Config.load(path)

    def test_dedicated_home_uses_its_own_auth_context_without_copying(self):
        self.config.codex_home = "isolated"
        expected = self.config.state_directory / "codex-home"
        self.assertEqual(Path(bridge.child_environment(self.config)["CODEX_HOME"]), expected)
        self.assertFalse(expected.exists())
        expected.mkdir()
        (expected / "AGENTS.md").write_text("fixture instructions that must never reach the model")
        with self.assertRaises(bridge.BridgeError) as error:
            bridge.require_clean_instruction_home(self.config)
        self.assertEqual(error.exception.code, "codex_home_instructions_detected_use_isolated_home")
        self.assertFalse((expected / "auth.json").exists())

    def test_api_key_and_agent_environment_never_reaches_cli(self):
        self.config.codex_home = "isolated"
        values = {"OPENAI_API_KEY":"dummy-not-a-real-key", "CODEX_API_KEY":"dummy-not-a-real-key", "OPENAI_BASE_URL":"https://untrusted.invalid", "CODEX_THREAD_ID":"fixture-parent", "CODEX_HOME":"fixture-wrong-home", "HTTPS_PROXY":"http://fixture.invalid:3128"}
        with patch.dict(bridge.os.environ, values):
            environment = bridge.child_environment(self.config)
        for name in ("OPENAI_API_KEY","CODEX_API_KEY","OPENAI_BASE_URL","CODEX_THREAD_ID"):
            self.assertNotIn(name, environment)
        self.assertEqual(environment["CODEX_HOME"], str(self.config.state_directory / "codex-home"))
        self.assertEqual(environment["HTTPS_PROXY"], values["HTTPS_PROXY"])

    def test_shared_home_global_instructions_are_rejected_metadata_only(self):
        shared = self.config.state_directory / "shared"
        shared.mkdir()
        (shared / "AGENTS.override.md").write_text("fixture only")
        with patch.dict(bridge.os.environ, {"CODEX_HOME": str(shared)}):
            with self.assertRaises(bridge.BridgeError): bridge.require_clean_instruction_home(self.config)

    def test_failure_codes_never_echo_cli_error_or_model_prompt(self):
        self.assertEqual(bridge.safe_failure('Reasoning effort unsupported: PRIVATE'), 'unsupported_reasoning_effort')
        self.assertEqual(bridge.safe_failure('Model not available PRIVATE'), 'codex_model_unavailable')

    def test_api_key_auth_mode_is_rejected(self):
        status = bridge.subprocess.CompletedProcess([], 0, "Logged in using an API key", "")
        with patch.object(bridge.subprocess, "run", return_value=status):
            self.assertFalse(bridge.check_chatgpt_auth(self.config))

    def test_request_snapshot_preserves_portable_state_and_cli_capabilities(self):
        self.config.disabled_features = ("shell_tool", "in_app_browser")
        snapshot = self.server.request_config()
        self.assertEqual(snapshot.state_directory, Path(self.temporary.name))
        self.assertEqual(snapshot.disabled_features, self.config.disabled_features)
        self.server.change_selection({"model": "codex-default", "reasoningEffort": "low"})
        self.assertTrue((Path(self.temporary.name) / "selection.json").is_file())

    def test_npm_windows_shim_resolves_to_native_codex(self):
        root = Path(self.temporary.name)
        shim = root / "codex.cmd"
        shim.write_text("fixture", encoding="utf-8")
        executable = root / "node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/codex/codex.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"fixture")
        self.assertEqual(bridge.resolve_codex_executable(str(shim), root), str(executable.resolve()))

    def test_unsupported_cli_is_rejected_before_a_server_can_start(self):
        result = bridge.subprocess.CompletedProcess([], 0, "--json --sandbox", "")
        with patch.object(bridge.subprocess, "run", return_value=result):
            with self.assertRaises(bridge.BridgeError) as error:
                bridge.inspect_cli(self.config)
        self.assertEqual(error.exception.code, "codex_cli_update_required")

    def test_cli_capability_check_disables_available_tool_features(self):
        help_text = "--ephemeral --ignore-user-config --ignore-rules --json --sandbox --strict-config"
        features = "shell_tool stable true\nin_app_browser stable true\ncode_mode_host stable true\nunknown_new_feature stable false\n"
        results = [bridge.subprocess.CompletedProcess([], 0, help_text, ""),
                   bridge.subprocess.CompletedProcess([], 0, features, "")]
        with patch.object(bridge.subprocess, "run", side_effect=results):
            bridge.inspect_cli(self.config)
        self.assertEqual(set(self.config.disabled_features), {"shell_tool", "in_app_browser", "code_mode_host"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
