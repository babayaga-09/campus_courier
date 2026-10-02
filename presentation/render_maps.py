"""Render the real CampusCourier floor map (world.py + Lab 1 A*) to PNGs for the deck."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, r"C:\Users\91750\OneDrive\Desktop\Autonomous Agents\CampusCourier")
import world

OUT = Path(__file__).parent
C, G, PAD = 44, 3, 40           # cell px, gap px, padding
COL = {"#": (10, 9, 8), ".": (58, 52, 44), "~": (31, 86, 115), "g": (110, 106, 28)}
BG = (16, 15, 13)
ROBOT = {"CB-1": (233, 180, 76), "CB-2": (88, 196, 221), "CB-3": (184, 216, 107)}
AMBER = (242, 178, 51)
F = lambda s, b=False: ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf" if b else r"C:\Windows\Fonts\arial.ttf", s)

def centre(x, y):
    return PAD + x * C + C // 2, PAD + y * C + C // 2

def base(labels=True, top_pad=0):
    w, h = PAD * 2 + world.WIDTH * C, PAD * 2 + world.HEIGHT * C + top_pad
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    for y, row in enumerate(world.ROWS):
        for x, ch in enumerate(row):
            k = ch if ch in COL else "."
            x0, y0 = PAD + x * C + G, PAD + y * C + G + top_pad
            d.rounded_rectangle([x0, y0, x0 + C - 2 * G, y0 + C - 2 * G], radius=4, fill=COL[k])
    return img

def locations(img, top_pad=0, labels=True):
    d = ImageDraw.Draw(img)
    for name, (x, y) in world.LOCATIONS.items():
        cx, cy = centre(x, y); cy += top_pad
        r = 13
        d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=BG, outline=AMBER, width=4)
        if labels:
            f = F(26, True)
            tw = d.textlength(name, font=f)
            tx = min(max(cx - tw / 2, 6), img.width - tw - 6)
            d.text((tx, cy - 50), name, font=f, fill=(236, 230, 219), stroke_width=5, stroke_fill=BG)

def route(img, path, color, top_pad=0):
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    pts = [(centre(x, y)[0], centre(x, y)[1] + top_pad) for x, y in path]
    gd.line(pts, fill=color + (110,), width=26, joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(7))
    img.paste(glow, (0, 0), glow)
    ImageDraw.Draw(img).line(pts, fill=color, width=8, joint="curve")

def robots(img, positions, top_pad=0):
    d = ImageDraw.Draw(img)
    for rid, (x, y) in positions.items():
        cx, cy = centre(x, y); cy += top_pad
        d.ellipse([cx - 15, cy - 15, cx + 15, cy + 15], fill=ROBOT[rid], outline=BG, width=5)

start = {"CB-1": (1, 1), "CB-2": (2, 1), "CB-3": (1, 2)}
goal = world.LOCATIONS["Studio 3"]

# Title / roadmap map: verified routes to Studio 3
img = base()
for rid in ("CB-2", "CB-1"):
    route(img, world.plan_route(start[rid], goal)["path"], ROBOT[rid])
locations(img, labels=False)
robots(img, start)
img.save(OUT / "map_routes.png")

# Situation map: labelled locations, hazards, no routes
img = base()
locations(img)
robots(img, start)
img.save(OUT / "map_labelled.png")

for rid in ("CB-1", "CB-2"):
    r = world.plan_route(start[rid], goal)
    print(rid, "steps", r["steps"], "gas", r["quiet_cells_on_route"], "wet", r["wet_cells_on_route"])
print(img.size)
