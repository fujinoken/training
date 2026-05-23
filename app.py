import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import date, datetime
from io import BytesIO
import altair as alt

APP_TITLE = "2026 年間研修管理システム Ver1.5 監査ファイル自動生成型"
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
FISCAL_YEAR = 2026

# 6月開始を想定した効率重視スケジュール。
# 委員会・監査重要項目・季節性を考慮し、1か月2〜3件程度に分散。
RECOMMENDED_SCHEDULE = [
    ("2026-06-10", "6月", "感染症の予防", "感染対策委員会と同日", "会議室", "全職員", "夏前に感染対策を確認。手洗い・標準予防策・嘔吐物対応を確認。"),
    ("2026-06-24", "6月", "事故防止", "管理者", "フロア会議", "全職員", "転倒・誤薬・ヒヤリハットの共有。事故報告書との連動を確認。"),
    ("2026-06-28", "6月", "運営推進会議", "管理者", "施設内", "参加者", "年度開始後の運営状況共有。"),

    ("2026-07-08", "7月", "身体拘束適正化", "身体拘束委員会と同日", "会議室", "全職員", "身体拘束に該当する行為、三原則、記録の必要性を確認。"),
    ("2026-07-22", "7月", "虐待防止", "虐待防止委員会と同日", "会議室", "全職員", "不適切ケア・スピーチロック・通報相談体制を確認。"),

    ("2026-08-12", "8月", "業務継続計画（感染症）", "管理者", "会議室", "全職員", "感染症発生時の役割分担、連絡、ゾーニングを確認。"),
    ("2026-08-26", "8月", "ハラスメント防止", "管理者", "フロア会議", "全職員", "職員間・利用者家族対応・相談窓口を確認。"),
    ("2026-08-28", "8月", "運営推進会議", "管理者", "施設内", "参加者", "夏季の運営状況共有。"),

    ("2026-09-09", "9月", "身体拘束適正化", "身体拘束委員会と同日", "会議室", "全職員", "事例検討。見守り・声かけ・環境調整で代替できる支援を確認。"),
    ("2026-09-23", "9月", "認知症専門ケア研修", "管理者", "フロア会議", "全職員", "認知症の方への声かけ、安心を作る関わりを確認。"),

    ("2026-10-07", "10月", "虐待防止", "虐待防止委員会と同日", "会議室", "全職員", "不適切ケアの早期発見、記録、相談ルートを確認。"),
    ("2026-10-21", "10月", "避難訓練", "防火管理者", "施設内", "全職員・利用者", "秋の避難訓練。夜間想定や誘導手順も確認。"),
    ("2026-10-28", "10月", "運営推進会議", "管理者", "施設内", "参加者", "上半期の運営状況共有。"),

    ("2026-11-11", "11月", "身体拘束適正化", "身体拘束委員会と同日", "会議室", "全職員", "身体拘束廃止に向けたチーム対応を確認。"),
    ("2026-11-25", "11月", "事故防止", "管理者", "フロア会議", "全職員", "冬場の転倒、夜間事故、服薬確認を中心に振り返り。"),

    ("2026-12-09", "12月", "感染症の予防", "感染対策委員会と同日", "会議室", "全職員", "冬季感染症、換気、面会対応、発熱時対応を確認。"),
    ("2026-12-23", "12月", "業務継続計画（自然災害）", "管理者", "会議室", "全職員", "地震・風水害時の初動、備蓄、連絡体制を確認。"),
    ("2026-12-28", "12月", "運営推進会議", "管理者", "施設内", "参加者", "年末時点の運営状況共有。"),

    ("2027-01-13", "1月", "虐待防止", "虐待防止委員会と同日", "会議室", "全職員", "年末年始後の疲労・不適切ケア防止を確認。"),
    ("2027-01-20", "1月", "認知症専門ケア研修", "管理者", "フロア会議", "全職員", "BPSDへの対応、本人の不安を増やさない関わりを確認。"),
    ("2027-01-27", "1月", "ハラスメント防止", "管理者", "フロア会議", "全職員", "相談しやすい職場づくり、対応記録、管理者報告を確認。"),

    ("2027-02-10", "2月", "身体拘束適正化", "身体拘束委員会と同日", "会議室", "全職員", "年度末前の最終確認。記録・議事録の不足確認。"),
    ("2027-02-17", "2月", "業務継続計画（感染症）", "管理者", "会議室", "全職員", "感染症BCPの訓練・振り返り。役割分担の再確認。"),
    ("2027-02-24", "2月", "避難訓練", "防火管理者", "施設内", "全職員・利用者", "年度内2回目の避難訓練。記録写真・参加者記録を保存。"),
    ("2027-02-28", "2月", "運営推進会議", "管理者", "施設内", "参加者", "年度末前の運営状況共有。"),

    ("2027-03-03", "3月", "虐待防止", "虐待防止委員会と同日", "会議室", "全職員", "年度最終確認。未受講者・新入職員への補講確認。"),
    ("2027-03-10", "3月", "業務継続計画（自然災害）", "管理者", "会議室", "全職員", "自然災害BCPの訓練・振り返り。備蓄と連絡網を確認。"),
    ("2027-03-17", "3月", "看取り", "管理者", "フロア会議", "全職員", "看取り期の本人・家族支援、記録、医療連携を確認。"),
    ("2027-03-24", "3月", "運営推進会議", "管理者", "施設内", "参加者", "年度まとめと次年度課題共有。"),
]

