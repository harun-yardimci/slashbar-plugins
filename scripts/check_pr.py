#!/usr/bin/env python3
"""PR-level checks, run by CI on top of validate.py.

Usage: check_pr.py --base <dir-with-base-checkout> --author <github-login>

Compares the PR's plugins/ against the base branch:
  - UPDATE of an existing plugin → PR author must match owners.json on base
    (prevents hijacking someone else's plugin), and version must increase.
  - NEW plugin → head owners.json must map the id to the PR author.
  - owners.json and plugins/ must stay consistent (every id owned, no orphans).
  - Any shell command in a new/changed manifest is highlighted in the job
    summary — merges are manual, this is the "look here before merging" signal.

Exit code 1 = don't merge without a maintainer decision.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_packs(root: Path):
    packs = {}
    for path in sorted((root / "plugins").glob("*.json")):
        try:
            packs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass  # validate.py already reports parse errors
    return packs


def load_owners(root: Path):
    path = root / "owners.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def version_tuple(v):
    return tuple(int(x) for x in str(v).split(".") if x.isdigit())


def summary(line):
    print(line)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="checkout of the base branch")
    ap.add_argument("--author", required=True, help="PR author's GitHub login")
    args = ap.parse_args()

    base_root = Path(args.base)
    author = args.author.lower()

    head_packs = load_packs(ROOT)
    base_packs = load_packs(base_root)
    head_owners = {k: str(v).lower() for k, v in load_owners(ROOT).items()}
    base_owners = {k: str(v).lower() for k, v in load_owners(base_root).items()}

    errors = []
    shell_flags = []

    # owners.json ↔ plugins/ consistency on the head.
    for pid in head_packs:
        if pid not in head_owners:
            errors.append(f"'{pid}' has no entry in owners.json")
    for pid in head_owners:
        if pid not in head_packs:
            errors.append(f"owners.json entry '{pid}' has no manifest in plugins/")

    for pid, pack in head_packs.items():
        base_pack = base_packs.get(pid)
        changed = base_pack != pack

        if base_pack is None:
            # New plugin: the same PR must register the author as its owner.
            if head_owners.get(pid) != author:
                errors.append(
                    f"new plugin '{pid}': owners.json must map it to the PR author "
                    f"'{author}' (found: {head_owners.get(pid)!r})")
        elif changed:
            # Update: only the recorded owner may change it.
            owner = base_owners.get(pid)
            if owner != author:
                errors.append(
                    f"'{pid}' is owned by '{owner}' but this PR is from '{author}' "
                    f"— only the owner may update it")
            if version_tuple(pack.get("version", "0")) <= version_tuple(base_pack.get("version", "0")):
                errors.append(
                    f"'{pid}': version must increase "
                    f"({base_pack.get('version')} → {pack.get('version')})")

        # Ownership transfers need a maintainer, never an automatic pass.
        if base_pack is not None and base_owners.get(pid) != head_owners.get(pid):
            errors.append(
                f"'{pid}': ownership change ({base_owners.get(pid)} → {head_owners.get(pid)}) "
                f"requires a maintainer")

        if (base_pack is None or changed) and any(
                c.get("kind") == "shell" for c in pack.get("commands", []) if isinstance(c, dict)):
            shell_flags.append(pid)

    # Deleting someone else's plugin also needs the owner or a maintainer.
    for pid in base_packs:
        if pid not in head_packs and base_owners.get(pid) != author:
            errors.append(f"'{pid}' was removed but the PR author is not its owner")

    if shell_flags:
        summary("⚠️ **SHELL COMMANDS — manual review required** in: "
                + ", ".join(f"`{p}`" for p in shell_flags)
                + ". Read every command body before merging.")

    if errors:
        summary("❌ **PR checks failed:**")
        for e in errors:
            summary(f"- {e}")
        return 1

    summary("✅ Ownership, versioning and consistency checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
