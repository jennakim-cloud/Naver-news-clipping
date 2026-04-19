"""
auto_clipping.py
================
GitHub Actions (또는 cron)에서 실행되는 자동 뉴스 클리핑 스크립트.

흐름:
  1. 네이버 뉴스 API로 섹션별 기사 수집 (최근 24시간)
  2. Claude API로 섹션당 최대 5개 중요 기사 자동 선별
  3. 슬랙봇으로 지정 채널에 포스팅

필요한 환경변수 (GitHub Secrets):
  NAVER_CLIENT_ID       네이버 검색 API Client ID
  NAVER_CLIENT_SECRET   네이버 검색 API Client Secret
  ANTHROPIC_API_KEY     Claude API 키
  SLACK_BOT_TOKEN       슬랙봇 OAuth 토큰 (xoxb-...)
  SLACK_CHANNEL_ID      전송할 슬랙 채널 ID (ex. C0XXXXXXXXX)
"""

import os
import re
import html
import time
import json
import difflib
import logging
import requests
from collections import defaultdict
from datetime import datetime, timedelta, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
#  환경변수
# ══════════════════════════════════════════════════════════════

NAVER_CLIENT_ID     = os.environ["NAVER_CLIENT_ID"]
NAVER_CLIENT_SECRET = os.environ["NAVER_CLIENT_SECRET"]
ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]
SLACK_BOT_TOKEN     = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID    = os.environ["SLACK_CHANNEL_ID"]

# ══════════════════════════════════════════════════════════════
#  설정
# ══════════════════════════════════════════════════════════════

MAX_ARTICLES_PER_SECTION = 5    # 섹션당 최종 슬랙 노출 기사 수
CANDIDATE_MULTIPLIER     = 6    # AI에게 넘길 후보 = MAX × MULTIPLIER
DEDUP_THRESHOLD          = 0.70 # 제목 유사도 중복 제거 임계값
COLLECT_HOURS            = 24   # 수집 기간 (시간)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ══════════════════════════════════════════════════════════════
#  매핑 테이블 (utils.py / 2_Daily_News_Clipping.py 와 동일하게 유지)
# ══════════════════════════════════════════════════════════════

