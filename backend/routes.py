from flask import Response, jsonify, request, send_from_directory
import os
import re
import requests

import score_app as core


def register_routes(app):
    @app.route("/")
    def dashboard():
        return send_from_directory(core.FRONTEND_DIR, "index.html")

    @app.route("/<path:filename>")
    def frontend_asset(filename):
        if os.path.isfile(os.path.join(core.FRONTEND_DIR, filename)):
            return send_from_directory(core.FRONTEND_DIR, filename)
        return jsonify({"error": "Not found"}), 404

    @app.route("/score")
    def score():
        try:
            core.fetch_match_meta()
            res  = requests.post(core.COMMENTARY_URL, json=core.COMMENTARY_PAYLOAD, headers=core.HEADERS, timeout=5)
            data = res.json()

            events = []
            if isinstance(data, dict):
                events = data.get("data") or data.get("events") or data.get("ballCommentary") or data.get("commentary") or []
                match_result = core.extract_match_result(data)
                if match_result:
                    core.set_finished_text(match_result)
            elif isinstance(data, list):
                events = data
                match_result = core.extract_match_result(data)
                if match_result:
                    core.set_finished_text(match_result)

            if not events:
                core.latest_score["ticker"] = "Match starting soon..."
                return jsonify(core.latest_score)

            core.process_events(events)
            core.recover_toss_from_commentary()
            core.recover_target_from_commentary()
            core.update_partnership_fallback()
            core.recover_team_squads_from_commentary()
            core.build_squad_players()
            core.build_team_squads()
            core.refresh_team_images()

            try:
                rt = int(core.latest_score["score"].split("/")[0])
                ov = float(core.latest_score["over"])
                core.latest_score["rr"] = str(round(rt/ov, 2)) if ov > 0 else "0.00"
            except: core.latest_score["rr"] = "0.00"

            if not core.latest_score.get("matchResult") and core.latest_score.get("winChance") in ["", "--"]:
                core.latest_score["winChance"] = core.calculate_live_win_chance()

            if core.latest_score.get("matchResult") == "Match closed":
                inferred_result = core.infer_match_result()
                if inferred_result:
                    core.latest_score["matchResult"] = inferred_result
                    core.latest_score["ticker"] = inferred_result

            return jsonify(core.latest_score)
        except Exception as e:
            print("Score error:", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/debug")
    def debug():
        try:
            meta_res = requests.post(core.META_URL, json=core.META_PAYLOAD, headers=core.HEADERS, timeout=5)
            comm_res = requests.post(core.COMMENTARY_URL, json=core.COMMENTARY_PAYLOAD, headers=core.HEADERS, timeout=5)
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
                "player_img_map": core.player_img_map, "team_img_map": core.team_img_map,
                "player_image_overrides": core.player_image_overrides,
                "team_image_overrides": core.team_image_overrides,
                "dismissed": list(core.dismissed), "lastWicket": core.latest_score["lastWicket"],
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
            return jsonify({"overrides": core.player_image_overrides})

        body = request.get_json(silent=True) or {}
        player = str(body.get("player") or body.get("name") or body.get("fkey") or "").strip()
        url = str(body.get("url") or "").strip()

        if not player:
            return jsonify({"error": "Player name or fkey is required"}), 400
        if not core.valid_image_url(url):
            return jsonify({"error": "Image URL must start with http:// or https://"}), 400

        player_lower = player.lower()
        matched_keys = []

        for seen_key, seen in core.players_seen.items():
            if seen_key == player_lower or seen.get("fkey") == player or seen.get("name", "").lower() == player_lower:
                matched_keys.append(seen_key)

        if matched_keys:
            for seen_key in matched_keys:
                seen = core.players_seen[seen_key]
                fkey = seen.get("fkey", "")
                if fkey:
                    core.player_image_overrides[fkey] = url
                    core.player_img_map[fkey] = url
                core.player_image_overrides[seen.get("name", "").lower()] = url
                seen["img"] = url
                seen["imgCandidates"] = core.player_img_candidates(fkey, url, seen.get("name", ""))
        elif " " in player:
            core.player_image_overrides[player_lower] = url
        else:
            core.player_image_overrides[player] = url
            core.player_img_map[player] = url

        core.build_batsmen_stats()
        if core.latest_score.get("bowlerStats", {}).get("name"):
            core.build_bowler_stats(core.latest_score["bowlerStats"]["name"])
        core.build_squad_players()

        return jsonify({
            "status": "saved",
            "player": player,
            "url": url,
            "matched": len(matched_keys),
        })

    @app.route("/team-image", methods=["GET", "POST"])
    def team_image():
        if request.method == "GET":
            return jsonify({"overrides": core.team_image_overrides})

        body = request.get_json(silent=True) or {}
        team = str(body.get("team") or body.get("name") or body.get("fkey") or "").strip()
        url = str(body.get("url") or "").strip()

        if not team:
            return jsonify({"error": "Team name or fkey is required"}), 400
        if not core.valid_image_url(url):
            return jsonify({"error": "Image URL must start with http:// or https://"}), 400

        team_lower = team.lower()
        matched = 0

        for side in ["team1", "team2"]:
            name = core.latest_score.get(side, "")
            fkey = core.latest_score.get(f"{side}Fkey", "")
            if team_lower == str(name).lower() or team == fkey:
                matched += 1
                if name:
                    core.team_image_overrides[str(name).lower()] = url
                if fkey:
                    core.team_image_overrides[fkey] = url
                    core.team_img_map[fkey] = url
                core.latest_score[f"{side}Img"] = url
                core.latest_score[f"{side}ImgCandidates"] = core.team_img_candidates(fkey, url)

        if not matched:
            if " " in team:
                core.team_image_overrides[team_lower] = url
            else:
                core.team_image_overrides[team] = url
                core.team_img_map[team] = url

        core.refresh_team_images()

        return jsonify({
            "status": "saved",
            "team": team,
            "url": url,
            "matched": matched,
        })

    @app.route("/reset")
    def reset():
        core.latest_id = 0; core.meta_loaded = False; core.current_inning = None
        core.bowler_data = {}; core.batsman_store = {}
        core.dismissed = set(); core.confirmed_pair = []
        core.player_img_map = {}; core.team_img_map = {}
        core.completed_overs = []
        core.players_seen = {}
        core.team_squads = {}
        core.player_image_overrides = {}
        core.team_image_overrides = {}
        core.player_web_image_cache = {}
        core.partnership_runs = 0
        core.partnership_balls = 0

        for k in list(core.latest_score.keys()):
            if isinstance(core.latest_score[k], list): core.latest_score[k] = []
            elif isinstance(core.latest_score[k], dict): core.latest_score[k] = {}
            else: core.latest_score[k] = ""
        core.latest_score.update({
            "score":"0/0","over":"0.0","rr":"0.00",
            "inningsBreak": False, "inningsBreakText": "", "target": "", "inningsLimitBalls": "", "inning": "",
            "partnership": "0(0)",
            "team1Squad": [], "team2Squad": [],
        })
        return jsonify({"status":"reset done"})

    @app.route("/audio-config")
    def audio_config():
        return jsonify({
            "backgroundMusicUrl": core.BACKGROUND_MUSIC_URL,
            "backgroundVolume": 0.18,
            "crowdMusicUrl": core.CROWD_MUSIC_URL,
            "crowdVolume": 0.78,
            "hindiCommentaryStreamUrl": core.HINDI_COMMENTARY_STREAM_URL,
            "hindiCommentaryVolume": 0.9,
        })