AUDIT_CHECK_ITEMS = [
    ("年間研修計画表", "研修テーマ・頻度・実施予定月が確認できること"),
    ("研修実施記録", "実施日・テーマ・担当者・参加者・内容が記録されていること"),
    ("参加者一覧", "誰が受講したか確認できること"),
    ("研修資料", "使用した資料・レジュメ・動画URL等が残っていること"),
    ("委員会議事録", "感染・身体拘束・虐待など委員会と連動していること"),
    ("未実施・不足確認表", "必要回数に対する不足が見えること"),
    ("補講・未受講者対応", "欠席者がいた場合の対応が確認できること"),
    ("BCP訓練記録", "感染症・自然災害の訓練または振り返りが確認できること"),
    ("避難訓練記録", "訓練日・参加者・想定・課題が確認できること"),
]

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
        evidence_status TEXT DEFAULT '未確認',
        material_link TEXT,
        photo_link TEXT,
        committee_minutes_link TEXT,
        absent_follow TEXT,
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
            ("evidence_status", "TEXT DEFAULT '未確認'"),
            ("material_link", "TEXT"),
            ("photo_link", "TEXT"),
            ("committee_minutes_link", "TEXT"),
            ("absent_follow", "TEXT"),
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
        cur.execute("""
        UPDATE training_plan
        SET committee=?, frequency=?, required_count=?
        WHERE theme=?
        """, (committee, frequency, required_count, theme))

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
        valid_records = records.copy()
        valid_records = valid_records[valid_records["theme"].notna()]
        counts = valid_records.groupby("theme").size().reset_index(name="done_count")

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


def records_for_display():
    records = get_records()
    if records.empty:
        return pd.DataFrame(columns=["id", "実施日", "研修テーマ", "担当者", "参加者", "根拠確認", "研修記録リンク", "資料リンク", "写真リンク", "委員会議事録", "欠席者対応", "メモ"])
    df = records.copy()
    df = df.rename(columns={
        "training_date": "実施日",
        "theme": "研修テーマ",
        "staff": "担当者",
        "participants": "参加者",
        "record_link": "研修記録リンク",
        "memo": "メモ",
        "evidence_status": "根拠確認",
        "material_link": "資料リンク",
        "photo_link": "写真リンク",
        "committee_minutes_link": "委員会議事録",
        "absent_follow": "欠席者対応",
    })
    cols = ["id", "実施日", "研修テーマ", "担当者", "参加者", "根拠確認", "研修記録リンク", "資料リンク", "写真リンク", "委員会議事録", "欠席者対応", "メモ"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]


def audit_check_df():
    progress = progress_df()
    records = get_records()
    schedule = get_schedule()

    rows = []
    rows.append(["年間研修計画", "年間予定表", "作成済" if not schedule.empty else "未作成", "6月開始スケジュールを登録すると監査説明がしやすくなります。"])
    rows.append(["研修実施状況", "実施記録", "作成済" if not records.empty else "未実施", "実施日に参加者・資料・写真・議事録リンクを保存します。"])

    for _, r in progress.iterrows():
        status = "完了" if int(r["remaining"]) == 0 else "不足"
        note = f"必要{int(r['required_count'])}回／実施{int(r['done_count'])}回／残り{int(r['remaining'])}回"
        rows.append([str(r["theme"]), "必要回数チェック", status, note])

    if not records.empty:
        for _, r in records.iterrows():
            theme = str(r.get("theme", "") or "")
            evidence = str(r.get("evidence_status", "") or "未確認")
            missing = []
            if not str(r.get("participants", "") or "").strip():
                missing.append("参加者")
            if not str(r.get("record_link", "") or "").strip():
                missing.append("研修記録")
            if not str(r.get("material_link", "") or "").strip():
                missing.append("資料")
            rows.append([theme, "証拠書類チェック", evidence, "不足：" + "・".join(missing) if missing else "主要項目入力済み"])

    return pd.DataFrame(rows, columns=["項目", "確認対象", "状態", "メモ"])


