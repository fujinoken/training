
import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import date, datetime
import altair as alt

APP_TITLE = "2026 年間研修管理システム Ver1.4 安定版"
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
MONTH_NUM = {"4月":4, "5月":5, "6月":6, "7月":7, "8月":8, "9月":9, "10月":10, "11月":11, "12月":12, "1月":1, "2月":2, "3月":3}

st.set_page_config(page_title=APP_TITLE, layout="wide")


def connect_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def table_columns(conn, table_name):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cur.fetchall()]


def add_column_if_missing(conn, table_name, column_name, column_type):
    if column_name not in table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def init_db():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS training_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        theme TEXT UNIQUE,
        committee TEXT,
        frequency TEXT,
        required_count INTEGER DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS training_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        training_date TEXT,
        theme TEXT,
        staff TEXT,
        participants TEXT,
        record_link TEXT,
        memo TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS training_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheduled_date TEXT,
        scheduled_month TEXT,
        theme TEXT,
        staff TEXT,
        place TEXT,
        target_staff TEXT,
        memo TEXT,
        status TEXT DEFAULT '予定',
        created_at TEXT
    )
    """)

    for table, cols in {
        "training_schedule": [
            ("scheduled_date", "TEXT"),
            ("scheduled_month", "TEXT"),
            ("theme", "TEXT"),
            ("staff", "TEXT"),
            ("place", "TEXT"),
            ("target_staff", "TEXT"),
            ("memo", "TEXT"),
            ("status", "TEXT DEFAULT '予定'"),
            ("created_at", "TEXT"),
        ],
        "training_records": [
            ("training_date", "TEXT"),
            ("theme", "TEXT"),
            ("staff", "TEXT"),
            ("participants", "TEXT"),
            ("record_link", "TEXT"),
            ("memo", "TEXT"),
            ("created_at", "TEXT"),
        ],
    }.items():
        for col, typ in cols:
            add_column_if_missing(conn, table, col, typ)

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


def get_schedule():
    return read_sql("SELECT * FROM training_schedule ORDER BY id ASC")


def fiscal_month_order(month_text):
    order = {m: i for i, m in enumerate(MONTHS, start=1)}
    return order.get(str(month_text), 99)


def get_row_month(row):
    month = str(row.get("scheduled_month", "") or "").strip()
    if month in MONTHS:
        return month
    dt = pd.to_datetime(row.get("scheduled_date", ""), errors="coerce")
    if pd.isna(dt):
        return ""
    return f"{dt.month}月"


def progress_df():
    plan = get_plan()
    records = get_records()

    if records.empty or "theme" not in records.columns:
        counts = pd.DataFrame(columns=["theme", "done_count"])
    else:
        counts = records.groupby("theme").size().reset_index(name="done_count")

    df = plan.merge(counts, on="theme", how="left")
    df["done_count"] = df["done_count"].fillna(0).astype(int)
    df["remaining"] = (df["required_count"] - df["done_count"]).clip(lower=0)
    df["rate"] = df.apply(lambda r: min(r["done_count"] / r["required_count"], 1.0) if r["required_count"] else 0, axis=1)
    df["状況"] = df.apply(lambda r: "✅ 完了" if r["done_count"] >= r["required_count"] else ("⚠ 不足" if r["done_count"] > 0 else "❌ 未実施"), axis=1)
    return df


def monthly_schedule_matrix():
    plan = get_plan()
    schedule = get_schedule()

    matrix = plan[["theme", "committee", "frequency", "required_count"]].copy()
    matrix.columns = ["研修テーマ", "委員会", "頻度", "年間必要回数"]

    for m in MONTHS:
        matrix[m] = ""

    if schedule.empty:
        return matrix

    for col in ["scheduled_month", "scheduled_date", "theme", "staff", "status", "memo"]:
        if col not in schedule.columns:
            schedule[col] = ""

    for _, row in schedule.iterrows():
        month = get_row_month(row)
        theme = str(row.get("theme", "") or "").strip()

        if month not in MONTHS or theme == "":
            continue

        if theme not in matrix["研修テーマ"].values:
            continue

        dt = pd.to_datetime(row.get("scheduled_date", ""), errors="coerce")
        day_text = "" if pd.isna(dt) else f"{dt.day}日"
        status_text = str(row.get("status", "予定") or "予定").strip()
        staff_text = str(row.get("staff", "") or "").strip()
        staff_text = f"／{staff_text}" if staff_text else ""

        entry = f"{day_text} {status_text}{staff_text}".strip()

        idx = matrix.index[matrix["研修テーマ"] == theme][0]
        current = matrix.at[idx, month]
        matrix.at[idx, month] = entry if current == "" else current + "\n" + entry

    return matrix


def schedule_list_df():
    schedule = get_schedule()
    cols = ["id", "月", "予定日", "研修テーマ", "担当者", "場所", "対象者", "状態", "メモ"]

    if schedule.empty:
        return pd.DataFrame(columns=cols)

    for col in ["scheduled_month", "scheduled_date", "theme", "staff", "place", "target_staff", "status", "memo"]:
        if col not in schedule.columns:
            schedule[col] = ""

    df = schedule.copy()
    df["月"] = df.apply(get_row_month, axis=1)
    df["月順"] = df["月"].apply(fiscal_month_order)

    dt = pd.to_datetime(df["scheduled_date"], errors="coerce")
    df["予定日"] = dt.dt.strftime("%Y-%m-%d")
    df["予定日"] = df["予定日"].fillna("")

    df = df.rename(columns={
        "theme": "研修テーマ",
        "staff": "担当者",
        "place": "場所",
        "target_staff": "対象者",
        "status": "状態",
        "memo": "メモ"
    })

    for col in cols:
        if col not in df.columns:
            df[col] = ""

    return df.sort_values(["月順", "予定日", "研修テーマ"])[cols]


init_db()

st.title(APP_TITLE)
st.caption("年間研修を、4月〜翌3月の月単位で予定管理できます。")

menu = st.sidebar.radio(
    "メニュー",
    [
        "管理者ダッシュボード",
        "年間実施予定カレンダー",
        "研修予定登録",
        "研修実施入力",
        "研修記録一覧・更新削除",
        "研修計画管理",
        "Excel出力"
    ]
)

if menu == "管理者ダッシュボード":
    st.header("管理者ダッシュボード")

    df = progress_df()
    total_required = int(df["required_count"].sum()) if not df.empty else 0
    total_done = int(df["done_count"].sum()) if not df.empty else 0
    total_rate = total_done / total_required if total_required else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("年間必要回数", total_required)
    c2.metric("実施済み回数", total_done)
    c3.metric("年間実施率", f"{total_rate:.0%}")
    c4.metric("未実施・不足項目", int((df["done_count"] < df["required_count"]).sum()))

    st.subheader("年間実施予定（月単位）")
    st.dataframe(monthly_schedule_matrix(), use_container_width=True, hide_index=True, height=420)

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

elif menu == "年間実施予定カレンダー":
    st.header("年間実施予定カレンダー")
    st.caption("研修テーマごとに、4月〜翌3月の予定を横並びで確認できます。")

    matrix = monthly_schedule_matrix()
    st.dataframe(matrix, use_container_width=True, hide_index=True, height=540)

    st.subheader("月別の予定一覧")
    selected_month = st.selectbox("表示する月", MONTHS)
    list_df = schedule_list_df()
    month_df = list_df[list_df["月"] == selected_month].drop(columns=["id"], errors="ignore")

    if month_df.empty:
        st.info(f"{selected_month}の予定はまだ登録されていません。")
    else:
        st.dataframe(month_df, use_container_width=True, hide_index=True)

elif menu == "研修予定登録":
    st.header("研修予定登録")
    st.caption("日付未定でも、予定月だけで登録できます。")

    plan = get_plan()
    themes = plan["theme"].tolist()

    with st.form("schedule_form"):
        scheduled_month = st.selectbox("予定月", MONTHS)
        use_date = st.checkbox("具体的な予定日も入力する", value=False)

        scheduled_date = ""
        if use_date:
            year = 2026 if MONTH_NUM[scheduled_month] >= 4 else 2027
            scheduled_date = st.date_input("予定日", value=date(year, MONTH_NUM[scheduled_month], 1)).isoformat()

        theme = st.selectbox("研修テーマ", themes)
        staff = st.text_input("担当者")
        place = st.text_input("場所・実施方法", placeholder="例：事務室／オンライン／フロア会議")
        target_staff = st.text_input("対象者", placeholder="例：全職員／夜勤者／新規採用者")
        status = st.selectbox("状態", ["予定", "延期", "中止", "実施待ち"])
        memo = st.text_area("メモ")
        submitted = st.form_submit_button("予定を登録する")

    if submitted:
        execute_sql("""
        INSERT INTO training_schedule(scheduled_date, scheduled_month, theme, staff, place, target_staff, memo, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (scheduled_date, scheduled_month, theme, staff, place, target_staff, memo, status, datetime.now().isoformat(timespec="seconds")))
        st.success("研修予定を登録しました。")

    st.subheader("予定の更新・削除")
    schedule = get_schedule()
    if schedule.empty:
        st.info("更新・削除できる予定はまだありません。")
    else:
        list_df = schedule_list_df()
        st.dataframe(list_df, use_container_width=True, hide_index=True)

        target_id = st.number_input("対象ID", min_value=1, step=1, key="schedule_id")
        selected = schedule[schedule["id"] == target_id]

        if selected.empty:
            st.info("上の一覧から更新・削除したいIDを入力してください。")
        else:
            row = selected.iloc[0]
            with st.form("edit_schedule"):
                default_month = get_row_month(row)
                if default_month not in MONTHS:
                    default_month = "4月"

                new_month = st.selectbox("予定月", MONTHS, index=MONTHS.index(default_month))
                has_date = bool(str(row.get("scheduled_date", "") or "").strip())
                use_date_edit = st.checkbox("具体的な予定日も入力する", value=has_date)

                new_date = ""
                if use_date_edit:
                    default_date = pd.to_datetime(row.get("scheduled_date", ""), errors="coerce")
                    if pd.isna(default_date):
                        year = 2026 if MONTH_NUM[new_month] >= 4 else 2027
                        default_date = pd.Timestamp(date(year, MONTH_NUM[new_month], 1))
                    new_date = st.date_input("予定日", value=default_date.date(), key="edit_schedule_date").isoformat()

                current_theme = str(row.get("theme", "") or "")
                new_theme = st.selectbox("研修テーマ", themes, index=themes.index(current_theme) if current_theme in themes else 0)
                new_staff = st.text_input("担当者", value=row.get("staff", "") or "")
                new_place = st.text_input("場所・実施方法", value=row.get("place", "") or "")
                new_target = st.text_input("対象者", value=row.get("target_staff", "") or "")

                status_options = ["予定", "延期", "中止", "実施待ち"]
                current_status = str(row.get("status", "") or "予定")
                new_status = st.selectbox("状態", status_options, index=status_options.index(current_status) if current_status in status_options else 0)
                new_memo = st.text_area("メモ", value=row.get("memo", "") or "")

                col1, col2 = st.columns(2)
                update_btn = col1.form_submit_button("更新する")
                delete_btn = col2.form_submit_button("削除する")

            if update_btn:
                execute_sql("""
                UPDATE training_schedule
                SET scheduled_date=?, scheduled_month=?, theme=?, staff=?, place=?, target_staff=?, status=?, memo=?
                WHERE id=?
                """, (new_date, new_month, new_theme, new_staff, new_place, new_target, new_status, new_memo, int(target_id)))
                st.success("予定を更新しました。")

            if delete_btn:
                execute_sql("DELETE FROM training_schedule WHERE id=?", (int(target_id),))
                st.warning("予定を削除しました。")

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
        """, (training_date.isoformat(), theme, staff, participants, record_link, memo, datetime.now().isoformat(timespec="seconds")))
        st.success("研修記録を登録しました。")

elif menu == "研修記録一覧・更新削除":
    st.header("研修記録一覧・更新削除")
    records = get_records()

    if records.empty:
        st.info("まだ研修記録がありません。")
    else:
        st.dataframe(records, use_container_width=True, hide_index=True)

        st.subheader("記録の更新・削除")
        record_id = st.number_input("対象ID", min_value=1, step=1)
        selected = records[records["id"] == record_id]

        if selected.empty:
            st.info("上の一覧から更新・削除したいIDを入力してください。")
        else:
            row = selected.iloc[0]
            plan = get_plan()
            themes = plan["theme"].tolist()

            with st.form("edit_record"):
                new_date = st.date_input("実施日", value=pd.to_datetime(row["training_date"]).date())
                new_theme = st.selectbox("研修名", themes, index=themes.index(row["theme"]) if row["theme"] in themes else 0)
                new_staff = st.text_input("担当者", value=row.get("staff", "") or "")
                new_participants = st.text_area("参加者", value=row.get("participants", "") or "")
                new_link = st.text_input("研修記録リンク", value=row.get("record_link", "") or "")
                new_memo = st.text_area("備考・メモ", value=row.get("memo", "") or "")

                col1, col2 = st.columns(2)
                update_btn = col1.form_submit_button("更新する")
                delete_btn = col2.form_submit_button("削除する")

            if update_btn:
                execute_sql("""
                UPDATE training_records
                SET training_date=?, theme=?, staff=?, participants=?, record_link=?, memo=?
                WHERE id=?
                """, (new_date.isoformat(), new_theme, new_staff, new_participants, new_link, new_memo, int(record_id)))
                st.success("更新しました。")

            if delete_btn:
                execute_sql("DELETE FROM training_records WHERE id=?", (int(record_id),))
                st.warning("削除しました。")

elif menu == "研修計画管理":
    st.header("研修計画管理")
    plan = get_plan()
    st.dataframe(plan, use_container_width=True, hide_index=True)

elif menu == "Excel出力":
    st.header("Excel出力")

    output = Path("training_export.xlsx")
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        monthly_schedule_matrix().to_excel(writer, sheet_name="年間予定表_月単位", index=False)
        schedule_list_df().to_excel(writer, sheet_name="予定一覧", index=False)
        progress_df().to_excel(writer, sheet_name="進捗一覧", index=False)
        get_records().to_excel(writer, sheet_name="研修記録", index=False)

    with open(output, "rb") as f:
        st.download_button(
            label="Excelをダウンロード",
            data=f,
            file_name="年間研修管理_月単位予定表.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

st.caption("Ver1.4：古いDBが残っていても落ちない安定版。年間予定を月単位で表示します。")
