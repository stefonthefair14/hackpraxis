"""A deliberately small Markdown-to-HTML converter.

HackPraxis ships its learning content as Markdown. Rather than take a dependency
just to render a few docs, this handles the subset the content uses: headings,
paragraphs, unordered/ordered lists, fenced and inline code, bold, links and
horizontal rules. It escapes HTML first, so content is safe to inject.
"""

from __future__ import annotations

import html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+?)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = _CODE.sub(lambda m: f"<code>{m.group(1)}</code>", text)
    text = _BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", text)
    text = _LINK.sub(lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>', text)
    return text


def render(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    list_type: str | None = None

    def close_list():
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None

    while i < len(lines):
        line = lines[i]

        # fenced code block
        if line.strip().startswith("```"):
            close_list()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(html.escape(lines[i], quote=False))
                i += 1
            i += 1  # skip closing fence
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            continue

        stripped = line.strip()

        if not stripped:
            close_list()
            i += 1
            continue

        if stripped.startswith("#"):
            close_list()
            level = len(stripped) - len(stripped.lstrip("#"))
            level = min(level, 6)
            out.append(f"<h{level}>{_inline(stripped[level:].strip())}</h{level}>")
            i += 1
            continue

        if stripped in ("---", "***", "___"):
            close_list()
            out.append("<hr>")
            i += 1
            continue

        # ordered list
        m_ol = re.match(r"^\d+\.\s+(.*)$", stripped)
        if m_ol:
            if list_type != "ol":
                close_list()
                out.append("<ol>")
                list_type = "ol"
            out.append(f"<li>{_inline(m_ol.group(1))}</li>")
            i += 1
            continue

        # unordered list
        if stripped.startswith(("- ", "* ")):
            if list_type != "ul":
                close_list()
                out.append("<ul>")
                list_type = "ul"
            out.append(f"<li>{_inline(stripped[2:])}</li>")
            i += 1
            continue

        # paragraph (gather consecutive non-blank, non-special lines)
        close_list()
        buf = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#|```|-\s|\*\s|\d+\.\s|---$)", lines[i].strip()
        ):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + _inline(" ".join(buf)) + "</p>")

    close_list()
    return "\n".join(out)
