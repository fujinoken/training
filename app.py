import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import date, datetime
import altair as alt
import shutil
import zipfile
import re

APP_TITLE = "2026 年間研修管理システム Ver1.6 監査ファイル・研修レポート添付対応版"
DB_PATH = Path("training_management.db")
UPLOAD_DIR = Path("training_uploads")
CASE_DIR = UPLOAD_DIR / "case_materials"
REPORT_DIR = UPLOAD_DIR / "staff_reports"
AUDIT_DIR = Path("audit_exports")

for p in [UPLOAD_DIR, CASE_DIR, REPORT_DIR, AUDIT_DIR]:
    p.mkdir(parents=True, exist_ok=True)

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

RECOMMENDED_SCHEDULE_6_START = [
    ("6月", "2026-06-10", "感染症の予防", "感染対策委員会と連動。夏前に感染対策を確認。"),
    ("6月", "2026-06-24", "事故防止", "転倒・ヒヤリハット事例を使い、夜間対応も確認。"),
    ("7月", "2026-07-15", "身体拘束適正化", "身体拘束委員会と連動。不適切ケアのグレー事例を確認。"),
    ("8月", "2026-08-12", "業務継続計画（感染症）", "感染症流行期前にBCPの動きを確認。"),
    ("9月", "2026-09-16", "虐待防止", "声かけ・不適切ケア・心理的虐待の事例検討。"),
    ("10月", "2026-10-07", "認知症専門ケア研修", "認知症の方への声かけ・不安軽減の支援。"),
    ("10月", "2026-10-21", "避難訓練", "秋の避難訓練。夜間想定も確認。"),
    ("11月", "2026-11-11", "ハラスメント防止", "職員間・利用者家族対応の基本確認。"),
    ("12月", "2026-12-09", "感染症の予防", "冬の感染症流行前の再確認。"),
    ("1月", "2027-01-13", "身体拘束適正化", "年度後半の振り返り。"),
    ("1月", "2027-01-27", "虐待防止", "不適切ケア防止の再確認。"),
    ("2月", "2027-02-10", "業務継続計画（自然災害）", "自然災害BCPと備蓄・連絡体制確認。"),
    ("2月", "2027-02-24", "避難訓練", "年度内2回目の避難訓練。"),
    ("3月", "2027-03-10", "看取り", "看取り期の本人・家族支援の基本確認。"),
    ("3月", "2027-03-24", "認知症専門ケア研修", "認知症ケアの年度末振り返り。"),
]

st.set_page_config(page_title=APP_TITLE, layout="wide")


