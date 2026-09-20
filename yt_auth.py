#!/usr/bin/env python3
"""
YouTube ek-time setup — APNE PC pe chalao (Render pe nahi).

  pip install requests
  python3 yt_auth.py

Isse milega: YOUTUBE_REFRESH_TOKEN + YT_CHANNEL_ID → Render env me daalna.
OAuth Client ID/Secret Google Cloud Console se aata hai (SM-SETUP.md padho).
"""
import http.server
import secrets
import threading
import time
import urllib.parse
import webbrowser

import requests

API_BASE = "https://www.googleapis.com/youtube/v3"
REDIRECT = "http://localhost:8765/callback"
result = {}
httpd = None


def stop():
    try:
        httpd.shutdown()
    except Exception:
        pass


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.urlparse(self.path).query
        d = dict(urllib.parse.parse_qsl(q))
        if "code" in d:
            result["code"] = d["code"]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Token mil gaya! Is tab ko band kar sakte ho.")
            threading.Thread(target=stop, daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


def main():
    client_id = input("1) OAuth Client ID: ").strip()
    client_secret = input("2) OAuth Client Secret: ").strip()

    state = secrets.token_urlsafe(10)
    auth = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/youtube.force-ssl",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    print("\n--- Neeche wala link browser me kholo (Google login + consent do) ---\n")
    print(auth)
    print("\n------------------------------------------------------------------\n")
    try:
        webbrowser.open(auth)
    except Exception:
        pass

    global httpd
    httpd = http.server.HTTPServer(("127.0.0.1", 8765), Handler)
    print("Waiting for callback (http://localhost:8765) ...")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    for _ in range(300):
        if "code" in result:
            break
        time.sleep(1)

    if "code" in result:
        code = result["code"]
    else:
        print("\nTimeout. Agar page khula tha toh yahan code paste karo (url me ?code=... wala hissa):")
        code = input("code: ").strip()
    if not code:
        print("Code nahi mila — dobara try karo.")
        return

    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT,
        },
        timeout=30,
    ).json()
    if "refresh_token" not in r:
        print("ERROR (refresh_token nahi mila):", r)
        print("Note: same Google account se pehle consent diya hai toh refresh_token nahi deta.")
        print("Fix: consent revoke karo → https://myaccount.google.com/permissions (Xavier app dhundo)")
        return

    ch = requests.get(
        f"{API_BASE}/channels",
        params={"part": "snippet", "mine": "true"},
        headers={"Authorization": f"Bearer {r['access_token']}"},
        timeout=30,
    ).json()
    items = ch.get("items") or [{}]
    cid = items[0].get("id")
    name = items[0].get("snippet", {}).get("title", "?")

    print("\n================= RENDER ENV (xavier-social-bot) =================")
    print(f"YT_REFRESH_TOKEN={r['refresh_token']}")
    print(f"YT_CLIENT_ID={client_id}")
    print(f"YT_CLIENT_SECRET={client_secret}")
    print(f"YT_CHANNEL_ID={cid}")
    print("====================================================================")
    print(f"\nChannel: {name}")


API_BASE = "https://www.googleapis.com/youtube/v3"

if __name__ == "__main__":
    main()
