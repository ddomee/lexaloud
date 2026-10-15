"""Tests for config.toml loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from lexaloud.config import Config, load_config, validate_local_tts_endpoint


def test_load_config_missing_file_returns_defaults(tmp_path: Path):
    cfg = load_config(tmp_path / "nonexistent.toml")
    assert isinstance(cfg, Config)
    assert cfg.capture.max_bytes == 200 * 1024
    assert cfg.daemon.host == "127.0.0.1"
    assert cfg.daemon.port == 5487
    assert cfg.provider.endpoint == "http://127.0.0.1:8880/v1/audio/speech"
    assert cfg.provider.model == "kokoro"
    assert cfg.provider.timeout_s == 60.0
    assert cfg.provider.voice == "af_heart"
    assert cfg.provider.lang == "en-us"
    assert cfg.provider.speed == 1.0
    assert cfg.preprocessor.strip_numeric_bracket_citations is True
    assert cfg.preprocessor.strip_parenthetical_citations is False


def test_load_config_speed_override(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[provider]
voice = "af_bella"
speed = 1.15
""".strip()
    )
    cfg = load_config(path)
    assert cfg.provider.voice == "af_bella"
    assert cfg.provider.speed == 1.15
    # Unchanged
    assert cfg.provider.lang == "en-us"


def test_load_config_partial_override(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[daemon]
port = 9999

[provider]
voice = "bf_emma"
""".strip()
    )
    cfg = load_config(path)
    assert cfg.daemon.port == 9999
    # Unchanged defaults
    assert cfg.daemon.host == "127.0.0.1"
    assert cfg.provider.voice == "bf_emma"
    assert cfg.provider.lang == "en-us"


def test_load_config_unknown_keys_ignored(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[daemon]
nonexistent_key = "value"
port = 8080
""".strip()
    )
    # Should not raise, should pick up known key and ignore the other.
    cfg = load_config(path)
    assert cfg.daemon.port == 8080


def test_load_config_loads_preprocessor_section(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[preprocessor]
strip_parenthetical_citations = true
""".strip()
    )
    cfg = load_config(path)
    assert cfg.preprocessor.strip_parenthetical_citations is True


def test_load_config_capture_section(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[capture]
max_bytes = 1000
subprocess_timeout_s = 5.0
""".strip()
    )
    cfg = load_config(path)
    assert cfg.capture.max_bytes == 1000
    assert cfg.capture.subprocess_timeout_s == 5.0


def test_validate_local_tts_endpoint_accepts_ipv4_and_ipv6_loopback():
    assert validate_local_tts_endpoint("http://127.0.0.1:8880/v1/audio/speech")
    assert validate_local_tts_endpoint("http://[::1]:8880/v1/audio/speech")


@pytest.mark.parametrize("endpoint", ["http://localhost:8880", "https://127.0.0.1", "http://10.0.0.1"])
def test_validate_local_tts_endpoint_rejects_non_loopback_or_hostname(endpoint: str):
    with pytest.raises(ValueError, match="literal loopback"):
        validate_local_tts_endpoint(endpoint)
