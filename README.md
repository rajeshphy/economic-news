# Economy Brief

Daily English economy and markets brief for India-first stock-market awareness.

The project collects configurable RSS feeds, filters for fresh market-moving items, groups duplicates, scores stories before the AI call, asks Gemini for a concise digest, and writes a Jekyll Markdown post under `docs/_posts/`.

## Output

- `India Markets`: RBI, inflation, GDP, rupee, SEBI/NSE/BSE, earnings, FII/DII, sector policy
- `Global Cues`: Fed, US markets, crude oil, dollar index, bond yields, geopolitics when relevant to India
- The final post lists at most five points total. If there are not enough worthwhile stories, it shows fewer.
- This is for market awareness only. It does not generate buy/sell advice.
- Each point keeps source chips that link back to the supporting article/feed item.

## Local Run

Create `.env` locally:

```bash
ECONOMIC_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
```

Generate:

```bash
./run.sh generate
```

Run without Gemini:

```bash
./run.sh no-ai
```

Preview locally:

```bash
./run.sh serve
```

## Sources

Edit:

```text
config/sources.yml
```

Add a source under `india` or `world`:

```yml
- name: Example Economy Source
  type: rss
  weight: 3
  url: "https://example.com/rss.xml"
```

Before Gemini runs, the script filters old and irrelevant items, removes excluded topics, groups similar headlines, scores each group, and sends only the top `max_groups_per_section` groups per section.

## GitHub Deployment

1. Push this folder as the root of a repo named `economic-news`.
2. Add a GitHub Actions repository secret:

```text
ECONOMIC_API_KEY
```

3. In GitHub Pages settings, set source to `GitHub Actions`.

The site is configured for:

```text
/economic-news
```

## Schedule

The workflow runs at:

- 06:00 IST
- 14:00 IST
- 20:00 IST

Each successful run commits the generated post into `docs/_posts/` and deploys GitHub Pages.
