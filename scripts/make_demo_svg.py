"""
Build docs/img/app-demo.svg and app-demo-dark.svg, the animated demo at the top of the README.

    python scripts/make_demo_svg.py [--shots DIR] [--reuse] [--quality 72] [--res 1.25] [--lang en|pl]

The demo is an illustration made of screenshots of the real app, not a recording. One loop of 13 s: the view rests
on the loss-making bestsellers, the cursor drags the bestseller slider from the top 500 to the top 200 (the value
next to the slider follows the drag, the numbers and the table change after the release, like the app's updatemode
"mouseup"), clicks the second product of the new table and the page scrolls to its product card: the card's own
margin cascade comes into view. Then the page glides back to the start, which is again the first frame.

The script starts the Dash app on 127.0.0.1 and takes full-page screenshots 960 CSS px wide at device scale factor 2
(headless Chrome or Edge on a free DevTools port, scripts/browser.py) of each state, set from the address:
the default view, the top 400 and top 300 (only the value next to the slider is used) and the top 200 with the card
of the clicked product. The numbers of each state come from product_profitability, the same code as the app and the
README, and the script stops if the app shows other numbers. Track, bar and thumb of the slider, the cursor, the
clicks and the scrollbar are vectors; scroll positions come from the screenshots' geometry.

Only CSS animations of transform and opacity inside the SVG, no script and no external file: GitHub shows README
images through <img>. With prefers-reduced-motion the image shows the end state (top 200) without motion. The two
files differ only in the browser frame (light and dark GitHub theme). --shots keeps the screenshots and geometry in
DIR; --reuse builds from them without starting the app; two builds from the same screenshots give the same bytes.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from browser import Browser, stop_tree, wait_for  # noqa: E402

from product_profitability import data, diagnose, margin, report  # noqa: E402
from product_profitability import theme as look  # noqa: E402

OUT_DIR = ROOT / "docs" / "img"
CSS_W, DSF = 960, 2  # app page width in CSS px, screenshot pixels per CSS px
VIEW = 640  # CSS px of the page in view
W = 1000  # SVG width
K = W / CSS_W
BAR = 36  # browser bar above the page
LIMIT = 500 * 1024  # bytes per SVG
EASE = "cubic-bezier(.65,0,.35,1)"
EASE_OUT = "cubic-bezier(.22,1,.36,1)"
INK = look.INK
CURSOR = "M0 0V17.2L4.3 13.3L7.2 20.1L10.3 18.8L7.5 12.2H13.2Z"  # arrow, tip at 0,0
FRAMES = {  # browser frame in GitHub's light and dark theme; the app keeps its own light page
    "light": {"bar": "#f6f8fa", "border": "#d0d7de", "dot": "#d0d7de", "pill": "#ffffff", "pill_text": "#57606a"},
    "dark": {"bar": "#161b22", "border": "#30363d", "dot": "#484f58", "pill": "#0d1117", "pill_text": "#8b949e"},
}
HIDDEN = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}

START, END = 500, 200  # bestsellers before and after the drag
STEPS_SHOWN = (400, 300)  # values passed on the way, each its own screenshot of the slider value
CLICK_ROW = 2  # the product opened from the new table (1 = the first row)

# Timeline (seconds)
T = 13.0
PRESS, RELEASE = 1.6, 2.7
LAG = 0.3  # the app recalculates after the release
CLICK = 4.4
TO_CARD = (4.7, 5.9)
TO_CHART = (6.6, 7.6)
RESET = 9.6  # the bestseller section goes back to the start while the card is in view
BACK = (9.8, 11.4)


def bestseller_rules(bestsellers: int) -> diagnose.Rules:
    return diagnose.Rules(bestsellers=bestsellers)


def numbers() -> dict:
    """What the app must show: loss-making bestsellers of the top 500 and top 200, the product to open."""
    shop = data.load()
    lines = margin.line_costs(shop)
    products = margin.product_margins(shop, lines)
    out = {}
    for n in (START, END):
        losing = diagnose.loss_making_bestsellers(products, bestseller_rules(n))
        loss = float(losing["true_margin"].sum())
        out[n] = {"count": f"{len(losing):,}", "loss": report.compact(loss), "rows": len(losing),
                  "count_pl": f"{len(losing):,}".replace(",", " "), "loss_pl": report.compact(loss, "pl")}
    table = report.loss_table(diagnose.loss_making_bestsellers(products, bestseller_rules(END)))
    pick = table.iloc[CLICK_ROW - 1]
    out["product_id"], out["product"] = int(pick["product_id"]), pick["product"]
    out["product_pl"] = report.loss_table(diagnose.loss_making_bestsellers(products, bestseller_rules(END)),
                                          "pl").iloc[CLICK_ROW - 1]["product"]
    first = report.loss_table(diagnose.loss_making_bestsellers(products, bestseller_rules(START))).iloc[0]
    out["start_product"] = first["product"]
    return out


def alt_text(values: dict, language: str = "pl") -> str:
    """The description of the demo, for the SVG title and the README <img alt>."""
    start, end = values[START], values[END]
    if language == "pl":
        return (f"Aplikacja Product Profitability w ilustracji: suwak bestsellerów przesuwa się z top {START} na top "
                f"{END}, liczba stratnych bestsellerów zmienia się z {start['count_pl']} na {end['count_pl']}, "
                f"a strata razem z {start['loss_pl']} na {end['loss_pl']} zł; kliknięcie produktu "
                f"{values['product_pl']} w tabeli otwiera jego kartę z kaskadą marży i listą zamówień.")
    return (f"Product Profitability app, illustrated: the bestseller slider moves from the top {START} to the top "
            f"{END}, loss-making bestsellers go from {start['count']} to {end['count']} and the loss together from "
            f"{start['loss']} to {end['loss']} PLN; a click on {values['product']} in the table opens its product "
            f"card with its margin cascade and order list.")


# ---- 1. screenshots ----------------------------------------------------------------------------------------------

STATES = {
    "base": {"bestsellers": START},
    **{f"top-{n}": {"bestsellers": n} for n in STEPS_SHOWN},
    "final": {"bestsellers": END, "product": None},  # the product to open is filled in from numbers()
}

GEOMETRY_JS = """(() => {
  const box = e => { const r = e.getBoundingClientRect();
    return {x: r.left, y: r.top + scrollY, w: r.width, h: r.height}; };
  const text = e => { const r = document.createRange(); r.selectNodeContents(e); return box(r); };
  const css = (e, pseudo) => { const s = getComputedStyle(e, pseudo);
    return {color: s.color, background: s.backgroundColor, border: s.borderTopColor,
            border_width: parseFloat(s.borderTopWidth) || 0}; };
  const rule = document.getElementById('bestsellers').closest('.pp-rule') ||
               document.querySelector('.pp-rule');
  const value = document.getElementById('bestsellers-value');
  const thumb = rule.querySelector('.mantine-Slider-thumb');
  return JSON.stringify({
    slider: {value: text(value), value_text: value.textContent, thumb: box(thumb), thumb_style: css(thumb),
             track: box(rule.querySelector('.mantine-Slider-track')),
             track_style: css(rule.querySelector('.mantine-Slider-track'), '::before'),
             bar: box(rule.querySelector('.mantine-Slider-bar')),
             bar_style: css(rule.querySelector('.mantine-Slider-bar')),
             min: +thumb.getAttribute('aria-valuemin'), max: +thumb.getAttribute('aria-valuemax'),
             now: +thumb.getAttribute('aria-valuenow')},
    losses: box(document.getElementById('losses')), stats: box(document.getElementById('loss-stats')),
    table: box(document.getElementById('loss-table')),
    stat_values: [...document.querySelectorAll('#loss-stats .dg-stat-value')].map(e => e.textContent),
    rows: document.querySelectorAll('#loss-table tbody tr').length,
    links: [...document.querySelectorAll('#loss-table .pp-open')].slice(0, 4).map(e => ({box: box(e),
                                                                                     text: e.textContent})),
    card_section: box(document.getElementById('product-card')), card: box(document.getElementById('card')),
    card_name: document.querySelector('#card h3').textContent,
    card_chart: box(document.querySelector('#card .dg-chart')),
    page_bg: getComputedStyle(document.querySelector('.dg-page')).backgroundColor,
    height: document.documentElement.scrollHeight});
})()"""


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def capture(port: int, shots: Path, values: dict) -> None:
    geometry = {}
    async with Browser() as page:
        await page.viewport(CSS_W, 900, DSF)
        for name, query in STATES.items():
            query = {**query, "product": values["product_id"]} if "product" in query else query
            address = "&".join(f"{key}={value}" for key, value in query.items())
            await page.open(f"http://127.0.0.1:{port}/?{address}")
            card = values["product"] if name == "final" else values["start_product"]
            label = json.dumps("top {}".format(query["bestsellers"]))
            await page.until("document.querySelectorAll('#loss-table tbody tr').length > 0 && "
                             "document.querySelectorAll('#card tbody tr').length > 0 && "
                             f"document.getElementById('bestsellers-value').textContent === {label} && "
                             f"document.querySelector('#card h3').textContent === {json.dumps(card)}")
            await page.js("document.fonts.ready.then(() => true)")
            await page.js("document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0)")
            await page.send("Input.dispatchMouseEvent", type="mouseMoved", x=2, y=2)
            await asyncio.sleep(1.5)
            height = await page.js("document.documentElement.scrollHeight")
            shot = await page.send("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                                   clip={"x": 0, "y": 0, "width": CSS_W, "height": height, "scale": 1})
            (shots / f"{name}.png").write_bytes(base64.b64decode(shot["data"]))
            geometry[name] = json.loads(await page.js(GEOMETRY_JS))
            print(name, height, " | ".join(geometry[name]["stat_values"][:2]), "|", geometry[name]["card_name"])
    (shots / "geometry.json").write_text(json.dumps(geometry, indent=1), encoding="utf-8")


def take_screenshots(shots: Path, values: dict) -> None:
    port = free_port()
    env = {**os.environ, "MPLBACKEND": "Agg", "PP_PORT": str(port)}
    app = subprocess.Popen([sys.executable, "-m", "ui.app"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, **HIDDEN)
    try:
        wait_for(f"http://127.0.0.1:{port}/")
        asyncio.run(capture(port, shots, values))
    finally:
        stop_tree(app)


def check(geo: dict, values: dict) -> None:
    """Stop when the screenshots are not these states, show other numbers or have a layout the overlays break."""
    if set(geo) != set(STATES):
        sys.exit("The screenshots are not the states of this script: run without --reuse.")
    for name, n in (("base", START), ("final", END)):
        shown = geo[name]["stat_values"][:2]
        wanted = [values[n]["count"], values[n]["loss"]]
        if shown != wanted or geo[name]["rows"] != values[n]["rows"]:
            sys.exit(f"The app shows {shown} ({geo[name]['rows']} rows) for {name}, the model gives {wanted} "
                     f"({values[n]['rows']} rows): retake the screenshots.")
    if geo["base"]["links"][CLICK_ROW - 1]["text"] == values["product"]:
        sys.exit("The clicked product is already in the same row before the drag: the demo would show no change.")
    for key in ("losses", "stats", "card_section"):
        if abs(geo["base"][key]["y"] - geo["final"][key]["y"]) > 2:
            sys.exit(f"{key} moves between the states ({geo['base'][key]['y']:.0f} / {geo['final'][key]['y']:.0f}): "
                     "the overlays would not line up.")


# ---- 2. animation ------------------------------------------------------------------------------------------------

class Motion:
    """CSS keyframes on one timeline. Each track: (seconds, value, easing to the next stop)."""

    def __init__(self, total: float):
        self.total = total
        self.css: list[str] = []
        self.count = 0

    def track(self, prop: str, stops: list, rest) -> str:
        """A class animating prop through stops; rest is the value without motion (prefers-reduced-motion)."""
        self.count += 1
        name = f"m{self.count}"
        stops = sorted(stops, key=lambda s: s[0])
        if stops[0][0] > 0:
            stops.insert(0, (0, stops[0][1], "linear"))
        if stops[-1][0] < self.total:
            stops.append((self.total, stops[-1][1], "linear"))
        frames = "".join(f"{s / self.total * 100:.3f}%{{{prop}:{value};animation-timing-function:{ease}}}"
                         for s, value, ease in stops)
        self.css.append(f"@keyframes {name}{{{frames}}}.{name}{{{prop}:{rest};"
                        f"animation:{name} {self.total:g}s linear 0s infinite both}}")
        return name


def ease_io(u: float) -> float:
    return 4 * u**3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def path_value(stops: list[tuple[float, float]], t: float) -> float:
    """Value at time t of a path through (time, value) stops, eased between them and held outside."""
    if t <= stops[0][0]:
        return stops[0][1]
    for (t0, v0), (t1, v1) in zip(stops, stops[1:], strict=False):
        if t <= t1:
            return v0 + (v1 - v0) * ease_io((t - t0) / (t1 - t0)) if t1 > t0 else v1
    return stops[-1][1]


def tr(x: float, y: float) -> str:
    return f"translate({x:.1f}px,{y:.1f}px)"


def css_color(value: str) -> str:
    """rgb(1, 2, 3) to #010203."""
    parts = [int(float(p)) for p in value[value.index("(") + 1:value.index(")")].split(",")[:3]]
    return "#{:02x}{:02x}{:02x}".format(*parts)