FIXED_MAP = {
    "1conomynews": "1코노미뉴스", "cctimes": "충청타임즈", "chungnamilbo": "충남일보",
    "dtnews24": "대전뉴스", "enetnews": "이넷뉴스", "financialreview": "파이낸셜리뷰",
    "globalepic": "글로벌에픽", "gokorea": "고코리아", "goodmorningcc": "굿모닝충청",
    "hinews": "하이뉴스", "idaegu": "아이대구", "joongdo": "중도일보",
    "kdfnews": "한국면세뉴스", "ktnews": "강원타임즈", "newslock": "뉴스락",
    "newsway": "뉴스웨이", "opinionnews": "오피니언뉴스", "startuptoday": "스타트업투데이",
    "straightnews": "스트레이트뉴스", "tfmedia": "조세금융신문", "weekly": "주간한국",
    "wolyo": "월요신문", "womaneconomy": "여성경제신문",
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
    "pointdaily": "포인트데일리", "ajunews": "아주경제", "asiatoday": "아시아투데이",
    "xportsnews": "엑스포츠뉴스", "sports": "엑스포츠뉴스", "kukinews": "쿠키뉴스",
    "youthdaily": "청년일보", "seoulwire": "서울와이어", "newstomato": "뉴스토마토",
    "widedaily": "와이드경제", "apparelnews": "어패럴뉴스", "biztribune": "비즈트리뷴",
    "etoday": "이투데이", "ngetnews": "뉴스저널리즘", "hansbiz": "한스경제",
    "byline": "바이라인네트워크", "dealsite": "딜사이트", "businesspost": "비즈니스포스트",
    "dnews": "대한경제", "insight": "인사이트", "slist": "싱글리스트",
    "theviewers": "뷰어스", "daily": "데일리한국", "veritas-a": "베리타스알파",
    "fortunekorea": "포춘코리아", "huffingtonpost": "허프포스트", "mediapen": "미디어펜",
    "paxetv": "팍스경제TV", "shinailbo": "신아일보", "pinpointnews": "핀포인트뉴스",
    "sisunnews": "시선뉴스", "sisaon": "시사온", "smarttoday": "스마트투데이",
    "ziksir": "직썰", "job-post": "잡포스트", "issuenbiz": "이슈앤비즈",
    "fashionn": "패션엔", "thebell": "더벨", "ftoday": "파이낸셜투데이",
    "newspost": "뉴스포스트", "econonews": "이코노뉴스", "thevaluenews": "더밸류뉴스",
    "megaeconomy": "메가경제", "greened": "녹색경제신문",
    "sisajournal-e": "시사저널이코노미", "digitaltoday": "디지털투데이",
    "smedaily": "중소기업신문", "thedailypost": "더데일리포스트",
    "dailypost": "더데일리포스트", "topicaldaily": "토피컬데일리",
    "edaily": "이데일리", "skydaily": "스카이데일리", "gooddaily": "굿데일리",
    "safedaily": "세이프타임즈", "meditoday": "메디투데이", "mdtoday": "메디컬투데이",
    "healthinnews": "헬스인뉴스", "health": "헬스조선", "kormedi": "코메디닷컴",
    "hitnews": "히트뉴스", "yakup": "약업신문", "doctorsnews": "의사신문",
    "monews": "메디칼옵저버", "rapportian": "라포르시안", "newsmp": "뉴스메디",
    "medifonews": "메디포뉴스",
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
    "277": "아시아경제", "584": "아시아투데이", "293": "블로터", "321": "브릿지경제",
    "323": "한국섬유신문", "324": "이투데이", "329": "뉴데일리", "366": "조선비즈",
    "374": "SBS Biz", "383": "한국정경신문", "410": "어패럴뉴스", "417": "머니S",
    "421": "뉴스1", "437": "JTBC", "445": "대한경제", "448": "서울와이어",
    "449": "TV조선", "465": "여성경제신문", "468": "스포츠경향", "512": "뉴스핌",
    "529": "싱글리스트", "586": "시사저널e", "629": "뉴스토마토", "645": "아주경제",
    "648": "비즈워치", "654": "비즈트리뷴", "658": "뷰어스", "660": "청년일보",
    "929": "디지털투데이", "239": "바이라인네트워크", "273": "패션비즈",
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

SECTION_NOISE_FILTER = {
    "패션 업계": ["주가", "증시", "코스피", "코스닥", "주식", "배당", "공시", "매출채권", "채권"],
    "뷰티 업계": ["주가", "증시", "코스피", "코스닥", "주식", "배당", "공시", "매출채권", "채권"],
    "유통 업계": ["주가", "증시", "코스피", "코스닥", "주식", "배당", "공시"],
    "IT 업계":   ["주가", "증시", "코스피", "코스닥", "주식", "배당", "공시", "네이버지도", "카카오맵"],
    "패션 플랫폼": ["주가", "증시", "코스피", "코스닥", "주식", "배당", "공시"],
    "무신사": [],
}

# 수집 우선순위 (섹션 간 중복 시 앞 섹션이 우선권)
SECTIONS = [
    ("무신사",    ["무신사", "29CM", "MUSINSA"]),
    ("패션 업계", ["패션 업계", "유니클로", "패션 브랜드", "하고하우스", "LF",
                   "신세계 인터내셔날", "삼성물산 패션", "F&F", "영원무역", "한섬", "이랜드"]),
    ("뷰티 업계", ["올리브영", "에이피알", "뷰티 업계", "화장품 업계", "코스맥스", "콜마"]),
    ("패션 플랫폼",["W컨셉", "에이블리", "지그재그", "네이버 크림", "차란",
                   "패션 플랫폼", "명품 플랫폼"]),
    ("유통 업계", ["쿠팡", "컬리", "백화점", "유통업계", "공정위"]),
    ("IT 업계",   ["네이버", "카카오", "토스", "배달앱", "온플법"]),
]

DISPLAY_ORDER = ["무신사", "패션 업계", "뷰티 업계", "유통 업계", "IT 업계", "패션 플랫폼"]

# ══════════════════════════════════════════════════════════════
#  헬퍼 함수
# ══════════════════════════════════════════════════════════════

def clean_html_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]*>", "", text)
    return text.replace('"', "'")


