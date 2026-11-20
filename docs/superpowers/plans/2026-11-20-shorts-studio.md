# Hanako Shorts Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a password-protected "Shorts Studio" page to the existing Streamlit app. It turns a catalog book into a ready-to-post 1080×1920 MP4 plus per-platform post text, in the author's voice.

**Architecture:** A plain Python package `shorts/` (catalog → script → guardrail → voice → visuals → captions → ffmpeg render → zip) with every external service behind a small Protocol. Fakes make the whole pipeline testable offline. A two-stage run: stage 1 writes the script and post text (cheap) for review and editing; stage 2 renders (the paid steps). A Streamlit multipage file drives it, and `app.py` (the journal generator) stays untouched.

**Tech Stack:** Python 3.11+ (container has 3.13), Streamlit ≥1.37, `anthropic` SDK (`messages.parse` + Pydantic v2), `requests` (ElevenLabs + OpenAI images REST), Pillow, PyYAML, ffmpeg/ffprobe via subprocess (zoompan + libass), pytest.

**Spec:** `docs/superpowers/specs/2026-11-20-shorts-studio-design.md` and `docs/superpowers/specs/2026-11-20-starting-catalog-draft.md` (approved catalog content).

## Global Constraints

- Output video: H.264/AAC MP4, **1080×1920, 30 fps, under 60 s** (target 20–45 s).
- Caption/text safe zone: nothing in the top **250 px** or bottom **400 px**. Keep **≥120 px** clear on the right for platform icons, and ≥60 px on the left.
- All posting is from the single **Hanako Design & Media** account. The end card reads `Link in bio · <Author> · Hanako Design & Media`.
- Author name is spelled **Ren Hawthorne**.
- Secrets come from `st.secrets` or env vars only: `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `OPENAI_API_KEY` (optional), `SHORTS_PASSWORD`, `SHORTS_DAILY_CAP` (default 10), `SHORTS_CLAUDE_MODEL` (default `claude-opus-5-5`). Never commit them.
- Never invent book facts: script prompts may use only catalog fields; quotes appear verbatim. Guardrail flags anything not supported by the book entry or listed in `do_not_say`.
- Fiction gets #BookTok tags. Journals and coloring books never do (enforced in formats + hashtag merge).
- `post.md` always ends with the AI-disclosure reminder line: `Reminder: turn on the platform's "AI-generated content" label (AI voice/images used).`
- `app.py` and `master_publisher.py` behaviour is unchanged.
- Generated output goes to `output/` (git-ignored). No music file is ever downloaded or invented.

## Review Focus

