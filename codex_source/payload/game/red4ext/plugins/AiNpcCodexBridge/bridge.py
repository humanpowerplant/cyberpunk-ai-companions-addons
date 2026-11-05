"""Loopback Chat Completions adapter for an existing Codex ChatGPT login.

No API keys, prompts, replies, or Codex event streams are written to logs.
Each request uses an ephemeral session and a read-only sandbox. Tool features
are restricted, not a claim that the upstream CLI exposes no native tools.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import collections
import dataclasses
import hmac
import hashlib
import ipaddress
import json
import os
import platform
import queue
import re
import secrets
import select
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
VERSION = "1.2.0-rc.2"
DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "apps", "plugins", "hooks", "multi_agent",
    "multi_agent_v2", "browser_use", "browser_use_external", "computer_use",
    "view_image", "image_generation", "code_mode", "code_mode_host", "memories",
    "skill_search", "skill_mcp_dependency_install", "shell_snapshot", "sleep_tool",
    "tool_suggest", "workspace_dependencies", "remote_plugin", "recommended_plugins",
)
DEVELOPER_INSTRUCTIONS = (
    "You are a stateless text completion backend for a fictional NPC conversation application. "
    "The user input is a JSON chat transcript, not a request to operate a computer or repository. "
    "Produce only the next assistant reply requested by that transcript. Respect its system and "
    "developer conversation instructions, character voice, language, and knowledge boundaries. "
    "Do not narrate your work or mention Codex. You have no tools: do not access files, commands, "
    "network, applications, memories, other chats, or external sources. Use only this transcript "
    "and its explicitly attached scene images. Do not claim to have performed real actions."
)
TOOL_ITEM_TYPES = {
    "command_execution", "file_change", "mcp_tool_call", "web_search", "tool_call",
    "function_call", "computer_call", "image_generation", "collab_tool_call",
}


def default_state_directory() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    return (Path(local) if local else Path.home() / ".local" / "state") / "AiNpcCodexBridge"


def resolve_codex_executable(value: str, relative_to: Path) -> str:
    """Resolve a native CLI, including the native binary behind npm's Windows shim."""
    candidate = os.path.expandvars(os.path.expanduser(value)) if value else shutil.which("codex.exe") or shutil.which("codex")
    if not candidate:
        raise ValueError("Codex executable not found")
    path = Path(candidate)
    if not path.is_absolute():
        path = relative_to / path
    path = path.resolve()
    if path.suffix.lower() in {".cmd", ".bat", ".ps1"}:
        npm = path.parent / "node_modules" / "@openai"
        arch = "arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "x64"
        target = "aarch64-pc-windows-msvc" if arch == "arm64" else "x86_64-pc-windows-msvc"
        for package in (npm / f"codex-win32-{arch}", npm / "codex/node_modules/@openai" / f"codex-win32-{arch}", npm / "codex"):
            matches = sorted(package.glob(f"vendor/{target}/codex/codex.exe"))
            if matches:
                return str(matches[0].resolve())
        raise ValueError("Native Codex executable not found behind npm shim")
    if not path.is_file() or (os.name == "nt" and path.suffix.lower() != ".exe"):
        raise ValueError("Codex executable not found")
    return str(path)


class BridgeError(Exception):
    def __init__(self, code: str, status: int = 502):
        super().__init__(code)
        self.code, self.status = code, status