def publisher_from_url(link: str) -> str:
    if "naver.com" in link:
        m = re.search(r"article/(\d+)/", link)
        if m:
            oid = m.group(1).zfill(3)
            if oid in OID_MAP:
                return OID_MAP[oid]
    try:
        domain = link.split("//")[-1].split("/")[0].lower()
        domain = re.sub(r"^(www\d?\.|n\.|news\.|m\.|blog\.|sports\.|biz\.)", "", domain)
        domain_full = domain.split(":")[0]
        domain_base = domain_full.split(".")[0]

        # 1차: 전체 도메인 정확 매칭
        for key, name in sorted(FIXED_MAP.items(), key=lambda x: -len(x[0])):
            if domain_full == key or domain_full.startswith(key + "."):
                return name
        # 2차: 첫 세그먼트 정확 매칭
        for key, name in sorted(FIXED_MAP.items(), key=lambda x: -len(x[0])):
            if key == domain_base:
                return name
        # 3차: 서브스트링 매칭 (60% 이상 길이일 때만)
        for key, name in sorted(FIXED_MAP.items(), key=lambda x: -len(x[0])):
            if key in domain_base and len(key) >= len(domain_base) * 0.6:
                return name
        return domain_base.upper()
    except Exception:
        return "기타매체"


def deduplicate(items: list) -> list:
    """제목 유사도 DEDUP_THRESHOLD 이상이면 그룹 A 우선 1개만 유지."""
    if not items:
        return items

    GROUP_PRIORITY = {"그룹 A": 0, "그룹 B": 1, "그룹 C": 2, "": 3}
    n = len(items)
    titles = [it["제목"] for it in items]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            ratio = difflib.SequenceMatcher(None, titles[i], titles[j]).ratio()
            if ratio >= DEDUP_THRESHOLD:
                union(i, j)

    clusters: dict = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    kept: set = set()
    for cluster_idx in clusters.values():
        # 그룹 A 우선, 같은 그룹이면 원래 순서(시간순) 우선
        best = sorted(
            cluster_idx,
            key=lambda i: (GROUP_PRIORITY.get(items[i].get("그룹", ""), 3), i)
        )[0]
        kept.add(best)

    return [it for i, it in enumerate(items) if i in kept]

# ══════════════════════════════════════════════════════════════
#  1단계: 네이버 뉴스 수집
# ══════════════════════════════════════════════════════════════

