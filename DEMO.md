# Demo guide

A 3–4 minute video walkthrough of Lastenheft, designed to land in a recruiter's inbox or be embedded in the README.

## Recording tips

- Use OBS Studio (free) or Windows + G (game bar) for screen capture.
- 1080p, 30 fps, mp4.
- Quiet background — no music. Voiceover or captions only.
- Keep total length ≤ 4 min. Recruiters skim.

---

## Script (~3 min 30 sec)

### 0:00 — 0:20 / The hook

**Slide / first frame:** GitHub README page on screen.
**Voiceover:**
> "This is Lastenheft. Sovereign multimodal RAG over German industrial documentation —
> Siemens, Bosch, TRUMPF, KUKA, Festo. Built in five days as a portfolio piece for
> Mittelstand AI roles."

### 0:20 — 0:50 / The problem

**Show:** README "Why this exists" section. Highlight the four bullets.
**Voiceover:**
> "German industrial Mittelstand can't send their IP to OpenAI. They need AI on their
> technical PDFs — diagrams, datasheets, drawings — but every tool either OCRs and
> loses the structure, or violates EU AI Act compliance. Lastenheft addresses both."

### 0:50 — 1:40 / The demo

**Show:** http://localhost:3000 with the sidebar history visible.
**Voiceover:**
> "I'll ask a real engineering question."

**Type the query (already as an example button):**
> *What is the maximum sheet thickness for stainless steel on the TruLaser 2030 fiber?*

**Click Ask. Voiceover continues over the agent trace appearing live:**
> "The multi-agent flow: planner decomposes, retriever runs ColPali multimodal
> ANN over 909 pages, the BGE LoRA reranker scores the top 5, the validator
> checks coverage, the synthesizer writes the answer with citations."

**When answer renders:** highlight the [1] citation pill, click it to scroll to source.
> "Every fact cites a source page. Sovereignty mode is local-only here — Qwen3 4B
> ran the whole thing on-prem at zero cost."

### 1:40 — 2:10 / The German angle

**Click the second example button (the German query about DSBC).**
> "Same pipeline in German. The reranker was fine-tuned on synthetic DE + EN
> technical queries, so it handles both languages natively."

### 2:10 — 2:40 / Compliance

**Click "Compliance" in the nav.**
**Voiceover:**
> "EU AI Act compliance designed in, not bolted on. Article 6 risk classification
> is seeded in the database on init. Article 13 transparency obligations are
> persisted to audit_events — every agent node writes a row with provider, model,
> token counts, cost, latency."

**Scroll down to the audit log table; point at one row.**
> "Real audit trail, queryable, paginated, GDPR Art. 17 deletable per-query
> from the sidebar."

### 2:40 — 3:15 / The numbers

**Switch to README, scroll to eval results table.**
**Voiceover:**
> "Reproducible eval over 108 held-out synthetic queries on 909 corpus pages.
> ColPali baseline: 0.34 MRR. Off-the-shelf BGE reranker: 0.71. LoRA fine-tuned
> reranker: 0.76 MRR, 70 percent Hit at 1 — that's +8 points over off-the-shelf
> from a fine-tune on synthetic data. Code, training script, and synth dataset
> all in the repo."

### 3:15 — 3:30 / Close

**Show README top.**
**Voiceover:**
> "Built end to end — Postgres, ColPali, LangGraph, Next.js. Repo on GitHub at
> Ekansh1605/Lastenheft. Open to AI Engineer roles in Bonn or remote across the
> German Mittelstand."

---

## Screenshots to capture

Save to `web/public/screenshots/` and embed in README under a `## Screenshots` section.

1. **chat-empty.png** — Home page on first load: sidebar, example query buttons, sovereignty toggle visible.
2. **chat-trace.png** — Mid-query: agent trace timeline with the in-flight pulse on one node.
3. **chat-answer.png** — Completed query: answer with [1][2] citations + citation cards below.
4. **sidebar-history.png** — Sidebar with 3-4 past queries.
5. **compliance.png** — `/compliance` page showing risk classifications + populated audit table.
6. **mobile.png** — Chrome devtools iPhone view showing collapsed sidebar drawer.

---

## After recording

1. Upload the video to YouTube as **unlisted** (not public, not private — shareable via link).
2. Add to README right under the headline:
   ```markdown
   ## 📺 [Watch the 3-minute demo](https://youtu.be/YOUR_VIDEO_ID)
   ```
3. Embed thumbnail with link:
   ```markdown
   [![Lastenheft demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/maxresdefault.jpg)](https://youtu.be/YOUR_VIDEO_ID)
   ```
