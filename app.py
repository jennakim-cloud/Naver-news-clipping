from utils import *

st.set_page_config(page_title="S&C 뉴스 클리핑", page_icon="📰", layout="wide")

st.title("📰 커버리지 리포트")
st.caption("키워드로 원하는 기간의 기사를 수집하고 엑셀로 다운로드합니다.")

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
    days = st.slider("기사 게재일 기준", min_value=1, max_value=7, value=7, step=1, format="%d일")
    st.divider()
    st.markdown("**추가 매체 수집** (네이버 미등록)")
    extra_fi    = st.checkbox("패션인사이트", value=True)
    extra_itnk  = st.checkbox("국제섬유신문", value=True)
    extra_fpost = st.checkbox("패션포스트",   value=True)
    extra_tn    = st.checkbox("테넌트뉴스",   value=True)

col_input, col_btn = st.columns([4, 1])
with col_input:
    query = st.text_input("검색어", placeholder="예: 무신사", label_visibility="collapsed")
with col_btn:
    search_clicked = st.button("🔍 검색", use_container_width=True, type="primary")

if search_clicked:
    if not query.strip():
        st.warning("검색어를 입력해주세요.")
    elif not client_id or not client_secret:
        st.error("API 키가 설정되지 않았습니다.")
    else:
        progress_bar = st.progress(0)
        status_text  = st.empty()
        df = run_search(query.strip(), client_id, client_secret, progress_bar, status_text, days)
        if df is not None and not df.empty:
            kst_now  = datetime.now(timezone(timedelta(hours=9)))
            since_dt = kst_now - timedelta(days=days)
            extra_rows = []
            selected_extras = {
                "패션인사이트": extra_fi, "국제섬유신문": extra_itnk,
                "패션포스트": extra_fpost, "테넌트뉴스": extra_tn,
            }
            for name, enabled in selected_extras.items():
                if enabled:
                    status_text.text(f"🔍 {name} 크롤링 중...")
                    extra_rows.extend(EXTRA_CRAWLERS[name](query.strip(), since_dt))
            if extra_rows:
                df = pd.concat([df, pd.DataFrame(extra_rows)], ignore_index=True)
            st.session_state["cr_df"]    = df
            st.session_state["cr_query"] = query.strip()

if "cr_df" in st.session_state:
    df    = st.session_state["cr_df"]
    query = st.session_state["cr_query"]
    kst   = timezone(timedelta(hours=9))
    now   = datetime.now(kst)
    st.divider()

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("전체",   f"{len(df)}건")
    m2.metric("그룹 A", f"{(df['그룹']=='그룹 A').sum()}건")
    m3.metric("그룹 B", f"{(df['그룹']=='그룹 B').sum()}건")
    m4.metric("그룹 C", f"{(df['그룹']=='그룹 C').sum()}건")
    m5.metric("미분류", f"{(df['그룹']=='').sum()}건")
    m6.metric("PICK",   f"{(df['PICK']=='PICK').sum()}건")
    st.divider()

    fc1, fc2, fc3 = st.columns([2, 2, 2])
    with fc1:
        group_filter = st.multiselect("그룹 필터",
            ["그룹 A", "그룹 B", "그룹 C", "미분류"],
            default=["그룹 A", "그룹 B", "그룹 C", "미분류"])
    with fc2:
        pick_filter = st.checkbox("PICK 기사만 보기", value=False)
    with fc3:
        keyword_filter = st.text_input("제목 키워드 필터", placeholder="추가 필터...")

    sc1, sc2 = st.columns([2, 2])
    with sc1:
        sort_by = st.selectbox("정렬 기준", ["게시일", "그룹", "매체명", "제목"], index=0)
    with sc2:
        sort_order = st.radio("정렬 방향", ["내림차순 ↓", "오름차순 ↑"], horizontal=True, index=0)

    mask = pd.Series([True] * len(df), index=df.index)
    mask &= df["그룹"].isin([("" if g == "미분류" else g) for g in group_filter])
    if pick_filter:
        mask &= df["PICK"] == "PICK"
    if keyword_filter.strip():
        mask &= df["제목_표시"].str.contains(keyword_filter.strip(), case=False, na=False)

    col_map = {"게시일": "게시일", "그룹": "그룹", "매체명": "매체명", "제목": "제목_표시"}
    df_filtered = df[mask].sort_values(
        by=col_map[sort_by], ascending=(sort_order == "오름차순 ↑")
    ).reset_index(drop=True)
    st.caption(f"필터 결과: {len(df_filtered)}건")

    def render_table(df_view):
        rows_html = ""
        for _, row in df_view.iterrows():
            group = row["그룹"]
            badge_style = GROUP_BADGE.get(group, GROUP_BADGE[""])
            badge      = f'<span style="{badge_style}">{group if group else "미분류"}</span>'
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
            .clip-table th {{ background:#2C3E50; color:#fff; padding:8px 10px; text-align:left; position:sticky; top:0; }}
            .clip-table tr:hover {{ filter: brightness(0.96); }}
        </style>
        <div style="overflow-x:auto; max-height:600px; overflow-y:auto;">
        <table class="clip-table">
            <thead><tr><th>그룹</th><th>매체명</th><th>제목</th><th>PICK</th><th>게시일</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table></div>"""

    st.markdown(render_table(df_filtered), unsafe_allow_html=True)
    st.divider()

    df_excel    = df_filtered[["그룹", "매체명", "제목", "PICK", "게시일"]].reset_index(drop=True)
    excel_bytes = build_excel(df_excel)
    st.download_button(
        label="📥 엑셀 다운로드",
        data=excel_bytes,
        file_name=f"coverage_{query}_{now.strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )
