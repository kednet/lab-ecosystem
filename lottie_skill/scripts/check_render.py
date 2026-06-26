"""Sanity-check Lottie JSON: render 1 frame via lottie-python, check that all expected colors appear.

Usage: python check_render.py <animation.json> [--frame N]

If the output has only 1-2 unique non-white colors, layers are in wrong order
(bg is on top, covering everything).
"""
import argparse
import io
import json
import sys
from pathlib import Path

from lottie.exporters.svg import export_svg
from lottie.parsers.tgs import parse_tgs


def main():
    parser = argparse.ArgumentParser(description="Sanity-check Lottie JSON render")
    parser.add_argument("json_path", help="Path to Lottie JSON file")
    parser.add_argument("--frame", type=int, default=0, help="Frame to render (default 0)")
    parser.add_argument("--min-colors", type=int, default=2, help="Minimum expected non-white colors (default 2)")
    args = parser.parse_args()

    json_path = Path(args.json_path)
    if not json_path.exists():
        print(f"ERROR: file not found: {json_path}")
        sys.exit(1)

    # Parse and inspect
    with open(json_path, encoding="utf-8") as f:
        anim = parse_tgs(f)
    print(f"Loaded: {json_path.name}")
    print(f"  Size: {anim.width}x{anim.height}")
    print(f"  Duration: {anim.out_point - anim.in_point} frames @ {anim.frame_rate} fps "
          f"= {(anim.out_point - anim.in_point) / anim.frame_rate:.2f} sec")
    print(f"  Layers: {len(anim.layers)}")
    for L in anim.layers:
        nm = getattr(L, "name", "?")
        print(f"    - {nm}")
    print()

    # Render frame
    buf = io.BytesIO()
    export_svg(anim, buf, args.frame, pretty=False)
    svg = buf.getvalue().decode("utf-8").replace(
        "<?xml version='1.0' encoding='utf-8'?>", ""
    ).lstrip()

    # Save SVG next to source for inspection
    svg_out = json_path.with_suffix(f".frame{args.frame}.svg")
    svg_out.write_text(svg, encoding="utf-8")
    print(f"SVG saved: {svg_out}")
    print()

    # Render via Playwright + check colors
    try:
        from playwright.sync_api import sync_playwright
        from PIL import Image
        import collections
    except ImportError as e:
        print(f"Playwright/PIL not available: {e}")
        print("Install: pip install playwright pillow")
        print(f"Run: playwright install chromium")
        sys.exit(1)

    html_path = json_path.parent / f"_check_{args.frame}.html"
    html_path.write_text(
        f'<!DOCTYPE html><html><head><style>body{{margin:0;background:#fff}}svg{{display:block;width:{anim.width}px;height:{anim.height}px}}</style></head><body>{svg}</body></html>',
        encoding="utf-8",
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": anim.width, "height": anim.height})
        page = ctx.new_page()
        page.goto(f"file://{html_path.absolute()}", wait_until="load")
        page.wait_for_timeout(500)
        png_path = json_path.with_suffix(f".frame{args.frame}.png")
        page.screenshot(path=str(png_path), clip={"x": 0, "y": 0, "width": anim.width, "height": anim.height})
        browser.close()

    im = Image.open(png_path).convert("RGB")
    pixels = list(im.getdata())
    colors = collections.Counter(pixels)
    non_white = [(c, n) for c, n in colors.most_common(20) if c != (255, 255, 255)]

    print(f"Top 10 colors in rendered frame {args.frame}:")
    for c, n in colors.most_common(10):
        marker = " <-- background" if c == (255, 255, 255) else ""
        print(f"  rgb{c}: {n} px{marker}")
    print()

    # Extract expected colors from JSON
    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)
    expected_rgb = set()
    def walk(obj):
        if isinstance(obj, dict):
            if "c" in obj and isinstance(obj["c"], dict) and isinstance(obj["c"].get("k"), list) and len(obj["c"]["k"]) >= 3:
                k = obj["c"]["k"]
                if all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in k[:3]):
                    expected_rgb.add(tuple(int(round(x * 255)) for x in k[:3]))
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
    walk(raw)
    expected_rgb.discard((255, 255, 255))
    print(f"Expected fill colors (from JSON): {sorted(expected_rgb)}")
    print()

    # Check coverage
    seen = {c for c, _ in non_white}
    missing = expected_rgb - seen
    if missing:
        print(f"WARNING: expected colors NOT visible in render: {missing}")
        print("  Possible cause: layer order is wrong (bg covers everything).")
        print("  Fix: move 'background' layer to the END of layers[] array.")
    else:
        print(f"OK: all expected colors visible in render")
    print()

    # Cleanup
    html_path.unlink(missing_ok=True)

    # Summary
    n_unique = len(non_white)
    print(f"Result: {n_unique} unique non-white colors visible (min expected: {args.min_colors})")
    if n_unique < args.min_colors:
        print("FAIL: too few colors visible — likely layer order bug")
        sys.exit(1)
    else:
        print("PASS")


if __name__ == "__main__":
    main()
