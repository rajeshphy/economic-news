from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timedelta, timezone

try:
    from .common import IST, NewsItem, clean_text, config_bool
except ImportError:
    from common import IST, NewsItem, clean_text, config_bool


def configured_keywords(settings: dict, key: str, default: str) -> list[str]:
    raw = settings.get(key, default)
    return [clean_text(keyword).lower() for keyword in str(raw).split(",") if clean_text(keyword)]


def section_keywords(section: str, settings: dict) -> list[str]:
    default_india = "india,indian,nifty,sensex,nse,bse,rbi,sebi,rupee,inflation,gdp,budget,tax,earnings"
    default_world = "federal reserve,fed,us markets,nasdaq,dow,treasury yields,crude oil,brent,global markets,dollar index"
    return configured_keywords(settings, f"{section}_keywords", default_india if section == "india" else default_world)


def domain_topic_keywords(settings: dict) -> list[str]:
    return configured_keywords(
        settings,
        "economics_topic_keywords",
        (
            "market,markets,nifty,sensex,nse,bse,rbi,sebi,rupee,inflation,gdp,"
            "repo rate,monetary policy,budget,tax,gst,earnings,ipo,fii,dii,"
            "bond yield,crude oil,brent,banking,credit,fed,global cues"
        ),
    )


def item_sort_key(item: NewsItem) -> tuple[int, float]:
    if not item.published_at:
        return (0, 0.0)
    return (1, item.published_at.timestamp())


def filter_fresh_items(items: list[NewsItem], settings: dict) -> list[NewsItem]:
    require_today = config_bool(settings.get("require_ist_today"), True)
    allow_unknown_dates = config_bool(settings.get("allow_unknown_dates"), False)
    max_age_hours = int(settings.get("max_age_hours", 30))
    now_ist = datetime.now(IST)
    fresh: list[NewsItem] = []
    for item in items:
        if not item.published_at:
            if allow_unknown_dates:
                fresh.append(item)
            continue
        published_ist = item.published_at.astimezone(IST)
        if require_today:
            if published_ist.date() == now_ist.date():
                fresh.append(item)
            continue
        if now_ist - published_ist <= timedelta(hours=max_age_hours):
            fresh.append(item)
    return sorted(fresh, key=item_sort_key, reverse=True)


def filter_relevant_items(section: str, items: list[NewsItem], settings: dict) -> list[NewsItem]:
    keywords = section_keywords(section, settings)
    topic_keywords = domain_topic_keywords(settings)
    india_anchors = configured_keywords(
        settings,
        "india_anchor_keywords",
        "india,indian,nifty,sensex,nse,bse,rbi,sebi,rupee,gst",
    )
    if not keywords:
        return items
    relevant = []
    for item in items:
        haystack = f"{item.title} {item.source}".lower()
        section_match = any(keyword in haystack for keyword in keywords)
        topic_match = any(keyword in haystack for keyword in topic_keywords)
        if section == "india":
            anchor_match = any(keyword in haystack for keyword in india_anchors)
            if section_match and topic_match and anchor_match:
                relevant.append(item)
            continue
        if section_match or topic_match:
            relevant.append(item)
    return relevant


def filter_excluded_items(items: list[NewsItem], settings: dict) -> list[NewsItem]:
    excluded = configured_keywords(
        settings,
        "exclude_keywords",
        "horoscope,astrology,photo gallery,photos,web story,viral video,recipe,lottery,result live,cricket score,match preview",
    )
    if not excluded:
        return items
    useful = []
    for item in items:
        haystack = f"{item.title} {item.source}".lower()
        if not any(keyword in haystack for keyword in excluded):
            useful.append(item)
    return useful


def assign_ids(section: str, items: list[NewsItem]) -> list[NewsItem]:
    prefix = "I" if section == "india" else "W"
    for index, item in enumerate(items, 1):
        item.item_id = f"{prefix}{index}"
    return items


