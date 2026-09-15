import os
import sys
import json
import re
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

STATE_DIR = 'automation/state'
DEFAULT_APPS_CONFIG = 'automation/apps.json'

def extract_image_url(entry):
    """Extracts high-resolution image or video thumbnail from RSS entry"""
    # 1. YouTube media_thumbnail
    media_thumbnail = entry.get('media_thumbnail')
    if media_thumbnail and isinstance(media_thumbnail, list) and len(media_thumbnail) > 0:
        thumb = media_thumbnail[0].get('url', '')
        if thumb:
            # Upgrade standard YouTube thumb to hqdefault for crisp rendering
            return thumb.replace('default.jpg', 'hqdefault.jpg')

    # 2. media_content
    media_content = entry.get('media_content')
    if media_content and isinstance(media_content, list) and len(media_content) > 0:
        img_url = media_content[0].get('url', '')
        if img_url:
            return img_url

    # 3. enclosures
    enclosures = entry.get('enclosures')
    if enclosures and isinstance(enclosures, list) and len(enclosures) > 0:
        for enc in enclosures:
            if 'image' in enc.get('type', '') or enc.get('href', '').endswith(('.jpg', '.jpeg', '.png', '.webp')):
                return enc.get('href')

    # 4. links with image type
    links = entry.get('links')
    if links and isinstance(links, list):
        for link in links:
            if 'image' in link.get('type', ''):
                return link.get('href')

    # 5. Extract <img src="..."> from summary or description HTML
    summary = entry.get('summary', '') or entry.get('description', '')
    if summary:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary, re.IGNORECASE)
        if match:
            return match.group(1)

    return None

def send_onesignal_notification(app_id, rest_key, title, message, link=None, image_url=None, accent_color="FFE11D48"):
    """Sends a rich, beautiful push notification via OneSignal REST API"""
    if not app_id or not rest_key or app_id == 'YOUR_APP_ID_HERE':
        print(f"Skipping notification (missing credentials for App ID: {app_id})")
        return

    url = "https://onesignal.com/api/v1/notifications"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {rest_key}"
    }

    payload = {
        "app_id": app_id,
        "included_segments": ["All"],
        "headings": {"en": title},
        "contents": {"en": message},
        "android_accent_color": accent_color,
        "android_visibility": 1,
        "priority": 10
    }

    # Rich Media: Full-width banner in Android & preview thumbnail
    if image_url:
        payload["big_picture"] = image_url
        payload["chrome_web_image"] = image_url
        payload["ios_attachments"] = {"id1": image_url}
        payload["large_icon"] = image_url

    # Action link & Deep Linking
    if link:
        payload["url"] = link
        payload["data"] = {
            "url": link,
            "title": message,
            "image": image_url or ""
        }
        payload["buttons"] = [
            {"id": "btn_open", "text": "▶ Watch Now", "icon": "ic_play_circle"},
            {"id": "btn_share", "text": "🔗 Share"}
        ]

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=12)
        print(f"[{title}] OneSignal Response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error sending notification: {e}")

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
    except Exception as e:
        # Silently ignore temporary network timeouts
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
                        # rss_news in config.json
                        if 'rss_news' in data:
                            for item in data['rss_news']:
                                if item.get('url'):
                                    feeds.append({'name': item.get('title', 'RSS News'), 'url': item['url']})
                        # youtube_channels in config.json
                        if 'youtube_channels' in data:
                            for item in data['youtube_channels']:
                                channel_id = item.get('channel_id')
                                if channel_id:
                                    feeds.append({
                                        'name': item.get('name', 'YouTube Channel'),
                                        'url': f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
                                    })
            except Exception as e:
                pass
    return feeds

