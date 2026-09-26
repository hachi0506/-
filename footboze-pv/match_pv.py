"""試合映像（16:9）を切り出して、縦型リール PV を組み立てる。

どの場面を何秒使うかは EDL（match/edl.json）に書く。BGM・テロップ・エンドカードは
render_pv.py / make_bgm.py で作ったものを再利用する。

    python3 match_pv.py 試合映像.mp4 match/edl.json

EDL の各セグメント:
    dur        … PV 上の長さ（秒）
    src        … 試合映像の開始位置（"12:34.5" / "0:12:34" / 秒数）
    mode       … "fit"  = 横長のまま中央に置き、上下はぼかした同じ映像で埋める（全体が見える）
                 "crop" = 縦にトリミングして画面いっぱいに（迫力重視。focus で左右位置 0〜1）
    focus      … crop 時の左右位置（0 = 左端, 0.5 = 中央, 1 = 右端）
    zoom       … 拡大率（1.0 = 等倍）
    speed      … 再生速度（0.5 = スロー）
    dim        … 暗くする量（0〜1。テロップを読みやすくする）
    flash      … true で頭に白フラッシュ
    overlay    … 重ねる透過 PNG（output/overlays/ など）
    text       … その場で作るテロップ: [{"t": "文字", "font": "dela|noto|anton", "size": 120, "color": "orange|white|gray"}]
    text_y     … テロップの縦位置（0〜1、既定 0.5）
    src_audio  … 試合の音（歓声・実況）を BGM に混ぜる音量（0 = 混ぜない）
    card       … 試合映像の代わりに render_pv.py のアニメーションを使う: "logo" / "end" / [開始秒, 終了秒]
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

import render_pv as rp

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = Path(__file__).parent
W, H, FPS = rp.W, rp.H, rp.FPS
COLORS = {"orange": rp.ORANGE, "white": rp.WHITE, "gray": rp.GRAY, "light": rp.ORANGE_LIGHT, "ink": rp.INK}
CARDS = {"logo": (3.0, 6.0), "end": (27.0, 30.0)}
VCODEC = ["-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def parse_time(v):
    if isinstance(v, (int, float)):
        return float(v)
    parts = [float(p) for p in str(v).split(":")]
    sec = 0.0
    for p in parts:
        sec = sec * 60 + p
    return sec


def text_png(lines, y_frac, path):
    """EDL の text 指定から透過テロップを作る。"""
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sprites = []
    for ln in lines:
        key = ln.get("font", "dela")
        size = int(ln.get("size", 110))
        color = COLORS.get(ln.get("color", "white"), rp.WHITE)
        weight = ln.get("weight", "Black")
        sprites.append(rp.text_sprite(ln["t"], key, size, color, weight, tracking=int(ln.get("tracking", 0))))
    gap = 18
    total = sum(s.height for s in sprites) + gap * (len(sprites) - 1)
    y = H * y_frac - total / 2
    for s in sprites:
        rp.blit(canvas, s, W / 2, y + s.height / 2)
        y += s.height + gap
    canvas.save(path)


def video_filter(seg, n_overlays):
    mode = seg.get("mode", "fit")
    zoom = float(seg.get("zoom", 1.0))
    speed = float(seg.get("speed", 1.0))
    dim = float(seg.get("dim", 0.0))
    chain = [f"[0:v]setpts=PTS/{speed},fps={FPS}"]
    if mode == "crop":
        focus = float(seg.get("focus", 0.5))
        chain.append(f"scale=-2:{int(H * zoom)},crop={W}:{H}:(iw-{W})*{focus}:(ih-{H})/2")
        graph = ",".join(chain) + "[v0]"
    else:
        fg_y = float(seg.get("fg_y", 0.5))
        graph = (",".join(chain) + ",split[a][b];"
                 f"[a]scale=-2:{H},crop={W}:{H},boxblur=28:2,eq=brightness=-0.10:saturation=0.8[bg];"
                 f"[b]scale={int(W * zoom)}:-2[fg];"
                 f"[bg][fg]overlay=(W-w)/2:(H-h)*{fg_y}[v0]")
    last = "v0"
    post = []
    if dim > 0:
        post.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=black@{dim}:t=fill")
    if seg.get("flash"):
        post.append("fade=t=in:st=0:d=0.15:color=white")
    if post:
        graph += f";[{last}]{','.join(post)}[v1]"
        last = "v1"
    for k in range(n_overlays):
        graph += f";[{last}][{k + 1}:v]overlay=0:0[o{k}]"
        last = f"o{k}"
    graph += f";[{last}]setsar=1,format=yuv420p[out]"
    return graph


def render_clip(src, seg, out, tmp):
    dur = float(seg["dur"])
    speed = float(seg.get("speed", 1.0))
    start = parse_time(seg["src"])
    overlays = []
    if seg.get("overlay"):
        overlays.append(ROOT / seg["overlay"])
    if seg.get("text"):
        p = Path(tmp) / f"{out.stem}_text.png"
        text_png(seg["text"], float(seg.get("text_y", 0.5)), p)
        overlays.append(p)
    cmd = [FFMPEG, "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur * speed + 0.2:.3f}", "-i", str(src)]
    for o in overlays:
        cmd += ["-loop", "1", "-i", str(o)]
    cmd += ["-filter_complex", video_filter(seg, len(overlays)), "-map", "[out]", "-t", f"{dur:.3f}", "-an",
            *VCODEC, str(out)]
    subprocess.run(cmd, check=True)


def render_card(seg, out):
    a, b = CARDS[seg["card"]] if isinstance(seg["card"], str) else seg["card"]
    dur = float(seg.get("dur", b - a))
    cmd = [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", *VCODEC, str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(round(dur * FPS))):
        t = min(a + i / FPS, b - 1e-3)
        proc.stdin.write(rp.finish(rp.render_frame(t), t, int(t * FPS)).tobytes())
    proc.stdin.close()
    if proc.wait():
        sys.exit("card render failed")


def has_audio(src):
    info = subprocess.run([FFMPEG, "-hide_banner", "-i", str(src)], capture_output=True, text=True).stderr
    return "Audio:" in info


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, edl_path = Path(sys.argv[1]), Path(sys.argv[2])
    edl = json.loads(edl_path.read_text())
    segs = edl["segments"]
    missing = [k for k, s in enumerate(segs, 1) if "card" not in s and s.get("src") in (None, "")]
    if missing:
        sys.exit(f"src（試合映像の開始位置）が未設定のセグメントがあります: {missing}")
    rp.ensure_fonts()
    rp.init_layers()
    out = ROOT / edl.get("output", "output/FOOTBOZE_match_PV_reel.mp4")
    bgm = ROOT / edl.get("bgm", "output/bgm.wav")

    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for k, seg in enumerate(segs):
            part = Path(tmp) / f"part_{k:02d}.mp4"
            print(f"  segment {k + 1}/{len(segs)}  {seg.get('card') or seg.get('src')}  ({seg.get('dur')}s)")
            (render_card if "card" in seg else lambda s, o: render_clip(src, s, o, tmp))(seg, part)
            parts.append(part)
        listing = Path(tmp) / "list.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        video = Path(tmp) / "video.mp4"
        subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", str(video)], check=True)

        # 音: BGM + 指定した場面だけ試合の歓声・実況を重ねる
        inputs = ["-i", str(video), "-i", str(bgm)]
        mix, labels, t, n_inputs = [], ["[1:a]"], 0.0, 2
        use_src_audio = has_audio(src)
        for seg in segs:
            gain = float(seg.get("src_audio", 0)) if use_src_audio else 0
            if gain > 0 and "card" not in seg:
                n = n_inputs
                n_inputs += 1
                speed = float(seg.get("speed", 1.0))
                inputs += ["-ss", f"{parse_time(seg['src']):.3f}", "-t", f"{seg['dur'] * speed:.3f}", "-i", str(src)]
                ms = int(t * 1000)
                tempo = f"atempo={speed}," if 0.5 <= speed < 1 else ""
                mix.append(f"[{n}:a]{tempo}aresample=48000,volume={gain},afade=t=in:d=0.08,"
                           f"afade=t=out:st={max(0, seg['dur'] - 0.2):.2f}:d=0.2,adelay={ms}|{ms}[s{n}]")
                labels.append(f"[s{n}]")
            t += float(seg["dur"])
        graph = ";".join(mix + [f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first,"
                                "alimiter=limit=0.9[a]"])
        subprocess.run([FFMPEG, "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "0:v",
                        "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                        "-movflags", "+faststart", "-shortest", str(out)], check=True)
    print(f"wrote {out}  ({t:.1f}s)")


if __name__ == "__main__":
    main()
