"""
Xavier Social Media Bot — alag service (Render pe)
Wake-on-task: Telegram bot ka scheduler /task endpoint pe hit karta hai.

Platforms (jo connected hai, wahin post hota hai):
  Instagram  → image post + comment replies
  Facebook   → image post + comment replies
  YouTube    → community post + poll + video upload

Endpoints:
  GET  /health
  GET  /task?name=morning|evening|comments|poll|video&token=<TASK_SECRET>
         poll  → &topic=... (&options=A|B|C optional, warna AI banayega)
         video → &file=<uploaded-name>&title=...&desc=...
  POST /upload?token=...   multipart field "file" → save, {ok, file} wapas
"""
import asyncio
import io
import logging
import mimetypes
import os
import time
from datetime import datetime, timedelta, timezone

import aiohttp
from aiohttp import web

import card as cardmod
import content
import fb
import ig
import yt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("sm")

PORT = int(os.getenv("PORT", "10000"))
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("MODEL", "qwen/qwen3.8-27b")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_TG = os.getenv("OWNER_TG_ID", "")
TASK_SECRET = os.getenv("TASK_SECRET", "xavier-sm-task-2026")
# Instagram
IG_TOKEN = os.getenv("IG_USER_TOKEN", "")
IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_PAGE = os.getenv("IG_PAGE_NAME", "@xavier")
# Facebook Page
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN", "")
# YouTube
YT_REFRESH = os.getenv("YT_REFRESH_TOKEN", "")
YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_CHANNEL = os.getenv("YT_CHANNEL_ID", "")
# Media storage (Render disk ephemeral — files har redeploy pe reset)
MEDIA_DIR = os.getenv("MEDIA_DIR", "/tmp/sm-media")

STATE = {"seen_comments": set(), "yt_token": None}
IST = timezone(timedelta(hours=5, minutes=30))


# ---------- AI ----------
async def groq(messages, max_tokens=400, temperature=0.7):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as s:
        async with s.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        ) as r:
            if r.status != 200:
                raise RuntimeError(f"Groq {r.status}: {(await r.text())[:200]}")
            d = await r.json()
    return (d["choices"][0]["message"]["content"] or "").strip()


# ---------- YouTube token cache ----------
async def yt_token(session):
    if not (YT_REFRESH and YT_CLIENT_ID and YT_CLIENT_SECRET):
        return None
    now = time.time()
    t = STATE["yt_token"]
    if t and t[1] > now + 60:
        return t[0]
    tok, exp = await yt.yt_refresh(session, YT_REFRESH, YT_CLIENT_ID, YT_CLIENT_SECRET)
    STATE["yt_token"] = (tok, now + exp)
    return tok


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
    async with session.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto", data=data) as r:
        if r.status != 200:
            log.error("TG photo fail: %s %s", r.status, (await r.text())[:200])


# ---------- Posts (cross-post to all enabled platforms) ----------
async def do_post(session, kind):
    if kind == "morning":
        headlines = await content.fetch_headlines(session)
        prompt = content.MORNING_PROMPT
        label = "🌅 MORNING POST"
        user_msg = "Aaj ke headlines:\n" + "\n".join(headlines)
    else:
        prompt = content.EVENING_PROMPT
        label = "🌆 EVENING POST"
        user_msg = "Post likho."

    raw = await groq(
        [{"role": "system", "content": prompt}, {"role": "user", "content": user_msg}],
        max_tokens=500,
    )
    hook, caption = content.split_hook(raw)
    image = cardmod.make_card(hook, footer=IG_PAGE.upper())

    results = {}
    if IG_TOKEN and IG_USER_ID:
        try:
            await ig.ig_post_image(session, image, caption, IG_TOKEN, IG_USER_ID)
            results["Instagram"] = "✅"
        except Exception as e:
            log.exception("IG post fail")
            results["Instagram"] = f"❌ {str(e)[:100]}"
    if FB_PAGE_ID and FB_PAGE_TOKEN:
        try:
            await fb.fb_post_image(session, FB_PAGE_ID, FB_PAGE_TOKEN, image, caption)
            results["Facebook"] = "✅"
        except Exception as e:
            log.exception("FB post fail")
            results["Facebook"] = f"❌ {str(e)[:100]}"
    if YT_CHANNEL:
        try:
            tok = await yt_token(session)
            if tok:
                await yt.yt_community_post(session, tok, YT_CHANNEL, f"{hook}\n\n{caption}")
                results["YouTube"] = "✅"
        except Exception as e:
            log.exception("YT post fail")
            results["YouTube"] = f"❌ {str(e)[:100]}"

    lines = [label, ""]
    if results:
        lines += [f"{v} {k}" for k, v in results.items()]
        lines.append("")
        lines.append(caption[:700])
    else:
        lines.append("📱 Koi platform connected nahi — manual post karo:")
        lines.append("")
        lines.append(caption[:900])
    await tg_send_photo(session, image, caption="\n".join(lines))

    failed = [k for k, v in results.items() if not v.startswith("✅")]
    if not results:
        return "ok (manual)"
    return f"ok ({len(results) - len(failed)}/{len(results)} platforms)"


