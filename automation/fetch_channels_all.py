import urllib.request
import urllib.parse
import re
import json
import time
import os

categories_map = {
    "cooking_channels.json": [
        "Village Cooking Channel", "Madras Samayal", "Chef Damu", "Venkatesh Bhat's Idhayam Thotta Samayal",
        "Village Food Factory", "Gomathi's Kitchen", "Salem Kitchen", "Kovai Samayal", "Tamil Food Masala",
        "Traditional Tamil Samayal", "Grandma's Kitchen", "Subbu's Kitchen", "Amma Samayal", "Cooking Bow",
        "Simply Samayal", "Madurai Samayal", "Chennai Samayal", "Apoorvas Nalabagam", "Master Chef Tamil",
        "Danush Samayal", "Nanjil Samayal", "Chettinad Samayal", "Village Food Secrets", "Foodie Woodie",
        "Foodie Tamizha", "Gomathi Samayal", "Shravanthi's Kitchen", "Wow Varuni", "Hema's Kitchen",
        "Srimathi's Kitchen", "Jeya Samayal", "Kavitha Samayal", "South Indian Samayal", "Tamil Food",
        "Cook with Puttu", "Subha Samayal", "Mrs. Karthik Samayal", "Deepa's Kitchen", "Annapoorna Samayal",
        "Peppa Foodie Cooking", "Food Imprints", "Innaiku Enna Samayal", "Abhi Lifestory Cooking",
        "Revathy Shanmugam Cooking", "Samayal Samayal Food", "Food Area Tamil", "Veg Recipes of Karnataka Tamil",
        "Semma Samayal Cooking", "Grandma Traditional Food", "Village Village Cooking"
    ],
    "comedy_channels.json": [
        "Parithabangal", "Temple Monkeys", "Nakkalites", "Mic Set", "Eruma Saani", "Jump Cuts",
        "BlackSheep", "Put Chutney", "Being Thamizhan", "Finally", "Smile Settai", "Araathi",
        "Tamil Short Cuts", "Circusgun.com", "Madras Central", "Madras Prank", "Fun Panrom",
        "Pranksters Rahul", "Prankster Rahul", "Cheeky Monkeys", "Info Bells Tamil", "Chutti TV",
        "Smile Web Series", "Comedy Raja", "Vijay TV Comedy", "KPY Comedy", "Kalakka Povathu Yaaru",
        "Athu Ithu Ethu", "Adithya TV Comedy", "Sirippoli Comedy", "Tamil Comedy Junction", "Tamil Comedy Scenes",
        "Goundamani Senthil Comedy", "Vadivelu Comedy Hub", "Vivek Comedy Scenes", "Santhanam Comedy Scenes",
        "Karunas Comedy", "Yogi Babu Comedy", "Soori Comedy Scenes", "Tamil Cinema Comedy", "Comedy Express",
        "Comedy World Tamil", "Siri Siri", "Fun Unlimited Tamil", "Tamil Talkies Comedy", "Comedy Bazaar",
        "Sirippu Varuthu", "Lollu Sabha Comedy", "Vadivelu Memes", "Tamil Mimicry Show"
    ],
    "music_channels.json": [
        "Think Music India", "Sony Music South", "Muzik247", "Saregama Tamil", "Trend Music",
        "Aditya Music Tamil", "Lahari Music Tamil", "Sun Music", "Isaiyaruvi TV", "Raj Musix Tamil",
        "Divo Music", "Noise and Grains", "U1 Records", "Raaga Tamil Music", "Ilaiyaraaja Official",
        "A.R. Rahman Official", "Anirudh Ravichander Official", "Harris Jayaraj Official", "Yuvan Shankar Raja Official",
        "Santhosh Narayanan Official", "G.V. Prakash Kumar Official", "D. Imman Official", "Hiphop Tamizha Official",
        "Vijay Antony Official", "Sid Sriram Official", "Pradeep Kumar Official", "Jonita Gandhi Official",
        "Shreya Ghoshal Official", "S.P. Balasubrahmanyam Official", "K.J. Yesudas Music", "MSV Music",
        "Deva Hits Music", "Vidyasagar Hits", "Mani Sharma Music", "Karthik Music", "Vijay Yesudas Music",
        "Haricharan Music", "Chinmayi Sripada Official", "Shweta Mohan Official", "Anuradha Sriram Music",
        "Andrea Jeremiah Official", "Tamil Devotional Songs", "Saregama Devotional Tamil", "Symphony Devotional Tamil",
        "Bakthi Music Tamil", "Christian Songs Tamil", "Tamil Folk Music", "Independent Tamil Music",
        "Tamil Rap Music", "Behindwoods Music"
    ],
    "troll_channels.json": [
        "Today Trending", "TP MEMES", "KP TROLL", "Troll Vedi", "Troll Cinema", "Tamil Troll Master",
        "Cinema Ticket", "Vera Level Trolls", "Doomangoli", "Plip Plip", "Temple Monkeys Troll",
        "Sweat Shop", "Naan Thaan Da Troll", "Mr. Local Troll", "Tamil Memes", "Fun Panrom Troll",
        "Troll Boys", "Chella Kutty Troll", "Madan Gowri Troll", "GP Muthu Trolls", "TT Troll",
        "Cinema Troll", "Vadivelu Troll Hub", "Goundamani Troll", "Santhanam Troll", "Vivek Troll",
        "Lollu Sabha Troll", "Tamil Roasters", "Roaster Rithu", "Roast Mortem", "Tamil Tech Troll",
        "VJ Siddhu Troll", "Irfan Troll", "Behindwoods Troll", "Galatta Troll", "Sun TV Troll",
        "Vijay TV Troll", "Cook with Comali Troll", "Bigg Boss Tamil Troll", "Local Troll Boy",
        "Chennai Troll", "Madurai Troll", "Coimbatore Troll", "Trichy Troll", "Nelli Troll",
        "Salem Troll", "Kovai Troll", "Tamil Meme Creator", "Meme Nation Tamil", "Meme Hub Tamil"
    ],
    "news_channels.json": [
        "Polimer News", "Puthiyathalaimurai TV", "News7 Tamil", "News18 Tamilnadu", "Thanthi TV",
        "Kalaignar TV News", "Captain News", "BBC News Tamil", "Oneindia Tamil", "Tamil Hindu",
        "Dinamalar", "Vikatan WebTV", "Sun News", "NewsTamil 24X7", "Sathiyam News", "IBC Tamil",
        "YouTurn", "RedPix News", "Behindwoods News", "Galatta News", "Behindwoods Air", "Jeyam TV",
        "Velicham TV", "Moon TV", "Lotus News", "Cauvery News", "News Fast", "Samayam Tamil",
        "Asianet News Tamil", "NewsGlitz", "Nakkheeran Studio", "Nakkheeran webtv", "Chennai City News",
        "Raj News Tamil", "Jaya Plus", "Captain TV", "News Tamil", "Dinamani News", "Nakkeeran News",
        "Tamil News Live", "Malaimurasu TV", "Thanthi News", "News Tamil Live", "Puthiya Thalaimurai News",
        "Tamil News Today", "Polimer News Live", "News7 Tamil Live", "News18 Tamil Live", "Cauvery News Live",
        "Sathiyam News Live"
    ],
    "cinema_channels.json": [
        "Behindwoods TV", "Galatta Tamil", "Tamil Cinema Review", "Blue Sattai Maaran", "Valai Pechu",
        "Filmi Craft", "Kodangi Review", "Behindwoods Gold", "Galatta Voice", "IndiaGlitz Tamil Movies",
        "NewsGlitz Cinema", "Cineulagam", "Cinema Vikatan", "RedPix Cinema", "Tamil Talkies", "ItisPrashanth",
        "Cinema Ticket Reviews", "Cine Samugam", "Tamil Cinema News", "Cinema Express Tamil", "Indiaglitz News",
        "Galatta Exclusive", "Behindwoods Air Cinema", "Cinema Central", "Kollywood Cinema", "Tamil Cinema Updates",
        "Movie Review Tamil", "Cine News", "Kollywood News", "Behindwoods TV Show", "Galatta Special",
        "Cinema Hub", "Film Companion Local", "Baradwaj Rangan", "Film Companion Tamil", "Tamil Movie Promos",
        "Jukebox Tamil Cinema", "Cinema Box Office Tamil", "Kollywood Box Office", "Behindwoods Air News",
        "Cine Time", "Cine Focus", "Film Focus Tamil", "Cinema Cafe", "Film Cafe Tamil", "Kollywood Cafe",
        "Behindwoods Interview", "Galatta Interview", "IndiaGlitz Interview", "Cineulagam Interview"
    ]
}

