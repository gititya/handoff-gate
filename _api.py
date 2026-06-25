"""Shared Anthropic API key lookup — env first, then macOS keychain."""
from __future__ import annotations

import os
import subprocess


def get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        key = subprocess.check_output(
            ["security", "find-generic-password", "-s", "ANTHROPIC_API_KEY", "-w"],
            text=True,
        ).strip()
        if key:
            return key
    except subprocess.CalledProcessError:
        pass
    raise RuntimeError(
        "ANTHROPIC_API_KEY not found in env or macOS keychain. "
        "Set it via: export ANTHROPIC_API_KEY=<key> or add to Keychain."
    )
