import re
import markdown
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# Regex para ecuaciones LaTeX
MATH_BLOCK_RE = re.compile(r'\$\$(.+?)\$\$', re.S)   # $$...$$
MATH_INLINE_RE = re.compile(r'\$(.+?)\$')            # $...$

def replace_math(md_text: str) -> str:
    """
    Sustituye las ecuaciones LaTeX para que se rendericen con MathJax:
    - $...$   → \( ... \)
    - $$...$$ → \[ ... \]
    """
    md_text = MATH_BLOCK_RE.sub(lambda m: f"\\\\[{m.group(1).strip()}\\\\]", md_text)
    md_text = MATH_INLINE_RE.sub(lambda m: f"\\\\({m.group(1).strip()}\\\\)", md_text)
    return md_text

def markdown_to_html(md_text: str) -> str:
    """
    Convierte Markdown a HTML completo con soporte de tablas, código,
    tachado, listas, citas y ecuaciones LaTeX via MathJax.
    """
    # 1. Sustituir fórmulas LaTeX
    md_text = replace_math(md_text)

    # 2. Markdown -> HTML (fragmento)
    body_html = markdown.markdown(
        md_text,
        extensions=[
            "tables",        # tablas
            "fenced_code",   # bloques de código ```
            "sane_lists",    # listas consistentes
            "nl2br",         # saltos de línea automáticos
            "toc",           # tabla de contenidos
            "pymdownx.tilde" # ~~tachado~~
        ]
    )

    # 3. Envolver en HTML completo con CSS + MathJax
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

    # 4. Compactar en una sola línea (evita problemas en n8n)
    return " ".join(full_html.split())


@app.post("/html")
def make_html():
    """
    Endpoint principal: recibe JSON con {"markdown": "..."}
    y devuelve HTML completo (una sola línea) con MathJax y CSS.
    """
    data = request.get_json(silent=True)
    if not data or "markdown" not in data:
        return jsonify({"error": "Bad request: falta 'markdown'"}), 400

    md_text = data["markdown"]
    html = markdown_to_html(md_text)

    return Response(html, mimetype="text/html")

# ⚠️ Nota: En Render se ejecuta con Gunicorn, ejemplo:
# gunicorn -w 4 -b 0.0.0.0:$PORT main:app
