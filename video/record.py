# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright"]
# ///
# uv run video/record.py, after `uv run actas web`. Needs Google Chrome and ffmpeg.
# FRAMES=<folder> keeps the frames; PREVIEW=0.5,5.2 only captures the frames at those seconds.

import functools
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
STATIC = ROOT / "src/actas/web/static"
FPS = 30
STAGE_W = 360
PHONE_W = 414
REST_SCALE = 0.70
REST_Y = 196
POSTER_AT = 5.2  # seconds: the home page, with the bars of the companies
END_LEN = 3.0
TYPED = "piscina cubierta"
TOWN = json.loads((ROOT / "analisis/municipio.json").read_text(encoding="utf-8"))


def clamp(u: float) -> float:
    return min(1.0, max(0.0, u))


def span(t: float, a: float, b: float) -> float:
    return clamp((t - a) / (b - a))


def inout(u: float) -> float:
    u = clamp(u)
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def out(u: float) -> float:
    return 1 - (1 - clamp(u)) ** 4


def lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


HIDDEN = {"o": 0, "blur": 0, "y": 0}
SHOWN = {"o": 1, "blur": 0, "y": 0}


def text(t: float, t_in: float, t_out: float | None, dur_in: float = 0.45, dur_out: float = 0.3) -> dict:
    if t < t_in:
        return HIDDEN
    if t < t_in + dur_in:
        e = out(span(t, t_in, t_in + dur_in))
        return {"o": e, "blur": (1 - e) * 8, "y": (1 - e) * 12}
    if t_out is None or t < t_out:
        return SHOWN
    if t < t_out + dur_out:
        e = inout(span(t, t_out, t_out + dur_out))
        return {"o": 1 - e, "blur": e * 8, "y": -e * 12}
    return HIDDEN


def tap(t: float, at: float, x: float, y: float) -> dict | None:
    if not at <= t < at + 0.6:
        return None
    u = (t - at) / 0.6
    if u < 0.45:
        e = out(u / 0.45)
        return {"x": x, "y": y, "o": 0.9 * e, "scale": lerp(1.5, 1.0, e)}
    e = inout((u - 0.45) / 0.55)
    return {"x": x, "y": y, "o": 0.9 * (1 - e), "scale": lerp(1.0, 1.25, e)}