def monitor_app(app_config):
    """Monitors feeds for a specific app configuration"""
    app_id = app_config.get('app_id')
    app_name = app_config.get('name', app_id)
    folder = app_config.get('folder', app_id)
    env_app_id = app_config.get('env_app_id', f"{app_id.upper()}_ONESIGNAL_APP_ID")
    env_rest_key = app_config.get('env_rest_key', f"{app_id.upper()}_ONESIGNAL_REST_KEY")
    accent_color = app_config.get('accent_color', 'FFE11D48')
    emoji = app_config.get('emoji', '🔔')
    limit_per_run = app_config.get('limit_per_run', 2)

    onesignal_app_id = os.getenv(env_app_id) or os.getenv('ONESIGNAL_APP_ID')
    onesignal_rest_key = os.getenv(env_rest_key) or os.getenv('ONESIGNAL_REST_KEY')

    # Locate app assets directory
    target_dir = None
    if os.path.exists(folder):
        target_dir = folder
    elif os.path.exists(os.path.join('apps', folder)):
        target_dir = os.path.join('apps', folder)

    # If folder has no feeds and app/src/main/assets exists locally
    if target_dir and len(scan_feeds_in_directory(target_dir)) == 0 and os.path.exists('app/src/main/assets'):
        target_dir = 'app/src/main/assets'
    elif not target_dir and folder == 'malayalam' and os.path.exists('app/src/main/assets'):
        target_dir = 'app/src/main/assets'

    if not target_dir:
        print(f"[{app_name}] Folder '{folder}' not found. Skipping.")
        return

    daily_limit = app_config.get('daily_limit', 5)
    min_gap_hours = app_config.get('min_gap_hours', 2)
    active_hours = app_config.get('active_hours', [8, 22])
    priority_channels = app_config.get('priority_channels', [])

    # Load persistent state and metadata
    os.makedirs(STATE_DIR, exist_ok=True)
    state_file = os.path.join(STATE_DIR, f"last_seen_{app_id}.json")
    last_seen = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                last_seen = json.load(f)
        except Exception:
            last_seen = {}

    meta = last_seen.get('_meta', {})
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    today_str = now_ist.strftime('%Y-%m-%d')
    if meta.get('today_date') != today_str:
        today_sent_count = 0
    else:
        today_sent_count = meta.get('today_sent_count', 0)

    last_sent_ts = meta.get('last_sent_timestamp', 0)
    current_ts = int(now_ist.timestamp())
    current_hour = now_ist.hour

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
    print(f"[{app_name}] Scanning {len(feeds)} feeds from '{target_dir}' at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[{app_name}] Daily Stats: Sent {today_sent_count}/{daily_limit} today. Cooldown: {is_in_cooldown}, Quiet Hours: {is_quiet_hours}")
    print(f"==========================================")

    new_state = {}
    candidate_items = []

    # Fetch feeds concurrently for speed
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

        # If this feed was previously tracked and has a newly published video/article
        if url in last_seen and last_seen[url] != latest['id']:
            title = latest.get('title', '')
            title_lower = title.lower()

            # Skip YouTube shorts or 15-second teaser shorts
            if '#shorts' in title_lower or '#short' in title_lower or '/shorts/' in str(latest.get('link', '')):
                continue

            # Calculate Relevance & Priority Score
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

    # Sort new candidate items by highest score first (VIP channels and major trailers win)
    candidate_items.sort(key=lambda x: x['score'], reverse=True)

    notifications_sent = 0

    if candidate_items:
        print(f"[{app_name}] Found {len(candidate_items)} new upload(s) across all channels.")

        for cand in candidate_items:
            f_item = cand['feed']
            latest = cand['item']

            if is_quiet_hours:
                print(f"[{app_name}] Quiet hours active ({current_hour}:00). Skipping notification for: {latest['title']}")
                continue

            if is_daily_limit_reached:
                print(f"[{app_name}] Daily limit ({daily_limit}) reached for today. Skipping: {latest['title']}")
                continue

            if is_in_cooldown:
                print(f"[{app_name}] Cooldown active (min gap {min_gap_hours}h). Skipping: {latest['title']}")
                continue

            if notifications_sent < 1:  # Send the #1 best item this hour
                heading = f"{emoji} {f_item['name']} • New Upload!"
                send_onesignal_notification(
                    app_id=onesignal_app_id,
                    rest_key=onesignal_rest_key,
                    title=heading,
                    message=latest['title'],
                    link=latest['link'],
                    image_url=latest['image'],
                    accent_color=accent_color
                )
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

    # Also maintain backwards compatibility with legacy single state file
    legacy_file = 'automation/last_seen.json'
    try:
        legacy_state = {}
        if os.path.exists(legacy_file):
            with open(legacy_file, 'r', encoding='utf-8') as f:
                legacy_state = json.load(f)
        legacy_state.update(new_state)
        with open(legacy_file, 'w', encoding='utf-8') as f:
            json.dump(legacy_state, f, indent=2)
    except Exception:
        pass

    print(f"[{app_name}] Finished. Sent {notifications_sent} push notifications.")

def main():
    single_dir = os.getenv('SCAN_DIR')
    if single_dir:
        # Single app mode via SCAN_DIR env variable
        app_cfg = {
            'app_id': single_dir,
            'name': single_dir.capitalize(),
            'folder': single_dir,
            'env_app_id': f"{single_dir.upper()}_ONESIGNAL_APP_ID",
            'env_rest_key': f"{single_dir.upper()}_ONESIGNAL_REST_KEY"
        }
        monitor_app(app_cfg)
        return

    # Multi-App registry mode
    if os.path.exists(DEFAULT_APPS_CONFIG):
        with open(DEFAULT_APPS_CONFIG, 'r', encoding='utf-8') as f:
            apps = json.load(f)
        for app in apps:
            monitor_app(app)
    else:
        # Fallback to local assets
        monitor_app({
            'app_id': 'default',
            'name': 'Default App',
            'folder': 'app/src/main/assets'
        })

if __name__ == '__main__':
    main()
