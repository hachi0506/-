"""FOOTBOZE FUTSAL Instagram リール用 PV レンダラー。

1080x1920 / 30fps / 30 秒のモーショングラフィックス PV を書き出す。
BGM は make_bgm.py が作る output/bgm.wav を使う（先に実行しておく）。

    python3 make_bgm.py
    python3 render_pv.py            # 本編 + カバー画像 + CapCut 用透過テロップ
    python3 render_pv.py --stills   # 確認用の静止画だけ書き出す

出力（output/）:
    FOOTBOZE_PV_reel.mp4   … そのまま投稿できる完成版（H.264 + AAC）
    cover.jpg              … リールのカバー画像
    overlays/*.png         … CapCut で実写素材に重ねる透過テロップ
"""
import math
import subprocess
import sys
import urllib.request
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).parent
OUT = ROOT / "output"
FONT_DIR = ROOT / "fonts"

W, H = 1080, 1920
FPS = 30
DURATION = 30.0
BEAT = 0.5  # 120 BPM

ORANGE = (255, 106, 0)
ORANGE_LIGHT = (255, 150, 60)
INK = (12, 12, 14)
WHITE = (246, 246, 244)
GRAY = (150, 150, 156)
DIM = (70, 70, 76)

# Google Fonts (SIL Open Font License) を GitHub から取得する
FONTS = {
    "dela": ("DelaGothicOne-Regular.ttf", "ofl/delagothicone/DelaGothicOne-Regular.ttf"),
    "anton": ("Anton-Regular.ttf", "ofl/anton/Anton-Regular.ttf"),
    "bebas": ("BebasNeue-Regular.ttf", "ofl/bebasneue/BebasNeue-Regular.ttf"),
    "noto": ("NotoSansJP[wght].ttf", "ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"),
}


def ensure_fonts():
    FONT_DIR.mkdir(exist_ok=True)
    for name, remote in FONTS.values():
        path = FONT_DIR / name
        if not path.exists():
            url = f"https://raw.githubusercontent.com/google/fonts/main/{remote}"
            print(f"downloading {url}")
            urllib.request.urlretrieve(url, path)


@lru_cache(maxsize=None)
def font(key, size, weight="Black"):
    f = ImageFont.truetype(str(FONT_DIR / FONTS[key][0]), size)
    if key == "noto":
        f.set_variation_by_name(weight)
    return f


# ---------------------------------------------------------------- easing
def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def prog(t, start, dur):
    return clamp01((t - start) / dur)


def ease_out_cubic(x):
    return 1 - (1 - x) ** 3


def ease_out_expo(x):
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x, s=1.9):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, x):
    return a + (b - a) * x


def mix(c1, c2, x):
    return tuple(int(lerp(a, b, x)) for a, b in zip(c1, c2))


