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
    "weekly": "CNB저널",
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
    "asiatime": "아시아타임즈", "apnews": "아시아에이", "biz": "뉴데일리",
    "viva100": "브릿지경제", "srtimes": "SR타임스", "kpenews": "한국정경신문",
    "news2day": "뉴스투데이", "fashionbiz": "패션비즈", "econovill": "이코노믹리뷰",
    "businessplus": "비즈니스플러스", "newspim": "뉴스핌", "m-i": "매일일보",
    "pointdaily": "포인트데일리", "ajunews": "아주경제", "asiatoday": "아시아투데이", "xportsnews": "엑스포츠뉴스", "sports": "엑스포츠뉴스", "youthdaily": "청년일보",
    "seoulwire": "서울와이어", "newstomato": "뉴스토마토", "widedaily": "와이드경제",
    "apparelnews": "어패럴뉴스", "biztribune": "비즈트리뷴", "etoday": "이투데이",
    "ngetnews": "뉴스저널리즘", "hansbiz": "한스경제", "byline": "바이라인네트워크",
    "dealsite": "딜사이트", "businesspost": "비즈니스포스트", "dnews": "대한경제",
    "insight": "인사이트", "slist": "싱글리스트", "theviewers": "뷰어스",
    "daily": "데일리한국", "veritas-a": "베리타스알파", "fortunekorea": "포춘코리아",
    "huffingtonpost": "허핑턴포스트", "mediapen": "미디어펜", "paxetv": "팍스경제TV",
    "shinailbo": "신아일보", "pinpointnews": "핀포인트뉴스", "sisunnews": "시선뉴스",
    "sisaon": "시사온", "smarttoday": "스마트투데이", "ziksir": "직썰",
    "job-post": "잡포스트", "issuenbiz": "이슈앤비즈", "fashionn": "패션엔",
    "econonews": "이코노뉴스",
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
    "277": "아시아경제", "584": "아시아투데이", "293": "블로터", "321": "브릿지경제", "323": "한국섬유신문",
    "324": "이투데이", "329": "뉴데일리", "366": "조선비즈", "374": "SBS Biz",
    "383": "한국정경신문", "410": "어패럴뉴스", "417": "머니S", "421": "뉴스1",
    "437": "JTBC", "445": "대한경제", "448": "서울와이어", "449": "TV조선",
    "465": "여성경제신문", "468": "스포츠경향", "512": "뉴스핌", "529": "싱글리스트",
    "586": "시사저널e", "629": "뉴스토마토", "645": "아주경제", "648": "비즈워치",
    "654": "비즈트리뷴", "658": "뷰어스", "660": "청년일보", "929": "디지털투데이",
    "239": "바이라인네트워크", "273": "패션비즈",
}

