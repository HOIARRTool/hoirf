from __future__ import annotations

import io
import os
from pathlib import Path
from datetime import datetime, date, time
from typing import Dict, List

import pandas as pd
import streamlit as st


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Incident Entry + RCA",
    page_icon="🩺",
    layout="wide",
)


# =========================================================
# PATHS / CONFIG
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MASTERS_DIR = DATA_DIR / "masters"
OUTPUT_DIR = DATA_DIR / "output"

MASTERS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_path(env_name: str, *candidates: Path) -> Path:
    env_value = os.environ.get(env_name)
    if env_value:
        return Path(env_value)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


CODE_MASTER_PATH = resolve_path(
    "CODE_MASTER_PATH",
    MASTERS_DIR / "Code2024.xlsx",
    BASE_DIR / "Code2024.xlsx",
)

PSG9_MASTER_PATH = resolve_path(
    "PSG9_MASTER_PATH",
    MASTERS_DIR / "PSG9code.xlsx",
    BASE_DIR / "PSG9code.xlsx",
)

CONTRIB_MASTER_PATH = resolve_path(
    "CONTRIB_MASTER_PATH",
    MASTERS_DIR / "contributing_factor.xlsx",
    BASE_DIR / "contributing_factor.xlsx",
)

OUTPUT_CSV_PATH = Path(
    os.environ.get("INCIDENT_OUTPUT_PATH", OUTPUT_DIR / "incident_entry_records.csv")
)

FALLBACK_PSG9_LABEL = "ไม่จัดอยู่ใน PSG9 Catalog"

REQUIRED_EXPORT_COLUMNS = [
    # คอลัมน์หลักที่ app.py ใช้ประมวลผล
    "รหัส: เรื่องอุบัติการณ์",
    "วันที่เกิดอุบัติการณ์",
    "ความรุนแรง",
    "สถานะ",
    "รายละเอียดการเกิด",
    # Metadata เพิ่มเติม
    "timestamp",
    "เวลาที่เกิดอุบัติการณ์",
    "วันที่รายงาน",
    "หน่วยงาน/หอผู้ป่วย/คลินิก",
    "สถานที่เกิดเหตุ",
    "ผู้รายงาน",
    "HN",
    "AN/VN/Visit",
    "ชื่อผู้ป่วย",
    "อายุ",
    "เพศ",
    "ประเภทผู้ป่วย",
    "รหัส",
    "ชื่ออุบัติการณ์ความเสี่ยง",
    "กลุ่ม",
    "หมวด",
    "ประเภท",
    "ประเภทย่อย",
    "PSG_ID",
    "หมวดหมู่PSG",
    "หมวดหมู่มาตรฐานสำคัญ",
    "RCA - Problem Statement",
    "RCA - Event Timeline",
    "RCA - Immediate Cause",
    "RCA - Root Cause",
    "RCA - Human Factors",
    "RCA - System Factors",
    "RCA - Existing Barriers",
    "RCA - Barrier Gaps",
    "RCA - Corrective Action",
    "RCA - Preventive Action",
    "RCA - Learning",
    "RCA - Owner",
    "RCA - Due Date",
    "RCA - Follow-up Status",
    "selected_contributing_factor_codes",
    "selected_contributing_factor_details",
]


# =========================================================
# HELPERS
# =========================================================
def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def safe_int_string(value) -> str:
    if pd.isna(value) or normalize_text(value) == "":
        return ""
    text = normalize_text(value)
    try:
        as_float = float(text)
        if as_float.is_integer():
            return str(int(as_float))
        return text
    except Exception:
        return text


@st.cache_data(show_spinner=False)
def load_code_master(path_str: str) -> pd.DataFrame:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์ master code: {path}")

    df = pd.read_excel(path, sheet_name=0, dtype=object)
    df.columns = [normalize_text(c) for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c != ""]].copy()

    required_cols = ["รหัส", "ชื่ออุบัติการณ์ความเสี่ยง", "กลุ่ม", "หมวด", "ประเภท", "ประเภทย่อย"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"ไฟล์ Code2024.xlsx ขาดคอลัมน์: {', '.join(missing_cols)}")

    for col in required_cols:
        df[col] = df[col].apply(normalize_text)

    df = df[df["รหัส"] != ""].copy()
    df = df.drop_duplicates(subset=["รหัส"], keep="first").reset_index(drop=True)
    return df[required_cols]


