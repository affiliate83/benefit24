#!/usr/bin/env python3
"""
지원금알리미 복지서비스 자동 포스팅
공공데이터포털 중앙부처복지서비스 API → benefit24.aqmme.com WordPress 자동 발행

사용법:
  python scripts/welfare_poster.py             # 기본 100건
  python scripts/welfare_poster.py --max 50    # 50건만
  python scripts/welfare_poster.py --dry-run   # 발행 없이 수집 목록만 출력
  python scripts/welfare_poster.py --code 002  # 특정 대상 코드 (기본 001=노인)

대상 코드:
  001=노인, 002=장애인, 003=저소득, 006=한부모, 010=근로자
"""

import argparse
import json
import os
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from dotenv import load_dotenv

# .env는 프로젝트 루트 (scripts의 상위 디렉토리)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

# ── 환경 변수 ──────────────────────────────────────────────────────
WP_URL        = os.getenv('WP_URL', 'https://benefit24.aqmme.com').rstrip('/')
WP_USER       = os.getenv('WP_USER', '')
WP_APP_PASS   = os.getenv('WP_APP_PASS', '')
API_KEY       = os.getenv('DATA_GO_KR_API_KEY', '')
ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY', '')

WELFARE_ENDPOINT = 'https://apis.data.go.kr/B554287/NationalWelfareInformationsV001'
DB_PATH          = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dedup.db')

# 관심 테마 키워드 → WordPress 카테고리 이름
THEME_MAP = {
    '의료': '의료·건강', '건강': '의료·건강', '요양': '의료·건강',
    '간병': '의료·건강', '장기요양': '의료·건강', '치매': '의료·건강',
    '주거': '주거지원', '임대': '주거지원', '주택': '주거지원',
    '문화': '문화·여가', '여가': '문화·여가', '스포츠': '문화·여가',
    '취미': '문화·여가', '관광': '문화·여가',
    '돌봄': '돌봄서비스', '재가': '돌봄서비스', '방문': '돌봄서비스',
    '교육': '교육지원', '훈련': '교육지원', '학습': '교육지원',
}
DEFAULT_CATEGORY = '생활지원'

_cat_cache: dict = {}