@dataclasses.dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 17865
    codex_path: str = ""
    codex_home: str = ""
    model: str = ""
    reasoning_effort: str = "auto"
    timeout_seconds: float = 90
    queue_wait_seconds: float = 5
    max_request_bytes: int = 12 * 1024 * 1024
    max_text_chars: int = 250000
    max_images: int = 2
    max_image_bytes: int = 5 * 1024 * 1024
    enable_images: bool = True
    max_connections: int = 8
    max_requests_per_minute: int = 30
    max_output_chars: int = 100000
    state_directory: Path = dataclasses.field(default_factory=default_state_directory, init=False)
    disabled_features: tuple[str, ...] = dataclasses.field(default=DISABLED_FEATURES, init=False)

    @classmethod
    def load(cls, path: Path):
        if path.exists() and path.stat().st_size > 16384:
            raise ValueError("Configuration too large")
        raw = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
        if not isinstance(raw, dict) or set(raw) - {name for name, field in cls.__dataclass_fields__.items() if field.init}:
            raise ValueError("Unknown configuration keys")
        value = cls(**raw)
        if value.host != "127.0.0.1" or type(value.port) is not int or not 1024 <= value.port <= 65535:
            raise ValueError("The bridge must bind IPv4 loopback on an unprivileged port")
        if any(type(number) not in (int, float) for number in (value.timeout_seconds, value.queue_wait_seconds)) or not 5 <= value.timeout_seconds <= 180 or not 0 <= value.queue_wait_seconds <= 30:
            raise ValueError("Invalid request timeout")
        if value.reasoning_effort not in ("auto", "low", "medium", "high", "xhigh", "max", "ultra"):
            raise ValueError("Invalid reasoning effort")
        if not isinstance(value.model, str) or (value.model and not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value.model)):
            raise ValueError("Invalid model identifier")
        for field, lower, upper in (("max_request_bytes", 1024, 16 * 1024 * 1024),
                                    ("max_text_chars", 1024, 500000), ("max_images", 0, 4),
                                    ("max_image_bytes", 1024, 8 * 1024 * 1024),
                                    ("max_connections", 2, 16), ("max_requests_per_minute", 1, 120),
                                    ("max_output_chars", 1024, 200000)):
            if type(getattr(value, field)) is not int or not lower <= getattr(value, field) <= upper:
                raise ValueError("Invalid " + field)
        if type(value.enable_images) is not bool or not isinstance(value.codex_path, str) or not isinstance(value.codex_home, str):
            raise ValueError("Invalid configuration type")
        if value.codex_home and value.codex_home != "isolated":
            home = Path(os.path.expandvars(os.path.expanduser(value.codex_home)))
            value.codex_home = str((home if home.is_absolute() else path.parent / home).resolve())
        value.codex_path = resolve_codex_executable(value.codex_path, path.parent)
        return value


def local_token(directory: Path) -> str:
    """Private, per-user loopback credential. Never use or read Codex login files."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "local-token.json"
    if not path.exists():
        token = secrets.token_hex(32)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump({"schema": 1, "token": token}, output)
    try:
        if path.is_symlink() or path.stat().st_size > 1024:
            raise ValueError()
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if value.get("schema") != 1 or not isinstance(value.get("token"), str) or not re.fullmatch(r"[a-f0-9]{64}", value["token"]):
            raise ValueError()
        return value["token"]
    except (OSError, ValueError, AttributeError):
        raise BridgeError("invalid_local_token_file", 503) from None


def cli_home(config: Config) -> Path:
    if config.codex_home == "isolated":
        return config.state_directory / "codex-home"
    return Path(config.codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def require_clean_instruction_home(config: Config) -> None:
    """Metadata-only guard: global AGENTS are outside project_doc_max_bytes."""
    home = cli_home(config)
    if any((home / name).exists() for name in ("AGENTS.md", "AGENTS.override.md")):
        raise BridgeError("codex_home_instructions_detected_use_isolated_home", 503)


def instruction_home_mode(config: Config) -> str:
    # A pre-existing custom CODEX_HOME is not the dedicated home managed here.
    return "dedicated" if config.codex_home == "isolated" else "legacy-shared"


def child_environment(config: Config | None = None) -> dict[str, str]:
    """Retain Windows/auth paths and network routing, never inherited agent context/API keys."""
    allowed = {
        "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "PATHEXT", "USERPROFILE",
        "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "HOME",
        "CODEX_HOME", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY",
        "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    if config is not None and config.codex_home:
        env["CODEX_HOME"] = str(cli_home(config))
    env.update({"NO_COLOR": "1", "TERM": "dumb"})
    return env


def check_chatgpt_auth(config: Config) -> bool:
    """Use the CLI's status command only. Never open or parse credential files."""
    try:
        result = subprocess.run([config.codex_path, "login", "status"], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=15,
                                env=child_environment(config),
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except (OSError, subprocess.TimeoutExpired):
        return False
    status = result.stdout + result.stderr
    return result.returncode == 0 and "logged in using chatgpt" in status.lower()


def inspect_cli(config: Config) -> None:
    """Check required isolation flags locally; refuse an incompatible CLI before serving."""
    options = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace",
               "timeout": 15, "env": child_environment(config),
               "creationflags": subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0}
    try:
        help_result = subprocess.run([config.codex_path, "exec", "--help"], **options)
        features_result = subprocess.run([config.codex_path, "features", "list"], **options)
    except (OSError, subprocess.TimeoutExpired):
        raise BridgeError("codex_capability_check_failed", 503) from None
    required = ("--ephemeral", "--ignore-user-config", "--ignore-rules", "--json", "--sandbox", "--strict-config")
    if help_result.returncode or any(flag not in help_result.stdout for flag in required) or features_result.returncode:
        raise BridgeError("codex_cli_update_required", 503)
    available = {match.group(1) for line in features_result.stdout.splitlines()
                 if (match := re.match(r"^([a-z_][a-z0-9_]*)\s+.+\s+(?:true|false)\s*$", line))}
    if "shell_tool" not in available:
        raise BridgeError("codex_cli_update_required", 503)
    tool_prefixes = ("shell_", "unified_exec", "apps", "plugin", "hooks", "multi_agent", "browser_", "in_app_",
                     "computer_", "code_mode", "view_image", "image_generation", "memories", "skill_",
                     "sleep_tool", "tool_suggest", "workspace_dependencies", "remote_plugin", "recommended_plugins",
                     "agent_message", "artifact", "chronicle", "goals", "guardian_conversation_history", "send_message_to_user", "request_permissions", "default_mode_request_user_input", "token_budget", "current_time_reminder",
                     "deferred_executor", "standalone_web_search", "tool_call_mcp", "mcp_", "non_prefixed_mcp")
    # CLI 0.166 lists these retired flags but rejects even --disable for them.
    # They no longer control an executor. Keep actual dynamic tools disabled.
    retired_features = {"shell_zsh_fork", "unified_exec_zsh_fork"}
    config.disabled_features = tuple(sorted(name for name in available
        if name not in retired_features and
        (name in DISABLED_FEATURES or name in {"in_app_browser", "enable_mcp_apps"} or name.startswith(tool_prefixes))))