@st.cache_data(show_spinner=False)
def load_psg9_master(path_str: str) -> pd.DataFrame:
    path = Path(path_str)
    if not path.exists():
        return pd.DataFrame(columns=["รหัส", "PSG_ID", "หมวดหมู่PSG"])

    df = pd.read_excel(path, sheet_name=0, dtype=object)
    df.columns = [normalize_text(c) for c in df.columns]

    required_cols = ["รหัส", "PSG_ID", "หมวดหมู่PSG"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"ไฟล์ PSG9code.xlsx ขาดคอลัมน์: {', '.join(missing_cols)}")

    df = df[required_cols].copy()
    df["รหัส"] = df["รหัส"].apply(normalize_text)
    df["PSG_ID"] = df["PSG_ID"].apply(safe_int_string)
    df["หมวดหมู่PSG"] = df["หมวดหมู่PSG"].apply(normalize_text)
    df = df[df["รหัส"] != ""].drop_duplicates(subset=["รหัส"], keep="first").reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False)
def load_contributing_factors(path_str: str) -> pd.DataFrame:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์ contributing factor: {path}")

    df = pd.read_excel(path, sheet_name=0, dtype=object)
    df.columns = [normalize_text(c) for c in df.columns]

    required_cols = ["id", "code", "detail", "active"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"ไฟล์ contributing_factor.xlsx ขาดคอลัมน์: {', '.join(missing_cols)}")

    df["code"] = df["code"].apply(normalize_text)
    df["detail"] = df["detail"].apply(normalize_text)
    df["active"] = df["active"].apply(normalize_text)
    df = df[df["code"] != ""].copy()
    df = df[df["active"].isin(["1", "true", "True", "TRUE", "yes", "Y", "y"])].copy()
    df["group_label"] = df["detail"].apply(lambda x: x.split(":", 1)[0].strip() if ":" in x else "Other")
    df = df.reset_index(drop=True)
    return df[["id", "code", "detail", "group_label"]]


@st.cache_data(show_spinner=False)
def build_master_dataframe(code_path: str, psg_path: str) -> pd.DataFrame:
    code_df = load_code_master(code_path)
    psg_df = load_psg9_master(psg_path)

    master = code_df.merge(psg_df, on="รหัส", how="left")
    master["PSG_ID"] = master["PSG_ID"].fillna("").apply(safe_int_string)
    master["หมวดหมู่PSG"] = master["หมวดหมู่PSG"].fillna("").apply(normalize_text)

    # fallback PSG9
    missing_psg_mask = master["PSG_ID"].eq("") | master["หมวดหมู่PSG"].eq("")
    master.loc[missing_psg_mask, "PSG_ID"] = ""
    master.loc[missing_psg_mask, "หมวดหมู่PSG"] = FALLBACK_PSG9_LABEL
    master["หมวดหมู่มาตรฐานสำคัญ"] = master["หมวดหมู่PSG"]

    master["display_label"] = (
        master["รหัส"].astype(str)
        + " | "
        + master["ชื่ออุบัติการณ์ความเสี่ยง"].astype(str)
    )
    return master.sort_values(["รหัส"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_saved_records(path_str: str) -> pd.DataFrame:
    path = Path(path_str)
    if not path.exists():
        return pd.DataFrame(columns=REQUIRED_EXPORT_COLUMNS)
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    for col in REQUIRED_EXPORT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df


@st.cache_data(show_spinner=False)
def get_export_columns(contrib_path: str) -> List[str]:
    contrib_df = load_contributing_factors(contrib_path)
    factor_columns = [f"CF_{normalize_text(code)}" for code in contrib_df["code"].tolist()]
    return REQUIRED_EXPORT_COLUMNS + factor_columns



def ensure_all_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[columns]



def append_record_to_csv(record: Dict[str, str], output_path: Path, export_columns: List[str]) -> None:
    new_df = pd.DataFrame([record])
    new_df = ensure_all_columns(new_df, export_columns)

    if output_path.exists():
        existing = pd.read_csv(output_path, dtype=str, encoding="utf-8-sig").fillna("")
        existing = ensure_all_columns(existing, export_columns)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df.copy()

    combined.to_csv(output_path, index=False, encoding="utf-8-sig")



def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "incident_records") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    buffer.seek(0)
    return buffer.read()



def build_incident_text(code: str, incident_name: str) -> str:
    return f"{normalize_text(code)}: {normalize_text(incident_name)}"



def build_record_dict(
    selected_row: pd.Series,
    basic_fields: Dict[str, str],
    rca_fields: Dict[str, str],
    selected_factor_rows: pd.DataFrame,
    all_factor_codes: List[str],
) -> Dict[str, str]:
    selected_codes = selected_factor_rows["code"].tolist() if not selected_factor_rows.empty else []
    selected_details = selected_factor_rows["detail"].tolist() if not selected_factor_rows.empty else []

    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "วันที่เกิดอุบัติการณ์": basic_fields["incident_date"],
        "เวลาที่เกิดอุบัติการณ์": basic_fields["incident_time"],
        "วันที่รายงาน": basic_fields["report_date"],
        "สถานะ": basic_fields["status"],
        "ความรุนแรง": basic_fields["severity"],
        "หน่วยงาน/หอผู้ป่วย/คลินิก": basic_fields["department"],
        "สถานที่เกิดเหตุ": basic_fields["location"],
        "ผู้รายงาน": basic_fields["reporter"],
        "HN": basic_fields["hn"],
        "AN/VN/Visit": basic_fields["an_vn"],
        "ชื่อผู้ป่วย": basic_fields["patient_name"],
        "อายุ": basic_fields["age"],
        "เพศ": basic_fields["sex"],
        "ประเภทผู้ป่วย": basic_fields["patient_type"],
        "รายละเอียดการเกิด": basic_fields["description"],
        "รหัส: เรื่องอุบัติการณ์": build_incident_text(selected_row["รหัส"], selected_row["ชื่ออุบัติการณ์ความเสี่ยง"]),
        "รหัส": normalize_text(selected_row["รหัส"]),
        "ชื่ออุบัติการณ์ความเสี่ยง": normalize_text(selected_row["ชื่ออุบัติการณ์ความเสี่ยง"]),
        "กลุ่ม": normalize_text(selected_row["กลุ่ม"]),
        "หมวด": normalize_text(selected_row["หมวด"]),
        "ประเภท": normalize_text(selected_row["ประเภท"]),
        "ประเภทย่อย": normalize_text(selected_row["ประเภทย่อย"]),
        "PSG_ID": normalize_text(selected_row["PSG_ID"]),
        "หมวดหมู่PSG": normalize_text(selected_row["หมวดหมู่PSG"]),
        "หมวดหมู่มาตรฐานสำคัญ": normalize_text(selected_row["หมวดหมู่มาตรฐานสำคัญ"]),
        "RCA - Problem Statement": rca_fields["problem_statement"],
        "RCA - Event Timeline": rca_fields["timeline"],
        "RCA - Immediate Cause": rca_fields["immediate_cause"],
        "RCA - Root Cause": rca_fields["root_cause"],
        "RCA - Human Factors": rca_fields["human_factors"],
        "RCA - System Factors": rca_fields["system_factors"],
        "RCA - Existing Barriers": rca_fields["existing_barriers"],
        "RCA - Barrier Gaps": rca_fields["barrier_gaps"],
        "RCA - Corrective Action": rca_fields["corrective_action"],
        "RCA - Preventive Action": rca_fields["preventive_action"],
        "RCA - Learning": rca_fields["learning"],
        "RCA - Owner": rca_fields["owner"],
        "RCA - Due Date": rca_fields["due_date"],
        "RCA - Follow-up Status": rca_fields["followup_status"],
        "selected_contributing_factor_codes": "|".join(selected_codes),
        "selected_contributing_factor_details": " | ".join(selected_details),
    }

    for cf_code in all_factor_codes:
        record[f"CF_{cf_code}"] = "1" if cf_code in selected_codes else "0"

    return record


# =========================================================
# LOAD DATA
# =========================================================
try:
    master_df = build_master_dataframe(str(CODE_MASTER_PATH), str(PSG9_MASTER_PATH))
    contrib_df = load_contributing_factors(str(CONTRIB_MASTER_PATH))
    export_columns = get_export_columns(str(CONTRIB_MASTER_PATH))
