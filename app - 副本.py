# app.py
# -*- coding: utf-8 -*-
"""
培养方案 PDF 全量抽取（文本 + 表格 + 结构化解析）- 优化合成版
综合了：
1. app其他很全，但表格未显示.py 的文本结构识别能力
2. app表格能显示.py 的表格提取和展示能力
"""

from __future__ import annotations

import io
import json
import re
import zipfile
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

# 依赖：pdfplumber
try:
    import pdfplumber
except Exception as e:
    pdfplumber = None
    st.error(f"缺少依赖 pdfplumber: {e}")

# ----------------------------
# 基础工具
# ----------------------------
def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

def clean_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def normalize_multiline(text: str) -> str:
    """保留换行，做基础清理，便于正则分段。"""
    if text is None:
        return ""
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [clean_text(ln) for ln in text.split("\n")]
    out: List[str] = []
    blank = 0
    for ln in lines:
        if ln.strip() == "":
            blank += 1
            if blank <= 2:
                out.append("")
        else:
            blank = 0
            out.append(ln)
    return "\n".join(out).strip()

def make_unique_columns(cols: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    out: List[str] = []
    for c in cols:
        c0 = clean_text(c) or "col"
        if c0 not in seen:
            seen[c0] = 1
            out.append(c0)
        else:
            seen[c0] += 1
            out.append(f"{c0}_{seen[c0]}")
    return out

def postprocess_table_df(df: pd.DataFrame) -> pd.DataFrame:
    """表格后处理：去空白、去 NaN、合并格造成的空白做向下填充。"""
    if df is None or df.empty:
        return df

    df = df.copy()
    df = df.replace({None: ""}).fillna("")
    for c in df.columns:
        df[c] = df[c].astype(str).map(lambda x: clean_text(x))

    # 1) 删除完全空行
    mask_all_empty = df.apply(lambda r: all((clean_text(x) == "" for x in r.values.tolist())), axis=1)
    df = df.loc[~mask_all_empty].reset_index(drop=True)

    # 2) 向下填充（合并格常见列）
    fill_down_keywords = ["课程体系", "课程模块", "课程性质", "课程类别", "类别", "模块", "环节", "学期", "方向"]
    for c in df.columns:
        if any(k in str(c) for k in fill_down_keywords):
            last = ""
            new_col = []
            for v in df[c].tolist():
                if v != "":
                    last = v
                    new_col.append(v)
                else:
                    new_col.append(last)
            df[c] = new_col

    return df

def normalize_table(raw_table: List[List[Any]]) -> List[List[str]]:
    """
    pdfplumber.extract_tables() 返回 list[list[str|None]]
    这里做基础清洗：去空行、补齐列数、去掉全空列
    """
    if not raw_table:
        return []

    rows = []
    max_cols = 0
    for r in raw_table:
        if r is None:
            continue
        rr = [clean_text(c) for c in r]
        # 跳过全空行
        if all(c == "" for c in rr):
            continue
        rows.append(rr)
        max_cols = max(max_cols, len(rr))

    if not rows or max_cols == 0:
        return []

    # 补齐列数
    for i in range(len(rows)):
        if len(rows[i]) < max_cols:
            rows[i] = rows[i] + [""] * (max_cols - len(rows[i]))

    # 去掉全空列
    keep_cols = []
    for j in range(max_cols):
        col = [rows[i][j] for i in range(len(rows))]
        if any(c != "" for c in col):
            keep_cols.append(j)

    if not keep_cols:
        return []

    cleaned = [[row[j] for j in keep_cols] for row in rows]
    return cleaned

def table_to_df(cleaned_table: List[List[str]]) -> pd.DataFrame:
    """
    尝试把第一行当表头；如果表头太差就用默认列名。
    """
    if not cleaned_table or len(cleaned_table) == 0:
        return pd.DataFrame()
    
    if len(cleaned_table) == 1:
        # 只有一行，做单行df
        return pd.DataFrame([cleaned_table[0]])

    header = cleaned_table[0]
    body = cleaned_table[1:]

    # 表头判定：至少有一半单元格非空
    non_empty = sum(1 for x in header if clean_text(x) != "")
    if non_empty >= max(1, len(header) // 2):
        cols = [h if h else f"col_{i+1}" for i, h in enumerate(header)]
        df = pd.DataFrame(body, columns=cols)
    else:
        # 否则不用表头
        df = pd.DataFrame(cleaned_table)

    return postprocess_table_df(df)

# ----------------------------
# PDF 抽取：文本 + 表格 (使用 pdfplumber 的表格提取)
# ----------------------------
def extract_pages_text_and_tables(pdf_bytes: bytes, enable_ocr: bool = False) -> Tuple[List[Dict[str, Any]], str]:
    """
    提取每页的文本和表格
    返回：页面数据列表（含文本和表格），全文文本
    """
    if pdfplumber is None:
        return [], ""
    
    pages_data = []
    full_text_parts = []
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        # 表格设置：偏"宽松"，提升跨页/复杂表格提取成功率
        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "intersection_tolerance": 5,
            "snap_tolerance": 3,
            "join_tolerance": 3,
            "edge_min_length": 3,
            "min_words_vertical": 1,
            "min_words_horizontal": 1,
            "text_tolerance": 2,
        }
        
        for idx, page in enumerate(pdf.pages, start=1):
            # 提取文本
            text = page.extract_text() or ""
            text = normalize_multiline(text)
            
            # 如果需要OCR且文本太少
            if enable_ocr and len(text) < 50:
                try:
                    import pytesseract
                    from PIL import Image
                    img = page.to_image(resolution=220).original
                    ocr_text = pytesseract.image_to_string(img, lang="chi_sim+eng")
                    if len(ocr_text) > len(text):
                        text = normalize_multiline(ocr_text)
                except Exception:
                    pass
            
            full_text_parts.append(text)
            
            # 提取表格
            raw_tables = []
            try:
                raw_tables = page.extract_tables(table_settings=table_settings) or []
            except Exception:
                raw_tables = []
            
            # 清洗表格
            cleaned_tables = []
            for t in raw_tables:
                ct = normalize_table(t)
                if ct:
                    cleaned_tables.append(ct)
            
            pages_data.append({
                "page": idx,
                "text": text,
                "tables": cleaned_tables,
                "tables_count": len(cleaned_tables)
            })
    
    full_text = "\n".join(full_text_parts)
    return pages_data, full_text

# ----------------------------
# 结构化解析：章节/毕业要求/培养目标/附表标题
# ----------------------------
def split_sections(full_text: str) -> Dict[str, str]:
    """
    按 "一、/二、/三、..." 大章切分。
    兼容：三、 / 三. / 三．
    """
    text = normalize_multiline(full_text)
    lines = text.splitlines()
    pat = re.compile(r"^\s*([一二三四五六七八九十]+)\s*[、\.．]\s*([^\n\r]+?)\s*$")

    sections: Dict[str, List[str]] = {}
    cur_key = "封面/前言"

    for ln in lines:
        m = pat.match(ln)
        if m:
            num = m.group(1)
            title = clean_text(m.group(2))
            cur_key = f"{num}、{title}"
            sections.setdefault(cur_key, [])
        else:
            sections.setdefault(cur_key, []).append(ln)

    return {k: "\n".join(v).strip() for k, v in sections.items()}

def extract_appendix_titles(full_text: str) -> Dict[str, str]:
    """抽取"附表X -> 标题（可能含七、八…）"""
    titles: Dict[str, str] = {}
    text = normalize_multiline(full_text)
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # 1) 附表1：XXXX
        m = re.search(r"(附表\s*\d+)\s*[:：]\s*(.+)$", line)
        if m:
            key = re.sub(r"\s+", "", m.group(1))
            val = clean_text(m.group(2))
            if val:
                titles[key] = val
            continue

        # 2) 七、XXXX（附表1）
        m = re.search(r"^(?P<title>.+?)\s*[（(]\s*(?P<key>附表\s*\d+)\s*[)）]\s*$", line)
        if m:
            key = re.sub(r"\s+", "", m.group("key"))
            val = clean_text(m.group("title"))
            if val:
                titles[key] = val
            continue

        # 3) 行内出现（附表X）
        m = re.search(r"(?P<title>.+?)\s*[（(]\s*(?P<key>附表\s*\d+)\s*[)）]", line)
        if m:
            key = re.sub(r"\s+", "", m.group("key"))
            val = clean_text(m.group("title"))
            if val and key not in titles:
                titles[key] = val

    return titles

def parse_training_objectives(section_text: str) -> Dict[str, Any]:
    """
    提取"培养目标"条目。返回 items(list[str]) + raw。
    尽量包容：1) / 1． / 1、 / （1）等。
    """
    raw = normalize_multiline(section_text)
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    items: List[str] = []

    pat = re.compile(r"^(?:（?\s*\d+\s*）?|\d+\s*[\.、．])\s*(.+)$")
    for ln in lines:
        m = pat.match(ln)
        if m:
            body = clean_text(m.group(1))
            if body:
                items.append(body)

    # 如果没抓到编号条目，退化：取前若干行（不丢信息）
    if not items:
        items = lines[:30]

    return {"count": len(items), "items": items, "raw": raw}

def parse_graduation_requirements(text_any: str) -> Dict[str, Any]:
    """
    抽取 12 条毕业要求及其分项 1.1/1.2…
    返回结构：{"count":..,"items":[{"no":1,"title":"工程知识","body":"...","subitems":[...]}], "raw":...}
    """
    text = normalize_multiline(text_any or "")

    # 定位"二、毕业要求"
    start = re.search(r"(?m)^\s*(二\s*[、\.．]?\s*毕业要求|毕业要求)\s*$", text)
    if start:
        tail = text[start.start():]
    else:
        tail = text

    # 截断到下一大章
    end = re.search(r"(?m)^\s*[三四五六七八九十]\s*[、\.．]", tail)
    if end:
        tail = tail[:end.start()]

    lines = [ln.strip() for ln in tail.splitlines()]

    main_pat = re.compile(r"^(?P<no>\d{1,2})\s*[\.、](?!\d)\s*(?P<body>.+)$")   # 1. xxx (排除 1.1)
    sub_pat = re.compile(r"^(?P<no>\d{1,2}\.\d{1,2})\s+(?P<body>.+)$")       # 1.1 xxx

    items: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    cur_sub: Optional[Dict[str, Any]] = None

    def flush_sub():
        nonlocal cur_sub, cur
        if cur is not None and cur_sub is not None:
            cur.setdefault("subitems", []).append(cur_sub)
        cur_sub = None

    def flush_item():
        nonlocal cur
        if cur is not None:
            cur["title"] = clean_text(cur.get("title", ""))
            cur["body"] = clean_text(cur.get("body", ""))
            for s in cur.get("subitems", []):
                s["body"] = clean_text(s.get("body", ""))
            items.append(cur)
        cur = None

    for ln in lines:
        if not ln:
            continue

        m_main = main_pat.match(ln)
        m_sub = sub_pat.match(ln)

        if m_main:
            flush_sub()
            flush_item()
            no = int(m_main.group("no"))
            body_full = clean_text(m_main.group("body"))

            # 处理"工程知识：..."这种
            title = ""
            body = body_full
            if "：" in body_full:
                title, body = body_full.split("：", 1)
                title = clean_text(title)
                body = clean_text(body)

            cur = {"no": no, "title": title, "body": body, "subitems": []}
            continue

        if m_sub and cur is not None:
            flush_sub()
            cur_sub = {"no": m_sub.group("no"), "body": clean_text(m_sub.group("body"))}
            continue

        # 续行
        if cur_sub is not None:
            cur_sub["body"] += " " + ln
        elif cur is not None:
            cur["body"] += " " + ln

    flush_sub()
    flush_item()

    items = sorted(items, key=lambda x: x.get("no", 999))
    if len(items) > 12:
        items = [x for x in items if 1 <= x.get("no", 0) <= 12]

    return {"count": len(items), "items": items, "raw": tail.strip()}

# ----------------------------
# 表格标题/方向识别
# ----------------------------
def guess_table_appendix_by_page(page_no: int) -> Optional[str]:
    """
    针对常见培养方案（本样例 18 页）：
    10-11 附表1，12 附表2，13-14 附表3，15 附表4，16 附表5
    如果换不同模板，请自行调整或改为更智能的页内检测。
    """
    mapping = {
        10: "附表1", 11: "附表1",
        12: "附表2",
        13: "附表3", 14: "附表3",
        15: "附表4",
        16: "附表5",
    }
    return mapping.get(page_no)

def infer_table_title_from_page_text(page_text: str, appendix: Optional[str], appendix_titles: Dict[str, str], page_no: int) -> str:
    if appendix and appendix in appendix_titles:
        return appendix_titles[appendix]

    if appendix:
        m = re.search(rf"(?P<title>[^\n\r]{{2,120}}?)\s*[（(]\s*{re.escape(appendix)}\s*[)）]", page_text)
        if m:
            return clean_text(m.group("title"))

    m = re.search(r"(附表\s*\d+)\s*[:：]\s*([^\n\r]{2,120})", page_text)
    if m:
        return clean_text(m.group(2))

    return appendix or f"第{page_no}页表格"

def infer_direction_for_page(page_text: str) -> str:
    has_weld = "焊接" in page_text
    has_ndt = ("无损" in page_text) or ("无损检测" in page_text)
    if has_weld and has_ndt:
        return "混合（焊接+无损检测）"
    if has_weld:
        return "焊接"
    if has_ndt:
        return "无损检测"
    return ""

def add_direction_column_rowwise(df: pd.DataFrame, page_direction: str) -> pd.DataFrame:
    """
    行级方向识别：若表内有"焊接方向/无损检测方向"分隔行，则从该行开始向下标注。
    若识别不到，则使用 page_direction。
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    cur_dir = ""
    dirs = []
    for _, row in df.iterrows():
        row_txt = " ".join([clean_text(x) for x in row.values.tolist()])
        if re.search(r"焊接.*方向", row_txt):
            cur_dir = "焊接"
        elif re.search(r"无损.*方向", row_txt) or re.search(r"无损检测.*方向", row_txt):
            cur_dir = "无损检测"

        dirs.append(cur_dir or page_direction)

    # 插到最前
    if "专业方向" not in df.columns:
        df.insert(0, "专业方向", dirs)
    else:
        df["专业方向"] = [d or page_direction for d in dirs]

    return df

# ----------------------------
# 输出结构
# ----------------------------
@dataclass
class TablePack:
    page: int
    title: str
    appendix: str
    direction: str
    columns: List[str]
    rows: List[List[Any]]

@dataclass
class ExtractResult:
    page_count: int
    table_count: int
    ocr_used: bool
    file_sha256: str
    extracted_at: str
    pages_data: List[Dict[str, Any]]
    sections: Dict[str, str]
    appendix_titles: Dict[str, str]
    training_objectives: Dict[str, Any]
    graduation_requirements: Dict[str, Any]
    tables: List[Dict[str, Any]]  # TablePack as dict

# ----------------------------
# 主流程
# ----------------------------
def run_full_extract(pdf_bytes: bytes, use_ocr: bool = False) -> ExtractResult:
    # 1) 提取页面文本和表格
    pages_data, full_text = extract_pages_text_and_tables(pdf_bytes, enable_ocr=use_ocr)
    
    # 2) 结构化解析
    sections = split_sections(full_text)
    appendix_titles = extract_appendix_titles(full_text)
    
    # 3) 关键结构化：培养目标、毕业要求
    obj_key = next((k for k in sections.keys() if "培养目标" in k), "")
    obj = parse_training_objectives(sections.get(obj_key, "") or full_text)
    grad = parse_graduation_requirements(full_text)
    
    # 4) 处理表格
    tables: List[TablePack] = []
    total_tables = 0
    
    for page_data in pages_data:
        page_no = page_data["page"]
        page_text = page_data["text"]
        page_tables = page_data["tables"]
        
        total_tables += len(page_tables)
        
        appendix = guess_table_appendix_by_page(page_no) or ""
        base_title = infer_table_title_from_page_text(page_text, appendix or None, appendix_titles, page_no)
        title = f"{base_title}（{appendix}）" if appendix and appendix not in base_title else base_title
        page_dir = infer_direction_for_page(page_text)
        
        for i, table_data in enumerate(page_tables):
            df = table_to_df(table_data)
            if df is not None and not df.empty:
                df2 = add_direction_column_rowwise(df, page_dir)
                sub_title = title if len(page_tables) == 1 else f"{title} - 表{i+1}"
                pack = TablePack(
                    page=page_no,
                    title=sub_title,
                    appendix=appendix,
                    direction=page_dir,
                    columns=[str(c) for c in df2.columns],
                    rows=df2.values.tolist(),
                )
                tables.append(pack)
    
    result = ExtractResult(
        page_count=len(pages_data),
        table_count=total_tables,
        ocr_used=use_ocr,
        file_sha256=sha256_bytes(pdf_bytes),
        extracted_at=datetime.now().isoformat(timespec="seconds"),
        pages_data=pages_data,
        sections=sections,
        appendix_titles=appendix_titles,
        training_objectives=obj,
        graduation_requirements=grad,
        tables=[asdict(t) for t in tables],
    )
    return result

# ----------------------------
# 导出功能
# ----------------------------
def safe_df_from_tablepack(t: Dict[str, Any]) -> pd.DataFrame:
    """从 TablePack 字典创建 DataFrame"""
    cols = t.get("columns") or []
    rows = t.get("rows") or []
    
    if rows and len(rows) > 0:
        df = pd.DataFrame(rows, columns=cols)
        return postprocess_table_df(df)
    return pd.DataFrame()

def make_tables_zip(tables: List[Dict[str, Any]]) -> bytes:
    """CSV + tables.json 打包"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("tables.json", json.dumps(tables, ensure_ascii=False, indent=2))
        for idx, t in enumerate(tables, start=1):
            title = clean_text(t.get("title") or f"table_{idx}")
            title_safe = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_\-]+", "_", title)[:80].strip("_") or f"table_{idx}"

            df = safe_df_from_tablepack(t)

            # 方向列
            direction = clean_text(t.get("direction") or "")
            if direction and "专业方向" not in df.columns:
                df.insert(0, "专业方向", direction)

            csv_bytes = df.to_csv(index=False, encoding="utf-8-sig")
            zf.writestr(f"{idx:02d}_{title_safe}.csv", csv_bytes)
    return buf.getvalue()

