# Daily Insight Discussion System

毎朝7時に、宮川さんの関心領域からトピックを自動選定し、
思考深化のための設問をメールで送信するシステムです。

## ディレクトリ構成

```
C:\projects\daily-insight\
├── daily_insight.py          # メインスクリプト
├── requirements.txt
├── .env.example              # 環境変数テンプレート
└── .github/
    └── workflows/
        └── daily_insight.yml # GitHub Actions設定
```

## セットアップ手順

### 1. プロジェクトフォルダ作成（Windows）

```
mkdir C:\projects\daily-insight
```

上記ファイルをすべてコピー。

### 2. ライブラリインストール

```
cd C:\projects\daily-insight
pip install -r requirements.txt
```

### 3. ローカル動作確認

```
# .envファイルを作成（.env.exampleをコピーして編集）
copy .env.example .env

# テスト実行
set ANTHROPIC_API_KEY=xxxx
set GMAIL_USER=xxxx@gmail.com
set GMAIL_APP_PASSWORD=xxxx
python daily_insight.py

# 手動トピック指定でテスト
python daily_insight.py "中期経営計画と生成AIの関係"
```

### 4. GitHubリポジトリ設定

1. GitHubに新規リポジトリ作成（例：`daily-insight`）
2. Secrets登録：
   - `ANTHROPIC_API_KEY`
   - `GMAIL_USER`
   - `GMAIL_APP_PASSWORD`
   - `TO_EMAIL`
3. プッシュ → 翌朝7時から自動配信開始

### 5. 手動実行（GitHub Actions）

Actions → Daily Insight Discussion → Run workflow
→「手動指定トピック」欄にテキスト入力で任意トピック指定可能

## 使い方：ディスカッションの起動

メールを受信したら：

1. Claudeを開く
2. メール末尾の起動フレーズをコピー
3. 「私の考え：」以降に自分の回答を記入して送信

Claudeが反論・深掘り・別視点でディスカッションを展開します。

## 領域の優先度（変更する場合はDAIN_WEIGHTSを編集）

| 領域 | 重み |
|------|------|
| AI・テクノロジー | 35% |
| 経営・リーダーシップ | 25% |
| マクロ経済・地政学 | 20% |
| 監査・ガバナンス | 15% |
| 趣味・哲学・科学 | 5% |
