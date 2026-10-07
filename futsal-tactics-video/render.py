# -*- coding: utf-8 -*-
"""台本(script.py)から、ナレーション付きのフットサル戦術解説動画を生成する。

使い方: python3 render.py [--preview SCENE_INDEX] [--fps 30]
出力  : out/futsal_tactics.mp4, out/futsal_tactics.srt, out/youtube_description.txt
"""
import argparse
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from script import SCENES

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
TTS_DIR = os.path.join(OUT, "tts")
VOICE = os.path.join(HERE, "assets", "tohoku-f01-neutral.htsvoice")
DIC = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
FONT = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
SR = 48000

W, H = 1920, 1080
S = 36                      # 1m あたりのピクセル
OX, OY = 240, 168           # コート左上
CW, CH = 40 * S, 20 * S

# 配色
BG = (13, 19, 33)
COURT = (28, 92, 74)
COURT_DARK = (24, 80, 64)
LINE = (236, 240, 235)
BLUE = (59, 130, 246)
RED = (239, 68, 68)
GK_BLUE = (250, 204, 21)
GK_RED = (168, 85, 247)
YELLOW = (250, 204, 21)
ACCENT = (52, 211, 153)
ZONE_COL = {"blue": (59, 130, 246), "red": (239, 68, 68), "yellow": (250, 204, 21)}

BEAT_PAD = 0.75          # ナレーション後の間
SCENE_TAIL = 0.6         # シーン終わりの余韻


def font(size):
    return ImageFont.truetype(FONT, size)


def px(p):
    return (OX + p[0] * S, OY + p[1] * S)


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- 音声
def synth(text, path):
    if os.path.exists(path):
        return
    txt = path + ".txt"
    with open(txt, "w", encoding="utf-8") as f:
        f.write(text)
    subprocess.run(["open_jtalk", "-x", DIC, "-m", VOICE, "-r", "1.08", "-jf", "1.1",
                    "-ow", path, txt], check=True)
    os.remove(txt)


def read_wav(path):
    with wave.open(path) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


