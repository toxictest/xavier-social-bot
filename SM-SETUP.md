# Xavier Social Media Bot — Setup Guide

Ek service, **3 platforms** (jo connected hai, wahin post hota hai). Post ek baar AI likhta hai, phir sab jagah cross-post.

| Post type | Instagram | Facebook | YouTube |
|---|---|---|---|
| Image + caption | ✅ auto | ✅ auto | (community me text) |
| Text post | ❌ | ✅ | ✅ community post |
| **Poll** | ✅ (image + comment-vote) | ✅ (text) | ✅ (real poll, 24h) |
| **Video upload** | manual | manual | ✅ auto (TG me video bhejo) |
| Comment auto-reply | ✅ | ✅ | (v2 me) |
| Reels/Shorts/Live/Stories | manual | manual | Shorts = video upload |

---

## 1. Render deploy (ek baar)

1. Render → **New → Web Service** → repo `toxictest/xavier-social-bot`
2. Environment Variables (jo platform use karna hai uske vars daalo):
   - `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, `OWNER_TG_ID=5573716572`, `TASK_SECRET=xavier-sm-task-2026`
   - Instagram ke liye: `IG_USER_TOKEN`, `IG_USER_ID`, `IG_PAGE_NAME`
   - Facebook ke liye: `FB_PAGE_ID`, `FB_PAGE_TOKEN`
   - YouTube ke liye: `YT_REFRESH_TOKEN`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_CHANNEL_ID`
3. Deploy. URL milega `https://xavier-social-bot.onrender.com`
4. **`xavier-telegram-bot` service** pe env add karo: `SOCIAL_BOT_URL=https://xavier-social-bot.onrender.com` (redeploy trigger hoga, scheduler active)

Ab tak ka flow (bina IG/FB/YT token ke bhi): roz 8 AM post + 6 PM post tumhare **Telegram pe aati hai**, tum manually post karte ho.

---

## 2. Instagram connect (Meta Business)

1. Instagram account → **Professional (Business)** banao: Settings → Account type → Switch to professional
2. [developers.facebook.com](https://developers.facebook.com) → **My Apps → Create App** → Business type
3. App me **Instagram Graph API** product add karo
4. Permissions: `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`
5. **Generate Token** (Business Settings → System Users / Graph Explorer se long-lived token) → `IG_USER_TOKEN`
6. `https://graph.facebook.com/v19.0/me?access_token=...` → jo `id` aaye wo `IG_USER_ID`
7. App testing mode me hai toh apni Instagram profile ko **Test User** add karo (App Dashboard → Instagram API section)

## 3. Facebook Page connect

1. Facebook **Page** chahiye (personal profile nahi). Naya banao ya existing.
2. Wahi Meta app (upar banaya) me **Facebook Login / Pages API** permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`
3. Business Settings → **Pages** → apni Page add karo → Page access token generate (long-lived) → `FB_PAGE_TOKEN`
4. Page ka ID: Page → About → Page ID (ya Graph Explorer `/{page-name}?fields=id`) → `FB_PAGE_ID`

## 4. YouTube connect (Google)

1. [console.cloud.google.com](https://console.cloud.google.com) → project banao
2. **APIs & Services → Library → YouTube Data API v3 → Enable**
3. **OAuth consent screen**: External, apna Gmail add karo (Test users me khud)
4. **Credentials → Create Credentials → OAuth client ID → Desktop app** → Client ID + Secret note karo
5. Apne PC pe:
   ```bash
   pip install requests
   python3 yt_auth.py
   ```
   → Google login + consent do → terminal me 4 env values print hongi (`YT_REFRESH_TOKEN`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_CHANNEL_ID`)
6. Unhe Render env me daalo

Free quota: ~6 video uploads/day + polls/community posts practically unlimited (10,000 units/day).

---

## Tasks (sab TG bot ke scheduler se auto)

| Time (IST) | Task |
|---|---|
| 8:00 AM | Morning news post (IG+FB image, YT community) |
| 6:00 PM | Evening motivation/tip post |
| Sunday 12:00 PM | Engagement poll (YT pe real poll, IG/FB pe comment-vote) |
| 7 AM–11 PM, har 30 min | IG + FB comments ka AI reply |

### Manual trigger (curl ya browser se)

```bash
B="https://xavier-social-bot.onrender.com"
# poll — AI options banayega:
curl "$B/task?name=poll&topic=Best%20strategy%20for%20CGL%3F&token=xavier-sm-task-2026"
# poll — apne options:
curl -G "$B/task" --data-urlencode "name=poll" --data-urlencode "topic=Kaunsa subject?" --data-urlencode "options=GS|Reasoning|Maths" --data-urlencode "token=xavier-sm-task-2026"
```

### Video → YouTube (bot flow)

1. Apne phone se **@Xavier_dadaBot** ko video bhejo (≤20MB)
2. Bot download karke social bot ko forward karega
3. Social bot YouTube pe upload karega, link Telegram pe aayega

Note: Render free tier ki disk **ephemeral** hai — upload ki files redeploy pe saaf ho jaati hain (video upload turant hota hai, isliye issue nahi).
