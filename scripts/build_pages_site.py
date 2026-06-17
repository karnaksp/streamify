#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"


@dataclass(frozen=True)
class Page:
    title: str
    source: Path | None
    output: str
    summary: str
    section: str


DASHBOARD_DEMO = """# Демонстрация Дашборда

Streamify показывает не только таблицы, а продуктовые аналитические срезы: сюжет библиотеки, карту вкуса, atlas-визуализации, rediscovery-очереди, playlist health и data quality.

![Обзор Streamify dashboard](docs/assets/dashboard-story.png)

## Визуальные Экраны

![Atlas и визуальные инсайты](docs/assets/dashboard-atlas.png)

![Actions и очереди рекомендаций](docs/assets/dashboard-actions.png)

## Что Проверять

- `Story`: общая картина библиотеки, активность и жанровый отпечаток.
- `Atlas`: месячный ритм, карта жанров, playlist subway и готовность geo enrichment.
- `Actions`: готовые очереди для rediscovery, чистки плейлистов и экспортов.
- `Data Quality`: источник данных, checksums, raw counts и diagnostics.
"""


PAGES = [
    Page("Главная", ROOT / "README.md", "index.html", "Что это за продукт, как запустить и какую пользу он дает.", "overview"),
    Page("Запуск", ROOT / "docs" / "yandex_music_local.md", "runbook.html", "Токен, локальный запуск, sample-режим и приемка реального аккаунта.", "runbook"),
    Page("Дашборд", None, "dashboard.html", "Скриншоты и ключевые экраны Streamlit-интерфейса.", "dashboard"),
    Page("Atlas + Гео", ROOT / "docs" / "location_enrichment.md", "location.html", "Как готовить будущие карты без опасных догадок о местоположении.", "atlas"),
    Page("Поток данных", ROOT / "docs" / "yamusic_lineage.md", "lineage.html", "Raw, staging, marts и поток данных до дашборда.", "lineage"),
    Page("Проверка", ROOT / "docs" / "product_acceptance.md", "acceptance.html", "Требования MVP и команды, которые их доказывают.", "quality"),
    Page("Проект", ROOT / "docs" / "project_management.md", "project.html", "Направления агентов, правила работы и план релизов.", "project"),
    Page("Релизы", ROOT / "docs" / "release_process.md", "release.html", "Privacy-safe релизы и GitHub Pages workflow.", "release"),
    Page("Пример отчета", ROOT / "data" / "streamify_summary.md", "sample-summary.html", "Пример инсайтов, собранный на sample metadata.", "summary"),
]


def page_markdown(page: Page) -> str:
    if page.source is None:
        return DASHBOARD_DEMO
    if page.source.exists():
        return page.source.read_text(encoding="utf-8")
    return f"# {page.title}\n\nЗапустите `make report`, чтобы собрать эту страницу на sample metadata."


DOC_LINKS = {
    "docs/yandex_music_local.md": "runbook.html",
    "docs/yamusic_lineage.md": "lineage.html",
    "docs/product_acceptance.md": "acceptance.html",
    "docs/location_enrichment.md": "location.html",
    "docs/release_process.md": "release.html",
    "docs/project_management.md": "project.html",
    "data/streamify_summary.md": "sample-summary.html",
}


def rewrite_href(href: str) -> str:
    normalized = href.lstrip("./")
    if normalized in DOC_LINKS:
        return DOC_LINKS[normalized]
    if normalized.startswith("docs/releases/") and normalized.endswith(".md"):
        return "release.html"
    return href


def link_to_html(match: re.Match[str]) -> str:
    label, href = match.groups()
    return f'<a href="{escape(rewrite_href(href), quote=True)}">{label}</a>'


def inline_markdown(text: str) -> str:
    text = escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_to_html, text)
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


def image_to_html(line: str) -> str | None:
    match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", line.strip())
    if not match:
        return None
    alt, src = match.groups()
    if src.startswith("docs/assets/"):
        src = src.replace("docs/assets/", "assets/", 1)
    return (
        '<figure class="media-frame">'
        f'<img src="{escape(src)}" alt="{escape(alt)}" loading="lazy">'
        f'<figcaption>{inline_markdown(alt)}</figcaption>'
        "</figure>"
    )


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

        image_html = image_to_html(line)
        if image_html:
            flush_paragraph()
            in_list = close_list(body, in_list)
            body.append(image_html)
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


