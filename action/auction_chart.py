"""가락시장 경매결과를 조회해 무게(UUN)별로 가격대(PPRICE)-물량(QTY) 그래프를 PNG로 저장한다.

사용법: python auction_chart.py [YYYYMMDD] [법인코드] [품목:무게 ...]
  예) python auction_chart.py 20261021 11000101 사과:10kg 감귤:5kg
  날짜 생략 시 오늘, 항목 생략 시 환경변수 ITEM_GROUP(first/second/all, 기본 all)에 해당하는
  ITEMS_FIRST / ITEMS_SECOND 목록을 순서대로 조회한다.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

URL = "https://www.garak.co.kr/homepage/publicdata/dataJsonOpen.do"
# 가락시장 공공데이터 인증정보 (GitHub Secrets → 환경변수)
API_ID = os.environ.get("GARAK_API_ID", "")
API_PASSWD = os.environ.get("GARAK_API_PASSWD", "")
PAGE_SIZE = 1000
MAX_LOOKBACK_DAYS = 14  # 이전 데이터를 찾을 때 거슬러 올라갈 최대 일수

# 조회할 (품목, 무게) 목록. 순서대로 조회해 항목마다 PNG를 저장한다.
# 월~토 오전 6시에 조회·게시할 항목
ITEMS_FIRST = [
    ("감귤", "5kg"),
]
# 월~토 오전 10시에 조회·게시할 항목
ITEMS_SECOND = [
    ("사과", "10kg"),
]
ITEM_GROUPS = {"first": ITEMS_FIRST, "second": ITEMS_SECOND}

# Windows는 맑은 고딕, GitHub Actions(Ubuntu)는 fonts-nanum 의 나눔고딕을 쓴다.
plt.rcParams["font.family"] = ["Malgun Gothic", "NanumGothic"]
plt.rcParams["axes.unicode_minus"] = False


def fetch(date, pummok, bubin):
    """모든 페이지를 조회해 행 목록을 돌려준다. (품목명은 UTF-8로 인코딩해야 동작함)"""
    if not (API_ID and API_PASSWD):
        sys.exit("환경변수 GARAK_API_ID, GARAK_API_PASSWD 가 설정되지 않았습니다.")
    rows, page = [], 1
    while True:
        query = urlencode({
            "id": API_ID, "passwd": API_PASSWD, "dataid": "data12",
            "pagesize": PAGE_SIZE, "pageidx": page, "portal.templet": "false",
            "s_date": date, "s_bubin": bubin, "s_pummok": pummok, "s_sangi": "",
        })
        with urlopen(f"{URL}?{query}", timeout=30) as res:
            text = res.read().decode("utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            break  # "데이터가 없습니다" 응답(HTML)
        if data.get("resultCode") == "ERROR":
            sys.exit(f"API 오류: {data.get('message')}")
        batch = data.get("resultData", [])
        rows += batch
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    return rows


def group_by_weight(rows, pummok):
    """무게별로 {가격: 물량 합계}를 만든다. s_pummok은 부분일치라 정확히 같은 품목만 남긴다."""
    groups = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["PUMMOK"] != pummok:
            continue
        groups[r["UUN"]][int(r["PPRICE"])] += int(r["QTY"])
    return groups


def fetch_previous(date, pummok, bubin):
    """date 이전 날짜를 하루씩 거슬러 올라가며 데이터가 있는 가장 가까운 날을 찾는다."""
    day = datetime.strptime(date, "%Y%m%d")
    for _ in range(MAX_LOOKBACK_DAYS):
        day -= timedelta(days=1)
        prev = day.strftime("%Y%m%d")
        groups = group_by_weight(fetch(prev, pummok, bubin), pummok)
        if groups:
            return prev, groups
    return None, {}


def draw(weight, price_qty, date, prev_qty, prev_date, pummok, outdir):
    """위: 오늘(진한 색), 아래: 이전 영업일(옅은 색). 가격 축과 물량 축을 공유해 비교하기 쉽게 한다."""
    prices = sorted(set(price_qty) | set(prev_qty))
    labels = [f"{p:,}" for p in prices]
    panels = [(price_qty, f"{date} (오늘)", "#2f7ed8")]
    if prev_date:
        panels.append((prev_qty, f"{prev_date} (이전)", "#a9c9ee"))
    fig, axes = plt.subplots(len(panels), 1, sharex=True, sharey=True, squeeze=False,
                             figsize=(max(8, 0.4 * len(prices) + 2), 4 * len(panels)))
    for ax, (qty, title, color) in zip(axes[:, 0], panels):
        bars = ax.bar(labels, [qty.get(p, 0) for p in prices], color=color)
        ax.bar_label(bars, labels=[v or "" for v in bars.datavalues], padding=3)
        ax.set_ylabel("물량 (QTY)")
        ax.set_title(title, loc="left", fontsize=10)
    for ax in axes[:, 0]:
        ax.tick_params(axis="x", rotation=60, labelbottom=True)
        ax.set_xlabel("가격 (원)")
    fig.suptitle(f"{pummok} {weight} 가격대별 물량")
    fig.tight_layout()
    path = outdir / f"{date}_{pummok}_{weight}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def default_items():
    """환경변수 ITEM_GROUP(first/second)에 해당하는 항목 목록. 비었거나 all이면 전체를 돌려준다."""
    group = os.environ.get("ITEM_GROUP", "").strip().lower()
    if group in ("", "all"):
        return [item for items in ITEM_GROUPS.values() for item in items]
    if group not in ITEM_GROUPS:
        sys.exit(f"ITEM_GROUP 값 오류: '{group}' (first, second, all 중 하나)")
    return ITEM_GROUPS[group]


def parse_items(args):
    """'사과:10kg' 형태의 인자를 (품목, 무게) 목록으로 바꾼다. 인자가 없으면 default_items()를 쓴다."""
    if not args:
        return default_items()
    items = []
    for arg in args:
        pummok, sep, weight = arg.partition(":")
        if not sep or not weight:
            sys.exit(f"항목 형식 오류: '{arg}' (예: 사과:10kg)")
        items.append((pummok, weight))
    return items


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    bubin = sys.argv[2] if len(sys.argv) > 2 else "11000101"
    items = parse_items(sys.argv[3:])
    outdir = Path(__file__).parent / "output"
    outdir.mkdir(exist_ok=True)

    cache = {}  # 품목별 조회 결과 재사용: pummok -> (오늘 groups, 이전 날짜, 이전 groups)
    for pummok, weight in items:
        if pummok not in cache:
            groups = group_by_weight(fetch(date, pummok, bubin), pummok)
            prev_date, prev_groups = fetch_previous(date, pummok, bubin) if groups else (None, {})
            cache[pummok] = (groups, prev_date, prev_groups)
        groups, prev_date, prev_groups = cache[pummok]

        if weight not in groups and weight not in prev_groups:
            print(f"[건너뜀] {date} {pummok} {weight} 경매 데이터가 없습니다.")
            continue
        if prev_date:
            print(f"[{pummok} {weight}] 비교 대상: {prev_date}")
        else:
            print(f"[{pummok} {weight}] 최근 {MAX_LOOKBACK_DAYS}일 내 비교할 이전 데이터가 없습니다.")
        path = draw(weight, groups.get(weight, {}), date, prev_groups.get(weight, {}),
                    prev_date, pummok, outdir)
        print("저장:", path)


if __name__ == "__main__":
    main()