def safe_filename(name: str) -> str:
    name = str(name or "file").strip()
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", "_", name)
    return name[:120]


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
        case_title TEXT,
        case_summary TEXT,
        staff_report_comment TEXT,
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS training_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id INTEGER,
        attachment_type TEXT,
        original_filename TEXT,
        saved_path TEXT,
        file_note TEXT,
        uploaded_at TEXT
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
            ("case_title", "TEXT"),
            ("case_summary", "TEXT"),
            ("staff_report_comment", "TEXT"),
            ("created_at", "TEXT"),
        ],
        "training_attachments": [
            ("record_id", "INTEGER"),
            ("attachment_type", "TEXT"),
            ("original_filename", "TEXT"),
            ("saved_path", "TEXT"),
            ("file_note", "TEXT"),
            ("uploaded_at", "TEXT"),
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


def execute_sql(query, params=(), return_lastrowid=False):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id if return_lastrowid else None


def get_plan():
    return read_sql("SELECT * FROM training_plan ORDER BY id")


def get_records():
    return read_sql("SELECT * FROM training_records ORDER BY training_date DESC, id DESC")


def get_schedule():
    return read_sql("SELECT * FROM training_schedule ORDER BY id ASC")


def get_attachments(record_id=None):
    if record_id is None:
        return read_sql("SELECT * FROM training_attachments ORDER BY uploaded_at DESC, id DESC")
    return read_sql("SELECT * FROM training_attachments WHERE record_id=? ORDER BY id DESC", (int(record_id),))


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


def attachments_summary_df():
    records = get_records()
    attachments = get_attachments()
    if records.empty:
        return pd.DataFrame(columns=["研修ID", "実施日", "研修テーマ", "事例資料数", "職員レポート数", "その他資料数", "コメント"])

    df = records[["id", "training_date", "theme", "staff_report_comment"]].copy()
    df.columns = ["研修ID", "実施日", "研修テーマ", "コメント"]

    for typ, label in [("事例資料", "事例資料数"), ("職員レポート", "職員レポート数"), ("その他", "その他資料数")]:
        if attachments.empty:
            counts = pd.DataFrame(columns=["record_id", label])
        else:
            counts = attachments[attachments["attachment_type"] == typ].groupby("record_id").size().reset_index(name=label)
        df = df.merge(counts, left_on="研修ID", right_on="record_id", how="left").drop(columns=["record_id"], errors="ignore")
        df[label] = df[label].fillna(0).astype(int)

    return df.sort_values(["実施日", "研修ID"], ascending=[False, False])


def save_uploaded_files(record_id, files, attachment_type, note=""):
    if not files:
        return 0

    saved_count = 0
    base_dir = CASE_DIR if attachment_type == "事例資料" else REPORT_DIR if attachment_type == "職員レポート" else UPLOAD_DIR / "others"
    base_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = safe_filename(file.name)
        saved_name = f"record{record_id}_{timestamp}_{filename}"
        saved_path = base_dir / saved_name

        with open(saved_path, "wb") as f:
            f.write(file.getbuffer())

        execute_sql("""
        INSERT INTO training_attachments(record_id, attachment_type, original_filename, saved_path, file_note, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (int(record_id), attachment_type, file.name, str(saved_path), note, datetime.now().isoformat(timespec="seconds")))

        saved_count += 1

    return saved_count


def apply_recommended_schedule():
    existing = get_schedule()
    added = 0
    existing_keys = set()
    if not existing.empty:
        existing_keys = set(zip(existing["scheduled_date"].fillna(""), existing["theme"].fillna("")))

    for month, scheduled_date, theme, memo in RECOMMENDED_SCHEDULE_6_START:
        key = (scheduled_date, theme)
        if key in existing_keys:
            continue
        execute_sql("""
        INSERT INTO training_schedule(scheduled_date, scheduled_month, theme, staff, place, target_staff, memo, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scheduled_date, month, theme, "",
            "フロア会議・委員会と同時実施",
            "全職員",
            memo,
            "予定",
            datetime.now().isoformat(timespec="seconds")
        ))
        added += 1
    return added


def audit_checklist_df():
    progress = progress_df()
    attach = attachments_summary_df()
    rows = []

    for _, r in progress.iterrows():
        theme = r["theme"]
        recs = get_records()
        theme_recs = recs[recs["theme"] == theme] if not recs.empty else pd.DataFrame()
        has_record = not theme_recs.empty
        has_case = False
        has_report = False
        has_comment = False

        if has_record and not attach.empty:
            ids = theme_recs["id"].tolist()
            a = attach[attach["研修ID"].isin(ids)]
            has_case = int(a["事例資料数"].sum()) > 0
            has_report = int(a["職員レポート数"].sum()) > 0
            has_comment = any(str(x).strip() for x in a["コメント"].fillna("").tolist())

        rows.append({
            "研修テーマ": theme,
            "必要回数": int(r["required_count"]),
            "実施数": int(r["done_count"]),
            "不足": int(r["remaining"]),
            "実施記録": "あり" if has_record else "なし",
            "事例資料": "あり" if has_case else "なし",
            "職員レポート": "あり" if has_report else "なし",
            "コメント保存": "あり" if has_comment else "なし",
            "監査準備状況": "✅ 準備OK" if (r["remaining"] == 0 and has_record and has_report) else "⚠ 確認必要"
        })

    return pd.DataFrame(rows)


def create_audit_excel():
    output = AUDIT_DIR / f"監査ファイル_年間研修管理_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    records = get_records()
    attachments = get_attachments()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        monthly_schedule_matrix().to_excel(writer, sheet_name="01_年間予定表", index=False)
        schedule_list_df().to_excel(writer, sheet_name="02_予定一覧", index=False)
        progress_df().to_excel(writer, sheet_name="03_進捗一覧", index=False)
        records.to_excel(writer, sheet_name="04_研修実施記録", index=False)
        audit_checklist_df().to_excel(writer, sheet_name="05_監査チェックリスト", index=False)
        attachments_summary_df().to_excel(writer, sheet_name="06_添付状況一覧", index=False)
        attachments.to_excel(writer, sheet_name="07_添付ファイル台帳", index=False)

    return output


def create_audit_zip():
    excel_path = create_audit_excel()
    zip_path = AUDIT_DIR / f"監査ファイル一式_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(excel_path, arcname=excel_path.name)

        for folder in [CASE_DIR, REPORT_DIR, UPLOAD_DIR / "others"]:
            if folder.exists():
                for file in folder.rglob("*"):
                    if file.is_file():
                        z.write(file, arcname=str(file))

    return zip_path


init_db()

st.title(APP_TITLE)
st.caption("年間研修の予定・実施記録・事例資料・職員レポート添付・監査ファイル出力を一体管理します。")

menu = st.sidebar.radio(
    "メニュー",
    [
        "管理者ダッシュボード",
        "年間実施予定カレンダー",
        "おすすめスケジュール登録",
        "研修予定登録",
        "研修実施入力・資料添付",
        "研修記録一覧・更新削除",
        "添付資料・レポート管理",
        "監査ファイル自動生成",
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
    attach_df = attachments_summary_df()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("年間必要回数", total_required)
    c2.metric("実施済み回数", total_done)
    c3.metric("年間実施率", f"{total_rate:.0%}")
    c4.metric("未実施・不足項目", int((df["done_count"] < df["required_count"]).sum()))

    c5, c6, c7 = st.columns(3)
    c5.metric("事例資料あり研修", int((attach_df["事例資料数"] > 0).sum()) if not attach_df.empty and "事例資料数" in attach_df.columns else 0)
    c6.metric("職員レポートあり研修", int((attach_df["職員レポート数"] > 0).sum()) if not attach_df.empty and "職員レポート数" in attach_df.columns else 0)
    c7.metric("コメント保存あり研修", int(attach_df["コメント"].fillna("").astype(str).str.strip().ne("").sum()) if not attach_df.empty and "コメント" in attach_df.columns else 0)

    st.subheader("年間実施予定（月単位）")
    st.dataframe(monthly_schedule_matrix(), use_container_width=True, hide_index=True, height=360)

    st.subheader("監査チェックリスト")
    st.dataframe(audit_checklist_df(), use_container_width=True, hide_index=True)

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

elif menu == "おすすめスケジュール登録":
    st.header("6月開始おすすめスケジュール登録")
    st.caption("監査前に慌てないよう、6月開始で分散配置したおすすめ予定を一括登録します。")

    preview = pd.DataFrame(RECOMMENDED_SCHEDULE_6_START, columns=["月", "予定日", "研修テーマ", "狙い・メモ"])
    st.dataframe(preview, use_container_width=True, hide_index=True)

    if st.button("このおすすめスケジュールを一括登録する"):
        added = apply_recommended_schedule()
        st.success(f"{added}件の予定を登録しました。既に同じ日付・テーマの予定があるものは重複登録していません。")

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
        status = st.selectbox("状態", ["予定", "延期", "中止", "実施待ち", "実施済"])
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

                status_options = ["予定", "延期", "中止", "実施待ち", "実施済"]
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

elif menu == "研修実施入力・資料添付":
    st.header("研修実施入力・資料添付")
    st.caption("使用した事例資料、職員レポートExcel、コメントを研修記録に紐づけて保存できます。")

    plan = get_plan()
    themes = plan["theme"].tolist()

    with st.form("record_form"):
        training_date = st.date_input("実施日", value=date.today())
        theme = st.selectbox("研修名", themes)
        staff = st.text_input("担当者")
        participants = st.text_area("参加者")
        record_link = st.text_input("研修記録リンク（Google Drive、PDF、写真URLなど）")
        memo = st.text_area("備考・メモ")

        st.markdown("### 使用した事例")
        case_title = st.text_input("事例タイトル", placeholder="例：夜間トイレ移動時の転倒リスク事例")
        case_summary = st.text_area("事例内容メモ", placeholder="研修で使用した事例の要点を記録します。")
        case_files = st.file_uploader(
            "使用した事例ファイルを添付（Excel・Word・PDF・画像など）",
            type=["xlsx", "xls", "docx", "doc", "pdf", "png", "jpg", "jpeg", "txt"],
            accept_multiple_files=True
        )

        st.markdown("### 職員レポート")
        report_files = st.file_uploader(
            "職員レポートを添付（Excel推奨。Word・PDFも可）",
            type=["xlsx", "xls", "docx", "doc", "pdf", "txt"],
            accept_multiple_files=True
        )
        staff_report_comment = st.text_area("職員レポートへのコメント・確認メモ", placeholder="例：全職員提出済。転倒リスクへの理解が確認できた。")

        other_files = st.file_uploader(
            "その他添付（写真・議事録・配布資料など）",
            type=["xlsx", "xls", "docx", "doc", "pdf", "png", "jpg", "jpeg", "txt"],
            accept_multiple_files=True
        )

        submitted = st.form_submit_button("研修記録と添付資料を登録する")

    if submitted:
        record_id = execute_sql("""
        INSERT INTO training_records(training_date, theme, staff, participants, record_link, memo, case_title, case_summary, staff_report_comment, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            training_date.isoformat(), theme, staff, participants, record_link, memo,
            case_title, case_summary, staff_report_comment,
            datetime.now().isoformat(timespec="seconds")
        ), return_lastrowid=True)

        case_count = save_uploaded_files(record_id, case_files, "事例資料", case_title)
        report_count = save_uploaded_files(record_id, report_files, "職員レポート", staff_report_comment)
        other_count = save_uploaded_files(record_id, other_files, "その他", memo)

        execute_sql("""
        UPDATE training_schedule
        SET status='実施済'
        WHERE theme=? AND (scheduled_date=? OR scheduled_month=?)
        """, (theme, training_date.isoformat(), f"{training_date.month}月"))

        st.success(f"研修記録を登録しました。事例資料 {case_count}件、職員レポート {report_count}件、その他 {other_count}件を保存しました。")

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
                new_case_title = st.text_input("事例タイトル", value=row.get("case_title", "") or "")
                new_case_summary = st.text_area("事例内容メモ", value=row.get("case_summary", "") or "")
                new_report_comment = st.text_area("職員レポートへのコメント・確認メモ", value=row.get("staff_report_comment", "") or "")

                col1, col2 = st.columns(2)
                update_btn = col1.form_submit_button("更新する")
                delete_btn = col2.form_submit_button("削除する")

            if update_btn:
                execute_sql("""
                UPDATE training_records
                SET training_date=?, theme=?, staff=?, participants=?, record_link=?, memo=?, case_title=?, case_summary=?, staff_report_comment=?
                WHERE id=?
                """, (new_date.isoformat(), new_theme, new_staff, new_participants, new_link, new_memo, new_case_title, new_case_summary, new_report_comment, int(record_id)))
                st.success("更新しました。")

            if delete_btn:
                execute_sql("DELETE FROM training_records WHERE id=?", (int(record_id),))
                execute_sql("DELETE FROM training_attachments WHERE record_id=?", (int(record_id),))
                st.warning("記録と添付台帳を削除しました。保存済ファイル自体は監査用バックアップとしてフォルダに残ります。")

            st.subheader("この記録に紐づく添付資料")
            att = get_attachments(int(record_id))
            if att.empty:
                st.info("添付資料はありません。")
            else:
                st.dataframe(att, use_container_width=True, hide_index=True)

elif menu == "添付資料・レポート管理":
    st.header("添付資料・レポート管理")
    st.caption("研修ごとの事例資料・職員レポート提出状況を確認します。")

    summary = attachments_summary_df()
    st.subheader("添付状況サマリー")
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("添付ファイル台帳")
    att = get_attachments()
    if att.empty:
        st.info("添付ファイルはまだありません。")
    else:
        st.dataframe(att, use_container_width=True, hide_index=True)

        target_id = st.number_input("削除する添付ID", min_value=1, step=1)
        if st.button("添付台帳から削除する"):
            execute_sql("DELETE FROM training_attachments WHERE id=?", (int(target_id),))
            st.warning("添付台帳から削除しました。保存済ファイル自体はフォルダに残ります。")

elif menu == "監査ファイル自動生成":
    st.header("監査ファイル自動生成")
    st.caption("年間予定、進捗、実施記録、添付資料台帳、チェックリストを監査提出用にまとめます。")

    st.subheader("監査チェックリスト")
    st.dataframe(audit_checklist_df(), use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("監査用Excelを作成する"):
            output = create_audit_excel()
            with open(output, "rb") as f:
                st.download_button(
                    label="監査用Excelをダウンロード",
                    data=f,
                    file_name=output.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    with col2:
        if st.button("監査ファイル一式ZIPを作成する"):
            zip_path = create_audit_zip()
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="監査ファイル一式ZIPをダウンロード",
                    data=f,
                    file_name=zip_path.name,
                    mime="application/zip"
                )

    st.info("ZIPには監査用Excelと、保存済みの事例資料・職員レポート等の添付ファイルが含まれます。")

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
        attachments_summary_df().to_excel(writer, sheet_name="添付状況一覧", index=False)
        get_attachments().to_excel(writer, sheet_name="添付ファイル台帳", index=False)
        audit_checklist_df().to_excel(writer, sheet_name="監査チェックリスト", index=False)

    with open(output, "rb") as f:
        st.download_button(
            label="Excelをダウンロード",
            data=f,
            file_name="年間研修管理_添付資料対応版.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

st.caption("Ver1.6：研修レポート添付・使用事例保存・コメント保存・監査ファイル自動生成対応版。")