def model_catalog() -> list[dict]:
    """Only visible CLI catalog metadata, never account credentials or hidden models."""
    raw = json.loads((ROOT / "model_catalog.json").read_text(encoding="utf-8-sig"))
    models = []
    for row in raw.get("models", []):
        model_id = row.get("id", "")
        efforts = row.get("reasoning_efforts", [])
        if re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", model_id) and efforts:
            models.append({"id": model_id, "name": row.get("name", model_id), "reasoningEfforts": efforts})
    common = [effort for effort in ["low", "medium", "high", "xhigh", "max", "ultra"]
              if models and all(effort in row["reasoningEfforts"] for row in models)]
    for row in models:
        row["reasoningEfforts"] = ["auto"] + row["reasoningEfforts"]
    return [{"id": "codex-default", "name": "Codex CLI default", "reasoningEfforts": ["auto"] + (common or ["low"])}] + models


def validate_selection(model: str, effort: str, catalog: list[dict]) -> None:
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", model):
        raise BridgeError("unsupported_model", 422)
    supported = next((row for row in catalog if row["id"] == model), None)
    # The public catalog is advisory, never an entitlement or future-model allowlist.
    if effort not in (supported["reasoningEfforts"] if supported else ("auto", "low", "medium", "high", "xhigh", "max", "ultra")):
        raise BridgeError("unsupported_reasoning_effort", 422)


def cli_arguments(config: Config, cwd: Path, images: list[Path]) -> list[str]:
    args = [config.codex_path, "exec", "--strict-config", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "--json", "--color", "never", "--sandbox", "read-only",
            "--cd", str(cwd)]
    overrides = {
        "approval_policy": "never", "project_doc_max_bytes": 0,
        "project_doc_fallback_filenames": [], "memories.use_memories": False,
        "memories.generate_memories": False, "skills.include_instructions": False,
        "skills.bundled.enabled": False, "web_search": "disabled", "mcp_servers": {},
        "apps._default.enabled": False, "history.persistence": "none",
        "analytics.enabled": False, "developer_instructions": DEVELOPER_INSTRUCTIONS,
        "cloud.skills.enabled": False, "orchestrator.mcp.enabled": False,
        "include_environment_context": False, "include_apps_instructions": False,
        "include_collaboration_mode_instructions": False,
        "tools.update_plan.enabled": False, "tools.experimental_request_user_input.enabled": False,
        "agents.enabled": False,
    }
    if config.reasoning_effort != "auto":
        overrides["model_reasoning_effort"] = config.reasoning_effort
    for key, value in overrides.items():
        # TOML strings/booleans/arrays use the same spelling as these JSON values;
        # the sole table override is an empty TOML inline table.
        encoded = "{}" if value == {} else json.dumps(value, ensure_ascii=False)
        args += ["-c", f"{key}={encoded}"]
    for feature in config.disabled_features:
        args += ["--disable", feature]
    if config.model:
        args += ["--model", config.model]
    for image in images:
        args += ["--image", str(image)]
    return args + ["--", "-"]


