import re
import markdown
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# Regex
MATH_BLOCK_RE = re.compile(r'\$\$(.+?)\$\$', re.S)   # $$...$$
MATH_INLINE_RE = re.compile(r'\$(.+?)\$')            # $...$

def protect_math(md_text: str):
    """
    Sustituye las fórmulas por marcadores temporales para que
    markdown.markdown no las rompa.
    """
    formulas = {}
    counter = 0

    # Bloques
    def repl_block(m):
        nonlocal counter
        key = f"__MATHBLOCK{counter}__"
        formulas[key] = f"\\[{m.group(1).strip()}\\]"
        counter += 1
        return key

    # Inline
    def repl_inline(m):
        nonlocal counter
        key = f"__MATHINLINE{counter}__"
        formulas[key] = f"\\({m.group(1).strip()}\\)"
        counter += 1
        return key

    md_text = MATH_BLOCK_RE.sub(repl_block, md_text)
    md_text = MATH_INLINE_RE.sub(repl_inline, md_text)

    return md_text, formulas

def restore_math(html: str, formulas: dict):
    """Reinserta las fórmulas en el HTML final."""
    for key, formula in formulas.items():
        html = html.replace(key, formula)
    return html

def markdown_to_html(md_text: str) -> str:
    # 1. Proteger fórmulas
    md_text, formulas = protect_math(md_text)

    # 2. Procesar Markdown
    body_html = markdown.markdown(
        md_text,
        extensions=[
            "tables",
            "fenced_code",
            "sane_lists",
            "nl2br",
            "toc",
            "pymdownx.tilde"
        ]
    )

    # 3. Restaurar fórmulas
    body_html = restore_math(body_html, formulas)

    # 4. Envolver en HTML completo + MathJax + CSS
    full_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Markdown a HTML</title>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
  <style>
    table, th, td {{
      border: 1px solid black;
      border-collapse: collapse;
    }}
    th, td {{
      padding: 4px;
    }}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""

    return " ".join(full_html.split())  # una sola línea

@app.post("/html")
def make_html():
    data = request.get_json(silent=True)
    if not data or "markdown" not in data:
        return jsonify({"error": "Bad request: falta 'markdown'"}), 400

    md_text = data["markdown"]
    html = markdown_to_html(md_text)

    return Response(html, mimetype="text/html")
