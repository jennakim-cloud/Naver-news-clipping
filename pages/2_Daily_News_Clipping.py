# ============================================================
#  네이버 뉴스 클리핑 v4 - Streamlit 앱
#
#  실행 방법:
#    pip install streamlit requests beautifulsoup4 pandas xlsxwriter
#    streamlit run naver_news_clipping_streamlit.py
# ============================================================

import io
import re
import html
import time
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

# ══════════════════════════════════════════════════════════════
#  설정값
# ══════════════════════════════════════════════════════════════

MAX_WORKERS     = 10
REQUEST_TIMEOUT = 6
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    )
}

GROUP_COLORS = {
    "그룹 A": "#D5F5E3",
    "그룹 B": "#FEF9E7",
    "그룹 C": "#FDEBD0",
    "":       "#FFFFFF",
}

# ── 그룹 배지 색상 (Streamlit 테이블용 HTML) ─────────────────
GROUP_BADGE = {
    "그룹 A": "background:#D5F5E3; color:#1e7e34; padding:2px 8px; border-radius:4px; font-weight:bold;",
    "그룹 B": "background:#FEF9E7; color:#856404; padding:2px 8px; border-radius:4px; font-weight:bold;",
    "그룹 C": "background:#FDEBD0; color:#c05621; padding:2px 8px; border-radius:4px; font-weight:bold;",
    "":       "color:#999; padding:2px 8px;",
}

# ══════════════════════════════════════════════════════════════
#  매핑 테이블
# ══════════════════════════════════════════════════════════════

FIXED_MAP = {
    "1conomynews": "1코노미뉴스",
    "cctimes": "충청타임즈",
    "chungnamilbo": "충남일보",
    "dtnews24": "대전뉴스",
    "enetnews": "이넷뉴스",
    "financialreview": "파이낸셜리뷰",
    "globalepic": "글로벌에픽",
    "gokorea": "고코리아",
    "goodmorningcc": "굿모닝충청",
    "hinews": "하이뉴스",
    "idaegu": "아이대구",
    "joongdo": "중도일보",
    "kdfnews": "한국면세뉴스",
    "ktnews": "강원타임즈",
    "newslock": "뉴스락",
    "newsway": "뉴스웨이",
    "opinionnews": "오피니언뉴스",
    "startuptoday": "스타트업투데이",
    "straightnews": "스트레이트뉴스",
    "tfmedia": "조세금융신문",
    "weekly": "주간한국",
    "wolyo": "월요신문",
    "womaneconomy": "여성경제신문",
    "lawissue": "로이슈", "newsworker": "뉴스워커", "topdaily": "톱데일리",
    "wikitree": "위키트리", "thepublic": "더퍼블릭", "thebigdata": "빅데이터뉴스",
    "socialvalue": "소셜밸류", "smartfn": "스마트에프엔", "sisacast": "시사캐스트",
    "siminilbo": "시민일보", "seoultimes": "서울타임즈", "sentv": "서울경제TV",
    "segyebiz": "세계비즈", "pressman": "프레스맨", "popcornnews": "팝콘뉴스",
    "pointe": "포인트데일리", "onews": "열린뉴스통신", "nextdaily": "넥스트데일리",
    "newswatch": "뉴스워치", "newsquest": "뉴스퀘스트", "newsprime": "뉴스프라임",
    "newsinside": "뉴스인사이드", "mkhealth": "매경헬스", "metroseoul": "메트로신문",
    "meconomynews": "M이코노미", "kbsm": "경북신문", "joongangenews": "중앙이코노미뉴스",
    "iminju": "민주신문", "ilyo": "일요신문", "hankooki": "스포츠한국",
    "ezyeconomy": "이지경제", "enewstoday": "이뉴스투데이", "ekn": "에너지경제",
    "dizzotv": "디지틀조선일보", "cstimes": "컨슈머타임스",
    "consumernews": "소비자가만드는신문", "ceoscoredaily": "CEO스코어데일리",
    "breaknews": "브레이크뉴스", "bizwnews": "비즈월드", "beyondpost": "비욘드포스트",
    "asiatime": "아시아타임즈", "apnews": "아시아에이", "newdaily": "뉴데일리",
    "viva100": "브릿지경제", "srtimes": "SR타임스", "kpenews": "한국정경신문",
    "news2day": "뉴스투데이", "fashionbiz": "패션비즈", "econovill": "이코노믹리뷰",
    "businessplus": "비즈니스플러스", "newspim": "뉴스핌", "m-i": "매일일보",
    "pointdaily": "포인트데일리", "ajunews": "아주경제", "asiatoday": "아시아투데이", "xportsnews": "엑스포츠뉴스", "sports": "엑스포츠뉴스", "kukinews": "쿠키뉴스", "youthdaily": "청년일보",
    "seoulwire": "서울와이어", "newstomato": "뉴스토마토", "widedaily": "와이드경제",
    "apparelnews": "어패럴뉴스", "biztribune": "비즈트리뷴", "etoday": "이투데이", "edaily": "이데일리",
    "ngetnews": "뉴스저널리즘", "hansbiz": "한스경제", "byline": "바이라인네트워크",
    "dealsite": "딜사이트", "businesspost": "비즈니스포스트", "dnews": "대한경제",
    "insight": "인사이트", "slist": "싱글리스트", "theviewers": "뷰어스",
    "daily": "데일리한국", "veritas-a": "베리타스알파", "fortunekorea": "포춘코리아",
    "huffingtonpost": "허프포스트", "mediapen": "미디어펜", "paxetv": "팍스경제TV",
    "shinailbo": "신아일보", "pinpointnews": "핀포인트뉴스", "sisunnews": "시선뉴스",
    "sisaon": "시사온", "smarttoday": "스마트투데이", "ziksir": "직썰",
    "job-post": "잡포스트", "issuenbiz": "이슈앤비즈", "fashionn": "패션엔",
    "thebell": "더벨", "ftoday": "파이낸셜투데이", "newspost": "뉴스포스트",
    "econonews": "이코노뉴스", "thevaluenews": "더밸류뉴스", "megaeconomy": "메가경제", "greened": "녹색경제신문", "sisajournal-e": "시사저널이코노미", "digitaltoday": "디지털투데이"
}

