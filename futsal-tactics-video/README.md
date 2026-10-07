# フットサル戦術 完全ガイド（YouTube 解説動画）

作戦ボードのアニメーションとナレーションで、フットサルの戦術を解説する約9分の動画です。

## 成果物（`out/`）
| ファイル | 内容 |
|---|---|
| `futsal_tactics.mp4` | 本編（1920x1080 / 30fps / H.264 + AAC） |
| `thumbnail.png` | サムネイル（1280x720） |
| `futsal_tactics.srt` | 日本語字幕ファイル（YouTube の字幕としてアップロード可） |
| `youtube_description.txt` | タイトル・概要欄・チャプター（タイムスタンプ付き） |

## 構成
0. オープニング
1. フットサルの特徴
2. 4つのポジション（ゴレイロ／フィクソ／アラ／ピヴォ）
3. 基本フォーメーション（3-1／2-2／4-0）
4. 攻撃戦術① パラレラ
5. 攻撃戦術② ピヴォ当て
6. 攻撃戦術③ 4-0のローテーション
7. 攻撃戦術④ ファー詰め（セグンド・パロ）
8. 守備戦術① マンツーマンとゾーン
9. 守備戦術② プレスの高さ
10. 守備戦術③ サイドへ追い込む
11. 切り札 パワープレー
12. まとめ

## YouTube への投稿手順
1. YouTube Studio →「作成」→「動画をアップロード」で `futsal_tactics.mp4` を選択
2. タイトル・説明に `youtube_description.txt` の内容を貼り付け（チャプターは自動で認識されます）
3. サムネイルに `thumbnail.png` を設定
4. 「字幕」→「ファイルをアップロード」→「タイミングあり」で `futsal_tactics.srt` を追加
5. 「子ども向けではありません」を選んで公開

## 再生成
```
sudo apt-get install open-jtalk open-jtalk-mecab-naist-jdic ffmpeg fonts-ipafont-gothic
pip install numpy pillow
python3 render.py      # 動画・字幕・概要欄
python3 thumbnail.py   # サムネイル
```
台本とアニメーションは `script.py` を編集します。
ナレーション音声は Open JTalk + HTS voice「tohoku-f01」（東北大学, CC-BY 4.0）を使用しています。
BGM はスクリプト内で合成しているため、著作権の心配はありません。
