from utils import *

st.set_page_config(page_title="데일리 뉴스 클리핑", page_icon="📋", layout="wide")

# ── 섹션 정의: 각 섹션마다 여러 키워드로 수집 후 중복 제거 ──
SECTIONS = [
    ("무신사", [
        "무신사", "29CM", "MUSINSA",
    ]),
    ("패션 업계", [
        "패션 업계", "유니클로", "패션 브랜드", "의류",
        "하고하우스", "LF", "신세계 인터내셔날", "삼성물산 패션", "F&F", "영원무역", "한섬", "이랜드",
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

# ── API 키 ────────────────────────────────────────────────────
try:
    client_id     = st.secrets["naver"]["client_id"]
    client_secret = st.secrets["naver"]["client_secret"]
except Exception:
    import os
    client_id     = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")

# ── Claude API로 기사 요약 1줄 생성 ──────────────────────────
def summarize_article(title: str, description: str) -> str:
    """Claude API로 기사 핵심을 1줄로 요약"""
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 200,
                "messages": [{
                    "role": "user",
                    "content": (
                        f"아래 뉴스 기사의 핵심 내용을 한국어로 1줄(40자 이내)로 요약해줘.\n"
                        f"숫자나 구체적 수치가 있으면 반드시 포함해.\n"
                        f"요약문만 출력하고 다른 말은 하지 마.\n\n"
                        f"제목: {title}\n"
                        f"내용: {description}"
                    )
                }]
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["content"][0]["text"].strip()
    except Exception:
        pass
    return ""


def collect_section(section_name: str, keywords: list, days: int) -> list:
    """섹션별 기사 수집 — 키워드별로 수집 후 링크 기준 중복 제거"""
    naver_headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    kst        = timezone(timedelta(hours=9))
    since      = datetime.now(kst) - timedelta(days=days)
    seen_links = set()
    items      = []

    for keyword in keywords:
        try:
            url = (
                f"https://openapi.naver.com/v1/search/news.json"
                f"?query={requests.utils.quote(keyword)}&display=100&start=1&sort=date"
            )
            res = requests.get(url, headers=naver_headers, timeout=10)
            if res.status_code != 200:
                continue
            for item in res.json().get("items", []):
                pub_date = datetime.strptime(
                    item["pubDate"], "%a, %d %b %Y %H:%M:%S +0900"
                ).replace(tzinfo=kst)
                if pub_date < since:
                    break
                link = item.get("link", "")
                if link in seen_links:
                    continue
                seen_links.add(link)
                title       = clean_html_text(item.get("title", ""))
                description = clean_html_text(item.get("description", ""))
                publisher   = publisher_from_url(link)
                items.append({
                    "섹션":        section_name,
                    "매체명":      publisher,
                    "제목":        title,
                    "링크":        link,
                    "요약":        "",
                    "description": description,
                    "게시일":      pub_date.strftime("%Y-%m-%d"),
                    "선택":        False,
                })
            time.sleep(0.1)
        except Exception:
            continue
    return items


# ════════════════════════════════════════════════════════════
#  UI
# ════════════════════════════════════════════════════════════

st.title("📋 데일리 뉴스 클리핑")
st.caption("섹션별 주요 기사를 선택하고 AI 요약을 더해 데일리 클리핑을 완성합니다.")

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

# ── Step 1: 기사 수집 버튼 ────────────────────────────────────
if st.button("🔍 기사 수집 시작", type="primary", use_container_width=True):
    if not client_id or not client_secret:
        st.error("API 키를 확인해주세요.")
    else:
        all_items = {}
        prog = st.progress(0)
        for i, (sec_name, _) in enumerate(SECTIONS):
            prog.progress(int((i / len(SECTIONS)) * 100))
            kws = custom_queries[sec_name]
            st.toast(f"수집 중: {sec_name} ({len(kws)}개 키워드)")
            all_items[sec_name] = collect_section(sec_name, kws, days)
        prog.progress(100)
        st.session_state["daily_items"] = all_items
        st.success("수집 완료! 아래에서 기사를 선택하세요.")

# ── Step 2: 섹션별 기사 선택 ─────────────────────────────────
if "daily_items" in st.session_state:
    all_items = st.session_state["daily_items"]

    st.divider()
    st.subheader("📌 기사 선택 (섹션별 5~7개 권장)")

    selected_all = {}   # {섹션명: [선택된 기사 dict 리스트]}

    for sec_name, _ in SECTIONS:
        items = all_items.get(sec_name, [])
        st.markdown(f"### ■ {sec_name}")
        if not items:
            st.caption("수집된 기사가 없습니다.")
            selected_all[sec_name] = []
            continue

        selected_in_section = []
        for idx, item in enumerate(items[:30]):   # 최대 30개 표시
            col_chk, col_info = st.columns([1, 11])
            with col_chk:
                checked = st.checkbox("", key=f"chk_{sec_name}_{idx}", label_visibility="collapsed")
            with col_info:
                st.markdown(
                    f"**{item['제목']}** "
                    f"<span style='color:#888;font-size:0.85em;'>({item['매체명']} · {item['게시일']})</span>",
                    unsafe_allow_html=True
                )
            if checked:
                selected_in_section.append(item)

        selected_all[sec_name] = selected_in_section

    st.session_state["daily_selected"] = selected_all

# ── Step 3: AI 요약 생성 + 클리핑 완성 ───────────────────────
if "daily_selected" in st.session_state:
    selected_all = st.session_state["daily_selected"]
    total_selected = sum(len(v) for v in selected_all.values())

    if total_selected == 0:
        st.info("위에서 기사를 체크하면 클리핑이 생성됩니다.")
    else:
        st.divider()
        col_gen, col_info = st.columns([2, 3])
        with col_gen:
            gen_summary = st.button("✨ AI 요약 생성 후 클리핑 완성", type="primary", use_container_width=True)
        with col_info:
            st.caption(f"선택된 기사 {total_selected}건 · AI가 각 기사를 1줄로 요약합니다.")

        if gen_summary:
            prog2 = st.progress(0)
            done  = 0
            for sec_name, items in selected_all.items():
                for item in items:
                    item["요약"] = summarize_article(item["제목"], item["description"])
                    done += 1
                    prog2.progress(int(done / total_selected * 100))
            st.session_state["daily_selected"] = selected_all
            st.session_state["daily_done"] = True

        # ── 클리핑 미리보기 ──────────────────────────────────
        if st.session_state.get("daily_done"):
            st.divider()
            st.subheader("📄 데일리 뉴스 클리핑 미리보기")

            kst = timezone(timedelta(hours=9))
            today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")
            st.markdown(f"**{today_str} 데일리 뉴스 클리핑**")

            clip_text_lines = [f"{today_str} 데일리 뉴스 클리핑", ""]

            for sec_name, _ in SECTIONS:
                items = selected_all.get(sec_name, [])
                if not items:
                    continue

                st.markdown(f"#### ■ {sec_name}")
                clip_text_lines.append(f"■{sec_name}")

                for item in items:
                    title    = item["제목"]
                    media    = item["매체명"]
                    link     = item["링크"]
                    summary  = item.get("요약", "")

                    # 화면 표시
                    st.markdown(
                        f"* <a href='{link}' target='_blank' style='text-decoration:none;color:#1a73e8;'>{title}</a> "
                        f"<span style='color:#555;font-size:0.9em;'>({media})</span>",
                        unsafe_allow_html=True
                    )
                    if summary:
                        st.markdown(
                            f"<div style='margin-left:20px;color:#444;font-size:0.88em;'>"
                            f"* {summary}</div>",
                            unsafe_allow_html=True
                        )

                    # 텍스트 복사용
                    clip_text_lines.append(f"* {title} ({media})")
                    if summary:
                        clip_text_lines.append(f"   * {summary}")

                clip_text_lines.append("")

            # ── 텍스트 복사 영역 ─────────────────────────────
            st.divider()
            st.subheader("📋 텍스트 복사")
            st.caption("아래 텍스트를 복사해서 사용하세요.")
            clip_text = "\n".join(clip_text_lines)
            st.text_area("클리핑 텍스트", value=clip_text, height=400, label_visibility="collapsed")
