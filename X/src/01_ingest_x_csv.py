import glob
import json
import math
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import pandas as pd

from utils_io import ensure_dir
from utils_text import extract_domains, extract_hashtags, extract_urls, hash_id, normalize_text_basic


IN_GLOB = "data/*.csv"
OUT_COMMENTS = "data/comments.jsonl"
OUT_VIDEOS = "data/videos.jsonl"
CHUNK_SIZE = 50000

USER_ID_RE = re.compile(r"'id':\s*([0-9]+)")
HASHTAG_TEXT_RE = re.compile(r"'text':\s*'([^']+)'")
MENTION_SN_RE = re.compile(r"'screen_name':\s*'([^']+)'")
MENTION_TEXT_RE = re.compile(r"@([A-Za-z0-9_]{1,50})")
TWEET_ID_RE = re.compile(r"'id':\s*([0-9]+)")


def normalize_id(value: object) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    if "e" in s.lower():
        try:
            d = Decimal(s)
            return str(int(d))
        except (InvalidOperation, ValueError):
            return s
    return s


def extract_user_id(user_field: object) -> str:
    if not user_field:
        return ""
    m = USER_ID_RE.search(str(user_field))
    return m.group(1) if m else ""


def extract_hashtags_from_field(field: object) -> list[str]:
    if not field:
        return []
    tags = [t.lower() for t in HASHTAG_TEXT_RE.findall(str(field))]
    return list(dict.fromkeys(tags))


def extract_mentions_from_field(field: object) -> list[str]:
    if not field:
        return []
    mentions = [m.lower() for m in MENTION_SN_RE.findall(str(field))]
    return list(dict.fromkeys(mentions))


def extract_mentions_from_text(text: str) -> list[str]:
    if not text:
        return []
    mentions = [m.lower() for m in MENTION_TEXT_RE.findall(text)]
    return list(dict.fromkeys(mentions))


def extract_tweet_id(field: object) -> str:
    if not field:
        return ""
    m = TWEET_ID_RE.search(str(field))
    return m.group(1) if m else ""


def parse_date_string(value: str) -> str | None:
    if not value:
        return None
    try:
        if "T" in value:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_epoch(epoch_value: object, date_value: object) -> str | None:
    if epoch_value is not None and str(epoch_value).strip():
        try:
            ts = float(epoch_value)
            if not math.isnan(ts):
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            pass
    if date_value is not None and str(date_value).strip():
        return parse_date_string(str(date_value).strip())
    return None


def to_int(value: object) -> int:
    if value is None:
        return 0
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def main() -> None:
    files = sorted(glob.glob(IN_GLOB))
    if not files:
        raise RuntimeError(f"No CSV files found for {IN_GLOB}")

    ensure_dir(os.path.dirname(OUT_COMMENTS) or ".")

    total = 0
    kept = 0
    conv_to_channel: dict[str, str] = {}

    with open(OUT_COMMENTS, "w", encoding="utf-8") as fout:
        for path in files:
            for chunk in pd.read_csv(path, chunksize=CHUNK_SIZE, dtype=str, keep_default_na=False):
                for _, row in chunk.iterrows():
                    tweet_id = normalize_id(row.get("id_str") or row.get("id"))
                    if not tweet_id:
                        continue

                    conv_id = normalize_id(
                        row.get("conversationIdStr") or row.get("conversationId") or tweet_id
                    )

                    user_id = normalize_id(row.get("user_id"))
                    if not user_id:
                        user_id = extract_user_id(row.get("user"))
                    if not user_id:
                        continue

                    author_id = hash_id(user_id, salt="tw-osint")

                    text = row.get("rawContent") or row.get("text") or ""
                    text = normalize_text_basic(text)

                    published_at = parse_epoch(row.get("epoch"), row.get("date"))

                    urls = extract_urls(text)
                    tweet_url = row.get("url") or ""
                    if tweet_url and tweet_url not in urls:
                        urls = [tweet_url] + urls
                    links_field = row.get("links")
                    extra_urls = extract_urls(str(links_field)) if links_field else []
                    if extra_urls:
                        urls = list(dict.fromkeys(urls + extra_urls))
                    domains = extract_domains(urls)
                    hashtags = extract_hashtags(text)
                    extra_tags = extract_hashtags_from_field(row.get("hashtags"))
                    if extra_tags:
                        hashtags = list(dict.fromkeys(hashtags + extra_tags))

                    mentions = extract_mentions_from_text(text)
                    extra_mentions = extract_mentions_from_field(row.get("mentionedUsers"))
                    if extra_mentions:
                        mentions = list(dict.fromkeys(mentions + extra_mentions))

                    retweet_id = normalize_id(row.get("retweetedTweetID"))
                    retweet_user_id = normalize_id(row.get("retweetedUserID"))
                    quoted_id = normalize_id(row.get("quotedTweetID") or row.get("quotedTweetId"))
                    if not quoted_id:
                        quoted_id = extract_tweet_id(row.get("quotedTweet"))

                    in_reply_to = normalize_id(row.get("in_reply_to_status_id_str"))

                    out = {
                        "video_id": conv_id,
                        "conversation_id": conv_id,
                        "comment_id": tweet_id,
                        "author_id": author_id,
                        "published_at": published_at,
                        "text": text,
                        "urls": urls,
                        "links": extra_urls,
                        "domains": domains,
                        "hashtags": hashtags,
                        "mentions": mentions,
                        "retweeted_tweet_id": retweet_id,
                        "retweeted_user_id": retweet_user_id,
                        "quoted_tweet_id": quoted_id,
                        "in_reply_to_status_id_str": in_reply_to,
                        "lang": row.get("lang") or "",
                        "like_count": to_int(row.get("likeCount")),
                        "reply_count": to_int(row.get("replyCount")),
                        "retweet_count": to_int(row.get("retweetCount")),
                        "quote_count": to_int(row.get("quoteCount")),
                        "view_count": to_int(row.get("viewCount")),
                        "tweet_type": row.get("type") or row.get("_type") or "",
                        "tweet_url": tweet_url,
                    }

                    fout.write(json.dumps(out, ensure_ascii=False) + "\n")
                    kept += 1
                    total += 1

                    if conv_id and conv_id not in conv_to_channel:
                        conv_to_channel[conv_id] = author_id

            print(f"[OK] Processed: {path}")

    with open(OUT_VIDEOS, "w", encoding="utf-8") as fvid:
        for conv_id, channel_id in conv_to_channel.items():
            row = {"video_id": conv_id, "channel_id": channel_id, "source": "twitter"}
            fvid.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Total tweets read: {total}")
    print(f"Saved: {OUT_COMMENTS}")
    print(f"Conversations saved: {OUT_VIDEOS} ({len(conv_to_channel)})")


if __name__ == "__main__":
    main()