# ---------- Poll ----------
async def do_poll(session, topic, options):
    opts = [o.strip() for o in options.split("|") if o.strip()][:4]
    question = topic
    if len(opts) < 2:
        raw = await groq(
            [
                {
                    "role": "user",
                    "content": (
                        f"SSC CGL ke liye ek poll banao. Topic: {topic}\n"
                        "Format: pehli line = poll ka sawaal, phir 3 options (har ek nayi line). "
                        "Roman Hinglish, short. Kuch aur mat likho."
                    ),
                }
            ],
            max_tokens=120,
        )
        parts = [p.strip() for p in raw.splitlines() if p.strip()]
        question = parts[0] if parts else topic
        opts = parts[1:5]
    if not opts:
        return "error: no options"

    pseudo = f"🗳️ POLL: {question}\n\n" + "".join(
        f"{chr(65 + i)}) {o}\n" for i, o in enumerate(opts)
    ) + "\nComment me vote karo! ⬇️"

    results = {}
    if YT_CHANNEL:
        try:
            tok = await yt_token(session)
            if tok:
                await yt.yt_poll(session, tok, YT_CHANNEL, question, opts, hours=24)
                results["YouTube"] = "✅ poll"
        except Exception as e:
            log.exception("YT poll fail")
            results["YouTube"] = f"❌ {str(e)[:100]}"
    if IG_TOKEN and IG_USER_ID:
        try:
            img = cardmod.make_card(question[:90], footer="VOTE IN COMMENTS")
            await ig.ig_post_image(session, img, pseudo, IG_TOKEN, IG_USER_ID)
            results["Instagram"] = "✅ poll (image)"
        except Exception as e:
            log.exception("IG poll fail")
            results["Instagram"] = f"❌ {str(e)[:100]}"
    if FB_PAGE_ID and FB_PAGE_TOKEN:
        try:
            await fb.fb_post_text(session, FB_PAGE_ID, FB_PAGE_TOKEN, pseudo)
            results["Facebook"] = "✅ poll (text)"
        except Exception as e:
            log.exception("FB poll fail")
            results["Facebook"] = f"❌ {str(e)[:100]}"

    lines = ["🗳️ POLL", ""]
    if results:
        lines += [f"{v} {k}" for k, v in results.items()]
        lines.append("")
    lines.append(pseudo[:900])
    await tg_send(session, "\n".join(lines))

    if not results:
        return "ok (manual)"
    failed = [k for k, v in results.items() if not v.startswith("✅")]
    return f"ok ({len(results) - len(failed)}/{len(results)} platforms)"


# ---------- Video (YouTube upload) ----------
async def do_video(session, fname, title, desc):
    fpath = os.path.join(MEDIA_DIR, os.path.basename(fname or ""))
    if not (fname and os.path.exists(fpath)):
        return "error: file nahi mili (pehle /upload karo)"
    if not (YT_CHANNEL and YT_REFRESH and YT_CLIENT_ID and YT_CLIENT_SECRET):
        return "skip (YT token pending)"
    tok = await yt_token(session)
    size = os.path.getsize(fpath)
    if size > 500 * 1024 * 1024:
        return "error: video 500MB se badi"
    mime = mimetypes.guess_type(fpath)[0] or "video/mp4"
    with open(fpath, "rb") as f:
        data = f.read()
    vid = await yt.yt_upload_video(
        session, tok, data, mime, title or "Xavier update", desc or f"#SSCCGL #CurrentAffairs"
    )
    await tg_send(session, f"🎥 YouTube pe video upload ho gayi:\nhttps://youtu.be/{vid}")
    return f"ok (yt: {vid})"


# ---------- Comments (IG + FB) ----------
async def _reply_one(session, cid, c, prefix):
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
    if prefix == "ig":
        return await ig.ig_reply(session, IG_TOKEN, cid, reply)
    return await fb.fb_reply(session, FB_PAGE_TOKEN, cid, reply)


