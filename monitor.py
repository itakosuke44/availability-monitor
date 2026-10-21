"""Rendered-calendar monitor. Personal configuration belongs in Actions secrets."""
import base64
import hashlib
import io
import json
import os
import re
import smtplib
import ssl
import sys
from datetime import date, datetime
from email.message import EmailMessage
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet
from PIL import Image

URL = 'https://museum-tickets.nintendo.com/calendar'
STATE_PATH = '.monitor-state.enc'
STAGE = 'configuration'
JST = ZoneInfo('Asia/Tokyo')


def symbol(png):
    """Fail closed unless screenshot pixels form a dash or a hollow circle."""
    im = Image.open(io.BytesIO(png)).convert('RGB')
    points = {(x, y) for y in range(im.height) for x in range(im.width)
              if max(im.getpixel((x, y))) < 210}
    if not points:
        return 'unknown'
    x0, x1 = min(x for x, y in points), max(x for x, y in points)
    y0, y1 = min(y for x, y in points), max(y for x, y in points)
    w, h = x1-x0+1, y1-y0+1
    if w >= 8 and h <= 4 and w >= h*3:
        return 'soldout'
    if w < 8 or h < 8 or not 0.8 <= w/h <= 1.2:
        return 'unknown'
    # Circle must enclose a white centre and have ink on all four edges.
    cx, cy = (x0+x1)/2, (y0+y1)/2
    if any(abs(x-cx) < w*.18 and abs(y-cy) < h*.18 for x, y in points):
        return 'unknown'
    sides = [any(abs(x-cx)<w*.2 and y<y0+h*.25 for x,y in points),
             any(abs(x-cx)<w*.2 and y>y1-h*.25 for x,y in points),
             any(abs(y-cy)<h*.2 and x<x0+w*.25 for x,y in points),
             any(abs(y-cy)<h*.2 and x>x1-w*.25 for x,y in points)]
    return 'available' if all(sides) else 'unknown'


def transitions(previous, current):
    # Unknown never resets a previously notified available state.
    updated = dict(previous)
    opened = []
    for day, status in current.items():
        if status == 'unknown':
            continue
        if status == 'available' and previous.get(day) != 'available':
            opened.append(day)
        updated[day] = status
    return updated, opened


def inspect(dates):
    from playwright.sync_api import sync_playwright
    result, pictures = {}, {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale='ja-JP', timezone_id='Asia/Tokyo',
                                viewport={'width': 1365, 'height': 1000}, device_scale_factor=1)
        page.set_default_timeout(20000)
        page.goto(URL, wait_until='networkidle', timeout=60000)
        for month in sorted({d[:7] for d in dates}):
            month_num = int(month[5:])
            page.locator('.p-period__month').filter(has_text=re.compile(r'^\s*'+str(month_num)+r'月\s')).click()
            for day in [d for d in dates if d.startswith(month)]:
                cell = page.locator('td[data-date="'+day+'"]:visible')
                cell.wait_for(state='visible')
                # A fully-qualified date prevents accidentally reading another year/month.
                expected = f'{int(day[:4])}年{int(day[5:7])}月{int(day[8:])}日'
                if cell.locator('[aria-label="'+expected+'"]').count() != 1:
                    raise RuntimeError('date mismatch')
                item = cell.locator('.fc-event-main span')
                item.wait_for(state='visible')
                if item.inner_text().strip() in ('定休日', '臨時休館', '休館日'):
                    result[day] = 'closed'
                    continue
                bg = item.evaluate("e => getComputedStyle(e, '::after').backgroundImage")
                # Both the icon resource and actual rendered pixels must agree.
                kind = ('available' if 'icon_calendar_circle_primary' in bg else
                        'soldout' if 'icon_calendar_hyphen_primary' in bg else 'unknown')
                first = symbol(item.screenshot())
                page.wait_for_timeout(500)
                second = symbol(item.screenshot())
                result[day] = kind if kind == first == second else 'unknown'
                if result[day] == 'available':
                    pictures[day] = cell.screenshot()
        browser.close()
    return result, pictures


def github(method='GET', payload=None):
    req = Request('https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/contents/'+STATE_PATH,
                  method=method, headers={'Authorization': 'Bearer '+os.environ['GH_TOKEN'],
                  'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'},
                  data=json.dumps(payload).encode() if payload is not None else None)
    with urlopen(req, timeout=30) as r:
        return json.load(r)