def build_json_bytes(result: ExtractResult) -> bytes:
    """构建 JSON 导出文件"""
    return json.dumps(asdict(result), ensure_ascii=False, indent=2).encode("utf-8")

# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="培养方案PDF全量抽取（优化合成版）", layout="wide")

st.markdown("""
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 98vw; }
</style>
""", unsafe_allow_html=True)

st.title("培养方案 PDF 全量抽取（文本 + 表格 + 结构化解析）")
st.info("上传培养方案 PDF → 一键抽取全文文本、章节结构、毕业要求、培养目标、附表表格，并可下载 JSON/CSV。")

with st.sidebar:
    st.markdown("## 上传与抽取")
    uploaded = st.file_uploader("上传培养方案 PDF", type=["pdf"])
    use_ocr = st.checkbox("对无文本页启用 OCR（可选）", value=False, 
                         help="对于扫描版或图片版PDF，可以尝试启用OCR（需要安装pytesseract和tesseract-ocr）。")
    run_btn = st.button("开始全量抽取", type="primary")

if "extract_result" not in st.session_state:
    st.session_state["extract_result"] = None

if run_btn:
    if not uploaded:
        st.warning("请先上传 PDF。")
    else:
        pdf_bytes = uploaded.getvalue()
        with st.spinner("正在抽取…"):
            st.session_state["extract_result"] = run_full_extract(pdf_bytes, use_ocr=use_ocr)