GROUP_MAP = {
    "1코노미뉴스":"그룹 B","CBS노컷뉴스":"그룹 A","CEO 스코어데일리":"그룹 C",
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
        for key, name in FIXED_MAP.items():
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

st.set_page_config(
    page_title="네이버 뉴스 클리핑",
    page_icon="📰",
    layout="wide",
)

st.title("📰 네이버 뉴스 클리핑")
st.caption("키워드로 원하는 기간의 기사를 수집하고 엑셀로 다운로드합니다.")

# ── API 키: st.secrets 우선 → 없으면 환경변수 폴백 ──────────
# Streamlit Cloud: 앱 Settings > Secrets 에 아래 내용 추가
#   [naver]
#   client_id     = "YOUR_CLIENT_ID"
#   client_secret = "YOUR_CLIENT_SECRET"
try:
    client_id     = st.secrets["naver"]["client_id"]
    client_secret = st.secrets["naver"]["client_secret"]
except Exception:
    import os
    client_id     = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")

with st.sidebar:
    st.header("⚙️ 설정")
    if client_id and client_secret:
        st.success("✅ API 키 연결됨", icon="🔑")
    else:
        st.error("❌ API 키 없음\n`Secrets` 설정을 확인하세요.")
    st.divider()
    st.markdown("**그룹 색상 기준**")
    st.markdown(
        "<span style='background:#D5F5E3;padding:2px 8px;border-radius:4px;'>그룹 A</span> &nbsp;"
        "<span style='background:#FEF9E7;padding:2px 8px;border-radius:4px;'>그룹 B</span> &nbsp;"
        "<span style='background:#FDEBD0;padding:2px 8px;border-radius:4px;'>그룹 C</span>",
        unsafe_allow_html=True
    )
    st.caption("미분류 매체는 흰색으로 표시됩니다.")
    st.divider()
    st.markdown("**수집 기간**")
    days = st.slider("최근 며칠 기사", min_value=1, max_value=7, value=7, step=1,
                     format="%d일")

# ── 메인: 검색 입력 ───────────────────────────────────────────
col_input, col_btn = st.columns([4, 1])
with col_input:
    query = st.text_input(
        "검색어",
        placeholder="예: 패션 트렌드",
        label_visibility="collapsed"
    )
with col_btn:
    search_clicked = st.button("🔍 검색", use_container_width=True, type="primary")

# ── 검색 실행 ─────────────────────────────────────────────────
if search_clicked:
    if not query.strip():
        st.warning("검색어를 입력해주세요.")
    elif not client_id or not client_secret:
        st.error("API 키가 설정되지 않았습니다. Streamlit Secrets를 확인해주세요.")
    else:
        progress_bar = st.progress(0)
        status_text  = st.empty()

        df = run_search(query.strip(), client_id, client_secret,
                        progress_bar, status_text, days)

        if df is not None and not df.empty:
            # 세션에 저장 (그룹 필터링 등 후속 조작을 위해)
            st.session_state["df"]    = df
            st.session_state["query"] = query.strip()
            st.session_state["days"]  = days

# ── 결과 표시 ─────────────────────────────────────────────────
if "df" in st.session_state:
    df    = st.session_state["df"]
    query = st.session_state["query"]

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)

    st.divider()

    # 요약 지표
    total   = len(df)
    cnt_a   = (df["그룹"] == "그룹 A").sum()
    cnt_b   = (df["그룹"] == "그룹 B").sum()
    cnt_c   = (df["그룹"] == "그룹 C").sum()
    cnt_etc = (df["그룹"] == "").sum()
    cnt_pick = (df["PICK"] == "PICK").sum()

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("전체", f"{total}건")
    m2.metric("그룹 A", f"{cnt_a}건")
    m3.metric("그룹 B", f"{cnt_b}건")
    m4.metric("그룹 C", f"{cnt_c}건")
    m5.metric("미분류", f"{cnt_etc}건")
    m6.metric("PICK", f"{cnt_pick}건")

    st.divider()

    # 필터 컨트롤
    filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 2])
    with filter_col1:
        group_filter = st.multiselect(
            "그룹 필터",
            options=["그룹 A", "그룹 B", "그룹 C", "미분류"],
            default=["그룹 A", "그룹 B", "그룹 C", "미분류"],
        )
    with filter_col2:
        pick_filter = st.checkbox("PICK 기사만 보기", value=False)
    with filter_col3:
        keyword_filter = st.text_input("제목 키워드 필터", placeholder="추가 필터...")

    # 필터 적용
    mask = pd.Series([True] * len(df), index=df.index)

    # 그룹 필터 (미분류 = "")
    selected_groups = [("" if g == "미분류" else g) for g in group_filter]
    mask &= df["그룹"].isin(selected_groups)

    if pick_filter:
        mask &= df["PICK"] == "PICK"
    if keyword_filter.strip():
        mask &= df["제목_표시"].str.contains(keyword_filter.strip(), case=False, na=False)

    df_filtered = df[mask].reset_index(drop=True)
    st.caption(f"필터 결과: {len(df_filtered)}건")

    # ── 테이블 렌더링 (HTML) ──────────────────────────────────
    def render_table(df_view: pd.DataFrame) -> str:
        rows_html = ""
        for _, row in df_view.iterrows():
            group     = row["그룹"]
            badge_style = GROUP_BADGE.get(group, GROUP_BADGE[""])
            badge     = f'<span style="{badge_style}">{group if group else "미분류"}</span>'
            pick_html  = '<span style="color:#e74c3c;font-weight:bold;">PICK</span>' if row["PICK"] == "PICK" else ""
            title_html = f'<a href="{row["링크"]}" target="_blank" style="text-decoration:none;color:#1a73e8;">{row["제목_표시"]}</a>'
            row_bg = GROUP_COLORS.get(group, "#FFFFFF")
            rows_html += f"""
            <tr style="background:{row_bg};">
                <td style="padding:6px 10px;border-bottom:1px solid #eee;white-space:nowrap;">{badge}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;white-space:nowrap;font-weight:500;">{row["매체명"]}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;">{title_html}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:center;">{pick_html}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;white-space:nowrap;color:#666;font-size:0.85em;">{row["게시일"]}</td>
            </tr>"""

        return f"""
        <style>
            .clip-table {{ width:100%; border-collapse:collapse; font-size:0.9rem; }}
            .clip-table th {{ background:#2C3E50; color:#fff; padding:8px 10px;
                              text-align:left; position:sticky; top:0; }}
            .clip-table tr:hover {{ filter: brightness(0.96); }}
        </style>
        <div style="overflow-x:auto; max-height:600px; overflow-y:auto;">
        <table class="clip-table">
            <thead>
                <tr>
                    <th>그룹</th><th>매체명</th><th>제목</th><th>PICK</th><th>게시일</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>"""

    st.markdown(render_table(df_filtered), unsafe_allow_html=True)

    # ── 엑셀 다운로드 ─────────────────────────────────────────
    st.divider()
    # 엑셀용 df (제목_표시, 링크 컬럼 제거, 제목은 HYPERLINK 수식 유지)
    df_excel = df_filtered[["그룹", "매체명", "제목", "PICK", "게시일"]].reset_index(drop=True)
    excel_bytes = build_excel(df_excel)
    file_name   = f"naver_news_{query}_{now.strftime('%Y%m%d_%H%M%S')}.xlsx"

    st.download_button(
        label="📥 엑셀 다운로드",
        data=excel_bytes,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )
