"""試合のフル映像から、PV に使えそうな場面の候補を洗い出す。

歓声や実況が盛り上がった瞬間（ゴール・決定機のことが多い）を音量から拾い、
前後のサムネイルを並べたシートを作る。どの場面を使うかは、シートを見て
match/edl.json に秒数を書き込んで決める。

    python3 find_highlights.py 試合映像.mp4 [--top 14] [--every 20]

出力（output/highlights/）:
    candidates.csv   … 盛り上がり候補（秒数・盛り上がり度）
    candidates.jpg   … 候補ごとに -10s / -6s / -3s / 0s / +3s のサムネイル
    overview_NN.jpg  … 全編を --every 秒おきに並べた一覧（どこで何が起きているかの把握用）
"""
import argparse
import csv
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUT = Path(__file__).parent / "output" / "highlights"
THUMB_W, THUMB_H = 320, 180
AUDIO_SR = 8000
WIN = 0.5  # 音量を測る窓（秒）


def probe_duration(src):
    info = subprocess.run([FFMPEG, "-hide_banner", "-i", str(src)], capture_output=True, text=True).stderr
    for line in info.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    sys.exit(f"{src} の長さを読み取れませんでした")


def loudness_curve(src):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", str(AUDIO_SR),
                          "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = int(AUDIO_SR * WIN)
    frames = x[: len(x) // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-5)


def moving(x, k, fn):
    pad = np.pad(x, (k // 2, k - k // 2 - 1), mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(pad, k)
    return fn(windows, axis=1)


def pick_peaks(db, top, min_gap, min_db):
    smooth = moving(db, int(3 / WIN), np.mean)       # 3 秒の平均
    base = moving(db, int(60 / WIN), np.median)      # 1 分の中央値 = その時間帯の「普段の音量」
    excess = smooth - base
    order = np.argsort(excess)[::-1]
    chosen = []
    for i in order:
        t = i * WIN
        if excess[i] < min_db:
            break
        if all(abs(t - c) >= min_gap for c, _ in chosen):
            chosen.append((t, float(excess[i])))
        if len(chosen) >= top:
            break
    return sorted(chosen)


def thumb(src, t, dur):
    t = min(max(0.0, t), max(0.0, dur - 0.5))
    raw = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1",
                          "-vf", f"scale={THUMB_W}:{THUMB_H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    if len(raw) < THUMB_W * THUMB_H * 3:
        return Image.new("RGB", (THUMB_W, THUMB_H), (40, 40, 40))
    return Image.frombytes("RGB", (THUMB_W, THUMB_H), raw[: THUMB_W * THUMB_H * 3])


def stamp(sec):
    return f"{int(sec // 3600)}:{int(sec % 3600 // 60):02d}:{sec % 60:04.1f}"


def label_font():
    path = Path(__file__).parent / "fonts" / "NotoSansJP[wght].ttf"
    return ImageFont.truetype(str(path), 18) if path.exists() else ImageFont.load_default()


def sheet(rows, cols, cells, path, title):
    """cells: [(Image, label)]"""
    f = label_font()
    head = 36
    img = Image.new("RGB", (cols * THUMB_W, head + rows * (THUMB_H + 26)), (20, 20, 22))
    d = ImageDraw.Draw(img)
    d.text((10, 8), title, fill=(255, 150, 60), font=f)
    for k, (im, label) in enumerate(cells):
        x, y = (k % cols) * THUMB_W, head + (k // cols) * (THUMB_H + 26)
        img.paste(im, (x, y + 24))
        d.text((x + 6, y + 2), label, fill=(235, 235, 235), font=f)
    img.save(path, quality=85)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--top", type=int, default=14, help="候補の数")
    ap.add_argument("--gap", type=float, default=25, help="候補どうしの最小間隔（秒）")
    ap.add_argument("--min-db", type=float, default=3, help="普段より何 dB 大きければ候補にするか")
    ap.add_argument("--every", type=float, default=20, help="一覧サムネイルの間隔（秒）")
    args = ap.parse_args()
    src = Path(args.source)
    OUT.mkdir(parents=True, exist_ok=True)
    dur = probe_duration(src)
    print(f"source: {src} ({stamp(dur)})")

    db = loudness_curve(src)
    peaks = pick_peaks(db, args.top, args.gap, args.min_db) if len(db) else []
    with open(OUT / "candidates.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank_by_time", "seconds", "timestamp", "excess_db"])
        for k, (t, ex) in enumerate(peaks, 1):
            w.writerow([k, f"{t:.1f}", stamp(t), f"{ex:.1f}"])
            print(f"  #{k:02d} {stamp(t)}  +{ex:.1f} dB")

    offsets = (-10, -6, -3, 0, 3)
    cells = []
    for k, (t, ex) in enumerate(peaks, 1):
        for off in offsets:
            cells.append((thumb(src, t + off, dur), f"#{k:02d} {stamp(t + off)}" + (f"  +{ex:.1f}dB" if off == 0 else "")))
    if cells:
        sheet(len(peaks), len(offsets), cells, OUT / "candidates.jpg",
              "盛り上がり候補（各行: -10s / -6s / -3s / 0s / +3s）")

    times = np.arange(0, dur, args.every)
    per_page = 6 * 8
    for p in range(0, len(times), per_page):
        chunk = times[p:p + per_page]
        cells = [(thumb(src, t, dur), stamp(t)) for t in chunk]
        rows = (len(cells) + 5) // 6
        sheet(rows, 6, cells, OUT / f"overview_{p // per_page + 1:02d}.jpg",
              f"全編一覧 {stamp(chunk[0])} 〜 {stamp(chunk[-1])}（{args.every:g} 秒おき）")
    print(f"wrote sheets to {OUT}")


if __name__ == "__main__":
    main()
