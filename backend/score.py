from flask import Flask, Response, jsonify, request
import requests
from flask_cors import CORS
import json
import os
import re
from urllib.parse import quote

app = Flask(__name__)
CORS(app)

COMMENTARY_URL = "https://content.crickapi.com/commentary/getBallFeeds"
META_URL        = "https://crickapi.com/live/getMatchMetaData"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9,hi;q=0.8",
    "authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImV4cGlyZXNJbiI6IjM2NWQifQ.eyJ0aW1lIjoxNjYwMDQ2NjIwMDAwfQ.bTEmMWlR7hLRUHxPPq6-1TP7cuuW7m6sZ9jcdbYzLRA",
    "cache-control": "no-cache", "cc": "IN", "content-type": "application/json",
    "origin": "https://crex.com", "pragma": "no-cache", "priority": "u=1, i",
    "referer": "https://crex.com/", "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors", "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
}

META_PAYLOAD       = {"mf": "119D"}
COMMENTARY_PAYLOAD = {"matchKey": "119D", "lastDocId": None, "filters": {}}

PLAYER_IMG_BASE = "https://cricketvectors.akamaized.net/cricketimages/Players/{fkey}.png"
TEAM_IMG_BASE   = "https://cricketvectors.akamaized.net/cricketimages/Teams/{fkey}.png"
IMAGE_PROXY_BASE = "https://images.weserv.nl/?url={url}"
BACKEND_PUBLIC_URL = os.environ.get("BACKEND_PUBLIC_URL", "http://127.0.0.1:5001").rstrip("/")
GOOGLE_IMAGE_API_KEY = os.environ.get("GOOGLE_IMAGE_API_KEY") or os.environ.get("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_IMAGE_CX = os.environ.get("GOOGLE_IMAGE_CX") or os.environ.get("GOOGLE_SEARCH_CX", "")
BACKGROUND_MUSIC_URL = os.environ.get(
    "BACKGROUND_MUSIC_URL",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
)
CROWD_MUSIC_URL = os.environ.get("CROWD_MUSIC_URL", "")
HINDI_COMMENTARY_STREAM_URL = os.environ.get("HINDI_COMMENTARY_STREAM_URL", "")

# ── state ──────────────────────────────────────────────────────────
latest_score = {
    "team": "", "team1": "", "team2": "",
    "team1Fkey": "", "team2Fkey": "",
    "team1Img": "", "team2Img": "",
    "battingTeam": "", "bowlingTeam": "",
    "battingTeamFkey": "", "bowlingTeamFkey": "",
    "battingTeamImg": "", "bowlingTeamImg": "",
    "venue": "", "matchTime": "", "toss": "",
    "score": "0/0", "over": "0.0", "rr": "0.00",
    "event": "", "ticker": "", "winChance": "",
    "lastBallRuns": "", "lastBatter": "", "lastBowler": "", "lastBallSpeed": "",
    "thisOver": [], "recentOvers": [],
    "squadPlayers": [],
    "team1Squad": [], "team2Squad": [],
    "batsmen": [], "batsmenStats": [], "striker": "", "nonStriker": "",
    "bowler": "", "bowlerStats": {},
    "lastWicket": "", "partnership": "",
    "matchResult": "",
    "inningsBreak": False,
    "inningsBreakText": "",
    "target": "",
    "inningsLimitBalls": "",
    "inning": "",
}

latest_id      = 0
meta_loaded    = False
current_inning = None
bowler_data    = {}       # full_name -> stats dict
batsman_store  = {}       # full_name -> {runs,balls,fours,sixes,fkey}
dismissed      = set()    # full names dismissed this innings
confirmed_pair = []       # confirmed on-crease pair from last type:"o"
player_img_map = {}       # fkey -> image url (from type:"w" url field)
team_img_map   = {}       # fkey -> image url
completed_overs = []
players_seen = {}
team_squads = {}
player_image_overrides = {}  # fkey or lower-case player name -> manual image url
team_image_overrides = {}    # fkey or lower-case team name -> manual logo url
player_web_image_cache = {}  # lower-case player name -> discovered image url
partnership_runs = 0
partnership_balls = 0

# ── helpers ────────────────────────────────────────────────────────
def pimg(fkey):
    if not fkey:
        return ""
    return player_image_overrides.get(fkey) or player_img_map.get(fkey, PLAYER_IMG_BASE.format(fkey=fkey))

def player_override(fkey="", name=""):
    fkey = str(fkey or "").strip()
    name_key = str(name or "").strip().lower()
    return player_image_overrides.get(fkey) or player_image_overrides.get(name_key, "")

def valid_image_url(url):
    return bool(re.match(r"^https?://", str(url or "").strip(), re.I))

def timg(fkey):
    if not fkey:
        return ""
    return team_image_overrides.get(fkey) or team_img_map.get(fkey, TEAM_IMG_BASE.format(fkey=fkey))

def team_override(fkey="", name=""):
    fkey = str(fkey or "").strip()
    name_key = str(name or "").strip().lower()
    return team_image_overrides.get(fkey) or team_image_overrides.get(name_key, "")

def proxy_img(url):
    return IMAGE_PROXY_BASE.format(url=url.replace("https://", "").replace("http://", ""))

def player_placeholder_url(name):
    name = str(name or "Player").strip() or "Player"
    return f"{BACKEND_PUBLIC_URL}/player-placeholder/{quote(name)}.svg"

def is_bad_player_image_url(url):
    return bool(re.search(
        r"\b(family|meets|modi|govinda|event|ceremony|poster|logo)\b",
        str(url or "").replace("_", " "),
        re.I,
    ))

def wikimedia_file_url(title):
    try:
        res = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "titles": title,
                "prop": "imageinfo",
                "iiprop": "url",
            },
            timeout=2,
            headers={"user-agent": HEADERS["user-agent"]},
        )
        if not res.ok:
            return ""
        pages = res.json().get("query", {}).get("pages", {})
        for page in pages.values():
            infos = page.get("imageinfo") or []
            if infos and valid_image_url(infos[0].get("url")):
                return infos[0]["url"]
    except Exception:
        return ""
    return ""

def search_wikimedia_player_images(name):
    name_tokens = [
        token for token in re.findall(r"[a-z0-9]+", str(name or "").lower())
        if len(token) > 2
    ]
    if len(name_tokens) < 2:
        return []

    try:
        res = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrnamespace": 6,
                "gsrlimit": 4,
                "gsrsearch": f'{name} cricketer filetype:bitmap',
                "prop": "imageinfo",
                "iiprop": "url",
            },
            timeout=2,
            headers={"user-agent": HEADERS["user-agent"]},
        )
        if not res.ok:
            return []
        pages = res.json().get("query", {}).get("pages", {})
        urls = []
        for page in pages.values():
            title = page.get("title", "")
            title_text = title.lower().replace("_", " ")
            if not all(token in title_text for token in name_tokens[:2]):
                continue
            if re.search(r"\b(family|meets|modi|govinda|event|ceremony|poster|logo)\b", title_text, re.I):
                continue
            if not re.search(r"\.(jpg|jpeg|png|webp)$", title, re.I):
                continue
            infos = page.get("imageinfo") or []
            image_url = infos[0].get("url", "") if infos else wikimedia_file_url(title)
            if valid_image_url(image_url) and not is_bad_player_image_url(image_url):
                urls.append(image_url)
        return urls
    except Exception:
        return []

def search_google_player_images(name):
    if not GOOGLE_IMAGE_API_KEY or not GOOGLE_IMAGE_CX:
        return []

    try:
        res = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": GOOGLE_IMAGE_API_KEY,
                "cx": GOOGLE_IMAGE_CX,
                "q": f"{name} cricketer headshot",
                "searchType": "image",
                "num": 3,
                "safe": "active",
                "imgType": "face",
            },
            timeout=3,
            headers={"user-agent": HEADERS["user-agent"]},
        )
        if not res.ok:
            return []
        urls = []
        for item in res.json().get("items", []):
            image_url = item.get("link", "")
            if valid_image_url(image_url) and not is_bad_player_image_url(image_url):
                urls.append(image_url)
        return urls
    except Exception:
        return []

def lookup_player_web_images(name):
    name = str(name or "").strip()
    if not name:
        return []

    cache_key = name.lower()
    if cache_key in player_web_image_cache:
        return player_web_image_cache[cache_key]

    urls = []
    for title in [name, f"{name} (cricketer)"]:
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
            res = requests.get(url, timeout=2, headers={"user-agent": HEADERS["user-agent"]})
            if not res.ok:
                continue
            data = res.json()
            image_url = (
                data.get("thumbnail", {}).get("source")
                or data.get("originalimage", {}).get("source")
                or ""
            )
            if valid_image_url(image_url) and not is_bad_player_image_url(image_url):
                urls.append(image_url)
        except Exception:
            continue

    urls.extend(search_google_player_images(name))
    urls.extend(search_wikimedia_player_images(name))
    player_web_image_cache[cache_key] = list(dict.fromkeys(urls))
    return player_web_image_cache[cache_key]

def player_img_candidates(fkey="", primary_url="", name=""):
    urls = []
    if primary_url:
        urls.append(primary_url)
        urls.append(proxy_img(primary_url))
    if fkey:
        direct = PLAYER_IMG_BASE.format(fkey=fkey)
        urls.extend([
            direct,
            proxy_img(direct),
            f"https://cricketvectors.akamaized.net/Players/{fkey}.png",
            proxy_img(f"https://cricketvectors.akamaized.net/Players/{fkey}.png"),
        ])
    for web_image in lookup_player_web_images(name):
        urls.append(web_image)
        urls.append(proxy_img(web_image))
    if name:
        urls.append(player_placeholder_url(name))
    return list(dict.fromkeys(urls))

def basic_player_img_candidates(fkey="", primary_url="", name=""):
    urls = []
    if primary_url:
        urls.extend([primary_url, proxy_img(primary_url)])
    if fkey:
        direct = PLAYER_IMG_BASE.format(fkey=fkey)
        urls.extend([direct, proxy_img(direct)])
    urls.append(player_placeholder_url(name))
    return list(dict.fromkeys(urls))

def team_img_candidates(fkey="", primary_url=""):
    urls = []
    if primary_url:
        urls.append(primary_url)
        urls.append(proxy_img(primary_url))
    if fkey:
        direct = TEAM_IMG_BASE.format(fkey=fkey)
        alt = f"https://cricketvectors.akamaized.net/Teams/{fkey}.png"
        urls.extend([direct, proxy_img(direct), alt, proxy_img(alt)])
    return list(dict.fromkeys(urls))

def refresh_team_images():
    team1_img = team_override(latest_score.get("team1Fkey", ""), latest_score.get("team1", "")) or timg(latest_score.get("team1Fkey", ""))
    team2_img = team_override(latest_score.get("team2Fkey", ""), latest_score.get("team2", "")) or timg(latest_score.get("team2Fkey", ""))

    if team1_img:
        latest_score["team1Img"] = team1_img
        latest_score["team1ImgCandidates"] = team_img_candidates(latest_score.get("team1Fkey", ""), team1_img)
    if team2_img:
        latest_score["team2Img"] = team2_img
        latest_score["team2ImgCandidates"] = team_img_candidates(latest_score.get("team2Fkey", ""), team2_img)

    refresh_live_team_images()

def team_side_from_fkey(fkey):
    fkey = str(fkey or "").strip()
    if fkey and fkey == latest_score.get("team1Fkey"):
        return "team1"
    if fkey and fkey == latest_score.get("team2Fkey"):
        return "team2"
    return ""

def refresh_live_team_images():
    for role in ["batting", "bowling"]:
        name_key = f"{role}Team"
        fkey_key = f"{role}TeamFkey"
        img_key = f"{role}TeamImg"
        candidates_key = f"{role}TeamImgCandidates"
        side = team_side_from_fkey(latest_score.get(fkey_key, ""))
        if side:
            latest_score[name_key] = latest_score.get(side, latest_score.get(name_key, ""))
            fkey = latest_score.get(f"{side}Fkey", "")
            image_url = latest_score.get(f"{side}Img", "") or timg(fkey)
            latest_score[img_key] = image_url
            latest_score[candidates_key] = team_img_candidates(fkey, image_url)

def set_live_teams_from_batting_fkey(bat_fkey=""):
    bat_side = team_side_from_fkey(bat_fkey)
    if not bat_side:
        return

    bowl_side = "team2" if bat_side == "team1" else "team1"
    latest_score["battingTeam"] = latest_score.get(bat_side, "")
    latest_score["battingTeamFkey"] = latest_score.get(f"{bat_side}Fkey", "")
    latest_score["bowlingTeam"] = latest_score.get(bowl_side, "")
    latest_score["bowlingTeamFkey"] = latest_score.get(f"{bowl_side}Fkey", "")
    refresh_live_team_images()

def remember_player(name, fkey="", role="", image_url=""):
    name = str(name or "").strip()
    fkey = str(fkey or "").strip()
    if not name:
        return

    key = name.lower()
    if fkey:
        for existing_key, existing in list(players_seen.items()):
            if existing.get("fkey") == fkey:
                key = existing_key
                if len(name) > len(existing.get("name", "")):
                    players_seen.pop(existing_key, None)
                    key = name.lower()
                break

    current = players_seen.get(key, {})
    if image_url and fkey:
        player_img_map[fkey] = image_url

    primary_img = player_override(fkey or current.get("fkey", ""), name) or image_url or current.get("img", "") or pimg(fkey or current.get("fkey", ""))

    players_seen[key] = {
        "name": name if len(name) >= len(current.get("name", "")) else current.get("name", name),
        "role": role or current.get("role", ""),
        "fkey": fkey or current.get("fkey", ""),
        "img": primary_img,
        "imgCandidates": player_img_candidates(fkey or current.get("fkey", ""), primary_img, name),
    }

def remember_team_squad_player(team_fkey, name, fkey="", role="", image_url=""):
    team_fkey = str(team_fkey or "").strip()
    name = str(name or "").strip()
    fkey = str(fkey or "").strip()
    if not team_fkey or not name:
        return

    team_squads.setdefault(team_fkey, {})
    key = fkey or name.lower()
    primary_img = player_override(fkey, name) or image_url or pimg(fkey)
    team_squads[team_fkey][key] = {
        "name": name,
        "role": role,
        "fkey": fkey,
        "img": primary_img,
        "imgCandidates": basic_player_img_candidates(fkey, primary_img, name),
    }

def build_squad_players():
    latest_score["squadPlayers"] = list(players_seen.values())[:11]

def build_team_squads():
    for side in ["team1", "team2"]:
        fkey = latest_score.get(f"{side}Fkey", "")
        players = list((team_squads.get(fkey) or {}).values())
        latest_score[f"{side}Squad"] = players[:11]

def recover_team_squads_from_commentary(max_pages=40):
    team1_fkey = latest_score.get("team1Fkey", "")
    team2_fkey = latest_score.get("team2Fkey", "")
    if team1_fkey and team2_fkey:
        if len(team_squads.get(team1_fkey, {})) >= 11 and len(team_squads.get(team2_fkey, {})) >= 11:
            build_team_squads()
            return

    payload = dict(COMMENTARY_PAYLOAD)
    payload["lastDocId"] = None
    seen_pages = set()

    for _ in range(max_pages):
        page_key = str(payload.get("lastDocId"))
        if page_key in seen_pages:
            break
        seen_pages.add(page_key)

        try:
            res = requests.post(COMMENTARY_URL, json=payload, headers=HEADERS, timeout=5)
            data = res.json()
        except Exception:
            break

        events = data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []
        if not events:
            break

        for event in events:
            if event.get("type") == "ps":
                role = "BAT" if str(event.get("cat", "")) == "1" else "BOWL"
                remember_team_squad_player(event.get("tf", ""), event.get("n", ""), event.get("pf", ""), role, event.get("url", ""))

        if team1_fkey and team2_fkey:
            if len(team_squads.get(team1_fkey, {})) >= 11 and len(team_squads.get(team2_fkey, {})) >= 11:
                break

        ids = [event.get("id") for event in events if event.get("id")]
        if not ids:
            break
        payload["lastDocId"] = min(ids)

    build_team_squads()

def parse_sc(s):
    try:
        r = int(s.split("(")[0].strip())
        b = int(s.split("(")[1].rstrip(")").strip())
        return r, b
    except: return 0, 0

def parse_bowler_figures(value):
    try:
        left, overs_part = str(value).split("(", 1)
        wickets, runs = left.split("-", 1)
        overs_text = overs_part.rstrip(")")
        over_bits = overs_text.split(".", 1)
        balls = int(over_bits[0]) * 6 + int(over_bits[1] if len(over_bits) > 1 else 0)
        return int(runs), int(wickets), balls
    except Exception:
        return None

def ball_runs(value):
    value = str(value).upper()
    if value in ["WD", "NB"]:
        return 1
    if value in ["W", ""]:
        return 0
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else 0

def normalize_ball(value):
    value = str(value).strip().upper()
    return "WD" if value == "WD" else "NB" if value == "NB" else value

def is_legal_delivery(value):
    return str(value or "").strip().upper() not in ["WD", "NB"]

def extract_ball_speed(event):
    speed_keys = [
        "speed", "ball_speed", "ballSpeed", "delivery_speed",
        "deliverySpeed", "spd", "pace", "kph", "kmph"
    ]
    for key in speed_keys:
        value = event.get(key)
        if value in [None, ""]:
            continue
        text = str(value).strip()
        match = re.search(r"(\d{2,3}(?:\.\d+)?)", text)
        if match:
            unit = "km/h" if re.search(r"km/?h|kmph", text, re.I) else "kph"
            return f"{match.group(1)} {unit}"

    for key in ["c2", "c1", "commentary", "comment", "desc", "description"]:
        text = strip_html(event.get(key, ""))
        match = re.search(r"\b(\d{2,3}(?:\.\d+)?)\s*(kph|kmph|km/h|k\.p\.h\.?)\b", text, re.I)
        if match:
            return f"{match.group(1)} km/h"
    return ""

