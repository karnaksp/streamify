#!/usr/bin/env python3
from __future__ import annotations

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"

PAGES = [
    ("README", ROOT / "README.md"),
    ("Local Runbook", ROOT / "docs" / "yandex_music_local.md"),
    ("Lineage", ROOT / "docs" / "yamusic_lineage.md"),
    ("Acceptance", ROOT / "docs" / "product_acceptance.md"),
    ("Project Management", ROOT / "docs" / "project_management.md"),
    ("Release Process", ROOT / "docs" / "release_process.md"),
    ("Sample Summary", ROOT / "data" / "streamify_summary.md"),
]


def markdown_to_html(markdown: str) -> str:
    body: list[str] = []
    in_list = False
    in_code = False
    code_lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            if in_code:
                body.append("<pre><code>" + escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                if in_list:
                    body.append("</ul>")
                    in_list = False
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line:
            if in_list:
                body.append("</ul>")
                in_list = False
            continue
        if line.startswith("# "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h3>{escape(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{escape(line[2:])}</li>")
        else:
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<p>{escape(line)}</p>")
    if in_code:
        body.append("<pre><code>" + escape("\n".join(code_lines)) + "</code></pre>")
    if in_list:
        body.append("</ul>")
    return "\n".join(body)


def page_html(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} | Streamify</title>
  <style>
    body {{ margin: 0; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #16202a; background: #f7f8fa; }}
    header {{ background: #132238; color: white; padding: 28px 32px; }}
    nav a {{ color: #d8e8ff; margin-right: 18px; text-decoration: none; font-weight: 600; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px; background: white; min-height: 80vh; }}
    h1, h2, h3 {{ color: #132238; }}
    code, pre {{ background: #eef2f6; border-radius: 6px; }}
    code {{ padding: 2px 5px; }}
    pre {{ padding: 16px; overflow: auto; }}
    table {{ border-collapse: collapse; width: 100%; }}
    p, li {{ line-height: 1.55; }}
  </style>
</head>
<body>
  <header>
    <h1>Streamify</h1>
    <nav><a href="index.html">Home</a><a href="runbook.html">Runbook</a><a href="lineage.html">Lineage</a><a href="acceptance.html">Acceptance</a><a href="management.html">Management</a><a href="release.html">Release</a><a href="sample-summary.html">Sample Summary</a></nav>
  </header>
  <main>{body}</main>
</body>
</html>
"""


def main() -> int:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    filenames = ["index.html", "runbook.html", "lineage.html", "acceptance.html", "management.html", "release.html", "sample-summary.html"]
    for (title, path), filename in zip(PAGES, filenames):
        markdown = path.read_text(encoding="utf-8") if path.exists() else f"# {title}\n\nRun `make report` to generate this page."
        (PUBLIC_DIR / filename).write_text(page_html(title, markdown_to_html(markdown)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