def normalized_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def normalize_match_text(text: str) -> str:
    text = clean_text(text).lower()
    replacements = {
        r"\brbi\b": "reserve bank of india",
        r"\bsebi\b": "securities and exchange board of india",
        r"\bnse\b": "national stock exchange",
        r"\bbse\b": "bombay stock exchange",
        r"\bfii\b": "foreign institutional investors",
        r"\bdii\b": "domestic institutional investors",
        r"\bfed\b": "federal reserve",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    return text


def keyword_set(text: str) -> set[str]:
    normalized = normalize_match_text(text)
    words = re.findall(r"[\w-]{4,}", normalized, flags=re.UNICODE)
    stopwords = {
        "about", "after", "from", "have", "into", "that", "their", "this", "with",
        "news", "latest", "today", "google", "india", "indian", "world", "market",
        "markets", "economy", "economic", "says", "said", "could", "first", "new",
        "update", "updates", "story", "stories", "live",
    }
    return {word for word in words if word not in stopwords}


def title_fingerprint(title: str) -> str:
    return " ".join(sorted(keyword_set(title)))


def dedupe_items(items: list[NewsItem]) -> list[NewsItem]:
    result: list[NewsItem] = []
    seen_urls: set[str] = set()
    seen_keys: set[str] = set()
    for item in items:
        url_key = normalized_url(item.url)
        title_key = title_fingerprint(item.title)
        if url_key in seen_urls or title_key in seen_keys:
            continue
        seen_urls.add(url_key)
        seen_keys.add(title_key)
        result.append(item)
    return result


def similar_titles(a: str, b: str) -> bool:
    left = keyword_set(a)
    right = keyword_set(b)
    if not left or not right:
        return False
    return len(left & right) / max(len(left), len(right)) >= 0.72


def related_titles(a: str, b: str) -> bool:
    left = keyword_set(a)
    right = keyword_set(b)
    if not left or not right:
        return False
    overlap = len(left & right)
    return overlap >= 3 and overlap / min(len(left), len(right)) >= 0.55


def group_related_items(items: list[NewsItem]) -> list[list[NewsItem]]:
    groups: list[list[NewsItem]] = []
    for item in items:
        matched_group = None
        for group in groups:
            if any(related_titles(item.title, existing.title) for existing in group):
                matched_group = group
                break
        if matched_group is None:
            groups.append([item])
        else:
            matched_group.append(item)
    return groups


def keyword_hits(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if keyword and keyword in text)


def unique_sources(group: list[NewsItem]) -> set[str]:
    return {clean_text(item.source).lower() for item in group if clean_text(item.source)}


def recency_score(group: list[NewsItem]) -> int:
    newest = max((item.published_at for item in group if item.published_at), default=None)
    if not newest:
        return 0
    age = datetime.now(timezone.utc) - newest.astimezone(timezone.utc)
    if age <= timedelta(hours=6):
        return 2
    if age <= timedelta(hours=12):
        return 1
    return 0


def score_story_group(group: list[NewsItem], settings: dict) -> tuple[int, list[str]]:
    if not group:
        return 0, []
    section = group[0].section
    text = " ".join(f"{item.title} {item.source}" for item in group).lower()
    score = 0
    reasons: list[str] = []

    source_boost = min(4, max((max(0, item.source_weight) for item in group), default=1))
    score += source_boost
    reasons.append(f"source weight +{source_boost}")

    if section == "india":
        india_hits = keyword_hits(text, section_keywords("india", settings))
        if india_hits:
            boost = min(6, india_hits * 2)
            score += boost
            reasons.append(f"India markets +{boost}")
        else:
            score -= 2
            reasons.append("weak India match -2")
    else:
        world_hits = keyword_hits(text, section_keywords("world", settings))
        if world_hits:
            boost = min(5, world_hits)
            score += boost
            reasons.append(f"global cues +{boost}")

    public_hits = keyword_hits(
        text,
        configured_keywords(
            settings,
            "research_keywords",
            "rbi,sebi,nse,bse,nifty,sensex,rupee,inflation,gdp,iip,pmi,monetary policy,repo rate,bond yield,crude oil,brent,earnings,profit,revenue,credit growth,liquidity,fii,dii,global cues,us markets,fed",
        ),
    )
    if public_hits:
        boost = min(6, public_hits * 2)
        score += boost
        reasons.append(f"market significance +{boost}")

    classroom_hits = keyword_hits(
        text,
        configured_keywords(settings, "classroom_keywords", "inflation,gdp,interest rate,repo rate,rupee,crude oil,bond yield,earnings,valuation,liquidity"),
    )
    if classroom_hits:
        boost = min(3, classroom_hits)
        score += boost
        reasons.append(f"investor context +{boost}")

    if len(group) > 1:
        boost = min(3, len(group) - 1)
        score += boost
        reasons.append(f"related headlines +{boost}")
    if len(unique_sources(group)) > 1:
        score += 2
        reasons.append("multiple sources +2")
    recency_boost = recency_score(group)
    if recency_boost:
        score += recency_boost
        reasons.append(f"freshness +{recency_boost}")

    low_value_hits = keyword_hits(text, configured_keywords(settings, "low_value_keywords", "campus diary,opinion,editorial,celebrity,entertainment,promotion,launch offer,poster,trailer"))
    if low_value_hits:
        penalty = min(6, low_value_hits * 3)
        score -= penalty
        reasons.append(f"low value -{penalty}")
    if len(keyword_set(text)) <= 2:
        score -= 2
        reasons.append("vague headline -2")
    return score, reasons


def select_top_story_groups(section: str, items: list[NewsItem], settings: dict) -> list[list[NewsItem]]:
    groups = group_related_items(items)
    scored = []
    for group in groups:
        score, _ = score_story_group(group, settings)
        newest = max((item.published_at.timestamp() for item in group if item.published_at), default=0.0)
        scored.append((score, newest, group))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    max_groups = int(settings.get("max_groups_per_section", 8))
    min_score = int(settings.get("min_group_score", 2))
    selected = [group for score, _, group in scored if score >= min_score][:max_groups]
    if not selected:
        selected = [group for _, _, group in scored[:max_groups]]
    return selected
