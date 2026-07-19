#!/usr/bin/env python3
"""Validate SlashPack plugin manifests.

Usage: validate.py [file ...]        (default: every JSON file in plugins/)

Checks, without external dependencies:
  - JSON parses; required fields, types, patterns (subset of the JSON schema)
  - filename equals the manifest id
  - command ids unique within the pack
  - shell commands contain no known-dangerous patterns
  - plugin ids unique across the whole registry
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"

ID_RE = re.compile(r"^[a-z0-9]+(\.[a-z0-9-]+)+$")
CMD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
VERSION_RE = re.compile(r"^\d+(\.\d+){0,2}$")
KINDS = {"ai", "shell", "url"}

# Patterns that get a shell command auto-rejected. Review still happens on top.
DANGEROUS = [
    (re.compile(r"\brm\s+(-\w*\s+)*-\w*[rf]"), "rm -rf style deletion"),
    (re.compile(r"\bsudo\b"), "sudo"),
    (re.compile(r"curl[^|;&]*\|\s*(ba)?sh"), "curl | sh"),
    (re.compile(r"wget[^|;&]*\|\s*(ba)?sh"), "wget | sh"),
    (re.compile(r"\bmkfs\b|\bdiskutil\s+erase"), "disk formatting"),
    (re.compile(r"\bdd\s+if="), "raw disk write (dd)"),
    (re.compile(r">\s*/dev/"), "writing to device files"),
    (re.compile(r"\bchmod\s+(-\w+\s+)*777"), "chmod 777"),
    (re.compile(r"\b(launchctl|systemsetup|csrutil|spctl)\b"), "system configuration"),
    (re.compile(r"\bosascript\b.*(System Events|keystroke)"), "UI scripting"),
    (re.compile(r"(^|[^A-Za-z])(:\(\)\s*\{)"), "fork bomb"),
    (re.compile(r"\bdefaults\s+write\s+/Library"), "global defaults write"),
    (re.compile(r"~/(\.ssh|\.aws|\.gnupg|Library/Keychains)"), "credential paths"),
]


def fail(errors, path, msg):
    errors.append(f"{path.name}: {msg}")


def check_str(errors, path, obj, key, pattern=None, max_len=None, required=True):
    val = obj.get(key)
    if val is None:
        if required:
            fail(errors, path, f"missing required field '{key}'")
        return
    if not isinstance(val, str) or (required and not val.strip()):
        fail(errors, path, f"'{key}' must be a non-empty string")
        return
    if pattern and not pattern.match(val):
        fail(errors, path, f"'{key}' value {val!r} doesn't match the required format")
    if max_len and len(val) > max_len:
        fail(errors, path, f"'{key}' is longer than {max_len} characters")


def validate_file(path: Path, errors: list):
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        fail(errors, path, f"invalid JSON: {e}")
        return None
    if not isinstance(pack, dict):
        fail(errors, path, "manifest must be a JSON object")
        return None

    if pack.get("schema") != 1:
        fail(errors, path, "'schema' must be 1")
    check_str(errors, path, pack, "id", ID_RE, 80)
    check_str(errors, path, pack, "name", max_len=60)
    check_str(errors, path, pack, "author", max_len=60)
    check_str(errors, path, pack, "version", VERSION_RE)
    check_str(errors, path, pack, "description", max_len=200)
    check_str(errors, path, pack, "minAppVersion", VERSION_RE, required=False)

    if pack.get("id") and path.stem != pack["id"]:
        fail(errors, path, f"filename must be '{pack['id']}.json'")

    commands = pack.get("commands")
    if not isinstance(commands, list) or not commands:
        fail(errors, path, "'commands' must be a non-empty array")
        return pack
    if len(commands) > 30:
        fail(errors, path, "at most 30 commands per pack")

    seen = set()
    for i, cmd in enumerate(commands):
        if not isinstance(cmd, dict):
            fail(errors, path, f"commands[{i}] must be an object")
            continue
        check_str(errors, path, cmd, "id", CMD_ID_RE, 60)
        check_str(errors, path, cmd, "name", max_len=60)
        check_str(errors, path, cmd, "body", max_len=4000)
        cid = cmd.get("id")
        if cid in seen:
            fail(errors, path, f"duplicate command id '{cid}'")
        seen.add(cid)
        kind = cmd.get("kind")
        if kind not in KINDS:
            fail(errors, path, f"commands[{i}].kind must be one of {sorted(KINDS)}")
        body = cmd.get("body") or ""
        if kind == "shell":
            for pattern, label in DANGEROUS:
                if pattern.search(body):
                    fail(errors, path, f"command '{cid}': shell body rejected ({label})")
        if kind == "url" and not body.startswith(("https://", "http://")):
            fail(errors, path, f"command '{cid}': url body must start with http(s)://")
    return pack


def main(argv):
    paths = [Path(p) for p in argv] or sorted(PLUGINS.glob("*.json"))
    if not paths:
        print("no manifests found")
        return 0
    errors, ids = [], {}
    for path in paths:
        pack = validate_file(path, errors)
        if pack and pack.get("id"):
            if pack["id"] in ids:
                errors.append(f"{path.name}: duplicate plugin id '{pack['id']}' (also in {ids[pack['id']]})")
            ids[pack["id"]] = path.name

    if errors:
        print(f"FAILED — {len(errors)} problem(s):")
        for e in errors:
            print(f"  • {e}")
        return 1
    print(f"OK — {len(paths)} manifest(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