result: Optional[ExtractResult] = st.session_state.get("extract_result")

if result is None:
    st.stop()

# 概览指标
c1, c2, c3, c4 = st.columns(4)
c1.metric("总页数", result.page_count)
c2.metric("表格总数", result.table_count)
c3.metric("OCR启用", "是" if result.ocr_used else "否")
c4.caption(f"SHA256: {result.file_sha256[:16]}...")

tabs = st.tabs(["概览与下载", "章节大标题（全部）", "培养目标", "毕业要求（12条）", "附表表格（可下载CSV）", "分页原文与表格"])

# ---- Tab 0 概览与下载
with tabs[0]:
    st.markdown("### 结构化识别结果（可先在这里校对）")

    # 下载 JSON（全量）
    json_bytes = build_json_bytes(result)
    st.download_button(
        "下载抽取结果 JSON（全量基础库）",
        data=json_bytes,
        file_name="training_plan_full_extract.json",
        mime="application/json",
        use_container_width=True,
    )

    if result.tables:
        zip_bytes = make_tables_zip(result.tables)
        st.download_button(
            "下载表格 ZIP（CSV + tables.json）",
            data=zip_bytes,
            file_name="training_plan_tables.zip",
            mime="application/zip",
            use_container_width=True,
        )
    
    st.markdown("#### 附表标题映射（用于给表格命名）")
    if result.appendix_titles:
        st.json(result.appendix_titles)
    else:
        st.info("未在正文中检测到附表标题映射（不影响表格抽取，但表名可能不够精准）。")

