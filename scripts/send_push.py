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
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

WP_BASE_URL    = os.environ['WP_BASE_URL'].rstrip('/')
APP_ID         = os.environ['SWING2APP_APP_ID']
API_KEY        = os.environ['SWING2APP_API_KEY']

# 스윙투앱 서버 푸시 API (공식 문서 기준)
SWING_PUSH_URL = 'https://www.swing2app.com/swapi/push_api_send_message'

# 시간대별 메시지 템플릿
def get_template():
    hour = datetime.now(KST).hour
    if hour < 12:
        return '☀️ 오늘의 지원금 소식', '오늘 새로 업데이트된 복지·지원금 정보를 확인하세요!'
    elif hour < 17:
        return '💰 놓치면 손해! 지원금 알림', '신청 기간이 얼마 남지 않은 지원금이 있습니다.'
    else:
        return '🔔 저녁 지원금 소식', '오늘 하루 업데이트된 지원금·복지 혜택을 확인하세요.'


def get_posts(count: int = 6) -> list:
    """WordPress REST API로 최신 포스트 조회"""
    url = f'{WP_BASE_URL}/wp-json/wp/v2/posts'
    params = {
        'per_page': count,
        'status': 'publish',
        'orderby': 'date',
        'order': 'desc',
        '_fields': 'id,title,link,excerpt,date',
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def pick_post(posts: list) -> dict:
    """
    시간대에 따라 다른 포스트 선택:
    오전 → 최신, 오후 → 2번째, 저녁 → 3번째 (없으면 최신으로 fallback)
    """
    hour = datetime.now(KST).hour
    if hour < 12:
        idx = 0
    elif hour < 17:
        idx = 1
    else:
        idx = 2
    return posts[min(idx, len(posts) - 1)]


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
        return result.get('result') is True
    except Exception:
        return resp.status_code == 200


def clean_html(text: str) -> str:
    import re
    return html.unescape(re.sub(r'<[^>]+>', '', text)).strip()


def main():
    now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')
    print(f'[{now_str}] 지원금알리미 자동 푸시 시작')

    posts = get_posts(6)
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