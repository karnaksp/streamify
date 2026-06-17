#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"


@dataclass(frozen=True)
class Page:
    title: str
    source: Path
    output: str
    summary: str


PAGES = [
    Page("Product Overview", ROOT / "README.md", "index.html", "What Streamify is, why it exists, and how to run it."),
    Page("Local Runbook", ROOT / "docs" / "yandex_music_local.md", "runbook.html", "Token-safe local setup and real-account acceptance."),
    Page("Atlas + Location", ROOT / "docs" / "location_enrichment.md", "location.html", "Map-ready enrichment contract and privacy guardrails."),
    Page("Lineage", ROOT / "docs" / "yamusic_lineage.md", "lineage.html", "Raw, staging, mart and dashboard data flow."),
    Page("Acceptance", ROOT / "docs" / "product_acceptance.md", "acceptance.html", "Product requirements mapped to concrete checks."),
    Page("Release Process", ROOT / "docs" / "release_process.md", "release.html", "Privacy-safe release and Pages workflow."),
    Page("Sample Summary", ROOT / "data" / "streamify_summary.md", "sample-summary.html", "Generated example insights from the sample library."),
]


def inline_markdown(text: str) -> str:
    text = escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def close_list(body: list[str], in_list: bool) -> bool:
    if in_list:
        body.append("</ul>")
    return False


def table_to_html(lines: list[str]) -> str:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    if len(rows) < 2:
        return ""
    headers = rows[0]
    data_rows = rows[2:] if set("".join(rows[1])) <= {"-", ":", " "} else rows[1:]
    html = ["<div class=\"table-wrap\"><table>", "<thead><tr>"]
    html.extend(f"<th>{inline_markdown(header)}</th>" for header in headers)
    html.append("</tr></thead><tbody>")
    for row in data_rows:
        html.append("<tr>")
        html.extend(f"<td>{inline_markdown(cell)}</td>" for cell in row)
        html.append("</tr>")
    html.append("</tbody></table></div>")
    return "".join(html)