# ---------------------------------------------------------------- 静的描画
def draw_court(sub=2):
    """コートを高解像度で描いて縮小(アンチエイリアス)。"""
    k = sub
    img = Image.new("RGB", (W * k, H * k), BG)
    d = ImageDraw.Draw(img)

    def P(x, y):
        return ((OX + x * S) * k, (OY + y * S) * k)

    lw = 3 * k
    # 外側の余白(ランオフ)
    d.rounded_rectangle([P(-1.6, -0.9), P(41.6, 20.9)], radius=14 * k, fill=(20, 60, 50))
    d.rectangle([P(0, 0), P(40, 20)], fill=COURT)
    # 縞模様
    for i in range(0, 40, 4):
        if (i // 4) % 2 == 0:
            d.rectangle([P(i, 0), P(i + 4, 20)], fill=COURT_DARK)
    d.rectangle([P(0, 0), P(40, 20)], outline=LINE, width=lw)
    d.line([P(20, 0), P(20, 20)], fill=LINE, width=lw)
    r = 3
    d.ellipse([P(20 - r, 10 - r), P(20 + r, 10 + r)], outline=LINE, width=lw)
    d.ellipse([P(20 - .15, 10 - .15), P(20 + .15, 10 + .15)], fill=LINE)
    for side in (0, 1):
        sx = 0 if side == 0 else 40
        sg = 1 if side == 0 else -1
        # ペナルティエリア: ポスト中心の半径6mの四分円 + 直線
        for post, (a0, a1) in ((8.5, (270, 360)), (11.5, (0, 90))):
            box = [P(sx - 6, post - 6), P(sx + 6, post + 6)]
            if side == 0:
                d.arc(box, a0, a1, fill=LINE, width=lw)
            else:
                d.arc(box, 180 - a1, 180 - a0, fill=LINE, width=lw)
        d.line([P(sx + sg * 6, 8.5), P(sx + sg * 6, 11.5)], fill=LINE, width=lw)
        for m in (6, 10):
            c = (sx + sg * m, 10)
            d.ellipse([P(c[0] - .14, c[1] - .14), P(c[0] + .14, c[1] + .14)], fill=LINE)
        # ゴール
        gx0, gx1 = (sx - 1.0, sx) if side == 0 else (sx, sx + 1.0)
        d.rectangle([P(gx0, 8.5), P(gx1, 11.5)], fill=(235, 235, 235), outline=LINE, width=lw)
        for yy in np.arange(8.75, 11.5, 0.35):
            d.line([P(gx0, yy), P(gx1, yy)], fill=(180, 180, 180), width=k)
        # コーナーアーク
        for cy, ang in ((0, (0, 90) if side == 0 else (90, 180)), (20, (270, 360) if side == 0 else (180, 270))):
            box = [P(sx - .5, cy - .5), P(sx + .5, cy + .5)]
            d.arc(box, ang[0], ang[1], fill=LINE, width=lw)
    # コーナーアーク外側を消す代わりに外枠を再描画
    img = img.resize((W, H), Image.LANCZOS)
    # ランオフ外をBGで塗り直し(アークのはみ出し除去)
    return img


def text_center(d, xy, text, f, fill, stroke=0, stroke_fill=(0, 0, 0)):
    d.text(xy, text, font=f, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=stroke_fill)


def wrap(text, f, maxw):
    lines, cur = [], ""
    for ch in text:
        if f.getlength(cur + ch) > maxw:
            # 句読点が行頭に来ないように
            if ch in "、。！？」）":
                cur += ch
                lines.append(cur)
                cur = ""
                continue
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def split_lines(text, f, maxw):
    """1行に収まらなければ、句読点など自然な位置で2行に分ける。"""
    if f.getlength(text) <= maxw:
        return [text]
    best = None
    mid = len(text) / 2
    for i in range(1, len(text)):
        a, b = text[:i], text[i:]
        if f.getlength(a) > maxw or f.getlength(b) > maxw:
            continue
        prev, nxt = text[i - 1], text[i]
        if nxt in "、。！？」）":
            continue
        if prev in "、。！？" or (prev in "」）" and not ("\u3041" <= nxt <= "\u309f")):
            score = abs(i - mid)
        elif prev in "はがをにでとのへも" and not ("\u3041" <= nxt <= "\u309f") and nxt not in "ーァィゥェォャュョッ":
            score = abs(i - mid) + 6
        else:
            continue
        if best is None or score < best[0]:
            best = (score, i)
    if best is None:
        return wrap(text, f, f.getlength(text) / 2 + 60)
    return [text[:best[1]], text[best[1]:]]


def subtitle_layer(text):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(44)
    lines = split_lines(text, f, 1640)
    lh = 60
    total = lh * len(lines)
    y0 = 905 + (160 - total) // 2
    d.rounded_rectangle([110, y0 - 16, W - 110, y0 + total + 10], radius=18, fill=(0, 0, 0, 170))
    for i, ln in enumerate(lines):
        d.text((W // 2, y0 + i * lh + lh // 2 - 4), ln, font=f, fill=(255, 255, 255),
               anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
    return layer


def header_layer(chapter, idx):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if chapter:
        d.rounded_rectangle([60, 40, 60 + 92, 132], radius=16, fill=ACCENT + (255,))
        text_center(d, (106, 87), f"{idx:02d}", font(46), (10, 30, 25))
        d.text((176, 86), chapter, font=font(54), fill=(255, 255, 255), anchor="lm",
                stroke_width=1, stroke_fill=(255, 255, 255))
    d.text((W - 60, 62), "FUTSAL TACTICS BOARD", font=font(24), fill=(148, 163, 184), anchor="rm")
    if chapter:
        f = font(24)
        x = W - 60
        items = [("dash", "走る"), ("line", "パス"), ("dot", RED, "相手"), ("dot", BLUE, "味方")]
        for it in items:
            label = it[-1]
            tw = f.getlength(label)
            d.text((x, 108), label, font=f, fill=(203, 213, 225), anchor="rm")
            x -= tw + 10
            if it[0] == "dot":
                d.ellipse([x - 20, 98, x, 118], fill=it[1], outline=(255, 255, 255), width=2)
                x -= 20
            elif it[0] == "line":
                d.line([x - 40, 108, x, 108], fill=(255, 255, 255), width=4)
                x -= 40
            else:
                for j in range(3):
                    d.line([x - 40 + j * 15, 108, x - 32 + j * 15, 108], fill=(255, 255, 255), width=4)
                x -= 40
            x -= 26
    return layer


# ---------------------------------------------------------------- スプライト
def make_sprite(color, label, ring=False):
    k = 4
    r = int(0.78 * S)
    size = (r * 2 + 24) * k
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size // 2
    # 影
    sh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([c - r * k + 4 * k, c - r * k + 6 * k, c + r * k + 4 * k, c + r * k + 6 * k],
                               fill=(0, 0, 0, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(4 * k))
    im.alpha_composite(sh)
    d = ImageDraw.Draw(im)
    d.ellipse([c - r * k, c - r * k, c + r * k, c + r * k], fill=color + (255,),
              outline=(255, 255, 255, 255), width=3 * k)
    if label:
        dark = sum(color) > 500
        d.text((c, c + k), label, font=font(int(r * 0.95 * k)), anchor="mm",
               fill=(20, 20, 20) if dark else (255, 255, 255))
    im = im.resize((size // k, size // k), Image.LANCZOS)
    return im


def make_ball():
    k = 4
    r = 12
    size = (r * 2 + 8) * k
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size // 2
    d.ellipse([c - r * k, c - r * k, c + r * k, c + r * k], fill=(255, 255, 255, 255),
              outline=(15, 15, 15, 255), width=3 * k)
    d.regular_polygon((c, c, r * k * 0.45), 5, fill=(20, 20, 20, 255))
    return im.resize((size // k, size // k), Image.LANCZOS)


def make_ring():
    k = 4
    r = int(1.25 * S)
    size = (r * 2 + 10) * k
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size // 2
    d.ellipse([c - r * k, c - r * k, c + r * k, c + r * k], fill=YELLOW + (60,),
              outline=YELLOW + (255,), width=5 * k)
    return im.resize((size // k, size // k), Image.LANCZOS)


SPRITES = {}
LABEL_NAMES = {"GK": "ゴレイロ", "FI": "フィクソ", "AL": "アラ", "PI": "ピヴォ"}


def sprite_for(pid, label):
    key = (pid[0], "gk" in pid, label)
    if key not in SPRITES:
        team = pid[0]
        if "gk" in pid:
            col = GK_BLUE if team == "a" else GK_RED
        else:
            col = BLUE if team == "a" else RED
        txt = label if team == "a" else ""
        if "gk" in pid:
            txt = "GK"
        SPRITES[key] = make_sprite(col, txt)
    return SPRITES[key]


# ---------------------------------------------------------------- 矢印など(ビート単位の静的レイヤー)
def dashed_line(d, p0, p1, color, width, dash=14, gap=10):
    x0, y0 = p0
    x1, y1 = p1
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 1:
        return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    t = 0
    while t < L:
        e = min(t + dash, L)
        d.line([(x0 + ux * t, y0 + uy * t), (x0 + ux * e, y0 + uy * e)], fill=color, width=width)
        t = e + gap


def arrow(d, p0, p1, color, width, dashed=False, k=1, trim0=0.0, trim1=0.0):
    x0, y0 = p0
    x1, y1 = p1
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 8 * k + trim0 + trim1:
        return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    x0, y0 = x0 + ux * trim0, y0 + uy * trim0
    x1, y1 = x1 - ux * trim1, y1 - uy * trim1
    head = 22 * k
    bx, by = x1 - ux * head, y1 - uy * head
    if dashed:
        dashed_line(d, (x0, y0), (bx, by), color, width, 16 * k, 11 * k)
    else:
        d.line([(x0, y0), (bx, by)], fill=color, width=width)
    nx, ny = -uy, ux
    d.polygon([(x1, y1), (bx + nx * head * 0.55, by + ny * head * 0.55),
               (bx - nx * head * 0.55, by - ny * head * 0.55)], fill=color)


def overlay_layer(beat, pos_start, pos_end, ball_paths):
    """ビート中ずっと表示する静的な描画(ゾーン・ライン・矢印)。2倍で描いて縮小。"""
    k = 2
    layer = Image.new("RGBA", (W * k, H * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    def P(p):
        return ((OX + p[0] * S) * k, (OY + p[1] * S) * k)

    for z in beat.get("zones", []):
        x0, y0, x1, y1 = z["rect"]
        col = ZONE_COL[z["color"]]
        d.rounded_rectangle([P((x0, y0)), P((x1, y1))], radius=10 * k, fill=col + (55,),
                            outline=col + (200,), width=3 * k)
    for v in beat.get("vlines", []):
        col = ZONE_COL[v["color"]]
        dashed_line(d, P((v["x"], -0.5)), P((v["x"], 20.5)), col + (255,), 6 * k, 22 * k, 12 * k)
    if beat.get("poly"):
        pts = [P(pos_start[i]) for i in beat["poly"] if i in pos_start]
        if beat.get("steps"):
            pts = [P(pos_end[i]) for i in beat["poly"] if i in pos_end]
        d.polygon(pts, fill=ACCENT + (40,), outline=ACCENT + (230,), width=4 * k)
    for a, b in beat.get("links", []):
        if a in pos_start and b in pos_start:
            dashed_line(d, P(pos_start[a]), P(pos_start[b]), (255, 255, 255, 200), 3 * k, 8 * k, 8 * k)
    # 走る矢印(点線)
    for pid, (p0, p1) in moves_of(beat, pos_start).items():
        if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > 1.2:
            if pid[0] == "a":
                arrow(d, P(p0), P(p1), (255, 255, 255, 235), 5 * k, dashed=True, k=k, trim1=0.95 * S * k)
            else:
                arrow(d, P(p0), P(p1), (255, 170, 170, 200), 4 * k, dashed=True, k=k, trim1=0.95 * S * k)
    # パス/シュート矢印(実線)
    for p0, p1, shot in ball_paths:
        col = (250, 204, 21, 255) if shot else (255, 255, 255, 255)
        arrow(d, P(p0), P(p1), col, 6 * k, dashed=False, k=k, trim0=0.25 * S * k,
              trim1=(0.15 if shot else 0.5) * S * k)
    if beat.get("dims"):
        c = (255, 255, 255, 255)
        y = -0.55
        d.line([P((0, y)), P((40, y))], fill=c, width=3 * k)
        f = font(30 * k)
        mid = P((20, y))
        d.rounded_rectangle([mid[0] - 70 * k, mid[1] - 24 * k, mid[0] + 70 * k, mid[1] + 24 * k],
                            radius=10 * k, fill=(13, 19, 33, 255))
        d.text(mid, "約40m", font=f, fill=c, anchor="mm")
        x = 40.9
        d.line([P((x, 0)), P((x, 20))], fill=c, width=3 * k)
        mid = P((x, 10))
        d.rounded_rectangle([mid[0] - 45 * k, mid[1] - 24 * k, mid[0] + 45 * k, mid[1] + 24 * k],
                            radius=10 * k, fill=(13, 19, 33, 255))
        d.text(mid, "20m", font=f, fill=c, anchor="mm")
    # ラベル(ゾーン・ライン)
    f = font(30 * k)
    for z in beat.get("zones", []):
        if z.get("label"):
            x0, y0, x1, y1 = z["rect"]
            q = P(((x0 + x1) / 2, y0))
            tw = f.getlength(z["label"])
            d.rounded_rectangle([q[0] - tw / 2 - 12 * k, q[1] - 22 * k, q[0] + tw / 2 + 12 * k, q[1] + 22 * k],
                                radius=8 * k, fill=(0, 0, 0, 200))
            d.text(q, z["label"], font=f, fill=(255, 255, 255, 255), anchor="mm")
    for v in beat.get("vlines", []):
        q = P((v["x"], -0.55))
        tw = f.getlength(v["label"])
        col = ZONE_COL[v["color"]]
        d.rounded_rectangle([q[0] - tw / 2 - 12 * k, q[1] - 22 * k, q[0] + tw / 2 + 12 * k, q[1] + 22 * k],
                            radius=8 * k, fill=col + (255,))
        d.text(q, v["label"], font=f, fill=(10, 10, 10, 255), anchor="mm")
    return layer.resize((W, H), Image.LANCZOS)


def moves_of(beat, pos_start):
    res = {}
    cur = dict(pos_start)
    for st in beat.get("steps", []):
        for pid, p in st.get("move", {}).items():
            p0 = res[pid][0] if pid in res else cur[pid]
            res[pid] = (p0, p)
    return res


# ---------------------------------------------------------------- シーン状態のタイムライン
class Timeline:
    """ビート内の時刻 t における選手・ボール位置を計算する。"""

    def __init__(self, beat, pos, ball, labels):
        self.pos0 = dict(pos)
        self.labels = dict(labels)
        self.ball0 = ball  # ("owner", pid) or ("pt", (x,y))
        self.tracks = {}   # pid -> [(t0, t1, p0, p1)]
        self.added = {}    # pid -> t (フェードイン開始)
        self.ball_tracks = []  # (t0, t1, p0, p1, target)
        self.ball_paths = []
        steps = beat.get("steps", [])
        cur = dict(pos)
        # 1) 選手の移動
        for st in steps:
            t0 = st.get("at", 0.25)
            dur = st.get("dur", 1.4)
            for pid, (p, lab) in st.get("add", {}).items():
                cur[pid] = p
                self.pos0[pid] = p
                self.labels[pid] = lab
                self.added[pid] = t0
            for pid, p in st.get("move", {}).items():
                self.tracks.setdefault(pid, []).append((t0, t0 + dur, None, p))
        # 開始位置の確定
        for pid, tr in self.tracks.items():
            p = self.pos0[pid]
            fixed = []
            for (a, b, _, p1) in sorted(tr):
                fixed.append((a, b, p, p1))
                p = p1
            self.tracks[pid] = fixed
        # 2) ボール
        owner = ball
        for st in steps:
            if "ball" not in st:
                continue
            t0 = st.get("at", 0.25)
            dur = st.get("dur", 0.8)
            p0 = self.ball_pos_static(owner, t0)
            tgt = st["ball"]
            if isinstance(tgt, str):
                p1 = self.player_pos(tgt, t0 + dur)
                new_owner = ("owner", tgt)
            else:
                p1 = tuple(tgt)
                new_owner = ("pt", p1)
            self.ball_tracks.append((t0, t0 + dur, p0, p1, new_owner))
            self.ball_paths.append((p0, p1, st.get("shot", False)))
            owner = new_owner
        self.ball_final = owner

    def player_pos(self, pid, t):
        p = self.pos0[pid]
        for (a, b, p0, p1) in self.tracks.get(pid, []):
            if t >= b:
                p = p1
            elif t > a:
                e = ease((t - a) / (b - a))
                p = (p0[0] + (p1[0] - p0[0]) * e, p0[1] + (p1[1] - p0[1]) * e)
                break
            else:
                break
        return p

    def end_positions(self):
        return {pid: self.player_pos(pid, 1e9) for pid in self.pos0}

    def ball_pos_static(self, owner, t):
        if owner is None:
            return None
        if owner[0] == "owner":
            p = self.player_pos(owner[1], t)
            return (p[0] + 0.55, p[1] + 0.45)
        return owner[1]

    def ball_pos(self, t):
        owner = self.ball0
        for (a, b, p0, p1, new_owner) in self.ball_tracks:
            if t >= b:
                owner = new_owner
            elif t > a:
                u = (t - a) / (b - a)
                u = 1 - (1 - u) ** 2  # パスは減速
                return (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u)
            else:
                break
        return self.ball_pos_static(owner, t)


# ---------------------------------------------------------------- フレーム合成
def composite(base, layers):
    img = base.copy()
    for lay, alpha in layers:
        if lay is None or alpha <= 0:
            continue
        if alpha >= 1:
            img.paste(lay, (0, 0), lay)
        else:
            a = lay.getchannel("A").point(lambda v: int(v * alpha))
            img.paste(lay, (0, 0), a)
    return img


def paste_center(img, spr, xy, alpha=1.0):
    x, y = xy
    w, h = spr.size
    if alpha < 1:
        spr = spr.copy()
        spr.putalpha(spr.getchannel("A").point(lambda v: int(v * alpha)))
    img.paste(spr, (int(round(x - w / 2)), int(round(y - h / 2))), spr)


def flash_sprite(text):
    f = font(84)
    tw = int(f.getlength(text)) + 90
    im = Image.new("RGBA", (tw, 140), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 10, tw - 1, 130], radius=26, fill=(0, 0, 0, 185),
                        outline=YELLOW + (255,), width=4)
    d.text((tw // 2, 70), text, font=f, fill=YELLOW + (255,), anchor="mm",
           stroke_width=4, stroke_fill=(0, 0, 0, 255))
    return im


def slide_base(scene, n_bullets):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 背景にうっすらコート
    court = draw_court(1).filter(ImageFilter.GaussianBlur(3))
    img = Image.blend(img, court, 0.28)
    d = ImageDraw.Draw(img)
    if scene.get("kind") == "title":
        d.text((W // 2, 360), "作戦ボードで学ぶ", font=font(56), fill=ACCENT, anchor="mm")
        d.text((W // 2, 480), scene["title"], font=font(120), fill=(255, 255, 255), anchor="mm",
               stroke_width=4, stroke_fill=(0, 0, 0))
        d.text((W // 2, 610), scene["subtitle"], font=font(44), fill=(226, 232, 240), anchor="mm",
               stroke_width=2, stroke_fill=(0, 0, 0))
        # 選手アイコン装飾
        for i, (col, lab) in enumerate([(GK_BLUE, "GK"), (BLUE, "FI"), (BLUE, "AL"), (BLUE, "AL"), (BLUE, "PI")]):
            spr = make_sprite(col, lab)
            paste_center(img, spr, (W // 2 - 240 + i * 120, 730))
    else:
        d.text((W // 2, 210), scene["title"], font=font(96), fill=(255, 255, 255), anchor="mm",
               stroke_width=3, stroke_fill=(0, 0, 0))
        for i, ln in enumerate(scene["bullet_lines"][:n_bullets]):
            y = 340 + i * 120
            d.rounded_rectangle([170, y - 46, W - 170, y + 46], radius=20, fill=(30, 41, 59))
            d.ellipse([200, y - 18, 236, y + 18], fill=ACCENT)
            d.text((270, y), ln, font=font(46), fill=(255, 255, 255), anchor="lm")
    return img


# ---------------------------------------------------------------- メイン
def build(args):
    os.makedirs(TTS_DIR, exist_ok=True)
    # 1) 音声合成とタイミング
    plan = []  # (scene_idx, beat_idx, start, dur, wavpath)
    t = 0.0
    chapters = []
    for si, sc in enumerate(SCENES):
        if args.preview is not None and si != args.preview:
            continue
        chapters.append((t, sc.get("chapter") or "オープニング"))
        for bi, bt in enumerate(sc["beats"]):
            wp = os.path.join(TTS_DIR, f"s{si:02d}_b{bi:02d}.wav")
            synth(bt.get("say", bt["sub"]), wp)
            dur = len(read_wav(wp)) / SR
            # 動きが長いビートは、動きが終わるまで待つ
            mv_end = 0
            for st in bt.get("steps", []):
                mv_end = max(mv_end, st.get("at", 0.25) + st.get("dur", 1.4 if "move" in st else 0.8))
            if bt.get("flash"):
                mv_end = max(mv_end, bt.get("flash_at", 0) + 1.2)
            lead = 0.35 if bi == 0 else 0.15
            bdur = max(lead + dur + BEAT_PAD, mv_end + 0.8)
            plan.append((si, bi, t, bdur, wp, lead))
            t += bdur
        t += SCENE_TAIL
        plan[-1] = plan[-1][:3] + (plan[-1][3] + SCENE_TAIL,) + plan[-1][4:]
    total = t
    print(f"total duration: {total:.1f}s")

    # 2) 音声トラック(ナレーション + 控えめなBGM)
    n = int(total * SR) + SR
    voice = np.zeros(n, np.float32)
    for (si, bi, st, bd, wp, lead) in plan:
        w = read_wav(wp)
        i0 = int((st + lead) * SR)
        voice[i0:i0 + len(w)] += w * 1.15
    bgm = make_bgm(n)
    # ダッキング: ナレーション中はBGMを下げる
    env = np.abs(voice)
    win = int(0.3 * SR)
    cs = np.concatenate([[0.0], np.cumsum(env, dtype=np.float64)])
    idx = np.arange(n)
    lo = np.clip(idx - win // 2, 0, n)
    hi = np.clip(idx + win // 2, 0, n)
    env = ((cs[hi] - cs[lo]) / win).astype(np.float32)
    duck = 1.0 - 0.55 * np.clip(env * 25, 0, 1)
    mix = voice + bgm * duck
    mix = np.clip(mix / max(1.0, np.max(np.abs(mix)) / 0.95), -1, 1)
    suffix = f"_preview{args.preview}" if args.preview is not None else ""
    wav_path = os.path.join(OUT, f"audio{suffix}.wav")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())

    # 3) 字幕ファイルと概要欄
    write_srt(plan, os.path.join(OUT, f"futsal_tactics{suffix}.srt"))
    write_description(chapters, os.path.join(OUT, f"youtube_description{suffix}.txt"))

    # 4) 映像
    out_mp4 = os.path.join(OUT, f"futsal_tactics{suffix}.mp4")
    fps = args.fps
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-i", wav_path,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
        "-shortest", out_mp4], stdin=subprocess.PIPE)

    court = draw_court(2)
    ball_spr = make_ball()
    ring = make_ring()
    frame_no = 0
    by_scene = {}
    for p in plan:
        by_scene.setdefault(p[0], []).append(p)

    for si, beats in by_scene.items():
        sc = SCENES[si]
        is_slide = sc.get("kind") in ("title", "summary")
        header = header_layer(sc.get("chapter", ""), si) if not is_slide else None
        pos = {pid: v[0] for pid, v in sc.get("players", {}).items()}
        labels = {pid: v[1] for pid, v in sc.get("players", {}).items()}
        ball = ("owner", sc["ball"]) if sc.get("ball") else None
        scene_start = beats[0][2]
        scene_end = beats[-1][2] + beats[-1][3]
        for (_, bi, bstart, bdur, _, _) in beats:
            bt = sc["beats"][bi]
            sub = subtitle_layer(bt["sub"])
            if is_slide:
                base = slide_base(sc, bt.get("bullets", 0))
                tl = None
                over = None
            else:
                base = composite(court, [(header, 1)])
                tl = Timeline(bt, pos, ball, labels)
                over = overlay_layer(bt, tl.pos0, tl.end_positions(), tl.ball_paths)
            fl = flash_sprite(bt["flash"]) if bt.get("flash") else None
            nframes = int(round((bstart + bdur) * fps)) - frame_no
            for fi in range(nframes):
                tg = (frame_no + fi) / fps          # 全体時刻
                tb = tg - bstart                     # ビート内時刻
                img = composite(base, [(over, ease(tb / 0.35)), (sub, 1)])
                if tl is not None:
                    # ハイライト
                    for pid in bt.get("hl", []):
                        a = ease(tb / 0.4) * (0.75 + 0.25 * math.sin(tb * 5))
                        paste_center(img, ring, px(tl.player_pos(pid, tb)), a)
                    for pid in sorted(tl.pos0, key=lambda p: p[0] == "a"):
                        p = tl.player_pos(pid, tb)
                        alpha = 1.0
                        if pid in tl.added:
                            alpha = ease((tb - tl.added[pid]) / 0.5)
                            if alpha <= 0:
                                continue
                        paste_center(img, sprite_for(pid, labels_get(tl, pid)), px(p), alpha)
                        if sc.get("labels") and tl.labels.get(pid) in LABEL_NAMES and pid[0] == "a":
                            draw_name(img, LABEL_NAMES[tl.labels[pid]], px(p))
                    bp = tl.ball_pos(tb)
                    if bp is not None:
                        paste_center(img, ball_spr, px(bp))
                if fl is not None:
                    fa = bt.get("flash_at", 0.2)
                    u = tb - fa
                    if 0 <= u:
                        a = ease(u / 0.25) * (1 - ease((u - 2.2) / 0.4))
                        sc_ = 0.85 + 0.15 * ease(u / 0.25)
                        spr = fl if sc_ >= 1 else fl.resize((int(fl.width * sc_), int(fl.height * sc_)))
                        if a > 0:
                            paste_center(img, spr, (W // 2, OY + 95), a)
                # シーン冒頭/末尾のフェード
                fade = min(1.0, (tg - scene_start) / 0.4, (scene_end - tg) / 0.4)
                if fade < 1:
                    img = Image.blend(Image.new("RGB", (W, H), BG), img, max(0.0, fade))
                ff.stdin.write(img.tobytes())
            frame_no += nframes
            if tl is not None:
                pos = tl.end_positions()
                labels = tl.labels
                ball = tl.ball_final
            print(f"scene {si} beat {bi} done ({frame_no / fps:.1f}s)", flush=True)
    ff.stdin.close()
    ff.wait()
    print("wrote", out_mp4)


def labels_get(tl, pid):
    return tl.labels.get(pid, "")


NAME_CACHE = {}


def draw_name(img, name, xy):
    if name not in NAME_CACHE:
        f = font(28)
        tw = int(f.getlength(name)) + 24
        im = Image.new("RGBA", (tw, 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, tw - 1, 39], radius=10, fill=(0, 0, 0, 190))
        d.text((tw // 2, 20), name, font=f, fill=(255, 255, 255, 255), anchor="mm")
        NAME_CACHE[name] = im
    paste_center(img, NAME_CACHE[name], (xy[0], xy[1] + 0.78 * S + 26))


def make_bgm(n):
    """控えめなアンビエント・パッド(コード進行)を合成。"""
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    # Am - F - C - G (各4秒)
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63],
              [196.0 * 2 / 1.5 * 0.75 * 2, 329.63, 392.0], [196.0, 246.94, 293.66]]
    chords[2] = [261.63, 329.63, 392.0]
    seg = 4.0
    idx = (t // seg).astype(int) % 4
    for ci, ch in enumerate(chords):
        m = idx == ci
        tt = t[m]
        local = (tt % seg) / seg
        env = np.minimum(1, local * 6) * np.minimum(1, (1 - local) * 6)
        sig = np.zeros_like(tt)
        for f in ch:
            sig += np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2 * tt + 0.5)
            sig += 0.5 * np.sin(2 * np.pi * f / 2 * tt)
        out[m] = sig * env
    # 軽いパルス(ビート感)
    beat = 0.5
    ph = (t % beat) / beat
    kick = np.exp(-ph * 18) * np.sin(2 * np.pi * 55 * t)
    hat_ph = ((t + beat / 2) % beat) / beat
    rng = np.random.default_rng(0)
    hat = np.exp(-hat_ph * 60) * rng.standard_normal(n).astype(np.float32) * 0.15
    out = out / np.max(np.abs(out)) * 0.05 + kick * 0.05 + hat * 0.06
    # 全体の頭と終わりのフェード
    f = int(2 * SR)
    out[:f] *= np.linspace(0, 1, f)
    out[-f:] *= np.linspace(1, 0, f)
    return out.astype(np.float32)


def fmt_ts(sec, sep=","):
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{int(s):02d}{sep}{int((s % 1) * 1000):03d}"


def write_srt(plan, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, (si, bi, st, bd, wp, lead) in enumerate(plan, 1):
            sub = SCENES[si]["beats"][bi]["sub"]
            f.write(f"{i}\n{fmt_ts(st)} --> {fmt_ts(st + bd - 0.05)}\n{sub}\n\n")


def write_description(chapters, path):
    lines = [
        "【図解】フットサル戦術 完全ガイド｜フォーメーション・攻撃・守備・パワープレーを作戦ボードで解説",
        "",
        "フットサルの戦術を、作戦ボードのアニメーションで基礎から分かりやすく解説します。",
        "3-1・2-2・4-0のフォーメーション、パラレラ・ピヴォ当て・ローテーション・ファー詰めといった攻撃パターン、",
        "マンツーマンとゾーン、プレスの高さ、サイドへの追い込みといった守備戦術、そして試合終盤の切り札パワープレーまで。",
        "",
        "■ チャプター",
    ]
    for t, name in chapters:
        m, s = int(t // 60), int(t % 60)
        lines.append(f"{m}:{s:02d} {name}")
    lines += [
        "",
        "#フットサル #フットサル戦術 #futsal #パラレラ #ピヴォ #戦術解説",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=int, default=None)
    ap.add_argument("--fps", type=int, default=30)
    build(ap.parse_args())
