# src/utils_yt.py
import os
import time
import random
from typing import Any
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def yt_client():
    load_dotenv()
    api_key = os.getenv("YT_API_KEY")
    if not api_key:
        raise RuntimeError("Missing YT_API_KEY in .env")
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def safe_execute(req, retries: int = 8, base_backoff: float = 1.7):
    """
    Robust execute with:
    - exponential backoff + jitter
    - special handling for quotaExceeded / rateLimitExceeded
    - prints full HttpError reason
    """
    last_exc = None

    for i in range(retries):
        try:
            return req.execute()

        except HttpError as e:
            last_exc = e
            status = getattr(e.resp, "status", None)
            content = ""
            try:
                content = e.content.decode("utf-8", errors="ignore") if hasattr(e, "content") else str(e)
            except Exception:
                content = str(e)

            msg = f"[HttpError] status={status} attempt={i+1}/{retries} content={content[:300]}"
            print(msg)

            # Detect common reasons
            lower = content.lower()
            if "commentsdisabled" in lower:
                # caller should handle; here just rethrow to be caught outside
                raise

            # Exponential backoff with jitter
            sleep_s = (base_backoff ** i) + random.uniform(0, 1.0)

            # If quota exceeded, sleep longer (minutes)
            if "quotaexceeded" in lower or "daily limit exceeded" in lower:
                sleep_s = max(sleep_s, 60 * 10)  # 10 minutes

            # If rate limited, sleep a bit longer
            if "ratelimitexceeded" in lower or status in (429,):
                sleep_s = max(sleep_s, 20 + random.uniform(0, 10))

            # Transient server errors
            if status in (500, 503):
                sleep_s = max(sleep_s, 10 + random.uniform(0, 10))

            time.sleep(sleep_s)
            continue

        except Exception as e:
            last_exc = e
            sleep_s = (base_backoff ** i) + random.uniform(0, 1.0)
            print(f"[Error] attempt={i+1}/{retries} {type(e).__name__}: {e}  -> sleeping {sleep_s:.1f}s")
            time.sleep(sleep_s)
            continue

    raise RuntimeError(f"YouTube API request failed after retries. Last error: {last_exc}")
