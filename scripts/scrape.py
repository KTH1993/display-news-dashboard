#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
디스플레이 뉴스 대시보드 스크래퍼
- 유비리서치넷 / KDIA 일일뉴스 / 삼성디스플레이 뉴스룸 / LG디스플레이(공식 보도자료)
- 결과를 data/news.json 에 저장한다.

⚠️ 주의: 각 사이트의 HTML 구조가 바뀌면 셀렉터가 깨질 수 있습니다.
한 소스가 실패해도 다른 소스는 계속 진행하고, 실패한 소스는 기존 news.json의
데이터를 그대로 유지합니다 (완전히 비우지 않음).
"""

import json
import re
import sys
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 20
ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "data" / "news.json"

MAX_ITEMS = {"ubi": 6, "kdia": 10, "samsung": 5, "lg": 5}


def get_soup(url, **kwargs):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kwargs)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    return BeautifulSoup(resp.text, "lxml")


def load_existing():
    if JSON_PATH.exists():
        try:
            return json.loads(JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sources": {}}


# ---------------------------------------------------------------------------
# 1) 유비리서치넷 — 워드프레스(Enfold 테마), 포커스온/포커스Pro 게시물
#    permalink 앵커에 rel="bookmark" 가 붙는 워드프레스 기본 패턴을 사용한다.
# ---------------------------------------------------------------------------
def scrape_ubi():
    soup = get_soup("https://ubiresearchnet.com/")
    items = []
    seen = set()

    anchors = soup.select('a[rel="bookmark"]') or soup.select("h2 a, h3 a")
    for a in anchors:
        title = a.get_text(strip=True)
        url = a.get("href", "")
        if not title or not url or url in seen:
            continue
        if "ubiresearchnet.com" not in url:
            continue
        seen.add(url)

        # 날짜: 인접 텍스트에서 "2026년 8월 4일" 패턴 탐색
        date_str = ""
        container = a.find_parent(["article", "div", "li"])
        if container:
            m = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", container.get_text())
            if m:
                y, mo, d = m.groups()
                date_str = f"{y}.{int(mo):02d}.{int(d):02d}"

        # 카테고리 태그(포커스온 / 포커스 Pro) 추정
        tag = ""
        if container:
            cat_link = container.find("a", href=re.compile(r"/category/"))
            if cat_link:
                tag = cat_link.get_text(strip=True)

        items.append({"title": title, "url": url, "date": date_str, "tag": tag, "desc": ""})
        if len(items) >= MAX_ITEMS["ubi"]:
            break

    return items


# ---------------------------------------------------------------------------
# 2) KDIA 일일뉴스 — 게시판 테이블(mgrId=64)
# ---------------------------------------------------------------------------
def scrape_kdia():
    soup = get_soup("https://www.kdia.org/bbs/bbsList.jsp?mgrId=64")
    items = []

    rows = soup.select("table tr")
    for row in rows:
        a = row.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        if not title:
            continue
        href = a["href"]
        if href.startswith("/"):
            href = "https://www.kdia.org" + href

        date_str = ""
        m = re.search(r"\d{4}-\d{2}-\d{2}", row.get_text())
        if m:
            date_str = m.group(0).replace("-", ".")

        items.append({"title": title, "url": href, "date": date_str, "tag": "", "desc": ""})
        if len(items) >= MAX_ITEMS["kdia"]:
            break

    return items


# ---------------------------------------------------------------------------
# 3) 삼성디스플레이 뉴스룸 — 상단 "최신 기사" 위젯의 앵커(/{숫자} 형태)
# ---------------------------------------------------------------------------
def scrape_samsung():
    soup = get_soup("https://news.samsungdisplay.com/")
    items = []
    seen = set()

    anchors = soup.find_all("a", href=re.compile(r"^https://news\.samsungdisplay\.com/\d+$"))
    for a in anchors:
        url = a["href"]
        if url in seen:
            continue
        text = a.get_text(" ", strip=True)
        if not text:
            continue
        seen.add(url)

        # 첫 문장(또는 첫 30자 정도)을 제목으로, 나머지를 설명으로 근사 분리
        title, desc = text, ""
        m = re.match(r"^(.{5,60}?)(?<=[.가-힣])([A-Z가-힣].{20,})$", text)
        # 위 정규식이 애매하면 그냥 통짜 텍스트를 제목으로 사용
        items.append({"title": title, "url": url, "date": "", "tag": "", "desc": desc})
        if len(items) >= MAX_ITEMS["samsung"]:
            break

    return items


# ---------------------------------------------------------------------------
# 4) LG디스플레이 — news.lgdisplay.com은 JS 렌더링이라 스크래핑이 어려워
#    공식 lgdisplay.com 보도자료(서버 렌더링) 페이지를 대신 사용한다.
# ---------------------------------------------------------------------------
def scrape_lg():
    soup = get_soup("https://www.lgdisplay.com/kor/company/media-center/latest-news")
    items = []

    # "자세히보기" 링크가 각 게시물의 상세 링크
    for a in soup.find_all("a", string=re.compile("자세히보기")):
        url = a.get("href", "")
        if url.startswith("/"):
            url = "https://www.lgdisplay.com" + url
        block = a.find_parent(["li", "div", "article"])
        title = ""
        date_str = ""
        if block:
            title_tag = block.find(["strong", "h3", "h4"])
            title = title_tag.get_text(strip=True) if title_tag else ""
            m = re.search(r"\d{4}-\d{2}-\d{2}", block.get_text())
            if m:
                date_str = m.group(0).replace("-", ".")
        if not title:
            continue
        items.append({"title": title, "url": url, "date": date_str, "tag": "PR", "desc": ""})
        if len(items) >= MAX_ITEMS["lg"]:
            break

    return items


SCRAPERS = {
    "ubi": ("유비리서치넷", "https://ubiresearchnet.com/", scrape_ubi),
    "kdia": ("KDIA 일일뉴스", "https://www.kdia.org/bbs/bbsList.jsp?mgrId=64", scrape_kdia),
    "samsung": ("삼성디스플레이 뉴스룸", "https://news.samsungdisplay.com/", scrape_samsung),
    "lg": ("LG디스플레이", "https://www.lgdisplay.com/kor/company/media-center/latest-news", scrape_lg),
}


def main():
    existing = load_existing()
    sources_out = {}
    had_error = False

    for key, (name, url, fn) in SCRAPERS.items():
        try:
            items = fn()
            if not items:
                raise ValueError("수집된 항목이 없습니다 (셀렉터 확인 필요)")
            sources_out[key] = {"name": name, "url": url, "items": items}
            print(f"[OK] {key}: {len(items)}건 수집")
        except Exception as e:
            had_error = True
            print(f"[FAIL] {key}: {e}", file=sys.stderr)
            traceback.print_exc()
            # 실패 시 기존 데이터 유지 (완전히 비우지 않음)
            fallback = existing.get("sources", {}).get(key)
            if fallback:
                sources_out[key] = fallback
                print(f"[FALLBACK] {key}: 기존 데이터 {len(fallback.get('items', []))}건 유지")
            else:
                sources_out[key] = {"name": name, "url": url, "items": []}

    now = datetime.now(KST)
    output = {
        "generated_at": now.isoformat(),
        "generated_at_display": now.strftime("%Y.%m.%d %H:%M KST"),
        "sources": sources_out,
    }

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장 완료: {JSON_PATH}")

    # 모든 소스가 실패한 경우에만 워크플로우를 실패 처리 (알림용)
    if had_error and all(not v.get("items") for v in sources_out.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