except Exception as exc:
    st.error(f"โหลดไฟล์ master ไม่สำเร็จ: {exc}")
    st.stop()

all_factor_codes = contrib_df["code"].tolist()


# =========================================================
# HEADER
# =========================================================
st.title("🩺 Incident Entry + RCA + Contributing Factors")
st.caption(
    "เลือก code แล้วระบบจะเติม ชื่ออุบัติการณ์ความเสี่ยง / กลุ่ม / หมวด / ประเภท / ประเภทย่อย / PSG9 ให้อัตโนมัติ พร้อม fallback PSG9"
)

with st.expander("ดูแหล่งข้อมูล master ที่ใช้", expanded=False):
    st.write(f"Code master: `{CODE_MASTER_PATH}`")
    st.write(f"PSG9 master: `{PSG9_MASTER_PATH}`")
    st.write(f"Contributing factor master: `{CONTRIB_MASTER_PATH}`")
    st.write(f"Output CSV: `{OUTPUT_CSV_PATH}`")


# =========================================================
# MAIN FORM
# =========================================================
code_options = master_df["display_label"].tolist()
if not code_options:
    st.error("ไม่พบรหัสอุบัติการณ์ใน master file")
    st.stop()

selected_display = st.selectbox(
    "เลือกรหัสอุบัติการณ์",
    options=code_options,
    index=0,
)
selected_code = selected_display.split("|", 1)[0].strip()
selected_row = master_df[master_df["รหัส"] == selected_code].iloc[0]

left_col, right_col = st.columns([1.2, 0.9])

with right_col:
    st.markdown("### ข้อมูลที่ระบบเติมให้อัตโนมัติ")
    st.text_input("รหัส", value=selected_row["รหัส"], disabled=True)
    st.text_area("ชื่ออุบัติการณ์ความเสี่ยง", value=selected_row["ชื่ออุบัติการณ์ความเสี่ยง"], height=80, disabled=True)
    st.text_input("กลุ่ม", value=selected_row["กลุ่ม"], disabled=True)
    st.text_input("หมวด", value=selected_row["หมวด"], disabled=True)
    st.text_input("ประเภท", value=selected_row["ประเภท"], disabled=True)
    st.text_input("ประเภทย่อย", value=selected_row["ประเภทย่อย"], disabled=True)
    st.text_input("PSG_ID", value=selected_row["PSG_ID"], disabled=True)
    st.text_area("หมวดหมู่PSG / Fallback", value=selected_row["หมวดหมู่PSG"], height=80, disabled=True)

with left_col:
    st.markdown("### ข้อมูลพื้นฐานที่ผู้ใช้กรอก")
    basic_col1, basic_col2 = st.columns(2)

    with basic_col1:
        incident_date = st.date_input("วันที่เกิดอุบัติการณ์", value=date.today(), format="YYYY-MM-DD")
        report_date = st.date_input("วันที่รายงาน", value=date.today(), format="YYYY-MM-DD")
        severity = st.selectbox("ระดับความรุนแรง", ["A", "B", "C", "D", "E", "F", "G", "H", "I", "1", "2", "3", "4", "5"])
        status = st.selectbox("สถานะ", ["รอแก้ไข", "อยู่ระหว่างดำเนินการ", "แก้ไขแล้ว", "ปิดเคส"])
        department = st.text_input("หน่วยงาน/หอผู้ป่วย/คลินิก")
        location = st.text_input("สถานที่เกิดเหตุ")
        reporter = st.text_input("ผู้รายงาน")

    with basic_col2:
        incident_time = st.time_input("เวลาที่เกิดอุบัติการณ์", value=time(8, 0))
        hn = st.text_input("HN")
        an_vn = st.text_input("AN/VN/Visit")
        patient_name = st.text_input("ชื่อผู้ป่วย")
        age = st.text_input("อายุ")
        sex = st.selectbox("เพศ", ["", "ชาย", "หญิง", "ไม่ระบุ"])
        patient_type = st.selectbox("ประเภทผู้ป่วย", ["", "OPD", "IPD", "ER", "OR", "Dental", "อื่น ๆ"])

    description = st.text_area(
        "รายละเอียดการเกิด",
        height=180,
        help="คอลัมน์นี้ app.py ใช้ต่อในการ anonymize และประมวลผล",
    )

