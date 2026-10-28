import mimetypes
import os
import sys
from urllib import parse

import requests

from naver_auth import TokenError, get_access_token

# ===== 테스트용 설정값: 여기에 직접 입력 =====
CLUB_ID = "31784891"  # 카페 고유 ID (숫자)
MENU_ID = "8"  # 게시판 ID (상품게시판은 불가)

SUBJECT = "네이버 Cafe api Test Python"
CONTENT = "<font color='red'>python</font>으로 작성한 테스트 글입니다.<br>"
IMAGE_PATHS = []  # 예: ["a.jpg", "b.jpg"]
# ============================================

API_URL = "https://openapi.naver.com/v1/cafe/{clubid}/menu/{menuid}/articles"


def post_article(token, clubid, menuid, subject, content, image_paths=None):
    url = API_URL.format(clubid=clubid, menuid=menuid)
    headers = {"Authorization": "Bearer " + token}
    subject = parse.quote(subject)
    content = parse.quote(content)

    if not image_paths:
        # 이미지가 없으면 urlencoded form 으로 전송
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        data = f"subject={subject}&content={content}"
        return requests.post(url, headers=headers, data=data.encode("utf-8"), timeout=30)

    # 이미지가 있으면 multipart 로 전송
    files = []
    opened = []
    try:
        for path in image_paths:
            f = open(path, "rb")
            opened.append(f)
            files.append(("image", (parse.quote(os.path.basename(path)), f, mimetypes.guess_type(path)[0] or "image/jpeg", {"Expires": "0"})))
        return requests.post(
            url,
            headers=headers,
            data={"subject": subject, "content": content},
            files=files,
            timeout=60,
        )
    finally:
        for f in opened:
            f.close()


if __name__ == "__main__":
    if not (CLUB_ID and MENU_ID):
        print("CLUB_ID, MENU_ID 값을 파일 상단에 입력하세요.")
        sys.exit(1)

    try:
        token = get_access_token()
    except TokenError as exc:
        print(f"[TOKEN_ERROR] {exc}")
        sys.exit(2)  # 워크플로에서 토큰 만료 알림을 구분하기 위한 종료 코드

    res = post_article(token, CLUB_ID, MENU_ID, SUBJECT, CONTENT, IMAGE_PATHS)
    print("status:", res.status_code)
    print(res.text)
    if res.status_code != 200:
        sys.exit(1)
