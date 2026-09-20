"""Content engine — Google News RSS se headlines + prompts"""
import logging
import urllib.parse
import xml.etree.ElementTree as ET

log = logging.getLogger("sm.content")

QUERIES = [
    ("current affairs today general knowledge", 5),
    ("SSC CGL latest update exam", 4),
]

MORNING_PROMPT = (
    "Tum ek SSC CGL coaching ke Instagram page ka content writer ho. Neeche diye aaj ke headlines se "
    "ek Instagram post likho Roman Hinglish me (Devanagari mat use karo). Format:\n"
    "Line 1: BADA HOOK (short, catchy, uppercase)\n"
    "Line 2-5: 2-3 current affairs ka simple explanation (exam ke liye kyun important)\n"
    "End: 3 hashtags (#SSCCGL #CurrentAffairs + 1 relevant)\n"
    "Total under 180 words. Pehli line ko 'HOOK:' se shuru karo."
)

EVENING_PROMPT = (
    "Tum ek SSC CGL coaching ke Instagram page ka content writer ho. Ek raat ka "
    "study motivation + exam tip wala post likho Roman Hinglish me (Devanagari mat use karo). "
    "Ek specific, actionable tip do (time management / practice / revision jaisa). "
    "Format: BADA HOOK pehli line (uppercase), phir 3-4 lines, end me 3 hashtags. Under 120 words. "
    "Pehli line ko 'HOOK:' se shuru karo."
)

COMMENT_REPLY_PROMPT = (
    "Tum SSC CGL coaching ke Instagram page ke owner ka assistant ho. Ek comment aaya hai: "
    '"{comment}" (user: {user}).\n'
    "Ek short, friendly, helpful reply do Roman Hinglish me (max 2 lines). "
    "Agar sawaal CGL/exam se related hai toh helpful jawab do. Bas reply likhna, kuch aur nahi."
)


async def fetch_headlines(session, limit=12):
    seen, out = set(), []
    for q, n in QUERIES:
        params = urllib.parse.urlencode(
            {"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}
        )
        try:
            async with session.get(
                f"https://news.google.com/rss/search?{params}",
                headers={"User-Agent": "Mozilla/5.0 (xavier-sm-bot)"},
            ) as r:
                if r.status != 200:
                    continue
                root = ET.fromstring(await r.read())
                for item in root.iter("item"):
                    t = (item.findtext("title") or "").strip()
                    s_el = item.find("source")
                    s = (s_el.text or "").strip() if s_el is not None else ""
                    if t and t.lower() not in seen:
                        seen.add(t.lower())
                        out.append(f"- {t} [{s}]")
                    if len(out) >= limit:
                        return out
        except Exception:
            log.exception("rss fail: %s", q)
    return out


def split_hook(post_text):
    """'HOOK: ...' wale format me pehli line alag, baaki caption."""
    lines = [l.strip() for l in post_text.splitlines() if l.strip()]
    if lines and lines[0].upper().startswith("HOOK:"):
        return lines[0].replace("HOOK:", "").strip(), "\n".join(lines[1:])
    return (lines[0] if lines else "CGL Preparation").strip(), "\n".join(lines[1:])