def scroll_positions(geo: dict) -> dict[str, float]:
    """Where the view rests: the bestseller section with the clicked row, the card, the card's own cascade."""
    base, final = geo["base"], geo["final"]
    row = final["links"][CLICK_ROW - 1]["box"]
    start = min(base["losses"]["y"] - 16, row["y"] + row["h"] + 60 - VIEW)
    card = final["card_section"]["y"] - 16
    chart = final["card_chart"]
    return {"start": start, "card": card, "chart": max(card, chart["y"] + chart["h"] + 24 - VIEW)}


def switch(on: float, off: float | None = None, fade: float = 0.22) -> list:
    """Opacity: hidden until `on`, shown until `off` (or the end of the loop)."""
    stops = [(0, 0, "linear"), (on, 0, EASE), (on + fade, 1, "linear")]
    if off is not None:
        stops += [(off, 1, "linear"), (off + 0.01, 0, "linear")]
    return stops


def build(shots: Path, quality: int, res: float, language: str) -> tuple[dict[str, str], dict]:
    geo = json.loads((shots / "geometry.json").read_text(encoding="utf-8"))
    values = numbers()
    check(geo, values)
    base, final = geo["base"], geo["final"]
    images = {name: Image.open(shots / f"{name}.png").convert("RGB") for name in geo}
    for name, im in images.items():
        if im.width != CSS_W * DSF:
            sys.exit(f"{name}.png is not {CSS_W} CSS px at device scale factor {DSF}: run without --reuse.")
    page_bg = css_color(base["page_bg"])
    y = scroll_positions(geo)
    height = max(base["height"], final["height"])
    if y["card"] - y["start"] < VIEW + 20:
        sys.exit("The product card is in view together with the bestsellers: the loop would show the switch.")

    def image(name: str, x0: float, y0: float, x1: float, y1: float) -> str:
        """Part of a screenshot (CSS px box) as a WebP <image> in page px."""
        crop = images[name].crop((round(x0 * DSF), round(y0 * DSF), round(x1 * DSF), round(y1 * DSF)))
        size = (max(1, round((x1 - x0) * K * res)), max(1, round((y1 - y0) * K * res)))
        buffer = io.BytesIO()
        crop.resize(size, Image.LANCZOS).save(buffer, "WEBP", quality=quality, method=6)
        encoded = base64.b64encode(buffer.getvalue()).decode()
        return (f'<image x="{x0 * K:.2f}" y="{y0 * K:.2f}" width="{(x1 - x0) * K:.2f}" height="{(y1 - y0) * K:.2f}" '
                f'preserveAspectRatio="none" href="data:image/webp;base64,{encoded}"/>')

    m = Motion(T)
    page: list[str] = []  # page coordinates, moved by the scroll
    view: list[str] = []  # fixed in the view: cursor, click rings, scrollbar

    # 1. the page: the default view; the bestsellers after the drag; the card of the clicked product
    page.append(f'<rect width="{CSS_W * K:.2f}" height="{height * K:.2f}" fill="{page_bg}"/>')
    page.append(image("base", 0, max(0, y["start"] - 8), CSS_W, base["height"]))
    s = final["stats"]
    losses_end = final["losses"]["y"] + final["losses"]["h"]
    page.append(f'<g class="{m.track("opacity", switch(RELEASE + LAG, RESET), 1)}">'
                f'{image("final", 0, s["y"] - 6, CSS_W, losses_end)}</g>')
    c = final["card_section"]
    card_off = m.track("opacity", switch(TO_CARD[0]), 1)
    cover = (f'<rect y="{final["height"] * K:.2f}" width="{CSS_W * K:.2f}" '
             f'height="{(height - final["height"]) * K:.2f}" fill="{page_bg}"/>' if height > final["height"] else "")
    page.append(f'<g class="{card_off}">{image("final", 0, c["y"] - 6, CSS_W, final["height"])}{cover}</g>')

    # 2. the slider: a patch over it, then track, bar and thumb as vectors moving with the drag
    times = [round(i / 50, 2) for i in range(int(T * 50) + 1)]
    stops = [(0, START), (PRESS, START), (RELEASE, END), (RESET, END), (RESET + 0.01, START)]
    r = base["slider"]
    tx, tw = r["track"]["x"], r["track"]["w"]
    cy = r["thumb"]["y"] + r["thumb"]["h"] / 2
    radius = r["thumb"]["w"] / 2
    bar_x, end = r["bar"]["x"], tx + tw + radius
    line_h = r["bar"]["h"]

    def x_of(v: float) -> float:
        return tx + (v - r["min"]) / (r["max"] - r["min"]) * tw

    page.append(f'<rect x="{(bar_x - 8) * K:.2f}" y="{(cy - radius - 4) * K:.2f}" '
                f'width="{(end - bar_x + 16) * K:.2f}" height="{(2 * radius + 8) * K:.2f}" fill="{page_bg}"/>')
    bar = f'y="{(cy - line_h / 2) * K:.2f}" height="{line_h * K:.2f}" rx="{line_h * K / 2:.2f}"'
    full = end - bar_x
    page.append(f'<rect x="{bar_x * K:.2f}" width="{full * K:.2f}" {bar} '
                f'fill="{css_color(r["track_style"]["background"])}"/>')
    moving = [t for t in times if PRESS <= t <= RELEASE]
    keys = sorted({0.0, T, *[t for t, _ in stops], *moving})
    rest_x, final_x = x_of(START), x_of(END)
    fill = m.track("transform", [(t, f"scaleX({(x_of(path_value(stops, t)) + radius - bar_x) / full:.4f})", "linear")
                                 for t in keys], f"scaleX({(final_x + radius - bar_x) / full:.4f})")
    page.append(f'<g transform="translate({bar_x * K:.2f} 0)"><rect class="{fill}" width="{full * K:.2f}" {bar} '
                f'fill="{css_color(r["bar_style"]["background"])}"/></g>')
    move = m.track("transform", [(t, tr((x_of(path_value(stops, t)) - rest_x) * K, 0), "linear") for t in keys],
                   tr((final_x - rest_x) * K, 0))
    ts = r["thumb_style"]
    ring = ts["border_width"]
    page.append(f'<g class="{move}"><circle cx="{rest_x * K:.2f}" cy="{cy * K:.2f}" r="{(radius - ring / 2) * K:.2f}" '
                f'fill="{css_color(ts["background"])}" stroke="{css_color(ts["border"])}" '
                f'stroke-width="{ring * K:.2f}"/></g>')
    # the value next to the label follows the drag: one screenshot crop per value passed
    crops = {START: "base", **{n: f"top-{n}" for n in STEPS_SHOWN}, END: "final"}
    widest = max(geo[name]["slider"]["value"]["w"] for name in crops.values())
    vb = base["slider"]["value"]
    right = vb["x"] + vb["w"]
    shown_values = sorted(crops, reverse=True)
    for v in shown_values[1:]:
        # shown while the slider is nearest to v (steps of 100)
        on = [min(shown_values, key=lambda n, t=t: abs(n - path_value(stops, t))) == v for t in times]
        track = [(0, int(on[0]), "linear")]
        for i in range(1, len(times)):
            if on[i] != on[i - 1]:
                track += [(times[i] - 0.001, int(on[i - 1]), "linear"), (times[i], int(on[i]), "linear")]
        crop = image(crops[v], right - widest - 6, vb["y"] - 3, right + 3, vb["y"] + vb["h"] + 3)
        page.append(f'<g class="{m.track("opacity", track, int(v == END))}">{crop}</g>')

    # 3. the scroll: the page glides between the views, a scrollbar thumb follows
    scroll = [(0, y["start"]), (TO_CARD[0], y["start"]), (TO_CARD[1], y["card"]), (TO_CHART[0], y["card"]),
              (TO_CHART[1], y["chart"]), (BACK[0], y["chart"]), (BACK[1], y["start"]), (T, y["start"])]
    scroll_stops = [(t, v, EASE if i + 1 < len(scroll) and scroll[i + 1][1] != v else "linear")
                    for i, (t, v) in enumerate(scroll)]
    scrolling = m.track("transform", [(t, tr(0, -v * K), e) for t, v, e in scroll_stops], tr(0, -y["start"] * K))
    thumb_h = VIEW * VIEW / height
    room = VIEW - thumb_h - 6

    def thumb_y(v: float) -> float:
        return v / (height - VIEW) * room

    scrollbar = m.track("transform", [(t, tr(0, thumb_y(v) * K), e) for t, v, e in scroll_stops],
                        tr(0, thumb_y(y["start"]) * K))
    view.append(f'<rect class="{scrollbar}" x="{(CSS_W - 7) * K:.2f}" y="{3 * K:.2f}" width="{4 * K:.2f}" '
                f'height="{thumb_h * K:.2f}" rx="{2 * K:.2f}" fill="{INK}" opacity="0.28"/>')

    # 4. the cursor (view coordinates): rest, drag the slider, open the second product, rest
    rest = (760, 470)
    grab = (x_of(START), cy - y["start"])
    link = final["links"][CLICK_ROW - 1]["box"]
    target = (link["x"] + min(link["w"] / 2, 90), link["y"] + link["h"] / 2 - y["start"])
    path = [(0, rest, "linear"), (0.6, rest, EASE), (PRESS - 0.1, grab, "linear")]
    path += [(t, (x_of(path_value(stops, t)), cy - y["start"]), "linear") for t in times if PRESS <= t <= RELEASE]
    path += [(RELEASE + 0.5, (x_of(END), cy - y["start"]), EASE), (CLICK - 0.12, target, "linear"),
             (TO_CARD[0] + 0.2, target, EASE), (TO_CARD[1] + 0.4, rest, "linear")]
    cursor_move = m.track("transform", [(t, tr(px * K, py * K), e) for t, (px, py), e in path],
                          tr(rest[0] * K, rest[1] * K))
    cursor_show = m.track("opacity", [(0, 1, "linear")], 0)
    press = [(0, "scale(1)", "linear")]
    for down, up in ((PRESS, RELEASE), (CLICK, CLICK + 0.12)):
        press += [(down - 0.08, "scale(1)", EASE_OUT), (down, "scale(.88)", "linear"), (up, "scale(.88)", EASE_OUT),
                  (up + 0.18, "scale(1)", "linear")]
    cursor_press = m.track("transform", press, "scale(1)")
    accent = css_color(r["bar_style"]["background"])
    for t0, (px, py) in ((PRESS, grab), (CLICK, target)):
        ring_cls = m.track("transform", [(t0, "scale(.2)", EASE_OUT), (t0 + 0.5, "scale(1)", "linear"),
                                         (t0 + 0.51, "scale(.2)", "linear")], "scale(1)")
        fade = m.track("opacity", [(t0 - 0.01, 0, "linear"), (t0, 0.45, EASE_OUT), (t0 + 0.5, 0, "linear")], 0)
        view.append(f'<g transform="translate({px * K:.1f} {py * K:.1f})"><g class="{fade}"><circle class="{ring_cls}" '
                    f'r="18" fill="{accent}" fill-opacity="0.35"/></g></g>')
    view.append(f'<g class="{cursor_show}"><g class="{cursor_move}"><g class="{cursor_press}">'
                f'<path d="{CURSOR}" transform="scale(1.15)" fill="{INK}" stroke="#ffffff" stroke-width="1.3" '
                f'stroke-linejoin="round" filter="url(#shadow)"/></g></g></g>')

    alt = alt_text(values, language)
    vh = VIEW * K
    H = BAR + vh
    css = "".join(m.css) + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    content = (f'<g clip-path="url(#view)"><g transform="translate(0 {BAR})"><g class="{scrolling}">{"".join(page)}'
               f'</g>{"".join(view)}</g></g>')
    out = {}
    for theme, colors in FRAMES.items():
        dots = "".join(f'<circle cx="{18 + i * 16}" cy="{BAR / 2}" r="5" fill="{colors["dot"]}"/>' for i in range(3))
        host, pill_w = "127.0.0.1:8050", 150
        out[theme] = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" width="{W}" height="{H:.0f}" '
            f'role="img" aria-label="{alt}"><title>{alt}</title><defs><style>{css}</style>'
            f'<clipPath id="frame"><rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1:.1f}" rx="10"/></clipPath>'
            f'<clipPath id="view"><rect x="0" y="{BAR}" width="{W}" height="{vh:.1f}"/></clipPath>'
            f'<filter id="shadow" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="1.2" '
            f'stdDeviation="1.4" flood-color="#000" flood-opacity="0.35"/></filter></defs>'
            f'<g clip-path="url(#frame)"><rect width="{W}" height="{H:.1f}" fill="{page_bg}"/>{content}'
            f'<rect width="{W}" height="{BAR}" fill="{colors["bar"]}"/>'
            f'<line x1="0" y1="{BAR - 0.5}" x2="{W}" y2="{BAR - 0.5}" stroke="{colors["border"]}"/>{dots}'
            f'<rect x="{W / 2 - pill_w / 2}" y="{BAR / 2 - 11}" width="{pill_w}" height="22" rx="11" '
            f'fill="{colors["pill"]}" stroke="{colors["border"]}"/>'
            f'<text x="{W / 2}" y="{BAR / 2 + 4.3}" text-anchor="middle" font-size="12.5" '
            f'fill="{colors["pill_text"]}" style="font-family:ui-monospace,SFMono-Regular,Consolas,monospace">'
            f'{host}</text></g>'
            f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1:.1f}" rx="10" fill="none" '
            f'stroke="{colors["border"]}"/></svg>')
    return out, {"alt": alt, **values}