# ---- Tab 1 章节大标题
with tabs[1]:
    st.markdown("### 章节大标题（用于确保'三~六'等内容不丢）")
    st.caption("这里展示 split_sections 抽到的全部大章标题，点击可展开查看正文（用于溯源和校对）。")
    for k in result.sections.keys():
        with st.expander(k, expanded=False):
            st.text(result.sections.get(k, ""))

# ---- Tab 2 培养目标
with tabs[2]:
    st.markdown("### 1）培养目标（可编辑/校对）")
    st.caption("若培养目标有多方向版本（焊接/无损），后续可在此基础上增强为分方向抽取。")

    obj = result.training_objectives
    st.write(f"识别条目数：**{obj.get('count', 0)}**")
    st.text_area("培养目标（逐条）", value="\n".join(obj.get("items", [])), height=220)
    with st.expander("原始文本（培养目标段）"):
        st.text(obj.get("raw", ""))

# ---- Tab 3 毕业要求
with tabs[3]:
    st.markdown("### 2）毕业要求（12条 + 分项）")
    grad = result.graduation_requirements
    st.write(f"识别主条目数：**{grad.get('count', 0)}**（理想为 12）")

    items = grad.get("items", [])
    if not items:
        st.warning("未识别到毕业要求，请在'分页原文'中确认 PDF 是否可提取文本。")
    else:
        for it in items:
            no = it.get("no")
            title = it.get("title") or ""
            body = it.get("body") or ""
            header = f"{no}. {title}".strip()
            with st.expander(header, expanded=(no in [1, 2])):
                st.write(body)
                subs = it.get("subitems", [])
                if subs:
                    st.markdown("**分项：**")
                    for s in subs:
                        st.write(f"- {s.get('no')}: {s.get('body')}")
    with st.expander("原始文本（毕业要求段）"):
        st.text(grad.get("raw", ""))

