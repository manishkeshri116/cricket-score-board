import os
import sys
import threading
import webbrowser


def app_root():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.abspath(os.path.dirname(__file__))


def read_match_key():
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()

    print("Cricket Scoreboard Dashboard")
    print("---------------------------")
    match_key = input("Enter match key (example: 119F): ").strip()
    return match_key or "119F"


def main():
    root = app_root()
    backend_dir = os.path.join(root, "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    match_key = read_match_key()
    os.environ["MATCH_KEY"] = match_key

    from score_app import app

    url = "http://127.0.0.1:5001/"
    print("")
    print(f"Starting dashboard for match key: {match_key}")
    print(f"Open dashboard: {url}")
    print("Keep this terminal open. Press Ctrl+C to stop.")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