def collect_section(section_name: str, keywords: list, since: datetime,
                    global_seen: set) -> list:
    """섹션 키워드로 뉴스 수집. global_seen으로 섹션 간 중복 방지."""
    naver_headers = {
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    items = []

    for keyword in keywords:
        for start_idx in [1, 101]:
            try:
                url = (
                    "https://openapi.naver.com/v1/search/news.json"
                    f"?query={requests.utils.quote(keyword)}"
                    f"&display=100&start={start_idx}&sort=date"
                )
                res = requests.get(url, headers=naver_headers, timeout=10)
                if res.status_code != 200:
                    log.warning(f"네이버 API {res.status_code}: {keyword}")
                    break

                api_items = res.json().get("items", [])
                if not api_items:
                    break

                stop_early = False
                kst = timezone(timedelta(hours=9))
                for item in api_items:
                    pub_date = datetime.strptime(
                        item["pubDate"], "%a, %d %b %Y %H:%M:%S +0900"
                    ).replace(tzinfo=kst)

                    if pub_date < since:
                        stop_early = True
                        break

                    link          = item.get("link", "")
                    original_link = item.get("originallink", "")
                    dedup_key     = link or original_link

                    if dedup_key in global_seen:
                        continue
                    global_seen.add(dedup_key)

                    title       = clean_html_text(item.get("title", ""))
                    description = clean_html_text(item.get("description", ""))
                    publisher   = publisher_from_url(link)

                    # 미분류 매체 / 중앙이코노미뉴스 제외
                    if GROUP_MAP.get(publisher, "") == "":
                        continue
                    if publisher == "중앙이코노미뉴스":
                        continue

                    # 노이즈 필터: 증시/주가 등
                    noise = SECTION_NOISE_FILTER.get(section_name, [])
                    if noise and any(nw in title for nw in noise):
                        continue

                    # 키워드가 제목에 없으면 제외 (본문 매칭 오탐 방지)
                    kw_tokens = [t for kw in keywords for t in kw.split() if len(t) > 1]
                    if kw_tokens and not any(t in title for t in kw_tokens):
                        continue

                    items.append({
                        "섹션":        section_name,
                        "제목":        title,
                        "링크":        link or original_link,
                        "description": description,
                        "매체명":      publisher,
                        "그룹":        GROUP_MAP.get(publisher, ""),
                        "게시일":      pub_date.strftime("%Y-%m-%d %H:%M"),
                    })

                if stop_early:
                    break
                time.sleep(0.1)

            except Exception as e:
                log.warning(f"수집 오류 ({keyword}): {e}")
                break

    return items


def collect_all() -> dict:
    """전 섹션 수집 후 섹션별 dict 반환."""
    kst   = timezone(timedelta(hours=9))
    since = datetime.now(kst) - timedelta(hours=COLLECT_HOURS)
    global_seen: set = set()
    all_items: dict  = {}

    for sec_name, keywords in SECTIONS:
        log.info(f"수집 중: {sec_name} ({len(keywords)}개 키워드)")
        raw = collect_section(sec_name, keywords, since, global_seen)
        deduped = deduplicate(raw)
        # 최신순 + 그룹 A 우선 정렬
        GROUP_ORDER = {"그룹 A": 0, "그룹 B": 1, "그룹 C": 2, "": 3}
        deduped.sort(key=lambda x: (
            -datetime.strptime(x["게시일"], "%Y-%m-%d %H:%M").timestamp()
            if x["게시일"] else 0,
            GROUP_ORDER.get(x["그룹"], 3),
        ))
        all_items[sec_name] = deduped
        log.info(f"  → 수집 {len(raw)}건, 중복 제거 후 {len(deduped)}건")

    return all_items

# ══════════════════════════════════════════════════════════════
#  2단계: Claude API로 AI 선별
# ══════════════════════════════════════════════════════════════

def ai_select_section(section_name: str, candidates: list) -> list:
    """
    Claude에게 후보 기사 목록을 넘겨 최대 MAX_ARTICLES_PER_SECTION개 선별.
    반환: [{"제목": ..., "링크": ..., "매체명": ..., "게시일": ...}, ...]
    """
    if not candidates:
        return []

    # 후보 수 제한 (토큰 절약)
    pool = candidates[: MAX_ARTICLES_PER_SECTION * CANDIDATE_MULTIPLIER]

    # 번호를 붙여 전달 (Claude가 index로 응답)
    numbered = "\n".join(
        f"{i+1}. [{it['매체명']}] {it['제목']} ({it['게시일'][:10]})"
        + (f"\n   요약: {it['description'][:80]}" if it.get("description") else "")
        for i, it in enumerate(pool)
    )

    prompt = f"""당신은 패션·뷰티·유통·IT 업계 담당 PR 팀의 뉴스 큐레이터입니다.
아래는 오늘 수집된 「{section_name}」 섹션의 뉴스 후보 목록입니다.

{numbered}

다음 기준으로 가장 중요한 기사 최대 {MAX_ARTICLES_PER_SECTION}개를 선별하세요.
선별 기준:
1. 업계 실무자(마케터, 브랜드 매니저, 전략 기획자)에게 실질적으로 중요한 기사 우선
2. 단순 보도자료 단순 재배포(여러 매체가 동일 내용)보다 단독·심층 기사 우선
3. 동일/유사 내용 기사는 1개만 선택
4. 광고성 기사, 단신은 후순위

반드시 아래 JSON 형식으로만 응답하세요 (설명 없이 JSON만):
{{"selected": [1, 3, 7]}}   ← 선택한 기사의 번호 목록 (1-based)"""

    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-sonnet-4-20250514",
                "max_tokens": 256,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        res.raise_for_status()
        raw_text = res.json()["content"][0]["text"].strip()

        # JSON 파싱
        raw_text = re.sub(r"```json|```", "", raw_text).strip()
        data     = json.loads(raw_text)
        indices  = [int(i) - 1 for i in data.get("selected", [])
                    if 1 <= int(i) <= len(pool)]

        selected = [pool[i] for i in indices[:MAX_ARTICLES_PER_SECTION]]
        log.info(f"  [{section_name}] AI 선별 완료: {len(selected)}건 선택")
        return selected

    except Exception as e:
        log.warning(f"  [{section_name}] AI 선별 실패 ({e}), 규칙 기반 폴백 사용")
        # 폴백: 그룹 A 우선 상위 N개
        GROUP_ORDER = {"그룹 A": 0, "그룹 B": 1, "그룹 C": 2, "": 3}
        fallback = sorted(pool, key=lambda x: GROUP_ORDER.get(x.get("그룹", ""), 3))
        return fallback[:MAX_ARTICLES_PER_SECTION]


def ai_select_all(all_items: dict) -> dict:
    """전 섹션에 대해 AI 선별 수행."""
    result = {}
    for sec_name in DISPLAY_ORDER:
        candidates = all_items.get(sec_name, [])
        log.info(f"AI 선별 중: {sec_name} (후보 {len(candidates)}건)")
        result[sec_name] = ai_select_section(sec_name, candidates)
        time.sleep(0.5)  # API 호출 간격
    return result

# ══════════════════════════════════════════════════════════════
#  3단계: 슬랙 전송
# ══════════════════════════════════════════════════════════════

def build_slack_blocks(selected: dict) -> list:
    """슬랙 Block Kit 형식 메시지 구성."""
    kst     = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst)
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday  = weekdays[now_kst.weekday()]
    date_str = f"{now_kst.month}월 {now_kst.day}일({weekday})"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📋 {date_str} 데일리 뉴스 클리핑",
                "emoji": True,
            },
        },
        {"type": "divider"},
    ]

    section_emoji = {
        "무신사":    "👟",
        "패션 업계": "👗",
        "뷰티 업계": "💄",
        "유통 업계": "🛒",
        "IT 업계":   "💻",
        "패션 플랫폼":"📱",
    }

    has_any = False
    for sec_name in DISPLAY_ORDER:
        articles = selected.get(sec_name, [])
        if not articles:
            continue
        has_any = True

        emoji = section_emoji.get(sec_name, "■")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{emoji} {sec_name}*",
            },
        })

        lines = []
        for art in articles:
            title   = art["제목"]
            link    = art["링크"]
            media   = art["매체명"]
            pub_day = art.get("게시일", "")[:10]
            lines.append(f"• <{link}|{title}>  _({media} · {pub_day})_")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(lines),
            },
        })
        blocks.append({"type": "divider"})

    if not has_any:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "오늘은 수집된 기사가 없습니다."},
        })

    # 푸터
    since_str = (datetime.now(timezone(timedelta(hours=9))) - timedelta(hours=COLLECT_HOURS)
                 ).strftime("%m/%d %H:%M")
    now_str   = datetime.now(timezone(timedelta(hours=9))).strftime("%m/%d %H:%M")
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"🤖 Claude AI 자동 선별 | 수집 기간: {since_str} ~ {now_str} (KST)",
        }],
    })

    return blocks


