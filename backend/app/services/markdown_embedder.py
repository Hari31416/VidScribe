import base64
import mimetypes
import re
from pathlib import Path

IMG_INLINE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
IMG_HTML_RE = re.compile(r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'][^>]*>)', re.I)
DEFAULT_PREAMBLE = r"""date: \today
lang: en
toc: true
toc-depth: 3
toc-title: "Table of Contents"
toc-own-page: true
numbersections: true
papersize: a4
fontsize: 11pt
geometry:
  - margin=1in
linestretch: 1.1
colorlinks: true
linkcolor: blue
urlcolor: blue
pdf-engine: xelatex
listings: true
header-includes:
    - \usepackage{listings}
    - \usepackage{booktabs}
    - \usepackage{array}
    - \usepackage{xcolor}
    - \usepackage{minted}
    - \usepackage{microtype}
    - \usepackage{parskip}
    - \usemintedstyle{default}"""

DEFAULT_PREAMBLE_WITHOUT_TOC = r"""date: \today
lang: en
numbersections: true
papersize: a4
fontsize: 11pt
geometry:
  - margin=1in
linestretch: 1.1
colorlinks: true
linkcolor: blue
urlcolor: blue
pdf-engine: xelatex
listings: true
header-includes:
    - \usepackage{listings}
    - \usepackage{booktabs}
    - \usepackage{array}
    - \usepackage{xcolor}
    - \usepackage{minted}
    - \usepackage{microtype}
    - \usepackage{parskip}
    - \usemintedstyle{default}"""


def guess_mime(path: Path) -> str:
    mt, _ = mimetypes.guess_type(path.name)
    return mt or "application/octet-stream"


def to_data_uri(p: Path) -> str:
    b = p.read_bytes()
    b64 = base64.b64encode(b).decode("ascii")
    return f"data:{guess_mime(p)};base64,{b64}"


def parse_title(url: str):
    m = re.match(r'(.+?)\s+["\'](.*)["\']\s*$', url)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return url.strip(), None


def make_id_from_path(p: Path, existing: set, base="img"):
    stem = re.sub(r"[^a-z0-9]+", "-", p.stem.lower())
    cand = stem or base
    i = 1
    ident = cand
    while ident in existing:
        i += 1
        ident = f"{cand}-{i}"
    return ident


def collect_existing_ids(md: str) -> set:
    ref_def = re.compile(r"^\[([^\]]+)\]:\s+\S+", re.M)
    return set(m.group(1) for m in ref_def.finditer(md))


def convert_markdown(md_path: Path, assign_ids_from="filename") -> str:  # or "seq"
    md = md_path.read_text(encoding="utf-8")
    md_dir = md_path.parent
    existing_ids = collect_existing_ids(md)
    defs = []  # footer definitions we will append
    id_map = {}  # local path -> id to dedupe

    def convert_one_markdown(match):
        alt = match.group(1)
        url_full = match.group(2).strip()
        url, title = parse_title(url_full)

        if re.match(r"^(https?://|data:)", url, re.I):
            return match.group(0)  # leave as is

        abs_path = (md_dir / url).resolve()
        if not abs_path.exists():
            return match.group(0)  # keep original if missing

        if url not in id_map:
            if assign_ids_from == "filename":
                ident = make_id_from_path(abs_path, existing_ids)
            else:
                ident = make_id_from_path(
                    Path(f"img{id_map.__len__()+1}"), existing_ids
                )
            existing_ids.add(ident)
            id_map[url] = ident
            defs.append((ident, to_data_uri(abs_path), title))

        ident = id_map[url]
        if title:
            return f"![{alt}][{ident}]"
        else:
            return f"![{alt}][{ident}]"

    body = IMG_INLINE_RE.sub(convert_one_markdown, md)

    # Convert <img> tags similarly; generate an ID and replace with reference-style Markdown
    def convert_one_html(match):
        pre, url, post = match.group(1), match.group(2).strip(), match.group(3)
        alt = ""  # could parse alt= from pre/post if present
        if re.match(r"^(https?://|data:)", url, re.I):
            return match.group(0)
        abs_path = (md_dir / url).resolve()
        if not abs_path.exists():
            return match.group(0)

        if url not in id_map:
            ident = make_id_from_path(abs_path, existing_ids)
            existing_ids.add(ident)
            id_map[url] = ident
            defs.append((ident, to_data_uri(abs_path), None))
        ident = id_map[url]
        return f"![{alt}][{ident}]"

    body = IMG_HTML_RE.sub(convert_one_html, body)

    # Prepare footer with definitions; preserve existing trailing whitespace/newlines
    footer_lines = []
    if not body.endswith("\n"):
        body += "\n"
    footer_lines.append("\n<!-- Embedded image data below -->\n")
    for ident, data_uri, title in defs:
        if title:
            footer_lines.append(f'[{ident}]: {data_uri} "{title}"\n')
        else:
            footer_lines.append(f"[{ident}]: {data_uri}\n")

    return body + "".join(footer_lines)


def _guess_title(md_path: Path) -> str:
    md = md_path.read_text(encoding="utf-8")
    for line in md.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return (
                line.lstrip("#")
                .strip()
                .replace("-", " ")
                .replace("_", " ")
                .replace(":", " ")
            )

    return md_path.stem.replace("-", " ").replace("_", " ").replace(":", " ").title()


def embed_images_reference_style(
    input_md: Path, output_md: Path, preamble=DEFAULT_PREAMBLE
):
    rewritten = convert_markdown(input_md)
    if preamble:
        title = _guess_title(input_md)
        preamble = f"title: {title}\n" + preamble
        rewritten = f"---\n{preamble}\n---\n\n{rewritten}"
    output_md.write_text(rewritten, encoding="utf-8")
