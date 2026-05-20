
import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import date, datetime
import altair as alt

APP_TITLE = "2026 年間研修管理システム Ver1.0"
DB_PATH = Path("training_management.db")

TRAINING_MASTER = [
    ("感染症の予防", "感染対策委員会", "年2回以上", 2),
    ("身体拘束適正化", "身体拘束委員会", "年4回以上", 4),
    ("虐待防止", "虐待防止委員会", "年4回以上", 4),
    ("ハラスメント防止", "", "年2回以上", 2),
    ("業務継続計画（感染症）", "", "研修・訓練 各2回以上", 2),
    ("業務継続計画（自然災害）", "", "研修・訓練 各2回以上", 2),
    ("事故防止", "", "年2回", 2),
    ("認知症専門ケア研修", "", "年2回以上", 2),
    ("避難訓練", "", "年2回", 2),
    ("看取り", "", "年1回", 1),
    ("運営推進会議", "", "年6回", 6),
]

MONTHS = ["4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月", "1月", "2月", "3月"]

st.set_page_config(page_title=APP_TITLE, layout="wide")


def connect_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS training_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        theme TEXT UNIQUE NOT NULL,
        committee TEXT,
        frequency TEXT,
        required_count INTEGER NOT NULL DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS training_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        training_date TEXT NOT NULL,
        theme TEXT NOT NULL,
        staff TEXT,
        participants TEXT,
        record_link TEXT,
        memo TEXT,
        created_at TEXT NOT NULL
    )
    """)

    for theme, committee, frequency, required_count in TRAINING_MASTER:
        cur.execute("""
        INSERT OR IGNORE INTO training_plan(theme, committee, frequency, required_count)
        VALUES (?, ?, ?, ?)
        """, (theme, committee, frequency, required_count))

    conn.commit()
    conn.close()


def read_sql(query, params=()):
    conn = connect_db()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def execute_sql(query, params=()):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()


def get_plan():
    return read_sql("SELECT * FROM training_plan ORDER BY id")


def get_records():
    return read_sql("SELECT * FROM training_records ORDER BY training_date DESC, id DESC")


def progress_df():
    plan = get_plan()
    records = get_records()

    if records.empty:
        counts = pd.DataFrame(columns=["theme", "done_count"])
    else:
        counts = records.groupby("theme").size().reset_index(name="done_count")

    df = plan.merge(counts, on="theme", how="left")
    df["done_count"] = df["done_count"].fillna(0).astype(int)
    df["remaining"] = (df["required_count"] - df["done_count"]).clip(lower=0)
    df["rate"] = df.apply(
        lambda r: min(r["done_count"] / r["required_count"], 1.0) if r["required_count"] else 0,
        axis=1
    )
    df["状況"] = df.apply(
        lambda r: "✅ 完了" if r["done_count"] >= r["required_count"] else ("⚠ 不足" if r["done_count"] > 0 else "❌ 未実施"),
        axis=1
    )
    return df


def month_label(d):
    dt = pd.to_datetime(d)
    return f"{dt.month}月"


init_db()

st.title(APP_TITLE)
st.caption("Streamlit Cloudで無料運用できる、介護施設向けの年間研修管理Webアプリです。")

menu = st.sidebar.radio(
    "メニュー",
    [
        "管理者ダッシュボード",
        "研修実施入力",
        "研修記録一覧・更新削除",
        "研修計画管理",
        "Excel出力"
    ]
)

if menu == "管理者ダッシュボード":
    st.header("管理者ダッシュボード")

    df = progress_df()
    records = get_records()

    total_required = int(df["required_count"].sum()) if not df.empty else 0
    total_done = int(df["done_count"].sum()) if not df.empty else 0
    total_rate = total_done / total_required if total_required else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("年間必要回数", total_required)
    c2.metric("実施済み回数", total_done)
    c3.metric("年間実施率", f"{total_rate:.0%}")
    c4.metric("未実施・不足項目", int((df["done_count"] < df["required_count"]).sum()))

    st.subheader("研修進捗一覧")
    view = df[["theme", "committee", "frequency", "required_count", "done_count", "remaining", "rate", "状況"]].copy()
    view.columns = ["研修テーマ", "委員会", "頻度", "必要回数", "実施数", "残り", "実施率", "状況"]
    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
        column_config={"実施率": st.column_config.ProgressColumn("実施率", min_value=0, max_value=1, format="%.0f%%")}
    )

    st.subheader("年間実施率グラフ")
    chart_df = df[["theme", "rate"]].copy()
    chart_df["rate_percent"] = chart_df["rate"] * 100
    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("rate_percent:Q", title="実施率（%）", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("theme:N", title="研修テーマ", sort="-x"),
            tooltip=["theme", alt.Tooltip("rate_percent:Q", format=".0f")]
        )
        .properties(height=380)
    )
    st.altair_chart(chart, use_container_width=True)

    st.subheader("今月の実施記録")
    if records.empty:
        st.info("まだ研修記録がありません。")
    else:
        now_month = f"{datetime.now().month}月"
        records["月"] = records["training_date"].apply(month_label)
        this_month = records[records["月"] == now_month]
        if this_month.empty:
            st.warning(f"{now_month}の実施記録はまだありません。")
        else:
            st.dataframe(this_month[["training_date", "theme", "staff", "participants", "record_link", "memo"]], use_container_width=True, hide_index=True)

elif menu == "研修実施入力":
    st.header("研修実施入力")

    plan = get_plan()
    themes = plan["theme"].tolist()

    with st.form("record_form"):
        training_date = st.date_input("実施日", value=date.today())
        theme = st.selectbox("研修名", themes)
        staff = st.text_input("担当者")
        participants = st.text_area("参加者")
        record_link = st.text_input("研修記録リンク（Google Drive、PDF、写真URLなど）")
        memo = st.text_area("備考・メモ")
        submitted = st.form_submit_button("登録する")

    if submitted:
        execute_sql("""
        INSERT INTO training_records(training_date, theme, staff, participants, record_link, memo, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            training_date.isoformat(),
            theme,
            staff,
            participants,
            record_link,
            memo,
            datetime.now().isoformat(timespec="seconds")
        ))
        st.success("研修記録を登録しました。")

elif menu == "研修記録一覧・更新削除":
    st.header("研修記録一覧・更新削除")

    records = get_records()
    if records.empty:
        st.info("まだ研修記録がありません。")
    else:
        plan = get_plan()
        themes = ["すべて"] + plan["theme"].tolist()

        c1, c2 = st.columns(2)
        selected_theme = c1.selectbox("研修テーマで検索", themes)
        keyword = c2.text_input("担当者・参加者・メモ検索")

        filtered = records.copy()
        if selected_theme != "すべて":
            filtered = filtered[filtered["theme"] == selected_theme]
        if keyword:
            mask = (
                filtered["staff"].fillna("").str.contains(keyword, case=False, na=False) |
                filtered["participants"].fillna("").str.contains(keyword, case=False, na=False) |
                filtered["memo"].fillna("").str.contains(keyword, case=False, na=False)
            )
            filtered = filtered[mask]

        st.dataframe(
            filtered[["id", "training_date", "theme", "staff", "participants", "record_link", "memo"]],
            use_container_width=True,
            hide_index=True
        )

        st.subheader("記録の更新・削除")
        record_id = st.number_input("対象ID", min_value=1, step=1)
        selected = records[records["id"] == record_id]

        if selected.empty:
            st.info("上の一覧から更新・削除したいIDを入力してください。")
        else:
            row = selected.iloc[0]
            with st.form("edit_record"):
                new_date = st.date_input("実施日", value=pd.to_datetime(row["training_date"]).date())
                new_theme = st.selectbox("研修名", plan["theme"].tolist(), index=plan["theme"].tolist().index(row["theme"]) if row["theme"] in plan["theme"].tolist() else 0)
                new_staff = st.text_input("担当者", value=row["staff"] or "")
                new_participants = st.text_area("参加者", value=row["participants"] or "")
                new_link = st.text_input("研修記録リンク", value=row["record_link"] or "")
                new_memo = st.text_area("備考・メモ", value=row["memo"] or "")

                col1, col2 = st.columns(2)
                update_btn = col1.form_submit_button("更新する")
                delete_btn = col2.form_submit_button("削除する")

            if update_btn:
                execute_sql("""
                UPDATE training_records
                SET training_date=?, theme=?, staff=?, participants=?, record_link=?, memo=?
                WHERE id=?
                """, (new_date.isoformat(), new_theme, new_staff, new_participants, new_link, new_memo, int(record_id)))
                st.success("更新しました。画面を再読み込みしてください。")

            if delete_btn:
                execute_sql("DELETE FROM training_records WHERE id=?", (int(record_id),))
                st.warning("削除しました。画面を再読み込みしてください。")

elif menu == "研修計画管理":
    st.header("研修計画管理")

    plan = get_plan()
    st.dataframe(plan[["id", "theme", "committee", "frequency", "required_count"]], use_container_width=True, hide_index=True)

    st.subheader("研修計画の追加")
    with st.form("add_plan"):
        theme = st.text_input("研修テーマ")
        committee = st.text_input("委員会・担当者")
        frequency = st.text_input("頻度")
        required_count = st.number_input("年間必要回数", min_value=1, max_value=20, value=1)
        add = st.form_submit_button("追加する")

    if add and theme:
        try:
            execute_sql("""
            INSERT INTO training_plan(theme, committee, frequency, required_count)
            VALUES (?, ?, ?, ?)
            """, (theme, committee, frequency, int(required_count)))
            st.success("研修計画を追加しました。")
        except sqlite3.IntegrityError:
            st.error("同じ研修テーマが既に登録されています。")

    st.subheader("研修計画の更新・削除")
    plan = get_plan()
    target_id = st.number_input("対象ID", min_value=1, step=1, key="plan_id")
    selected = plan[plan["id"] == target_id]

    if selected.empty:
        st.info("上の一覧から更新・削除したいIDを入力してください。")
    else:
        row = selected.iloc[0]
        with st.form("edit_plan"):
            new_theme = st.text_input("研修テーマ", value=row["theme"])
            new_committee = st.text_input("委員会・担当者", value=row["committee"] or "")
            new_frequency = st.text_input("頻度", value=row["frequency"] or "")
            new_required = st.number_input("年間必要回数", min_value=1, max_value=20, value=int(row["required_count"]))

            col1, col2 = st.columns(2)
            update = col1.form_submit_button("更新する")
            delete = col2.form_submit_button("削除する")

        if update:
            execute_sql("""
            UPDATE training_plan
            SET theme=?, committee=?, frequency=?, required_count=?
            WHERE id=?
            """, (new_theme, new_committee, new_frequency, int(new_required), int(target_id)))
            st.success("研修計画を更新しました。")

        if delete:
            execute_sql("DELETE FROM training_plan WHERE id=?", (int(target_id),))
            st.warning("研修計画を削除しました。")

elif menu == "Excel出力":
    st.header("Excel出力")

    df = progress_df()
    records = get_records()

    output = Path("training_export.xlsx")
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="進捗一覧", index=False)
        records.to_excel(writer, sheet_name="研修記録", index=False)

    with open(output, "rb") as f:
        st.download_button(
            label="Excelをダウンロード",
            data=f,
            file_name="年間研修管理_出力.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

st.caption("Ver1.0：SQLite保存・検索更新削除・実施率自動計算・Excel出力対応")