def normalise_messages(body: dict, config: Config) -> tuple[list[dict], list[tuple[str, bytes]]]:
    if body.get("tools") or body.get("functions") or body.get("tool_choice") not in (None, "none"):
        raise BridgeError("tools_not_supported", 400)
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages or len(messages) > 300:
        raise BridgeError("invalid_messages", 400)
    result, images, characters = [], [], 0
    for message in messages:
        if not isinstance(message, dict) or not isinstance(message.get("role"), str) or message["role"] not in {"system", "developer", "user", "assistant"}:
            raise BridgeError("unsupported_message_role", 400)
        content = message.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts = []
            for part in content:
                if not isinstance(part, dict):
                    raise BridgeError("invalid_content_part", 400)
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    parts.append(part["text"])
                elif part.get("type") == "image_url":
                    if not config.enable_images:
                        raise BridgeError("images_disabled", 400)
                    if message["role"] != "user":
                        raise BridgeError("image_role_not_supported", 400)
                    spec = part.get("image_url", {})
                    url = spec.get("url") if isinstance(spec, dict) else None
                    match = re.fullmatch(r"data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\r\n]+)", url) if isinstance(url, str) else None
                    if not match:
                        raise BridgeError("only_embedded_base64_images_supported", 400)
                    if len(images) >= config.max_images or len(match[2]) > config.max_image_bytes * 4 // 3 + 8:
                        raise BridgeError("image_limit_exceeded", 413)
                    try:
                        data = base64.b64decode(match[2].replace("\r", "").replace("\n", ""), validate=True)
                    except (binascii.Error, ValueError):
                        raise BridgeError("invalid_base64_image", 400) from None
                    ext = "jpg" if match[1] in {"jpeg", "jpg"} else match[1]
                    valid = ((ext == "png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or
                             (ext == "jpg" and data.startswith(b"\xff\xd8\xff")) or
                             (ext == "webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP"))
                    if not valid or len(data) > config.max_image_bytes:
                        raise BridgeError("invalid_or_oversized_image", 400)
                    images.append((ext, data))
                    parts.append(f"[Scene image {len(images)} is attached to this request.]")
                else:
                    raise BridgeError("unsupported_content_part", 400)
            text = "\n".join(parts)
        else:
            raise BridgeError("invalid_message_content", 400)
        characters += len(text)
        if characters > config.max_text_chars:
            raise BridgeError("text_limit_exceeded", 413)
        result.append({"role": message["role"], "content": text})
    return result, images


def safe_failure(stderr: str) -> str:
    lower = stderr.lower()
    if "reasoning" in lower and any(word in lower for word in ("unsupported", "not supported", "invalid", "not allowed")):
        return "unsupported_reasoning_effort"
    if "model" in lower and any(word in lower for word in ("unsupported", "not supported", "not found", "does not exist", "not available", "not have access", "retired")):
        return "codex_model_unavailable"
    if any(word in lower for word in ["rate limit", "usage limit", "quota", "429"]):
        return "codex_usage_limit"
    if any(word in lower for word in ["not logged in", "unauthorized", "authentication", "401"]):
        return "codex_auth_required"
    if any(word in lower for word in ["network", "connection", "timed out", "dns", "certificate"]):
        return "codex_connection_failed"
    if "unexpected argument" in lower or "unknown feature" in lower or "error loading config" in lower:
        return "codex_configuration_failed"
    return "codex_process_failed"


def terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        # Only this bridge-created PID and descendants; never identify by executable name.
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/taskkill.exe"
        try:
            subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
                           creationflags=subprocess.CREATE_NO_WINDOW, check=False)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
    else:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


