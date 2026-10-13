import os
import sys
import json
import re
import urllib.parse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import feedparser

# Base paths for the UK news files in config repo
TARGET_FOLDERS = [
    'news/ccom.uknewsnow.localnews',
    'news/com.uknewsnow.localnews'
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*'
}

UK_TOP_RSS_FEEDS = [
    ("https://news.google.com/rss?hl=en-GB&gl=GB&ceid=GB:en", "Google News UK", "uk_general"),
    ("http://feeds.bbci.co.uk/news/uk/rss.xml", "BBC News", "uk_general"),
    ("https://feeds.skynews.com/feeds/rss/uk.xml", "Sky News", "uk_general"),
    ("https://www.theguardian.com/uk-news/rss", "The Guardian", "uk_general"),
    ("https://www.telegraph.co.uk/rss.xml", "The Telegraph", "uk_general"),
    ("https://news.google.com/rss/headlines/section/topic/POLITICS?hl=en-GB&gl=GB&ceid=GB:en", "UK Politics", "uk_politics"),
    ("http://feeds.bbci.co.uk/news/politics/rss.xml", "BBC Politics", "uk_politics"),
    ("https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-GB&gl=GB&ceid=GB:en", "UK Business", "uk_economy"),
    ("https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-GB&gl=GB&ceid=GB:en", "Technology", "technology"),
    ("https://news.google.com/rss/headlines/section/topic/SPORTS?hl=en-GB&gl=GB&ceid=GB:en", "UK Sport", "sports"),
    ("http://feeds.bbci.co.uk/sport/rss.xml", "BBC Sport", "sports"),
    ("https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=en-GB&gl=GB&ceid=GB:en", "Entertainment", "entertainment"),
    ("https://news.google.com/rss/headlines/section/topic/HEALTH?hl=en-GB&gl=GB&ceid=GB:en", "Health & NHS", "health"),
]

REGIONAL_CITIES = {
    "london": "London",
    "birmingham": "Birmingham",
    "manchester": "Manchester",
    "glasgow": "Glasgow",
    "edinburgh": "Edinburgh",
    "belfast": "Belfast",
    "cardiff": "Cardiff",
    "leeds": "Leeds",
    "liverpool": "Liverpool",
    "newcastle": "Newcastle upon Tyne",
    "sheffield": "Sheffield",
    "bristol": "Bristol",
    "nottingham": "Nottingham",
    "southampton": "Southampton",
    "oxford": "Oxford",
    "cambridge": "Cambridge",
    "brighton": "Brighton",
    "leicester": "Leicester",
    "plymouth": "Plymouth",
    "norwich": "Norwich",
    "aberdeen": "Aberdeen",
    "swansea": "Swansea"
}

def clean_html(raw_html):
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

def extract_image_url(entry):
    # Check media_thumbnail
    media_thumbnail = entry.get('media_thumbnail')
    if media_thumbnail and isinstance(media_thumbnail, list) and len(media_thumbnail) > 0:
        thumb = media_thumbnail[0].get('url', '')
        if thumb:
            return thumb

    # Check media_content
    media_content = entry.get('media_content')
    if media_content and isinstance(media_content, list) and len(media_content) > 0:
        img_url = media_content[0].get('url', '')
        if img_url:
            return img_url

    # Check enclosures
    enclosures = entry.get('enclosures')
    if enclosures and isinstance(enclosures, list) and len(enclosures) > 0:
        for enc in enclosures:
            if 'image' in enc.get('type', '') or enc.get('href', '').endswith(('.jpg', '.jpeg', '.png', '.webp')):
                return enc.get('href')

    # Look for <img> tags in description or summary
    for field in [entry.get('summary', ''), entry.get('description', '')]:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', field or "")
        if match:
            return match.group(1)

    return "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=800"

def fetch_feed(feed_url, default_source, category_id):
    items = []
    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.content)
            for entry in feed.entries:
                title = entry.get('title', '').strip()
                link = entry.get('link', '')
                if not title or not link:
                    continue

                source_name = default_source
                if ' - ' in title:
                    parts = title.rsplit(' - ', 1)
                    title = parts[0].strip()
                    source_name = parts[1].strip()

                desc = clean_html(entry.get('summary') or entry.get('description') or '')
                if not desc:
                    desc = title

                pub_date = entry.get('published') or entry.get('pubDate') or datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                image = extract_image_url(entry)

                domain = urllib.parse.urlparse(link).netloc.replace('www.', '')
                if not domain:
                    domain = "news.google.com"

                items.append({
                    'title': title,
                    'url': link,
                    'link': link,
                    'source': source_name,
                    'source_domain': domain,
                    'sourceName': source_name,
                    'published_at': pub_date,
                    'pubDate': pub_date,
                    'image_url': image,
                    'imageUrl': image,
                    'summary': desc,
                    'description': desc,
                    'category_id': category_id,
                    'category': category_id.replace('uk_', '').replace('_', ' ').title()
                })
    except Exception as e:
        print(f"[FETCH ERROR] {feed_url}: {e}")
    return items

