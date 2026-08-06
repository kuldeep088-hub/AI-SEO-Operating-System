#!/usr/bin/env python
"""Compile the whole specification into one PDF.

    UV_PROJECT_ENVIRONMENT=~/.seoos/venv uv run python scripts/build_pdf.py

Reads README.md, docs/01..14 and the appendices, renders them to a single
styled HTML document, and prints that through headless Chrome (the only PDF
engine already on a Mac — no pandoc, no LaTeX, nothing to install, $0).

Mermaid and highlight.js are fetched once and cached under ~/.seoos/pdf-assets.
If the network is unavailable the build still succeeds: diagrams fall back to
their source text and code blocks render unhighlighted.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path.home() / ".seoos" / "pdf-assets"
OUT_PDF = ROOT / "AI-SEO-Operating-System.pdf"
OUT_HTML = CACHE / "book.html"

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9333

VENDOR = {
    "mermaid.min.js": "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js",
    "highlight.min.js": "https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11/highlight.min.js",
    "sql.min.js": "https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11/languages/sql.min.js",
}


# ---------------------------------------------------------------- structure


@dataclass
class Doc:
    path: str
    title: str
    descriptor: str
    part: str
    slug: str = ""
    html: str = ""
    sections: list[tuple[str, str]] = field(default_factory=list)  # (anchor, text)
    span: str = ""  # "§22–§25", filled in from the headings actually found

    @property
    def subtitle(self) -> str:
        return f"{self.span} — {self.descriptor}" if self.span else self.descriptor


DOCS: list[Doc] = [
    Doc("README.md", "The System at a Glance", "What it is, what it replaces, how it runs", "Front Matter"),
    Doc("docs/01-product-vision.md", "Product Vision", "the thesis, the user, the wedge", "Part I — The Product"),
    Doc("docs/02-features.md", "Features", "every capability, in scope order", "Part I — The Product"),
    Doc("docs/03-user-journeys.md", "User Journeys", "what a week actually looks like", "Part I — The Product"),
    Doc("docs/04-ui-ux.md", "UI & UX", "every screen, state and interaction", "Part II — Surface & Data"),
    Doc("docs/05-database.md", "Database", "schema, partitioning, RLS, queries", "Part II — Surface & Data"),
    Doc("docs/06-api-auth.md", "API & Auth", "endpoints, sessions, RBAC", "Part II — Surface & Data"),
    Doc("docs/07-ai-architecture.md", "AI Architecture", "agents, prompts, RAG, evidence rules", "Part III — The Machine"),
    Doc("docs/08-infrastructure.md", "Infrastructure", "storage, jobs, queue, webhooks, tenancy", "Part III — The Machine"),
    Doc("docs/09-security-ops.md", "Security & Operations", "threat model, logging, monitoring", "Part III — The Machine"),
    Doc("docs/10-deployment.md", "Deployment", "stack decisions and how it ships", "Part IV — Running the Business"),
    Doc("docs/11-costs.md", "Costs", "the $0 constraint, proven line by line", "Part IV — Running the Business"),
    Doc("docs/12-roadmap.md", "Roadmap", "phases, exit criteria, what is next", "Part IV — Running the Business"),
    Doc("docs/13-business.md", "Business Model", "packaging, pricing, positioning", "Part IV — Running the Business"),
    Doc("docs/14-execution.md", "Execution", "how the build is actually run", "Part IV — Running the Business"),
    Doc("DEPLOY.md", "Appendix A — Going Live", "The operational runbook", "Appendices"),
    Doc("CLAUDE.md", "Appendix B — Engineering Rules", "The hard rules and current state", "Appendices"),
    Doc("DESIGN.md", "Appendix C — Design Language", "Tokens, type scale, components", "Appendices"),
]

# §12 → the anchor of the heading that defines it. Filled while rendering, used
# afterwards to turn every cross-reference in the prose into a live link.
SECTION_ANCHORS: dict[str, str] = {}


# ---------------------------------------------------------------- rendering


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower().replace("§", "s"))
    return re.sub(r"[\s_-]+", "-", s).strip("-") or "section"


def doc_slug(path: str) -> str:
    return "doc-" + slugify(Path(path).stem)


def strip_front_matter(text: str) -> tuple[str, str]:
    """Pull a leading YAML block out so it renders as code, not as prose."""
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    return text[4:end], text[end + 5 :]


def build_link_map() -> dict[str, str]:
    m: dict[str, str] = {}
    for d in DOCS:
        anchor = "#" + doc_slug(d.path)
        name = Path(d.path).name
        m[name] = anchor
        m[d.path] = anchor
        m["../" + d.path] = anchor
        m["docs/" + name] = anchor
        m["../" + name] = anchor
        m["./" + name] = anchor
    return m


LINKS = build_link_map()


def rewrite_href(href: str) -> str:
    if href.startswith(("http://", "https://", "#", "mailto:")):
        return href
    base, _, frag = href.partition("#")
    target = LINKS.get(base) or LINKS.get(base.lstrip("./"))
    if target:
        return target
    # A link to a source file we are not printing — leave the text, drop the link.
    return ""


def is_nav(text: str) -> bool:
    """Site navigation that means nothing once the docs are one bound volume."""
    t = text.strip()
    if "Back to index" in t:
        return True
    if ("Index" in t or "index" in t) and ("Next:" in t or t.startswith("←")):
        return True
    return bool(re.fullmatch(r"Section §\d+\.?", t))


def render_doc(doc: Doc) -> None:
    raw = (ROOT / doc.path).read_text(encoding="utf-8")
    front, body = strip_front_matter(raw)

    md = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    tokens = md.parse(body)

    # Drop navigation paragraphs, and the horizontal rule that decorated them.
    keep: list[Token] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if (
            tok.type == "paragraph_open"
            and i + 1 < len(tokens)
            and tokens[i + 1].type == "inline"
            and is_nav(tokens[i + 1].content)
        ):
            i += 3  # paragraph_open, inline, paragraph_close
            while keep and keep[-1].type == "hr":
                keep.pop()
            continue
        keep.append(tok)
        i += 1
    while keep and keep[-1].type == "hr":
        keep.pop()
    tokens = keep

    seen: set[str] = set()
    heading_level = 0
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open":
            heading_level = int(tok.tag[1])
            text = tokens[i + 1].content if i + 1 < len(tokens) else ""
            base = f"{doc.slug}-{slugify(text)}"
            anchor, n = base, 2
            while anchor in seen:
                anchor, n = f"{base}-{n}", n + 1
            seen.add(anchor)
            tok.attrSet("id", anchor)
            tok.attrSet("class", f"h{heading_level}")
            if heading_level == 2:
                doc.sections.append((anchor, text))
                m = re.match(r"§(\d+)", text.strip())
                if m:
                    SECTION_ANCHORS.setdefault(m.group(1), anchor)
        elif tok.type == "link_open":
            new = rewrite_href(tok.attrGet("href") or "")
            if new:
                tok.attrSet("href", new)
            else:
                tok.attrSet("href", "#")
                tok.attrSet("class", "dead")
        elif tok.type == "fence":
            lang = (tok.info or "").strip().split()[0] if tok.info.strip() else ""
            if lang == "mermaid":
                tok.type = "html_block"
                tok.content = (
                    '<figure class="diagram"><pre class="mermaid">'
                    + esc(tok.content)
                    + "</pre></figure>\n"
                )
                tok.tag = ""

    # The first h1 becomes the chapter title page, rendered separately.
    if tokens and tokens[0].type == "heading_open" and tokens[0].tag == "h1":
        tokens = tokens[3:]

    html = md.renderer.render(tokens, md.options, {})
    if front:
        html = (
            '<h2 class="h2" id="%s-tokens">Design tokens</h2>\n'
            '<pre class="lang-yaml"><code class="language-yaml">%s</code></pre>\n' % (doc.slug, esc(front))
            + html
        )
        doc.sections.insert(0, (f"{doc.slug}-tokens", "Design tokens"))
    doc.html = html

    nums = [int(m.group(1)) for a, t in doc.sections if (m := re.match(r"§(\d+)", t.strip()))]
    if nums:
        doc.span = f"§{min(nums)}" if len(nums) == 1 else f"§{min(nums)}–§{max(nums)}"


SKIP_OPEN = re.compile(r"<(pre|code|a|h1|h2|h3|h4|h5|h6)\b", re.I)
SKIP_CLOSE = re.compile(r"</(pre|code|a|h1|h2|h3|h4|h5|h6)>", re.I)
XREF = re.compile(r"§(\d+)")


def link_cross_references(html: str) -> str:
    """Make every "§17" in the prose a link to §17 — 164 pages is too many to flip."""
    out: list[str] = []
    depth = 0
    for chunk in re.split(r"(<[^>]+>)", html):
        if chunk.startswith("<"):
            if SKIP_OPEN.match(chunk) and not chunk.endswith("/>"):
                depth += 1
            elif SKIP_CLOSE.match(chunk):
                depth = max(0, depth - 1)
            out.append(chunk)
            continue
        if depth or "§" not in chunk:
            out.append(chunk)
            continue
        out.append(
            XREF.sub(
                lambda m: (
                    f'<a class="xref" href="#{SECTION_ANCHORS[m.group(1)]}">§{m.group(1)}</a>'
                    if m.group(1) in SECTION_ANCHORS
                    else m.group(0)
                ),
                chunk,
            )
        )
    return "".join(out)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------- assets


def fetch_assets() -> dict[str, str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    out: dict[str, str] = {}
    for name, url in VENDOR.items():
        dest = CACHE / name
        if not dest.exists():
            try:
                print(f"  fetching {name} …")
                with urllib.request.urlopen(url, timeout=30) as r:
                    dest.write_bytes(r.read())
            except (urllib.error.URLError, TimeoutError) as e:
                print(f"  ! {name} unavailable ({e}) — continuing without it")
                continue
        out[name] = dest.read_text(encoding="utf-8")
    return out


# ---------------------------------------------------------------- the page

CSS = """
:root {
  --ink: #0a0a0a; --body: #262626; --muted: #737373; --faint: #a3a3a3;
  --rule: #e5e5e5; --wash: #fafafa; --code-bg: #f7f7f8;
  --accent: #0060df; --accent-soft: #eef4ff;
}
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  margin: 0; color: var(--body); background: #fff;
  font: 10.2pt/1.62 -apple-system, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
  font-feature-settings: "kern" 1, "liga" 1;
  text-rendering: optimizeLegibility;
}
code, pre, .mono {
  font-family: "SF Mono", "JetBrains Mono", Menlo, ui-monospace, monospace;
  font-variant-ligatures: none;
}

