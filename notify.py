#!/usr/bin/env python3
"""Telegram 한 줄 알림. 사용: python notify.py "메시지"
TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 없으면 조용히 건너뛴다(알림 실패가 갱신 작업을 실패시키지 않게)."""
import os, sys, urllib.parse, urllib.request

tok, chat = os.environ.get('TELEGRAM_BOT_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
msg = sys.argv[1] if len(sys.argv) > 1 else '업데이트 완료'
if not (tok and chat):
    print('telegram: not configured'); sys.exit(0)
try:
    data = urllib.parse.urlencode({'chat_id': chat, 'text': msg, 'disable_web_page_preview': 'true'}).encode()
    with urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data, timeout=30) as r:
        print('telegram:', 'sent' if r.status == 200 else r.status)
except Exception as e:
    print('telegram: failed', type(e).__name__)