def get_channel_id(query):
    try:
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}&sp=EgIQAg%253D%253D"
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            match = re.search(r'"browseId":"(UC[a-zA-Z0-9_-]{22})"', html)
            if match:
                return match.group(1)
            match = re.search(r'/channel/(UC[a-zA-Z0-9_-]{22})', html)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Error searching {query}: {e}")
    return None

def main():
    assets_dir = "app/src/main/assets"
    if not os.path.exists(assets_dir):
        print(f"Assets directory not found at {assets_dir}")
        return

    for filename, queries in categories_map.items():
        print(f"\n--- Starting category: {filename} ({len(queries)} channels) ---")
        filepath = os.path.join(assets_dir, filename)
        
        # Load existing data if any, to avoid re-fetching what we already have
        existing_data = []
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                print(f"Error reading existing file {filename}: {e}")
        
        existing_titles = {item['title'].lower() for item in existing_data}
        channels_list = list(existing_data)
        
        count = len(channels_list)
        for q in queries:
            if q.lower() in existing_titles:
                print(f"Skipping {q} (already exists)")
                continue
                
            print(f"Fetching ID for: {q}...", end="", flush=True)
            cid = get_channel_id(q)
            if cid:
                channel_obj = {
                    "title": q,
                    "provider": "rss",
                    "arguments": [
                        f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
                    ],
                    "link": f"https://www.youtube.com/channel/{cid}"
                }
                channels_list.append(channel_obj)
                existing_titles.add(q.lower())
                count += 1
                print(f" SUCCESS: {cid}")
            else:
                print(" FAILED")
            
            # Save progress incrementally
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(channels_list, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Error saving progress: {e}")
                
            time.sleep(0.5) # Sleep to avoid rate limits
            
        print(f"Completed {filename}. Total: {len(channels_list)} channels")

if __name__ == "__main__":
    main()
