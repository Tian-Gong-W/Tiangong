#!/usr/bin/env python3
"""统一版配置：全部通过环境变量读取。"""

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(APP_DIR / "data"))).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

ZHENAI_TOKEN = os.getenv("ZHENAI_TOKEN", "").strip()
ZHENAI_SEEDTOKEN = os.getenv("ZHENAI_SEEDTOKEN", "").strip()

CRAWL_MODE = os.getenv("CRAWL_MODE", "search").strip().lower()
AGE_BEGIN = int(os.getenv("AGE_BEGIN", "25"))
AGE_END = int(os.getenv("AGE_END", "65"))
GENDER_FILTER = os.getenv("GENDER_FILTER", "女").strip() or None
MAX_PAGES = int(os.getenv("MAX_PAGES", "49"))
LOOP_INTERVAL_MINUTES_RAW = os.getenv("LOOP_INTERVAL_MINUTES", "60").strip()
LOOP_INTERVAL_MINUTES = None if LOOP_INTERVAL_MINUTES_RAW.lower() in {"", "none", "null", "0"} else int(LOOP_INTERVAL_MINUTES_RAW)

CITY_NAMES = [x.strip() for x in os.getenv("CITY_NAMES", "").split(",") if x.strip()]

OUTPUT_FILE = DATA_DIR / "zhenai_members.csv"
SCRAPED_IDS_FILE = DATA_DIR / "scraped_ids.txt"
CITY_PROGRESS_FILE = DATA_DIR / "city_progress.txt"

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
TG_GROUP_CHAT_ID = os.getenv("TG_GROUP_CHAT_ID", "").strip()
TG_REPORT_CHAT_ID = os.getenv("TG_REPORT_CHAT_ID", "").strip()
INSTANCE_LABEL = os.getenv("INSTANCE_LABEL", "统一版").strip() or "统一版"