OID_MAP = {
    "001": "연합뉴스", "002": "프레시안", "003": "뉴시스", "004": "내일신문",
    "005": "국민일보", "008": "머니투데이", "009": "매일경제", "011": "서울경제",
    "014": "파이낸셜뉴스", "015": "한국경제", "016": "헤럴드경제", "018": "이데일리",
    "020": "동아일보", "021": "문화일보", "022": "세계일보", "023": "조선일보",
    "025": "중앙일보", "028": "한겨레", "029": "디지털타임스", "030": "전자신문",
    "031": "아이뉴스24", "032": "경향신문", "034": "이코노미스트", "038": "한국일보",
    "052": "YTN", "055": "SBS", "056": "KBS", "057": "MBN", "065": "스포츠서울",
    "076": "스포츠조선", "079": "노컷뉴스", "081": "서울신문", "082": "부산일보",
    "088": "매일신문", "092": "지디넷코리아", "117": "마이데일리", "119": "데일리안",
    "123": "조세일보", "138": "디지털데일리", "143": "쿠키뉴스", "144": "스포츠월드",
    "214": "MBC", "215": "한국경제TV", "241": "시사IN", "243": "이코노미스트",
    "277": "아시아경제", "584": "아시아투데이", "584": "아시아투데이", "293": "블로터", "321": "브릿지경제", "323": "한국섬유신문",
    "324": "이투데이", "329": "뉴데일리", "366": "조선비즈", "374": "SBS Biz",
    "383": "한국정경신문", "410": "어패럴뉴스", "417": "머니S", "421": "뉴스1",
    "437": "JTBC", "445": "대한경제", "448": "서울와이어", "449": "TV조선",
    "465": "여성경제신문", "468": "스포츠경향", "512": "뉴스핌", "529": "싱글리스트",
    "586": "시사저널e", "629": "뉴스토마토", "645": "아주경제", "648": "비즈워치",
    "654": "비즈트리뷴", "658": "뷰어스", "660": "청년일보", "929": "디지털투데이",
    "239": "바이라인네트워크", "273": "패션비즈",
}

