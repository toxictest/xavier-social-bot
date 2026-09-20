"""Facebook Page adapter — same Meta Graph API as Instagram"""
import logging

import aiohttp

log = logging.getLogger("sm.fb")

BASE = "https://graph.facebook.com/v19.0"


async def fb_post_image(session, page_id, token, image_bytes, caption):
    data = aiohttp.FormData()
    data.add_field("message", caption[:2200])
    data.add_field("source", image_bytes, filename="post.jpg", content_type="image/jpeg")
    data.add_field("access_token", token)
    async with session.post(f"{BASE}/{page_id}/photos", data=data) as r:
        body = await r.json(content_type=None)
        if r.status != 200:
            raise RuntimeError(f"FB photo {r.status}: {str(body)[:200]}")
        return body.get("post_id") or body.get("id")


async def fb_post_text(session, page_id, token, text):
    async with session.post(
        f"{BASE}/{page_id}/feed",
        data={"message": text[:5000], "access_token": token},
    ) as r:
        body = await r.json(content_type=None)
        if r.status != 200:
            raise RuntimeError(f"FB feed {r.status}: {str(body)[:200]}")
        return body.get("id")


async def fb_recent_comments(session, page_id, token, limit=5):
    """Recent page posts ke saath attached public comments."""
    url = (
        f"{BASE}/{page_id}/feed?limit={limit}"
        f"&fields=created_time,comments.limit(10){{id,text,from,created_time}}"
        f"&access_token={token}"
    )
    out = []
    async with session.get(url) as r:
        body = await r.json(content_type=None)
        if r.status != 200:
            raise RuntimeError(f"FB comments {r.status}: {str(body)[:200]}")
        for node in body.get("data", []):
            for c in (node.get("comments") or {}).get("data", []):
                out.append(c)
    return out


async def fb_reply(session, token, comment_id, text):
    async with session.post(
        f"{BASE}/{comment_id}/comments",
        data={"message": text[:500], "access_token": token},
    ) as r:
        body = await r.json(content_type=None)
        if r.status != 200:
            raise RuntimeError(f"FB reply {r.status}: {str(body)[:200]}")
        return True
