"""auction_chart.py가 만든 그래프를 품목마다 게시글 1개씩 카페에 올린다.

사용법: python post_auction_articles.py [YYYYMMDD] [품목:무게 ...]  (항목 생략 시 환경변수 ITEM_GROUP 의 ITEMS_FIRST/ITEMS_SECOND, 기본 전체)
제목: "[YYYY-MM-DD] 사과 10kg 경매 결과"
"""
import sys
import time
from datetime import datetime
from pathlib import Path

from auction_analysis import analyze, to_html
from auction_chart import default_items, fetch, fetch_previous, group_by_weight
from naver_auth import TokenError, get_access_token
from post_cafe_article import CLUB_ID, MENU_ID, post_article

POST_INTERVAL = 90  # 초
OUTDIR = Path(__file__).parent / "output"
SUMMARY = OUTDIR / "summary.txt"  # 워크플로가 디스코드 알림 본문으로 쓰는 항목별 결과


def record(line):
    """항목별 결과를 출력하고 요약 파일에 바로 덧붙인다 (중간에 죽어도 지금까지의 결과가 남는다)."""
    print(line)
    with SUMMARY.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    pretty = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    OUTDIR.mkdir(exist_ok=True)
    SUMMARY.write_text("", encoding="utf-8")
    try:
        token = get_access_token()
    except TokenError as exc:
        record(f"❌ 네이버 토큰 오류: {exc}")
        sys.exit(2)

    items = [tuple(a.split(":", 1)) for a in sys.argv[2:]] or default_items()
    bubin = "11000101"
    cache = {}  # pummok -> (오늘 groups, 이전 날짜, 이전 groups)
    failed = False
    for i, (pummok, weight) in enumerate(items):
        if i:
            time.sleep(POST_INTERVAL)  # 연속 등록 제한 회피
        image = OUTDIR / f"{date}_{pummok}_{weight}.png"
        if not image.exists():
            record(f"⚠️ {pummok} {weight}: 그래프 파일 없음, 건너뜀")
            continue
        subject = f"[{pretty}] {pummok} {weight} 가락 시장 경매 결과"
        if pummok not in cache:
            groups = group_by_weight(fetch(date, pummok, bubin), pummok)
            prev_date, prev_groups = fetch_previous(date, pummok, bubin) if groups else (None, {})
            cache[pummok] = (groups, prev_date, prev_groups)
        groups, prev_date, prev_groups = cache[pummok]
        content = f"{subject}<br><br>"
        try:
            content += to_html(analyze(pummok, weight, date, groups.get(weight, {}),
                                       prev_date, prev_groups.get(weight, {})))
        except Exception as exc:  # 분석 없는 글이 올라가지 않도록 건너뛴다
            record(f"❌ {pummok} {weight}: 분석 실패, 게시 건너뜀 ({exc})")
            failed = True
            continue
        res = post_article(token, CLUB_ID, MENU_ID, subject, content, [str(image)])
        print(subject, "->", res.status_code, res.text)
        if res.status_code == 200:
            record(f"✅ {pummok} {weight}: 게시 성공")
        else:
            record(f"❌ {pummok} {weight}: 게시 실패 (HTTP {res.status_code}) {res.text[:200]}")
        failed |= res.status_code != 200
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