def over_total(balls):
    return sum(ball_runs(ball) for ball in balls)

def current_over_label(over_text):
    try:
        return f"OVER {int(str(over_text).split('.')[0]) + 1}"
    except Exception:
        return "THIS OVER"

def build_recent_overs(label="THIS OVER"):
    overs = []
    if latest_score["thisOver"]:
        overs.append({
            "label": label,
            "balls": latest_score["thisOver"],
            "total": over_total(latest_score["thisOver"]),
            "current": True,
        })

    overs.extend(reversed(completed_overs[-3:]))
    latest_score["recentOvers"] = overs

def sr(r, b): return round(r/b*100, 2) if b else 0.0
def eco(r, b): return round(r/(b/6), 2) if b else 0.0
def ovs(b): return f"{b//6}.{b%6}"

def balls_to_over_text(total_balls):
    total_balls = max(0, int(total_balls or 0))
    return f"{total_balls // 6}.{total_balls % 6}"

def normalize_over_value(value):
    try:
        parts = str(value or "0").split(".", 1)
        overs = int(parts[0] or 0)
        balls = int(parts[1] if len(parts) > 1 and parts[1] else 0)
        return balls_to_over_text(overs * 6 + balls)
    except Exception:
        return str(value or "")

def overs_to_balls(value):
    try:
        parts = str(value or "0").split(".", 1)
        overs = int(parts[0] or 0)
        balls = int(parts[1] if len(parts) > 1 and parts[1] else 0)
        return overs * 6 + balls
    except Exception:
        return 0

def over_after_delivery(raw_over, delivery, previous_over=""):
    raw_balls = overs_to_balls(raw_over)
    previous_balls = overs_to_balls(previous_over)

    if is_legal_delivery(delivery):
        return balls_to_over_text(raw_balls)

    # Some feeds advance the ball counter even for WD/NB. They are not legal
    # deliveries, so keep the over at the last legal ball and never move back.
    adjusted_balls = max(0, raw_balls - 1)
    if previous_balls and adjusted_balls < previous_balls:
        adjusted_balls = previous_balls
    return balls_to_over_text(adjusted_balls)

def first_innings_complete(score_value, over_value):
    _, wickets = parse_score_value(score_value)
    balls = overs_to_balls(over_value)
    return wickets >= 10 or balls in [120, 300]

def parse_score_value(value):
    try:
        runs, wickets = str(value or "0/0").split("/", 1)
        return int(runs), int("".join(ch for ch in wickets if ch.isdigit()) or 0)
    except Exception:
        return 0, 0

def target_from_score(score_value):
    runs, _ = parse_score_value(score_value)
    return str(runs + 1) if runs else ""

def innings_limit_balls_from_over(over_value):
    balls = overs_to_balls(over_value)
    return 300 if balls > 120 else 120

