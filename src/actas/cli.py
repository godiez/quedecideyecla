import argparse
from pathlib import Path

from actas import catalog, municipality, sync
from actas.config import DB_PATH, PDF_DIR, PUBLIC_REPO, ROOT
from actas.http import Fetcher


def _status(conn) -> None:
    rows = conn.execute(
        "SELECT kind, COUNT(*) n, SUM(local_path IS NOT NULL) d, MIN(session_date) a, MAX(session_date) b,"
        " SUM(session_date IS NULL) nd, COALESCE(SUM(size_bytes), 0) sz FROM minutes GROUP BY kind"
    ).fetchall()
    for r in rows:
        print(f"{r['kind']:16} {r['n']:4} actas, {r['d']:4} en disco, {r['a']} → {r['b']},"
              f" {r['nd']} sin fecha, {r['sz'] / 1e6:.0f} MB")
    print("\nPor año:")
    for r in conn.execute(
        "SELECT substr(session_date, 1, 4) y, SUM(kind = 'jgl_minutes') j, SUM(kind = 'plenary_minutes') p"
        " FROM minutes GROUP BY y ORDER BY y"
    ):
        print(f"  {r['y'] or 'sin fecha'}: JGL {r['j']:3}  Pleno {r['p']:3}")


def _review(args) -> None:
    import webbrowser

    from actas.revision.server import create_server

    analysis = ROOT / "analisis" / args.year
    srv = create_server(analysis, PDF_DIR, args.db, args.port)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"Revisión en {url} (Ctrl+C para salir). Decisiones en {analysis / 'revision.json'}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def _check(args) -> None:
    from actas import checks

    errors = 0
    for year in args.years:
        analysis = ROOT / "analisis" / str(year)
        if not (analysis / "json").is_dir():
            raise SystemExit(f"No hay análisis en {analysis / 'json'}")
        errors += checks.run(analysis)
    if errors:
        raise SystemExit(f"{errors} errores en las votaciones o nombres de personas: mira los ERROR de arriba")


def _web(args) -> None:
    from actas.web import build

    written = build.build_site(ROOT / "analisis", args.db, args.out)
    print(f"{len(written)} páginas en {args.out}")
    print(f"Para verla: python3 -m http.server -d {args.out} 8010  →  http://127.0.0.1:8010/")


def _publish(args) -> None:
    from actas import public
    from actas.web import publish

    # Always regenerated: that way what is published matches the current analysis and passed the privacy check.
    _web(args)
    try:
        source = public.export(ROOT, args.to)
    except ValueError as err:
        raise SystemExit(str(err))
    print(f"Código y datos: {'commit ' + source[:7] if source else 'sin cambios'} en {args.to} (rama main)")
    h = publish.publish(args.out, args.to, args.branch, env=public.AUTHOR)
    print(f"Web: rama {args.branch} en el commit {h[:7]}. No se ha subido nada.")
    print("Para subirlo (cada rama tiene un solo commit, sin historial, por eso --force):")
    print(f"  git -C {args.to} push --force origin main {args.branch}")
    remote = f"{municipality.load().code_url}.git" if municipality.load().code_url else "<url>"
    print(f"La primera vez: crea el repositorio público en GitHub, «git -C {args.to} remote add origin {remote}» y, en "
          f"GitHub, Settings → Pages → Deploy from a branch → {args.branch}, carpeta / (root).")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="actas")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover", help=f"Registra las actas publicadas en {municipality.load().council_domain}")
    d.add_argument("--first-year", type=int)
    d.add_argument("--last-year", type=int)
    f = sub.add_parser("fetch", help="Descarga las actas registradas que no están en disco")
    f.add_argument("--local-dir", type=Path, action="append", default=[],
                   help="Carpeta con PDF ya descargados (se reutilizan por nombre de fichero)")
    f.add_argument("--limit", type=int)
    f.add_argument("--delay", type=float, default=1.0, help="Segundos entre peticiones")
    sub.add_parser("status", help="Resumen del catálogo")
    e = sub.add_parser("extras", help="PDF de otras carpetas que no están en el catálogo")
    e.add_argument("dirs", type=Path, nargs="+")
    c = sub.add_parser("check", help="Comprueba el análisis de un año: votaciones, importes, dinero y resumen")
    c.add_argument("years", type=int, nargs="+")
    r = sub.add_parser("review", help="Abre la herramienta de revisión del análisis en el navegador")
    r.add_argument("--year", default="2026")
    r.add_argument("--port", type=int, default=8766)
    r.add_argument("--no-open", action="store_true", help="No abrir el navegador")
    w = sub.add_parser("web", help="Genera la web estática a partir del análisis")
    w.add_argument("--out", type=Path, default=ROOT / "web")
    pub = sub.add_parser("publish", help="Regenera la web y prepara el repositorio público: código y datos "
                                          "publicables en main y la web en gh-pages (sin hacer push)")
    pub.add_argument("--out", type=Path, default=ROOT / "web")
    pub.add_argument("--to", type=Path, default=PUBLIC_REPO, help="Repositorio público (se crea si no existe)")
    pub.add_argument("--branch", default="gh-pages")
    args = ap.parse_args(argv)

    if args.cmd == "publish":
        return _publish(args)
    if args.cmd == "web":
        return _web(args)

    if args.cmd == "check":
        return _check(args)
    if args.cmd == "review":
        return _review(args)
    conn = catalog.connect(args.db)
    if args.cmd == "discover":
        print(sync.discover(conn, Fetcher(), args.last_year, args.first_year))
    elif args.cmd == "fetch":
        print(sync.fetch(conn, Fetcher(delay_s=args.delay), args.local_dir, args.limit))
    elif args.cmd == "status":
        _status(conn)
    elif args.cmd == "extras":
        for p in sync.extras(conn, args.dirs):
            print(p)


if __name__ == "__main__":
    main()