# ── 유틸 ──────────────────────────────────────────────────────────
def log(msg: str):
    print(f"{datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)


def _xml_text(el, tag: str, default='') -> str:
    if el is None:
        return default
    node = el.find(tag)
    return node.text.strip() if node is not None and node.text else default


def _infer_category(themes: str) -> str:
    for keyword, cat in THEME_MAP.items():
        if keyword in themes:
            return cat
    return DEFAULT_CATEGORY


# ── 공공데이터포털 API ─────────────────────────────────────────────
def get_welfare_list(page: int = 1, size: int = 100, srch_key_code: str = '001'):
    url = f"{WELFARE_ENDPOINT}/NationalWelfarelistV001"
    params = {
        'serviceKey': API_KEY,
        'numOfRows':  size,
        'pageNo':     page,
        'srchKeyCode': srch_key_code,
    }
    try:
        res = requests.get(url, params=params, timeout=20)
        res.raise_for_status()
        root  = ET.fromstring(res.content)
        items = root.findall('.//servList') or root.findall('.//item')
        total_node = root.find('.//totCnt') or root.find('.//totalCount')
        total = int(total_node.text) if total_node is not None and total_node.text else 0
        return items, total
    except Exception as e:
        log(f"[API 오류] 목록 조회: {e}")
        return [], 0


def get_welfare_detail(service_id: str):
    url = f"{WELFARE_ENDPOINT}/NationalWelfaredetailedV001"
    try:
        res = requests.get(
            url,
            params={'serviceKey': API_KEY, 'servId': service_id},
            timeout=20,
        )
        if res.status_code == 429:
            log(f"[API] 상세 API 일일 할당량 초과 — 목록 데이터만 사용 (id={service_id})")
            return None
        res.raise_for_status()
        root = ET.fromstring(res.content)
        return root.find('.//servDtlInfo') or root.find('.//item')
    except Exception as e:
        log(f"[API 오류] 상세 조회 (id={service_id}): {e}")
        return None


# ── 콘텐츠 생성 ───────────────────────────────────────────────────
def _enrich_with_claude(name: str, overview: str, target: str, how_to: str) -> str:
    """Claude API로 추가 콘텐츠 생성 (API 키 없으면 빈 문자열 반환)"""
    if not ANTHROPIC_KEY:
        return ''
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        prompt = f"""다음 복지 서비스 정보를 바탕으로 어르신들이 이해하기 쉬운 추가 설명을 HTML로 작성하세요.

서비스명: {name}
개요: {overview[:300]}
지원 대상: {target[:200]}
신청 방법: {how_to[:200]}

아래 세 섹션을 HTML로 작성하세요.
- h2, p, ul, li, div 태그만 사용 (h1 절대 금지)
- HTML 속성은 반드시 작은따옴표 사용
- 코드 펜스(```) 없이 HTML만 출력
- 없는 정보는 절대 지어내지 말 것
- 60대 이상 어르신이 이해하기 쉬운 쉬운 말투

1. <h2>이런 분께 꼭 필요한 서비스입니다</h2>
   ul/li 3개로 해당되는 어르신 상황 설명

2. <h2>신청 전 꼭 확인하세요</h2>
   ul/li 2~3개로 주의사항 또는 준비사항

3. <h2>자주 묻는 질문</h2>
   Q&A 3개 (각각 <div class='faq-item'><p class='q'>Q: ...</p><p class='a'>A: ...</p></div> 형식)"""

        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1500,
            messages=[{'role': 'user', 'content': prompt}],
        )
        text = msg.content[0].text
        # 코드 펜스 제거
        text = re.sub(r'```[a-z]*\n?', '', text).strip()
        return text
    except Exception as e:
        log(f"[Claude] 콘텐츠 강화 실패: {e}")
        return ''


def build_content(item, detail) -> str:
    # 목록 API 필드
    overview   = _xml_text(item, 'servDgst')
    dept       = _xml_text(item, 'jurMnofNm')
    org        = _xml_text(item, 'jurOrgNm')
    contact    = _xml_text(item, 'rprsCtadr')
    detail_url = _xml_text(item, 'servDtlLink')
    cycle      = _xml_text(item, 'sprtCycNm')
    method     = _xml_text(item, 'srvPvsnNm')
    online     = _xml_text(item, 'onapPsbltYn')
    themes     = _xml_text(item, 'intrsThemaArray')
    name       = _xml_text(item, 'servNm')
    target_list= _xml_text(item, 'tgtrDtlCn')

    # 상세 API 필드 (있을 때 덮어쓰기)
    target   = target_list
    criteria = ''
    how_to   = ''
    if detail is not None:
        overview = _xml_text(detail, 'wlfareInfoOutlCn') or overview
        target   = _xml_text(detail, 'tgtrDtlCn') or target_list
        criteria = _xml_text(detail, 'slctCritCn')
        how_to   = _xml_text(detail, 'alwServCn')
        contact  = _xml_text(detail, 'rprsCtadr') or contact
        dept     = _xml_text(detail, 'jurMnofNm') or dept

    online_text = '온라인 신청 가능' if online == 'Y' else ('방문·전화 신청' if online == 'N' else '')

    parts = ['<div class="welfare-detail">\n\n']

    if overview:
        parts.append(f'<h2>서비스 개요</h2>\n<p>{overview}</p>\n\n')

    if target:
        parts.append(f'<h2>지원 대상</h2>\n<p>{target}</p>\n\n')

    if criteria:
        parts.append(f'<h2>선정 기준</h2>\n<p>{criteria}</p>\n\n')

    if how_to:
        parts.append(f'<h2>신청 방법</h2>\n<p>{how_to}</p>\n\n')

    # 서비스 정보 표
    info_rows = [
        ('소관 부처', dept),
        ('소관 기관', org),
        ('지원 주기', cycle),
        ('서비스 형태', method),
        ('신청 방법', online_text),
        ('관련 테마', themes.replace(',', ', ') if themes else ''),
        ('문의처', contact),
    ]
    table_rows = '\n'.join(
        f'  <tr><th>{k}</th><td>{v}</td></tr>'
        for k, v in info_rows if v
    )
    if table_rows:
        parts.append(
            f'<h2>서비스 정보</h2>\n'
            f'<table class="welfare-table">\n{table_rows}\n</table>\n\n'
        )

    if detail_url:
        parts.append(
            f'<div class="welfare-link">\n'
            f'<a href="{detail_url}" target="_blank" rel="noopener">'
            f'복지로에서 자세한 내용 확인하기 →</a>\n'
            f'</div>\n\n'
        )

    enriched = _enrich_with_claude(name, overview, target, how_to)
    if enriched:
        parts.append(enriched + '\n\n')

    parts.append('</div>')
    return ''.join(parts)


