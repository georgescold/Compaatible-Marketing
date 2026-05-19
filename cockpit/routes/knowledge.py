"""Routes Knowledge : recherche full-text + lecture intégrale des fichiers."""
from __future__ import annotations
from flask import Blueprint, abort, render_template, request

from brain import knowledge_search
from config import Config

bp = Blueprint("knowledge", __name__, url_prefix="/knowledge")


@bp.route("/")
def index():
    files = knowledge_search.list_files()
    query = (request.args.get("q") or "").strip()
    file_filter = request.args.get("file") or None

    results = []
    if query:
        results = knowledge_search.search(query, file_filter=file_filter, max_results=100)

    # Group results par fichier
    grouped: dict[str, list[dict]] = {}
    for r in results:
        grouped.setdefault(r["file"], []).append(r)

    return render_template(
        "knowledge.html",
        files=files,
        query=query,
        file_filter=file_filter,
        results=results,
        grouped=grouped,
    )


@bp.route("/file/<path:filename>")
def view_file(filename: str):
    """Affiche le contenu intégral d'un fichier de la knowledge base."""
    # Sécurité : interdire path traversal, n'autoriser que les .md dans Knowledges/
    if "/" in filename or "\\" in filename or ".." in filename or not filename.endswith(".md"):
        abort(404)

    path = Config.KNOWLEDGE_DIR / filename
    if not path.exists() or not path.is_file():
        abort(404)

    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        abort(500)

    files = knowledge_search.list_files()
    size_kb = path.stat().st_size // 1024
    line_count = content.count("\n") + 1

    return render_template(
        "knowledge_file.html",
        files=files,
        filename=filename,
        content=content,
        size_kb=size_kb,
        line_count=line_count,
    )
