# Economy Brief `src` split

This folder is the split version of the original monolithic `src/main.py`.

## Files

- `main.py` — entry point; loads config, collects news, calls Gemini/fallback, writes the post.
- `common.py` — shared constants, paths, `NewsItem`, YAML/env helpers.
- `fetch.py` — RSS/Atom fetching and conversion into `NewsItem` objects.
- `directlink.py` — opens the RSS/indirect link and stores only the final landed URL.
- `filter.py` — relevance filtering, freshness, dedupe, grouping, scoring.
- `ai.py` — Gemini prompt, quota handling, and fallback summary generation.
- `markdown.py` — front matter, source chips, HTML/Markdown output.

## Direct-link rule

The important change is in `fetch.py` and `directlink.py`.

`fetch.py` sends each RSS link to `resolve_direct_link()`.

`directlink.py` opens the indirect link with a browser-like GET request and returns only `response.geturl()`, the final URL reached after redirects. It does not guess article links from page HTML and it does not use random image/favicon links.

If a final URL cannot be resolved, the item is skipped. This prevents RSS wrapper links from appearing in generated source links.
