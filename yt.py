"""YouTube Data API v3 adapter — community post, poll, video upload.

Quota (free): 10,000 units/day → ~6 video uploads/day (1600 units each),
community posts/polls ~50 units → practically unlimited for daily use.
"""
import logging

log = logging.getLogger("sm.yt")

API = "https://www.googleapis.com/youtube/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"


async def yt_refresh(session, refresh_token, client_id, client_secret):
    async with session.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    ) as r:
        d = await r.json(content_type=None)
        if r.status != 200:
            raise RuntimeError(f"YT oauth {r.status}: {str(d)[:200]}")
        return d["access_token"], int(d.get("expires_in", 3500))


def _check(body, ctx):
    if isinstance(body, dict) and "error" in body:
        msg = body["error"].get("message", str(body))
        raise RuntimeError(f"{ctx}: {msg[:300]}")
    return body


async def yt_community_post(session, access_token, channel_id, text):
    payload = {
        "snippet": {
            "type": "post",
            "ownerChannelId": channel_id,
            "description": text[:10000],
        }
    }
    async with session.post(
        f"{API}/communityPosts?part=snippet",
        json=payload,
        headers={"Authorization": f"Bearer {access_token}"},
    ) as r:
        body = await r.json(content_type=None)
        if r.status // 100 != 2:
            _check(body, "YT community")
            raise RuntimeError(f"YT community {r.status}: {str(body)[:200]}")
        return body.get("id")


async def yt_poll(session, access_token, channel_id, question, options, hours=24):
    payload = {
        "snippet": {
            "type": "poll",
            "ownerChannelId": channel_id,
            "description": question[:500],
            "poll": {
                "options": [{"text": o[:100], "voteCount": 0} for o in options[:4]],
                "votingPeriod": min(max(int(hours), 1), 24) * 3600,
            },
        }
    }
    async with session.post(
        f"{API}/communityPosts?part=snippet",
        json=payload,
        headers={"Authorization": f"Bearer {access_token}"},
    ) as r:
        body = await r.json(content_type=None)
        if r.status // 100 != 2:
            _check(body, "YT poll")
            raise RuntimeError(f"YT poll {r.status}: {str(body)[:200]}")
        return body.get("id")


async def yt_upload_video(session, access_token, video_bytes, mime, title, description):
    """2-step resumable upload. Returns video id."""
    meta = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "categoryId": "22",  # People & Blogs
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    async with session.post(
        f"{API}/videos?uploadType=resumable&part=snippet,status",
        json=meta,
        headers=headers,
    ) as r:
        if r.status != 200:
            raise RuntimeError(f"YT upload init {r.status}: {(await r.text())[:200]}")
        loc = r.headers.get("Location")
        if not loc:
            raise RuntimeError("YT upload init: Location header nahi mila")
    async with session.put(
        loc,
        data=video_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": mime or "video/mp4",
        },
    ) as r:
        body = await r.json(content_type=None)
        if r.status // 100 != 2:
            _check(body, "YT upload")
            raise RuntimeError(f"YT upload {r.status}: {str(body)[:300]}")
        return body.get("id")
