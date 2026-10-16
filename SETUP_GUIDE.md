# Setup guide: every step (about 30-40 minutes, done once)

You need: a GitHub account, a Google account that owns your YouTube channel, a Telegram account, Python 3.10+ on your computer.

## PART A: Accounts and keys

### Step 1. Put the project on GitHub
1. Unzip `leetcode-yt-bot-v2.zip`.
2. On github.com click New repository. Name it (for example `leetcode-yt-bot`). Choose **Public** (unlimited free Actions minutes; your secrets stay private). Do not add a README.
3. In the unzipped folder run:
   ```
   git init
   git add .
   git commit -m "first version"
   git branch -M main
   git remote add origin https://github.com/YOUR_NAME/leetcode-yt-bot.git
   git push -u origin main
   ```
   (.gitignore already blocks .env, token.json, client_secret.json.)

### Step 2. Free Gemini API key
1. Open https://aistudio.google.com and sign in.
2. Click **Get API key** > create a key. Copy it.
3. In your GitHub repo: Settings > Secrets and variables > Actions > **New repository secret**.
   Name `GEMINI_API_KEY`, value = the key.

### Step 3. YouTube API project
1. Open https://console.cloud.google.com > create a **new project**.
2. APIs & Services > Library > search **YouTube Data API v3** > Enable.
3. APIs & Services > **OAuth consent screen** > User type **External** > fill app name and your email > Save.
4. On the same screen click **Publish app** so the status shows **In production**. (If it stays in "Testing", the login expires after 7 days and the bot silently stops.)
5. APIs & Services > Credentials > Create credentials > **OAuth client ID** > Application type **Desktop app** > Create > **Download JSON**.
6. Rename the downloaded file to `client_secret.json` and put it in the project folder (NOT committed to GitHub).

### Step 4. Log in once on your computer
1. In the project folder run: `pip install google-auth-oauthlib google-api-python-client python-dotenv`
2. Run: `python scripts/auth_youtube.py`
3. A browser opens. Choose the Google account that owns your YouTube channel. If you see "Google hasn't verified this app", click **Advanced** > **Go to ... (unsafe)**. It is your own app. Allow access.
4. A file `token.json` appears. Open it, copy ALL of its text.
5. GitHub repo > Settings > Secrets and variables > Actions > New repository secret: name `YOUTUBE_TOKEN_JSON`, value = the pasted text.
6. Never share or commit `token.json`.

### Step 5. Telegram alerts
1. In Telegram search **@BotFather** > send `/newbot` > follow the prompts > copy the token it gives you.
2. Add secret `TELEGRAM_BOT_TOKEN` with that token.
3. Open your new bot in Telegram and send it any message (for example "hi").
4. In a browser open: `https://api.telegram.org/botYOUR_TOKEN/getUpdates`
5. Find `"chat":{"id": 123456789 ...` and copy the number. Add secret `TELEGRAM_CHAT_ID` with it.

### Step 6. Settings (repo Variables, not secrets)
Settings > Secrets and variables > Actions > **Variables** tab > New repository variable:

| Name | Example | Meaning |
|---|---|---|
| PUBLISH_TIME | 09:00 | when the video goes public (use 08:00 or later) |
| PUBLISH_TZ | Asia/Kolkata | your time zone |
| CHANNEL_NAME | My Channel | shown in the video header |
| REGION | IN | used for trend research |

Optional: `PUBLISH_MODE=manual` (every video waits for your approval), `LLM_MODEL` (if Gemini reports an unknown model), `KOKORO_VOICE` (try `af_heart`, `bm_george`, ...).

## PART B: Test, then go live

### Step 7. Test on your computer (optional, 2 minutes)
- Mac/Linux: `TTS_PROVIDER=preview python scripts/demo_offline.py`
- Windows (PowerShell): `$env:TTS_PROVIDER="preview"; python scripts/demo_offline.py`
(needs `pip install -r requirements.txt` and FFmpeg installed). Output: `data/demo-two-sum/final.mp4` and `thumb.jpg`.
`python scripts/selftest.py` runs the logic checks.

### Step 8. Dry run in the cloud
1. GitHub repo > Actions tab > **daily-leetcode-video** > **Run workflow**.
2. Tick **dry_run** > Run. Wait 20-40 minutes (the first run also downloads the voice model).
3. Open the finished run > Artifacts > **video-preview** > download. Watch the video, thumbnail and metadata.json. Nothing is uploaded in dry-run mode.

### Step 9. First real run
1. Run the workflow again with **dry_run unticked**.
2. You get a Telegram message: thumbnail, title, the exact go-live time, links to watch/review.
3. The video is uploaded private with a scheduled publish time. YouTube makes it public at that moment.

### Step 10. YouTube API audit (needed for public videos)
Videos uploaded through an unaudited API project are forced private. Submit Google's free **"YouTube API Services - Audit and Quota Extension"** form for your Cloud project (search that title; link is in the YouTube API docs). Approval can take days to weeks. Until then the bot works but videos stay private.

### Step 11. Done: it now runs every day
GitHub starts it daily at 00:30 UTC (06:00 IST). Keep the repo active: scheduled workflows are paused after 60 days with no repo activity, so push a tiny commit now and then.

## PART C: Your control

| I want to... | Do this |
|---|---|
| Do nothing | It publishes itself at PUBLISH_TIME |
| Watch first | Telegram link, or the video-preview artifact of that day's run |
| Stop today's video | Actions > **review-video** > Run workflow > action `hold`, video_id = the id in the Telegram link |
| Publish immediately | action `publish` + video_id |
| Move the time | action `reschedule` + video_id + when = `2026-10-14 09:00` |
| Remove it | action `delete` + video_id |
| See what's scheduled | action `list` |
| Approve every video | set variable PUBLISH_MODE = manual |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Video stays private after the go-live time | API audit not approved yet (Step 10) |
| Run fails with `invalid_grant` / 401 | OAuth app was in Testing; set to In production, redo Step 4, update the secret |
| Gemini error 404 / unknown model | set variable LLM_MODEL to a current Flash model name from AI Studio |
| Gemini error 429 | free-tier limit; the bot retries, otherwise re-run later |
| No Telegram message | message your bot first, recheck TELEGRAM_CHAT_ID |
| "Thumbnail not set" in the log | verify your channel with a phone number at youtube.com/verify |
| Run did not start on time | GitHub cron can be delayed; the publish time is still exact because YouTube handles it |
| Any other error | copy the red error text from the Actions log and send it to Claude |