# ---------------------------------------------------------------- sprites
@lru_cache(maxsize=None)
def text_sprite(text, key, size, fill=WHITE, weight="Black", tracking=0, stroke=0, stroke_fill=None):
    """テキストをタイトにトリミングした RGBA 画像にする（キャッシュ）。"""
    f = font(key, size, weight)
    pad = 8 + stroke
    if tracking == 0:
        box = f.getbbox(text, stroke_width=stroke)
        w, h = box[2] - box[0], box[3] - box[1]
        img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((pad - box[0], pad - box[1]), text, font=f, fill=fill,
                                 stroke_width=stroke, stroke_fill=stroke_fill)
        return img
    advances = [f.getlength(ch) + tracking for ch in text]
    total = int(sum(advances) - tracking)
    asc, desc = f.getmetrics()
    img = Image.new("RGBA", (total + pad * 2, asc + desc + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = pad
    for ch, adv in zip(text, advances):
        d.text((x, pad), ch, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        x += adv
    return img.crop(img.getbbox())


def with_alpha(spr, alpha):
    if alpha >= 0.999:
        return spr
    out = spr.copy()
    out.putalpha(spr.getchannel("A").point(lambda v: int(v * alpha)))
    return out


def blit(canvas, spr, cx, cy, scale=1.0, alpha=1.0, rot=0.0, anchor="c"):
    """スプライトを中心（または左端 anchor='l'）基準で合成する。"""
    if alpha <= 0.003 or scale <= 0.01:
        return
    s = spr
    if abs(scale - 1) > 1e-3:
        s = s.resize((max(1, int(s.width * scale)), max(1, int(s.height * scale))), Image.BICUBIC)
    if abs(rot) > 0.05:
        s = s.rotate(rot, resample=Image.BICUBIC, expand=True)
    s = with_alpha(s, alpha)
    x = int(cx - s.width / 2) if anchor == "c" else int(cx)
    y = int(cy - s.height / 2)
    paste(canvas, s, x, y)


def paste(canvas, s, x, y):
    if canvas.mode == "RGB":
        canvas.paste(s, (x, y), s)
        return
    # RGBA キャンバス（透過テロップ書き出し用）はクリップしてから合成
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.width, x + s.width), min(canvas.height, y + s.height)
    if x1 <= x0 or y1 <= y0:
        return
    canvas.alpha_composite(s.crop((x0 - x, y0 - y, x1 - x, y1 - y)), dest=(x0, y0))


def reveal(spr, frac, direction="lr"):
    """マスクワイプ：左から frac だけ見せる。"""
    frac = clamp01(frac)
    if frac >= 1:
        return spr
    out = Image.new("RGBA", spr.size, (0, 0, 0, 0))
    if direction == "lr":
        w = int(spr.width * frac)
        if w > 0:
            out.paste(spr.crop((0, 0, w, spr.height)), (0, 0))
    else:  # bottom -> top
        h = int(spr.height * frac)
        if h > 0:
            out.paste(spr.crop((0, spr.height - h, spr.width, spr.height)), (0, spr.height - h))
    return out


def rect_sprite(w, h, color, radius=0):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=color)
    return img


# ---------------------------------------------------------------- ball
@lru_cache(maxsize=None)
def ball_sprite(r=110):
    ss = 3
    R = r * ss
    img = Image.new("RGBA", (R * 2 + 4, R * 2 + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = R + 2
    d.ellipse((c - R, c - R, c + R, c + R), fill=(250, 250, 248, 255))

    def pent(cx, cy, rad, rot):
        return [(cx + rad * math.cos(rot + k * 2 * math.pi / 5),
                 cy + rad * math.sin(rot + k * 2 * math.pi / 5)) for k in range(5)]

    d.polygon(pent(c, c, R * 0.30, -math.pi / 2), fill=INK + (255,))
    for k in range(5):
        a = -math.pi / 2 + math.pi / 5 + k * 2 * math.pi / 5
        px, py = c + math.cos(a) * R * 0.86, c + math.sin(a) * R * 0.86
        d.polygon(pent(px, py, R * 0.30, a + math.pi), fill=INK + (255,))
        # 中央五角形から外側五角形へのシーム
        sx, sy = c + math.cos(a) * R * 0.30 * 0.81, c + math.sin(a) * R * 0.30 * 0.81
        d.line((sx, sy, px - math.cos(a) * R * 0.24, py - math.sin(a) * R * 0.24),
               fill=(90, 90, 96, 255), width=ss * 3)
    # 円の外にはみ出た部分を切り取る
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse((c - R, c - R, c + R, c + R), fill=255)
    img.putalpha(mask)
    # 陰影
    shade = Image.new("L", img.size, 0)
    ImageDraw.Draw(shade).ellipse((c - R * 0.95 + R * 0.35, c - R * 0.95 + R * 0.35,
                                   c + R * 1.4, c + R * 1.4), fill=110)
    shade = shade.filter(ImageFilter.GaussianBlur(R * 0.35))
    dark = Image.new("RGBA", img.size, (0, 0, 0, 255))
    dark.putalpha(Image.fromarray((np.asarray(shade, np.float32) * np.asarray(mask, np.float32) / 255).astype(np.uint8)))
    img = Image.alpha_composite(img, dark)
    return img.resize((r * 2 + 2, r * 2 + 2), Image.LANCZOS)


# ---------------------------------------------------------------- court (top-down futsal court)
PX_PER_M = 45
COURT_W, COURT_L = 20 * PX_PER_M, 40 * PX_PER_M
CX0, CY0 = (W - COURT_W) // 2, (H - COURT_L) // 2


def _arc(cx, cy, r, a0, a1, n=40):
    return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in np.linspace(a0, a1, n)]


def court_paths():
    m = PX_PER_M
    x0, y0, x1, y1 = CX0, CY0, CX0 + COURT_W, CY0 + COURT_L
    cx, cy = W / 2, H / 2
    paths = [
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
        [(x0, cy), (x1, cy)],
        _arc(cx, cy, 3 * m, 0, 2 * math.pi, 80),
    ]
    for gy, sgn in ((y0, 1), (y1, -1)):
        # ペナルティエリア：ゴールポストを中心にした半径 6m の 1/4 円 + 3.16m の直線
        lp_, rp_ = cx - 1.58 * m, cx + 1.58 * m
        left = _arc(lp_, gy, 6 * m, math.pi, math.pi / 2 if sgn > 0 else 3 * math.pi / 2, 30)
        right = _arc(rp_, gy, 6 * m, math.pi / 2 if sgn > 0 else 3 * math.pi / 2, 0 if sgn > 0 else 2 * math.pi, 30)
        paths.append(left + right)
        paths.append([(cx - 1.5 * m, gy), (cx - 1.5 * m, gy - sgn * 0.8 * m),
                      (cx + 1.5 * m, gy - sgn * 0.8 * m), (cx + 1.5 * m, gy)])
    return paths


COURT = court_paths()


def draw_court(canvas, frac, color, width=4):
    d = ImageDraw.Draw(canvas)
    for path in COURT:
        seg = [math.dist(a, b) for a, b in zip(path, path[1:])]
        total = sum(seg)
        remain = total * clamp01(frac)
        pts = [path[0]]
        for (a, b), L in zip(zip(path, path[1:]), seg):
            if remain <= 0:
                break
            if remain >= L:
                pts.append(b)
                remain -= L
            else:
                k = remain / L
                pts.append((lerp(a[0], b[0], k), lerp(a[1], b[1], k)))
                remain = 0
        if len(pts) > 1:
            d.line(pts, fill=color, width=width, joint="curve")


# ---------------------------------------------------------------- background layers
def radial_gradient(inner, outer, cx=W / 2, cy=H * 0.45, radius=1300):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / radius
    k = np.clip(dist, 0, 1)[..., None]
    arr = np.array(inner, np.float32) * (1 - k) + np.array(outer, np.float32) * k
    return Image.fromarray(arr.astype(np.uint8))


BG_DARK = None
VIGNETTE = None
GRAIN = None


def init_layers():
    global BG_DARK, VIGNETTE, GRAIN
    BG_DARK = radial_gradient((34, 30, 30), (8, 8, 10))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
    VIGNETTE = np.clip(1.08 - 0.55 * d ** 2.2, 0.35, 1.0)[..., None].astype(np.float32)
    rng = np.random.default_rng(7)
    GRAIN = [np.repeat(np.repeat(rng.normal(0, 4, (H // 2, W // 2)), 2, 0), 2, 1)[..., None].astype(np.float32)
             for _ in range(6)]


def dark_bg(t, court=1.0, court_alpha=0.16, zoom=0.0):
    canvas = BG_DARK.copy()
    if court > 0:
        draw_court(canvas, court, mix(INK, ORANGE, court_alpha), width=4)
    if zoom:
        s = 1 + zoom
        big = canvas.resize((int(W * s), int(H * s)), Image.BILINEAR)
        canvas = big.crop(((big.width - W) // 2, (big.height - H) // 2,
                           (big.width - W) // 2 + W, (big.height - H) // 2 + H))
    return canvas


def glow(canvas, cx, cy, radius, color, strength):
    """オレンジの光だまりを加算合成する。"""
    if strength <= 0:
        return canvas
    size = int(radius * 2)
    g = _glow_sprite(size)
    arr = np.asarray(canvas, np.float32)
    x0, y0 = int(cx - radius), int(cy - radius)
    xs0, ys0 = max(0, -x0), max(0, -y0)
    x0c, y0c = max(0, x0), max(0, y0)
    x1c, y1c = min(W, x0 + size), min(H, y0 + size)
    if x1c <= x0c or y1c <= y0c:
        return canvas
    patch = g[ys0:ys0 + (y1c - y0c), xs0:xs0 + (x1c - x0c)]
    arr[y0c:y1c, x0c:x1c] += patch * np.array(color, np.float32) * strength
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


@lru_cache(maxsize=None)
def _glow_sprite(size):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    return (np.clip(1 - d, 0, 1) ** 2.2)[..., None]


def speed_lines(canvas, t, seed, color, count=26, alpha=0.35):
    rng = np.random.default_rng(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(count):
        a = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(430, 700) + t * 900
        r1 = r0 + rng.uniform(250, 700)
        wdt = int(rng.uniform(2, 9))
        d.line((W / 2 + math.cos(a) * r0, H / 2 + math.sin(a) * r0,
                W / 2 + math.cos(a) * r1, H / 2 + math.sin(a) * r1),
               fill=color + (int(255 * alpha * rng.uniform(0.4, 1)),), width=wdt)
    canvas.paste(layer, (0, 0), layer)


# ---------------------------------------------------------------- text helpers
def pop_line(canvas, text, cx, cy, t, start, key="dela", size=150, fill=WHITE,
             stagger=0.045, dur=0.28, highlight=None, weight="Black"):
    """1 文字ずつ弾むように出す。highlight={文字index: 色}"""
    f = font(key, size, weight)
    advances = [f.getlength(ch) for ch in text]
    total = sum(advances)
    x = cx - total / 2
    for i, (ch, adv) in enumerate(zip(text, advances)):
        p = prog(t, start + i * stagger, dur)
        if p > 0:
            color = highlight.get(i, fill) if highlight else fill
            spr = text_sprite(ch, key, size, color, weight)
            sc = lerp(1.6, 1.0, ease_out_back(p, 2.2)) if p < 1 else 1.0
            dy = lerp(40, 0, ease_out_cubic(p))
            blit(canvas, spr, x + adv / 2, cy + dy, scale=sc, alpha=clamp01(p * 3))
        x += adv


def line_width(text, key, size, weight="Black"):
    return font(key, size, weight).getlength(text)


# ---------------------------------------------------------------- scenes
# 各シーン: fn(canvas, t) → canvas。t はグローバル秒。
# overlay=True のときは背景を描かず、テロップだけを透過キャンバスに描く。

def scene_hook(t, overlay=False, only=None):
    """0-3s：見極めろ。/ 決断しろ。/ 伝えろ。"""
    words = [("見極めろ。", "READ THE GAME"), ("決断しろ。", "MAKE THE CALL"), ("伝えろ。", "SHARE THE IDEA")]
    i = min(2, int(t)) if only is None else only
    lt = t - i
    jp, en = words[i]
    bg, fg, accent = [(INK, WHITE, ORANGE), (ORANGE, INK, WHITE), (INK, WHITE, ORANGE)][i]
    if overlay:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fg, accent = WHITE, ORANGE
    else:
        canvas = Image.new("RGB", (W, H), bg)
        if i != 1:
            canvas = glow(canvas, W / 2, H / 2, 700, ORANGE, 0.22)
        speed_lines(canvas, lt, 100 + i, fg if i == 1 else ORANGE, alpha=0.30 if i == 1 else 0.45)
    p = prog(lt, 0, 0.32)
    sc = lerp(1.18, 1.0, ease_out_expo(p))
    rot = lerp(-6, 0, ease_out_expo(p)) + lt * 1.2
    blit(canvas, text_sprite(jp, "dela", 176, fg), W / 2, H * 0.47, scale=sc * (1 + lt * 0.05), rot=rot)
    pe = prog(lt, 0.12, 0.3)
    blit(canvas, text_sprite(en, "anton", 58, accent, tracking=10), W / 2, H * 0.47 + 170,
         alpha=pe, scale=lerp(0.85, 1, ease_out_cubic(pe)))
    num = text_sprite(f"0{i + 1}", "anton", 64, accent)
    blit(canvas, num, W / 2, H * 0.47 - 175, alpha=pe)
    return canvas


def scene_logo(t, overlay=False):
    """3-6s：FOOTBOZE FUTSAL ロゴモーション"""
    lt = t - 3.0
    if overlay:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    else:
        canvas = dark_bg(t, court=ease_in_out(prog(lt, 0, 1.3)), court_alpha=0.28, zoom=0.03 * lt)
        canvas = glow(canvas, W / 2, H * 0.44, 650, ORANGE, 0.28 + 0.1 * math.sin(lt * 3))
    cy = H * 0.47
    # ボール：左下から転がり込んでロゴの上に止まる
    pb = ease_out_back(prog(lt, 0.0, 0.7), 1.4)
    bx, by = lerp(-160, W / 2, pb), lerp(H * 0.8, cy - 300, pb) - math.sin(prog(lt, 0, 0.7) * math.pi) * 180
    blit(canvas, ball_sprite(), bx, by, rot=-lerp(0, 540, ease_out_cubic(prog(lt, 0, 0.9))) - lt * 20)
    # FOOTBOZE：左からワイプ
    p1 = ease_out_expo(prog(lt, 0.05, 0.45))
    foot = text_sprite("FOOTBOZE", "anton", 250, WHITE, tracking=4)
    blit(canvas, reveal(foot, p1), W / 2 + lerp(-120, 0, p1), cy)
    # FUTSAL：右から
    p2 = ease_out_expo(prog(lt, 0.2, 0.45))
    futsal = text_sprite("FUTSAL", "anton", 132, ORANGE, tracking=38)
    blit(canvas, futsal, W / 2 + lerp(260, 0, p2), cy + 205, alpha=p2)
    # バー
    p3 = ease_out_cubic(prog(lt, 0.35, 0.5))
    if p3 > 0:
        bar = rect_sprite(max(2, int(640 * p3)), 10, ORANGE)
        blit(canvas, bar, W / 2, cy - 160)
    p4 = prog(lt, 0.6, 0.4)
    blit(canvas, text_sprite("フットボウズ・フットサル", "noto", 46, WHITE, "Bold", tracking=6),
         W / 2, cy + 320, alpha=p4, scale=lerp(0.9, 1, ease_out_cubic(p4)))
    p5 = prog(lt, 0.85, 0.4)
    blit(canvas, text_sprite("SINCE 1998  /  TOKYO MITAKA", "bebas", 60, GRAY, tracking=6),
         W / 2, cy + 400, alpha=p5)
    return canvas


def two_line_scene(t, start, l1, l2, sub, hi1=None, hi2=None, overlay=False, bg_seed=0,
                   size1=112, size2=138):
    lt = t - start
    if overlay:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    else:
        canvas = dark_bg(t, court=1.0, court_alpha=0.12, zoom=0.02 + 0.015 * lt)
        canvas = glow(canvas, W * (0.3 + 0.4 * bg_seed), H * 0.36, 620, ORANGE, 0.25)
    pop_line(canvas, l1, W / 2, H * 0.40, t, start + 0.02, size=size1, highlight=hi1)
    pop_line(canvas, l2, W / 2, H * 0.40 + 175, t, start + 0.22, size=size2, highlight=hi2)
    ps = prog(lt, 0.65, 0.35)
    if sub and ps > 0:
        bar = rect_sprite(int(90 * ease_out_cubic(ps)) + 1, 6, ORANGE)
        blit(canvas, bar, W / 2, H * 0.40 + 320)
        blit(canvas, text_sprite(sub, "noto", 42, GRAY, "Bold", tracking=2), W / 2, H * 0.40 + 390,
             alpha=ps, scale=lerp(0.92, 1, ease_out_cubic(ps)))
    return canvas


def scene_think(t, overlay=False):
    return two_line_scene(t, 6.0, "考えるのは、", "キミ自身だ。", "選手自身が考え、仲間と話す。",
                          hi2={0: ORANGE, 1: ORANGE, 2: ORANGE, 3: ORANGE}, overlay=overlay, bg_seed=0)


def scene_own_game(t, overlay=False):
    return two_line_scene(t, 8.0, "自分のゲームを、", "しよう。", "主体性 ── それが FOOTBOZE のスタイル",
                          hi1={0: ORANGE, 1: ORANGE}, overlay=overlay, bg_seed=1, size1=120, size2=170)


# 違い → チームの力：ばらばらの点がフォーメーションに集まる
PLAYERS = [  # (散らばり位置, フォーメーション位置, 半径, 色)
    ((170, 1030), (540, 1455), 44, WHITE),      # GK
    ((930, 1180), (300, 1210), 30, ORANGE),
    ((360, 1370), (780, 1210), 58, GRAY),
    ((820, 1450), (540, 1030), 38, ORANGE_LIGHT),
    ((560, 1120), (540, 850), 50, WHITE),       # ピヴォ
]
PASS_LINES = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (1, 2)]


def draw_players(canvas, t, gather):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    pos = []
    for k, (a, b, r, col) in enumerate(PLAYERS):
        wob = (1 - gather) * 14
        x = lerp(a[0], b[0], gather) + math.sin(t * 2.3 + k) * wob
        y = lerp(a[1], b[1], gather) + math.cos(t * 1.9 + k * 2) * wob
        pos.append((x, y, r, col))
    pl = prog(gather, 0.75, 0.25) if gather < 1 else 1.0
    for i, j in PASS_LINES:
        if pl <= 0:
            break
        (x1, y1, *_), (x2, y2, *_) = pos[i], pos[j]
        d.line((x1, y1, lerp(x1, x2, pl), lerp(y1, y2, pl)), fill=ORANGE + (200,), width=6)
    for x, y, r, col in pos:
        d.ellipse((x - r - 8, y - r - 8, x + r + 8, y + r + 8), fill=INK + (255,))
        d.ellipse((x - r, y - r, x + r, y + r), fill=col + (255,))
    canvas.paste(layer, (0, 0), layer)


def scene_diversity(t, overlay=False, only=None):
    """10-14s：違っていい → チームの力に"""
    part = (0 if t < 12 else 1) if only is None else only
    start = 10.0 if part == 0 else 12.0
    lt = t - start
    if overlay:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    else:
        canvas = dark_bg(t, court=1.0, court_alpha=0.14, zoom=0.01 * (t - 10))
        canvas = glow(canvas, W / 2, H * 0.62, 700, ORANGE, 0.18 + 0.12 * part)
        gather = 0.0 if part == 0 else ease_in_out(prog(lt, 0.0, 0.8))
        draw_players(canvas, t, gather)
    if part == 0:
        pop_line(canvas, "ひとりひとり、", W / 2, H * 0.22, t, start, size=108)
        pop_line(canvas, "違っていい。", W / 2, H * 0.22 + 165, t, start + 0.25, size=136,
                 highlight={0: ORANGE, 1: ORANGE})
    else:
        pop_line(canvas, "その違いが、", W / 2, H * 0.22, t, start, size=108)
        pop_line(canvas, "チームの力になる。", W / 2, H * 0.22 + 165, t, start + 0.2, size=112,
                 highlight={4: ORANGE})
    return canvas


def scene_powers(t, overlay=False):
    """14-18s：FOOTBOZE で身につく 3 つのチカラ"""
    lt = t - 14.0
    if overlay:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    else:
        canvas = dark_bg(t, court=1.0, court_alpha=0.10)
        canvas = glow(canvas, W * 0.85, H * 0.25, 600, ORANGE, 0.25)
    ph = ease_out_cubic(prog(lt, 0, 0.35))
    blit(canvas, text_sprite("FOOTBOZEで身につく", "noto", 46, GRAY, "Bold", tracking=4),
         W / 2, 380, alpha=ph)
    title_y = 490
    blit(canvas, text_sprite("3", "anton", 170, ORANGE), W / 2 - 250, title_y + 5,
         scale=lerp(1.6, 1, ease_out_back(prog(lt, 0.05, 0.35))), alpha=prog(lt, 0.05, 0.1))
    blit(canvas, text_sprite("つのチカラ", "dela", 112, WHITE), W / 2 + 70, title_y + 12, alpha=ph,
         scale=lerp(0.9, 1, ph))
    items = [("01", "見極める", "戦況を、自分の目で瞬時に。"),
             ("02", "決断する", "ベストな選択を、自分の頭で。"),
             ("03", "伝える", "決断を仲間に伝え、共に実行。")]
    for k, (num, head, sub) in enumerate(items):
        p = prog(lt, 0.55 + k * 0.8, 0.45)
        if p <= 0:
            continue
        e = ease_out_expo(p)
        y = 790 + k * 245
        x = 150 + lerp(500, 0, e)
        bar = rect_sprite(10, 170, ORANGE)
        blit(canvas, bar, x - 40, y + 40, alpha=e)
        blit(canvas, text_sprite(num, "anton", 96, ORANGE), x, y - 5, anchor="l", alpha=e)
        blit(canvas, text_sprite(head, "dela", 96, WHITE), x + 135, y, anchor="l", alpha=e)
        blit(canvas, text_sprite(sub, "noto", 40, GRAY, "Bold"), x + 140, y + 95, anchor="l",
             alpha=prog(lt, 0.75 + k * 0.8, 0.35))
    return canvas


def scene_records(t, overlay=False):
    """18-22s：実績"""
    lt = t - 18.0
    if overlay:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    else:
        canvas = dark_bg(t, court=1.0, court_alpha=0.10, zoom=0.012 * lt)
        canvas = glow(canvas, W / 2, H * 0.40, 800, ORANGE, 0.22)
    ph = prog(lt, 0, 0.3)
    blit(canvas, text_sprite("TRACK RECORD", "anton", 64, ORANGE, tracking=14), W / 2, 370, alpha=ph)
    cards = [
        ("全日本ユース(U-18)フットサル大会", "全国準優勝", ORANGE),
        ("東京都ユース(U-18)フットサルリーグ", "1部 優勝", WHITE),
        ("OB 清水和也 選手", "フットサル日本代表", WHITE),
    ]
    for k, (small, big, color) in enumerate(cards):
        p = prog(lt, 0.3 + k * 0.95, 0.4)
        if p <= 0:
            continue
        y = 610 + k * 300
        sc = lerp(1.7, 1.0, ease_out_expo(p))
        blit(canvas, text_sprite(small, "noto", 40, GRAY, "Bold", tracking=2), W / 2, y - 80,
             alpha=prog(lt, 0.4 + k * 0.95, 0.3))
        blit(canvas, text_sprite(big, "dela", 118 if k < 2 else 96, color), W / 2, y + 30, scale=sc,
             alpha=clamp01(p * 3))
        if k < 2:
            ln = ease_out_cubic(prog(lt, 0.55 + k * 0.95, 0.4))
            if ln > 0:
                blit(canvas, rect_sprite(int(700 * ln) + 1, 3, DIM), W / 2, y + 145)
    pf = prog(lt, 2.55, 0.35)
    blit(canvas, text_sprite("FIFAフットサルワールドカップ2021 出場", "noto", 38, ORANGE_LIGHT, "Bold"),
         W / 2, 610 + 2 * 300 + 120, alpha=pf)
    return canvas


def scene_categories(t, overlay=False):
    """22-25s：U-12 / U-15 / U-18"""
    lt = t - 22.0
    if overlay:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    else:
        pulse = 0.04 * ease_in_out(prog(lt, 2.0, 1.0))
        canvas = dark_bg(t, court=1.0, court_alpha=0.12, zoom=0.01 + pulse)
        canvas = glow(canvas, W / 2, H * 0.5, 800, ORANGE, 0.15 + 0.25 * prog(lt, 2.0, 1.0))
    ph = prog(lt, 0, 0.3)
    blit(canvas, text_sprite("育成年代専門のフットサルクラブ", "noto", 48, WHITE, "Black", tracking=3),
         W / 2, 420, alpha=ph, scale=lerp(0.9, 1, ease_out_cubic(ph)))
    tiles = [("U-12", "小学3〜6年生"), ("U-15", "中学生"), ("U-18", "高校生")]
    for k, (cat, grade) in enumerate(tiles):
        p = prog(lt, 0.2 + k * 0.3, 0.35)
        if p <= 0:
            continue
        e = ease_out_expo(p)
        side = -1 if k % 2 == 0 else 1
        y = 640 + k * 250
        x = W / 2 + side * lerp(900, 0, e)
        fill = ORANGE if k == 1 else WHITE
        ink = INK
        slab = rect_sprite(840, 200, fill, radius=18)
        blit(canvas, slab, x, y)
        blit(canvas, text_sprite(cat, "anton", 150, ink), x - 400, y, anchor="l")
        blit(canvas, text_sprite(grade, "dela", 58, ink), x + 380 - line_width(grade, "dela", 58) - 16, y + 8,
             anchor="l")
    pf = prog(lt, 1.4, 0.4)
    blit(canvas, text_sprite("小3から高3まで、ひとつのクラブで。", "noto", 44, GRAY, "Bold"), W / 2, 1420,
         alpha=pf)
    return canvas


def scene_goal(t, overlay=False):
    """25-27s：目指すは、日本一。"""
    lt = t - 25.0
    if overlay:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    else:
        canvas = Image.new("RGB", (W, H), INK)
        canvas = glow(canvas, W / 2, H * 0.5, 900, ORANGE, 0.55 + 0.1 * math.sin(lt * 6))
        speed_lines(canvas, lt * 0.6, 777, ORANGE_LIGHT, count=40, alpha=0.5)
        # 衝撃リング
        ring = ease_out_cubic(prog(lt, 0, 0.9))
        if 0 < ring < 1:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            r = lerp(80, 1100, ring)
            ImageDraw.Draw(layer).ellipse((W / 2 - r, H * 0.5 - r, W / 2 + r, H * 0.5 + r),
                                          outline=WHITE + (int(220 * (1 - ring)),), width=int(lerp(30, 4, ring)))
            canvas.paste(layer, (0, 0), layer)
    p0 = prog(lt, 0.0, 0.3)
    blit(canvas, text_sprite("目指すは、", "noto", 76, WHITE, "Black", tracking=4), W / 2, H * 0.5 - 220,
         alpha=p0, scale=lerp(0.85, 1, ease_out_cubic(p0)))
    p1 = prog(lt, 0.12, 0.4)
    sc = lerp(2.2, 1.0, ease_out_expo(p1)) * (1 + 0.03 * lt)
    blit(canvas, text_sprite("日本一。", "dela", 230, ORANGE if overlay else WHITE, stroke=0),
         W / 2, H * 0.5 + 20, scale=sc, alpha=clamp01(p1 * 4))
    p2 = prog(lt, 0.7, 0.4)
    blit(canvas, text_sprite("勝利を目指すゲームに、本気で。", "noto", 42, WHITE, "Bold"), W / 2, H * 0.5 + 230,
         alpha=p2)
    return canvas


def scene_end(t, overlay=False):
    """27-30s：エンドカード（練習参加の CTA）"""
    lt = t - 27.0
    if overlay:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    else:
        canvas = dark_bg(t, court=1.0, court_alpha=0.22, zoom=0.02 - 0.02 * ease_out_cubic(prog(lt, 0, 1.2)))
        canvas = glow(canvas, W / 2, H * 0.36, 700, ORANGE, 0.30)
    p = ease_out_expo(prog(lt, 0.0, 0.5))
    blit(canvas, ball_sprite(), W / 2, lerp(180, 360, p), scale=0.62, rot=-lt * 90, alpha=p)
    blit(canvas, text_sprite("FOOTBOZE", "anton", 190, WHITE, tracking=3), W / 2, 590, alpha=p,
         scale=lerp(1.2, 1, p))
    blit(canvas, text_sprite("FUTSAL", "anton", 100, ORANGE, tracking=30), W / 2, 745, alpha=p,
         scale=lerp(1.2, 1, p))
    p2 = ease_out_back(prog(lt, 0.35, 0.45), 1.6)
    if p2 > 0:
        cap = rect_sprite(860, 150, ORANGE, radius=75)
        blit(canvas, cap, W / 2, 960, scale=p2)
        blit(canvas, text_sprite("練習参加 受付中", "dela", 84, INK), W / 2, 958, scale=p2)
    p3 = prog(lt, 0.6, 0.4)
    blit(canvas, text_sprite("U-12 / U-15 / U-18", "anton", 76, WHITE, tracking=6), W / 2, 1115, alpha=p3)
    blit(canvas, text_sprite("東京都三鷹市", "noto", 42, GRAY, "Bold", tracking=6), W / 2, 1200, alpha=p3)
    p4 = prog(lt, 0.85, 0.4)
    blit(canvas, text_sprite("@footboze_futsal", "anton", 72, ORANGE_LIGHT, tracking=3), W / 2, 1330, alpha=p4,
         scale=lerp(0.9, 1, ease_out_cubic(p4)))
    blink = 0.65 + 0.35 * math.sin(lt * 7) if lt > 1.2 else 1
    blit(canvas, text_sprite("▶ 詳しくはプロフィールのリンクから", "noto", 40, WHITE, "Bold"), W / 2, 1415,
         alpha=prog(lt, 1.05, 0.4) * blink)
    return canvas


TIMELINE = [
    (0.0, 3.0, scene_hook),
    (3.0, 6.0, scene_logo),
    (6.0, 8.0, scene_think),
    (8.0, 10.0, scene_own_game),
    (10.0, 14.0, scene_diversity),
    (14.0, 18.0, scene_powers),
    (18.0, 22.0, scene_records),
    (22.0, 25.0, scene_categories),
    (25.0, 27.0, scene_goal),
    (27.0, 30.0, scene_end),
]

# 衝撃（シェイク・フラッシュ・RGB ずれ）のタイミング
IMPACTS = [(0.0, 1.0), (1.0, 1.0), (2.0, 1.0), (3.0, 0.8), (6.0, 0.35), (8.0, 0.35), (10.0, 0.3),
           (12.0, 0.45), (14.0, 0.4), (18.3, 0.5), (19.25, 0.5), (20.2, 0.5), (22.0, 0.4), (25.0, 1.2),
           (27.0, 0.6), (29.0, 0.35)]
WIPES = [6.0, 10.0, 14.0, 18.0, 22.0, 27.0]


def impact_level(t, decay=0.28):
    lvl = 0.0
    for at, amp in IMPACTS:
        if 0 <= t - at < decay:
            lvl = max(lvl, amp * (1 - (t - at) / decay) ** 2)
    return lvl


def draw_wipe(canvas, t):
    """シーン切替：オレンジの斜めパネルが画面を横切る。"""
    for at in WIPES:
        p = (t - at + 0.18) / 0.36
        if 0 <= p <= 1:
            e = ease_in_out(p)
            d = ImageDraw.Draw(canvas)
            skew = 520
            x = lerp(-W - skew, W + skew, e)
            d.polygon([(x, 0), (x + W * 0.9, 0), (x + W * 0.9 - skew, H), (x - skew, H)], fill=ORANGE)
            d.polygon([(x + W * 0.9, 0), (x + W * 0.9 + 60, 0), (x + W * 0.9 + 60 - skew, H),
                       (x + W * 0.9 - skew, H)], fill=INK)
    return canvas


def finish(canvas, t, frame_idx):
    arr = np.asarray(canvas, np.float32)
    lvl = impact_level(t)
    if lvl > 0:
        rng = np.random.default_rng(frame_idx)
        dx, dy = (rng.uniform(-1, 1, 2) * 26 * lvl).astype(int)
        arr = np.roll(arr, (dy, dx), axis=(0, 1))
        k = int(10 * lvl)
        if k:
            arr[..., 0] = np.roll(arr[..., 0], k, axis=1)
            arr[..., 2] = np.roll(arr[..., 2], -k, axis=1)
        # 冒頭 0.1 秒はフラッシュしない（1 フレーム目がサムネイルになっても白飛びしないように）
        flash = 0.0 if t < 0.1 else 0.55 * lvl * (1 if lvl > 0.5 else 0.5)
        arr = arr + (255 - arr) * flash
    arr = arr * VIGNETTE + GRAIN[frame_idx % len(GRAIN)]
    return np.clip(arr, 0, 255).astype(np.uint8)


def render_frame(t):
    for start, end, fn in TIMELINE:
        if start <= t < end:
            canvas = fn(t)
            break
    else:
        canvas = TIMELINE[-1][2](min(t, DURATION - 1e-3))
    if canvas.mode != "RGB":
        canvas = canvas.convert("RGB")
    return draw_wipe(canvas, t)


# ---------------------------------------------------------------- outputs
def render_video():
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    bgm = OUT / "bgm.wav"
    if not bgm.exists():
        sys.exit("output/bgm.wav がありません。先に python3 make_bgm.py を実行してください。")
    out = OUT / "FOOTBOZE_PV_reel.mp4"
    cmd = [ffmpeg, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(bgm),
           "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-maxrate", "9M", "-bufsize", "18M",
           "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-level", "4.2", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", "-shortest", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = int(DURATION * FPS)
    for i in range(total):
        t = i / FPS
        proc.stdin.write(finish(render_frame(t), t, i).tobytes())
        if i % 60 == 0:
            print(f"  frame {i}/{total}", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    print(f"wrote {out}")


OVERLAYS = [
    ("01_hook_見極めろ", lambda: scene_hook(0.9, overlay=True, only=0)),
    ("02_hook_決断しろ", lambda: scene_hook(1.9, overlay=True, only=1)),
    ("03_hook_伝えろ", lambda: scene_hook(2.9, overlay=True, only=2)),
    ("04_logo", lambda: scene_logo(5.9, overlay=True)),
    ("05_考えるのはキミ自身だ", lambda: scene_think(7.9, overlay=True)),
    ("06_自分のゲームをしよう", lambda: scene_own_game(9.9, overlay=True)),
    ("07_違っていい", lambda: scene_diversity(11.9, overlay=True, only=0)),
    ("08_チームの力になる", lambda: scene_diversity(13.9, overlay=True, only=1)),
    ("09_3つのチカラ", lambda: scene_powers(17.9, overlay=True)),
    ("10_実績", lambda: scene_records(21.9, overlay=True)),
    ("11_カテゴリー", lambda: scene_categories(24.9, overlay=True)),
    ("12_目指すは日本一", lambda: scene_goal(26.9, overlay=True)),
    ("13_エンドカード", lambda: scene_end(29.9, overlay=True)),
]


def render_overlays():
    d = OUT / "overlays"
    d.mkdir(parents=True, exist_ok=True)
    for name, fn in OVERLAYS:
        fn().save(d / f"{name}.png", optimize=True)
    print(f"wrote {len(OVERLAYS)} overlays to {d}")


def render_cover():
    t = 29.9
    # カバーはグリッドで 1:1 に切り抜かれても読めるよう、中央にコピーを寄せる
    canvas = dark_bg(t, court=1.0, court_alpha=0.22)
    canvas = glow(canvas, W / 2, H * 0.42, 760, ORANGE, 0.38)
    blit(canvas, ball_sprite(), W / 2, 470, scale=0.7, rot=-20)
    blit(canvas, text_sprite("自分のゲームを、", "dela", 104, WHITE), W / 2, 700)
    blit(canvas, text_sprite("しよう。", "dela", 150, ORANGE), W / 2, 870)
    blit(canvas, text_sprite("FOOTBOZE", "anton", 170, WHITE, tracking=3), W / 2, 1110)
    blit(canvas, text_sprite("FUTSAL", "anton", 88, ORANGE, tracking=28), W / 2, 1250)
    blit(canvas, text_sprite("東京・三鷹 ｜ U-12 / U-15 / U-18", "noto", 44, GRAY, "Bold"), W / 2, 1360)
    arr = np.clip(np.asarray(canvas, np.float32) * VIGNETTE + GRAIN[0], 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(OUT / "cover.jpg", quality=94)
    print(f"wrote {OUT / 'cover.jpg'}")


def render_stills(times):
    d = OUT / "stills"
    d.mkdir(parents=True, exist_ok=True)
    for t in times:
        i = int(t * FPS)
        Image.fromarray(finish(render_frame(t), t, i)).save(d / f"t{t:05.2f}.jpg", quality=88)
    print(f"wrote {len(times)} stills to {d}")


if __name__ == "__main__":
    ensure_fonts()
    OUT.mkdir(exist_ok=True)
    init_layers()
    if "--stills" in sys.argv:
        render_stills([0.4, 1.5, 2.6, 3.3, 5.5, 7.5, 9.5, 11.5, 13.5, 15.2, 17.5, 21.5, 24.5, 25.4, 26.5, 29.5])
    else:
        render_cover()
        render_overlays()
        render_video()
