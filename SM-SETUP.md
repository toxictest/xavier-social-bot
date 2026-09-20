# 📱 Social Media Bot — Setup Guide

Alag project, alag env, alag Render service. Main project (Telegram/WhatsApp bot) se poori tarah alag.

## Kya karta hai
| Task | Time (IST) | Kaam |
|---|---|---|
| `morning` | 8:00 AM | Aaj ke current affairs se AI post (image card ke saath) → Instagram auto-post ya Telegram pe manual |
| `evening` | 6:00 PM | Study motivation + exam tip post → same flow |
| `comments` | 7 AM–11 PM, har 30 min | Naye Instagram comments ko AI se reply |

Trigger kisi bhi jagah nahi chahiye — **Telegram bot (xavier-telegram-bot) ka internal scheduler** yeh service jaagata hai. Isliye yeh service 95% time soya rehta hai = **~0-5 Render hours/month** (750 hr pool pe farak nahi padta).

## Files
```
app.py          # Main service (task endpoint)
content.py      # News RSS + AI prompts
card.py         # Instagram image card (PIL)
ig.py           # Instagram Graph API adapter
render.yaml     # Render service config
```

## Step 1: Render pe deploy (5 min, bina card ke)
1. Is repo ko GitHub pe push karo (agent karega)
2. Render → **New + → Web Service** → GitHub repo `xavier-social-bot`
3. render.yaml auto-apply hogi (python, `python app.py`, health `/health`)
4. **Environment variables**:
   | Name | Value |
   |---|---|
   | `GROQ_API_KEY` | tumhari gsk_ key |
   | `TELEGRAM_BOT_TOKEN` | tumhara bot token |
   | `OWNER_TG_ID` | `5573716572` |
   | `IG_USER_TOKEN` | (Step 3 me milega) |
   | `IG_USER_ID` | (Step 3 me milega) |
   | `IG_PAGE_NAME` | `@xavier` (apna handle) |
   | `TASK_SECRET` | `xavier-sm-task-2026` |
5. Region: **Frankfurt** → Deploy
6. Health check: `https://xavier-social-bot.onrender.com/health` → "sm-bot alive"

## Step 2: Telegram bot me link karo (2 min)
Render pe **xavier-telegram-bot** service → Settings → Environment → nayi variable:
- `SOCIAL_BOT_URL` = `https://xavier-social-bot.onrender.com`

(Save karte hi auto-redeploy hoga.) Ab scheduler sab trigger karega.

## Step 3: Instagram API setup (10 min, free)
1. **Instagram app**: Settings → Account type → **Professional/Creator** (free, personal bhi rahega bas API milegi)
2. [developers.facebook.com](https://developers.facebook.com) → **Create App** → Type: **Business**
3. App me **Instagram** product add karo
4. **Graph API Explorer** (graph.facebook.com) kholo:
   - Apna IG account login karo
   - Permissions: `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`
   - **Generate long-lived token** (60 din → usse permanent banao: graph.facebook.com/me?grant_type=fb_exchange_token...)
   - `/me` endpoint call karo → jo `id` aaye wahi **IG_USER_ID** hai
5. Token + ID Render ke env me daalo → redeploy
6. **App Settings → Basic → Add yourself as Test User** (dev mode me sirf test users ka account access hota hai)

> Ab tak token pending rahe toh bhi system chalega — posts **tumhare Telegram pe** aayengi "📱 Manual post karo" ke saath.

## Koi aur platform chahiye?
Code me `ig.py` jaisa adapter file banao (e.g. `x.py`) + `app.py` me call karo — 30 min ka kaam. Bata dena kaunsa: X / YouTube / Facebook.

## Important
- Yeh service Render free me hai, par **hours pool share hota hai** — isliye yeh 95% time soya rehta hai (wake-on-task design)
- Agar Render pool tight ho: yahi repo **Koyeb** (free, bina card, always-on) pe bhi chalega — code same
