# FOOTBOZE FUTSAL リール PV — 作業メモ（Claude Code 向け）

東京・三鷹の育成年代フットサルクラブ FOOTBOZE FUTSAL の Instagram リール用 PV を作るフォルダ。
ユーザーは日本語で話す。返答・コメント・テロップはすべて日本語。

## いまの状態

- 文字と図形だけの PV（`output/FOOTBOZE_PV_reel.mp4`）は完成済み。BGM `output/bgm.wav`、透過テロップ `output/overlays/`、エンドカードもここにある。
- 次の作業: **2016年 第3回全日本ユース(U-18)フットサル大会 決勝（FOOTBOZE FUTSAL U-18 vs 帝京長岡高校）の試合映像から、30秒の縦型 PV を作る。**
  - 構成は `match/edl.json` に決まっている。空欄なのは各カットの `"src"`（試合映像の何分何秒から使うか）だけ。
  - 試合映像は `input/` に置く（git には入れない）。

## 手順

1. 準備: `python3 -m venv .venv && source .venv/bin/activate && pip install pillow numpy scipy imageio-ffmpeg`
   （ffmpeg は imageio-ffmpeg に同梱。フォントは初回実行時に `fonts/` へ自動ダウンロードされる）
2. 候補探し: `python3 find_highlights.py input/<動画>.mp4`
   - `output/highlights/candidates.jpg`（歓声・実況が盛り上がった瞬間の前後）と `overview_NN.jpg`（全編一覧）を **Read で画像として見て**、場面を把握する。
   - 気になる区間は ffmpeg で数秒おきにフレームを書き出して、細かく確認する。
3. **ユーザーに確認（チェックポイント1）**: カットごとに「時刻・写っている内容・fit/crop」の表を出し、了承をもらってから進める。
   - FOOTBOZE がどちらのユニフォームの色かは、最初にユーザーに聞く。推測で決めない。
   - ゴールは FOOTBOZE の得点を使う。FOOTBOZE の得点場面が映像にない、または使えない場合は、「ハイライト4 ゴール」のカットを決定機やシュートに差し替え、`GOAL!!` のテロップも外す。
4. `match/edl.json` の `src` を埋め、必要なら `mode` / `focus` / `zoom` / `speed` を調整する（各項目の意味は `match_pv.py` の冒頭に書いてある）。
5. 書き出し: `python3 match_pv.py input/<動画>.mp4 match/edl.json` → `output/FOOTBOZE_match_PV_reel.mp4`
6. 自分で確認する: 書き出した動画から各カットの中央フレームを抜き出して Read で見る。確認すること:
   - crop のカットで選手やボールが画面外に切れていないか
   - テロップが読めるか
   - 画面下 20% に主要な文字がかかっていないか
   問題があれば `focus` などを直して、もう一度書き出す。
7. **ユーザーに確認（チェックポイント2）**: `open output/` で Finder を開き、見てもらう。修正依頼を受けて 4〜6 を繰り返す。

## 守ること

- この試合映像は大会の中継映像で、権利はアップロード元（大会主催側）にあると考えられる。**公開前に二次利用の許可を取るよう、ユーザーに一度は伝える。** Instagram への投稿など、外部への公開は Claude からは行わない。
- 試合映像（`input/`）と `output/highlights/` はコミットしない（.gitignore 済み）。
- 実績の表記は「全国準優勝」「東京都ユース(U-18)フットサルリーグ 1部優勝」「OB 清水和也 選手（フットサル日本代表・FIFAフットサルW杯2021出場）」まで。都リーグの優勝回数は情報源で食い違うので書かない。
- 相手チーム（帝京長岡高校）の選手をアップで大きく扱うカットは避ける。主役は FOOTBOZE の選手にする。