def make(shots: Path | None = None, reuse: bool = False, quality: int = 72, res: float = 1.25,
         language: str = "pl") -> dict:
    """Screenshots (unless reuse), then both SVG files; returns the alt text and the numbers shown."""
    shots = shots or ROOT / "output" / "demo-shots"
    shots.mkdir(parents=True, exist_ok=True)
    if not (reuse and (shots / "geometry.json").exists()):
        take_screenshots(shots, numbers())
    svgs, shown = build(shots, quality, res, language)
    for theme, svg in svgs.items():
        path = OUT_DIR / ("app-demo.svg" if theme == "light" else "app-demo-dark.svg")
        path.write_text(svg, encoding="utf-8", newline="\n")
        print(f"{path.name}: {path.stat().st_size / 1024:.0f} KB, loop {T:g} s")
        if path.stat().st_size > LIMIT:
            sys.exit(f"{path.name} is over {LIMIT // 1024} KB: lower --quality or --res.")
    return shown


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shots", type=Path, help="keep the screenshots and geometry in this folder")
    parser.add_argument("--reuse", action="store_true", help="build from --shots without starting the app")
    parser.add_argument("--quality", type=int, default=72, help="WebP quality of the screenshots")
    parser.add_argument("--res", type=float, default=1.25, help="image pixels per SVG pixel")
    parser.add_argument("--lang", choices=("pl", "en"), default="en", help="language of the description")
    args = parser.parse_args()
    make(args.shots, args.reuse, args.quality, args.res, args.lang)


if __name__ == "__main__":
    main()
