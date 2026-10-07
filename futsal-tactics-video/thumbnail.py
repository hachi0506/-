# -*- coding: utf-8 -*-
"""YouTube 用サムネイル(1280x720)を生成する。"""
import os

from PIL import Image, ImageDraw, ImageFilter

import render as R

img = R.draw_court(2)
d = ImageDraw.Draw(img)
over = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
od = ImageDraw.Draw(over)
k = 1


def P(p):
    return R.px(p)


# パラレラの図(右半分)
R.arrow(od, P((21, 6.5)), P((31, 1.8)), (255, 255, 255, 255), 9, dashed=True, trim1=0.95 * R.S)
R.arrow(od, P((16, 10)), P((31, 1.8)), (255, 255, 255, 255), 10, trim0=10, trim1=20)
R.arrow(od, P((31, 1.8)), P((37.2, 12.2)), (250, 204, 21, 255), 10, trim0=10, trim1=20)
R.arrow(od, P((24, 16.5)), P((37.2, 12.2)), (255, 255, 255, 255), 9, dashed=True, trim1=0.95 * R.S)
img.paste(over, (0, 0), over)
for pid, p, lab in [("a_gk", R.A_GK if hasattr(R, "A_GK") else (1.6, 10), "GK"), ("a_fi", (16, 10), "FI"),
                    ("a_al", (31, 1.8), "AL"), ("a_ar", (37.2, 12.2), "AL"), ("a_pi", (33, 8), "PI"),
                    ("b_gk", (38.4, 9.5), ""), ("b_1", (20, 10), ""), ("b_2", (26, 7), ""),
                    ("b_3", (33, 14), ""), ("b_4", (34.6, 8.5), "")]:
    R.paste_center(img, R.sprite_for(pid, lab), P(p))

# 左側を暗くして文字を載せる
grad = Image.new("L", (R.W, R.H))
gd = ImageDraw.Draw(grad)
for x in range(R.W):
    gd.line([(x, 0), (x, R.H)], fill=int(max(0, 235 - x * 0.2)))
dark = Image.new("RGB", (R.W, R.H), (5, 10, 20))
img = Image.composite(dark, img, grad)
d = ImageDraw.Draw(img)

d.rounded_rectangle([70, 90, 560, 190], radius=20, fill=R.ACCENT)
d.text((315, 140), "図解でわかる", font=R.font(66), fill=(5, 30, 25), anchor="mm")
d.text((70, 330), "フットサル", font=R.font(170), fill=(255, 255, 255), anchor="lm",
       stroke_width=8, stroke_fill=(0, 0, 0))
d.text((70, 520), "戦術", font=R.font(210), fill=R.YELLOW, anchor="lm",
       stroke_width=9, stroke_fill=(0, 0, 0))
d.text((560, 540), "完全ガイド", font=R.font(110), fill=(255, 255, 255), anchor="lm",
       stroke_width=6, stroke_fill=(0, 0, 0))
d.text((70, 720), "パラレラ／ピヴォ当て／ファー詰め", font=R.font(62), fill=(255, 255, 255), anchor="lm",
       stroke_width=4, stroke_fill=(0, 0, 0))
d.text((70, 810), "ゾーン／プレス／パワープレー", font=R.font(62), fill=(255, 255, 255), anchor="lm",
       stroke_width=4, stroke_fill=(0, 0, 0))

out = os.path.join(R.OUT, "thumbnail.png")
img.resize((1280, 720), Image.LANCZOS).save(out)
print("wrote", out)
