"""
Daily Insight Discussion System
毎朝Claudeがトピックを選定し、設問をメールで送信する
"""

import os
import json
import random
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic
import feedparser
from dotenv import load_dotenv
import truststore

load_dotenv()
truststore.inject_into_ssl()

# ============================================================
# 設定
# ============================================================

# RSSフィード一覧（領域ごとに優先度付き）
RSS_FEEDS = {
    "AI・テクノロジー": [
        "https://feeds.feedburner.com/venturebeat/SZYF",          # VentureBeat AI
        "https://techcrunch.com/feed/",                            # TechCrunch
        "https://www.technologyreview.com/feed/",                  # MIT Tech Review
        "https://ai.googleblog.com/feeds/posts/default",           # Google AI Blog
        "https://openai.com/blog/rss/",                            # OpenAI Blog
        "https://www.itmedia.co.jp/news/rss/bursts.xml",           # ITmedia（日本語）
        "https://japan.zdnet.com/rss/index.rdf",                   # ZDNet Japan
    ],
    "経営・リーダーシップ": [
        "https://hbr.org/stories.rss",                             # Harvard Business Review
        "https://feeds.feedburner.com/McKinseyInsights",           # McKinsey Insights
        "https://www.diamond.co.jp/rss/diamond-online.rdf",        # ダイヤモンドオンライン
        "https://toyokeizai.net/list/feed/rss",                    # 東洋経済オンライン
    ],
    "マクロ経済・地政学": [
        "https://www.ft.com/?format=rss",                          # Financial Times
        "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",  # MarketWatch
        "https://www.nikkei.com/rss/",                             # 日本経済新聞
        "https://www.reuters.com/tools/rss",                       # Reuters
    ],
    "監査・ガバナンス（AI規制含む）": [
        "https://www.fsa.go.jp/news/rss/index.rdf",                # 金融庁
        "https://www.meti.go.jp/rss/press.rdf",                    # 経済産業省
        "https://www.ifac.org/rss.xml",                            # IFAC
    ],
    "趣味・哲学・科学": [
        "https://www.scientificamerican.com/platform/morgue/rss/feed/", # Scientific American
        "https://nautil.us/feed/",                                  # Nautilus
        "https://www.philosophytalk.org/feeds/all",                 # Philosophy Talk
    ],
}

# 領域の優先重み（プロファイルに基づく）
DOMAIN_WEIGHTS = {
    "AI・テクノロジー": 35,
    "経営・リーダーシップ": 25,
    "マクロ経済・地政学": 20,
    "監査・ガバナンス（AI規制含む）": 15,
    "趣味・哲学・科学": 5,
}

# 設問型の定義
QUESTION_TYPES = {
    "フレームワーク構築型": "この現象を説明する自分なりの構造・軸を作るとしたら、どう整理しますか？",
    "統合型": "監査プロフェッショナル・経営幹部の立場から、複数の視点を統合すると何が見えますか？",
    "盲点発見型": "その前提が崩れるとしたら何がトリガーになりますか？あるいは自分が見落としている視点は？",
    "深掘り型": "この変化は5年後の経営・監査実務にどう影響しますか？担当クライアントに置き換えると？",
    "発想飛躍型": "この原理・仕組みを別の領域に転用するとしたら、どんなイノベーションが生まれますか？",
}

# プロファイル（システムプロンプトに埋め込む）
MIYAGAWA_PROFILE = """
あなたは宮川智洋さん（監査法人パートナー）の知的ディスカッションパートナーです。

【宮川さんのプロファイル】
- 職位：監査法人第4事業部パートナー
- 専門：監査・ガバナンス（プロフェッショナルレベル）
- 経営・リーダーシップ：役員経験あり、CxOとの接触多数
- AI・テクノロジー：概念・論考を研究中（技術実装は素人）
- マクロ経済：ニュースレベル、2段階以上の深掘りが目標
- 趣味：乗馬、料理、ギター、オーディオ、旅行
- 関心：組織行動論、業務スキルの拡張、AI時代の人間能力論、哲学、動物学、社会心理学

【ディスカッションのゴール】
- 新概念・フレームワークの習得（最優先）
- 思考の癖・盲点の発見（次点）

【設計原則】
- 設問は1問のみ。シンプルで鋭く。
- 宮川さんの知識レベルより「1.5段階上」の視点から問うこと
- 反論・別視点は歓迎、ただし押し付けない
- 監査・ガバナンスとAI・経営の統合視点を大切にする
"""


