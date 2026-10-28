"""환경변수의 refresh_token으로 access_token을 재발급한다 (GitHub Actions용).

필요한 환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_REFRESH_TOKEN
refresh_token은 로컬에서 token_tools/naver_login.py 로 발급받아 시크릿에 등록한다.
"""
import os

import requests

TOKEN_URL = "https://nid.naver.com/oauth2.0/token"


class TokenError(RuntimeError):
    """토큰 발급/재발급 실패 (refresh_token 만료 등). 다시 로그인해야 한다."""


def _request_token(params):
    res = requests.post(TOKEN_URL, data=params, timeout=30)
    try:
        body = res.json()
    except ValueError:
        raise RuntimeError(f"토큰 응답을 해석할 수 없습니다: HTTP {res.status_code}")
    # 네이버는 실패해도 200 + error 필드로 내려주는 경우가 있다.
    if "access_token" not in body:
        raise TokenError(f"토큰 요청 실패: {body}")
    return body


def get_access_token():
    """refresh_token으로 새 access_token을 받아 돌려준다. 실패하면 TokenError."""
    missing = [k for k in ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET", "NAVER_REFRESH_TOKEN")
               if not os.environ.get(k)]
    if missing:
        raise TokenError(f"환경변수가 설정되지 않았습니다: {', '.join(missing)}")
    body = _request_token(
        {
            "grant_type": "refresh_token",
            "client_id": os.environ["NAVER_CLIENT_ID"],
            "client_secret": os.environ["NAVER_CLIENT_SECRET"],
            "refresh_token": os.environ["NAVER_REFRESH_TOKEN"],
        }
    )
    return body["access_token"]


if __name__ == "__main__":
    print(get_access_token())
