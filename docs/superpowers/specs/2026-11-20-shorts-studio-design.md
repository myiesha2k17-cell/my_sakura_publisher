# Shorts Studio — Design

**Date:** 2026-11-20
**Status:** Draft, awaiting owner approval
**Repo:** `my_sakura_publisher`

## 1. Intent and the why

Hanako Design & Media publishes on Amazon KDP under several pen names. The owner wants an
"elite social media publisher" agent. It turns each published book into **finished,
ready-to-post vertical short videos** for YouTube Shorts, TikTok and Instagram Reels. Each
video is written and voiced in the persona of the book's author.

Why: to **build the Hanako brand and its author personas, reach the BookTok audience, and
drive organic Amazon sales and reviews**, all without paid ads. A short succeeds when it earns
follows, saves and click-throughs to the book. Views that don't convert are not the goal.

"Finished" means the same as a finished ad from Zeely: the owner downloads the files and
posts them, with no editing app in between.

## 2. Voices (who speaks)

| Voice | Books | Audience / angle |
|---|---|---|
| **Ren Hawthorn** | Creative fiction | Core BookTok: trope hooks, aesthetic moodboards, "books that feel like…", reading strong lines aloud |
| **Aris Thorne** | Tech, sonic branding, creative systems | Creators/builders: "one idea that changed how I…", contrarian takes, mini-lessons |
| **Julian Thorne** | Legacy / curated heritage | Reflective, archival, "what we keep and why" |
| **Elias Thorne** | Inspirational / devotional | Faith & encouragement: verse-style lines, gentle direct address, morning-word format |
| **Hanako Design & Media** (brand voice) | Low-content: Sakura journals, other journals, coloring books | Journaling / wellness / coloring communities: prompt-of-the-day, flip-throughs, "journal with me" |

Each voice has a **voice profile** file. The profile holds the tone, vocabulary to use and
avoid, sentence rhythm, signature phrases, sign-off line, an ElevenLabs voice ID, a colour
palette, fonts, a music mood and a default hashtag set. The owner writes and refines these.
The build ships with drafted starter profiles for all five voices, which the owner then
edits.

Hashtags and formats follow the book type. Fiction gets #BookTok tags. Journals and coloring
books get journaling, wellness and coloring tags instead. Everything is never tagged
#BookTok.

## 3. Goals, non-goals, anti-goals

**Goals**
- One run produces, for each requested short, a 1080×1920 MP4 under 60s that is ready to post. It has:
  - a hook in the first ~2 seconds
  - voiceover in the author's voice
  - burned-in word-timed captions
  - background music
  - the book cover or mockup on screen
  - a branded end card ("Link in bio · <Author> · Hanako Design & Media")
- Post text for each platform: TikTok caption + hashtags; Instagram caption + hashtags;
  YouTube Shorts title + description + tags.
- Runs from a phone browser via the existing Streamlit deployment.
- Several formats per book, so one book can feed many posts over weeks.
- The engine lives in a plain Python package, separate from the UI, so a Claude Code
  skill/agent entry point can be added later without a rewrite.

**Non-goals (v1)**
- Auto-posting to platforms. The owner posts manually or through their own scheduler.
- AI avatar / talking-head presenters. This may come later for Ren or Elias.
- Analytics, performance tracking, A/B testing.
- Long-form YouTube video.

