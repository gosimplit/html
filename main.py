import re
import markdown
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# Regex LaTeX
MATH_BLOCK_RE = re.compile(r'\$\$(.+?)\$\$', re.S)   # $$...$$ (multilínea)
MATH_INLINE_RE = re.compile(r'\$(.+?)\$')            # $...$ (inline)

# Detectores de cabeceras / etiquetas de bloque tipo "Python:" / "JSON:"
HEADING_LINE_RE = re.compile(r'^\s*#{1,6}\s+')
LABEL_LINE_RE   = re.compile(r'^[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ]*:\s*$')

def autofence_code_blocks(md_text: str) -> str:
    """
    Convierte secciones que empiezan por 'Python:' o 'JSON:' (sin ``` explícitos)
    en bloques de código con fenced_code. Termina al encontrar línea vacía,
    otra etiqueta tipo X:, o una cabecera Markdown.
    """
    lines = md_text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped in ("Python:", "JSON:"):
            lang = "python" if stripped == "Python:" else "json"
            # capturar hasta corte
            j = i + 1
            block = []
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():  # línea en blanco => fin de bloque
                    break
                if HEADING_LINE_RE.match(nxt):  # nueva cabecera
                    break
                if LABEL_LINE_RE.match(nxt.strip()):  # otra etiqueta X:
                    break
                block.append(nxt)
                j += 1
            # envolver en fenced code
            code = "\n".join(block).strip()
            out.append(f"```{lang}\n{code}\n```")
            i = j  # saltar bloque
            continue
        out.append(line)
        i += 1
    return "\n".join(out)

def protect_math(md_text: str):
    """
    Sustituye fórmulas por marcadores seguros para que markdown no las altere.
    Luego las repondremos tal cual con \(..\) y \[..\] (MathJax).
    """
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

def restore_math(html: str, formulas: dict) -> str:
    for key, formula in formulas.items():
        html = html.replace(key, formula)
    return html

def markdown_to_html(md_text: str) -> str:
    """
    Convierte Markdown a HTML completo con:
      - Tablas, listas, código, citas, tachado
      - LaTeX protegido y rendereable con MathJax
      - CSS inline para bordes de tabla
      - TODO en una sola línea
    """
    # 0) Normalizar saltos (JSON suele venir con \\n)
    md_text = md_text.replace("\r\n", "\n").replace("\r", "\n").replace("\\n", "\n")

    # 1) Auto-fence para bloques "Python:" / "JSON:"
    md_text = autofence_code_blocks(md_text)

    # 2) Proteger fórmulas LaTeX con marcadores seguros
    md_text, formulas = protect_math(md_text)

    # 3) Markdown -> HTML (fragmento)
    body_html = markdown.markdown(
        md_text,
        extensions=[
            "tables",
            "fenced_code",
            "sane_lists",
            "nl2br",
            "toc",
            "pymdownx.tilde",   # ~~tachado~~
        ]
    )

    # 4) Restaurar fórmulas ( \(..\) y \[..\] para MathJax )
    body_html = restore_math(body_html, formulas)

    # 5) Envolver documento + CSS de bordes en tablas + MathJax
    full_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Markdown a HTML</title>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
  <style>
    table, th, td {{ border: 1px solid black; border-collapse: collapse; }}
    th, td {{ padding: 4px; }}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""

    # 6) Devolver en UNA SOLA LÍNEA (compat n8n)
    return " ".join(full_html.split())

@app.post("/html")
def make_html():
    data = request.get_json(silent=True)
    if not data or "markdown" not in data:
        return jsonify({"error": "Bad request: falta 'markdown'"}), 400
    md_text = data["markdown"]
    html = markdown_to_html(md_text)
    return Response(html, mimetype="text/html")

# En Render lánzalo con:
# gunicorn -w 4 -b 0.0.0.0:$PORT main:app