GROUP_MAP = {
    "1코노미뉴스":"그룹 B","CBS노컷뉴스":"그룹 A","CEO스코어데일리":"그룹 C",
    "EBN":"그룹 B","FETV":"그룹 C","IT조선":"그룹 C","KBS":"그룹 A",
    "K패션뉴스":"그룹 C","MBC":"그룹 A","MBN":"그룹 A","S-저널":"그룹 C",
    "SBS":"그룹 A","SBS Biz":"그룹 A","SR타임스":"그룹 C","TV조선":"그룹 A",
    "YTN":"그룹 A","경향신문":"그룹 A","공공뉴스":"그룹 B","국민일보":"그룹 A",
    "국제섬유신문":"그룹 A","굿모닝경제":"그룹 C","남다른디테일":"그룹 B",
    "내일신문":"그룹 A","녹색경제신문":"그룹 C","뉴데일리":"그룹 A","뉴스1":"그룹 A",
    "뉴스워치":"그룹 C","뉴스워커":"그룹 C","뉴스웨이":"그룹 B","뉴스인사이드":"그룹 C",
    "뉴스저널리즘":"그룹 B","뉴스토마토":"그룹 C","뉴스톱":"그룹 B","뉴스투데이":"그룹 B",
    "뉴스포스트":"그룹 C","뉴스핌":"그룹 A","뉴시스":"그룹 A","뉴시안":"그룹 C",
    "대한경제":"그룹 B","더리브스":"그룹 C","더밸류뉴스":"그룹 B","더벨":"그룹 B",
    "더스쿠프":"그룹 B","더스탁":"그룹 B","더팩트":"그룹 A","더피알":"그룹 C",
    "데일리안":"그룹 A","데일리한국":"그룹 A","동아닷컴":"그룹 C","동아일보":"그룹 A",
    "동행미디어 시대":"그룹 A","디지털데일리":"그룹 A","디지털타임스":"그룹 A",
    "디지털투데이":"그룹 B","디지틀조선일보":"그룹 C","디토앤디토":"그룹 A",
    "딜사이트":"그룹 B","딜사이트TV":"그룹 C","로이슈":"그룹 B","마이데일리":"그룹 B",
    "매경이코노미":"그룹 B","매경헬스":"그룹 B","매일경제":"그룹 A",
    "매일경제 레이더M":"그룹 B","매일경제TV":"그룹 C","매일신문":"그룹 B",
    "매일일보":"그룹 B","머니투데이":"그룹 A","머니투데이방송":"그룹 A",
    "메가경제":"그룹 C","메트로신문":"그룹 C","문화일보":"그룹 A","문화저널21":"그룹 C",
    "미디어펜":"그룹 C","바이라인네트워크":"그룹 A","부산일보":"그룹 B","뷰어스":"그룹 C",
    "브릿지경제":"그룹 B","블로터":"그룹 A","비즈니스워치":"그룹 A","비즈니스포스트":"그룹 B",
    "비즈니스플러스":"그룹 B","비즈트리뷴":"그룹 C","비즈한국":"그룹 C",
    "서울경제":"그룹 A","서울경제TV":"그룹 A","서울신문":"그룹 A","서울와이어":"그룹 C",
    "서울파이낸스":"그룹 C","세계비즈":"그룹 C","세계일보":"그룹 A",
    "소비자가만드는신문":"그룹 B","소셜밸류":"그룹 C","스마트투데이":"그룹 C",
    "스트레이트뉴스":"그룹 C","스포츠조선":"그룹 B","스포츠한국":"그룹 B",
    "시사오늘":"그룹 C","시사위크":"그룹 C","시사저널이코노미":"그룹 C","시사캐스트":"그룹 C",
    "신아일보":"그룹 C","싱글리스트":"그룹 C","아시아경제":"그룹 A","아시아타임즈":"그룹 B",
    "아시아투데이":"그룹 A","아웃스탠딩":"그룹 A","아이뉴스24":"그룹 A","아주경제":"그룹 A",
    "아주일보":"그룹 C","알파경제":"그룹 B","약업신문":"그룹 C","어패럴뉴스":"그룹 A",
    "에너지경제":"그룹 B","여성경제신문":"그룹 C","연합 인포맥스":"그룹 B",
    "연합뉴스":"그룹 A","연합뉴스TV":"그룹 A","오늘경제":"그룹 C","월요신문":"그룹 B",
    "위키리크스한국":"그룹 B","위키트리":"그룹 C","이뉴스투데이":"그룹 B","이데일리":"그룹 A",
    "이코노미스트":"그룹 B","이코노믹리뷰":"그룹 B","이투데이":"그룹 A",
    "인베스트조선":"그룹 B","인사이트":"그룹 C","인사이트코리아":"그룹 B",
    "일간스포츠":"그룹 B","일요서울":"그룹 C","일요신문":"그룹 C","전자신문":"그룹 A",
    "조선비즈":"그룹 A","조선일보":"그룹 A","주간한국":"그룹 B","중소기업신문":"그룹 C",
    "중앙선데이":"그룹 A","중앙이코노미뉴스":"그룹 C","중앙일보":"그룹 A",
    "지디넷코리아":"그룹 A","청년일보":"그룹 C","커넥터스":"그룹 C","컨슈머타임즈":"그룹 B",
    "코리아중앙데일리":"그룹 A","코리아타임스":"그룹 A","코리아헤럴드":"그룹 A",
    "쿠키뉴스":"그룹 A","테넌트뉴스":"그룹 A","테크엠":"그룹 A","토요경제":"그룹 C",
    "톱데일리":"그룹 B","투데이신문":"그룹 B","투데이코리아":"그룹 C","파이낸셜뉴스":"그룹 A",
    "파이낸셜리뷰":"그룹 C","파이낸셜투데이":"그룹 C","파이낸셜포스트":"그룹 C",
    "팝콘뉴스":"그룹 C","패션비즈":"그룹 A","패션인사이트":"그룹 A","패션포스트":"그룹 A",
    "포인트데일리":"그룹 C","프라임경제":"그룹 C","하이뉴스":"그룹 C","한겨레":"그룹 A",
    "한경비즈니스":"그룹 B","한국경제":"그룹 A","한국경제TV":"그룹 A",
    "한국금융신문":"그룹 C","한국면세뉴스":"그룹 C","한국섬유신문":"그룹 A",
    "한국일보":"그룹 A","한국정경신문":"그룹 C","한스경제":"그룹 B","허프포스트":"그룹 C",
    "헤럴드경제":"그룹 A","현대경제신문":"그룹 C","후지TV":"그룹 C","MTN":"그룹 A",
}



# ══════════════════════════════════════════════════════════════
#  헬퍼 함수 (기존과 동일)
# ══════════════════════════════════════════════════════════════

def clean_html_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]*>', '', text)
    return text.replace('"', "'")


def publisher_from_url(link: str) -> str:
    if "naver.com" in link:
        m = re.search(r'article/(\d+)/', link)
        if m:
            oid = m.group(1).zfill(3)
            if oid in OID_MAP:
                return OID_MAP[oid]
    try:
        domain = link.split('//')[-1].split('/')[0].lower()
        domain = re.sub(r'^(www\.|n\.|news\.|m\.|blog\.|sports\.)', '', domain)
        # 긴 키워드부터 먼저 매칭 (짧은 키워드 오매핑 방지)
        for key, name in sorted(FIXED_MAP.items(), key=lambda x: -len(x[0])):
            if key in domain:
                return name
        return domain.split('.')[0].upper()
    except Exception:
        return "기타매체"



