import os
import sys
import json
import re
import requests
import feedparser
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials, messaging

STATE_DIR = 'automation/state'
DEFAULT_APPS_CONFIG = 'automation/apps.json'

_firebase_initialized = False

def init_firebase():
    """Initializes Firebase Admin SDK from environment secret"""
    global _firebase_initialized
    if _firebase_initialized:
        return True

    firebase_key = os.getenv('FIREBASE_KEY')
    if not firebase_key:
        print("[FCM] FIREBASE_KEY environment variable is missing.")
        return False

    try:
        if os.path.exists(firebase_key):
            cred = credentials.Certificate(firebase_key)
        else:
            service_account_info = json.loads(firebase_key)
            cred = credentials.Certificate(service_account_info)

        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        print("[FCM] Firebase Admin SDK successfully initialized.")
        return True
    except Exception as e:
        print(f"[FCM] Error initializing Firebase: {e}")
        return False

def extract_image_url(entry):
    """Extracts high-resolution image or video thumbnail from RSS entry"""
    media_thumbnail = entry.get('media_thumbnail')
    if media_thumbnail and isinstance(media_thumbnail, list) and len(media_thumbnail) > 0:
        thumb = media_thumbnail[0].get('url', '')
        if thumb:
            return thumb.replace('default.jpg', 'hqdefault.jpg')

    media_content = entry.get('media_content')
    if media_content and isinstance(media_content, list) and len(media_content) > 0:
        img_url = media_content[0].get('url', '')
        if img_url:
            return img_url

    enclosures = entry.get('enclosures')
    if enclosures and isinstance(enclosures, list) and len(enclosures) > 0:
        for enc in enclosures:
            if 'image' in enc.get('type', '') or enc.get('href', '').endswith(('.jpg', '.jpeg', '.png', '.webp')):
                return enc.get('href')

    summary = entry.get('summary', '') or entry.get('description', '')
    if summary:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary, re.IGNORECASE)
        if match:
            return match.group(1)

    return None

def send_fcm_topic_notification(topic, title, message, link=None, image_url=None, accent_color="#E11D48"):
    """Sends a rich push notification via Firebase Cloud Messaging (FCM) to a Topic"""
    if not init_firebase():
        print(f"[FCM] Cannot send notification to topic '{topic}': Firebase not initialized.")
        return False

    unique_id = str(int(datetime.now().timestamp()) % 1000000)

    # Prepare Data Payload (matching MyFirebaseMessageService.java)
    data_payload = {
        "unique_id": unique_id,
        "post_id": unique_id,
        "title": title,
        "message": message,
        "link": link or "",
        "big_image": image_url or ""
    }

    try:
        fcm_message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=message,
                image=image_url if image_url else None
            ),
            data=data_payload,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    color=accent_color,
                    default_sound=True,
                    default_vibrate_timings=True,
                    image=image_url if image_url else None
                )
            ),
            topic=topic
        )

        response = messaging.send(fcm_message)
        print(f"[FCM SUCCESS] Sent to topic '{topic}': {response}")
        return True
    except Exception as e:
        print(f"[FCM ERROR] Failed sending to topic '{topic}': {e}")
        return False

def get_latest_item(feed_url):
    """Fetches the latest entry from an RSS or YouTube feed"""
    try:
        resp = requests.get(feed_url, timeout=12, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        feed = feedparser.parse(resp.content)
        if feed.entries:
            latest = feed.entries[0]
            item_id = latest.get('id', latest.get('link'))
            title = latest.get('title', 'New Content')
            link = latest.get('link')
            image_url = extract_image_url(latest)

            return {
                'id': item_id,
                'title': title,
                'link': link,
                'image': image_url
            }
    except Exception:
        pass
    return None

def scan_feeds_in_directory(directory):
    """Collects all feed URLs from all JSON files in the given directory"""
    feeds = []
    if not os.path.exists(directory):
        return feeds

    for root, _, files in os.walk(directory):
        for filename in files:
            if not filename.endswith('.json'):
                continue
            path = os.path.join(root, filename)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    if isinstance(data, list):
                        for item in data:
                            name = item.get('name') or item.get('title')
                            if not name or item.get('provider') == 'webview':
                                continue

                            feed_url = None
                            provider = item.get('provider', '')
                            args = item.get('arguments', [])

                            if provider in ['rss', 'overview', 'category', 'videos'] and len(args) > 0 and args[0].startswith('http'):
                                feed_url = args[0]
                            elif provider == 'youtube_channel' and len(args) > 0:
                                ch_id = args[0]
                                if ch_id.startswith('UC'):
                                    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch_id}"
                            elif provider == 'youtube_playlist' and len(args) > 0:
                                pl_id = args[0]
                                feed_url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={pl_id}"
                            elif 'rss_url' in item:
                                feed_url = item['rss_url']
                            elif 'url' in item and str(item['url']).startswith('http'):
                                feed_url = item['url']

                            if feed_url and ('youtube.com/feeds' in feed_url or 'rss' in feed_url or 'feed' in feed_url or '.xml' in feed_url):
                                feeds.append({'name': name, 'url': feed_url})

                    elif isinstance(data, dict):
                        if 'rss_news' in data:
                            for item in data['rss_news']:
                                if item.get('url'):
                                    feeds.append({'name': item.get('title', 'RSS News'), 'url': item['url']})
                        if 'youtube_channels' in data:
                            for item in data['youtube_channels']:
                                channel_id = item.get('channel_id')
                                if channel_id:
                                    feeds.append({
                                        'name': item.get('name', 'YouTube Channel'),
                                        'url': f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
                                    })
            except Exception:
                pass
    return feeds