def seed_recommended_schedule(overwrite=False):
    conn = connect_db()
    cur = conn.cursor()
    inserted = 0
    skipped = 0

    if overwrite:
        cur.execute("DELETE FROM training_schedule")

    for scheduled_date, scheduled_month, theme, staff, place, target_staff, memo in RECOMMENDED_SCHEDULE:
        if not overwrite:
            cur.execute("""
            SELECT COUNT(*) FROM training_schedule
            WHERE scheduled_date=? AND theme=?
            """, (scheduled_date, theme))
            exists = cur.fetchone()[0] > 0
            if exists:
                skipped += 1
                continue
        cur.execute("""
        INSERT INTO training_schedule(scheduled_date, scheduled_month, theme, staff, place, target_staff, memo, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (scheduled_date, scheduled_month, theme, staff, place, target_staff, memo, "予定", datetime.now().isoformat(timespec="seconds")))
        inserted += 1

    conn.commit()
    conn.close()
    return inserted, skipped


def update_schedule_status_after_record(theme, training_date):
    month = f"{pd.to_datetime(training_date).month}月"
    execute_sql("""
    UPDATE training_schedule
    SET status='実施済'
    WHERE theme=? AND scheduled_month=? AND status IN ('予定', '実施待ち')
    """, (theme, month))


def theme_ledger_df(theme):
    schedule = schedule_list_df()
    records = records_for_display()

    s = schedule[schedule["研修テーマ"] == theme].copy() if not schedule.empty else pd.DataFrame()
    r = records[records["研修テーマ"] == theme].copy() if not records.empty else pd.DataFrame()

    rows = []
    for _, row in s.iterrows():
        rows.append({
            "区分": "予定",
            "日付": row.get("予定日", ""),
            "月": row.get("月", ""),
            "担当者": row.get("担当者", ""),
            "対象者/参加者": row.get("対象者", ""),
            "状態": row.get("状態", ""),
            "根拠リンク": "",
            "メモ": row.get("メモ", ""),
        })
    for _, row in r.iterrows():
        rows.append({
            "区分": "実施",
            "日付": row.get("実施日", ""),
            "月": f"{pd.to_datetime(row.get('実施日'), errors='coerce').month}月" if not pd.isna(pd.to_datetime(row.get('実施日'), errors='coerce')) else "",
            "担当者": row.get("担当者", ""),
            "対象者/参加者": row.get("参加者", ""),
            "状態": row.get("根拠確認", ""),
            "根拠リンク": row.get("研修記録リンク", ""),
            "メモ": row.get("メモ", ""),
        })
    return pd.DataFrame(rows)


def create_audit_excel():
    buffer = BytesIO()
    progress = progress_df()
    records = records_for_display()
    schedule = schedule_list_df()
    matrix = monthly_schedule_matrix()
    check = audit_check_df()

    cover = pd.DataFrame([
        ["帳票名", "年間研修 監査確認ファイル"],
        ["対象年度", "2026年度（2026年4月〜2027年3月）"],
        ["作成日時", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["説明", "年間予定・実施記録・不足確認・証拠書類チェックをまとめた監査確認用ファイルです。"],
        ["運用方針", "研修実施日に、参加者・資料・写真・議事録リンクまで入力することで、年度末の確認負担を減らします。"],
    ], columns=["項目", "内容"])

    shortage = progress[["theme", "committee", "frequency", "required_count", "done_count", "remaining", "状況"]].copy()
    shortage.columns = ["研修テーマ", "委員会", "頻度", "必要回数", "実施数", "不足回数", "状況"]

    checklist = pd.DataFrame(AUDIT_CHECK_ITEMS, columns=["監査確認書類", "確認ポイント"])
    checklist["保管状況"] = "□ 済　□ 未"
    checklist["備考"] = ""

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        cover.to_excel(writer, sheet_name="表紙", index=False)
        matrix.to_excel(writer, sheet_name="年間予定表", index=False)
        schedule.to_excel(writer, sheet_name="予定一覧", index=False)
        records.to_excel(writer, sheet_name="実施記録", index=False)
        shortage.to_excel(writer, sheet_name="不足確認", index=False)
        check.to_excel(writer, sheet_name="監査確認", index=False)
        checklist.to_excel(writer, sheet_name="提出書類チェック", index=False)

        for theme, *_ in TRAINING_MASTER:
            sheet_name = theme.replace("（", "").replace("）", "")[:28]
            ledger = theme_ledger_df(theme)
            if ledger.empty:
                ledger = pd.DataFrame(columns=["区分", "日付", "月", "担当者", "対象者/参加者", "状態", "根拠リンク", "メモ"])
            ledger.to_excel(writer, sheet_name=sheet_name, index=False)

        wb = writer.book
        for ws in wb.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    text = str(cell.value) if cell.value is not None else ""
                    max_len = max(max_len, min(len(text), 60))
                ws.column_dimensions[col_letter].width = max(12, min(max_len + 2, 45))
            for row in ws.iter_rows():
                for cell in row:
                    cell.alignment = cell.alignment.copy(wrap_text=True, vertical="top")

    buffer.seek(0)
    return buffer


init_db()

st.title(APP_TITLE)
st.caption("年間研修を予定登録・実施記録・監査確認ファイルまで一括管理します。")

menu = st.sidebar.radio(
    "メニュー",
    [
        "管理者ダッシュボード",
        "6月開始おすすめスケジュール",
        "年間実施予定カレンダー",
        "研修予定登録",
        "研修実施入力",
        "研修記録一覧・更新削除",
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("年間必要回数", total_required)
    c2.metric("実施済み回数", total_done)
    c3.metric("年間実施率", f"{total_rate:.0%}")
    c4.metric("未実施・不足項目", int((df["done_count"] < df["required_count"]).sum()))

    if total_rate < 0.5:
        st.warning("年度途中の場合は問題ありません。月ごとに実施して、実施日に記録と根拠資料リンクを入力してください。")
    elif total_rate < 1.0:
        st.info("実施済み項目が増えています。不足確認から残り回数を確認してください。")
    else:
        st.success("必要回数は満たしています。監査ファイルで根拠書類の不足を確認してください。")

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

elif menu == "6月開始おすすめスケジュール":
    st.header("6月開始おすすめスケジュール")
    st.caption("監査で見られやすい項目を前半から消化し、冬と年度末に集中しない配置です。")

    rec_df = pd.DataFrame(RECOMMENDED_SCHEDULE, columns=["予定日", "月", "研修テーマ", "担当者", "場所", "対象者", "メモ"])
    st.dataframe(rec_df, use_container_width=True, hide_index=True, height=520)

    st.info("登録すると、年間実施予定カレンダーに自動反映されます。既存予定を残す登録と、入れ替え登録を選べます。")
    col1, col2 = st.columns(2)
    if col1.button("おすすめスケジュールを追加登録する", type="primary"):
        inserted, skipped = seed_recommended_schedule(overwrite=False)
        st.success(f"追加登録しました。新規 {inserted} 件／重複スキップ {skipped} 件")
        st.rerun()
    if col2.button("既存予定を削除して、おすすめスケジュールに入れ替える"):
        inserted, skipped = seed_recommended_schedule(overwrite=True)
        st.warning(f"既存予定を入れ替えました。登録 {inserted} 件")
        st.rerun()

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
            year = FISCAL_YEAR if MONTH_NUM[scheduled_month] >= 4 else FISCAL_YEAR + 1
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
                        year = FISCAL_YEAR if MONTH_NUM[new_month] >= 4 else FISCAL_YEAR + 1
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

elif menu == "研修実施入力":
    st.header("研修実施入力")
    st.caption("監査で確認されやすい、参加者・資料・写真・議事録リンクまで同時に残せます。")
    plan = get_plan()
    themes = plan["theme"].tolist()

    with st.form("record_form"):
        training_date = st.date_input("実施日", value=date.today())
        theme = st.selectbox("研修名", themes)
        staff = st.text_input("担当者")
        participants = st.text_area("参加者", placeholder="例：中丸、藤野、阿部、武井")
        record_link = st.text_input("研修記録リンク（PDF、Google Drive、写真URLなど）")
        material_link = st.text_input("研修資料リンク")
        photo_link = st.text_input("写真・実施状況リンク")
        committee_minutes_link = st.text_input("委員会議事録リンク")
        absent_follow = st.text_area("欠席者・補講対応", placeholder="例：欠席者なし／〇〇職員は翌日資料確認")
        evidence_status = st.selectbox("根拠書類の確認状況", ["未確認", "一部あり", "確認済", "要追加"])
        memo = st.text_area("備考・メモ")
        mark_schedule_done = st.checkbox("同じ月の予定を『実施済』にする", value=True)
        submitted = st.form_submit_button("登録する")

    if submitted:
        execute_sql("""
        INSERT INTO training_records(training_date, theme, staff, participants, record_link, memo, evidence_status, material_link, photo_link, committee_minutes_link, absent_follow, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            training_date.isoformat(), theme, staff, participants, record_link, memo, evidence_status,
            material_link, photo_link, committee_minutes_link, absent_follow, datetime.now().isoformat(timespec="seconds")
        ))
        if mark_schedule_done:
            update_schedule_status_after_record(theme, training_date.isoformat())
        st.success("研修記録を登録しました。")

