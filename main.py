import re
import markdown
from flask import Flask, request, jsonify, Response
from latex2mathml.converter import convert

app = Flask(__name__)

# Regex para fórmulas LaTeX en Markdown
MATH_INLINE_RE = re.compile(r'\$(.+?)\$')
MATH_BLOCK_RE  = re.compile(r'\$\$(.+?)\$\$')

def markdown_to_html(md_text: str) -> str:
    """
    Convierte Markdown a HTML con soporte extendido y
    transformación de fórmulas LaTeX ($...$, $$...$$) a MathML.
    """

    # --- Paso 1: transformar fórmulas ---
    md_text = MATH_BLOCK_RE.sub(
        lambda m: convert(m.group(1).replace("\n", " ")),
        md_text
    )
    md_text = MATH_INLINE_RE.sub(
        lambda m: convert(m.group(1)),
        md_text
    )

    # --- Paso 2: Markdown -> HTML ---
    html = markdown.markdown(
        md_text,
        extensions=[
            "tables",
            "fenced_code",
            "sane_lists",
            "nl2br",
            "toc"
        ]
    )

    # --- Paso 3: Compactar en una sola línea ---
    html = " ".join(html.split())

    return html


@app.post("/html")
def make_html():
    """
    Endpoint principal: recibe JSON con {"markdown": "..."}
    y devuelve HTML en una sola línea con MathML.
    """
    data = request.get_json(silent=True)
    if not data or "markdown" not in data:
        return jsonify({"error": "Bad request: falta 'markdown'"}), 400

    md_text = data["markdown"]
    html = markdown_to_html(md_text)

    return Response(html, mimetype="text/html")

# ⚠️ Nota: Render levantará esto con gunicorn main:app
