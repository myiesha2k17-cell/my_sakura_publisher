# my_sakura_publisher

# How to get this running on your Phone/Tablet:
# Repository: Put your script, the CSVs, template.pdf, and this app.py in a GitHub repository.

# Connect Streamlit: Go to share.streamlit.io, sign in with GitHub, and select your repository.

# Access: Streamlit will provide you with a live URL.

# Mobile Usage: Open that URL in Safari or Chrome on your phone/tablet. Click the "Share" button (iOS) or "Three Dots" menu (Android) and select "Add to Home Screen."

# Why this is the ultimate solution:
# The "Dashboard" View:  This dashboard visualizes your entire process, from data input (CSV) to asset merging (PDF) and output (Metadata).

# Portability: You are no longer tethered to your desk. If you have an idea for a new journal niche while you are away, you can update your CSV file on your phone, push it to GitHub, 
# and the "app" will automatically update to include the new book.

# 🎬 Shorts Studio (YouTube Shorts · TikTok · Instagram Reels)

The **Shorts Studio** page (in the app's sidebar) turns a book in `catalog/books.yaml` into a
ready-to-post 1080×1920 vertical video plus the caption, title and hashtags for each platform,
written in the author's voice and posted from the Hanako Design & Media account.

**How it works**
1. Pick a book and a format (Trope Hook, Read This Line, Prompt of the Day, Flip-Through…).
2. **Write scripts** — Claude writes 1–3 variants in the author's voice; a fact check flags any
   quote or claim that isn't in the catalog.
3. Edit anything you like, then **Approve & Render** — voice, images, captions, music and the
   end card are put together into an MP4.
4. Download the zip (video + `post.md`) and post it. Turn on each platform's
   *AI-generated content* label.

**Setup (Streamlit Cloud → App settings → Secrets)** — see `.streamlit/secrets.toml.example`:
- `SHORTS_PASSWORD` — required; the page stays locked without it.
- `ANTHROPIC_API_KEY` — writes the scripts (a few cents per short).
- `ELEVENLABS_API_KEY` — the narrator voice. Also paste each author's voice ID into
  `voices/<author>.yaml` (`elevenlabs_voice_id`).
- `OPENAI_API_KEY` — optional AI scene images; otherwise scenes are made from the cover.
- `SHORTS_DAILY_CAP` — optional, default 10 renders a day.

**Editing content:** books live in `catalog/books.yaml` (quotes must be copied exactly from the
book); author voices live in `voices/`; music goes in `assets/music/` (licensed tracks only).
Sakura journals are added automatically from `data/`.

**Tests:** `pip install -r requirements.txt && pytest` (needs ffmpeg and poppler installed).