def fetch_rss_articles(max_per_domain: int = 3) -> list[dict]:
    """RSSフィードから最新記事を収集"""
    articles = []
    today = datetime.date.today()

    for domain, feeds in RSS_FEEDS.items():
        domain_articles = []
        for feed_url in feeds[:2]:  # 各領域2フィードまで
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    published = entry.get("published_parsed") or entry.get("updated_parsed")
                    # 過去7日以内の記事のみ
                    if published:
                        pub_date = datetime.date(*published[:3])
                        if (today - pub_date).days > 7:
                            continue
                    domain_articles.append({
                        "domain": domain,
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", "")[:300],
                        "link": entry.get("link", ""),
                        "published": str(published[:3]) if published else "不明",
                    })
                    if len(domain_articles) >= max_per_domain:
                        break
            except Exception as e:
                print(f"RSS取得エラー ({feed_url}): {e}")
        articles.extend(domain_articles[:max_per_domain])

    return articles


def select_topic_and_generate_question(articles: list[dict], manual_topic: str = None) -> dict:
    """Claude APIでトピック選定と設問生成"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # 手動指定がある場合はそれを優先
    if manual_topic:
        articles_text = f"手動指定トピック：{manual_topic}"
    else:
        # 優先重みに基づいてランダム選択
        domains = list(DOMAIN_WEIGHTS.keys())
        weights = list(DOMAIN_WEIGHTS.values())
        selected_domain = random.choices(domains, weights=weights, k=1)[0]

        # 選択された領域の記事を絞り込む
        domain_articles = [a for a in articles if a["domain"] == selected_domain]
        if not domain_articles:
            domain_articles = articles[:5]  # フォールバック

        articles_text = "\n".join([
            f"・{a['title']}\n  概要：{a['summary']}\n  URL：{a['link']}"
            for a in domain_articles[:5]
        ])

    # 設問型もランダム選択（重み付き）
    question_types = list(QUESTION_TYPES.keys())
    selected_type = random.choices(question_types, weights=[30, 25, 20, 15, 10], k=1)[0]

    prompt = f"""
{MIYAGAWA_PROFILE}

【本日の候補記事・トピック】
{articles_text}

【本日の設問型】
{selected_type}：{QUESTION_TYPES[selected_type]}

以下のJSON形式のみで回答してください（前後に説明不要）：

{{
  "topic_title": "トピックタイトル（20文字以内）",
  "topic_summary": "要点を3行で。①〜③の形式。",
  "source_url": "参照元URL（記事URLをそのまま）",
  "question_type": "{selected_type}",
  "question": "設問本文（宮川さんのプロファイルに合わせた鋭い問い。1文で。）",
  "domain": "領域名"
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    # JSONフェンス除去
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def compose_email(insight: dict, today: datetime.date) -> str:
    """メール本文を生成"""
    date_str = today.strftime("%Y/%m/%d")
    day_jp = ["月", "火", "水", "木", "金", "土", "日"][today.weekday()]

    body = f"""【Today's Insight】{date_str}（{day_jp}）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📰 Topic：{insight['topic_title']}
　　　　　{insight['topic_summary']}
🎯 Source：{insight['source_url']}
🏷️  領域：{insight['domain']}　／　設問型：{insight['question_type']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q：{insight['question']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 ディスカッションの起動方法：
Claudeを開き、以下を貼り付けてください：

「今日のInsightディスカッション。
トピック：{insight['topic_title']}
Q：{insight['question']}
私の考え：[ここに記入]」

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Daily Insight Discussion System
"""
    return body


def send_email(body: str, today: datetime.date):
    """Gmail SMTPでメール送信"""
    smtp_user = os.environ["GMAIL_USER"]
    smtp_pass = os.environ["GMAIL_APP_PASSWORD"]
    to_address = os.environ.get("TO_EMAIL", smtp_user)

    date_str = today.strftime("%m/%d")
    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = to_address
    msg["Subject"] = f"[Insight] {date_str} 今日のディスカッション"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_address, msg.as_string())
    print("✅ メール送信完了")


def main(manual_topic: str = None):
    today = datetime.date.today()
    print(f"🚀 Daily Insight 起動：{today}")

    print("📡 RSS記事収集中...")
    articles = fetch_rss_articles()
    print(f"   {len(articles)}件取得")

    print("🤖 Claude APIでトピック選定・設問生成中...")
    insight = select_topic_and_generate_question(articles, manual_topic)
    print(f"   トピック：{insight['topic_title']}")
    print(f"   設問型：{insight['question_type']}")

    body = compose_email(insight, today)
    print("\n--- メールプレビュー ---")
    print(body)
    print("---")

    print("📧 メール送信中...")
    send_email(body, today)


if __name__ == "__main__":
    import sys
    manual = sys.argv[1] if len(sys.argv) > 1 else None
    main(manual_topic=manual)
