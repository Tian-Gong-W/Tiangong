#!/usr/bin/env python3
"""统一采集入口：不再区分上海/香港/迪拜，单实例直接处理全国城市。"""

import importlib.util
import os
import sys

from settings import (
    APP_DIR, DATA_DIR, ZHENAI_TOKEN, ZHENAI_SEEDTOKEN,
    CRAWL_MODE, AGE_BEGIN, AGE_END, GENDER_FILTER, MAX_PAGES,
    LOOP_INTERVAL_MINUTES, CITY_NAMES, OUTPUT_FILE,
)

if not ZHENAI_TOKEN:
    print("❌ 缺少 ZHENAI_TOKEN。请通过 Railway Variables 配置。")
    sys.exit(2)

os.chdir(DATA_DIR)

spec = importlib.util.spec_from_file_location("TON_MAM", APP_DIR / "TON-MAM.py")
ton_mam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ton_mam)

if CITY_NAMES:
    unknown = [name for name in CITY_NAMES if name not in ton_mam.CITY_CODE_MAP]
    if unknown:
        print("⚠️ 未识别城市，将忽略：" + ", ".join(unknown))
    selected = {name: ton_mam.CITY_CODE_MAP[name] for name in CITY_NAMES if name in ton_mam.CITY_CODE_MAP}
    if not selected:
        print("❌ CITY_NAMES 中没有可用城市。")
        sys.exit(2)
    ton_mam.CITY_CODE_MAP = selected

print("=" * 64)
print("🚀 珍爱爬虫统一版")
print(f"📁 数据目录: {DATA_DIR}")
print(f"🌏 城市数量: {len(ton_mam.CITY_CODE_MAP)}")
print(f"🎯 年龄: {AGE_BEGIN}-{AGE_END} | 性别: {GENDER_FILTER or '不限'}")
print(f"📄 每城市最大页数: {MAX_PAGES}")
print(f"🔁 循环间隔: {LOOP_INTERVAL_MINUTES if LOOP_INTERVAL_MINUTES is not None else '单次'}")
print("=" * 64)

if CRAWL_MODE == "search":
    ton_mam.start_crawl_search(
        token=ZHENAI_TOKEN,
        seedtoken=ZHENAI_SEEDTOKEN,
        age_begin=AGE_BEGIN,
        age_end=AGE_END,
        work_city=-1,
        output_file=str(OUTPUT_FILE),
        gender_filter=GENDER_FILTER,
        city_filter=None,
        max_pages=MAX_PAGES,
        loop_interval_minutes=LOOP_INTERVAL_MINUTES,
    )
elif CRAWL_MODE == "recommend":
    ton_mam.start_crawl_recommend(
        token=ZHENAI_TOKEN,
        seedtoken=ZHENAI_SEEDTOKEN,
        output_file=str(OUTPUT_FILE),
        total_pages=MAX_PAGES,
        gender_filter=GENDER_FILTER,
        city_filter=None,
        loop_interval_minutes=LOOP_INTERVAL_MINUTES,
    )
elif CRAWL_MODE == "circle":
    ton_mam.start_crawl_circle(
        token=ZHENAI_TOKEN,
        seedtoken=ZHENAI_SEEDTOKEN,
        output_file=str(OUTPUT_FILE),
        gender_filter=GENDER_FILTER,
        city_filter=None,
        max_pages_per_circle=MAX_PAGES,
        loop_interval_minutes=LOOP_INTERVAL_MINUTES,
    )
else:
    print(f"❌ 未知 CRAWL_MODE={CRAWL_MODE!r}，可选 search/recommend/circle")
    sys.exit(2)
