"""
지원금알리미 자동 푸시 알림 스크립트
- WordPress REST API로 최신 포스트 조회
- 스윙투앱 서버 푸시 API로 전체 구독자에게 발송
- GitHub Actions에서 하루 3회 실행 (08:00 / 13:00 / 19:00 KST)
"""
import os
import sys
import requests
import html
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

WP_BASE_URL    = os.environ['WP_BASE_URL'].rstrip('/')
APP_ID         = os.environ['SWING2APP_APP_ID']
API_KEY        = os.environ['SWING2APP_API_KEY']

# 스윙투앱 서버 푸시 API (공식 문서 기준)
SWING_PUSH_URL = 'https://www.swing2app.com/swapi/push_api_send_message'
HTTP_HEADERS = {
    'Accept': 'application/json, text/xml;q=0.9, */*;q=0.8',
    'User-Agent': 'Benefit24PushBot/1.0 (+https://benefit24.aqmme.com)',
}

# 시간대별 메시지 템플릿
def get_template():
    hour = datetime.now(KST).hour
    if hour < 12:
        return '☀️ 오늘의 지원금 소식', '오늘 새로 업데이트된 복지·지원금 정보를 확인하세요!'
    elif hour < 17:
        return '💰 놓치면 손해! 지원금 알림', '신청 기간이 얼마 남지 않은 지원금이 있습니다.'
    else:
        return '🔔 저녁 지원금 소식', '오늘 하루 업데이트된 지원금·복지 혜택을 확인하세요.'


def normalize_post(title: str, link: str) -> dict:
    return {
        'title': {'rendered': title},
        'link': link,
    }


def fetch_posts_from_feed(count: int = 10) -> list:
    """REST API가 호스팅/WAF에서 막힐 때 RSS 피드로 최근 포스트 조회"""
    url = f'{WP_BASE_URL}/feed/'
    resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
    print(f'[WP Feed] status={resp.status_code}')
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    items = root.findall('./channel/item')[:count]
    posts = []
    for item in items:
        title = item.findtext('title', default='').strip()
        link = item.findtext('link', default='').strip()
        if title and link:
            posts.append(normalize_post(title, link))
    return posts


def get_posts(count: int = 50) -> list:
    """WordPress REST API로 최근 포스트 조회, 실패 시 RSS 피드로 백업"""
    url = f'{WP_BASE_URL}/wp-json/wp/v2/posts'
    params = {
        'per_page': count,
        'status': 'publish',
        'orderby': 'date',
        'order': 'desc',
    }
    resp = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=15)
    print(f'[WP REST] status={resp.status_code}')
    try:
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        print(f'[WP REST] failed: {exc}')
        print(f'[WP REST] body={resp.text[:500]}')
        print('[WP REST] RSS 피드로 다시 조회합니다.')
        return fetch_posts_from_feed(min(count, 10))


def pick_post(posts: list) -> dict:
    """시간대별로 1/2/3번째 최신 포스트 선택"""
    hour = datetime.now(KST).hour
    index = 0 if hour < 12 else 1 if hour < 17 else 2
    return posts[min(index, len(posts) - 1)]


def send_push(title: str, body: str, link: str) -> bool:
    """스윙투앱 전체 구독자 푸시 발송 (multipart/form-data)"""
    payload = {
        'app_id':           APP_ID,
        'app_api_key':      API_KEY,
        'send_target_list': '-1',    # 전체 발송
        'send_type':        'push',
        'message_title':    title,
        'message_content':  body,
        'message_link_url': link,
    }
    resp = requests.post(SWING_PUSH_URL, data=payload, timeout=15)
    print(f'[Push API] status={resp.status_code}  body={resp.text[:300]}')
    try:
        result = resp.json()
        r = result.get('result')
        # API가 boolean true 또는 문자열 "true"/"t"/1 등으로 반환하는 경우 모두 처리
        return r is True or str(r).lower() in ('true', 't', '1')
    except Exception:
        return resp.status_code == 200


def clean_html(text: str) -> str:
    import re
    return html.unescape(re.sub(r'<[^>]+>', '', text)).strip()


def main():
    now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')
    print(f'[{now_str}] 지원금알리미 자동 푸시 시작')

    posts = get_posts()
    if not posts:
        print('포스트 없음 - 종료')
        sys.exit(0)

    post  = pick_post(posts)
    tmpl_title, tmpl_body = get_template()

    push_title = f'{tmpl_title}: {clean_html(post["title"]["rendered"])}'
    push_body  = tmpl_body
    push_link  = post['link']

    print(f'선택된 포스트: {push_title}')
    print(f'URL: {push_link}')

    ok = send_push(push_title, push_body, push_link)
    if ok:
        print('✅ 푸시 발송 성공')
    else:
        print('❌ 푸시 발송 실패')
        sys.exit(1)


if __name__ == '__main__':
    main()