def monitor_fcm_app(app_config):
    """Monitors feeds and broadcasts to Firebase FCM topic"""
    app_id = app_config.get('app_id')
    app_name = app_config.get('name', app_id)
    folder = app_config.get('folder', app_id)
    fcm_topic = app_config.get('fcm_topic', f"{app_id}_topic")
    accent_color = "#" + app_config.get('accent_color', 'FFE11D48')[-6:]
    emoji = app_config.get('emoji', '🎬')

    daily_limit = app_config.get('daily_limit', 5)
    min_gap_hours = app_config.get('min_gap_hours', 2)
    active_hours = app_config.get('active_hours', [8, 22])
    priority_channels = app_config.get('priority_channels', [])

    # Locate app assets directory
    target_dir = None
    if os.path.exists(folder):
        target_dir = folder
    elif os.path.exists(os.path.join('apps', folder)):
        target_dir = os.path.join('apps', folder)

    if target_dir and len(scan_feeds_in_directory(target_dir)) == 0 and os.path.exists('app/src/main/assets'):
        target_dir = 'app/src/main/assets'
    elif not target_dir and folder == 'malayalam' and os.path.exists('app/src/main/assets'):
        target_dir = 'app/src/main/assets'

    if not target_dir:
        print(f"[FCM - {app_name}] Folder '{folder}' not found. Skipping.")
        return

    # Load persistent state and metadata
    os.makedirs(STATE_DIR, exist_ok=True)
    state_file = os.path.join(STATE_DIR, f"last_seen_fcm_{app_id}.json")
    last_seen = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                last_seen = json.load(f)
        except Exception:
            last_seen = {}

    meta = last_seen.get('_meta', {})
    today_str = datetime.now().strftime('%Y-%m-%d')
    if meta.get('today_date') != today_str:
        today_sent_count = 0
    else:
        today_sent_count = meta.get('today_sent_count', 0)

    last_sent_ts = meta.get('last_sent_timestamp', 0)
    current_ts = int(datetime.now().timestamp())
    current_hour = datetime.now().hour

    is_quiet_hours = False
    if active_hours and len(active_hours) == 2:
        start_h, end_h = active_hours
        if current_hour < start_h or current_hour >= end_h:
            is_quiet_hours = True

    min_gap_seconds = min_gap_hours * 3600
    is_in_cooldown = (current_ts - last_sent_ts) < min_gap_seconds
    is_daily_limit_reached = today_sent_count >= daily_limit

    feeds = scan_feeds_in_directory(target_dir)
    print(f"\n==========================================")
    print(f"[FCM - {app_name}] Topic: '{fcm_topic}' | Feeds: {len(feeds)}")
    print(f"[FCM - {app_name}] Daily Stats: Sent {today_sent_count}/{daily_limit} today | Cooldown: {is_in_cooldown} | Quiet Hours: {is_quiet_hours}")
    print(f"==========================================")

    new_state = {}
    candidate_items = []

    def check_single_feed(f_item):
        u = f_item['url']
        if not u:
            return None, None
        return f_item, get_latest_item(u)

    results = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(check_single_feed, f) for f in feeds]
        for fut in as_completed(futures):
            try:
                res = fut.result()
                if res and res[1]:
                    results.append(res)
            except Exception:
                pass

    for feed_item, latest in results:
        url = feed_item['url']
        new_state[url] = latest['id']

        if url in last_seen and last_seen[url] != latest['id']:
            title = latest.get('title', '')
            title_lower = title.lower()

            if '#shorts' in title_lower or '#short' in title_lower or '/shorts/' in str(latest.get('link', '')):
                continue

            score = 10
            for pc in priority_channels:
                if pc.lower() in feed_item['name'].lower():
                    score += 50
                    break

            for kw in ['trailer', 'teaser', 'review', 'breaking', 'official', 'exclusive', 'episode', 'live']:
                if kw in title_lower:
                    score += 25

            candidate_items.append({
                'feed': feed_item,
                'item': latest,
                'score': score
            })

    candidate_items.sort(key=lambda x: x['score'], reverse=True)
    notifications_sent = 0

    if candidate_items:
        print(f"[FCM - {app_name}] Found {len(candidate_items)} new upload(s).")

        for cand in candidate_items:
            f_item = cand['feed']
            latest = cand['item']

            if is_quiet_hours:
                print(f"[FCM - {app_name}] Quiet hours ({current_hour}:00). Skipping: {latest['title']}")
                continue

            if is_daily_limit_reached:
                print(f"[FCM - {app_name}] Daily limit ({daily_limit}) reached. Skipping: {latest['title']}")
                continue

            if is_in_cooldown:
                print(f"[FCM - {app_name}] Cooldown active ({min_gap_hours}h gap). Skipping: {latest['title']}")
                continue

            if notifications_sent < 1:
                heading = f"{emoji} {f_item['name']} • New Upload!"
                success = send_fcm_topic_notification(
                    topic=fcm_topic,
                    title=heading,
                    message=latest['title'],
                    link=latest['link'],
                    image_url=latest['image'],
                    accent_color=accent_color
                )
                if success:
                    notifications_sent += 1
                    today_sent_count += 1
                    last_sent_ts = int(datetime.now().timestamp())
                    is_in_cooldown = True

    # Save state and updated metadata
    last_seen.update(new_state)
    last_seen['_meta'] = {
        'today_date': today_str,
        'today_sent_count': today_sent_count,
        'last_sent_timestamp': last_sent_ts
    }

    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(last_seen, f, indent=2)

def main():
    if not os.path.exists(DEFAULT_APPS_CONFIG):
        print(f"[FCM] Config file {DEFAULT_APPS_CONFIG} not found.")
        return

    with open(DEFAULT_APPS_CONFIG, 'r', encoding='utf-8') as f:
        apps = json.load(f)

    for app in apps:
        monitor_fcm_app(app)

if __name__ == '__main__':
    main()