elif menu == "研修記録一覧・更新削除":
    st.header("研修記録一覧・更新削除")
    records = get_records()

    if records.empty:
        st.info("まだ研修記録がありません。")
    else:
        display_df = records_for_display()
        st.dataframe(display_df, use_container_width=True, hide_index=True)

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
                new_material = st.text_input("研修資料リンク", value=row.get("material_link", "") or "")
                new_photo = st.text_input("写真・実施状況リンク", value=row.get("photo_link", "") or "")
                new_minutes = st.text_input("委員会議事録リンク", value=row.get("committee_minutes_link", "") or "")
                new_absent = st.text_area("欠席者・補講対応", value=row.get("absent_follow", "") or "")
                evidence_options = ["未確認", "一部あり", "確認済", "要追加"]
                current_evidence = str(row.get("evidence_status", "") or "未確認")
                new_evidence = st.selectbox("根拠書類の確認状況", evidence_options, index=evidence_options.index(current_evidence) if current_evidence in evidence_options else 0)
                new_memo = st.text_area("備考・メモ", value=row.get("memo", "") or "")

                col1, col2 = st.columns(2)
                update_btn = col1.form_submit_button("更新する")
                delete_btn = col2.form_submit_button("削除する")

            if update_btn:
                execute_sql("""
                UPDATE training_records
                SET training_date=?, theme=?, staff=?, participants=?, record_link=?, memo=?, evidence_status=?, material_link=?, photo_link=?, committee_minutes_link=?, absent_follow=?
                WHERE id=?
                """, (new_date.isoformat(), new_theme, new_staff, new_participants, new_link, new_memo, new_evidence, new_material, new_photo, new_minutes, new_absent, int(record_id)))
                st.success("更新しました。")

            if delete_btn:
                execute_sql("DELETE FROM training_records WHERE id=?", (int(record_id),))
                st.warning("削除しました。")