/* ---- cover ---- */
.cover { height: 247mm; display: flex; flex-direction: column; page-break-after: always; }
.cover .mesh {
  height: 74mm; border-radius: 4mm; margin-bottom: 14mm;
  background:
    radial-gradient(60% 90% at 12% 20%, #00d1ff 0%, rgba(0,209,255,0) 60%),
    radial-gradient(55% 85% at 78% 10%, #ff2fd0 0%, rgba(255,47,208,0) 62%),
    radial-gradient(70% 100% at 62% 88%, #7c4dff 0%, rgba(124,77,255,0) 60%),
    radial-gradient(45% 70% at 30% 92%, #ffb020 0%, rgba(255,176,32,0) 58%),
    #0a0a0a;
}
.cover .eyebrow {
  font-size: 8.5pt; letter-spacing: .16em; text-transform: uppercase;
  color: var(--muted); margin-bottom: 6mm;
}
.cover h1 {
  font-size: 34pt; line-height: 1.06; letter-spacing: -.028em;
  color: var(--ink); margin: 0 0 6mm; font-weight: 700; max-width: 150mm;
}
.cover .deck {
  font-size: 13pt; line-height: 1.45; color: var(--body); max-width: 135mm; margin: 0 0 auto;
  letter-spacing: -.008em;
}
.cover .facts {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 6mm;
  border-top: 1px solid var(--rule); padding-top: 6mm; margin-top: 10mm;
}
.cover .facts div { font-size: 8.5pt; color: var(--muted); }
.cover .facts b {
  display: block; font-size: 15pt; color: var(--ink); letter-spacing: -.02em;
  font-weight: 650; margin-bottom: 1.5mm;
}
.cover .imprint {
  margin-top: 8mm; font-size: 8.5pt; color: var(--faint);
  display: flex; justify-content: space-between; border-top: 1px solid var(--rule); padding-top: 4mm;
}

/* ---- table of contents ---- */
.toc { page-break-after: always; }
.toc > h2 {
  font-size: 20pt; letter-spacing: -.02em; color: var(--ink); margin: 0 0 2mm; font-weight: 680;
}
.toc .lede { color: var(--muted); font-size: 9.5pt; margin: 0 0 9mm; }
.toc .part {
  font-size: 8pt; letter-spacing: .15em; text-transform: uppercase; color: var(--faint);
  border-top: 1px solid var(--rule); padding-top: 3mm; margin: 7mm 0 3.5mm;
}
.toc .entry { margin: 0 0 3.5mm; page-break-inside: avoid; }
.toc .entry a.chapter {
  color: var(--ink); text-decoration: none; font-weight: 620; font-size: 11pt;
  letter-spacing: -.012em;
}
.toc .entry .num {
  display: inline-block; width: 9mm; color: var(--faint); font-size: 9pt; font-weight: 500;
}
.toc .entry .sub { margin-left: 9mm; color: var(--muted); font-size: 8.6pt; margin-top: .8mm; }
.toc .entry .secs { margin-left: 9mm; margin-top: 1.4mm; font-size: 8.4pt; color: var(--muted); }
.toc .entry .secs a { color: var(--muted); text-decoration: none; }
.toc .entry .secs span { color: var(--rule); padding: 0 1.6mm; }

/* ---- chapter openers ---- */
.chapter-open { page-break-before: always; padding-top: 3mm; margin-bottom: 9mm; }
.chapter-open .part {
  font-size: 8pt; letter-spacing: .15em; text-transform: uppercase;
  color: var(--accent); margin-bottom: 3mm;
}
.chapter-open h1 {
  font-size: 25pt; letter-spacing: -.026em; color: var(--ink); margin: 0 0 3mm;
  font-weight: 700; line-height: 1.1;
}
.chapter-open .sub { color: var(--muted); font-size: 10pt; margin: 0 0 5mm; }
.chapter-open .rule { height: 2.6mm; border-radius: 1.3mm; background: linear-gradient(90deg,#00d1ff,#7c4dff 45%,#ff2fd0 75%,#ffb020); }

/* ---- prose ---- */
h2.h2 {
  font-size: 15pt; letter-spacing: -.02em; color: var(--ink); font-weight: 680;
  margin: 9mm 0 3mm; padding-top: 2mm; border-top: 1px solid var(--rule);
  page-break-after: avoid; line-height: 1.25;
}
h3.h3 {
  font-size: 11.6pt; letter-spacing: -.014em; color: var(--ink); font-weight: 650;
  margin: 6mm 0 2mm; page-break-after: avoid; line-height: 1.3;
}
h4.h4, h5.h5, h6.h6 {
  font-size: 9.6pt; letter-spacing: .01em; color: var(--ink); font-weight: 650;
  margin: 4.5mm 0 1.5mm; page-break-after: avoid;
}
p { margin: 0 0 3mm; orphans: 2; widows: 2; }
ul, ol { margin: 0 0 3mm; padding-left: 5.5mm; }
li { margin: 0 0 1.2mm; }
li > ul, li > ol { margin-top: 1.2mm; }
strong { color: var(--ink); font-weight: 620; }
a { color: var(--accent); text-decoration: none; }
a.dead { color: inherit; }
a.xref { color: var(--accent); white-space: nowrap; }
hr { border: 0; border-top: 1px solid var(--rule); margin: 6mm 0; }
/* The source uses --- before every ## ; the heading already draws that rule. */
hr:has(+ h2.h2) { display: none; }
blockquote {
  margin: 0 0 3mm; padding: 2.5mm 0 2.5mm 4mm; border-left: 2px solid var(--accent);
  background: var(--accent-soft); color: var(--body); page-break-inside: avoid;
}
blockquote p:last-child { margin-bottom: 0; }
blockquote > p:first-child { margin-top: 0; }

/* ---- code ---- */
:not(pre) > code {
  background: var(--code-bg); border: 1px solid var(--rule); border-radius: 1mm;
  padding: 0 1mm; font-size: 8.6pt; color: var(--ink); white-space: nowrap;
}
pre {
  background: var(--code-bg); border: 1px solid var(--rule); border-radius: 1.5mm;
  padding: 3mm 3.5mm; margin: 0 0 4mm; overflow: hidden;
  font-size: 8.1pt; line-height: 1.45; color: var(--ink);
  white-space: pre-wrap; word-break: break-word; page-break-inside: avoid;
}
pre.tall { page-break-inside: auto; }
pre code { background: none; border: 0; padding: 0; font-size: inherit; white-space: inherit; }

/* ---- tables ---- */
table {
  width: 100%; border-collapse: collapse; margin: 0 0 4mm; font-size: 8.7pt;
  page-break-inside: avoid;
}
table.tall { page-break-inside: auto; }
thead { background: var(--wash); }
th {
  text-align: left; font-weight: 620; color: var(--ink); padding: 1.8mm 2.2mm;
  border-bottom: 1px solid #d4d4d4; font-size: 8.2pt; letter-spacing: .01em;
}
td { padding: 1.8mm 2.2mm; border-bottom: 1px solid var(--rule); vertical-align: top; }
td code, th code { font-size: 8pt; white-space: normal; }
tr { page-break-inside: avoid; }

/* ---- diagrams ---- */
figure.diagram {
  margin: 0 0 5mm; padding: 4mm; border: 1px solid var(--rule); border-radius: 1.5mm;
  background: #fff; text-align: center; page-break-inside: avoid;
}
figure.diagram svg { max-width: 100%; height: auto; }
figure.diagram pre.mermaid { border: 0; background: none; padding: 0; margin: 0; text-align: left; }

/* ---- highlight.js, print-tuned ---- */
.hljs-keyword, .hljs-selector-tag, .hljs-literal, .hljs-section { color: #0550ae; }
.hljs-string, .hljs-attr, .hljs-symbol, .hljs-bullet, .hljs-addition { color: #0a7c42; }
.hljs-comment, .hljs-quote { color: #8b8b8b; font-style: italic; }
.hljs-number, .hljs-meta { color: #953800; }
.hljs-title, .hljs-name, .hljs-built_in, .hljs-type { color: #6639ba; }
.hljs-attribute, .hljs-variable, .hljs-template-variable { color: #0a3069; }
.hljs-deletion { color: #b31d28; }
"""

JS = """
(async () => {
  // Long code blocks and tables must be allowed to break, or they leave
  // half-empty pages behind.
  document.querySelectorAll('pre').forEach(el => {
    if (el.textContent.split('\\n').length > 34) el.classList.add('tall');
  });
  document.querySelectorAll('table').forEach(el => {
    if (el.querySelectorAll('tr').length > 18) el.classList.add('tall');
  });

  if (window.hljs) {
    document.querySelectorAll('pre > code[class*="language-"]').forEach(el => {
      const lang = (el.className.match(/language-([\\w-]+)/) || [])[1];
      if (lang && window.hljs.getLanguage(lang)) {
        try { window.hljs.highlightElement(el); } catch (e) {}
      }
    });
  }

  if (window.mermaid) {
    window.mermaid.initialize({
      startOnLoad: false, theme: 'neutral', securityLevel: 'loose',
      fontFamily: '-apple-system, "SF Pro Text", Helvetica, sans-serif',
      themeVariables: { fontSize: '13px', primaryColor: '#f7f7f8', primaryBorderColor: '#d4d4d4',
                        primaryTextColor: '#0a0a0a', lineColor: '#737373' },
      flowchart: { useMaxWidth: true }, sequence: { useMaxWidth: true }
    });
    try { await window.mermaid.run({ querySelector: 'pre.mermaid' }); } catch (e) {}
  }

  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  window.__pdfReady = true;
})();
"""


def build_html(assets: dict[str, str]) -> str:
    parts: list[str] = []
    today = date.today().strftime("%d %B %Y")

    parts.append(
        f"""<div class="cover">
  <div class="mesh"></div>
  <div class="eyebrow">Growleads Agency · Product & Engineering Specification</div>
  <h1>AI SEO<br>Operating System</h1>
  <p class="deck">A complete SEO platform that runs entirely on your own machine — Google's
  free data, a local AI model, agency-grade deliverables. $0/month at any number of clients.</p>
  <div class="facts">
    <div><b>18</b>documents, complete</div>
    <div><b>$0</b>recurring cost, by design</div>
    <div><b>49</b>tables, 29 RLS-protected</div>
    <div><b>5</b>tools replaced</div>
  </div>
  <div class="imprint"><span>Compiled {today}</span><span>Internal — Growleads Agency</span></div>
</div>"""
    )

    toc: list[str] = [
        '<div class="toc"><h2>Contents</h2>',
        '<p class="lede">Every document in <code>docs/</code>, in reading order, plus the '
        "operational appendices. Entries are linked — and the PDF carries bookmarks for the "
        "same structure.</p>",
    ]
    current_part = None
    for i, d in enumerate(DOCS, start=1):
        if d.part != current_part:
            current_part = d.part
            toc.append(f'<div class="part">{esc(current_part)}</div>')
        secs = " <span>·</span> ".join(
            f'<a href="#{a}">{esc(t)}</a>' for a, t in d.sections[:14]
        )
        more = " <span>·</span> …" if len(d.sections) > 14 else ""
        toc.append(
            f'<div class="entry">'
            f'<span class="num">{i:02d}</span>'
            f'<a class="chapter" href="#{d.slug}">{esc(d.title)}</a>'
            f'<div class="sub">{esc(d.subtitle)} · <span class="mono">{esc(d.path)}</span></div>'
            f'<div class="secs">{secs}{more}</div>'
            f"</div>"
        )
    toc.append("</div>")
    parts.append("\n".join(toc))

    for i, d in enumerate(DOCS, start=1):
        parts.append(
            f"""<section class="chapter">
  <div class="chapter-open" id="{d.slug}">
    <div class="part">{esc(d.part)} · {i:02d}</div>
    <h1>{esc(d.title)}</h1>
    <p class="sub">{esc(d.subtitle)}</p>
    <div class="rule"></div>
  </div>
{d.html}
</section>"""
        )

    scripts = "".join(
        f"<script>{assets[n]}</script>" for n in ("highlight.min.js", "sql.min.js", "mermaid.min.js") if n in assets
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<title>AI SEO Operating System — Complete Specification</title>"
        f"<style>{CSS}</style></head><body>"
        + "\n".join(parts)
        + scripts
        + f"<script>{JS}</script></body></html>"
    )


# ---------------------------------------------------------------- printing


async def print_pdf(html_path: Path, pdf_path: Path) -> None:
    import websockets

    profile = Path(tempfile.mkdtemp(prefix="seoos-pdf-"))
    chrome = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-gpu",
            "--allow-file-access-from-files",
            "--font-render-hinting=none",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        ws_url = None
        for _ in range(80):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1) as r:
                    ws_url = json.loads(r.read())["webSocketDebuggerUrl"]
                break
            except Exception:
                time.sleep(0.25)
        if not ws_url:
            raise RuntimeError("Chrome did not expose a debugging endpoint")

        async with websockets.connect(ws_url, max_size=256 * 1024 * 1024) as ws:
            counter = {"n": 0}

            async def send(method: str, params: dict | None = None, session: str | None = None) -> dict:
                counter["n"] += 1
                msg: dict = {"id": counter["n"], "method": method, "params": params or {}}
                if session:
                    msg["sessionId"] = session
                await ws.send(json.dumps(msg))
                while True:
                    reply = json.loads(await ws.recv())
                    if reply.get("id") == msg["id"]:
                        if "error" in reply:
                            raise RuntimeError(f"{method}: {reply['error']}")
                        return reply.get("result", {})

            target = await send("Target.createTarget", {"url": "about:blank"})
            attached = await send(
                "Target.attachToTarget", {"targetId": target["targetId"], "flatten": True}
            )
            sid = attached["sessionId"]

            await send("Page.enable", session=sid)
            await send("Runtime.enable", session=sid)
            await send("Emulation.setEmulatedMedia", {"media": "print"}, session=sid)
            await send("Page.navigate", {"url": html_path.as_uri()}, session=sid)

            print("  rendering (mermaid + highlighting) …")
            deadline = time.time() + 90
            while time.time() < deadline:
                res = await send(
                    "Runtime.evaluate",
                    {"expression": "!!window.__pdfReady", "returnByValue": True},
                    session=sid,
                )
                if res.get("result", {}).get("value"):
                    break
                await asyncio.sleep(0.4)
            else:
                print("  ! render did not signal ready in 90s — printing anyway")

            foot = (
                '<div style="width:100%;font:7pt -apple-system,Helvetica,sans-serif;color:#a3a3a3;'
                'padding:0 16mm;display:flex;justify-content:space-between;">'
                "<span>AI SEO Operating System — Complete Specification · Growleads Agency</span>"
                '<span class="pageNumber"></span></div>'
            )
            print("  printing …")
            result = await send(
                "Page.printToPDF",
                {
                    "printBackground": True,
                    "paperWidth": 8.27,
                    "paperHeight": 11.69,
                    "marginTop": 0.63,
                    "marginBottom": 0.63,
                    "marginLeft": 0.63,
                    "marginRight": 0.63,
                    "displayHeaderFooter": True,
                    "headerTemplate": "<div></div>",
                    "footerTemplate": foot,
                    "preferCSSPageSize": False,
                    "generateTaggedPDF": True,
                    "generateDocumentOutline": True,
                },
                session=sid,
            )
            pdf_path.write_bytes(base64.b64decode(result["data"]))
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=10)
        except subprocess.TimeoutExpired:
            chrome.kill()
        shutil.rmtree(profile, ignore_errors=True)


# ---------------------------------------------------------------- main


def main() -> int:
    if not Path(CHROME).exists():
        print(f"Chrome not found at {CHROME} — it is the PDF engine.", file=sys.stderr)
        return 1

    missing = [d.path for d in DOCS if not (ROOT / d.path).exists()]
    if missing:
        print("Missing: " + ", ".join(missing), file=sys.stderr)
        return 1

    print("AI SEO Operating System → PDF")
    assets = fetch_assets()

    for d in DOCS:
        d.slug = doc_slug(d.path)
        render_doc(d)
        print(f"  {d.path:32s} {len(d.sections):3d} sections  {d.span}")

    # Second pass: cross-references need every section's anchor to exist first.
    for d in DOCS:
        d.html = link_cross_references(d.html)
    print(f"  {len(SECTION_ANCHORS)} numbered sections indexed for cross-linking")

    CACHE.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(assets), encoding="utf-8")
    asyncio.run(print_pdf(OUT_HTML, OUT_PDF))

    size = OUT_PDF.stat().st_size / 1_048_576
    print(f"\n{OUT_PDF}  ({size:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