def _new_recent_comments(comments):
    """seen-set + 24h window filter."""
    out = []
    for c in comments:
        cid = c.get("id")
        if not cid or cid in STATE["seen_comments"]:
            continue
        try:
            ct = datetime.fromisoformat(c["created_time"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - ct > timedelta(hours=24):
                STATE["seen_comments"].add(cid)
                continue
        except Exception:
            pass
        out.append((cid, c))
    return out


async def do_comments(session):
    total = 0
    if IG_TOKEN and IG_USER_ID:
        try:
            media_ids = await ig.ig_recent_media(session, IG_TOKEN, IG_USER_ID, limit=5)
            for mid in media_ids:
                try:
                    comments = await ig.ig_comments(session, IG_TOKEN, mid)
                except Exception:
                    log.exception("IG comments fetch fail %s", mid)
                    continue
                for cid, c in _new_recent_comments(comments):
                    try:
                        if await _reply_one(session, cid, c, "ig"):
                            total += 1
                    except Exception:
                        log.exception("IG reply fail %s", cid)
                    STATE["seen_comments"].add(cid)
        except Exception:
            log.exception("IG comments fail")
    if FB_PAGE_ID and FB_PAGE_TOKEN:
        try:
            comments = await fb.fb_recent_comments(session, FB_PAGE_ID, FB_PAGE_TOKEN)
            for cid, c in _new_recent_comments(comments):
                try:
                    if await _reply_one(session, cid, c, "fb"):
                        total += 1
                except Exception:
                    log.exception("FB reply fail %s", cid)
                STATE["seen_comments"].add(cid)
        except Exception:
            log.exception("FB comments fail")
    if not (IG_TOKEN and IG_USER_ID) and not (FB_PAGE_ID and FB_PAGE_TOKEN):
        return "skip (no IG/FB token)"
    if total:
        await tg_send(session, f"💬 {total} comments ka reply kar diya (IG + FB)")
    STATE["seen_comments"] = set(list(STATE["seen_comments"])[-2000:])
    return f"ok ({total} replies)"


# ---------- HTTP ----------
async def health(request):
    return web.Response(text="sm-bot alive")


async def task(request):
    if request.query.get("token") != TASK_SECRET:
        return web.Response(status=403, text="forbidden")
    name = request.query.get("name", "")
    if name not in ("morning", "evening", "comments", "poll", "video"):
        return web.Response(status=400, text="unknown task")
    log.info("TASK START: %s", name)
    try:
        async with aiohttp.ClientSession() as session:
            if name == "comments":
                result = await do_comments(session)
            elif name == "poll":
                result = await do_poll(
                    session,
                    request.query.get("topic", "Aaj ke topic pe best study strategy kya hai?"),
                    request.query.get("options", ""),
                )
            elif name == "video":
                result = await do_video(
                    session,
                    request.query.get("file", ""),
                    request.query.get("title", ""),
                    request.query.get("desc", ""),
                )
            else:
                result = await do_post(session, name)
        log.info("TASK DONE: %s -> %s", name, result)
        if result.startswith("error"):
            return web.Response(text=result, status=400)
        return web.Response(text=f"done: {result}")
    except Exception as e:
        log.exception("TASK FAIL: %s", name)
        try:
            async with aiohttp.ClientSession() as session:
                await tg_send(session, f"⚠️ Social task '{name}' fail hua: {e}")
        except Exception:
            pass
        return web.Response(text=f"error: {e}", status=500)


async def upload(request):
    if request.query.get("token") != TASK_SECRET:
        return web.Response(status=403, text="forbidden")
    os.makedirs(MEDIA_DIR, exist_ok=True)
    reader = await request.multipart()
    saved = None
    async for part in reader:
        if part.name != "file" or not part.filename:
            continue
        fname = f"{int(time.time())}_{os.path.basename(part.filename)[:80]}"
        fpath = os.path.join(MEDIA_DIR, fname)
        size = 0
        with open(fpath, "wb") as f:
            while True:
                chunk = await part.read_chunk(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > 300 * 1024 * 1024:
                    f.close()
                    os.remove(fpath)
                    return web.Response(text="error: file 300MB se badi", status=413)
                f.write(chunk)
        saved = fname
    if not saved:
        return web.Response(text="error: 'file' field nahi mila", status=400)
    log.info("UPLOAD saved: %s", saved)
    return web.json_response({"ok": True, "file": saved})


def main():
    app = web.Application(client_max_size=300 * 1024 * 1024)
    app.router.add_get("/health", health)
    app.router.add_get("/task", task)
    app.router.add_post("/upload", upload)
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)
    platforms = []
    if IG_TOKEN and IG_USER_ID:
        platforms.append("IG")
    if FB_PAGE_ID and FB_PAGE_TOKEN:
        platforms.append("FB")
    if YT_CHANNEL:
        platforms.append("YT")
    log.info(
        "Social media bot running on :%s — platforms: %s",
        PORT,
        ", ".join(platforms) if platforms else "NONE (manual mode)",
    )


if __name__ == "__main__":
    main()