def side_links(current_output: str) -> str:
    return "\n".join(
        f'<a class="side-link{" active" if page.output == current_output else ""}" href="{page.output}">'
        f'<span>{escape(page.title)}</span><small>{escape(page.summary)}</small></a>'
        for page in PAGES
    )


def hero_visual() -> str:
    return """
      <div class="hero-visual" aria-label="Превью Streamify dashboard">
        <div class="visual-top"><span></span><span></span><span></span></div>
        <div class="visual-grid">
          <div class="visual-card wide">
            <small>Жанровый сдвиг</small>
            <div class="bars"><i style="height:42%"></i><i style="height:76%"></i><i style="height:54%"></i><i style="height:88%"></i><i style="height:61%"></i></div>
          </div>
          <div class="visual-card">
            <small>Artist gravity</small>
            <strong>3.4x</strong>
          </div>
          <div class="visual-card">
            <small>Playlist overlap</small>
            <strong>0.28</strong>
          </div>
          <div class="visual-card wide line-card">
            <small>Monthly rhythm</small>
            <svg viewBox="0 0 300 90" role="img" aria-label="Линейный график">
              <path d="M5 70 C40 20, 80 55, 112 38 S170 22, 202 48 S260 78, 295 18" fill="none" stroke="#ffe14d" stroke-width="5" stroke-linecap="round"/>
              <path d="M5 78 C48 68, 79 82, 120 62 S190 70, 220 44 S262 35, 295 52" fill="none" stroke="#56d6b1" stroke-width="4" stroke-linecap="round"/>
            </svg>
          </div>
        </div>
      </div>
    """


