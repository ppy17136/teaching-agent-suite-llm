import streamlit as st
import google.generativeai as genai
import pdfplumber
import pandas as pd
import json
import time
import io
import sqlite3

# ==========================================
# 1. 初始化与配置
# ==========================================
st.set_page_config(page_title="培养方案全要素智能解析平台", layout="wide")

def init_db():
    conn = sqlite3.connect("master_curriculum.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS plan_data 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  category TEXT, content TEXT, update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    return conn

# ==========================================
# 2. 物理引擎：精准提取 PDF 表格 (来自“表格能显示”代码)
# ==========================================
def extract_tables_physically(pdf_file):
    all_page_tables = []
    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for j, table in enumerate(tables):
                df = pd.DataFrame(table)
                # 清洗表格：处理合并单元格产生的 None 值（向下填充）
                df = df.fillna(method='ffill', axis=0)
                # 尝试将第一行设为表头
                if not df.empty:
                    df.columns = df.iloc[0]
                    df = df.drop(0).reset_index(drop=True)
                all_page_tables.append({
                    "page": i + 1,
                    "table_no": j + 1,
                    "df": df
                })
    return all_page_tables

# ==========================================
# 3. 语义引擎：LLM 提取文本结构 (来自“其他很全”逻辑)
# ==========================================
def extract_text_struct(api_key, pdf_file):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemini-2.0-flash')
    pdf_content = pdf_file.getvalue()
    
    prompt = """
    你是一个教务管理专家。请从PDF中提取：
    1. 一至六部分的文本内容（培养目标、毕业要求、专业特色等）。
    2. 将毕业要求(二)拆解为编号、标题、具体内容。
    请仅输出纯JSON格式，包含键：objectives, grad_requirements, profile, degree_info, graduation_limit。
    """
    
    response = model.generate_content([prompt, {"mime_type": "application/pdf", "data": pdf_content}])
    clean_text = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_text)

# ==========================================
# 4. 主界面
# ==========================================
def main():
    st.title("🎓 培养方案全要素“双引擎”识别平台")
    st.info("综合优势：物理引擎确保表格不丢项，LLM 引擎确保文本结构化。")

    with st.sidebar:
        st.header("⚙️ 配置")
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
        else:
            api_key = st.text_input("Enter API Key", type="password")
        
        uploaded_file = st.file_uploader("上传培养方案 PDF", type=['pdf'])
        run_btn = st.button("开始混合模式识别", type="primary")

    if run_btn and uploaded_file and api_key:
        # 第一步：物理抽取表格 (快且准)
        with st.spinner("物理引擎正在抽取所有附表..."):
            st.session_state.tables = extract_tables_physically(uploaded_file)
        
        # 第二步：语义抽取文本 (深且活)
        with st.spinner("语义引擎正在解析大纲结构..."):
            try:
                st.session_state.struct = extract_text_struct(api_key, uploaded_file)
                st.success("全要素识别完成！")
            except Exception as e:
                st.error(f"语义解析失败: {e}")

    # --- 展示与校对区域 ---
    if "struct" in st.session_state or "tables" in st.session_state:
        tabs = st.tabs(["📄 文本大纲校对", "📊 附表全量展示", "💾 数据封存"])
        
        with tabs[0]:
            s = st.session_state.get("struct", {})
            st.subheader("一、培养目标")
            s['objectives'] = st.text_area("内容", s.get('objectives', ''), height=150)
            
            st.subheader("二、毕业要求指标点")
            grad_df = pd.DataFrame(s.get('grad_requirements', []))
            s['grad_requirements'] = st.data_editor(grad_df, num_rows="dynamic", use_container_width=True).to_dict('records')
            
            st.subheader("三至六部分")
            s['profile'] = st.text_area("专业定位", s.get('profile', ''))
            s['degree_info'] = st.text_input("学制学位", s.get('degree_info', ''))

        with tabs[1]:
            st.subheader("所有识别到的原始表格")
            st.caption("提示：物理引擎按页码抽取，您可以直接修改单元格内容。")
            
            for i, item in enumerate(st.session_state.get("tables", [])):
                with st.expander(f"第 {item['page']} 页 - 表格 {item['table_no']}", expanded=(i==0)):
                    # 这里是核心：使用 data_editor 实现完美展示和修改
                    new_df = st.data_editor(item['df'], key=f"editor_{i}", use_container_width=True)
                    st.session_state.tables[i]['df'] = new_df

        with tabs[2]:
            st.warning("校对完成后，点击下方按钮将结构化文本和表格存入权威数据库。")
            if st.button("确认校对，存入数据库"):
                conn = init_db()
                # 存文本
                conn.execute("INSERT INTO plan_data (category, content) VALUES (?, ?)", 
                             ("TEXT_STRUCT", json.dumps(st.session_state.struct, ensure_ascii=False)))
                # 存表格
                table_data = [{"page": t['page'], "data": t['df'].to_dict('records')} for t in st.session_state.tables]
                conn.execute("INSERT INTO plan_data (category, content) VALUES (?, ?)", 
                             ("TABLES", json.dumps(table_data, ensure_ascii=False)))
                conn.commit()
                st.success("数据已成功合成并存入数据库！")

if __name__ == "__main__":
    main()