st.divider()

# =========================================================
# RCA SECTION
# =========================================================
st.markdown("### RCA")
rca_col1, rca_col2 = st.columns(2)

with rca_col1:
    problem_statement = st.text_area("RCA - Problem Statement", height=110)
    timeline = st.text_area("RCA - Event Timeline", height=110)
    immediate_cause = st.text_area("RCA - Immediate Cause", height=110)
    root_cause = st.text_area("RCA - Root Cause", height=110)
    human_factors = st.text_area("RCA - Human Factors", height=110)
    system_factors = st.text_area("RCA - System Factors", height=110)

with rca_col2:
    existing_barriers = st.text_area("RCA - Existing Barriers", height=110)
    barrier_gaps = st.text_area("RCA - Barrier Gaps", height=110)
    corrective_action = st.text_area("RCA - Corrective Action", height=110)
    preventive_action = st.text_area("RCA - Preventive Action", height=110)
    learning = st.text_area("RCA - Learning", height=110)

rca_meta_col1, rca_meta_col2, rca_meta_col3 = st.columns(3)
with rca_meta_col1:
    rca_owner = st.text_input("RCA - Owner")
with rca_meta_col2:
    rca_due_date = st.date_input("RCA - Due Date", value=date.today(), format="YYYY-MM-DD")
with rca_meta_col3:
    rca_followup_status = st.selectbox("RCA - Follow-up Status", ["", "Open", "In Progress", "Completed", "Deferred"])

st.divider()

# =========================================================
# CONTRIBUTING FACTORS
# =========================================================
st.markdown("### Contributing Factors (36 รายการ)")
st.caption("เลือกได้มากกว่า 1 รายการ ระบบจะบันทึกทั้งแบบสรุป และแยกเป็นคอลัมน์ CF_F0001 ... CF_F0036")

selected_factor_codes: List[str] = []
for group_label, group_df in contrib_df.groupby("group_label", sort=False):
    with st.expander(group_label, expanded=False):
        cols = st.columns(2)
        for idx, (_, row) in enumerate(group_df.iterrows()):
            col = cols[idx % 2]
            with col:
                checked = st.checkbox(
                    f"{row['code']} — {row['detail']}",
                    key=f"cf_{row['code']}",
                    value=False,
                )
                if checked:
                    selected_factor_codes.append(row["code"])

selected_factor_rows = contrib_df[contrib_df["code"].isin(selected_factor_codes)].copy()