class CodexRunner:
    def __init__(self, config: Config):
        self.config = config

    def run(self, messages: list[dict], images: list[tuple[str, bytes]], cancel: threading.Event,
            on_text: Callable[[str], None]) -> dict:
        start = time.monotonic()
        if cancel.is_set():
            raise BridgeError("request_cancelled", 499)
        require_clean_instruction_home(self.config)
        authenticated = check_chatgpt_auth(self.config)
        # CLI status can take up to its own timeout. Do not start a generation
        # after the requester disconnected or its total deadline already passed.
        if cancel.is_set():
            raise BridgeError("request_cancelled", 499)
        if time.monotonic() - start > self.config.timeout_seconds:
            raise BridgeError("codex_timeout", 504)
        if not authenticated:
            raise BridgeError("chatgpt_login_required", 503)
        work_root = self.config.state_directory / "work"
        work_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="turn-", dir=work_root) as temporary:
            cwd = Path(temporary)
            paths = []
            for index, (extension, data) in enumerate(images):
                image = cwd / f"scene-{index}.{extension}"
                image.write_bytes(data)
                paths.append(image)
            args = cli_arguments(self.config, cwd, paths)
            events: queue.Queue = queue.Queue(maxsize=128)
            output_overflow = threading.Event()
            reader_stop = threading.Event()
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            try:
                process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, cwd=cwd, env=child_environment(self.config),
                                           text=True, encoding="utf-8", errors="replace",
                                           creationflags=flags, bufsize=1)
            except OSError:
                raise BridgeError("codex_launch_failed") from None

            def drain(stream, label):
                try:
                    while not cancel.is_set() and not reader_stop.is_set():
                        line = stream.readline(1048577)
                        if not line:
                            break
                        if len(line) > 1048576:
                            output_overflow.set()
                            break
                        while not cancel.is_set() and not reader_stop.is_set():
                            try:
                                events.put((label, line), timeout=0.1)
                                break
                            except queue.Full:
                                pass
                finally:
                    while not cancel.is_set() and not reader_stop.is_set():
                        try:
                            events.put((label + "_eof", None), timeout=0.1)
                            break
                        except queue.Full:
                            pass

            def supply_input():
                try:
                    process.stdin.write(json.dumps({"messages": messages}, ensure_ascii=False))
                    process.stdin.close()
                except (OSError, ValueError):
                    while not cancel.is_set() and not reader_stop.is_set():
                        try:
                            events.put(("stdin_error", None), timeout=0.1)
                            break
                        except queue.Full:
                            pass

            threads = [threading.Thread(target=drain, args=(process.stdout, "stdout"), daemon=True),
                       threading.Thread(target=drain, args=(process.stderr, "stderr"), daemon=True),
                       threading.Thread(target=supply_input, daemon=True)]
            for thread in threads:
                thread.start()
            stderr, texts, event_types, usage = "", [], set(), None
            diagnostics = set()
            done = set()
            try:
                while len(done) < 2:
                    if output_overflow.is_set():
                        raise BridgeError("codex_output_limit")
                    if cancel.is_set():
                        raise BridgeError("request_cancelled", 499)
                    if time.monotonic() - start > self.config.timeout_seconds:
                        raise BridgeError("codex_timeout", 504)
                    try:
                        label, line = events.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if label == "stdin_error":
                        raise BridgeError("codex_input_failed")
                    if label.endswith("_eof"):
                        done.add(label)
                    elif label == "stderr":
                        stderr = (stderr + line)[-16384:]
                    else:
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        event_types.add(event.get("type", "unknown"))
                        item = event.get("item", {})
                        if item.get("type") == "error":
                            message = item.get("message", "")
                            if isinstance(message, str) and message.startswith("Code Mode is unavailable because code-mode host is disabled."):
                                diagnostics.add("code_mode_disabled")
                                continue
                            raise BridgeError(safe_failure(str(message)))
                        if item and item.get("type") not in {"agent_message", "reasoning"}:
                            kind = str(item.get("type", "missing"))
                            safe_kind = kind if re.fullmatch(r"[a-z_]{1,60}", kind) else "unknown"
                            raise BridgeError("unexpected_item_" + safe_kind)
                        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                            if item.get("phase") == "commentary":
                                continue
                            text = item.get("text", "")
                            if isinstance(text, str) and text.strip():
                                if len(text) + sum(map(len, texts)) > self.config.max_output_chars or len(texts) >= 64:
                                    raise BridgeError("codex_output_limit")
                                texts.append(text)
                                on_text(text)
                        elif event.get("type") == "turn.completed":
                            usage = event.get("usage")
                        elif event.get("type") in {"turn.failed", "error"}:
                            # Event errors may include upstream payloads; return a fixed code only.
                            raise BridgeError("codex_turn_failed")
                exit_code = process.wait(timeout=5)
                if exit_code != 0:
                    raise BridgeError(safe_failure(stderr))
                if not texts:
                    raise BridgeError("codex_empty_reply")
                return {"text": "\n".join(texts), "elapsed_ms": round((time.monotonic() - start) * 1000),
                        "usage": usage, "event_types": sorted(event_types), "tool_events": 0,
                        "model": self.config.model or "codex-default", "images": len(images),
                        "diagnostics": sorted(diagnostics)}
            finally:
                reader_stop.set()
                terminate_process(process)
                for thread in threads:
                    thread.join(timeout=2)
                for stream in [process.stdin, process.stdout, process.stderr]:
                    try:
                        stream.close()
                    except OSError:
                        pass


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, config: Config, runner=None, settings_path: Path | None = None):
        self.config = config
        self.local_token = local_token(config.state_directory)
        self.connection_slots = threading.BoundedSemaphore(config.max_connections)
        self.rate_lock = threading.Lock()
        self.admissions = collections.deque()
        self.runner = runner
        self.catalog = model_catalog()
        self.settings_path = settings_path or config.state_directory / "selection.json"
        self.settings_lock = threading.Lock()
        self.selected_model = config.model or "codex-default"
        self.selected_effort = config.reasoning_effort
        if self.settings_path.exists():
            try:
                if self.settings_path.is_symlink() or self.settings_path.stat().st_size > 16384:
                    raise ValueError()
                saved = json.loads(self.settings_path.read_text(encoding="utf-8-sig"))
                if not isinstance(saved, dict):
                    raise ValueError()
            except (OSError, ValueError):
                raise BridgeError("invalid_saved_selection", 503) from None
            self.selected_model = saved.get("model", self.selected_model)
            self.selected_effort = saved.get("reasoningEffort", self.selected_effort)
        validate_selection(self.selected_model, self.selected_effort, self.catalog)
        self.serial = threading.Lock()
        self.stopping = threading.Event()
        self.stats_lock = threading.Lock()
        self.stats = {"completed": 0, "failed": 0, "active": False, "last_code": None,
                      "last_elapsed_ms": None, "last_usage": None}
        super().__init__((config.host, config.port), Handler)

    def get_request(self):
        connection, address = super().get_request()
        # Applies before the first request line and headers are parsed (slowloris bound).
        connection.settimeout(5)
        return connection, address

    def process_request(self, request, client_address):
        if not self.connection_slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connection_slots.release()

    def admit_completion(self):
        with self.rate_lock:
            now = time.monotonic()
            while self.admissions and self.admissions[0] <= now - 60:
                self.admissions.popleft()
            if len(self.admissions) >= self.config.max_requests_per_minute:
                raise BridgeError("bridge_rate_limit", 429)
            self.admissions.append(now)

    def selection(self, include_catalog=False):
        with self.settings_lock:
            result = {"status": "ok", "model": self.selected_model, "reasoningEffort": self.selected_effort,
                      "configuredModel": self.config.model or "codex-default",
                      "appliesTo": "next-request", "active": self.serial.locked()}
        if include_catalog:
            result["models"] = self.catalog
            result["catalogNote"] = "Catalog membership does not prove per-model account entitlement."
        return result

    def request_config(self):
        with self.settings_lock:
            config = dataclasses.replace(self.config,
                                         model="" if self.selected_model == "codex-default" else self.selected_model,
                                         reasoning_effort=self.selected_effort)
            config.state_directory = self.config.state_directory
            config.disabled_features = self.config.disabled_features
            return config

    def change_selection(self, body):
        if not isinstance(body, dict) or set(body) != {"model", "reasoningEffort"} or not all(isinstance(value, str) for value in body.values()):
            raise BridgeError("invalid_settings_request", 400)
        validate_selection(body["model"], body["reasoningEffort"], self.catalog)
        with self.settings_lock:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.settings_path.with_name(self.settings_path.name + "." + uuid.uuid4().hex + ".tmp")
            try:
                temporary.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
                os.replace(temporary, self.settings_path)
            except OSError:
                raise BridgeError("settings_save_failed", 500) from None
            finally:
                temporary.unlink(missing_ok=True)
            self.selected_model, self.selected_effort = body["model"], body["reasoningEffort"]
        return self.selection()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "CodexCompanionBridge/1"

    def log_message(self, *_args):
        pass

    def reply_json(self, status: int, value: dict):
        encoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)
        self.close_connection = True

    def allowed(self):
        host = self.headers.get("Host", "").lower()
        origin = self.headers.get("Origin")
        valid_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        return len(self.headers.get_all("Host", [])) == 1 and ipaddress.ip_address(self.client_address[0]).is_loopback and host in valid_hosts and (
            origin is None or origin in {"http://" + entry for entry in valid_hosts})

    def authenticated(self):
        values = self.headers.get_all("Authorization", [])
        if len(values) != 1:
            return False
        try:
            candidate = values[0].encode("ascii")
        except UnicodeEncodeError:
            return False
        return hmac.compare_digest(candidate, ("Bearer " + self.server.local_token).encode("ascii"))

    def do_GET(self):
        if not self.allowed():
            return self.reply_json(403, {"error": {"code": "loopback_only"}})
        if self.path == "/healthz":
            challenge = self.headers.get("X-AiNpc-Challenge")
            if challenge is not None and (len(self.headers.get_all("X-AiNpc-Challenge", [])) != 1 or not re.fullmatch(r"[a-f0-9]{64}", challenge)):
                return self.reply_json(400, {"error": {"code": "invalid_local_challenge"}})
            proof = {}
            if challenge is not None:
                data = f"AiNpcCodexBridge/bearer-v1\n{self.server.server_port}\n{challenge}".encode("ascii")
                proof["local_auth_proof"] = hmac.new(self.server.local_token.encode("ascii"), data, hashlib.sha256).hexdigest()
            selection = self.server.selection()
            return self.reply_json(200, {"status": "ok", "service": "codex-companion-bridge", "version": 1,
                                         "local_auth": "bearer-v1",
                                         "instruction_home": instruction_home_mode(self.server.config),
                                         "auth_mode": "chatgpt", "model": selection["model"],
                                         "reasoningEffort": selection["reasoningEffort"],
                                         "images": self.server.config.enable_images, **proof})
        if not self.authenticated():
            return self.reply_json(401, {"error": {"code": "local_token_required"}})
        if self.path == "/codex/settings":
            return self.reply_json(200, self.server.selection(include_catalog=True))
        if self.path in {"/v1/models", "/models"}:
            return self.reply_json(200, {"object": "list", "data": [{"id": row["id"], "object": "model", "owned_by": "local-codex-cli"} for row in self.server.catalog]})
        return self.reply_json(404, {"error": {"code": "not_found"}})

    def do_POST(self):
        if not self.allowed():
            return self.reply_json(403, {"error": {"code": "loopback_only"}})
        if not self.authenticated():
            return self.reply_json(401, {"error": {"code": "local_token_required"}})
        if self.path != "/shutdown" and (len(self.headers.get_all("Content-Length", [])) != 1 or self.headers.get_content_type() != "application/json"):
            return self.reply_json(400, {"error": {"code": "invalid_json_request"}})
        if self.path == "/shutdown":
            self.server.stopping.set()
            self.reply_json(200, {"status": "stopping"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path == "/codex/settings":
            try:
                if self.headers.get("Transfer-Encoding"):
                    raise BridgeError("invalid_settings_request", 400)
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1024:
                    raise BridgeError("invalid_settings_request", 400)
                self.connection.settimeout(5)
                body = json.loads(self.rfile.read(size))
                return self.reply_json(200, self.server.change_selection(body))
            except (ValueError, socket.timeout):
                return self.reply_json(400, {"error": {"code": "invalid_settings_request"}})
            except BridgeError as error:
                return self.reply_json(error.status, {"error": {"code": error.code}})
        if self.path not in {"/v1/chat/completions", "/chat/completions"}:
            return self.reply_json(404, {"error": {"code": "not_found"}})
        cancel, sent_headers = threading.Event(), False
        locked = False
        try:
            if self.headers.get("Transfer-Encoding"):
                raise BridgeError("chunked_request_not_supported", 400)
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= self.server.config.max_request_bytes:
                raise BridgeError("request_size_limit", 413)
            self.connection.settimeout(10)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise BridgeError("incomplete_request", 400)
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise BridgeError("invalid_request", 400)
            messages, images = normalise_messages(body, self.server.config)
            self.server.admit_completion()
            locked = self.server.serial.acquire(timeout=self.server.config.queue_wait_seconds)
            if not locked:
                raise BridgeError("bridge_busy", 429)
            request_config = self.server.request_config()
            model = body.get("model")
            if model not in (None, "", "codex-default", request_config.model):
                raise BridgeError("model_does_not_match_bridge_configuration", 400)
            with self.server.stats_lock:
                self.server.stats["active"] = True
            stream = body.get("stream") is True
            completion_id, created = "chatcmpl-" + uuid.uuid4().hex, int(time.time())
            chosen_model = request_config.model or "codex-default"

            def chunk(delta, reason=None):
                return {"id": completion_id, "object": "chat.completion.chunk", "created": created,
                        "model": chosen_model, "choices": [{"index": 0, "delta": delta, "finish_reason": reason}]}

            def sse(value):
                payload = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                self.wfile.write(("data: " + payload + "\n\n").encode("utf-8"))
                self.wfile.flush()

            result_queue: queue.Queue = queue.Queue(maxsize=66)
            def publish(value):
                while not cancel.is_set():
                    try:
                        result_queue.put(value, timeout=0.1)
                        return
                    except queue.Full:
                        pass
            def run():
                try:
                    runner = self.server.runner or CodexRunner(request_config)
                    result = runner.run(messages, images, cancel, lambda text: publish(("text", text)))
                    publish(("done", result))
                except BridgeError as error:
                    publish(("error", error))
                except Exception:
                    publish(("error", BridgeError("internal_runner_error")))

            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-store")
                self.send_header("Connection", "close")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()
                sent_headers = True
                sse(chunk({"role": "assistant"}))
            worker = threading.Thread(target=run, daemon=True)
            worker.start()
            last_ping = time.monotonic()
            while True:
                try:
                    label, value = result_queue.get(timeout=0.25)
                except queue.Empty:
                    if self.server.stopping.is_set():
                        cancel.set()
                        raise BridgeError("bridge_stopping", 503)
                    if select.select([self.connection], [], [], 0)[0]:
                        if self.connection.recv(1, socket.MSG_PEEK) == b"":
                            cancel.set()
                            raise BridgeError("request_cancelled", 499)
                    # A heartbeat detects a disconnected streaming client and interrupts Codex.
                    if stream and time.monotonic() - last_ping >= 3:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_ping = time.monotonic()
                    continue
                if label == "text":
                    if stream:
                        sse(chunk({"content": value}))
                elif label == "error":
                    raise value
                else:
                    result = value
                    break
            with self.server.stats_lock:
                self.server.stats.update({"completed": self.server.stats["completed"] + 1,
                                          "last_code": "ok", "last_elapsed_ms": result.get("elapsed_ms"),
                                          "last_usage": result.get("usage")})
            if stream:
                sse(chunk({}, "stop"))
                sse("[DONE]")
            else:
                self.reply_json(200, {"id": completion_id, "object": "chat.completion", "created": created,
                                      "model": chosen_model, "choices": [{"index": 0, "message": {
                                          "role": "assistant", "content": result["text"]}, "finish_reason": "stop"}],
                                      "usage": result.get("usage")})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout):
            cancel.set()
        except (ValueError, json.JSONDecodeError):
            if not sent_headers:
                self.reply_json(400, {"error": {"code": "invalid_json_request", "message": "Invalid JSON request"}})
        except BridgeError as error:
            cancel.set()
            with self.server.stats_lock:
                self.server.stats.update({"failed": self.server.stats["failed"] + 1, "last_code": error.code})
            if sent_headers:
                try:
                    sse({"error": {"code": error.code, "message": error.code}})
                    sse("[DONE]")
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout):
                    pass
            else:
                self.reply_json(error.status, {"error": {"code": error.code, "message": error.code}})
        finally:
            cancel.set()
            # Keep serial ownership until a disconnected request has actually stopped its child.
            if "worker" in locals():
                worker.join(timeout=15)
            if locked:
                def release():
                    with self.server.stats_lock:
                        self.server.stats["active"] = False
                    self.server.serial.release()
                if "worker" in locals() and worker.is_alive():
                    def release_when_stopped():
                        worker.join()
                        release()
                    threading.Thread(target=release_when_stopped, daemon=True).start()
                else:
                    release()
            self.close_connection = True