def page_html(page: Page, body: str) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%23ffd83d'/%3E%3Cpath d='M19 40c6 4 20 4 26-5' fill='none' stroke='%23151515' stroke-width='6' stroke-linecap='round'/%3E%3Ccircle cx='24' cy='24' r='5' fill='%23151515'/%3E%3C/svg%3E">
  <title>{escape(page.title)} | Streamify</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #151515;
      --muted: #66707a;
      --soft: #f6f7f8;
      --paper: #ffffff;
      --line: #e1e5e9;
      --coal: #17191d;
      --coal-2: #22252b;
      --yellow: #ffd83d;
      --green: #23c99b;
      --cyan: #60c7ee;
      --shadow: 0 26px 70px rgba(22, 25, 31, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #fbfbfa;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}
    a {{ color: #0b735d; text-decoration-thickness: 1px; text-underline-offset: 3px; }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 20;
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
      align-items: center;
      gap: 22px;
      padding: 14px 28px;
      background: rgba(251, 251, 250, 0.92);
      border-bottom: 1px solid rgba(21, 21, 21, 0.08);
      backdrop-filter: blur(16px);
    }}
    .brand {{ display: flex; align-items: center; gap: 10px; color: var(--ink); text-decoration: none; }}
    .mark {{
      display: grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border-radius: 7px;
      background: var(--yellow);
      color: #111;
      font-weight: 900;
      box-shadow: inset 0 -2px 0 rgba(0,0,0,.12);
    }}
    .brand strong {{ display: block; font-size: 16px; line-height: 1; }}
    .brand span {{ display: block; margin-top: 3px; color: var(--muted); font-size: 12px; }}
    nav {{
      display: flex;
      justify-content: flex-end;
      gap: 4px;
      overflow-x: auto;
      min-width: 0;
      scrollbar-width: none;
    }}
    nav::-webkit-scrollbar {{ display: none; }}
    .nav-link {{
      flex: 0 0 auto;
      padding: 9px 11px;
      border-radius: 7px;
      color: #4f5963;
      text-decoration: none;
      font-size: 14px;
      font-weight: 700;
    }}
    .nav-link.active, .nav-link:hover {{ background: #151515; color: #fff; }}
    .hero {{
      color: #fff;
      background:
        linear-gradient(135deg, rgba(255,216,61,.16), transparent 38%),
        radial-gradient(circle at 78% 18%, rgba(35,201,155,.28), transparent 30%),
        #151515;
      border-bottom: 1px solid #2d3036;
    }}
    .hero-inner {{
      max-width: 1240px;
      min-height: 560px;
      margin: 0 auto;
      padding: 74px 28px 42px;
      display: grid;
      grid-template-columns: minmax(0, 0.95fr) minmax(360px, 0.75fr);
      gap: 54px;
      align-items: center;
    }}
    .section-label {{
      display: inline-flex;
      margin-bottom: 18px;
      color: var(--yellow);
      font-size: 13px;
      font-weight: 850;
      text-transform: uppercase;
    }}
    .hero h1 {{
      max-width: 820px;
      margin: 0 0 22px;
      font-size: clamp(42px, 6.6vw, 86px);
      line-height: .95;
      letter-spacing: 0;
    }}
    .hero p {{
      max-width: 700px;
      margin: 0;
      color: #d9dde2;
      font-size: 19px;
      line-height: 1.58;
    }}
    .hero-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 30px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      min-height: 44px;
      padding: 0 16px;
      border-radius: 7px;
      background: var(--yellow);
      color: #111;
      font-weight: 850;
      text-decoration: none;
    }}
    .button.secondary {{ background: #2a2e35; color: #fff; }}
    .hero-visual {{
      min-width: 0;
      padding: 16px;
      border: 1px solid rgba(255,255,255,.14);
      border-radius: 14px;
      background: linear-gradient(180deg, rgba(255,255,255,.12), rgba(255,255,255,.05));
      box-shadow: 0 28px 80px rgba(0,0,0,.28);
    }}
    .visual-top {{ display: flex; gap: 7px; padding: 0 0 13px; }}
    .visual-top span {{ width: 10px; height: 10px; border-radius: 50%; background: #4f5662; }}
    .visual-top span:first-child {{ background: var(--yellow); }}
    .visual-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .visual-card {{
      min-height: 112px;
      padding: 14px;
      border-radius: 10px;
      background: #20242b;
      border: 1px solid rgba(255,255,255,.08);
    }}
    .visual-card.wide {{ grid-column: span 2; }}
    .visual-card small {{ display: block; color: #9ba5b1; font-weight: 750; }}
    .visual-card strong {{ display: block; margin-top: 20px; color: #fff; font-size: 42px; }}
    .bars {{ display: flex; align-items: end; gap: 9px; height: 86px; margin-top: 14px; }}
    .bars i {{ flex: 1; border-radius: 6px 6px 0 0; background: linear-gradient(180deg, var(--yellow), var(--green)); }}
    .line-card svg {{ width: 100%; margin-top: 8px; }}
    .content-shell {{
      max-width: 1240px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 284px minmax(0, 1fr);
      gap: 40px;
      padding: 42px 28px 74px;
    }}
    aside {{
      align-self: start;
      position: sticky;
      top: 86px;
      display: grid;
      gap: 7px;
    }}
    .side-link {{
      display: block;
      padding: 12px 13px;
      border-left: 3px solid transparent;
      color: var(--ink);
      text-decoration: none;
    }}
    .side-link.active {{
      border-left-color: var(--yellow);
      background: #fff7c8;
    }}
    .side-link span {{ display: block; font-weight: 850; }}
    .side-link small {{ display: block; margin-top: 3px; color: var(--muted); line-height: 1.35; }}
    main {{
      min-width: 0;
      padding: 0 0 30px;
    }}
    .article {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 12px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .article-inner {{ padding: 42px; }}
    main h1:first-child {{
      margin-top: 0;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
      font-size: clamp(34px, 4vw, 54px);
    }}
    h1, h2, h3 {{ letter-spacing: 0; line-height: 1.12; }}
    h2 {{
      margin: 46px 0 14px;
      padding-top: 32px;
      border-top: 1px solid var(--line);
      font-size: clamp(26px, 3vw, 38px);
    }}
    h3 {{ margin: 30px 0 10px; font-size: 22px; }}
    p, li {{ color: #303841; font-size: 16px; line-height: 1.72; }}
    ul {{ padding-left: 22px; }}
    li + li {{ margin-top: 6px; }}
    code {{
      padding: 2px 5px;
      border-radius: 5px;
      background: #f0f2f4;
      color: #17212b;
      font-size: .92em;
    }}
    pre {{
      overflow: auto;
      margin: 20px 0;
      padding: 18px;
      border-radius: 10px;
      background: #17191d;
      color: #f4f6f8;
      line-height: 1.55;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.07);
    }}
    pre code {{ display: block; min-width: max-content; padding: 0; background: transparent; color: inherit; }}
    .table-wrap {{ overflow-x: auto; margin: 20px 0; border: 1px solid var(--line); border-radius: 10px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 720px; }}
    th, td {{ padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ background: #f5f6f7; color: #20242b; font-size: 13px; }}
    tr:last-child td {{ border-bottom: 0; }}
    .step {{
      padding: 12px 14px;
      border-left: 4px solid var(--yellow);
      background: #fff8d6;
      border-radius: 0 9px 9px 0;
    }}
    .media-frame {{
      margin: 28px 0;
      overflow: hidden;
      border: 1px solid #d9dee3;
      border-radius: 14px;
      background: #111;
      box-shadow: 0 24px 70px rgba(16, 19, 24, .16);
    }}
    .media-frame img {{ display: block; width: 100%; height: auto; }}
    .media-frame figcaption {{
      margin: 0;
      padding: 11px 14px;
      color: #dfe5eb;
      background: #17191d;
      font-size: 13px;
      font-weight: 750;
    }}
    footer {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 0 28px 34px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 980px) {{
      .topbar {{ grid-template-columns: 1fr; gap: 12px; padding: 12px 18px; }}
      nav {{ justify-content: flex-start; }}
      .hero-inner {{ grid-template-columns: 1fr; min-height: auto; padding: 48px 18px 30px; gap: 34px; }}
      .content-shell {{ grid-template-columns: 1fr; padding: 28px 18px 54px; }}
      aside {{ position: static; grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .article-inner {{ padding: 28px 20px; }}
    }}
    @media (max-width: 620px) {{
      .hero h1 {{ font-size: 42px; }}
      .hero p {{ font-size: 17px; }}
      .visual-grid, aside {{ grid-template-columns: 1fr; }}
      .visual-card.wide {{ grid-column: span 1; }}
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <a class="brand" href="index.html" aria-label="Streamify">
      <span class="mark">S</span>
      <span><strong>Streamify</strong><span>Локальная аналитика Яндекс Музыки</span></span>
    </a>
    <nav aria-label="Документация">{nav_html(page.output)}</nav>
  </div>
  <section class="hero">
    <div class="hero-inner">
      <div>
        <span class="section-label">{escape(page.title)}</span>
        <h1>Личная аналитика Яндекс Музыки на вашем ноутбуке.</h1>
        <p>{escape(page.summary)} Метаданные остаются локально: ingestion, DuckDB/dbt, dashboard, отчеты, action queues и воспроизводимая документация.</p>
        <div class="hero-actions">
          <a class="button" href="dashboard.html">Смотреть дашборд</a>
          <a class="button secondary" href="runbook.html">Запустить локально</a>
        </div>
      </div>
      {hero_visual()}
    </div>
  </section>
  <div class="content-shell">
    <aside aria-label="Разделы">{side_links(page.output)}</aside>
    <main>
      <article class="article">
        <div class="article-inner">{body}</div>
      </article>
    </main>
  </div>
  <footer>Собрано {generated}. Pages строятся на sample metadata; приватные данные Яндекс Музыки не нужны для публичного сайта.</footer>
</body>
</html>
"""


def main() -> int:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    assets_src = ROOT / "docs" / "assets"
    assets_dest = PUBLIC_DIR / "assets"
    if assets_src.exists():
        assets_dest.mkdir(parents=True, exist_ok=True)
        for asset in assets_src.iterdir():
            if asset.is_file():
                shutil.copy2(asset, assets_dest / asset.name)
    for page in PAGES:
        (PUBLIC_DIR / page.output).write_text(page_html(page, markdown_to_html(page_markdown(page))), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