def extract_need_runs(text):
    clean = strip_html(text)
    patterns = [
        r"\bneeds?\s+(\d+)\s+(?:runs?\s+)?in\s+(\d+)\s+balls?\b",
        r"\brequires?\s+(\d+)\s+(?:runs?\s+)?in\s+(\d+)\s+balls?\b",
        r"\bneed\s+(\d+)\s+off\s+(\d+)\b",
        r"\brequires?\s+(\d+)\s+off\s+(\d+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, re.I)
        if match:
            return int(match.group(1))
    return 0

def extract_need_context(text):
    clean = strip_html(text)
    patterns = [
        r"\bneeds?\s+(\d+)\s+(?:runs?\s+)?in\s+(\d+)\s+balls?\b",
        r"\brequires?\s+(\d+)\s+(?:runs?\s+)?in\s+(\d+)\s+balls?\b",
        r"\bneed\s+(\d+)\s+off\s+(\d+)\b",
        r"\brequires?\s+(\d+)\s+off\s+(\d+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, re.I)
        if match:
            return int(match.group(1)), int(match.group(2))
    return 0, 0

def plausible_target(value):
    try:
        target = int(value)
        limit = int(latest_score.get("inningsLimitBalls") or 120)
        return 1 <= target <= (420 if limit > 120 else 300)
    except Exception:
        return False

def format_percent(value):
    try:
        number = float(str(value).replace("%", "").strip())
        if 0 <= number <= 1:
            number *= 100
        return f"{round(max(0, min(100, number)))}%"
    except Exception:
        return ""

def short_team_name(name):
    words = re.findall(r"[A-Za-z0-9]+", str(name or ""))
    if not words:
        return ""
    if len(words) == 1:
        return words[0][:12]
    return "".join(word[0] for word in words[:3]).upper()

def team_label_from_key(key):
    key_text = str(key or "").strip()
    if not key_text:
        return ""

    team = team_name_from_fkey(key_text) or team_from_abbr(key_text)
    if team and team != key_text:
        return short_team_name(team)

    key_lower = key_text.lower()
    for team in [latest_score.get("team1", ""), latest_score.get("team2", "")]:
        if team and (key_lower in team.lower() or team.lower() in key_lower):
            return short_team_name(team)

    cleaned = re.sub(r"(win|chance|probability|percent|pct|team|_)"," ", key_text, flags=re.I).strip()
    return short_team_name(cleaned or key_text)

def full_team_name_from_text(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""

    best = ""
    for team in [latest_score.get("team1", ""), latest_score.get("team2", "")]:
        team_text = team.lower()
        if not team_text:
            continue
        if team_text in text or text in team_text:
            return team

        team_words = [word for word in re.findall(r"[a-z0-9]+", team_text) if len(word) > 2]
        if team_words and all(word in text for word in team_words[:2]):
            best = team
    return best

def opposite_team_name(team):
    team = full_team_name_from_text(team) or str(team or "")
    if team and latest_score.get("team1") and team.lower() == latest_score["team1"].lower():
        return latest_score.get("team2", "")
    if team and latest_score.get("team2") and team.lower() == latest_score["team2"].lower():
        return latest_score.get("team1", "")
    return ""

def toss_team_name(value):
    text = str(value or "").strip()
    team = full_team_name_from_text(text)
    if team:
        return team

    # Captain/name fallback for known current match.
    if re.search(r"\bshreyas\s+iyer\b", text, re.I):
        return full_team_name_from_text("Punjab Kings") or "Punjab Kings"
    return text

def default_win_team_label():
    if latest_score.get("team2"):
        return short_team_name(latest_score["team2"])
    if latest_score.get("team1"):
        return short_team_name(latest_score["team1"])
    return "TEAM"

def extract_win_chance(obj, depth=0):
    if depth > 4:
        return ""
    if isinstance(obj, dict):
        values = []
        for key, value in obj.items():
            key_text = str(key).lower()
            is_win_key = "win" in key_text and "winner" not in key_text
            is_probability_key = any(word in key_text for word in ["chance", "prob", "percent", "pct"])

            if is_win_key and is_probability_key:
                if isinstance(value, (int, float, str)):
                    direct = format_percent(value) if isinstance(value, (int, float)) else ""
                    if direct:
                        label = team_label_from_key(key) or default_win_team_label()
                        return f"{label} {direct}"
                    match = re.search(r"\d+(?:\.\d+)?\s*%", str(value))
                    if match:
                        label = team_label_from_key(key) or default_win_team_label()
                        return f"{label} {match.group(0).replace(' ', '')}"
                if isinstance(value, dict):
                    for nested_key, nested_value in value.items():
                        percent = format_percent(nested_value)
                        if percent:
                            label = team_label_from_key(nested_key)
                            values.append(f"{label} {percent}" if label else percent)
                    if values:
                        return " / ".join(values[:2])

            nested = extract_win_chance(value, depth + 1)
            if nested:
                return nested
    elif isinstance(obj, list):
        for item in obj:
            nested = extract_win_chance(item, depth + 1)
            if nested:
                return nested
    return ""

def calculate_live_win_chance():
    if latest_score.get("matchResult"):
        return latest_score.get("winChance") or "100%"

    runs, wickets = parse_score_value(latest_score.get("score", ""))
    balls = overs_to_balls(latest_score.get("over", ""))
    if not runs and not balls:
        return f"{default_win_team_label()} 50%"

    overs_played = balls / 6 if balls else 0
    rr_value = runs / overs_played if overs_played else 0
    wickets_left = max(0, 10 - wickets)
    progress = min(1, balls / 120) if balls else 0

    chance = 50
    chance += (rr_value - 7.0) * 3.6
    chance += (wickets_left - 5) * 2.4
    chance += progress * 6

    return f"{default_win_team_label()} {round(max(5, min(95, chance)))}%"

def ticker_msg(ev, bat, bowl, runs):
    if ev == "WICKET": return f"WICKET! {bowl} dismisses {bat}!"
    if ev == "RUNOUT": return f"RUN OUT! {bat} is short of the crease!"
    if ev == "FOUR":   return f"FOUR! {bat} hits a boundary!"
    if ev == "SIX":    return f"SIX! {bat} goes big!"
    if runs == "WD":   return f"Wide ball by {bowl}"
    if runs == "NB":   return f"No ball by {bowl}"
    if str(runs).isdigit(): return f"{runs} run(s) for {bat}"
    return "Match in progress..."

def team_name_from_fkey(fkey):
    if not fkey:
        return ""
    if fkey == latest_score.get("team1Fkey"):
        return latest_score.get("team1", "")
    if fkey == latest_score.get("team2Fkey"):
        return latest_score.get("team2", "")
    return ""

def strip_html(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()

def team_from_abbr(abbr):
    original = str(abbr or "").strip()
    abbr = original.upper()
    for team in [latest_score.get("team1", ""), latest_score.get("team2", "")]:
        initials = "".join(part[0] for part in team.split() if part).upper()
        if abbr == initials:
            return team
        if original and original.lower() == team.lower():
            return team
    return original

def result_from_text(text):
    clean = strip_html(text)
    if not clean:
        return ""

    if re.search(r"\b(time\s+to\s+say\s+goodbye|signing\s+off|as\s+a\s+consequence\s+of\s+this\s+result|post[-\s]?match|match\s+summary)\b", clean, re.I):
        return "Match closed"
    if re.search(r"\b(match\s+)?tied\b", clean, re.I):
        return "Match tied"
    if re.search(r"\b(no\s+result|abandoned|called\s+off)\b", clean, re.I):
        return "No result"

    team_pattern = r"([A-Za-z][A-Za-z0-9 .&'()-]{1,60}?)"
    margin_pattern = r"(\d+)\s+(runs?|wickets?)"

    match = re.search(rf"\b{team_pattern}\s+(?:won|wins)\s+by\s+{margin_pattern}\b", clean, re.I)
    if match:
        return f"{team_from_abbr(match.group(1).strip())} won by {match.group(2)} {match.group(3).lower()}"

    match = re.search(rf"\b{team_pattern}\s+(?:beat|beats|defeated|defeats)\s+{team_pattern}\s+by\s+{margin_pattern}\b", clean, re.I)
    if match:
        return f"{team_from_abbr(match.group(1).strip())} won by {match.group(3)} {match.group(4).lower()}"

    match = re.search(r"\b([A-Z]{2,4})\s+walked away with .*?\b(\d+)-run victory\b", clean, re.I)
    if match:
        return f"{team_from_abbr(match.group(1))} won by {match.group(2)} runs"

    match = re.search(rf"\b{team_pattern}\s+walked away with .*?\b(\d+)-run victory\b", clean, re.I)
    if match:
        return f"{team_from_abbr(match.group(1).strip())} won by {match.group(2)} runs"
    return ""

def infer_match_result():
    if str(latest_score.get("inning")) not in ["2", "2nd"]:
        return ""

    target_text = str(latest_score.get("target") or "").strip()
    if not target_text.isdigit():
        return ""

    target = int(target_text)
    runs, wickets = parse_score_value(latest_score.get("score", ""))
    if not target or not runs:
        return ""

    batting_team = latest_score.get("battingTeam") or latest_score.get("team2") or "Batting team"
    bowling_team = latest_score.get("bowlingTeam") or latest_score.get("team1") or "Bowling team"

    if runs >= target:
        return f"{batting_team} won by {max(0, 10 - wickets)} wickets"

    if runs == target - 1:
        return "Match tied"

    margin = target - runs - 1
    if margin >= 0:
        return f"{bowling_team} won by {margin} runs"
    return ""

def extract_match_result(obj, depth=0):
    if depth > 4:
        return ""
    if isinstance(obj, (str, int, float)):
        return result_from_text(str(obj))
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_text = str(key).lower()
            if isinstance(value, (str, int, float)):
                text = str(value)
                if any(word in key_text for word in ["result", "status", "winner", "won", "summary", "title", "desc", "comment", "c"]):
                    result = result_from_text(text)
                    if result:
                        return result
                result = result_from_text(text)
                if result:
                    return result
            else:
                result = extract_match_result(value, depth + 1)
                if result:
                    return result
    elif isinstance(obj, list):
        for item in obj:
            result = extract_match_result(item, depth + 1)
            if result:
                return result
    return ""

def toss_from_text(text):
    clean = strip_html(text)
    patterns = [
        r"([A-Za-z .&'-]+?)\s+won\s+the\s+toss\s+and\s+(?:elected|opted|chose)\s+to\s+(bat|bowl|field)",
        r"toss\s*:\s*([A-Za-z .&'-]+?)\s+(?:elected|opted|chose)\s+to\s+(bat|bowl|field)",
        r"([A-Za-z .&'-]+?)\s+(?:elected|opted|chose)\s+to\s+(bat|bowl|field)\s+first",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, re.I)
        if match:
            team = toss_team_name(match.group(1).strip(" .-"))
            choice = match.group(2).lower()
            decision = "batting" if choice == "bat" else "bowling"
            return f"{team} won toss, {decision}"

    invited = re.search(
        r"(?:^|[.!?]\s+|,\s*)([A-Z][A-Za-z .&'-]{1,60}?)\s+won\s+the\s+toss\s+and\s+invited\s+([A-Z][A-Za-z .&'-]{1,60}?)\s+to\s+bat(?:\s+first)?",
        clean,
        re.I,
    )
    if invited:
        winner = toss_team_name(invited.group(1).strip(" .-"))
        batting_team = invited.group(2).strip(" .-")
        winner = winner or opposite_team_name(batting_team)
        return f"{winner} won toss, bowling"

    chose_field = re.search(
        r"([A-Za-z .&'-]+?)\s+won\s+the\s+toss\s+and\s+(?:decided|elected|opted|chose)\s+to\s+(?:field|bowl)\s+first",
        clean,
        re.I,
    )
    if chose_field:
        return f"{toss_team_name(chose_field.group(1).strip(' .-'))} won toss, bowling"
    return ""

def set_toss_from_text(text):
    toss = toss_from_text(text)
    if toss and not latest_score.get("toss"):
        latest_score["toss"] = toss

def recover_toss_from_commentary(max_pages=12):
    if latest_score.get("toss"):
        return latest_score["toss"]

    payload = dict(COMMENTARY_PAYLOAD)
    payload["lastDocId"] = None
    seen_pages = set()

    for _ in range(max_pages):
        page_key = str(payload.get("lastDocId"))
        if page_key in seen_pages:
            break
        seen_pages.add(page_key)

        try:
            res = requests.post(COMMENTARY_URL, json=payload, headers=HEADERS, timeout=5)
            data = res.json()
        except Exception:
            break

        events = data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []
        if not events:
            break

        for event in events:
            for key in ["c", "commentary", "comment", "desc", "description"]:
                toss = toss_from_text(event.get(key, ""))
                if toss:
                    latest_score["toss"] = toss
                    return toss

        ids = [event.get("id") for event in events if event.get("id")]
        if not ids:
            break
        payload["lastDocId"] = min(ids)

    return ""

def set_finished_match(event):
    winner_name = team_name_from_fkey(event.get("winner", ""))
    result = event.get("c", "")

    latest_score["matchResult"] = result
    latest_score["ticker"] = result or "Match finished"
    latest_score["event"] = ""
    latest_score["winChance"] = f"{winner_name} 100%" if winner_name else "100%"

def set_finished_text(text):
    result = result_from_text(text)
    if not result:
        return
    if result == "Match closed":
        result = infer_match_result() or result
    latest_score["matchResult"] = result
    latest_score["ticker"] = result
    latest_score["event"] = ""
    latest_score["winChance"] = "100%"

def set_match_closed(text="Match closed"):
    if latest_score.get("matchResult"):
        return
    text = infer_match_result() or text
    latest_score["matchResult"] = text
    latest_score["ticker"] = text
    latest_score["event"] = ""

def reset_score_line():
    latest_score["score"] = "0/0"
    latest_score["over"] = "0.0"
    latest_score["rr"] = "0.00"
    latest_score["event"] = ""

def reset_live_innings_state(reset_score=False, reset_players=True):
    global bowler_data, batsman_store, dismissed, confirmed_pair, completed_overs, players_seen

    bowler_data = {}
    batsman_store = {}
    dismissed = set()
    confirmed_pair = []
    completed_overs = []
    if reset_players:
        players_seen = {}

    latest_score["winChance"] = ""
    latest_score["lastBallRuns"] = ""
    latest_score["lastBatter"] = ""
    latest_score["lastBowler"] = ""
    latest_score["lastBallSpeed"] = ""
    latest_score["thisOver"] = []
    latest_score["recentOvers"] = []
    latest_score["batsmen"] = []
    latest_score["batsmenStats"] = []
    latest_score["squadPlayers"] = []
    latest_score["striker"] = ""
    latest_score["nonStriker"] = ""
    latest_score["bowler"] = ""
    latest_score["bowlerStats"] = {}
    latest_score["lastWicket"] = ""
    reset_partnership()
    if reset_score:
        reset_score_line()

def clear_innings_break():
    latest_score["inningsBreak"] = False
    latest_score["inningsBreakText"] = ""

def set_innings_break(event):
    target = str(event.get("target") or "").strip()
    message = strip_html(event.get("c", ""))
    event_type = event.get("type")
    tf_fkey = event.get("tf") or event.get("tfkey") or ""
    bowl_tfkey = event.get("bowl_tfkey") or event.get("bf") or ""

    if event_type == "tc":
        chasing_fkey = tf_fkey
        defending_fkey = bowl_tfkey
    else:
        chasing_fkey = bowl_tfkey
        defending_fkey = tf_fkey

    if not target.isdigit():
        target = target_from_score(latest_score.get("score", ""))
    if target and target not in message:
        message = f"{message} | Target {target}" if message else f"Target {target}"
    innings_limit_balls = event.get("inningsLimitBalls") or innings_limit_balls_from_over(latest_score.get("over", ""))

    reset_live_innings_state(reset_score=True, reset_players=True)

    latest_score["inningsBreak"] = True
    latest_score["inningsBreakText"] = message or "Innings break"
    latest_score["target"] = target
    latest_score["inningsLimitBalls"] = innings_limit_balls
    latest_score["ticker"] = message or "Innings break"
    latest_score["event"] = ""

    if chasing_fkey:
        latest_score["battingTeam"] = team_name_from_fkey(chasing_fkey) or latest_score.get("battingTeam", "")
        latest_score["battingTeamFkey"] = chasing_fkey
    if defending_fkey:
        latest_score["bowlingTeam"] = team_name_from_fkey(defending_fkey) or latest_score.get("bowlingTeam", "")
        latest_score["bowlingTeamFkey"] = defending_fkey
    refresh_live_team_images()

def recover_target_from_commentary(max_pages=8):
    should_recover_score = latest_score.get("score") in ["", "0/0"] and not latest_score.get("inningsBreak")
    should_recover_target = not plausible_target(latest_score.get("target"))
    if should_recover_target:
        latest_score["target"] = ""
    if (not should_recover_score and not should_recover_target) or str(latest_score.get("inning")) not in ["1", "2", "2nd"]:
        return ""

    payload = dict(COMMENTARY_PAYLOAD)
    payload["lastDocId"] = None
    score_context = ""
    best_target = ""
    seen_pages = set()

    for _ in range(max_pages):
        page_key = str(payload.get("lastDocId"))
        if page_key in seen_pages:
            break
        seen_pages.add(page_key)

        try:
            res = requests.post(COMMENTARY_URL, json=payload, headers=HEADERS, timeout=5)
            data = res.json()
        except Exception:
            break

        events = data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []
        if not events:
            break

        if should_recover_score:
            for event in events:
                event_score = str(event.get("s") or event.get("score") or "").strip()
                if re.match(r"^\d+/\d+", event_score):
                    latest_score["score"] = event_score
                    if event.get("o") not in [None, ""]:
                        latest_score["over"] = normalize_over_value(event.get("o"))
                    bat_team_fkey = event.get("bat_team_fkey") or event.get("tfkey") or event.get("tf") or ""
                    if bat_team_fkey:
                        set_live_teams_from_batting_fkey(bat_team_fkey)
                    if event.get("inning") is not None:
                        latest_score["inning"] = str(event.get("inning"))
                    should_recover_score = False
                    break

        for event in sorted(events, key=lambda x: x.get("id", 0)):
            event_score = str(event.get("s") or event.get("score") or "").strip()
            if re.match(r"^\d+/\d+", event_score):
                score_context = event_score

            explicit_target = str(event.get("target") or "").strip()
            if should_recover_target and explicit_target.isdigit() and plausible_target(explicit_target):
                best_target = explicit_target
                break

            need_runs, need_balls = extract_need_context(event.get("c", ""))
            if should_recover_target and need_runs:
                # At the start of a chase feeds say "needs 197 runs in 120 balls".
                # That value is already the target, not first-innings score + 197.
                if need_balls in [120, 300] and plausible_target(need_runs):
                    best_target = str(need_runs)
                    break
                if score_context:
                    runs, _ = parse_score_value(score_context)
                    possible_target = runs + need_runs
                    if plausible_target(possible_target):
                        best_target = str(possible_target)
                        break

        if best_target:
            latest_score["target"] = best_target
            should_recover_target = False

        if not should_recover_score and not should_recover_target:
            return latest_score.get("target", "")

        ids = [event.get("id") for event in events if event.get("id")]
        if not ids:
            break
        payload["lastDocId"] = min(ids)

    return ""

def clean_player_name(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(value or "").lower())).strip()

def same_player_name(left, right):
    a = clean_player_name(left)
    b = clean_player_name(right)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True

    a_parts = a.split()
    b_parts = b.split()
    if len(a_parts) >= 2 and len(b_parts) >= 2 and a_parts[-1] == b_parts[-1]:
        return a_parts[0][0] == b_parts[0][0]
    return False

def merge_batter_record(source_name, target_name):
    if not source_name or not target_name or source_name == target_name:
        return
    source = batsman_store.pop(source_name, {})
    target = batsman_store.get(target_name, {})
    if not source:
        return
    batsman_store[target_name] = {
        "runs": max(target.get("runs", 0), source.get("runs", 0)),
        "balls": max(target.get("balls", 0), source.get("balls", 0)),
        "fours": max(target.get("fours", 0), source.get("fours", 0)),
        "sixes": max(target.get("sixes", 0), source.get("sixes", 0)),
        "fkey": target.get("fkey", "") or source.get("fkey", ""),
    }

def dedupe_active_batters():
    unique = []
    for name in latest_score.get("batsmen", []):
        if not name:
            continue
        duplicate = next((existing for existing in unique if same_player_name(name, existing)), "")
        if duplicate:
            preferred = name if len(name) > len(duplicate) else duplicate
            other = duplicate if preferred == name else name
            merge_batter_record(other, preferred)
            unique = [preferred if existing == duplicate else existing for existing in unique]
        else:
            unique.append(name)
    latest_score["batsmen"] = unique[-2:]

def resolve_batter_name(name):
    dedupe_active_batters()
    for batter in latest_score.get("batsmen", []):
        if same_player_name(name, batter):
            return batter
    return str(name or "").strip()

def set_striker(name):
    striker = resolve_batter_name(name)
    if not striker and latest_score.get("batsmen"):
        striker = latest_score["batsmen"][0]

    latest_score["striker"] = striker
    latest_score["nonStriker"] = ""
    for batter in latest_score.get("batsmen", []):
        if not same_player_name(batter, striker):
            latest_score["nonStriker"] = batter
            break

def ensure_active_batter(name, fkey=""):
    name = str(name or "").strip()
    fkey = str(fkey or "").strip()
    if not name:
        return

    if any(same_player_name(name, out_name) for out_name in dismissed):
        return

    existing_name = ""
    for batter in latest_score.get("batsmen", []):
        if same_player_name(name, batter):
            existing_name = batter
            break

    display_name = existing_name or name
    if not existing_name:
        latest_score["batsmen"].append(display_name)
        dedupe_active_batters()
        display_name = resolve_batter_name(display_name)

    current = batsman_store.get(display_name, {})
    batsman_store[display_name] = {
        "runs": current.get("runs", 0),
        "balls": current.get("balls", 0),
        "fours": current.get("fours", 0),
        "sixes": current.get("sixes", 0),
        "fkey": fkey or current.get("fkey", ""),
    }

def update_batter_from_ball(name, fkey, runs_raw):
    name = resolve_batter_name(name)
    if not name:
        return

    runs_text = str(runs_raw or "").upper()
    is_extra = "WD" in runs_text or "NB" in runs_text
    is_legal_ball = not is_extra
    if not is_extra and re.fullmatch(r"\d+(?:\+\d+)*", runs_text):
        batter_runs = sum(int(part) for part in runs_text.split("+"))
    else:
        batter_runs = int(runs_text) if runs_text.isdigit() else 0

    current = batsman_store.get(name, {})
    batsman_store[name] = {
        "runs": current.get("runs", 0) + batter_runs,
        "balls": current.get("balls", 0) + (1 if is_legal_ball else 0),
        "fours": current.get("fours", 0) + (1 if runs_text == "4" else 0),
        "sixes": current.get("sixes", 0) + (1 if runs_text == "6" else 0),
        "fkey": fkey or current.get("fkey", ""),
    }

def build_batsmen_stats():
    dedupe_active_batters()
    stats = []
    seen = []
    striker = latest_score.get("striker", "")
    non_striker = latest_score.get("nonStriker", "")
    for name in latest_score["batsmen"]:
        if any(same_player_name(name, existing) for existing in seen):
            continue
        seen.append(name)
        d = batsman_store.get(name, {})
        r, b = d.get("runs",0), d.get("balls",0)
        fkey = d.get("fkey", "")
        image_url = player_override(fkey, name) or pimg(fkey)
        stats.append({
            "name": name, "runs": r, "balls": b,
            "sr": sr(r,b), "fours": d.get("fours",0),
            "sixes": d.get("sixes",0),
            "fkey": fkey,
            "img": image_url,
            "imgCandidates": player_img_candidates(fkey, image_url, name),
            "isStriker": same_player_name(name, striker),
            "isNonStriker": same_player_name(name, non_striker),
        })
    latest_score["batsmenStats"] = stats[:2]

def update_partnership_fallback():
    if latest_score.get("partnership"):
        return

    active = latest_score.get("batsmenStats") or []
    if not active:
        latest_score["partnership"] = "0(0)"
        return

    runs = sum(int(player.get("runs") or 0) for player in active)
    balls = sum(int(player.get("balls") or 0) for player in active)
    latest_score["partnership"] = f"{runs}({balls})"

def set_partnership_text():
    latest_score["partnership"] = f"{partnership_runs}({partnership_balls})"

def reset_partnership():
    global partnership_runs, partnership_balls
    partnership_runs = 0
    partnership_balls = 0
    set_partnership_text()

def update_partnership_from_ball(runs_raw):
    global partnership_runs, partnership_balls

    runs_text = str(runs_raw or "").upper()
    if runs_text == "W":
        reset_partnership()
        return

    partnership_runs += ball_runs(runs_text)
    if is_legal_delivery(runs_text):
        partnership_balls += 1
    set_partnership_text()

def build_bowler_stats(name):
    if not name or name not in bowler_data: return
    bd = bowler_data[name]
    tb = bd["balls"]
    fkey = bd.get("fkey", "")
    image_url = player_override(fkey, name) or pimg(fkey)
    latest_score["bowlerStats"] = {
        "name": name, "overs": ovs(tb),
        "runs": bd["runs"], "wickets": bd["wickets"],
        "economy": eco(bd["runs"], tb),
        "wides": bd["wides"], "noballs": bd["noballs"],
        "fkey": fkey,
        "img": image_url,
        "imgCandidates": player_img_candidates(fkey, image_url, name)
    }
    # Also update the bowler display name to the full name
    latest_score["bowler"] = name

# ── meta ───────────────────────────────────────────────────────────
def fetch_match_meta():
    global meta_loaded
    if meta_loaded: return
    try:
        res  = requests.post(META_URL, json=META_PAYLOAD, headers=HEADERS, timeout=5)
        data = res.json()
        print("META RAW:", data)

        meta = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}

        team1 = meta.get("team1") or meta.get("t1") or meta.get("homeTeam") or ""
        team2 = meta.get("team2") or meta.get("t2") or meta.get("awayTeam") or ""
        venue = meta.get("v") or meta.get("venue") or meta.get("ground") or ""
        mt    = meta.get("t") or meta.get("matchTime") or meta.get("startTime") or ""

        # Toss — deep scan every key and nested level
        toss = ""
        def find_toss(obj, depth=0):
            if depth > 3: return ""
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if "toss" in k.lower():
                        return str(v)
                    result = find_toss(v, depth+1)
                    if result: return result
            elif isinstance(obj, list):
                for item in obj:
                    result = find_toss(item, depth+1)
                    if result: return result
            return ""
        toss_raw = find_toss(meta)
        toss = toss_from_text(toss_raw) or toss_raw
        if not toss:
            toss = toss_from_text(json.dumps(meta, ensure_ascii=False))
        win_chance = extract_win_chance(meta)
        match_result = extract_match_result(meta)

        t1fkey = meta.get("team1Fkey") or meta.get("team1_fkey") or meta.get("t1f") or meta.get("tf1") or ""
        t2fkey = meta.get("team2Fkey") or meta.get("team2_fkey") or meta.get("t2f") or meta.get("tf2") or ""

        if team1: latest_score["team1"] = team1
        if team2: latest_score["team2"] = team2
        if team1 and team2: latest_score["team"] = f"{team1} vs {team2}"
        latest_score["venue"]     = venue
        latest_score["matchTime"] = mt
        if toss: latest_score["toss"] = toss
        if win_chance: latest_score["winChance"] = win_chance
        if match_result: set_finished_text(match_result)
        if t1fkey:
            latest_score["team1Fkey"] = t1fkey
        if t2fkey:
            latest_score["team2Fkey"] = t2fkey
        if team1 and not latest_score.get("battingTeam"):
            latest_score["battingTeam"] = team1
            latest_score["battingTeamFkey"] = t1fkey
        if team2 and not latest_score.get("bowlingTeam"):
            latest_score["bowlingTeam"] = team2
            latest_score["bowlingTeamFkey"] = t2fkey
        if str(meta.get("s", "")).strip() == "2":
            set_match_closed()
        refresh_team_images()

        if team1 and team2: meta_loaded = True
        else: print("Meta teams not found. Keys:", list(meta.keys()))
    except Exception as e:
        print("Meta error:", e)

# ── event processor ────────────────────────────────────────────────
def process_events(events):
    global latest_id, confirmed_pair, current_inning

    for event in sorted(events, key=lambda x: x.get("id", 0)):
        eid = event.get("id", 0)
        if eid <= latest_id: continue
        latest_id = eid
        etype = event.get("type")
        incoming_inning = event.get("inning")
        if incoming_inning is not None:
            if current_inning is not None and incoming_inning != current_inning and etype in ["b", "ps"]:
                reset_live_innings_state(reset_score=True)
            current_inning = incoming_inning
            latest_score["inning"] = str(incoming_inning)
        api_win_chance = extract_win_chance(event)
        if api_win_chance:
            latest_score["winChance"] = api_win_chance
        api_match_result = extract_match_result(event)
        if api_match_result:
            set_finished_text(api_match_result)
        set_toss_from_text(event.get("c", ""))

        # Collect team fkeys from any event
        for fk in [event.get("bat_team_fkey"), event.get("tfkey"), event.get("tf")]:
            if fk and fk not in team_img_map:
                team_img_map[fk] = TEAM_IMG_BASE.format(fkey=fk)
        bfk = event.get("bf","")
        if bfk and bfk not in team_img_map:
            team_img_map[bfk] = TEAM_IMG_BASE.format(fkey=bfk)

        # ── type:"b" individual ball ────────────────────────────
        if etype == "b":
            incoming_inning = event.get("inning")
            if incoming_inning is not None:
                if current_inning is not None and incoming_inning != current_inning:
                    reset_live_innings_state(reset_score=True)
                current_inning = incoming_inning
                latest_score["inning"] = str(incoming_inning)
            if latest_score.get("inningsBreak"):
                reset_live_innings_state(reset_score=True)
                clear_innings_break()

            runs_raw  = normalize_ball(event.get("b", "0"))
            c1        = event.get("c1", "")
            score_str = str(event.get("s", ""))
            over_str  = over_after_delivery(event.get("o", ""), runs_raw, latest_score.get("over", ""))
            bowler_fkey = event.get("bf", "")
            bat_team_fkey = event.get("bat_team_fkey") or event.get("tfkey") or event.get("tf") or ""
            ball_speed = extract_ball_speed(event)

            if score_str: latest_score["score"] = score_str
            if over_str:  latest_score["over"]  = over_str
            if bat_team_fkey: set_live_teams_from_batting_fkey(bat_team_fkey)
            latest_score["lastBallRuns"] = runs_raw
            latest_score["lastBallSpeed"] = ball_speed
            update_partnership_from_ball(runs_raw)

            bowl_short, bat_short = "", ""
            if " to " in c1:
                parts      = c1.split(" to ", 1)
                bowl_short = parts[0].strip()
                bat_short  = parts[1].strip()
                latest_score["lastBatter"] = bat_short
                latest_score["lastBowler"] = bowl_short

            if bowl_short:
                latest_score["bowler"] = bowl_short
                remember_player(bowl_short, bowler_fkey, "BOWL")
            if bat_short:
                remember_player(bat_short, event.get("pf", ""), "BAT")
                ensure_active_batter(bat_short, event.get("pf", ""))
                update_batter_from_ball(bat_short, event.get("pf", ""), runs_raw)
                set_striker(bat_short)
                build_batsmen_stats()

            latest_score["thisOver"].append(runs_raw)
            latest_score["thisOver"] = latest_score["thisOver"][-12:]
            build_recent_overs(current_over_label(over_str))

            if bowl_short:
                current_balls = latest_score["thisOver"]
                legal_balls = sum(1 for b in current_balls if str(b).upper() not in ["WD", "NB"])
                latest_score["bowlerStats"] = {
                    "name": bowl_short,
                    "overs": ovs(legal_balls),
                    "runs": sum(ball_runs(b) for b in current_balls),
                    "wickets": sum(1 for b in current_balls if str(b).upper() == "W"),
                    "economy": eco(sum(ball_runs(b) for b in current_balls), legal_balls),
                    "wides": sum(1 for b in current_balls if str(b).upper() == "WD"),
                    "noballs": sum(1 for b in current_balls if str(b).upper() == "NB"),
                    "fkey": bowler_fkey,
                    "img": player_override(bowler_fkey, bowl_short) or pimg(bowler_fkey),
                    "imgCandidates": player_img_candidates(
                        bowler_fkey,
                        player_override(bowler_fkey, bowl_short) or pimg(bowler_fkey),
                        bowl_short
                    )
                }

            ev = ""
            if runs_raw == "W":           ev = "WICKET"
            elif runs_raw in ["4","4b"]:  ev = "FOUR"
            elif runs_raw in ["6","6b"]:  ev = "SIX"
            elif runs_raw == "WD":        ev = "WIDE"
            elif runs_raw == "NB":        ev = "NOBALL"

            latest_score["event"]  = ev
            latest_score["ticker"] = ticker_msg(ev, bat_short, bowl_short, runs_raw)

            if str(current_inning) in ["2", "2nd"] and latest_score.get("target") and first_innings_complete(latest_score["score"], latest_score["over"]):
                result = infer_match_result()
                if result:
                    set_match_closed(result)
            elif str(current_inning) in ["0", "1", "1st"] and first_innings_complete(latest_score["score"], latest_score["over"]):
                set_innings_break({
                    "c": f"{latest_score.get('bowlingTeam') or 'Chasing team'} needs {target_from_score(latest_score['score'])} after first innings",
                    "target": target_from_score(latest_score["score"]),
                    "inningsLimitBalls": innings_limit_balls_from_over(latest_score["over"]),
                    "tf": latest_score.get("battingTeamFkey", ""),
                    "bowl_tfkey": latest_score.get("bowlingTeamFkey", ""),
                })

        elif etype == "wc":
            set_finished_match(event)

        elif etype in ["ic2", "tc"]:
            set_innings_break(event)

        elif etype == "pm":
            remember_player(event.get("n", ""), event.get("pf", ""), "BAT", event.get("url", ""))

        elif etype == "ps":
            incoming_inning = event.get("inning")
            if incoming_inning is not None:
                if current_inning is not None and incoming_inning != current_inning:
                    reset_live_innings_state(reset_score=True)
                current_inning = incoming_inning
                latest_score["inning"] = str(incoming_inning)
                clear_innings_break()

            name = event.get("n", "")
            fkey = event.get("pf", "")
            team_fkey = event.get("tf", "")
            is_batter = str(event.get("cat", "")) == "1"
            remember_team_squad_player(team_fkey, name, fkey, "BAT" if is_batter else "BOWL", event.get("url", ""))

            if is_batter and team_fkey == latest_score.get("battingTeamFkey"):
                remember_player(name, fkey, "BAT", event.get("url", ""))
                ensure_active_batter(name, fkey)
                if not latest_score.get("striker"):
                    set_striker(name)
                build_batsmen_stats()

        elif etype == "t":
            set_toss_from_text(event.get("c", ""))
            set_finished_text(event.get("c", ""))

        # ── type:"w" wicket card ────────────────────────────────
        elif etype == "w":
            # Field names from your actual data:
            # player_fullname, player, wicketDesc, r, b, sr, url, pf
            full_name   = event.get("player_fullname") or event.get("player", "")
            short_name  = event.get("player", "")
            wdesc       = event.get("wicketDesc", "")
            r_out       = event.get("r", 0)
            b_out       = event.get("b", 0)
            sr_out      = event.get("sr", "0.00")
            img_url     = event.get("url", "")   # ← direct image URL
            pf          = event.get("pf", "")    # ← fkey is "pf" not "player_fkey"

            print(f"WICKET event: full={full_name} short={short_name} pf={pf} img={img_url}")

            # Save image
            if pf and img_url:
                player_img_map[pf] = img_url
            remember_player(full_name or short_name, pf, "BAT", img_url)

            # Save accurate stats at dismissal
            if full_name:
                existing = batsman_store.get(full_name, {})
                batsman_store[full_name] = {
                    "runs":  r_out,
                    "balls": b_out,
                    "fours": existing.get("fours", 0),
                    "sixes": existing.get("sixes", 0),
                    "fkey":  pf,
                }
                dismissed.add(full_name)
                if short_name: dismissed.add(short_name)

            # Set lastWicket — always update even if wdesc is empty
            display_name = full_name or short_name or "Unknown"
            latest_score["lastWicket"] = f"{display_name} {wdesc} - {r_out}({b_out})"
            print(f"lastWicket set to: {latest_score['lastWicket']}")
            if re.search(r"run\s*out|runout", wdesc, re.I):
                latest_score["event"] = "RUNOUT"
                latest_score["ticker"] = f"RUN OUT! {display_name} is short of the crease!"

            # Remove from pair and batsmen list
            def is_out(n):
                if not n: return False
                return (n in dismissed or n == short_name or n == full_name or
                        (full_name and n.lower() in full_name.lower()) or
                        (full_name and full_name.lower() in n.lower()) or
                        (short_name and n.lower() in short_name.lower()))

            confirmed_pair           = [n for n in confirmed_pair if not is_out(n)]
            latest_score["batsmen"]  = [n for n in latest_score["batsmen"] if not is_out(n)]
            build_batsmen_stats()
            reset_partnership()

        # ── type:"o" over summary ───────────────────────────────
        elif etype == "o":
            bowler_full = event.get("bowler", "")
            p1_name     = event.get("p1", "")
            p2_name     = event.get("p2", "")
            s1_str      = event.get("s1", "")
            s2_str      = event.get("s2", "")
            pf1         = event.get("pf1", "")
            pf2         = event.get("pf2", "")
            over_runs   = event.get("runs", 0)
            rb_str      = event.get("rb", "")
            bd_str      = event.get("bd", "")
            bat_fkey    = event.get("tfkey","") or event.get("tf","")
            bowl_fkey   = event.get("bf","")
            striker_name = event.get("striker") or event.get("st") or event.get("onStrike") or event.get("on_strike") or ""

            if rb_str:
                balls = [normalize_ball(ball) for ball in rb_str.split(".") if ball]
                over_no = event.get("o", "")
                completed_overs.append({
                    "label": f"OVER {over_no}",
                    "balls": balls,
                    "total": over_total(balls),
                    "current": False,
                })
                del completed_overs[:-3]

            # Team images from over summary
            if bat_fkey:
                team_img_map[bat_fkey] = TEAM_IMG_BASE.format(fkey=bat_fkey)
                if not latest_score["team1Img"]:
                    latest_score["team1Img"] = TEAM_IMG_BASE.format(fkey=bat_fkey)
                set_live_teams_from_batting_fkey(bat_fkey)
            if bowl_fkey:
                team_img_map[bowl_fkey] = TEAM_IMG_BASE.format(fkey=bowl_fkey)
                if not latest_score["team2Img"]:
                    latest_score["team2Img"] = TEAM_IMG_BASE.format(fkey=bowl_fkey)
            refresh_team_images()

            # Bowler
            if bowler_full:
                remember_player(bowler_full, bowl_fkey, "BOWL")
                parsed_figures = parse_bowler_figures(bd_str)
                if parsed_figures:
                    runs, wickets, balls = parsed_figures
                else:
                    runs = over_runs
                    wickets = rb_str.split(".").count("W") if rb_str else 0
                    balls = sum(1 for ball in rb_str.split(".") if ball.upper() not in ["WD", "NB"]) if rb_str else 6

                bowler_data[bowler_full] = {
                    "balls": balls, "runs": runs,
                    "wickets": wickets, "wides": 0, "noballs": 0,
                    "fkey": bowl_fkey,
                }
                bd = bowler_data[bowler_full]
                if rb_str:
                    for ball in rb_str.split("."):
                        ball = ball.upper()
                        if ball == "WD": bd["wides"]   += 1
                        elif ball == "NB": bd["noballs"] += 1
                build_bowler_stats(bowler_full)

            # Batsmen — only non-dismissed
            r1, b1 = parse_sc(s1_str)
            r2, b2 = parse_sc(s2_str)

            for name, fkey, r, b in [
                (p1_name, pf1, r1, b1),
                (p2_name, pf2, r2, b2),
            ]:
                remember_player(name, fkey, "BAT")
                if not name or any(same_player_name(name, out_name) for out_name in dismissed): continue
                existing_name = resolve_batter_name(name)
                display_name = existing_name if existing_name else name
                existing = batsman_store.get(display_name, {})
                batsman_store[display_name] = {
                    "runs": r, "balls": b,
                    "fours": existing.get("fours", 0),
                    "sixes": existing.get("sixes", 0),
                    "fkey": fkey,
                }

            # confirmed pair = non-dismissed only
            confirmed_pair = []
            for name in [p1_name, p2_name]:
                if not name or any(same_player_name(name, out_name) for out_name in dismissed):
                    continue
                resolved = resolve_batter_name(name) or name
                if not any(same_player_name(resolved, existing) for existing in confirmed_pair):
                    confirmed_pair.append(resolved)
            latest_score["batsmen"] = list(confirmed_pair)
            dedupe_active_batters()
            if striker_name:
                set_striker(striker_name)
            elif confirmed_pair:
                legal_balls = sum(1 for ball in rb_str.split(".") if ball and ball.upper() not in ["WD", "NB"]) if rb_str else 0
                set_striker(confirmed_pair[legal_balls % 2])
            build_batsmen_stats()

            # Reset thisOver for new over
            latest_score["thisOver"] = []
            build_recent_overs()

# ── routes ─────────────────────────────────────────────────────────
@app.route("/score")
def score():
    try:
        fetch_match_meta()
        res  = requests.post(COMMENTARY_URL, json=COMMENTARY_PAYLOAD, headers=HEADERS, timeout=5)
        data = res.json()

        events = []
        if isinstance(data, dict):
            events = data.get("data") or data.get("events") or data.get("ballCommentary") or data.get("commentary") or []
            match_result = extract_match_result(data)
            if match_result:
                set_finished_text(match_result)
        elif isinstance(data, list):
            events = data
            match_result = extract_match_result(data)
            if match_result:
                set_finished_text(match_result)

        if not events:
            latest_score["ticker"] = "Match starting soon..."
            return jsonify(latest_score)

        process_events(events)
        recover_toss_from_commentary()
        recover_target_from_commentary()
        update_partnership_fallback()
        recover_team_squads_from_commentary()
        build_squad_players()
        build_team_squads()
        refresh_team_images()

        try:
            rt = int(latest_score["score"].split("/")[0])
            ov = float(latest_score["over"])
            latest_score["rr"] = str(round(rt/ov, 2)) if ov > 0 else "0.00"
        except: latest_score["rr"] = "0.00"

        if not latest_score.get("matchResult") and latest_score.get("winChance") in ["", "--"]:
            latest_score["winChance"] = calculate_live_win_chance()

        if latest_score.get("matchResult") == "Match closed":
            inferred_result = infer_match_result()
            if inferred_result:
                latest_score["matchResult"] = inferred_result
                latest_score["ticker"] = inferred_result

        return jsonify(latest_score)
    except Exception as e:
        print("Score error:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/debug")
def debug():
    try:
        meta_res = requests.post(META_URL, json=META_PAYLOAD, headers=HEADERS, timeout=5)
        comm_res = requests.post(COMMENTARY_URL, json=COMMENTARY_PAYLOAD, headers=HEADERS, timeout=5)
        meta_data = meta_res.json()
        comm_data = comm_res.json()

        meta_keys = list(meta_data[0].keys()) if isinstance(meta_data, list) and meta_data \
                    else list(meta_data.keys()) if isinstance(meta_data, dict) else []

        raw = comm_data if isinstance(comm_data, list) else comm_data.get("data",[])
        type_counts, samples = {}, {}
        for e in raw:
            t = e.get("type","?")
            type_counts[t] = type_counts.get(t,0) + 1
            if t not in samples: samples[t] = e

        return jsonify({
            "meta_status": meta_res.status_code, "meta_keys": meta_keys,
            "meta_raw": meta_data,
            "commentary_status": comm_res.status_code,
            "event_type_counts": type_counts, "sample_by_type": samples,
            "player_img_map": player_img_map, "team_img_map": team_img_map,
            "player_image_overrides": player_image_overrides,
            "team_image_overrides": team_image_overrides,
            "dismissed": list(dismissed), "lastWicket": latest_score["lastWicket"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/player-placeholder/<path:name>.svg")
def player_placeholder(name):
    clean_name = re.sub(r"\.svg$", "", str(name or "Player"), flags=re.I)
    clean_name = re.sub(r"[_-]+", " ", clean_name).strip() or "Player"
    clean_name = re.sub(r"[^A-Za-z0-9 .'-]", "", clean_name).strip() or "Player"
    initials = "".join(part[0] for part in clean_name.split()[:2]).upper() or "P"

    seed = sum(ord(ch) for ch in clean_name)
    palette = [
        ("#12343b", "#2d8f85", "#f6f4d2"),
        ("#1d1f33", "#ffb703", "#ffffff"),
        ("#22223b", "#4a9dff", "#f8f9fa"),
        ("#102a43", "#38bdf8", "#ffffff"),
    ]
    bg, accent, text = palette[seed % len(palette)]
    safe_name = (
        clean_name.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320">
  <rect width="320" height="320" fill="{bg}"/>
  <circle cx="160" cy="122" r="68" fill="{accent}" opacity="0.95"/>
  <path d="M48 292c13-66 58-102 112-102s99 36 112 102" fill="{accent}" opacity="0.9"/>
  <text x="160" y="144" text-anchor="middle" font-family="Arial, sans-serif" font-size="64" font-weight="800" fill="{text}">{initials}</text>
  <text x="160" y="286" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="{text}">{safe_name}</text>
</svg>"""
    return Response(svg, mimetype="image/svg+xml")

@app.route("/player-image", methods=["GET", "POST"])
def player_image():
    if request.method == "GET":
        return jsonify({"overrides": player_image_overrides})

    body = request.get_json(silent=True) or {}
    player = str(body.get("player") or body.get("name") or body.get("fkey") or "").strip()
    url = str(body.get("url") or "").strip()

    if not player:
        return jsonify({"error": "Player name or fkey is required"}), 400
    if not valid_image_url(url):
        return jsonify({"error": "Image URL must start with http:// or https://"}), 400

    player_lower = player.lower()
    matched_keys = []

    for seen_key, seen in players_seen.items():
        if seen_key == player_lower or seen.get("fkey") == player or seen.get("name", "").lower() == player_lower:
            matched_keys.append(seen_key)

    if matched_keys:
        for seen_key in matched_keys:
            seen = players_seen[seen_key]
            fkey = seen.get("fkey", "")
            if fkey:
                player_image_overrides[fkey] = url
                player_img_map[fkey] = url
            player_image_overrides[seen.get("name", "").lower()] = url
            seen["img"] = url
            seen["imgCandidates"] = player_img_candidates(fkey, url, seen.get("name", ""))
    elif " " in player:
        player_image_overrides[player_lower] = url
    else:
        player_image_overrides[player] = url
        player_img_map[player] = url

    build_batsmen_stats()
    if latest_score.get("bowlerStats", {}).get("name"):
        build_bowler_stats(latest_score["bowlerStats"]["name"])
    build_squad_players()

    return jsonify({
        "status": "saved",
        "player": player,
        "url": url,
        "matched": len(matched_keys),
    })

@app.route("/team-image", methods=["GET", "POST"])
def team_image():
    if request.method == "GET":
        return jsonify({"overrides": team_image_overrides})

    body = request.get_json(silent=True) or {}
    team = str(body.get("team") or body.get("name") or body.get("fkey") or "").strip()
    url = str(body.get("url") or "").strip()

    if not team:
        return jsonify({"error": "Team name or fkey is required"}), 400
    if not valid_image_url(url):
        return jsonify({"error": "Image URL must start with http:// or https://"}), 400

    team_lower = team.lower()
    matched = 0

    for side in ["team1", "team2"]:
        name = latest_score.get(side, "")
        fkey = latest_score.get(f"{side}Fkey", "")
        if team_lower == str(name).lower() or team == fkey:
            matched += 1
            if name:
                team_image_overrides[str(name).lower()] = url
            if fkey:
                team_image_overrides[fkey] = url
                team_img_map[fkey] = url
            latest_score[f"{side}Img"] = url
            latest_score[f"{side}ImgCandidates"] = team_img_candidates(fkey, url)

    if not matched:
        if " " in team:
            team_image_overrides[team_lower] = url
        else:
            team_image_overrides[team] = url
            team_img_map[team] = url

    refresh_team_images()

    return jsonify({
        "status": "saved",
        "team": team,
        "url": url,
        "matched": matched,
    })

@app.route("/reset")
def reset():
    global latest_id, meta_loaded, current_inning, bowler_data, batsman_store
    global dismissed, confirmed_pair, player_img_map, team_img_map, completed_overs, players_seen, team_squads
    global player_image_overrides, team_image_overrides
    global player_web_image_cache, partnership_runs, partnership_balls

    latest_id = 0; meta_loaded = False; current_inning = None
    bowler_data = {}; batsman_store = {}
    dismissed = set(); confirmed_pair = []
    player_img_map = {}; team_img_map = {}
    completed_overs = []
    players_seen = {}
    team_squads = {}
    player_image_overrides = {}
    team_image_overrides = {}
    player_web_image_cache = {}
    partnership_runs = 0
    partnership_balls = 0

    for k in list(latest_score.keys()):
        if isinstance(latest_score[k], list): latest_score[k] = []
        elif isinstance(latest_score[k], dict): latest_score[k] = {}
        else: latest_score[k] = ""
    latest_score.update({
        "score":"0/0","over":"0.0","rr":"0.00",
        "inningsBreak": False, "inningsBreakText": "", "target": "", "inningsLimitBalls": "", "inning": "",
        "partnership": "0(0)",
        "team1Squad": [], "team2Squad": [],
    })
    return jsonify({"status":"reset done"})

@app.route("/audio-config")
def audio_config():
    return jsonify({
        "backgroundMusicUrl": BACKGROUND_MUSIC_URL,
        "backgroundVolume": 0.18,
        "crowdMusicUrl": CROWD_MUSIC_URL,
        "crowdVolume": 0.28,
        "hindiCommentaryStreamUrl": HINDI_COMMENTARY_STREAM_URL,
        "hindiCommentaryVolume": 0.9,
    })

if __name__ == "__main__":
    app.run(debug=True, port=5001)