1. **Script too long once voiced:** TTS audio over 58 s must not produce an over-limit video. The pipeline speeds the voice up to 1.12× atempo if that's enough, otherwise fails with a clear "script too long — shorten it" message. (Test in Task 8.)
2. **Non-ASCII and special characters** (`Èṣù`, `Ọṣun`, curly quotes, `{`, `\`, commas) must render in captions and cards and must not break the ASS file. (Test in Task 5.)
3. **Missing keys:** with no `ANTHROPIC_API_KEY` or `ELEVENLABS_API_KEY`, the page shows which key is missing and disables the matching button. It never shows a traceback, and it never renders a silent video. (Tests in Tasks 3 and 9.)
4. **Model refusal or invalid structured output** surfaces as a readable `ScriptError` in the UI and is not retried endlessly. One retry happens on a validation error. (Test in Task 4.)
5. **Odd image sizes** (a 1600×2560 cover, a 1024×1536 generated image, a tiny image) always fill 1080×1920 without distortion (blurred-fill background). (Test in Task 6.)

---

## File Structure

```
shorts/
  __init__.py
  models.py          # Pydantic models: Book, VoiceProfile, Format, Scene, PostText, Script, WordTiming
  catalog.py         # load_catalog(); Sakura CSV auto-entries
  voices.py          # load_voices()
  formats.py         # FORMATS registry, formats_for(book_type)
  settings.py        # Settings.from_env(), missing keys, DailyCap
  providers/
    __init__.py
    base.py          # Protocols: LLM, TTS, ImageGen + TTSResult
    fakes.py         # FakeLLM, FakeTTS, FakeImageGen
    anthropic_llm.py # AnthropicLLM
    elevenlabs_tts.py
    openai_images.py
    cover_only.py    # CoverOnlyImages (no key needed)
  script.py          # build_prompt(), write_scripts(), check_script()
  captions.py        # group_words(), write_ass()
  cards.py           # fit_9x16(), text_card(), end_card()
  render.py          # render_video()
  package.py         # post_markdown(), make_zip()
  pipeline.py        # stage1_scripts(), stage2_render()
pages/1_Shorts_Studio.py
catalog/books.yaml
voices/{ren_hawthorne,aris_thorne,julian_thorne,elias_thorne,hanako}.yaml
assets/covers/  (exists)   assets/music/README.md   assets/fonts/ (system DejaVu via packages.txt)
packages.txt  requirements.txt (modify)  .gitignore  README.md (modify)
tests/...      (one test file per module, plus tests/conftest.py)
```

---

### Task 1: Models, catalog and voice data

**Files:**
- Create: `shorts/__init__.py`, `shorts/models.py`, `shorts/catalog.py`, `shorts/voices.py`, `catalog/books.yaml`, `voices/*.yaml` (5 files), `tests/conftest.py`, `tests/test_catalog.py`, `.gitignore`
- Modify: `requirements.txt` (add `anthropic>=1.0`, `pydantic>=2.7`, `PyYAML>=6.0`, `Pillow>=10.0`, `requests>=2.31`, `pytest>=8`)

**Interfaces:**
- Produces (in `shorts/models.py`, all Pydantic `BaseModel`):
  - `BookType = Literal["fiction","nonfiction","devotional","journal","coloring"]`
  - `Book(id: str, title: str, subtitle: str = "", series: str = "", author: str, voice: str, book_type: BookType, amazon_url: str = "", blurb: str, tropes: list[str], quotes: list[str], do_not_say: list[str] = [], hashtags: list[str] = [], cover: str, page_images: list[str] = [], source_pdf: str = "")`
  - `VoiceProfile(id: str, display_name: str, persona: str, tone: str, use_words: list[str], avoid_words: list[str], signature_phrases: list[str], sign_off: str, elevenlabs_voice_id: str = "", palette: list[str], font: str, music_mood: str, default_hashtags: list[str])`
  - `WordTiming(word: str, start: float, end: float)`
- Produces: `load_catalog(path: Path = Path("catalog/books.yaml"), data_dir: Path = Path("data")) -> dict[str, Book]` and `load_voices(dir: Path = Path("voices")) -> dict[str, VoiceProfile]`

- [ ] **Step 1: Write failing tests** in `tests/test_catalog.py`:
  - `test_loads_two_ren_books`: the keys include `"the_ledger"` and `"the_ones_nobody_came_for"`; both have `author == "Ren Hawthorne"`, `voice == "ren_hawthorne"` and `book_type == "fiction"`; `catalog["the_ledger"].amazon_url == "https://a.co/d/0dXjLJ2d"`; `catalog["the_ones_nobody_came_for"].amazon_url == "https://a.co/d/0aPWMork"`; each cover path exists.
  - `test_ledger_quotes_verbatim`: `"Not superstition. Bookkeeping." in catalog["the_ledger"].quotes`.
  - `test_sakura_auto_entries`: `catalog["sakura_calm"]` has `book_type == "journal"`, `voice == "hanako"`, `len(quotes) == 30`, the first quote is `"What does 'peace' feel like in your body right now?"`, and no hashtag contains `BookTok`.
  - `test_all_voices_load`: `set(load_voices()) == {"ren_hawthorne","aris_thorne","julian_thorne","elias_thorne","hanako"}` and every book's `voice` is in it.
  - `test_unknown_voice_rejected`: a tmp YAML with `voice: nobody` makes `load_catalog` raise `ValueError` that names the book id.
- [ ] **Step 2: Run** `pytest tests/test_catalog.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Write the data.**
  - `catalog/books.yaml` copies the approved draft's fields exactly: blurbs, tropes, quotes, do_not_say and hashtags. Covers are `assets/covers/the_ledger.jpg` and `assets/covers/the_ones_nobody_came_for.jpg`.
  - Voice YAMLs are starter drafts. Ren: literary, understated, wry, short declaratives, no exclamation marks, avoid "buckle up/unputdownable/game-changer", palette from the covers (indigo `#2B2560`, amber `#F2A93B`, dusk blue `#3E5A6B`, cream `#F4EAD5`), font `DejaVuSerif-Bold`, music mood `quiet-piano`. Hanako: calm, invitational, journaling tags. Elias, Aris and Julian follow the spec §2 one-liners. Leave `elevenlabs_voice_id` empty.
  - Add `output/`, `.streamlit/secrets.toml` and `__pycache__/` to `.gitignore`.
- [ ] **Step 4: Implement** `load_catalog` (YAML list → `Book`, then add one journal `Book` per `data/sakura_*_prompts.csv`: id from the file stem minus `_prompts`, title `Sakura <Topic> Journal`, author `Hanako Design & Media`, cover `assets/covers/sakura.jpg` if it exists, else `""`, blurb `A 30-day guided journal from the Sakura Series.`, hashtags `#JournalPrompts #Journaling #SelfCare #GuidedJournal #HanakoDesignAndMedia`). It validates `voice` against `load_voices()`. Also implement `load_voices`.
- [ ] **Step 5: Run** `pytest tests/test_catalog.py -v`. Expected: PASS.
- [ ] **Step 6: Commit** with `git add shorts catalog voices tests requirements.txt .gitignore && git commit -m "feat(shorts): catalog, voices and models"`.

### Task 2: Formats registry

**Files:** Create `shorts/formats.py` and `tests/test_formats.py`.

**Interfaces:**
- Produces: `Format(id: str, name: str, book_types: list[BookType], beats: list[str], target_seconds: tuple[int,int], instructions: str)` in `shorts/models.py`, plus `FORMATS: dict[str, Format]` and `formats_for(book_type: BookType) -> list[Format]` in `shorts/formats.py`.

- [ ] **Step 1: Failing tests:**
  - `test_fiction_formats`: `{f.id for f in formats_for("fiction")} == {"trope_hook","read_this_line","books_that_feel_like"}`.
  - `test_journal_formats`: `{"prompt_of_the_day","flip_through"} == {f.id for f in formats_for("journal")}`.
  - `test_devotional`: `"word_for_today"` is in the result.
  - `test_nonfiction`: `"idea_in_30"` is in the result.
  - `test_all_targets_under_60`: every `target_seconds[1] <= 45` and every `target_seconds[0] >= 20`.
- [ ] **Step 2: Run** and expect FAIL.
- [ ] **Step 3: Implement** the 7 formats from spec §6.2. `beats` are the scene roles in order (e.g. trope_hook: `["hook","trope","trope","trope","cover_reveal","cta"]`), and `instructions` is 2–4 sentences of format direction for the prompt. `read_this_line` also allows `nonfiction` and `devotional`. `flip_through` allows `journal` and `coloring`.
- [ ] **Step 4: Run** and expect PASS. **Step 5: Commit** with `feat(shorts): short formats`.

### Task 3: Settings, provider protocols, fakes, daily cap

**Files:** Create `shorts/settings.py`, `shorts/providers/__init__.py`, `shorts/providers/base.py`, `shorts/providers/fakes.py`, `tests/test_settings.py`.

**Interfaces:**
- Produces (`providers/base.py`):
  - `class LLM(Protocol): def parse(self, system: str, user: str, schema: type[T]) -> T`
  - `class TTS(Protocol): def synthesize(self, text: str, voice_id: str, out_path: Path) -> TTSResult`
  - `TTSResult(audio_path: Path, words: list[WordTiming], duration: float)` (dataclass)
  - `class ImageGen(Protocol): def generate(self, prompt: str, out_path: Path, book: Book) -> Path`
- Produces (`fakes.py`):
  - `FakeLLM(responses: list[BaseModel])` returns them in order and records `.calls`.
  - `FakeTTS(words_per_sec: float = 2.5)` writes a silent AAC `.m4a` of the computed length via ffmpeg `anullsrc` and evenly spaced `WordTiming`s.
  - `FakeImageGen(color="#2B2560")` writes a solid 1024×1536 PNG.
- Produces (`settings.py`): `Settings(anthropic_key: str|None, elevenlabs_key: str|None, openai_key: str|None, password: str|None, daily_cap: int, claude_model: str, output_dir: Path)` with `Settings.from_sources(env: Mapping[str,str], secrets: Mapping[str,str] | None) -> Settings` (secrets win over env), `missing_for_script() -> list[str]` and `missing_for_render() -> list[str]`; plus `DailyCap(path: Path, limit: int)` with `remaining(today: date) -> int` and `use(today: date) -> None` (raises `CapReached`).

- [ ] **Step 1: Failing tests:**
  - `test_defaults`: with empty env, `claude_model == "claude-opus-5-5"`, `daily_cap == 10`, `password is None`.
  - `test_secrets_override_env`.
  - `test_missing_keys`: with no keys, `missing_for_script() == ["ANTHROPIC_API_KEY"]` and `missing_for_render() == ["ELEVENLABS_API_KEY"]`; `OPENAI_API_KEY` is never listed as missing.
  - `test_daily_cap`: with a limit of 2, `use` works twice and the third call raises `CapReached`; the next day `remaining == 2`.
  - `test_fake_tts_duration`: 10 words at 2.5 w/s gives `duration ≈ 4.0 ± 0.1` (checked with ffprobe), `len(words) == 10`, and timings strictly increasing.
- [ ] **Step 2: Run** and expect FAIL. **Step 3: Implement.** DailyCap stores `{"date": "...", "count": n}` JSON in `output/.daily_cap.json`. **Step 4: Run** and expect PASS. **Step 5: Commit** with `feat(shorts): settings, provider protocols and fakes`.

### Task 4: Script writer and guardrail

**Files:** Create `shorts/script.py` and `tests/test_script.py`. Modify `shorts/models.py`.

**Interfaces:**
- Produces (models):
  - `Scene(role: str, narration: str, on_screen_text: str, image_prompt: str, seconds: float)`
  - `PostText(tiktok_caption: str, instagram_caption: str, youtube_title: str, youtube_description: str, hashtags: list[str])`
  - `Script(book_id: str, format_id: str, hook: str, scenes: list[Scene], cta: str, post: PostText)`
  - `GuardrailReport(ok: bool, flags: list[str], revised: Script | None)`
- Produces (`script.py`):
  - `build_prompt(book: Book, voice: VoiceProfile, fmt: Format, extra: str = "") -> tuple[str, str]` returns `(system, user)`
  - `write_scripts(llm: LLM, book, voice, fmt, n: int = 1, extra: str = "") -> list[Script]`
  - `check_script(llm: LLM, script: Script, book: Book, voice: VoiceProfile) -> GuardrailReport`
  - `merge_hashtags(script: Script, book: Book, voice: VoiceProfile) -> list[str]`
  - `class ScriptError(Exception)`

- [ ] **Step 1: Failing tests (using FakeLLM):**
  - `test_prompt_contains_only_catalog_facts`: the user prompt contains the blurb, every quote and every `do_not_say` item (under a "Never mention" heading), and contains `"Hanako Design & Media"` and `"Link in bio"`; the system prompt contains `voice.tone` and every `avoid_words` entry.
  - `test_write_scripts_n`: with `n=2`, FakeLLM is called twice, 2 scripts come back, `book_id`/`format_id` are set from the inputs (not trusted from the model), and the second call's prompt asks for a different angle than the first hook.
  - `test_validation_retry_then_error`: when FakeLLM raises `pydantic.ValidationError` twice, `ScriptError("...could not produce a valid script...")` is raised after exactly 2 calls.
  - `test_refusal_is_script_error`: when FakeLLM raises `providers.base.Refusal("policy")`, the result is `ScriptError` whose message contains `"declined"`.
  - `test_guardrail_flags_unlisted_quote`: when a script's on-screen text quotes a line not in `book.quotes`, `check_script` includes a flag mentioning that line. This is a deterministic local check that runs before the LLM pass: any text in quotation marks must be a substring of some catalog quote.
  - `test_hashtags_no_booktok_for_journals` and `test_hashtags_deduped_max_8`.
  - `test_total_seconds_within_format`: `write_scripts` rescales scene `seconds` so the sum sits inside `fmt.target_seconds`.
- [ ] **Step 2: Run** and expect FAIL.
- [ ] **Step 3: Implement.** Add `class Refusal(Exception)` to `providers/base.py`. The guardrail LLM pass asks the model to compare the script against the book entry and voice, and to return a `GuardrailReport`. The local quote check's flags are merged in. `ok` is False if there are any flags.
- [ ] **Step 4: Run** and expect PASS. **Step 5: Commit** with `feat(shorts): script writer and guardrail`.

### Task 5: Captions and cards

**Files:** Create `shorts/captions.py`, `shorts/cards.py`, `tests/test_captions.py` and `tests/test_cards.py`.

**Interfaces:**
- `group_words(words: list[WordTiming], max_words: int = 3, max_chars: int = 18) -> list[WordTiming]` returns phrase-level timings.
- `write_ass(phrases: list[WordTiming], out: Path, font: str, primary: str, outline: str) -> Path` uses PlayRes 1080×1920, Alignment 2, MarginV 520, MarginL 60, MarginR 120, font size 78, bold, 6 px outline. Each phrase is one Dialogue line, and the active phrase pops via `{\fscx110\fscy110\t(0,120,\fscx100\fscy100)}`.
- `fit_9x16(src: Path, out: Path) -> Path` produces a 1080×1920 image: a blurred, darkened cover-fill background with the source contained and centred.
- `text_card(text: str, base: Path, out: Path, font_path: Path, color: str) -> Path` draws wrapped text centred in the safe zone, with a translucent panel behind it.
- `end_card(book: Book, voice: VoiceProfile, out: Path) -> Path` places the cover at 60% width plus the line `Link in bio · {author} · Hanako Design & Media`.
- `font_path(name: str) -> Path` resolves `DejaVuSerif-Bold` / `DejaVuSans-Bold` from `/usr/share/fonts/truetype/dejavu/`.

- [ ] **Step 1: Failing tests:**
  - `test_group_words`: 7 words become 3 phrases, phrase start equals its first word's start and end equals its last word's end.
  - `test_ass_escapes`: phrase text `Èṣù {owes} a\debt, really` keeps `Èṣù` in UTF-8, writes `{` and `}` as `\{` `\}`, writes the backslash as `\\`, and makes the file parse in ffmpeg (`ffmpeg -f lavfi -i color=c=black:s=1080x1920:d=1 -vf ass=<file> -f null -` exits 0).
  - `test_ass_safe_zone`: the file contains `MarginV` 520 and `PlayResY: 1920`.
  - `test_fit_9x16_sizes`: inputs of 1600×2560, 1024×1536 and 200×100 all give a 1080×1920 output.
  - `test_text_card_inside_safe_zone`: drawing a long string on a pure black base leaves rows 0–249 and 1520–1919 unchanged apart from the panel's alpha. In practice, assert the bounding box of non-black pixels is within y∈[250,1520] and x∈[60,960].
  - `test_end_card_text`: the end card is 1080×1920, and `end_card` returns the path with the expected line recorded in an `end_card.txt` sidecar.
- [ ] **Step 2: Run** and expect FAIL. **Step 3: Implement.** **Step 4: Run** and expect PASS. **Step 5: Commit** with `feat(shorts): captions and cards`.

### Task 6: Video render

**Files:** Create `shorts/render.py` and `tests/test_render.py`.

**Interfaces:**
- `RenderScene(image: Path, seconds: float)` (dataclass)
- `render_video(scenes: list[RenderScene], voice_audio: Path, captions_ass: Path, out: Path, music: Path | None = None, end_card: Path | None = None, end_seconds: float = 2.5) -> Path`
- `probe(path: Path) -> dict` returns `{"width","height","fps","duration","has_audio"}` from ffprobe JSON.

- [ ] **Step 1: Failing tests** (fixtures from Task 3 fakes and Task 5 cards):
  - `test_render_specs`: 3 scenes of 3 s plus a 2.5 s end card give `probe(out)` with `width == 1080`, `height == 1920`, `fps == 30`, `duration` within ±0.3 of 11.5, and `has_audio`.
  - `test_render_with_music_ducked`: with music (generated sine via lavfi in the fixture), the output has one audio stream and a duration that still matches the visuals (music is trimmed, not extended).
  - `test_render_odd_image`: a 200×100 PNG scene image renders without error (render calls `fit_9x16` internally on each image).
- [ ] **Step 2: Run** and expect FAIL.
- [ ] **Step 3: Implement** with a single ffmpeg call. Each scene image is a looped input → `scale=1188:2112,zoompan=z='min(zoom+0.0008,1.1)':d=<frames>:s=1080x1920:fps=30` (alternate the zoom-in and pan direction per scene) → `xfade=fade:0.4` between scenes → `ass=` captions over the scene segment only → concat the end card. Audio is the voice plus music at `volume=0.12` with `sidechaincompress` ducking, then `apad` and `-shortest` to the video length. Output uses `-c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 21 -c:a aac -b:a 160k -movflags +faststart`. On a non-zero exit, raise `RenderError` with the last 20 stderr lines.
- [ ] **Step 4: Run** and expect PASS. **Step 5: Commit** with `feat(shorts): ffmpeg renderer`.

### Task 7: Real providers

**Files:** Create `shorts/providers/anthropic_llm.py`, `elevenlabs_tts.py`, `openai_images.py` and `cover_only.py`, plus `tests/test_providers.py`.

**Interfaces:**
- `AnthropicLLM(api_key: str, model: str)` implements `LLM.parse` via `client.messages.parse(model=..., max_tokens=16000, system=..., messages=[...], output_format=schema)` and returns `response.parsed_output`. It raises `Refusal(category)` when `stop_reason == "refusal"`. If the installed SDK supports it on `parse`, it sends server-side fallbacks (`betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"` via `client.beta.messages.parse`). If not, it uses plain `messages.parse` and adds a code comment.
- `ElevenLabsTTS(api_key: str, model_id: str = "eleven_multilingual_v2")` POSTs to `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps` with header `xi-api-key`. It decodes `audio_base64` to mp3 and builds `WordTiming`s from `alignment.characters` / `character_start_times_seconds` / `character_end_times_seconds` by splitting on whitespace. Duration comes from `probe`.
- `OpenAIImages(api_key: str, model: str = "gpt-image-1")` POSTs to `https://api.openai.com/v1/images/generations` with `size: "1024x1536"`, decodes `data[0].b64_json` and writes a PNG.
- `CoverOnlyImages()` makes a deterministic variant per call index from `book.cover`: a crop region from a fixed list of 6 (top third, centre, bottom third, left/right detail, full), a gradient tint from the voice palette, and a light blur. It ignores the prompt.
- `make_providers(settings: Settings) -> tuple[LLM | None, TTS | None, ImageGen]` returns None for a provider whose key is missing, and `CoverOnlyImages` when there's no OpenAI key.

- [ ] **Step 1: Failing tests** (no network; monkeypatch `requests.post` and the anthropic client):
  - `test_elevenlabs_word_timings`: the fake alignment for `"Not superstition. Bookkeeping."` gives 3 words with the starts of their first characters.
  - `test_elevenlabs_http_error`: a 401 raises `ProviderError` containing `"ElevenLabs"` and `"401"`, with the key never in the message.
  - `test_openai_images_writes_png`.
  - `test_cover_only_distinct`: 3 calls give 3 different images, each 1024×1536 or larger.
  - `test_anthropic_refusal`: a stubbed response with `stop_reason="refusal"` raises `Refusal`.
  - `test_make_providers_without_keys`: the result is `(None, None, CoverOnlyImages)`.
- [ ] **Step 2: Run** and expect FAIL. **Step 3: Implement.** **Step 4: Run** and expect PASS. **Step 5: Commit** with `feat(shorts): real providers`.

### Task 8: Package and pipeline

**Files:** Create `shorts/package.py`, `shorts/pipeline.py` and `tests/test_pipeline.py`.

**Interfaces:**
- `post_markdown(script: Script, book: Book) -> str` has sections `## TikTok`, `## Instagram`, `## YouTube Shorts` (title, description with the `amazon_url`, tags) and ends with the Global Constraints reminder line.
- `make_zip(run_dir: Path) -> Path` packages `short.mp4`, `post.md`, `script.json` and `images/*`.
- `stage1_scripts(book_id: str, format_id: str, n: int, extra: str, llm: LLM, catalog, voices) -> list[tuple[Script, GuardrailReport]]`
- `stage2_render(script: Script, tts: TTS, images: ImageGen, catalog, voices, settings: Settings, music_dir: Path = Path("assets/music")) -> RunResult`, where `RunResult(run_dir: Path, video: Path, zip: Path, post_md: str, warnings: list[str])`.
- `run_dir` is `output/<YYYYMMDD-HHMMSS>-<book_id>-<format_id>/`. Images are cached by `sha1(prompt)` inside it, and the voice audio is cached by `sha1(narration)`. A re-render of an edited script only redoes the changed parts.
- `MAX_AUDIO = 58.0`. If `duration > MAX_AUDIO`, the audio is re-timed with `atempo` when `duration / MAX_AUDIO <= 1.12`, scaling the word timings. Otherwise it raises `ScriptError("Script too long when spoken (NN s). Shorten it to under 58 s.")`.
- Music: pick a random file in `music_dir` whose name contains `voice.music_mood`, else any `.mp3`/`.m4a`, else none, with the warning `"No music in assets/music — rendered voice only."`
- Scene durations are stretched proportionally so the scenes cover the voice audio exactly.
- `flip_through` scenes use real pages, not generated images. A `sakura_*` journal makes a PDF with `master_publisher.run_master_publisher(csv, tmp.pdf)` and converts pages 1, 2, 3, 12 and 22 with `pdftoppm -png -r 150`. Other books use `book.page_images`. If neither is available, it raises `ScriptError("Flip-Through needs page images for this book.")`.

- [ ] **Step 1: Failing tests** (fakes end to end):
  - `test_end_to_end_fake`: `stage1_scripts` → `stage2_render` for `the_ledger` + `trope_hook` gives an existing zip containing exactly `short.mp4`, `post.md`, `script.json` and at least one `images/` entry; `probe(video)` is 1080×1920 with duration < 60; `post_md` contains `https://a.co/d/0dXjLJ2d` and the reminder line.
  - `test_too_long_errors`: FakeTTS with 0.5 words/s on a 40-word script raises `ScriptError` matching `"too long"`.
  - `test_slightly_long_is_sped_up`: audio of 62 s ends up ≤ 58.5 s and words are rescaled.
  - `test_no_music_warning`: an empty music dir puts the warning in `RunResult.warnings`.
  - `test_flip_through_uses_journal_pages`: for `sakura_calm` + `flip_through`, FakeImageGen is never called and the zip's `images/` has 5 PNGs.
  - `test_rerender_uses_cache`: rendering the same script twice in the same run dir calls `FakeImageGen` and `FakeTTS` only once for each unchanged scene and narration.
- [ ] **Step 2: Run** and expect FAIL. **Step 3: Implement.** **Step 4: Run** and expect PASS. **Step 5: Commit** with `feat(shorts): pipeline and packaging`.

### Task 9: Streamlit Shorts Studio page and deployment files

**Files:**
- Create: `pages/1_Shorts_Studio.py`, `packages.txt` (`ffmpeg`, `fonts-dejavu-core`, `poppler-utils`), `assets/music/README.md` (licence rule: only tracks you hold a licence for; name files with the mood, e.g. `quiet-piano_01.mp3`), `.streamlit/secrets.toml.example`, `tests/test_page.py`
- Modify: `README.md` (add a "Shorts Studio" section covering secrets, keys and costs, and that posting is manual with the AI label switched on)

**Interfaces:**
- Consumes everything above.
- Page flow:
  1. Password gate (`st.text_input(type="password")` compared with `hmac.compare_digest` against `settings.password`). If `password` is None, show "Set SHORTS_PASSWORD in secrets to use this page" and stop.
  2. Show the missing-key notices.
  3. Book select showing `title — author`.
  4. Format select from `formats_for`.
  5. Variants 1–3, extra direction, and a "Skip review" checkbox.
  6. **Write scripts** (disabled if `missing_for_script()`) runs `stage1`.
  7. For each variant, an expander shows the hook and an editable table of scenes (`st.data_editor` on narration, on-screen text and image prompt) plus editable post text and guardrail flags in `st.warning`.
  8. **Approve & Render** (disabled if `missing_for_render()` or `DailyCap.remaining == 0`) runs `stage2` with `st.status` steps, then shows `st.video`, the post text in `st.code` blocks (one per platform for easy copying) and `st.download_button` for the zip.
  9. Errors (`ScriptError`, `ProviderError`, `RenderError`, `CapReached`) appear in `st.error` with a plain message, never a traceback.
- Session state keys: `scripts`, `reports` and `results`.

- [ ] **Step 1: Failing tests** with `streamlit.testing.v1.AppTest.from_file("pages/1_Shorts_Studio.py")`:
  - `test_locked_without_password_secret`: the page shows the "Set SHORTS_PASSWORD" text and has no selectbox.
  - `test_wrong_password_stays_locked`.
  - `test_missing_keys_disable_buttons`: with the correct password and no API keys, both buttons are disabled and the info text names `ANTHROPIC_API_KEY`.
  - `test_fake_flow`: with env `SHORTS_FAKE_PROVIDERS=1` (makes `make_providers` return fakes; this is test-only and documented as such), selecting The Ledger + Trope Hook → Write → Approve & Render shows a download button. Mark it `@pytest.mark.slow`.
  - `test_journal_app_untouched`: `AppTest.from_file("app.py").run()` has no exception.
- [ ] **Step 2: Run** and expect FAIL. **Step 3: Implement.** Add the `SHORTS_FAKE_PROVIDERS` branch in `make_providers`. **Step 4: Run** `pytest -v` (full suite) and expect everything to PASS.
- [ ] **Step 5: Manual check:** run `streamlit run app.py --server.headless true`, open the Shorts Studio page in Playwright at a phone viewport (390×844) with `SHORTS_FAKE_PROVIDERS=1`, generate one short and screenshot the page and a frame from the MP4 (`ffmpeg -ss 3 -frames:v 1`). Confirm the captions sit inside the safe zone and are readable.
- [ ] **Step 6: Commit** with `feat(shorts): Streamlit Shorts Studio page`.

---

## Owner steps (not code, after the merge)

1. In Streamlit Cloud → App settings → Secrets, add `SHORTS_PASSWORD`, `ANTHROPIC_API_KEY` and, later, `ELEVENLABS_API_KEY` (and optionally `OPENAI_API_KEY`).
2. After signing up for ElevenLabs, pick or design a voice for Ren and paste its ID into `voices/ren_hawthorne.yaml` (`elevenlabs_voice_id`).
3. Drop licensed music tracks into `assets/music/`.
