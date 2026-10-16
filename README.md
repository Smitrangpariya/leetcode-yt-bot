# LeetCode -> YouTube: fully automatic daily channel (free, cloud)

Every day at an exact time, with zero clicks from you:

1. Fetches LeetCode's daily problem.
2. Asks a free LLM (Gemini) for 2-4 approaches, **runs every approach on 10 tests and requires identical outputs** (retries on mismatch).
3. Researches YouTube: top videos on this problem/niche, their tags, hashtags and thumbnail style.
4. Writes title, description (with chapters), hashtags and tags; draws a thumbnail.
5. Renders an **animated walkthrough**: code appears line by line, a highlight follows the narration, and a side panel shows the **real variable values** captured by running the code.
6. Voices it with a free open-source neural voice (Kokoro) with natural pacing variation, mixes optional music.
7. Uploads it **private with an exact `publishAt` time**: YouTube itself makes it public at that second.
8. Sends you a Telegram alert (thumbnail, link, scheduled time). Do nothing and it goes live. Want to look? Watch it, then hold / publish / reschedule / delete it.

## Why it publishes at the exact time
GitHub's cron can start 5-60 min late (the job starts ~06:00 IST and takes ~20-40 min, so pick a `PUBLISH_TIME` of 08:00 IST or later). So the job runs early (00:30 UTC), uploads a *scheduled* video, and YouTube publishes at `PUBLISH_TIME`. The gap is your review window.

## Setup (about 30 minutes, once)
1. **Free LLM key:** https://aistudio.google.com -> Get API key -> secret `GEMINI_API_KEY`.
   Model names change; if a run fails with a model error, set repo variable `LLM_MODEL` to a current Flash model from AI Studio.
2. **YouTube API:** Google Cloud console -> new project -> enable *YouTube Data API v3* -> OAuth consent screen -> **set publishing status to "In production"** (in "Testing" the login token expires after 7 days and the bot breaks) -> create *Desktop app* credentials -> save as `client_secret.json`.
   On your computer: `pip install google-auth-oauthlib google-api-python-client python-dotenv && python scripts/auth_youtube.py` -> creates `token.json`. Paste its contents into secret `YOUTUBE_TOKEN_JSON`.
3. **IMPORTANT, API audit:** videos uploaded through an *unaudited* API project are forced to private. Apply for Google's free "YouTube API Services - Audit and Quota Extension" form so scheduled public publishing works. Until approved, the bot still runs but videos stay private.
4. **Telegram (recommended):** talk to @BotFather -> /newbot -> token; message your bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` to read your chat id. Secrets `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
5. Push this folder to a GitHub repo. Add the secrets above. Add repo **variables** (Settings -> Variables): `PUBLISH_TIME` (e.g. `09:00`), `PUBLISH_TZ` (e.g. `Asia/Kolkata`), `CHANNEL_NAME`, `REGION`.
6. Test: Actions -> *daily-leetcode-video* -> Run workflow with **dry_run = true**. Download the `video-preview` artifact and watch it. Then run once with dry_run = false.

Try locally with no keys at all: `TTS_PROVIDER=preview python scripts/demo_offline.py` (silent, 20 s) or without `TTS_PROVIDER` for the real voice.

## Control
| I want to... | Do this |
|---|---|
| Let it run itself | Nothing. It publishes at `PUBLISH_TIME`. |
| Watch before it goes live | Link in the Telegram alert, or the workflow artifact. |
| Stop today's video | Actions -> *review-video* -> action `hold` + video id. (Or edit the schedule in YouTube Studio.) |
| Publish now / change the time / delete | `publish` / `reschedule` (+ `when`) / `delete`. |
| Approve every video myself | Set variable `PUBLISH_MODE=manual`: uploads stay private until you `publish`. |

## Free-tier reality check
- **GitHub Actions:** unlimited on public repos; 2,000 min/month on private repos (this uses roughly 20-30 min/day, so a private repo is tight, public is fine).
  GitHub disables scheduled workflows after 60 days with no repo activity: push a small commit now and then.
- **Gemini free tier:** rate-limited, and Google may use free-tier inputs/outputs to improve its models (fine for public LeetCode content). Check Google's terms for commercial use.
- **YouTube API quota:** upload ~1,600 units + research ~200 of the 10,000/day default.
- **Voice:** Kokoro is free but not *your* voice. Cloning your own voice needs a paid ElevenLabs plan (`TTS_PROVIDER=elevenlabs`). The free Microsoft "edge-tts" voice is blocked from cloud IPs, so it is only a fallback.

## Make it feel less "bot"
- Drop a royalty-free `assets/music.mp3` (YouTube Audio Library). It is mixed in quietly.
- Keep `AI_DISCLOSURE=true`. YouTube requires disclosing realistic synthetic media, and its monetization rules target mass-produced repetitive content, so quality and honesty are your best protection.
- Skim the first 2 weeks of videos; tweak prompts in `pipeline/solver.py` (voice of the script) and `pipeline/draw.py` (look).