elif menu == "監査ファイル自動生成":
    st.header("監査ファイル自動生成")
    st.caption("年間予定・実施記録・不足確認・証拠書類チェックを1つのExcelにまとめます。")

    st.subheader("監査確認サマリー")
    st.dataframe(audit_check_df(), use_container_width=True, hide_index=True, height=420)

    st.subheader("提出書類チェックリスト")
    checklist = pd.DataFrame(AUDIT_CHECK_ITEMS, columns=["監査確認書類", "確認ポイント"])
    checklist["保管状況"] = "□ 済　□ 未"
    checklist["備考"] = ""
    st.dataframe(checklist, use_container_width=True, hide_index=True)

    excel_data = create_audit_excel()
    st.download_button(
        label="監査確認ファイルExcelをダウンロード",
        data=excel_data,
        file_name="年間研修_監査確認ファイル_2026年度.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

elif menu == "研修計画管理":
    st.header("研修計画管理")
    plan = get_plan()
    st.dataframe(plan, use_container_width=True, hide_index=True)
    st.info("この画面はマスタ確認用です。必要回数やテーマ名を変える場合は、TRAINING_MASTERを修正してください。")

elif menu == "Excel出力":
    st.header("Excel出力")
    st.caption("通常の管理用Excelです。監査用は『監査ファイル自動生成』から出力してください。")

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        monthly_schedule_matrix().to_excel(writer, sheet_name="年間予定表_月単位", index=False)
        schedule_list_df().to_excel(writer, sheet_name="予定一覧", index=False)
        progress_df().to_excel(writer, sheet_name="進捗一覧", index=False)
        records_for_display().to_excel(writer, sheet_name="研修記録", index=False)
    output.seek(0)

    st.download_button(
        label="Excelをダウンロード",
        data=output,
        file_name="年間研修管理_月単位予定表.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.caption("Ver1.5：6月開始おすすめスケジュール、監査ファイル自動生成、根拠資料リンク管理を追加。")
