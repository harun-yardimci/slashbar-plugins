# Slashbar Plugin Registry

Community action packs for [Slashbar](https://github.com/slashbar/slashbar). A plugin
is a single JSON manifest (a **SlashPack**) containing metadata and a list of commands.
Slashbar fetches `index.json` from this repo and lets users browse and install packs
from Settings → Plugins.

## Submitting a plugin

1. Fork this repo.
2. Add your manifest as `plugins/<your.plugin.id>.json` (the filename must equal the
   manifest's `id`), and register yourself in `owners.json`
   (`"your.plugin.id": "your-github-login"`).
3. Open a pull request. CI validates the manifest automatically; a maintainer reviews
   the content (especially `shell` commands) before merging.
4. On merge, `index.json` is rebuilt and published automatically — your plugin shows
   up in the app within minutes.

To update a plugin, bump `version` in the same file and open a new PR.

### Automated PR checks

Besides manifest validation, CI enforces ownership and versioning
(`scripts/check_pr.py`):

- **Updates** are only accepted from the plugin's recorded owner in `owners.json`,
  and `version` must increase.
- **New plugins** must register the PR author as their owner in the same PR.
- **Ownership transfers and deletions** by anyone but the owner fail CI and need an
  explicit maintainer decision.
- **Shell commands** in new or changed manifests are flagged prominently in the CI
  summary — maintainers read every command body before merging those.

A red ✗ means "do not merge without looking"; merges themselves stay manual.

## Manifest format (schema 1)

```json
{
  "schema": 1,
  "id": "dev.yourname.git-helpers",
  "name": "Git Helpers",
  "author": "yourname",
  "version": "1.0.0",
  "description": "Git workflow actions",
  "icon": "arrow.triangle.branch",
  "homepage": "https://github.com/yourname/whatever",
  "minAppVersion": "1.0.0",
  "commands": [
    {
      "id": "conventional-commit",
      "name": "Conventional Commit",
      "kind": "ai",
      "body": "Rewrite the following change description as a conventional commit message. Return only the message.",
      "description": "Turn a change description into a conventional commit.",
      "keywords": ["git", "commit"]
    },
    {
      "id": "pr-search",
      "name": "Search Pull Requests",
      "kind": "url",
      "body": "https://github.com/pulls?q={q}"
    }
  ]
}
```

### Fields

| Field | Required | Notes |
|---|---|---|
| `schema` | ✓ | Always `1` for now. |
| `id` | ✓ | Reverse-DNS, lowercase, `[a-z0-9.-]` only. Must match the filename. |
| `name`, `author`, `version`, `description` | ✓ | `version` is dotted-numeric ("1.2.0"). |
| `icon` | – | An [SF Symbol](https://developer.apple.com/sf-symbols/) name. |
| `homepage`, `minAppVersion` | – | |
| `commands[].id` | ✓ | Unique within the pack, `[a-z0-9-]`. |
| `commands[].kind` | ✓ | `ai` (prompt; the user's input text is appended), `url` (template; `{q}` is the URL-encoded input), or `shell` (runs via `/bin/sh`; input is piped to stdin). |
| `commands[].body` | ✓ | The prompt, URL template, or shell command. |
| `commands[].description`, `icon`, `keywords` | – | |

### Rules for `shell` commands

Shell commands run with the user's account, so they get extra scrutiny:

- CI rejects obviously destructive patterns (`rm -rf`, `curl … | sh`, `sudo`, writes
  outside stdout). See `scripts/validate.py` for the full list.
- Reviewers may ask you to justify any shell usage; prefer `ai`/`url` when possible.
- The app labels shell packs with a warning and shows the full command text before
  the user installs.

## Local validation

```sh
python3 scripts/validate.py plugins/your.plugin.id.json
python3 scripts/build_index.py   # writes public/index.json
```