# ---- Tab 4 表格
with tabs[4]:
    st.markdown("### 3）附表表格（表名 + 方向尽量清晰）")
    if not result.tables:
        st.info("未检测到表格。请检查PDF是否有表格，或尝试启用OCR。")
    else:
        # 方向过滤
        all_dirs = sorted({clean_text(t.get("direction") or "") for t in result.tables if clean_text(t.get("direction") or "")})
        opt_dirs = ["全部"] + all_dirs
        sel = st.selectbox("方向过滤", opt_dirs, index=0)

        for t in result.tables:
            direction = clean_text(t.get("direction") or "")
            if sel != "全部" and direction != sel:
                continue

            st.subheader(f"第{t.get('page')}页｜{t.get('title')}")
            if direction:
                st.caption(f"页面方向提示：{direction}")

            df = safe_df_from_tablepack(t)
            st.dataframe(df, use_container_width=True, hide_index=True)

# ---- Tab 5 分页原文与表格
with tabs[5]:
    st.markdown("### 4）分页原文与表格（用于溯源/调试抽取缺失）")
    
    for page_data in result.pages_data:
        page_no = page_data["page"]
        page_text = page_data["text"]
        page_tables = page_data["tables"]
        
        with st.expander(f"第{page_no}页（{len(page_tables)}个表格）", expanded=False):
            st.text(page_text)
            
            if page_tables:
                st.markdown(f"**表格 ({len(page_tables)}个):**")
                for i, table_data in enumerate(page_tables, start=1):
                    df = table_to_df(table_data)
                    if not df.empty:
                        st.markdown(f"**表格 {i}:**")
                        st.dataframe(df, use_container_width=True, height=200)
                    else:
                        st.info(f"表格 {i} 为空或无法解析")