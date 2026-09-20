"""Instagram Graph API adapter — post + comments + replies"""
import json
import logging

import aiohttp

log = logging.getLogger("sm.ig")

VERSION = "v19.0"
BASE = f"https://graph.facebook.com/{VERSION}"


def _tok(token):
    return {"access_token": token}


async def ig_post_image(session, image_bytes, caption, token, user_id):
    """2-step: create container -> publish. Returns media id."""
    form = aiohttp.FormData()
    form.add_field("media_type", "IMAGE")
    form.add_field("image", image_bytes, filename="post.jpg", content_type="image/jpeg")
    form.add_field("caption", caption[:2200])
    form.add_field("access_token", token)
    async with session.post(f"{BASE}/{user_id}/media", data=form) as r:
        d = await r.json()
    cid = d.get("id")
    if not cid:
        raise RuntimeError(f"container create fail: {json.dumps(d)[:300]}")
    async with session.post(
        f"{BASE}/{user_id}/media_publish",
        params={"creation_id": cid, "access_token": token},
    ) as r:
        d = await r.json()
    mid = d.get("id")
    if not mid:
        raise RuntimeError(f"publish fail: {json.dumps(d)[:300]}")
    return mid


async def ig_recent_media(session, token, user_id, limit=5):
    async with session.get(
        f"{BASE}/{user_id}/media",
        params={"fields": "id,caption,timestamp", "limit": limit, **_tok(token)},
    ) as r:
        d = await r.json()
    return [m["id"] for m in d.get("data", [])]


async def ig_comments(session, token, media_id, limit=50):
    async with session.get(
        f"{BASE}/{media_id}/comments",
        params={
            "fields": "id,text,from.name,created_time",
            "limit": limit,
            **_tok(token),
        },
    ) as r:
        d = await r.json()
    return d.get("data", [])


async def ig_reply(session, token, comment_id, text):
    async with session.post(
        f"{BASE}/{comment_id}/replies",
        params={"message": text[:500], **_tok(token)},
    ) as r:
        d = await r.json()
    return d.get("id")
