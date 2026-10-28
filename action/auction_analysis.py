"""group_by_weight 결과(오늘/이전)를 Claude API에 보내 비교 분석 글을 만든다.

API 키는 환경변수 ANTHROPIC_API_KEY 에서 읽는다.
"""
import html
import os
import time

import requests

FALLBACK_MODEL = "claude-haiku-5-5"  # 최신 haiku 조회 실패 시 사용
MAX_ATTEMPTS = 20  # 과일(항목)별 최대 시도 횟수
RETRY_INTERVAL = 1  # 재시도 간격(초)
API_URL = "https://api.anthropic.com/v1/messages"
MODELS_URL = "https://api.anthropic.com/v1/models"
_model = None


def _latest_haiku(headers):
    """Models API(최신순)에서 가장 최신 haiku 모델 ID를 찾아 캐시한다."""
    global _model
    if _model is None:
        _model = FALLBACK_MODEL
        try:
            res = requests.get(MODELS_URL, headers=headers, params={"limit": 100}, timeout=30)
            res.raise_for_status()
            _model = next((m["id"] for m in res.json()["data"] if "haiku" in m["id"]), FALLBACK_MODEL)
        except (requests.RequestException, KeyError, ValueError) as exc:
            print(f"[모델 조회 실패, {FALLBACK_MODEL} 사용] {exc}")
        print(f"[모델] {_model}")
    return _model


def _table(price_qty):
    return "\n".join(f"{p:,}원: {q:,}" for p, q in sorted(price_qty.items())) or "(데이터 없음)"


def _stats(price_qty):
    total = sum(price_qty.values())
    if not total:
        return "총 물량 0"
    avg = sum(p * q for p, q in price_qty.items()) / total
    return f"총 물량 {total:,}, 물량 가중평균가 {avg:,.0f}원, 최저 {min(price_qty):,}원, 최고 {max(price_qty):,}원"


def build_prompt(pummok, weight, date, price_qty, prev_date, prev_qty):
    prev = (f"[이전 영업일 {prev_date}] {_stats(prev_qty)}\n(가격: 물량)\n{_table(prev_qty)}"
            if prev_date else "[이전 영업일] 비교할 데이터 없음")
    return (
        f"가락시장 {pummok} {weight} 경매 결과를 카페 회원에게 공유할 분석 글을 한국어로 작성해줘.\n"
        "오늘과 이전 영업일을 비교해 가격 수준(가중평균·가격대 분포)과 물량 변화를 3~5문장으로 요약하고, "
        "마지막에 한 줄 시사점을 덧붙여. 주어진 숫자에 없는 내용은 추측하지 말고, "
        "마크다운 문법 없이 일반 텍스트로만 써줘.\n\n"
        f"[오늘 {date}] {_stats(price_qty)}\n(가격: 물량)\n{_table(price_qty)}\n\n{prev}"
    )


def analyze(pummok, weight, date, price_qty, prev_date, prev_qty):
    """분석 텍스트를 돌려준다. 실패하면 예외를 던진다."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("환경변수 ANTHROPIC_API_KEY 가 설정되지 않았습니다.")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    body = {"model": _latest_haiku(headers), "max_tokens": 128000,
            "thinking": {"type": "disabled"}, "messages": [{"role": "user", "content": build_prompt(
        pummok, weight, date, price_qty, prev_date, prev_qty)}]}
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            res = requests.post(API_URL, headers=headers, json=body, timeout=60)
            if res.status_code in (400, 401, 403, 404):  # 재시도해도 소용없는 오류
                raise RuntimeError(f"Claude 요청 거부 {res.status_code}: {res.text}")
            res.raise_for_status()
            text = "".join(b.get("text", "") for b in res.json()["content"] if b.get("type") == "text")
            if not text.strip():
                raise ValueError(f"텍스트 응답 없음: {res.text[:300]}")
            return text.strip()
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            last = exc
            print(f"[Claude 실패 {attempt}/{MAX_ATTEMPTS}] {pummok} {weight}: {exc}")
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_INTERVAL)
    raise RuntimeError(f"Claude 호출 {MAX_ATTEMPTS}회 실패 ({last})")


def to_html(text):
    """카페 본문용: HTML 이스케이프 후 줄바꿈을 <br>로 바꾼다."""
    return html.escape(text).replace("\n", "<br>")
