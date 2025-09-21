import re
import markdown
from flask import Flask, request, jsonify, Response, send_file
import io
import asyncio

app = Flask(__name__)

# Regex para LaTeX
MATH_BLOCK_RE = re.compile(r'\$\$(.+?)\$\$', re.S)
MATH_INLINE_RE = re.compile(r'\$(.+?)\$')

# Regex para bloques de código ```...```
CODEBLOCK_RE = re.compile(r'```.*?```', re.S)


def extract_codeblocks(md_text: str):
    codeblocks = {}
    counter = 0

    def repl(m):
        nonlocal counter
        key = f"§§CODE{counter}§§"
        codeblocks[key] = m.group(0)
        counter += 1
        return key

    md_text = CODEBLOCK_RE.sub(repl, md_text)
    return md_text, codeblocks


def restore_codeblocks(html: str, codeblocks: dict):
    for key, block in codeblocks.items():
        block_html = markdown.markdown(block, extensions=["fenced_code"])
        html = html.replace(key, block_html)
    return html


def protect_math(md_text: str):
    formulas = {}
    counter = 0

    def repl_block(m):
        nonlocal counter
        key = f"§§MATHBLOCK{counter}§§"
        formulas[key] = f"\\[{m.group(1).strip()}\\]"
        counter += 1
        return key

    def repl_inline(m):
        nonlocal counter
        key = f"§§MATHINLINE{counter}§§"
        formulas[key] = f"\\({m.group(1).strip()}\\)"
        counter += 1
        return key

    md_text = MATH_BLOCK_RE.sub(repl_block, md_text)
    md_text = MATH_INLINE_RE.sub(repl_inline, md_text)
    return md_text, formulas


def restore_math(html: str, formulas: dict):
    for key, formula in formulas.items():
        html = html.replace(key, formula)
    return html


def markdown_to_html(md_text: str) -> str:
    md_text = md_text.replace("\r\n", "\n").replace("\r", "\n").replace("\\n", "\n")
    md_text, codeblocks = extract_codeblocks(md_text)
    md_text, formulas = protect_math(md_text)

    body_html = markdown.markdown(
        md_text,
        extensions=[
            "tables",
            "fenced_code",
            "sane_lists",
            "nl2br",
            "pymdownx.tilde",
            "pymdownx.tasklist"
        ],
        extension_configs={
            "pymdownx.tasklist": {
                "custom_checkbox": True
            }
        }
    )

    body_html = restore_math(body_html, formulas)
    body_html = restore_codeblocks(body_html, codeblocks)

    full_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Markdown a HTML</title>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
  <style>
    table, th, td {{ border: 1px solid black; border-collapse: collapse; }}
    th, td {{ padding: 4px; }}
    @page {{ size: A4; margin: 18mm; }}
    .page-break {{ break-before: page; }}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""

    return " ".join(full_html.split())


@app.post("/html")
def make_html():
    data = request.get_json(silent=True)
    if not data or "markdown" not in data:
        return jsonify({"error": "Bad request: falta 'markdown'"}), 400

    md_text = data["markdown"]
    html = markdown_to_html(md_text)
    return Response(html, mimetype="text/html")


# -------- NUEVO: /html2pdf --------

PAGE_BREAK_TOKEN = r"\[NUEVA PÁGINA\]"

def normalize_html(raw_html: str) -> str:
    # Limpia saltos de línea alrededor del marcador
    cleaned = re.sub(r"\n*\s*\[NUEVA PÁGINA\]\s*\n*", "[NUEVA PÁGINA]", raw_html, flags=re.IGNORECASE)
    # Sustituye marcador por salto real
    return re.sub(PAGE_BREAK_TOKEN, '<div class="page-break"></div>', cleaned, flags=re.IGNORECASE)

async def html_to_pdf_bytes(html: str) -> bytes:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        try:
            await page.wait_for_function("window.MathJax && MathJax.typesetPromise", timeout=5000)
            await page.evaluate("return MathJax.typesetPromise()")
        except Exception:
            pass
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "18mm", "bottom": "18mm", "left": "18mm", "right": "18mm"}
        )
        await browser.close()
        return pdf_bytes

@app.post("/html2pdf")
def html2pdf():
    data = request.get_json(silent=True)
    if not data or "markdown" not in data:
        return jsonify({"error": "Bad request: falta 'markdown'"}), 400

    md_text = data["markdown"]
    html = markdown_to_html(md_text)
    html = normalize_html(html)

    pdf_bytes = asyncio.run(html_to_pdf_bytes(html))
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="documento.pdf"
    )


# Render lo lanza con:
# gunicorn -w 4 -b 0.0.0.0:$PORT main:app