if not selected_factor_rows.empty:
    st.success(f"เลือก contributing factor แล้ว {len(selected_factor_rows)} รายการ")
    st.dataframe(
        selected_factor_rows[["code", "detail"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("ยังไม่ได้เลือก contributing factor")

st.divider()

# =========================================================
# BUILD RECORD / PREVIEW / SAVE
# =========================================================
basic_fields = {
    "incident_date": incident_date.strftime("%d/%m/%Y"),
    "incident_time": incident_time.strftime("%H:%M"),
    "report_date": report_date.strftime("%d/%m/%Y"),
    "severity": severity,
    "status": status,
    "department": department.strip(),
    "location": location.strip(),
    "reporter": reporter.strip(),
    "hn": hn.strip(),
    "an_vn": an_vn.strip(),
    "patient_name": patient_name.strip(),
    "age": age.strip(),
    "sex": sex.strip(),
    "patient_type": patient_type.strip(),
    "description": description.strip(),
}

rca_fields = {
    "problem_statement": problem_statement.strip(),
    "timeline": timeline.strip(),
    "immediate_cause": immediate_cause.strip(),
    "root_cause": root_cause.strip(),
    "human_factors": human_factors.strip(),
    "system_factors": system_factors.strip(),
    "existing_barriers": existing_barriers.strip(),
    "barrier_gaps": barrier_gaps.strip(),
    "corrective_action": corrective_action.strip(),
    "preventive_action": preventive_action.strip(),
    "learning": learning.strip(),
    "owner": rca_owner.strip(),
    "due_date": rca_due_date.strftime("%Y-%m-%d"),
    "followup_status": rca_followup_status.strip(),
}

record = build_record_dict(
    selected_row=selected_row,
    basic_fields=basic_fields,
    rca_fields=rca_fields,
    selected_factor_rows=selected_factor_rows,
    all_factor_codes=all_factor_codes,
)

preview_df = ensure_all_columns(pd.DataFrame([record]), export_columns)

preview_col1, preview_col2 = st.columns([0.25, 0.75])
with preview_col1:
    save_clicked = st.button("💾 บันทึกข้อมูล", use_container_width=True)
with preview_col2:
    st.download_button(
        "⬇️ ดาวน์โหลดรายการนี้เป็น Excel",
        data=df_to_excel_bytes(preview_df, sheet_name="one_record"),
        file_name=f"incident_entry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

if save_clicked:
    if not description.strip():
        st.error("กรุณากรอกรายละเอียดการเกิด ก่อนบันทึก")
    else:
        append_record_to_csv(record, OUTPUT_CSV_PATH, export_columns)
        load_saved_records.clear()
        st.success(f"บันทึกข้อมูลเรียบร้อยแล้ว → {OUTPUT_CSV_PATH}")

with st.expander("Preview row ที่จะถูกบันทึก", expanded=False):
    st.dataframe(preview_df.T.rename(columns={0: "value"}), use_container_width=True)

with st.expander("Preview เฉพาะคอลัมน์สำคัญสำหรับ app.py", expanded=False):
    app_py_preview_cols = [
        "รหัส: เรื่องอุบัติการณ์",
        "วันที่เกิดอุบัติการณ์",
        "ความรุนแรง",
        "สถานะ",
        "รายละเอียดการเกิด",
        "รหัส",
        "ชื่ออุบัติการณ์ความเสี่ยง",
        "กลุ่ม",
        "หมวด",
        "PSG_ID",
        "หมวดหมู่มาตรฐานสำคัญ",
    ]
    st.dataframe(preview_df[app_py_preview_cols], use_container_width=True, hide_index=True)


# =========================================================
# RECENT / EXPORT ALL
# =========================================================
st.divider()
st.markdown("### ข้อมูลที่บันทึกล่าสุด")
saved_df = load_saved_records(str(OUTPUT_CSV_PATH))
if saved_df.empty:
    st.info("ยังไม่มีข้อมูลที่ถูกบันทึก")
else:
    saved_df = ensure_all_columns(saved_df, export_columns)
    st.dataframe(saved_df.tail(20), use_container_width=True, hide_index=True)

    download_col1, download_col2 = st.columns(2)
    with download_col1:
        st.download_button(
            "⬇️ ดาวน์โหลดทั้งหมดเป็น CSV",
            data=saved_df.to_csv(index=False, encoding="utf-8-sig"),
            file_name="incident_entry_records.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with download_col2:
        st.download_button(
            "⬇️ ดาวน์โหลดทั้งหมดเป็น Excel",
            data=df_to_excel_bytes(saved_df, sheet_name="incident_records"),
            file_name="incident_entry_records.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

st.divider()
with st.expander("Notes for integration", expanded=False):
    st.markdown(
        """
- คอลัมน์สำคัญที่ `app.py` ต้องใช้มีครบแล้ว ได้แก่ `รหัส: เรื่องอุบัติการณ์`, `วันที่เกิดอุบัติการณ์`, `ความรุนแรง`, `สถานะ`, `รายละเอียดการเกิด`
- ระบบจะเติม `กลุ่ม`, `หมวด`, `ประเภท`, `ประเภทย่อย`, `PSG_ID`, `หมวดหมู่มาตรฐานสำคัญ` ให้อัตโนมัติ
- กรณีไม่พบ mapping ใน PSG9 จะใช้ fallback เป็น `ไม่จัดอยู่ใน PSG9 Catalog`
- Contributing factor จะถูกเก็บ 2 แบบ:
  1. แบบสรุปใน `selected_contributing_factor_codes` และ `selected_contributing_factor_details`
  2. แบบแยกคอลัมน์ `CF_F0001 ... CF_F0036` เพื่อให้ง่ายต่อการวิเคราะห์ต่อ
        """
    )
