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


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    pretty = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    try:
        token = get_access_token()
    except TokenError as exc:
        print(f"[TOKEN_ERROR] {exc}")
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
            print(f"[건너뜀] 그래프 파일 없음: {image}")
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
            print(f"[분석 실패, 게시 건너뜀] {pummok} {weight}: {exc}")
            failed = True
            continue
        res = post_article(token, CLUB_ID, MENU_ID, subject, content, [str(image)])
        print(subject, "->", res.status_code, res.text)
        failed |= res.status_code != 200
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