def keyframes(points: list[tuple[float, float]], t: float) -> float:
    if t <= points[0][0]:
        return points[0][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t < t1:
            return lerp(v0, v1, inout(span(t, t0, t1)))
    return points[-1][1]


def s_home(t, g):
    return {"scroll": lerp(0, g["h1"]["top"] - 14, inout(span(t, 2.3, 4.1))),
            "tap": tap(t, 5.25, g["bar"]["x"], g["bar"]["y"] - (g["h1"]["top"] - 14))}


def s_entity(t, g):
    return {"scroll": lerp(g["h1"]["top"] - 60, g["h1"]["top"] + 190, inout(span(t, 1.0, 3.4)))}


def s_decisions(t, g):
    return {"scroll": lerp(g["h1"]["top"] - 14, g["edition"]["top"] - 150, inout(span(t, 0.35, 3.0)))}


def s_permits(t, g):
    return {"scroll": lerp(g["h1"]["top"] - 14, g["table"]["top"] - 90, inout(span(t, 0.35, 3.1)))}


def s_votes(t, g):
    return {"scroll": lerp(g["h1"]["top"] - 14, g["same"]["top"] - 14, inout(span(t, 2.0, 3.8)))}


def s_search(t, g):
    # Until the results come, the page is too short to scroll down to the heading: start from where it can be.
    top = min(g["h1"]["top"] - 14, g["room"]["top"])
    return {"scroll": lerp(top, g["h1"]["top"] - 14 + 190, inout(span(t, 3.0, 4.3))),
            "tap": tap(t, 0.45, g["q"]["x"], g["q"]["y"] - top),
            "focus": t >= 0.6,
            "typed": TYPED[:round(len(TYPED) * span(t, 1.0, 2.5))]}


def first(sel, contains=None):
    return f"""(() => {{
      const e = [...document.querySelectorAll({sel!r})].find(e => {contains!r} === null || e.textContent.includes({contains!r}));
      if (!e) throw new Error("No está en la página: " + {sel!r});
      const r = e.getBoundingClientRect();
      return {{top: r.top + scrollY, x: r.left + r.width / 2, y: r.top + scrollY + r.height / 2}};
    }})()""".replace("None", "null")


# The sentences avoid figures, so the video does not age with the data.
SCENES = [
    {"url": "index.html", "dur": 6.4, "caption": "El dinero, empresa por empresa",
     "measure": {"h1": first("main h1"), "bar": first("ol.bars a")}, "state": s_home},
    {"url": "{entity}", "dur": 3.8,
     "caption": "Contratos, pagos y subvenciones de cada una", "measure": {"h1": first("main h1")}, "state": s_entity},
    {"url": "{year}/decisiones/", "dur": 4.2, "caption": "Cada reunión, contada en lenguaje llano",
     "measure": {"h1": first("main h1"), "edition": first(".edition")}, "state": s_decisions},
    {"url": "{year}/permisos/", "dur": 3.6, "caption": "Quién pide licencias de obra y de actividad",
     "measure": {"h1": first("main h1"), "table": first("main table")}, "state": s_permits},
    {"url": "votaciones/", "dur": 4.4, "caption": "Cómo vota cada grupo en el Pleno",
     "measure": {"h1": first("main h1"), "same": first("main h2", "Cuántas veces")}, "state": s_votes},
    {"url": "buscar/", "dur": 4.6, "caption": "Busca una calle, un tema o una empresa",
     "measure": {"h1": first("main h1"), "q": first("#q"),
                 "room": "({top: document.documentElement.scrollHeight - innerHeight})"}, "state": s_search},
]
START = []
_t = 0.0
for _s in SCENES:
    START.append(_t)
    _t += _s["dur"]
END_AT = _t
TOTAL = END_AT + END_LEN

ZOOM = [(0, 1.0), (3.7, 1.0), (5.0, 1.12), (START[1], 1.12), (START[2] - 0.2, 1.04), (START[2], 1.04),
        (START[3] - 0.6, 1.14), (START[3], 1.14), (START[4] - 0.2, 1.06), (START[4], 1.06), (START[4] + 1.6, 1.2),
        (START[4] + 2.0, 1.2), (START[5] - 0.2, 1.06), (START[5], 1.06), (START[5] + 1.0, 1.14), (TOTAL, 1.14)]


def entry(t: float) -> float:
    return lerp(560, 0, out(span(t, 1.0, 1.9)))


def end_wipe(t: float) -> float:
    return out(span(t, END_AT, END_AT + 0.55))


def state(t: float, k: int, local: dict) -> dict:
    last = len(SCENES) - 1
    zoom = keyframes(ZOOM, t)
    scale = REST_SCALE * zoom
    speed = abs(entry(t + 1 / FPS) - entry(t)) * FPS
    phone = {"x": STAGE_W / 2 - PHONE_W / 2 * scale, "y": REST_Y + entry(t), "scale": scale,
             "mblur": min(12.0, speed / 200)}
    s0, s1 = START[k], START[k] + SCENES[k]["dur"]
    screen = {"o": 1, "blur": 0}
    if k > 0 and t < s0 + 0.28:
        e = out(span(t, s0, s0 + 0.28))
        screen = {"o": e, "blur": (1 - e) * 10}
    elif k < last and t > s1 - 0.25:
        e = inout(span(t, s1 - 0.25, s1))
        screen = {"o": 1 - e, "blur": e * 10}
    captions = [HIDDEN] * len(SCENES)
    captions[k] = text(t, 1.65 if k == 0 else s0 + 0.05, None if k == last else s1 - 0.3)
    wipe = end_wipe(t)
    end_speed = abs(end_wipe(t + 1 / FPS) - wipe) * FPS * 640
    return {"brand": text(t, 0.15, 1.1, dur_in=0.6, dur_out=0.35), "captions": captions, "phone": phone,
            "screen": screen, "tap": local.get("tap"),
            "end": {"p": wipe, "mblur": min(14.0, end_speed / 300), "text": text(t, END_AT + 0.35, None, 0.55)}}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(folder: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                             functools.partial(QuietHandler, directory=str(folder)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


HIDE_SCROLLBAR = "html { scrollbar-width: none; scroll-behavior: auto !important; }"


def site_paths() -> dict[str, str]:
    home = (WEB / "index.html").read_text(encoding="utf-8")
    entity = re.search(r'<ol class="bars">.*?<a href="([^"]+)"', home, re.S).group(1)
    year = max(int(p.name) for p in WEB.iterdir() if p.is_dir() and p.name.isdigit())
    return {"entity": entity, "year": str(year)}


def load(frame, site: str, k: int, paths: dict[str, str]) -> dict:
    if k > 0:  # the notice is shown on the first page only, as on a real visit after closing it
        frame.evaluate("sessionStorage.setItem('notice-closed', '1')")
    frame.goto(site + SCENES[k]["url"].format(**paths))
    frame.wait_for_load_state("load")
    frame.add_style_tag(content=HIDE_SCROLLBAR)
    return {name: frame.evaluate(js) for name, js in SCENES[k]["measure"].items()}


def record(frames_dir: Path, only: set[int] | None = None) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        stage_dir = Path(tmp)
        (stage_dir / "stage.html").write_bytes((ROOT / "video/stage.html").read_bytes())
        (stage_dir / "site").symlink_to(WEB)
        server, port = serve(stage_dir)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="chrome")
                page = browser.new_context(viewport={"width": STAGE_W, "height": 640},
                                           device_scale_factor=3).new_page()
                page.goto(f"http://127.0.0.1:{port}/stage.html")
                page.evaluate("t => setCaptions(t)", [s["caption"] for s in SCENES])
                address = re.sub(r"^https://|/$", "", TOWN["web"].get("direccion", ""))
                page.evaluate("b => setBrand(b[0], b[1], b[2])", [TOWN["web"]["nombre"], TOWN["municipio"], address])
                paths = site_paths()
                frame = page.query_selector("#site").content_frame()
                site = f"http://127.0.0.1:{port}/site/"
                current, measured, typed, focused = -1, {}, "", False
                for i in range(round(TOTAL * FPS)):
                    t = i / FPS
                    k = max(j for j, s0 in enumerate(START) if s0 <= t)
                    if k != current:
                        measured = load(frame, site, k, paths)
                        current, typed, focused = k, "", False
                    if only is not None and i not in only:
                        continue
                    local = SCENES[k]["state"](t - START[k], measured)
                    frame.evaluate("y => window.scrollTo({top: y, behavior: 'instant'})", round(local["scroll"]))
                    if local.get("focus") and not focused:
                        frame.focus("#q")
                        focused = True
                    if local.get("typed", "") != typed:
                        typed = local["typed"]
                        frame.evaluate("""v => { const q = document.getElementById('q'); q.value = v;
                                          q.dispatchEvent(new Event('input', {bubbles: true})); }""", typed)
                        if typed == TYPED:
                            frame.wait_for_function("/\\d/.test(document.getElementById('status').textContent)")
                        page.wait_for_timeout(120)
                    page.evaluate("s => setState(s)", state(t, k, local))
                    page.screenshot(path=frames_dir / f"{i:05d}.png")
                    if i % FPS == 0:
                        print(f"\r{t:4.0f} s / {TOTAL:.0f} s", end="", flush=True)
                print()
                browser.close()
        finally:
            server.shutdown()


def encode(frames_dir: Path) -> None:
    STATIC.mkdir(parents=True, exist_ok=True)
    video, poster = STATIC / "presentacion.mp4", STATIC / "presentacion.jpg"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", str(frames_dir / "%05d.png"),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p", "-profile:v", "high",
                    "-movflags", "+faststart", "-an", str(video)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(frames_dir / f"{round(POSTER_AT * FPS):05d}.png"),
                    "-vf", "scale=720:-1", "-q:v", "4", str(poster)], check=True)
    print(f"{video.relative_to(ROOT)} ({video.stat().st_size / 1e6:.1f} MB) y {poster.relative_to(ROOT)}")


def main() -> None:
    if not (WEB / "index.html").exists():
        sys.exit("Falta la web: ejecuta antes «uv run actas web».")
    keep, preview = os.environ.get("FRAMES"), os.environ.get("PREVIEW")
    with tempfile.TemporaryDirectory() as tmp:
        frames_dir = Path(keep) if keep else Path(tmp)
        frames_dir.mkdir(parents=True, exist_ok=True)
        if preview:
            record(frames_dir, {round(float(x) * FPS) for x in preview.split(",")})
            return
        record(frames_dir)
        encode(frames_dir)


if __name__ == "__main__":
    main()
