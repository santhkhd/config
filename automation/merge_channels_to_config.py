import json
import os
import re

def main():
    assets_dir = r"c:\Users\santh\OneDrive\Desktop\WebDroid\app\src\main\assets"
    
    category_files = [
        "comedy_channels.json",
        "music_channels.json",
        "news_channels.json",
        "troll_channels.json",
        "cooking_channels.json",
        "cinema_channels.json"
    ]
    
    merged_channels = []
    seen_ids = set()
    
    for filename in category_files:
        filepath = os.path.join(assets_dir, filename)
        if not os.path.exists(filepath):
            print(f"Warning: {filename} does not exist.")
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            channels = json.load(f)
            
        print(f"Reading {filename}: found {len(channels)} channels")
        
        for ch in channels:
            title = ch.get("title")
            args = ch.get("arguments", [])
            if not title or not args:
                continue
                
            # Extract channel ID from arguments URL
            # e.g., "https://www.youtube.com/feeds/videos.xml?channel_id=UCk3JZr7eS3pg5AGEvBdEvFg"
            feed_url = args[0]
            match = re.search(r'channel_id=(UC[a-zA-Z0-9_-]+)', feed_url)
            if match:
                channel_id = match.group(1)
            else:
                # Try link field
                link = ch.get("link", "")
                link_match = re.search(r'channel/(UC[a-zA-Z0-9_-]+)', link)
                if link_match:
                    channel_id = link_match.group(1)
                else:
                    print(f"Could not extract channel ID for {title} (URL: {feed_url})")
                    continue
            
            if channel_id not in seen_ids:
                seen_ids.add(channel_id)
                merged_channels.append({
                    "name": title,
                    "channel_id": channel_id
                })
                
    print(f"\nTotal merged unique channels: {len(merged_channels)}")
    
    # Let's update config.json and config_multipurpose.json
    configs = ["config.json", "config_multipurpose.json"]
    for config_name in configs:
        config_path = os.path.join(assets_dir, config_name)
        if not os.path.exists(config_path):
            print(f"Warning: {config_name} not found.")
            continue
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            
        # Update youtube_channels list
        config_data["youtube_channels"] = merged_channels
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
            
        print(f"Successfully updated {config_name} with {len(merged_channels)} channels.")

if __name__ == "__main__":
    main()