def post_to_slack(blocks: list) -> None:
    """슬랙봇으로 메시지 전송."""
    res = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type":  "application/json; charset=utf-8",
        },
        json={
            "channel": SLACK_CHANNEL_ID,
            "blocks":  blocks,
            "text":    "데일리 뉴스 클리핑",  # 알림 미리보기용 fallback
        },
        timeout=15,
    )
    res.raise_for_status()
    data = res.json()
    if not data.get("ok"):
        raise RuntimeError(f"슬랙 전송 실패: {data.get('error', 'unknown')}")
    log.info(f"슬랙 전송 완료 (ts={data.get('ts')})")

# ══════════════════════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════════════════════

def main():
    log.info("=== 자동 뉴스 클리핑 시작 ===")

    log.info("── 1단계: 기사 수집")
    all_items = collect_all()
    total = sum(len(v) for v in all_items.values())
    log.info(f"   전체 수집: {total}건")

    log.info("── 2단계: AI 선별 (Claude)")
    selected = ai_select_all(all_items)
    total_selected = sum(len(v) for v in selected.values())
    log.info(f"   선별 완료: {total_selected}건")

    log.info("── 3단계: 슬랙 전송")
    blocks = build_slack_blocks(selected)
    post_to_slack(blocks)

    log.info("=== 완료 ===")


if __name__ == "__main__":
    main()