class WindowsParentLifeline:
    """Keep one process handle so PID reuse cannot keep an automatic server alive."""
    def __init__(self, pid: int):
        if os.name != "nt" or not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
            raise ValueError("Invalid automatic-service parent")
        import ctypes
        from ctypes import wintypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only
        if not self.handle:
            raise OSError("The automatic-service parent has already ended")

    def wait(self, milliseconds=250):
        result = self.kernel.WaitForSingleObject(self.handle, milliseconds)
        if result == 0:
            return True
        if result == 258:  # WAIT_TIMEOUT
            return False
        raise OSError("Could not observe the automatic-service parent")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def watch_parent(server, parent):
    while not server.stopping.is_set():
        try:
            ended = parent.wait(250)
        except OSError:
            ended = True
        if ended:
            server.stopping.set()
            server.shutdown()
            return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=default_state_directory())
    parser.add_argument("--config", type=Path)
    parser.add_argument("--check", action="store_true", help="Check CLI capabilities and login locally; do not serve or generate text")
    parser.add_argument("--parent-pid", type=int, help="Automatically stop when the owning conversation service ends")
    args = parser.parse_args()
    parent, watcher = None, None
    try:
        if args.parent_pid is not None and not args.check:
            parent = WindowsParentLifeline(args.parent_pid)
        config = Config.load(args.config or args.data_dir / "config.json")
        config.state_directory = args.data_dir.resolve()
        if config.codex_home:
            cli_home(config).mkdir(parents=True, exist_ok=True)
        require_clean_instruction_home(config)
        inspect_cli(config)
        if not check_chatgpt_auth(config):
            raise BridgeError("chatgpt_login_required", 503)
        if args.check:
            print(json.dumps({"status": "ok", "version": VERSION, "auth_mode": "chatgpt",
                              "instruction_home": instruction_home_mode(config),
                              "disabled_feature_count": len(config.disabled_features)}), flush=True)
            return
        server = BridgeServer(config)
    except (ValueError, TypeError, OSError, BridgeError) as error:
        if parent:
            parent.close()
        code = error.code if isinstance(error, BridgeError) else "invalid_configuration_or_cli_path"
        print(json.dumps({"event": "startup_refused", "code": code}), flush=True)
        raise SystemExit(3)
    print(json.dumps({"event": "ready", "bind": f"{config.host}:{config.port}",
                      "model": config.model or "codex-default", "images": config.enable_images,
                      "auth_mode_chatgpt": True}), flush=True)
    try:
        if parent:
            watcher = threading.Thread(target=watch_parent, args=(server, parent), daemon=True)
            watcher.start()
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.stopping.set()
        if watcher:
            watcher.join(timeout=1)
        if parent:
            parent.close()
        if server.serial.acquire(timeout=20):
            server.serial.release()
        server.server_close()


if __name__ == "__main__":
    main()