# ── SQLite 중복 방지 ──────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute('''CREATE TABLE IF NOT EXISTS published (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id      TEXT UNIQUE NOT NULL,
        title        TEXT,
        published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    con.commit()
    con.close()


def is_published(item_id: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    row = con.execute('SELECT 1 FROM published WHERE item_id=?', (item_id,)).fetchone()
    con.close()
    return row is not None


def mark_published(item_id: str, title: str):
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute('INSERT INTO published (item_id, title) VALUES (?,?)', (item_id, title))
        con.commit()
    except sqlite3.IntegrityError:
        pass
    con.close()


# ── WordPress REST API ────────────────────────────────────────────
def _auth():
    return (WP_USER, WP_APP_PASS)


def get_or_create_category(name: str):
    if name in _cat_cache:
        return _cat_cache[name]
    try:
        res = requests.get(
            f"{WP_URL}/wp-json/wp/v2/categories",
            auth=_auth(),
            params={'search': name, 'per_page': 20},
            timeout=10,
        )
        for cat in res.json():
            if cat.get('name') == name:
                _cat_cache[name] = cat['id']
                return cat['id']
        # 없으면 새로 생성
        res = requests.post(
            f"{WP_URL}/wp-json/wp/v2/categories",
            auth=_auth(),
            headers={'Content-Type': 'application/json'},
            data=json.dumps({'name': name}),
            timeout=10,
        )
        if res.status_code == 201:
            cat_id = res.json().get('id')
            _cat_cache[name] = cat_id
            log(f"[WP] 카테고리 생성: {name} (ID:{cat_id})")
            return cat_id
    except Exception as e:
        log(f"[WP] 카테고리 오류: {e}")
    return None


def wp_post_exists(title: str) -> bool:
    try:
        res = requests.get(
            f"{WP_URL}/wp-json/wp/v2/posts",
            auth=_auth(),
            params={'search': title, 'per_page': 5},
            timeout=10,
        )
        for post in res.json():
            if post.get('title', {}).get('rendered', '').strip() == title.strip():
                return True
    except Exception as e:
        log(f"[WP] 중복 확인 오류: {e}")
    return False


def create_post(title: str, content: str, excerpt: str, category_name: str):
    if not all([WP_URL, WP_USER, WP_APP_PASS]):
        log("[오류] .env 설정 누락 — WP_URL, WP_USER, WP_APP_PASS 확인")
        return None

    data: dict = {
        'title':   title,
        'content': content,
        'excerpt': excerpt,
        'status':  'publish',
    }
    cat_id = get_or_create_category(category_name)
    if cat_id:
        data['categories'] = [cat_id]

    try:
        res = requests.post(
            f"{WP_URL}/wp-json/wp/v2/posts",
            auth=_auth(),
            headers={'Content-Type': 'application/json'},
            data=json.dumps(data),
            timeout=20,
        )
        if res.status_code == 201:
            post_id = res.json().get('id')
            log(f"[발행] ID:{post_id} [{category_name}] {title[:45]}")
            return post_id
        else:
            log(f"[발행 실패] {res.status_code}: {res.text[:200]}")
            return None
    except Exception as e:
        log(f"[WP] 통신 오류: {e}")
        return None


# ── 메인 ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='지원금알리미 복지서비스 자동 포스팅')
    parser.add_argument('--max',     type=int, default=100,  help='최대 발행 건수 (기본 100)')
    parser.add_argument('--code',    type=str, default='001', help='대상 코드 (기본 001=노인)')
    parser.add_argument('--dry-run', action='store_true',    help='발행 없이 수집 목록만 출력')
    args = parser.parse_args()

    if not API_KEY:
        log("[오류] DATA_GO_KR_API_KEY 미설정 — .env 파일 확인")
        return
    if not args.dry_run and not all([WP_USER, WP_APP_PASS]):
        log("[오류] WP_USER / WP_APP_PASS 미설정 — .env 파일 확인")
        return

    init_db()
    code_label = {'001': '노인', '002': '장애인', '003': '저소득', '006': '한부모', '010': '근로자'}
    label = code_label.get(args.code, args.code)
    log(f"{'='*55}")
    log(f"지원금알리미 복지서비스 포스팅 시작")
    log(f"대상: {label} (코드: {args.code}) | 목표: {args.max}건 | dry-run: {args.dry_run}")
    log(f"{'='*55}")

    published_count = 0
    skipped_count   = 0
    page      = 1
    page_size = 100

    while published_count < args.max:
        items, total = get_welfare_list(page=page, size=page_size, srch_key_code=args.code)
        if not items:
            log(f"[완료] 더 이상 데이터 없음")
            break

        log(f"[API] 페이지 {page}: {len(items)}건 조회 (API 전체 {total}건)")

        for item in items:
            if published_count >= args.max:
                break

            service_id = _xml_text(item, 'servId')
            name       = _xml_text(item, 'servNm')
            if not service_id or not name:
                continue

            item_id  = f"welfare_{service_id}"
            title    = f"[어르신 지원금] {name}"
            themes   = _xml_text(item, 'intrsThemaArray')
            category = _infer_category(themes)
            dgst     = _xml_text(item, 'servDgst')
            excerpt  = dgst[:120] if dgst else name

            # 1차 중복 확인 (SQLite DB)
            if is_published(item_id):
                skipped_count += 1
                continue

            # dry-run: 발행 없이 목록만 출력
            if args.dry_run:
                log(f"  [DRY] {item_id} | [{category}] {title[:50]}")
                published_count += 1
                continue

            # 2차 중복 확인 (WordPress 제목 검색)
            if wp_post_exists(title):
                log(f"  [중복] WP에 이미 존재: {title[:45]}")
                mark_published(item_id, title)
                skipped_count += 1
                continue

            # 상세 정보 조회 (1.5초 딜레이)
            time.sleep(1.5)
            detail = get_welfare_detail(service_id)

            # 콘텐츠 빌드 & 발행
            content = build_content(item, detail)
            post_id = create_post(title, content, excerpt, category)

            if post_id:
                mark_published(item_id, title)
                published_count += 1
            else:
                skipped_count += 1

            time.sleep(2)  # WordPress 서버 부하 방지

        # 다음 페이지 여부
        fetched_so_far = page * page_size
        if len(items) < page_size or fetched_so_far >= total:
            break
        page += 1
        time.sleep(3)

    log(f"{'='*55}")
    log(f"완료 - 발행: {published_count}건 / 건너뜀: {skipped_count}건")
    if not ANTHROPIC_KEY:
        log("(팁) ANTHROPIC_API_KEY 설정 시 AI로 콘텐츠를 더 풍부하게 만들 수 있습니다)")
    log(f"{'='*55}")


if __name__ == '__main__':
    main()