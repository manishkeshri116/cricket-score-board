import os


COMMENTARY_URL = "https://content.crickapi.com/commentary/getBallFeeds"
META_URL = "https://crickapi.com/live/getMatchMetaData"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9,hi;q=0.8",
    "authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImV4cGlyZXNJbiI6IjM2NWQifQ.eyJ0aW1lIjoxNjYwMDQ2NjIwMDAwfQ.bTEmMWlR7hLRUHxPPq6-1TP7cuuW7m6sZ9jcdbYzLRA",
    "cache-control": "no-cache",
    "cc": "IN",
    "content-type": "application/json",
    "origin": "https://crex.com",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": "https://crex.com/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
}

MATCH_KEY = os.environ.get("MATCH_KEY", "128Y").strip() or "128Y"
META_PAYLOAD = {"mf": MATCH_KEY}
COMMENTARY_PAYLOAD = {"matchKey": MATCH_KEY, "lastDocId": None, "filters": {}}

PLAYER_IMG_BASE = "https://cricketvectors.akamaized.net/cricketimages/Players/{fkey}.png"
TEAM_IMG_BASE = "https://cricketvectors.akamaized.net/cricketimages/Teams/{fkey}.png"
IMAGE_PROXY_BASE = "https://images.weserv.nl/?url={url}"

BACKEND_PUBLIC_URL = os.environ.get("BACKEND_PUBLIC_URL", "http://127.0.0.1:5001").rstrip("/")
GOOGLE_IMAGE_API_KEY = os.environ.get("GOOGLE_IMAGE_API_KEY") or os.environ.get("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_IMAGE_CX = os.environ.get("GOOGLE_IMAGE_CX") or os.environ.get("GOOGLE_SEARCH_CX", "")
BACKGROUND_MUSIC_URL = os.environ.get(
    "BACKGROUND_MUSIC_URL",
    "",
)
CROWD_MUSIC_URL = os.environ.get("CROWD_MUSIC_URL", f"{BACKEND_PUBLIC_URL}/audio/stadium-crowd.mp3")
HINDI_COMMENTARY_STREAM_URL = os.environ.get("HINDI_COMMENTARY_STREAM_URL", "")
