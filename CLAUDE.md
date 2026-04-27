# 지원금알리미 프로젝트 가이드

## 프로젝트 개요
benefit24.aqmme.com - 복지·지원금 정보 제공 서비스
스윙투앱 웹뷰 앱 (Android/iOS) + WordPress 기반 웹사이트

- **작업 디렉토리**: E:\projects\voucheralarm
- **사이트**: benefit24.aqmme.com (WordPress)
- **앱 플랫폼**: 스윙투앱 (Swing2App) 웹뷰형
- **수익화**: 구글 애드센스 (aqmme.com 승인 도메인의 하위 도메인)

## 기술 스택
- CMS: WordPress (WP Code 플러그인으로 PHP/CSS 스니펫 관리)
- 앱: 스윙투앱 웹뷰 (swingWebViewPlugin JS API 활용)
- 자동화: GitHub Actions (하루 3회 푸시 알림 발송)
- 스크립트: Python 3.11+ (scripts/send_push.py)

## 프로젝트 구조
```
e:\projects\voucheralarm\
  .github/
    workflows/
      daily-push.yml       - 자동 푸시 알림 워크플로우
  scripts/
    send_push.py           - WP REST API 조회 + 스윙투앱 푸시 발송
  스윙투앱 도움말.txt       - 스윙투앱 JS API 레퍼런스
  CLAUDE.md
```

## WordPress WP Code 스니펫 목록
- **PHP**: `benefit24_home` 숏코드 - 메인 홈페이지 카드형 레이아웃
- **CSS**: 메인 홈 디자인 (50대 이상 최적화, Noto Sans KR)
- **HTML**: 앱 알림 권한 팝업 (스윙투앱 isNotificationEnabled 연동)

## GitHub Actions 자동 푸시 스케줄
- 오전 8시 KST (23:00 UTC)
- 오후 1시 KST (04:00 UTC)
- 오후 7시 KST (10:00 UTC)

## GitHub Secrets 설정 목록
| Secret 이름 | 설명 |
|---|---|
| WP_BASE_URL | https://benefit24.aqmme.com |
| SWING2APP_APP_ID | 스윙투앱 앱 ID (관리자 패널 확인) |
| SWING2APP_API_KEY | 스윙투앱 API Key (관리자 패널 확인) |

## 스윙투앱 API 확인 경로
스윙투앱 관리자 > 앱관리 > 앱제작 > API 설정 메뉴에서 App ID, API Key 확인

## 주의사항
- .env 파일 또는 API 키를 절대 Git 커밋하지 말 것
- 스윙투앱 푸시 API 엔드포인트는 변경될 수 있으므로 공식 문서 최우선
- 애드센스 정책 준수: 클릭 유도 문구 금지, 콘텐츠 품질 유지
- 커밋 메시지 한글 작성 (예: feat: 메인 홈 카드 레이아웃 추가)