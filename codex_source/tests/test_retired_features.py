"""Capability inspection fixtures only; no CLI, login, network, or model runs."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "payload/game/red4ext/plugins/AiNpcCodexBridge"))
import bridge


class RetiredFeatures(unittest.TestCase):
    def test_deprecated_flags_are_not_sent_but_real_tools_are_disabled(self):
        names = ["shell_zsh_fork", "unified_exec_zsh_fork", "shell_tool", "unified_exec",
                 "code_mode", "code_mode_host", "browser_tool", "apps", "multi_agent",
                 "memories", "in_app_browser", "enable_mcp_apps", "unrelated_ui_option"]
        help_output = " ".join(["--ephemeral", "--ignore-user-config", "--ignore-rules", "--json", "--sandbox", "--strict-config"])
        responses = [SimpleNamespace(returncode=0, stdout=help_output),
                     SimpleNamespace(returncode=0, stdout="\n".join(name + " stable false" for name in names))]
        config = SimpleNamespace(codex_path="fixture-only", codex_home="")
        with patch.object(bridge.subprocess, "run", side_effect=responses) as run:
            bridge.inspect_cli(config)
        self.assertEqual(run.call_count, 2)
        self.assertFalse({"shell_zsh_fork", "unified_exec_zsh_fork"} & set(config.disabled_features))
        self.assertTrue(set(names[2:-1]).issubset(config.disabled_features))
        self.assertNotIn("unrelated_ui_option", config.disabled_features)


if __name__ == "__main__":
    unittest.main()
