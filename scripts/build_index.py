#!/usr/bin/env python3
"""Build public/index.json from plugins/*.json.

The index inlines the full manifests (they're small), so the app installs a
plugin by persisting the manifest locally — no second fetch needed.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
OUT = ROOT / "public" / "index.json"


def main():
    packs = []
    for path in sorted(PLUGINS.glob("*.json")):
        packs.append(json.loads(path.read_text(encoding="utf-8")))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    index = {"schema": 1, "plugins": packs}
    OUT.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} with {len(packs)} plugin(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