def fetch_top_uk_news():
    print("[1/2] Fetching Top 100 UK News...")
    all_stories = []
    seen_titles = set()

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_feed, url, src, cat) for url, src, cat in UK_TOP_RSS_FEEDS]
        for f in as_completed(futures):
            res = f.result()
            for item in res:
                # normalize title to avoid duplicates
                norm = re.sub(r'[^a-zA-Z0-9]', '', item['title'].lower())
                if norm not in seen_titles and len(norm) > 10:
                    seen_titles.add(norm)
                    all_stories.append(item)

    # Sort or rank stories, select exactly top 100
    top_100 = all_stories[:100]
    print(f" -> Successfully gathered {len(top_100)} unique Top UK news stories!")

    # Format into us_news.json format
    formatted = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "country": "GB",
        "language": "en-GB",
        "stories": []
    }

    for idx, story in enumerate(top_100):
        formatted["stories"].append({
            "id": f"uk_top_{1000 + idx}",
            "title": story["title"],
            "url": story["url"],
            "source": story["source"],
            "source_domain": story["source_domain"],
            "published_at": story["published_at"],
            "age_minutes": 15 + idx * 3,
            "image_url": story["image_url"],
            "category_id": story["category_id"],
            "category": story["category"],
            "story_group_id": None,
            "source_count": 1,
            "summary": story["summary"][:240] + ("..." if len(story["summary"]) > 240 else ""),
            "summary_type": "extractive"
        })

    return formatted

def fetch_regional_news_feed(city_key, city_name):
    query = urllib.parse.quote(f"{city_name} news when:7d")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-GB&gl=GB&ceid=GB:en"
    raw_items = fetch_feed(url, city_name, "regional")
    cleaned_items = []
    seen = set()

    for item in raw_items:
        norm = re.sub(r'[^a-zA-Z0-9]', '', item['title'].lower())
        if norm not in seen:
            seen.add(norm)
            cleaned_items.append({
                "title": item["title"],
                "link": item["link"],
                "description": item["description"],
                "pubDate": item["pubDate"],
                "sourceName": item["sourceName"],
                "imageUrl": item["imageUrl"]
            })
            if len(cleaned_items) >= 20:
                break

    return city_key, cleaned_items

def fetch_all_regional():
    print("[2/2] Fetching Regional News for 22 UK Cities...")
    regional_dict = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_regional_news_feed, k, v) for k, v in REGIONAL_CITIES.items()]
        for f in as_completed(futures):
            k, items = f.result()
            regional_dict[k] = items
            print(f" -> {REGIONAL_CITIES[k]}: {len(items)} stories")
    return regional_dict

def update_all_files():
    top_news_data = fetch_top_uk_news()
    regional_data = fetch_all_regional()

    for folder in TARGET_FOLDERS:
        if not os.path.exists(folder):
            continue

        # 1. Update us_news.json (Top 100 UK news)
        top_news_path = os.path.join(folder, "us_news.json")
        with open(top_news_path, "w", encoding="utf-8") as f:
            json.dump(top_news_data, f, indent=2, ensure_ascii=False)
        print(f"Saved: {top_news_path}")

        # 2. Update regional_news_feed.json
        regional_path = os.path.join(folder, "regional_news_feed.json")
        with open(regional_path, "w", encoding="utf-8") as f:
            json.dump(regional_data, f, indent=2, ensure_ascii=False)
        print(f"Saved: {regional_path}")

        # 3. Update individual states/<city>.json files
        states_dir = os.path.join(folder, "states")
        os.makedirs(states_dir, exist_ok=True)
        for city_key, stories in regional_data.items():
            city_file = os.path.join(states_dir, f"{city_key}.json")
            with open(city_file, "w", encoding="utf-8") as f:
                json.dump(stories, f, indent=2, ensure_ascii=False)

    print("\n[SUCCESS] All Top 100 UK News & Regional Feeds updated successfully!")

if __name__ == '__main__':
    update_all_files()
