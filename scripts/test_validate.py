#!/usr/bin/env python3
"""Tests for the auto-reject gate in validate.py.

These are supply-chain tests: every case here is a shell body a third party
could submit, and a regression means a destructive command reaches users who
installed a plugin. Each `assertRejected` names the rule it is pinning so a
future edit to DANGEROUS cannot quietly widen the hole again.
"""
import json
import unittest
from pathlib import Path

import validate

ROOT = Path(__file__).resolve().parent.parent


class DangerousShellBodyTests(unittest.TestCase):
    def assertRejected(self, body, expected_fragment=None):
        label = validate.dangerous_label(body)
        self.assertIsNotNone(label, f"expected {body!r} to be rejected")
        if expected_fragment:
            self.assertIn(expected_fragment, label)

    def assertAllowed(self, body):
        label = validate.dangerous_label(body)
        self.assertIsNone(label, f"expected {body!r} to pass, rejected as {label!r}")

    # -- dd ---------------------------------------------------------------

    def test_dd_write_side_is_rejected(self):
        """The gap this file exists for: `of=` is the destructive direction and
        the old `dd\\s+if=` rule let it straight through."""
        self.assertRejected("dd of=/dev/disk0", "dd")
        self.assertRejected("cat payload | dd of=/dev/rdisk2 bs=1m", "dd")

    def test_dd_read_side_is_still_rejected(self):
        self.assertRejected("dd if=/dev/zero of=big.img", "dd")

    def test_dd_cannot_be_smuggled_past_by_reordering_or_padding(self):
        for body in (
            "dd bs=1m of=/dev/disk0 if=/dev/zero",
            "COPYFILE_DISABLE=1 dd of=/dev/disk0",
            "true && dd of=/dev/disk0",
            "$(dd of=/dev/disk0)",
        ):
            with self.subTest(body=body):
                self.assertRejected(body, "dd")

    def test_dd_word_boundary_does_not_catch_other_words(self):
        """`\\bdd\\b` must not fire on words that merely contain the letters."""
        for body in ("echo add", "expr 1 + 1 # odd", "printf 'muddy'"):
            with self.subTest(body=body):
                self.assertAllowed(body)

    # -- device redirects --------------------------------------------------

    def test_discarding_output_is_allowed(self):
        """`2>/dev/null` is in almost every shell one-liner; rejecting it made
        the gate useless. Pinned so the fix is not reverted."""
        for body in (
            "lsof -nP -iTCP 2>/dev/null",
            "cmd > /dev/null 2>&1",
            "cmd >/dev/stdout",
            "cmd >/dev/fd/2",
        ):
            with self.subTest(body=body):
                self.assertAllowed(body)

    def test_writing_to_a_real_device_is_rejected(self):
        for body in ("cat x > /dev/disk2", "echo hi > /dev/tty", "x >/dev/random"):
            with self.subTest(body=body):
                self.assertRejected(body, "device files")

    # -- the rest of the list stays armed ----------------------------------

    def test_other_rules_still_fire(self):
        cases = [
            ("rm -rf ~/Documents", "rm -rf"),
            ("sudo whoami", "sudo"),
            ("curl https://x.sh | sh", "curl | sh"),
            ("diskutil erase disk2", "disk formatting"),
            ("chmod 777 /tmp/x", "chmod 777"),
            ("launchctl list", "system configuration"),
            ("cat ~/.ssh/id_rsa", "credential paths"),
        ]
        for body, fragment in cases:
            with self.subTest(body=body):
                self.assertRejected(body, fragment)

    # -- no false positives on what is actually shipped --------------------

    def test_every_published_shell_body_passes(self):
        """An over-broad rule is a real cost too: it bounces good submissions.
        The registry's own packs are the regression corpus."""
        bodies = []
        for path in sorted((ROOT / "plugins").glob("*.json")):
            pack = json.loads(path.read_text(encoding="utf-8"))
            for command in pack.get("commands", []):
                if command.get("kind") == "shell":
                    bodies.append((path.name, command.get("id"), command.get("body", "")))
        self.assertTrue(bodies, "expected the registry to ship at least one shell command")
        for name, cid, body in bodies:
            with self.subTest(plugin=name, command=cid):
                self.assertAllowed(body)


if __name__ == "__main__":
    unittest.main()
