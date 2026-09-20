"""
Xavier Social Media Bot — alag service (Render pe)
Wake-on-task: Telegram bot ka scheduler /task endpoint pe hit karta hai.

Endpoints:
  GET /health
  GET /task?name=morning|evening|comments&token=<TASK_SECRET>

Flow:
  morning  → news headlines + AI post → Instagram auto-post (token ho toh), warna Telegram pe manual post
  evening  → motivation/tip post → same flow
  comments → recent Instagram comments → AI reply (har 30 min)
"""
import asyncio
import io
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import aiohttp
from aiohttp import web

import card as cardmod
import content
import ig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("sm")

PORT = int(os.getenv("PORT", "10000"))
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("MODEL", "qwen/qwen3.8-27b")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_TG = os.getenv("OWNER_TG_ID", "")
TASK_SECRET = os.getenv("TASK_SECRET", "xavier-sm-task-2026")
IG_TOKEN = os.getenv("IG_USER_TOKEN", "")
IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_PAGE = os.getenv("IG_PAGE_NAME", "@xavier")

STATE = {"seen_comments": set(), "stats": {}}
IST = timezone(timedelta(hours=5, minutes=30))


# ---------- AI ----------
async def groq(messages, max_tokens=400, temperature=0.7):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as s:
        async with s.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
        ) as r:
            if r.status != 200:
                raise RuntimeError(f"Groq {r.status}: {(await r.text())[:200]}")
            d = await r.json()
    return (d["choices"][0]["message"]["content"] or "").strip()


# ---------- Telegram notify ----------
async def tg_send(session, text):
    if not (TG_TOKEN and OWNER_TG):
        return
    async with session.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={"chat_id": OWNER_TG, "text": text[:4000]},
    ) as r:
        if r.status != 200:
            log.error("TG send fail: %s %s", r.status, (await r.text())[:200])


async def tg_send_photo(session, photo_bytes, caption=""):
    if not (TG_TOKEN and OWNER_TG):
        return
    data = aiohttp.FormData()
    data.add_field("chat_id", OWNER_TG)
    if caption:
        data.add_field("caption", caption[:1000])
    data.add_field("photo", io.BytesIO(photo_bytes), filename="post.jpg", content_type="image/jpeg")
    async with session.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto", data=data
    ) as r:
        if r.status != 200:
            log.error("TG photo fail: %s %s", r.status, (await r.text())[:200])


# ---------- Tasks ----------
async def do_post(session, kind):
    if kind == "morning":
        headlines = await content.fetch_headlines(session)
        prompt = content.MORNING_PROMPT
        label = "🌅 MORNING POST"
    else:
        prompt = content.EVENING_PROMPT
        label = "🌆 EVENING POST"

    raw = await groq(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": (f"Aaj ke headlines:\n" + "\n".join(headlines)) if kind == "morning" else "Post likho."},
        ],
        max_tokens=500,
    )
    hook, caption = content.split_hook(raw)
    image = cardmod.make_card(hook, footer=IG_PAGE.upper())

    ig_ok = False
    if IG_TOKEN and IG_USER_ID:
        try:
            media_id = await ig.ig_post_image(session, image, caption, IG_TOKEN, IG_USER_ID)
            ig_ok = True
            log.info("IG post published: %s", media_id)
        except Exception as e:
            log.exception("IG post fail")
            caption = f"⚠️ IG post fail hua ({e}). Manual post karo:\n\n" + caption

    if ig_ok:
        msg = f"{label}\n✅ Instagram pe post ho gayi!\n\n{caption}"
        await tg_send(session, msg)
    else:
        # IG token nahi → image + caption dono Telegram pe, user manually post karega
        await tg_send_photo(
            session, image,
            caption=f"{label}\n📱 Ise manually Instagram pe post karo (caption neeche):\n\n{caption}",
        )
    return "ok"


async def do_comments(session):
    if not (IG_TOKEN and IG_USER_ID):
        return "skip (no IG token)"
    media_ids = await ig.ig_recent_media(session, IG_TOKEN, IG_USER_ID, limit=5)
    replied = 0
    for mid in media_ids:
        try:
            comments = await ig.ig_comments(session, IG_TOKEN, mid)
        except Exception as e:
            log.exception("comments fetch fail %s", mid)
            continue
        for c in comments:
            cid = c.get("id")
            if not cid or cid in STATE["seen_comments"]:
                if cid:
                    STATE["seen_comments"].add(cid)
                continue
            # sirf aakhri 24 ghante ke comments
            try:
                ct = datetime.fromisoformat(c["created_time"].replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - ct > timedelta(hours=24):
                    STATE["seen_comments"].add(cid)
                    continue
            except Exception:
                pass
            reply = await groq(
                [
                    {
                        "role": "user",
                        "content": content.COMMENT_REPLY_PROMPT.format(
                            comment=c.get("text", ""), user=c.get("from", {}).get("name", "user")
                        ),
                    }
                ],
                max_tokens=120,
                temperature=0.5,
            )
            try:
                if await ig.ig_reply(session, IG_TOKEN, cid, reply):
                    replied += 1
            except Exception as e:
                log.exception("comment reply fail %s", cid)
            STATE["seen_comments"].add(cid)
    if replied:
        await tg_send(session, f"💬 {replied} comments ka reply kar diya (Instagram)")
    STATE["seen_comments"] = set(list(STATE["seen_comments"])[-2000:])
    return f"ok ({replied} replies)"


# ---------- HTTP ----------
async def health(request):
    return web.Response(text="sm-bot alive")


async def task(request):
    if request.query.get("token") != TASK_SECRET:
        return web.Response(status=403, text="forbidden")
    name = request.query.get("name", "")
    if name not in ("morning", "evening", "comments"):
        return web.Response(status=400, text="unknown task")
    log.info("TASK START: %s", name)
    try:
        async with aiohttp.ClientSession() as session:
            if name == "comments":
                result = await do_comments(session)
            else:
                result = await do_post(session, name)
        log.info("TASK DONE: %s -> %s", name, result)
        return web.Response(text=f"done: {result}")
    except Exception as e:
        log.exception("TASK FAIL: %s", name)
        try:
            async with aiohttp.ClientSession() as session:
                await tg_send(session, f"⚠️ Social task '{name}' fail hua: {e}")
        except Exception:
            pass
        return web.Response(text=f"error: {e}", status=500)


def main():
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/task", task)
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)
    log.info("Social media bot running on :%s (IG token: %s)", PORT, "set" if IG_TOKEN else "NAHI")


if __name__ == "__main__":
    main()