def cipher():
    key = hashlib.sha256(('availability-monitor-state-v1:'+os.environ['SMTP_PASSWORD'].replace(' ', '')).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def load_state():
    try:
        obj = github()
    except HTTPError as e:
        if e.code == 404:
            return {}, None
        raise
    return json.loads(cipher().decrypt(base64.b64decode(obj['content']))), obj['sha']


def save_state(state, sha):
    encrypted = cipher().encrypt(json.dumps(state, sort_keys=True).encode())
    payload = {'message': 'Update encrypted monitor state', 'content': base64.b64encode(encrypted).decode()}
    if sha:
        payload['sha'] = sha
    github('PUT', payload)


def mail(subject, body, pictures=None):
    global STAGE
    STAGE = 'send email'
    msg = EmailMessage()
    msg['From'] = os.environ['SMTP_USER']
    msg['To'] = os.environ.get('NOTIFY_EMAIL') or os.environ['SMTP_USER']
    msg['Subject'] = subject
    msg.set_content(body)
    for day, png in (pictures or {}).items():
        msg.add_attachment(png, maintype='image', subtype='png', filename=day+'.png')
    STAGE = 'connect Gmail STARTTLS'
    with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        STAGE = 'authenticate Gmail'
        smtp.login(os.environ['SMTP_USER'].strip(), ''.join(os.environ['SMTP_PASSWORD'].split()), initial_response_ok=False)
        STAGE = 'deliver email'
        smtp.send_message(msg)


def main():
    global STAGE
    for name in ('TARGET_DATES', 'SMTP_USER', 'SMTP_PASSWORD', 'GH_TOKEN', 'GITHUB_REPOSITORY'):
        if not os.environ.get(name):
            print('Setup incomplete: configure repository secrets. Monitoring has not started.')
            return
    dates = sorted({date.fromisoformat(s.strip()).isoformat() for s in os.environ['TARGET_DATES'].split(',')})
    dates = [d for d in dates if d >= datetime.now(JST).date().isoformat()]
    if not dates:
        print('All target dates have passed; no site request or email sent.')
        return
    STAGE = 'read encrypted state'
    state, sha = load_state()
    old = json.loads(json.dumps(state))
    try:
        STAGE = 'render calendar'
        current, pictures = inspect(dates)
        healthy = all(v != 'unknown' for v in current.values())
    except Exception as error:
        print('Calendar inspection failed: '+type(error).__name__)
        # Never print browser exceptions: selectors can contain private dates.
        current, pictures, healthy = {}, {}, False
    statuses, opened = transitions(state.get('days', {}), current)
    stamp = datetime.now(JST).strftime('%Y年%m月%d日 %H:%M:%S（日本時間）')
    if opened:
        mail('【空き枠通知】ニンテンドーミュージアム',
             '\n'.join(d+'：○（先着順販売）' for d in opened)+'\n確認日時：'+stamp+'\n'+URL,
             {d: pictures[d] for d in opened})
    state['days'] = statuses
    if healthy:
        if not state.get('started'):
            mail('【設定確認】カレンダー監視の初回確認が完了しました',
                 '空き通知ではありません。初回の画面取得・判定が成功しました。\n対象日：'+', '.join(dates)+'\n確認日時：'+stamp+'\n'+URL)
            state['started'] = True
        elif state.get('error_notified'):
            mail('【復旧】カレンダー監視', '画面の取得・判定が復旧しました。\n'+stamp+'\n'+URL)
        state['failures'] = 0
        state['error_notified'] = False
    else:
        state['failures'] = min(state.get('failures', 0)+1, 3)
        if state['failures'] >= 3 and not state.get('error_notified'):
            mail('【監視エラー】空き状況を確認できません',
                 '取得または判定が3回連続で失敗しました。売り切れを意味しません。\n'+stamp+'\n'+URL)
            state['error_notified'] = True
    if state != old:
        STAGE = 'save encrypted state'
        save_state(state, sha)
    if not healthy:
        print('Calendar could not be verified. Previous availability state preserved.')
        sys.exit(1)
    print('Calendar checked successfully. Private results are not logged.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        code = getattr(error, 'smtp_code', getattr(error, 'code', None))
        if isinstance(error, smtplib.SMTPServerDisconnected):
            detail = str(error).lower()
            print('SMTP disconnect reason: '+('timeout' if 'timed out' in detail else 'server closed connection' if 'closed' in detail else 'connection ended'))
        print('Monitor failed at '+STAGE+': '+type(error).__name__+((' code='+str(code)) if isinstance(code, int) else '')+'. No availability conclusion.')
        sys.exit(1)
