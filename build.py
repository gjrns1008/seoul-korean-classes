# -*- coding: utf-8 -*-
"""서울 외국인 한국어 수업 공개 페이지(index.html)를 공식 포털에서 직접 만들어 갱신한다.
 - 출처: 서울외국인포털(global.seoul.go.kr) 프로그램 목록 중 '한국어' 분류(prgrm_se_cd=KR) 전 센터
 - 로그인·API 키 불필요 (GitHub Actions 에서 실행)
 - 서울외국인주민센터(영등포) 과정과 다른 센터 과정을 구획으로 분리해 표시
 - 포털 목록 응답이 비정상(0건 등)이면 기존 index.html 을 건드리지 않고 실패 처리
수동으로 쓴 '추가 학습 경로' 구획은 extra.json 에서 읽는다(바꾸려면 이 파일만 수정)."""
import urllib.request, urllib.parse, re, html, json, sys, os, datetime, time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 'https://global.seoul.go.kr'
LIST_PAGE = BASE + '/hmpg/ecpr/prgm/prgmListPage.do'
LIST_API = BASE + '/hmpg/ecpr/prgm/prgmListPgng.do'
MAIN_CENTER = '04E34E2046394333BCC451C20A4850D9'      # 서울외국인주민센터(영등포구 도신로 40)
KST = datetime.timezone(datetime.timedelta(hours=9))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36'
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'index.html')
esc = html.escape