def markdown_to_html(markdown: str) -> str:
    body: list[str] = []
    lines = markdown.splitlines()
    i = 0
    in_list = False
    in_code = False
    code_lines: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            body.append(f"<p>{inline_markdown(' '.join(paragraph))}</p>")
            paragraph = []

    while i < len(lines):
        raw_line = lines[i].rstrip()
        line = raw_line.strip()

        if line.startswith("```"):
            flush_paragraph()
            in_list = close_list(body, in_list)
            if in_code:
                body.append("<pre><code>" + escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_lines.append(raw_line)
            i += 1
            continue

        if not line:
            flush_paragraph()
            in_list = close_list(body, in_list)
            i += 1
            continue

        if line.startswith("|") and "|" in line[1:]:
            flush_paragraph()
            in_list = close_list(body, in_list)
            table_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].rstrip())
                i += 1
            body.append(table_to_html(table_lines))
            continue

        if line.startswith("#"):
            flush_paragraph()
            in_list = close_list(body, in_list)
            level = min(len(line) - len(line.lstrip("#")), 3)
            title = line[level:].strip()
            body.append(f"<h{level}>{inline_markdown(title)}</h{level}>")
            i += 1
            continue

        if line.startswith("- "):
            flush_paragraph()
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{inline_markdown(line[2:])}</li>")
            i += 1
            continue

        if re.match(r"^\d+\.\s+", line):
            flush_paragraph()
            in_list = close_list(body, in_list)
            item = re.sub(r"^\d+\.\s+", "", line)
            body.append(f"<p class=\"step\">{inline_markdown(item)}</p>")
            i += 1
            continue

        paragraph.append(line)
        i += 1

    flush_paragraph()
    close_list(body, in_list)
    if in_code:
        body.append("<pre><code>" + escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(part for part in body if part)


def nav_html(current_output: str) -> str:
    links = []
    for page in PAGES:
        active = " active" if page.output == current_output else ""
        links.append(f'<a class="nav-link{active}" href="{page.output}">{escape(page.title)}</a>')
    return "\n".join(links)


def page_html(page: Page, body: str) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cards = "\n".join(
        f'<a class="doc-card" href="{item.output}"><span>{escape(item.title)}</span><small>{escape(item.summary)}</small></a>'
        for item in PAGES
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(page.title)} | Streamify</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17212b;
      --muted: #627181;
      --line: #d9e1ea;
      --paper: #ffffff;
      --wash: #f4f7fa;
      --brand: #0c6b5f;
      --brand-dark: #084b45;
      --accent: #d96c2c;
      --accent-soft: #fff0e6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--wash);
      letter-spacing: 0;
    }}
    a {{ color: var(--brand-dark); text-decoration-thickness: 1px; text-underline-offset: 3px; }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: 14px 28px;
      background: rgba(255, 255, 255, 0.94);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(12px);
    }}
    .brand {{ display: flex; flex-direction: column; gap: 2px; min-width: 150px; }}
    .brand strong {{ font-size: 18px; }}
    .brand span {{ color: var(--muted); font-size: 12px; }}
    nav {{ display: flex; gap: 6px; overflow-x: auto; padding-bottom: 2px; }}
    nav {{ width: 100%; max-width: 100%; min-width: 0; }}
    .nav-link {{
      flex: 0 0 auto;
      padding: 8px 10px;
      border-radius: 6px;
      color: var(--muted);
      text-decoration: none;
      font-size: 14px;
      font-weight: 650;
    }}
    .nav-link.active, .nav-link:hover {{ color: var(--brand-dark); background: #e8f3f1; }}
    .hero {{
      background: linear-gradient(135deg, #f8fbfb 0%, #edf6f4 58%, #fff5ee 100%);
      border-bottom: 1px solid var(--line);
    }}
    .hero-inner {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 54px 28px 34px;
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(260px, 0.6fr);
      gap: 32px;
      align-items: end;
    }}
    .eyebrow {{
      color: var(--brand-dark);
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    .hero h1 {{
      max-width: 850px;
      margin: 10px 0 14px;
      font-size: clamp(34px, 6vw, 70px);
      line-height: 0.98;
      letter-spacing: 0;
    }}
    .hero p {{ max-width: 720px; color: #354351; font-size: 18px; line-height: 1.55; margin: 0; }}
    .metric-strip {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .metric {{
      min-height: 92px;
      padding: 14px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metric strong {{ display: block; color: var(--brand-dark); font-size: 23px; }}
    .metric span {{ color: var(--muted); font-size: 13px; line-height: 1.3; }}
    .layout {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 26px 28px 60px;
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      gap: 28px;
    }}
    aside {{
      align-self: start;
      position: sticky;
      top: 72px;
      display: grid;
      gap: 10px;
    }}
    .doc-card {{
      display: block;
      padding: 12px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      text-decoration: none;
    }}
    .doc-card span {{ display: block; color: var(--ink); font-weight: 750; }}
    .doc-card small {{ display: block; margin-top: 4px; color: var(--muted); line-height: 1.35; }}
    main {{
      min-width: 0;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 34px;
      box-shadow: 0 18px 45px rgba(28, 42, 56, 0.06);
    }}
    main h1:first-child {{ display: none; }}
    h1, h2, h3 {{ letter-spacing: 0; line-height: 1.15; }}
    h2 {{
      margin-top: 34px;
      padding-top: 24px;
      border-top: 1px solid var(--line);
      font-size: 28px;
    }}
    h3 {{ margin-top: 24px; font-size: 20px; }}
    p, li {{ color: #2c3946; line-height: 1.65; }}
    ul {{ padding-left: 21px; }}
    code {{
      padding: 2px 5px;
      border-radius: 5px;
      background: #edf2f6;
      color: #1d364f;
      font-size: 0.92em;
    }}
    pre {{
      overflow: auto;
      padding: 16px;
      border-radius: 8px;
      background: #11202d;
      color: #e8f2f7;
      line-height: 1.5;
    }}
    pre code {{ display: block; min-width: max-content; padding: 0; background: transparent; color: inherit; }}
    .table-wrap {{ overflow-x: auto; margin: 18px 0; border: 1px solid var(--line); border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 680px; }}
    th, td {{ padding: 11px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ background: #eef5f4; color: var(--brand-dark); font-size: 13px; }}
    tr:last-child td {{ border-bottom: 0; }}
    .step {{
      padding: 10px 12px;
      border-left: 3px solid var(--accent);
      background: var(--accent-soft);
      border-radius: 0 8px 8px 0;
    }}
    footer {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 0 28px 32px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 900px) {{
      .topbar {{ align-items: flex-start; flex-direction: column; padding: 12px 18px; overflow: hidden; }}
      .hero-inner {{ grid-template-columns: 1fr; padding: 38px 18px 24px; }}
      .layout {{ grid-template-columns: 1fr; padding: 18px 18px 44px; }}
      aside {{ position: static; grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      main {{ padding: 24px 18px; }}
    }}
    @media (max-width: 560px) {{
      aside, .metric-strip {{ grid-template-columns: 1fr; }}
      .hero h1 {{ font-size: 36px; }}
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="brand"><strong>Streamify</strong><span>Local Yandex Music self-analytics</span></div>
    <nav aria-label="Documentation">{nav_html(page.output)}</nav>
  </div>
  <section class="hero">
    <div class="hero-inner">
      <div>
        <div class="eyebrow">{escape(page.title)}</div>
        <h1>Personal music analytics that stays on your machine.</h1>
        <p>{escape(page.summary)} Metadata-only ingestion, DuckDB/dbt marts, Streamlit insights, action queues, and reproducible public docs.</p>
      </div>
      <div class="metric-strip" aria-label="Product pillars">
        <div class="metric"><strong>Local</strong><span>No account data in public artifacts.</span></div>
        <div class="metric"><strong>Typed</strong><span>Raw contracts, dbt tests, lineage.</span></div>
        <div class="metric"><strong>Useful</strong><span>Rediscovery, overlap, taste shifts.</span></div>
        <div class="metric"><strong>Map-ready</strong><span>Opt-in location enrichment only.</span></div>
      </div>
    </div>
  </section>
  <div class="layout">
    <aside aria-label="Pages">{cards}</aside>
    <main>{body}</main>
  </div>
  <footer>Generated {generated}. Built from tracked docs plus sample metadata; private Yandex Music data is never required for GitHub Pages.</footer>
</body>
</html>
"""


def main() -> int:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    for page in PAGES:
        if page.source.exists():
            markdown = page.source.read_text(encoding="utf-8")
        else:
            markdown = f"# {page.title}\n\nRun `make report` to generate this page from sample metadata."
        (PUBLIC_DIR / page.output).write_text(page_html(page, markdown_to_html(markdown)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