**Anti-goals (failure even if it "works")**
- Generic, AI-sounding copy that could belong to any author. Voice fidelity is the product.
- Mis-tagging (e.g. a coloring book pushed as #BookTok fiction), which reads as spam to the audience.
- Claims about the book that are false: invented plot, fake reviews, fake bestseller badges.
  Hooks may dramatise but must be true to the book.
- Copyrighted music or third-party images.
- Unreadable output on a phone: captions under the platform UI, low contrast, tiny text.

## 4. Constraints

- **Hosting:** Streamlit Community Cloud, as today. ffmpeg comes via `packages.txt`. Render
  time and memory must stay inside its limits (target: one 45s short renders in a few minutes
  at most, one short at a time).
- **Secrets:** API keys come from Streamlit secrets (`st.secrets`) or env vars. They never
  go in the repo.
- **Cost:** the target is under about $1–2 per finished short, all APIs included.
- **Platform safe zones:** captions and key text stay inside the centre-safe area. Avoid
  roughly the top 250px and bottom 400px, and the right-side icon column.
- **AI disclosure:** the post text output reminds the owner to switch on the platform's
  "AI-generated content" label when AI imagery or voice is used.
- **Existing app:** the journal generator in `app.py` / `master_publisher.py` must keep
  working unchanged.

## 5. Approaches considered

1. **Streamlit "Shorts Studio" page + Python engine (chosen).** It fits how the owner
   already uses this repo from a phone: tap and download. The cost is API keys for Anthropic,
   ElevenLabs and an image service, plus a small per-video cost.
2. **Claude Code skill/agent only.** No separate Claude API bill, and more flexible for one-off
   requests. It is not one-tap, and it doesn't fit the phone workflow.
3. **Both at once.** Most flexible, but double the surface to build up front.

**Chosen: 1.** The owner picked it. The engine is built so that option 2 can wrap it later.

Visual approach (also chosen): **faceless "book aesthetic"**. This means the cover/mockup,
mood imagery with slow pan/zoom, bold kinetic text and AI narration. The owner rejected
avatar presenters for v1.

## 6. How it works

### 6.1 Inputs
- **Book catalog** (`catalog/books.yaml` or CSV). Each book lists:
  - id, title, subtitle, author (one of the five voices) and book type (fiction / nonfiction / devotional / journal / coloring)
  - Amazon URL / ASIN
  - one-paragraph blurb, tropes/keywords and target-reader line
  - 3–10 **source excerpts or prompts**: quotable lines, journal prompts, sample pages
  - path to the cover image and optional interior page images
  - an optional "do not say" list (spoilers, claims to avoid)

  For Sakura journals, excerpts can come from the existing `data/*.csv` prompt files
  automatically.
- **Voice profiles** (`voices/<voice>.yaml`), as described in §2.
- **Brand assets** (`assets/`): fonts, logo, end-card template, a small licensed /
  royalty-free music library tagged by mood.

### 6.2 Formats (v1 set)
Each format is a template: a beat structure, length target and prompt instructions.
- **Trope Hook** (fiction): "POV: you want a book where…", followed by trope beats, the cover reveal and the CTA.
- **Read This Line** (any narrative book): hook, then 1–3 excerpt lines in kinetic text over mood imagery, then the CTA.
- **Books That Feel Like…** (fiction): vibes and aesthetic montage, ending on the cover.
- **Word for Today** (Elias/devotional): one encouraging line, a short reflection and the sign-off.
- **Prompt of the Day** (journals): the prompt shown large, "pause and answer this", then the journal reveal.
- **Flip-Through** (journals/coloring): animated pages from the interior PDF or images, plus the CTA.
- **Idea in 30 Seconds** (Aris/Julian nonfiction): a contrarian hook, the idea and one takeaway.

The UI lists only the formats valid for the selected book type.

### 6.3 Pipeline (one short)
1. **Script:** Claude gets the voice profile, book entry, format template and platform
   rules. It returns structured JSON: hook text, scenes (narration line, on-screen text,
   image prompt, duration hint), CTA, and the per-platform post text.
2. **Guardrail check:** a second Claude pass checks the script against the book entry and
   the "do not say" list, and checks the voice against the profile. It revises or flags.
3. **Voiceover:** ElevenLabs uses the author's voice ID and returns audio plus word
   timestamps for captions.
4. **Visuals:** an image model generates one image per scene in the voice's visual style. The
   cover or mockup is always used for the reveal and end card. Images are rendered at or
   cropped to 9:16.
5. **Render:** compose the scenes with Ken Burns motion and transitions, word-timed captions,
   on-screen text, music ducked under the voice, and the end card. Output is an H.264/AAC MP4
   at 1080×1920 and 30fps.
6. **Package:** a zip containing the MP4, `post.md` (TikTok / IG / YouTube text), the script
   JSON and the images used. Download it from the UI.

### 6.4 UI (Streamlit page "Shorts Studio")
```
🌸 Hanako Shorts Studio
[ Book ▾ ]           (shows author + type)
[ Format ▾ ]         (filtered by type)
[ How many variants: 1–3 ]
[ Extra direction (optional) ________ ]
( Generate )
 → progress: script ✓ · voice ✓ · images ✓ · render …
 → video preview · script preview · [Download zip]
```
The journal generator stays as its own page.

### 6.5 Code layout (proposal)
- `shorts/` engine package: `catalog.py`, `voices.py`, `formats/`, `script.py`,
  `voiceover.py`, `visuals.py`, `render.py`, `package.py`, `pipeline.py` (`make_short(book_id,
  format, options) -> output paths`).
- `pages/` Streamlit multipage: the journal generator stays in `app.py`, and Shorts Studio is
  added as a page.
- Each external service sits behind a small interface, so a provider can be swapped (e.g. a
  different TTS or image model) without touching the pipeline. Tests use fake providers.

## 7. Decided by the owner
- Purpose: brand building, BookTok reach, organic sales and reviews.
- Sakura journals and other low-content books speak as Hanako Design & Media, not a pen name.
- Output: finished, ready-to-post videos plus post text ("like a finished Zeely ad").
- Visual style: faceless book-aesthetic, no avatars in v1.
- Build: Streamlit Shorts Studio with a reusable engine.
- **Accounts:** everything posts from the single Hanako Design & Media account on each
  platform. Authors are presented as "a Hanako author", e.g. "Ren Hawthorn's new novel". The
  narration may still use the author's first-person voice for excerpts and reflections. The end
  card and CTA always point to the Hanako link in bio. Hashtags mix brand tags with tags
  suited to the book type.
- **Catalog to start:** the owner's 2 published Amazon books, both Ren Hawthorne fiction:
  *The Ledger* (Adebayo Ledger #1) and *The Ones Nobody Came For* (A Keeper Novel #1). The
  draft entries are in `2026-11-20-starting-catalog-draft.md`, and the covers are in
  `assets/covers/`. Ren's fiction is therefore the v1 focus. The other four voices get starter
  profiles but no books yet.
- **Voice provider:** the owner will sign up for ElevenLabs later. v1 is built and tested
  against the provider interface with a fake TTS. Until a key is added, the app tells the
  owner that voice is not configured and won't render.

## 8. Builder's calls (proposed defaults, owner may override)
- Providers:
  - Anthropic Claude for script and guardrail, using the latest Claude Sonnet model for cost
    with an option to switch to Opus
  - ElevenLabs for voice
  - one image API, chosen at build time for quality, cost and 9:16 support
  - MoviePy + ffmpeg for rendering
- Catalog and voice profiles as YAML in the repo, so the owner can edit them on GitHub from a phone.
- Music: a small bundled royalty-free library. The owner can add tracks.
- Output length targets: 20–45s. YouTube title ≤ 100 chars. Caption lengths kept within each platform's limits.
- Generated output is not committed to git.
- **Access & spend:** the Shorts Studio page sits behind a password stored in Streamlit
  secrets, so a shared link can't run up API bills. A configurable daily cap limits how many
  shorts can be generated.
- **Two-stage run with review:** stage 1 writes the script and runs the guardrail check, which
  is cheap. The owner sees the script and post text, can edit them, and taps **Approve &
  Render**. Stage 2 runs voice, images and render, which are the paid steps. Guardrail flags
  are shown next to the script, and they don't block the owner from approving it. A "skip
  review" toggle runs both stages in one go.
- **Music:** no scraped or uncertain tracks. v1 uses tracks the owner adds to `assets/music/`
  (any licence the owner holds) and can optionally generate a bed with ElevenLabs Music on a
  plan that allows commercial use. If neither is available, the short renders with
  voice only and says so.
- **Durability:** a lost render (phone locks, session drops) means tap again in v1. Each
  stage's output is cached on disk for the session, so a re-render doesn't redo the script.
- **Real book data only:** the builder ships a catalog schema, starter voice profiles and one
  example entry built from the existing Sakura CSVs. The builder never invents blurbs, excerpts
  or claims for real books. The owner supplies those.
- **Flip-Through for Sakura journals** renders pages straight from PDFs made by
  `master_publisher.py`. Other books use uploaded page images.