def fetch_naver_article_info(link: str) -> dict:
    result = {"publisher": publisher_from_url(link), "pick": ""}
    if "naver.com" not in link:
        return result
    try:
        res = requests.get(link, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if res.status_code != 200:
            return result
        soup = BeautifulSoup(res.text, 'html.parser')

        publisher = ""
        logo = soup.select_one('a.press_logo img, .media_end_head_top a img')
        if logo:
            publisher = logo.get('alt', '').strip()
        if not publisher:
            meta = soup.find('meta', property='og:article:author')
            if meta:
                publisher = meta.get('content', '').strip()
        if not publisher:
            press_tag = soup.select_one('.media_end_linked_more_point')
            if press_tag:
                publisher = press_tag.get_text(strip=True)
        if publisher:
            result["publisher"] = publisher

        # ── PICK 여부 ─────────────────────────────────────────
        if soup.select_one('.is_pick, .media_end_head_journalist_edit_label'):
            result["pick"] = "PICK"
        elif "PICK" in res.text:
            result["pick"] = "PICK"



    except Exception:
        pass
    return result



# ══════════════════════════════════════════════════════════════
#  외부 매체 크롤러 (네이버 미등록 4개 매체)
# ══════════════════════════════════════════════════════════════

def crawl_fi(query: str, since: datetime) -> list:
    """패션인사이트 fi.co.kr 크롤링"""
    results = []
    try:
        search_url = f"https://www.fi.co.kr/main/list.asp?search={requests.utils.quote(query)}"
        res = requests.get(search_url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.select('a[href*="view.asp"]'):
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = a['href']
            if not href.startswith('http'):
                href = 'https://www.fi.co.kr' + ('' if href.startswith('/') else '/main/') + href.lstrip('/')
            # 날짜: 상위 태그에서 탐색
            parent = a.find_parent(['li', 'div', 'tr'])
            date_txt = ''
            if parent:
                import re as _re
                m = _re.search(r'(\d{4})[.\-/](\d{2})[.\-/](\d{2})', parent.get_text())
                if m:
                    date_txt = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            pub_date = None
            if date_txt:
                try:
                    pub_date = datetime.strptime(date_txt, '%Y-%m-%d').replace(
                        tzinfo=timezone(timedelta(hours=9)))
                except Exception:
                    pass
            if pub_date and pub_date < since:
                continue
            results.append({
                "그룹": "그룹 A", "매체명": "패션인사이트",
                "제목": f'=HYPERLINK("{href}", "{title}")',
                "제목_표시": title, "링크": href,
                "PICK": "",
                "게시일": pub_date.strftime('%Y-%m-%d') if pub_date else "",
            })
    except Exception:
        pass
    return results


def crawl_itnk(query: str, since: datetime) -> list:
    """국제섬유신문 itnk.co.kr 크롤링 — 제목 키워드 필터링"""
    results = []
    try:
        search_url = f"https://www.itnk.co.kr/news/articleList.html?sc_word={requests.utils.quote(query)}&view_type=sm"
        res = requests.get(search_url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(res.text, 'html.parser')
        import re as _re
        query_tokens = [t.lower() for t in query.split() if len(t) > 1]
        for item in soup.select('li.item, div.item, .article-list li'):
            a = item.find('a', href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            if query_tokens and not any(tok in title.lower() for tok in query_tokens):
                continue
            href = a['href']
            if not href.startswith('http'):
                href = 'https://www.itnk.co.kr' + href
            m = _re.search(r"(\d{4})[.\-/](\d{2})[.\-/](\d{2})", item.get_text())
            pub_date = None
            if m:
                try:
                    pub_date = datetime.strptime(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", '%Y-%m-%d').replace(
                        tzinfo=timezone(timedelta(hours=9)))
                except Exception:
                    pass
            if pub_date and pub_date < since:
                continue
            results.append({
                "그룹": "그룹 A", "매체명": "국제섬유신문",
                "제목": f'=HYPERLINK("{href}", "{title}")',
                "제목_표시": title, "링크": href,
                "PICK": "",
                "게시일": pub_date.strftime('%Y-%m-%d') if pub_date else "",
            })
    except Exception:
        pass
    return results

def crawl_fpost(query: str, since: datetime) -> list:
    """패션포스트 fpost.co.kr 크롤링 — 목록 페이지에서 키워드 필터링"""
    results = []
    try:
        import re as _re
        # 검색 페이지와 메인 목록 페이지 모두 시도
        urls = [
            f"https://fpost.co.kr/board/bbs/search.php?bo_table=mainFsp&sfl=wr_subject&stx={requests.utils.quote(query)}",
            "https://fpost.co.kr/board/bbs/board.php?bo_table=mainFsp",
        ]
        query_tokens = [t.lower() for t in query.split() if len(t) > 1]
        seen_hrefs = set()

        for url in urls:
            try:
                res = requests.get(url, headers=HEADERS, timeout=8)
                if res.status_code != 200:
                    continue
                soup = BeautifulSoup(res.text, 'html.parser')

                # 기사 링크 선택: wr_id 파라미터 포함된 링크
                for a in soup.select('a[href*="wr_id"], a[href*="bo_table=mainFsp"]'):
                    title = a.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    # 키워드 필터
                    if query_tokens and not any(tok in title.lower() for tok in query_tokens):
                        continue
                    href = a['href']
                    if not href.startswith('http'):
                        href = 'https://fpost.co.kr' + href
                    if href in seen_hrefs:
                        continue
                    seen_hrefs.add(href)

                    # 날짜: 상위 요소에서 탐색
                    parent = a.find_parent(['li', 'div', 'tr', 'td', 'article'])
                    pub_date = None
                    if parent:
                        m = _re.search(r'(\d{4})[.\-/](\d{2})[.\-/](\d{2})', parent.get_text())
                        if m:
                            try:
                                pub_date = datetime.strptime(
                                    f"{m.group(1)}-{m.group(2)}-{m.group(3)}", '%Y-%m-%d'
                                ).replace(tzinfo=timezone(timedelta(hours=9)))
                            except Exception:
                                pass
                    if pub_date and pub_date < since:
                        continue
                    results.append({
                        "그룹": "그룹 A", "매체명": "패션포스트",
                        "제목": f'=HYPERLINK("{href}", "{title}")',
                        "제목_표시": title, "링크": href,
                        "PICK": "",
                        "게시일": pub_date.strftime('%Y-%m-%d') if pub_date else "",
                    })
            except Exception:
                continue
    except Exception:
        pass
    return results


def crawl_tnnews(query: str, since: datetime) -> list:
    """테넌트뉴스 tnnews.co.kr 크롤링 — 키워드 필터 + 날짜 파싱 강화"""
    results = []
    try:
        import re as _re
        search_url = f"https://tnnews.co.kr/?s={requests.utils.quote(query)}"
        res = requests.get(search_url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(res.text, 'html.parser')
        query_tokens = [t.lower() for t in query.split() if len(t) > 1]
        for item in soup.select('div.td-module-meta-info, div.item-details, div.td-block-span6'):
            a = item.find('a', href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            if query_tokens and not any(tok in title.lower() for tok in query_tokens):
                continue
            href = a['href']
            pub_date = None
            time_tag = item.find('time')
            if time_tag:
                dt_str = time_tag.get('datetime', '') or time_tag.get_text(strip=True)
                m = _re.search(r"(\d{4})-(\d{2})-(\d{2})", dt_str)
                if m:
                    try:
                        pub_date = datetime.strptime(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", '%Y-%m-%d').replace(
                            tzinfo=timezone(timedelta(hours=9)))
                    except Exception:
                        pass
            if not pub_date:
                m = _re.search(r"(\d{4})[.\-/](\d{2})[.\-/](\d{2})", item.get_text())
                if m:
                    try:
                        pub_date = datetime.strptime(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", '%Y-%m-%d').replace(
                            tzinfo=timezone(timedelta(hours=9)))
                    except Exception:
                        pass
            if pub_date and pub_date < since:
                continue
            results.append({
                "그룹": "그룹 A", "매체명": "테넌트뉴스",
                "제목": f'=HYPERLINK("{href}", "{title}")',
                "제목_표시": title, "링크": href,
                "PICK": "",
                "게시일": pub_date.strftime('%Y-%m-%d') if pub_date else "",
            })
    except Exception:
        pass
    return results

EXTRA_CRAWLERS = {
    "패션인사이트": crawl_fi,
    "국제섬유신문": crawl_itnk,
    "패션포스트":   crawl_fpost,
    "테넌트뉴스":   crawl_tnnews,
}

def build_excel(df: pd.DataFrame) -> bytes:
    """DataFrame → 서식 적용 엑셀 바이트 반환"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='뉴스클리핑')
        workbook  = writer.book
        worksheet = writer.sheets['뉴스클리핑']

        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#2C3E50', 'font_color': '#FFFFFF',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
        })
        for col_num, col_name in enumerate(df.columns):
            worksheet.write(0, col_num, col_name, header_fmt)

        col_widths = {"그룹": 8, "매체명": 16, "제목": 60, "PICK": 6, "게시일": 18}
        for col_num, col_name in enumerate(df.columns):
            worksheet.set_column(col_num, col_num, col_widths.get(col_name, 12))

        border_fmt_cache = {}
        for row_num, row in df.iterrows():
            group = row["그룹"]
            color = GROUP_COLORS.get(group, "#FFFFFF")
            if color not in border_fmt_cache:
                border_fmt_cache[color] = workbook.add_format({
                    'bg_color': color, 'border': 1, 'valign': 'vcenter',
                })
            cell_fmt = border_fmt_cache[color]
            excel_row = row_num + 1
            for col_num, col_name in enumerate(df.columns):
                value = row[col_name]
                if col_name == "제목":
                    worksheet.write_formula(excel_row, col_num, value, cell_fmt)
                else:
                    worksheet.write(excel_row, col_num, value, cell_fmt)

        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

    return output.getvalue()


# ══════════════════════════════════════════════════════════════
#  핵심 수집 로직 (Streamlit progress bar와 연동)
# ══════════════════════════════════════════════════════════════

def run_search(query: str, client_id: str, client_secret: str,
               progress_bar, status_text, days: int = 7) -> pd.DataFrame | None:

    naver_headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    since = now - timedelta(days=days)

    # ── Step 1: API 수집 ──────────────────────────────────────
    raw_items = []
    status_text.text(f"🔍 '{query}' 기사 수집 중...")
    progress_bar.progress(5)

    for start_index in [1, 101]:
        url = (
            f"https://openapi.naver.com/v1/search/news.json"
            f"?query={query}&display=100&start={start_index}&sort=date"
        )
        try:
            res = requests.get(url, headers=naver_headers, timeout=10)
            if res.status_code != 200:
                st.error(f"네이버 API 오류: {res.status_code} — API 키를 확인해주세요.")
                return None

            items = res.json().get('items', [])
            if not items:
                break

            stop_early = False
            for item in items:
                pub_date = datetime.strptime(
                    item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900'
                ).replace(tzinfo=kst)
                if pub_date < since:
                    stop_early = True
                    break
                raw_items.append({
                    "pub_date": pub_date,
                    "link": item.get('link', ''),
                    "title": clean_html_text(item.get('title', '')),
                })
            if stop_early:
                break
            time.sleep(0.2)

        except Exception as e:
            st.error(f"API 요청 오류: {e}")
            return None

    if not raw_items:
        st.warning("검색 결과가 없습니다.")
        return None

    status_text.text(f"📰 {len(raw_items)}개 기사 수집 완료 — 매체명 · PICK 크롤링 중...")
    progress_bar.progress(20)

    # ── Step 2: 병렬 크롤링 ───────────────────────────────────
    crawl_results = {}
    total = len(raw_items)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {
            executor.submit(fetch_naver_article_info, item["link"]): idx
            for idx, item in enumerate(raw_items)
        }
        done = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                crawl_results[idx] = future.result()
            except Exception:
                crawl_results[idx] = {
                    "publisher": publisher_from_url(raw_items[idx]["link"]),
                    "pick": ""
                }
            done += 1
            pct = 20 + int(done / total * 70)   # 20~90% 구간
            progress_bar.progress(pct)
            status_text.text(f"🔄 크롤링 진행: {done} / {total}")

    # ── Step 3: DataFrame 구성 ────────────────────────────────
    status_text.text("📊 데이터 정리 중...")
    progress_bar.progress(95)

    news_data = []
    for idx, item in enumerate(raw_items):
        info      = crawl_results.get(idx, {})
        publisher = info.get("publisher", "기타매체")
        pick_val  = info.get("pick", "")
        group_val = GROUP_MAP.get(publisher, "")
        link      = item["link"]
        title     = item["title"].replace('"', "'")
        news_data.append({
            "그룹":   group_val,
            "매체명": publisher,
            "제목":   f'=HYPERLINK("{link}", "{title}")',
            "제목_표시": title,   # 화면 표시용 (수식 없는 버전)
            "링크":   link,
            "PICK":   pick_val,
            "게시일": item["pub_date"].strftime('%Y-%m-%d %H:%M'),
        })

    progress_bar.progress(100)
    status_text.text("✅ 완료!")
    return pd.DataFrame(news_data)


# ══════════════════════════════════════════════════════════════
#  Streamlit UI
# ══════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════
#  섹션 정의
# ════════════════════════════════════════════════════════════

# 섹션별 제목 노이즈 필터 — 키워드가 다른 의미로 쓰인 기사 제외
SECTION_NOISE_FILTER = {
    "패션 업계": ["주가", "증시", "코스피", "코스닥", "주식", "배당", "공시", "매출채권", "채권"],
    "유통 업계": ["주가", "증시", "코스피", "코스닥", "주식", "배당", "공시"],
    "IT 업계":   ["주가", "증시", "코스피", "코스닥", "주식", "배당", "공시", "네이버지도", "카카오맵"],
    "패션 플랫폼": ["주가", "증시", "코스피", "코스닥", "주식", "배당", "공시"],
    "무신사": [],
}

SECTIONS = [
    ("무신사", [
        "무신사", "29CM", "MUSINSA",
    ]),
    ("패션 업계", [
        "패션 업계", "유니클로", "패션 브랜드",
        "하고하우스", "LF", "신세계 인터내셔날", "삼성물산 패션",
        "F&F", "영원무역", "한섬", "이랜드",
    ]),
    ("유통 업계", [
        "쿠팡", "컬리", "백화점", "유통업계", "공정위", "올리브영",
    ]),
    ("IT 업계", [
        "네이버", "카카오", "토스", "배달앱", "온플법",
    ]),
    ("패션 플랫폼", [
        "W컨셉", "에이블리", "지그재그", "네이버 크림", "차란", "패션 플랫폼", "명품 플랫폼",
    ]),
]

# ════════════════════════════════════════════════════════════
#  Streamlit 페이지 설정
# ════════════════════════════════════════════════════════════

st.set_page_config(page_title="Daily News Clipping", page_icon="📋", layout="wide")

try:
    client_id     = st.secrets["naver"]["client_id"]
    client_secret = st.secrets["naver"]["client_secret"]
except Exception:
    import os
    client_id     = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")


def collect_section(section_name: str, keywords: list, days: int, global_seen: set = None) -> list:
    """섹션별 기사 수집 — 키워드별 수집 후 링크 기준 중복 제거 (섹션 간 포함)"""
    naver_headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    kst        = timezone(timedelta(hours=9))
    since      = datetime.now(kst) - timedelta(days=days)
    seen_links = global_seen if global_seen is not None else set()
    items      = []

    for keyword in keywords:
        for start_idx in [1, 101]:   # 키워드당 최대 200개 수집
            try:
                url = (
                    f"https://openapi.naver.com/v1/search/news.json"
                    f"?query={requests.utils.quote(keyword)}&display=100&start={start_idx}&sort=date"
                )
                res = requests.get(url, headers=naver_headers, timeout=10)
                if res.status_code != 200:
                    break
                api_items = res.json().get("items", [])
                if not api_items:
                    break
                stop_early = False
                for item in api_items:
                    pub_date = datetime.strptime(
                        item["pubDate"], "%a, %d %b %Y %H:%M:%S +0900"
                    ).replace(tzinfo=kst)
                    if pub_date < since:
                        stop_early = True
                        break
                    link         = item.get("link", "")
                    original_link = item.get("originallink", "")
                    # 중복 체크: 섹션 내 + 섹션 간 (global_seen)
                    dedup_key = link or original_link
                    if dedup_key in seen_links:
                        continue
                    if global_seen is not None and dedup_key in global_seen:
                        continue
                    seen_links.add(dedup_key)
                    if global_seen is not None:
                        global_seen.add(dedup_key)
                    title       = clean_html_text(item.get("title", ""))
                    description = clean_html_text(item.get("description", ""))
                    # 매체명: naver link로 OID 추출 우선, 안 되면 originallink로 도메인 매핑
                    publisher = publisher_from_url(link)
                    if publisher and publisher == publisher_from_url(original_link):
                        pass  # 일치하면 그대로
                    elif "naver.com" not in link and original_link:
                        # naver link가 아닌 경우 originallink로 재시도
                        pub2 = publisher_from_url(original_link)
                        if pub2 and pub2 != publisher:
                            publisher = pub2
                    # 표시 링크: naver 링크 우선 (클릭 시 네이버로)
                    display_link = link if link else original_link
                    # 그룹 A/B/C 매체만 수집 (미분류 제외), 특정 매체 제외
                    if GROUP_MAP.get(publisher, "") == "":
                        continue
                    if publisher == "중앙이코노미뉴스":
                        continue
                    # 섹션별 노이즈 필터: 제목에 노이즈 단어 포함 시 제외
                    noise_words = SECTION_NOISE_FILTER.get(section_name, [])
                    if noise_words and any(nw in title for nw in noise_words):
                        continue
                    pick_val = ""  # PICK 크롤링 제거 (속도 우선)
                    items.append({
                        "섹션":        section_name,
                        "매체명":      publisher,
                        "제목":        title,
                        "링크":        display_link,
                        "요약":        "",
                        "description": description,
                        "게시일":      pub_date.strftime("%Y-%m-%d"),
                        "PICK":        pick_val,
                        "그룹":        GROUP_MAP.get(publisher, ""),
                    })
                if stop_early:
                    break
                time.sleep(0.1)
            except Exception:
                break
    return items


# ════════════════════════════════════════════════════════════
#  UI
# ════════════════════════════════════════════════════════════

st.title("📋 Daily News Clipping")
st.caption("섹션별 주요 기사를 선택하고 요약을 추가해 데일리 클리핑을 완성합니다.")

with st.sidebar:
    st.header("⚙️ 설정")
    if client_id and client_secret:
        st.success("✅ API 키 연결됨", icon="🔑")
    else:
        st.error("❌ API 키 없음")
    st.divider()
    st.markdown("**수집 기간**")
    days = st.slider("최근 며칠 기사", min_value=1, max_value=3, value=1, step=1, format="%d일")
    st.divider()
    st.markdown("**섹션별 키워드 수정**")
    st.caption("쉼표(,)로 구분해서 입력")
    custom_queries = {}
    for sec_name, sec_keywords in SECTIONS:
        default_val = ", ".join(sec_keywords)
        raw = st.text_area(sec_name, value=default_val, key=f"q_{sec_name}", height=68)
        custom_queries[sec_name] = [k.strip() for k in raw.split(",") if k.strip()]

# ── Step 1: 기사 수집 ────────────────────────────────────────
if st.button("🔍 기사 수집 시작", type="primary", use_container_width=True):
    if not client_id or not client_secret:
        st.error("API 키를 확인해주세요.")
    else:
        all_items = {}
        global_seen_links = set()  # 섹션 간 중복 제거용
        prog = st.progress(0)
        for i, (sec_name, _) in enumerate(SECTIONS):
            prog.progress(int((i / len(SECTIONS)) * 100))
            kws = custom_queries[sec_name]
            st.toast(f"수집 중: {sec_name} ({len(kws)}개 키워드)")
            all_items[sec_name] = collect_section(sec_name, kws, days, global_seen_links)
        prog.progress(100)
        # 섹션별: 게시일 최신순 + 동일 날짜 내 그룹 A 우선 정렬
        from datetime import datetime as _dt
        GROUP_ORDER = {"그룹 A": 0, "그룹 B": 1, "그룹 C": 2, "": 3}
        def _sort_key(x):
            d = x.get("게시일", "0000-00-00")
            try:
                ts = -_dt.strptime(d, "%Y-%m-%d").timestamp()  # 날짜 내림차순
            except Exception:
                ts = 0
            return (ts, GROUP_ORDER.get(x.get("그룹", ""), 3))
        for sec_name in all_items:
            all_items[sec_name].sort(key=_sort_key)
        st.session_state["daily_items"] = all_items
        st.session_state.pop("daily_done", None)
        st.success("수집 완료! 아래에서 기사를 선택하세요.")

        # 디버그: 섹션별 수집 건수 + 패션업계 전체 목록 표시
        with st.expander("🔍 수집 결과 디버그 (확인 후 삭제 예정)", expanded=True):
            for sec, its in all_items.items():
                st.markdown(f"**{sec}**: {len(its)}건")
            st.divider()
            st.markdown("**패션 업계 전체 수집 기사**")
            for it in all_items.get("패션 업계", []):
                st.caption(f"{it['그룹']} | {it['매체명']} | {it['제목'][:60]}")

# ── Step 2: 섹션별 기사 선택 ─────────────────────────────────
if "daily_items" in st.session_state:
    all_items = st.session_state["daily_items"]
    st.divider()
    st.subheader("📌 기사 선택 (섹션별 5~7개 권장)")

    selected_all = {}

    for sec_name, _ in SECTIONS:
        items = all_items.get(sec_name, [])
        st.markdown(f"### ■ {sec_name}")
        if not items:
            st.caption("수집된 기사가 없습니다.")
            selected_all[sec_name] = []
            continue

        selected_in_section = []
        for idx, item in enumerate(items[:50]):
            col_chk, col_info = st.columns([1, 11])
            with col_chk:
                checked = st.checkbox("", key=f"chk_{sec_name}_{idx}", label_visibility="collapsed")
            with col_info:
                grp   = item.get("그룹", "")
                pick  = item.get("PICK", "")
                badge_style = GROUP_BADGE.get(grp, GROUP_BADGE[""])
                grp_badge  = f"<span style='{badge_style}'>{grp if grp else '미분류'}</span> " if grp else ""
                pick_badge = "<span style='color:#e74c3c;font-weight:bold;font-size:0.8em;'>[PICK]</span> " if pick == "PICK" else ""
                st.markdown(
                    f"{grp_badge}{pick_badge}"
                    f"<a href=\"{item['링크']}\" target=\"_blank\" "
                    f"style=\"text-decoration:none;color:#1a73e8;font-weight:500;\">{item['제목']}</a> "
                    f"<span style='color:#888;font-size:0.85em;'>({item['매체명']} · {item['게시일']})</span>",
                    unsafe_allow_html=True
                )
            if checked:
                selected_in_section.append(dict(item))

        selected_all[sec_name] = selected_in_section

    st.session_state["daily_selected"] = selected_all

# ── Step 3: 요약 입력 + 클리핑 완성 ─────────────────────────
if "daily_selected" in st.session_state:
    selected_all = st.session_state["daily_selected"]
    total_selected = sum(len(v) for v in selected_all.values())

    if total_selected == 0:
        st.info("위에서 기사를 체크하면 클리핑이 생성됩니다.")
    else:
        st.divider()
        st.subheader("✏️ 요약 입력 (선택사항)")
        st.caption("각 기사 아래 입력란에 한 줄 요약을 직접 입력하세요. 비워두면 요약 없이 클리핑됩니다.")

        for sec_name, _ in SECTIONS:
            items = selected_all.get(sec_name, [])
            if not items:
                continue
            st.markdown(f"**■ {sec_name}**")
            for idx, item in enumerate(items):
                st.markdown(
                    f"<a href=\"{item['링크']}\" target=\"_blank\" "
                    f"style=\"text-decoration:none;color:#1a73e8;\">{item['제목']}</a> "
                    f"<span style='color:#888;font-size:0.85em;'>({item['매체명']})</span>",
                    unsafe_allow_html=True
                )
                item["요약"] = st.text_input(
                    "요약",
                    value=item.get("요약", ""),
                    placeholder="한 줄 요약 입력 (선택)...",
                    key=f"summary_{sec_name}_{idx}",
                    label_visibility="collapsed"
                )

        st.session_state["daily_selected"] = selected_all

        st.divider()
        if st.button("📄 클리핑 완성", type="primary", use_container_width=True):
            st.session_state["daily_done"] = True

        # ── 클리핑 미리보기 ──────────────────────────────────
        if st.session_state.get("daily_done"):
            st.divider()
            st.subheader("📄 데일리 뉴스 클리핑 미리보기")

            kst = timezone(timedelta(hours=9))
            now_kst = datetime.now(kst)
            weekdays = ["월", "화", "수", "목", "금", "토", "일"]
            weekday = weekdays[now_kst.weekday()]
            today_str = f"{now_kst.month}월 {now_kst.day}일({weekday}) 뉴스 클리핑 공유드립니다."
            st.markdown(f"**{today_str}**")

            clip_text_lines = [today_str, ""]

            for sec_name, _ in SECTIONS:
                items = selected_all.get(sec_name, [])
                if not items:
                    continue

                st.markdown(f"#### ■ {sec_name}")
                clip_text_lines.append(f"■{sec_name}")

                for item in items:
                    title   = item["제목"]
                    media   = item["매체명"]
                    link    = item["링크"]
                    summary = item.get("요약", "")

                    st.markdown(
                        f"* <a href=\"{link}\" target=\"_blank\" "
                        f"style=\"text-decoration:none;color:#1a73e8;font-weight:500;\">{title}</a> "
                        f"<span style='color:#555;font-size:0.9em;'>({media})</span>",
                        unsafe_allow_html=True
                    )
                    if summary:
                        st.markdown(
                            f"<div style='margin-left:20px;color:#444;font-size:0.88em;'>* {summary}</div>",
                            unsafe_allow_html=True
                        )

                    clip_text_lines.append(f"* {title} ({media})")
                    if summary:
                        clip_text_lines.append(f"   * {summary}")

                clip_text_lines.append("")

            st.divider()
            st.subheader("📋 텍스트 복사")
            st.caption("아래 텍스트를 복사해서 사용하세요.")
            clip_text = "\n".join(clip_text_lines)
            st.text_area("클리핑 텍스트", value=clip_text, height=400, label_visibility="collapsed")