def fetch(url, data=None, headers=None):
    last = None
    for i in range(4):
        try:
            req = urllib.request.Request(url, data=data, headers={'User-Agent': UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            last = e; time.sleep(2 * (i + 1))
    raise RuntimeError(f'fetch failed {url}: {last}')


def clean(s):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', ' ', s))).strip()


def collect():
    fetch(LIST_PAGE)
    H = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest', 'Referer': LIST_PAGE}
    items = {}
    for page in range(1, 6):
        body = urllib.parse.urlencode({'miv_pageNo': str(page), 'miv_pageSize': '50', 'prgrm_se_cd': 'KR', 'cntr_no': '', 'prgrm_nm': ''}).encode()
        s = fetch(LIST_API, body, H)
        blocks = re.findall(r'<a href="javascript:;" onclick="goPrgmDetail\(.*?</a>', s, re.S)
        if not blocks: break
        for b in blocks:
            m = re.search(r"goPrgmDetail\('([^']+)',\s*'([^']+)'\)", b)
            t = re.search(r'<strong class="txt-22">(.*?)</strong>', b, re.S)
            if not m or not t: continue
            st = re.search(r'<span class="program-state[^>]*>(.*?)</span>', b, re.S)
            meta = {clean(k): clean(v) for k, v in re.findall(r'<span class="fc-txt fw-500">(.*?)</span>\s*<p>(.*?)</p>', b, re.S)}
            center = re.search(r'<span class="[^"]*(?:place|center|cntr)[^"]*">(.*?)</span>', b, re.S)
            items[m.group(1)] = dict(id=m.group(1), cntr=m.group(2), title=clean(t.group(1)), status=clean(st.group(1)) if st else '확인 필요',
                                     meta=meta, center=clean(center.group(1)) if center else '',
                                     url=f'{BASE}/hmpg/ecpr/prgm/prgmDetail.do?prgrm_no={m.group(1)}&cntr_no={m.group(2)}')
        if len(blocks) < 50: break
        time.sleep(0.3)
    return list(items.values())


def detail(x):
    """상세 페이지에서 센터명·신청자격·신청방법·수강료·본문(장소/시간 등)을 가져온다. 실패해도 목록 정보만으로 표시."""
    try:
        s = fetch(x['url'])
    except Exception as e:
        print('detail fail', x['id'], e); return {}
    d = {}
    for k, v in re.findall(r'<em class="fc-txt fw-500">(.*?)</em>\s*<span>(.*?)</span>', s, re.S):
        d[clean(k)] = clean(v)
    c = re.search(r'<div class="program-content[^>]*>(.*?)</div>', s, re.S)
    if c:
        txt = re.sub(r'</p>|<br\s*/?>', chr(10), c.group(1)); txt = html.unescape(re.sub(r'<[^>]+>', '', txt))
        d['_body'] = [ln.strip() for ln in txt.split(chr(10)) if ln.strip()][:12]
    return d


def parse_end(s):
    m = re.findall(r'(\d{4})[-.](\d{2})[-.](\d{2})', s or '')
    return datetime.date(*map(int, m[-1])) if m else None


def card(x, today):
    md = dict(x['meta']); d = x.get('detail') or {}
    open_ = x['status'] == '신청중'
    cls = 'open' if open_ else 'closed'
    end = parse_end(md.get('교육기간', '')); ended = bool(end and end < today)
    for k in ('수강료', '신청자격', '신청방법'):
        if d.get(k): md[k] = d[k]
    rows = ''.join(f'<p><b>{esc(k)}</b> {esc(v)}</p>' for k, v in md.items() if v)
    body = ''.join(f'<p class="meta">{esc(l)}</p>' for l in d.get('_body', [])[1:] if l)
    extra = ' <span class="tag closed">교육 종료</span>' if ended and not open_ else ''
    return (f'<article class="card"><span class="tag {cls}">{esc(x["status"])}</span>{extra}'
            f'<h3>{esc(x["title"])}</h3>{rows}{body}'
            f'<a class="btn" href="{esc(x["url"])}" target="_blank" rel="noopener">서울시 공식 공고</a></article>')


def main():
    items = collect()
    print('collected', len(items))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as ex:
        for x, d in zip(items, ex.map(detail, items)): x['detail'] = d
    print('detail ok', sum(1 for x in items if x.get('detail')))
    if len(items) < 5:
        sys.exit(f'목록 {len(items)}건: 포털 응답 이상으로 보고 갱신하지 않습니다')
    now = datetime.datetime.now(KST); today = now.date()
    main_items = [x for x in items if x['cntr'] == MAIN_CENTER]
    others = [x for x in items if x['cntr'] != MAIN_CENTER]
    order = lambda x: (0 if x['status'] == '신청중' else 1, -(parse_end(x['meta'].get('신청기간', '')) or datetime.date(2000, 1, 1)).toordinal(), x['title'])
    main_items.sort(key=order); others.sort(key=order)
    n_open = sum(1 for x in items if x['status'] == '신청중')
    n_open_main = sum(1 for x in main_items if x['status'] == '신청중')

    # 센터별 묶음: 같은 센터 코드 -> 센터명이 응답에 없어서 코드 앞 8자리로 구분, 목록 페이지에서 이름 매핑을 시도
    names = {}
    try:
        lp = fetch(LIST_PAGE)
        for code, nm in re.findall(r'value="([0-9A-F]{32})"[^>]*>\s*([^<]{2,30})<', lp): names[code] = clean(nm)
    except Exception: pass
    groups = {}
    for x in others: groups.setdefault(x['cntr'], []).append(x)

    extra = []
    ep = os.path.join(HERE, 'extra.json')
    if os.path.exists(ep): extra = json.load(open(ep, encoding='utf-8'))

    parts = []
    parts.append(f'<section><h2>서울외국인주민센터 · 한국어 수업 <span class="muted">({len(main_items)}건 · 신청중 {n_open_main}건)</span></h2>')
    parts.append('<div class="grid">' + (''.join(card(x, today) for x in main_items) or '<p class="muted">현재 포털에 등록된 한국어 과정이 없습니다.</p>') + '</div>')
    parts.append('<p class="meta">문의: 한국어 02-2229-4921 · 다국어 02-2229-4900 · 서울 영등포구 도신로 40</p></section>')
    parts.append(f'<section><h2>서울의 다른 센터 한국어 수업 <span class="muted">({len(others)}건 · 신청중 {n_open - n_open_main}건)</span></h2>')
    for code, lst in sorted(groups.items(), key=lambda kv: (0 if any(x['status'] == '신청중' for x in kv[1]) else 1, kv[0])):
        label = next((x['detail'].get('센터') for x in lst if x.get('detail', {}).get('센터')), None) or names.get(code) or f'센터 {code[:8]}'
        parts.append(f'<h3 class="center">{esc(label)}</h3><div class="grid">' + ''.join(card(x, today) for x in lst) + '</div>')
    parts.append('</section>')
    if extra:
        parts.append('<section><h2>추가 학습 경로</h2><div class="grid">' + ''.join(
            f'<article class="card"><span class="tag other">{esc(e.get("tag",""))}</span><h3>{esc(e["title"])}</h3><p>{esc(e.get("text",""))}</p>' +
            ''.join(f'<a class="btn" href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l["label"])}</a>' for l in e.get('links', [])) + '</article>' for e in extra) + '</div></section>')
    parts.append('<section class="section"><h2>갱신 방식</h2><ul class="list">'
                 '<li>GitHub Actions가 매일 <b>20:00 KST</b>에 서울외국인포털의 한국어 분류 프로그램 목록(전 센터)을 조회해 이 페이지를 다시 만듭니다. PC가 꺼져 있어도 동작합니다.</li>'
                 '<li>목록의 접수 상태·신청기간·교육기간·정원은 포털 값을 그대로 옮긴 것입니다. 수업 시간·장소·문의처 등 상세 내용은 각 카드의 공식 공고에서 확인하세요.</li>'
                 '<li>서울외국인주민센터(영등포) 과정과 다른 센터 과정은 구획으로 분리했습니다.</li>'
                 '<li>포털에 한국어 분류로 올라오지 않은 공지(예: 일부 센터의 자체 게시판 공지)는 이 페이지에 나오지 않을 수 있습니다.</li></ul></section>'
                 '<section><h2>출처</h2><ul class="list"><li><a href="https://global.seoul.go.kr/hmpg/ecpr/prgm/prgmListPage.do" target="_blank" rel="noopener">서울외국인포털 프로그램 신청 목록</a></li></ul></section>')
    tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
    stamp = now.strftime('%Y-%m-%d %H:%M KST')
    summary = (f'서울외국인주민센터 한국어 과정 <b>{len(main_items)}건 중 신청중 {n_open_main}건</b>, 서울 다른 센터 포함 전체 <b>{len(items)}건 중 신청중 {n_open}건</b>입니다. '
               f'접수 상태는 {stamp} 기준 포털 값입니다.')
    out = tpl.replace('__WHEN__', stamp).replace('__SUMMARY__', summary).replace('__BODY__', '\n'.join(parts))
    open(OUT, 'w', encoding='utf-8', newline='').write(out)
    json.dump(items, open(os.path.join(HERE, 'programs.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('wrote', OUT, len(out), 'bytes | open', n_open, '| main', len(main_items), '| others', len(others), 'centers', len(groups))


main()
