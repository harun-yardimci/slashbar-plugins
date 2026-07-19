#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_index


class CatalogRenderingTests(unittest.TestCase):
    def test_md_escape_flattens_lines_and_escapes_markdown(self):
        self.assertEqual(
            build_index.md_escape("One\\|Two\r\n## Forged"),
            r"One\\\|Two \#\# Forged",
        )

    def test_md_url_rejects_non_http_urls(self):
        for url in (
            "javascript:alert(1)",
            "https://@",
            "https://example.com\n## Forged",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    build_index.md_url(url)

    def test_catalog_renders_manifest_fields_as_literal_text(self):
        pack = {
            "id": "dev.example.safe",
            "name": "Safe\n## Forged",
            "version": "1.0.0",
            "description": "Close </details>",
            "author": "A **Maintainer**",
            "homepage": "https://example.com/a_(b)?q=x y",
            "commands": [
                {
                    "name": "One\\|Two",
                    "kind": "url",
                    "description": "Line\r| Forged",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "CATALOG.md"
            with patch.object(build_index, "CATALOG", catalog):
                build_index.write_catalog([pack])
            rendered = catalog.read_text(encoding="utf-8")

        self.assertNotIn("\n## Forged", rendered)
        self.assertIn(r"## Safe \#\# Forged `v1.0.0`", rendered)
        self.assertIn(r"Close \<\/details\>", rendered)
        self.assertIn(r"by **A \*\*Maintainer\*\***", rendered)
        self.assertIn(
            "[Homepage](<https://example.com/a_%28b%29?q=x%20y>)",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
