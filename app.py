import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import sqlite3
import graphviz
from typing import Dict, Any

# ==========================================
# 1. 页面配置
# ==========================================
st.set_page_config(page_title="培养方案全要素数字化平台", layout="wide")

def init_db():
    conn = sqlite3.connect("curriculum_system.db")
    c = conn.cursor()
    # 存储 11 个模块的最终确权数据
    c.execute('''CREATE TABLE IF NOT EXISTS training_plan 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  section_id TEXT, 
                  section_name TEXT, 
                  content_json TEXT, 
                  status TEXT,
                  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    return conn

# ==========================================
# 2. Gemini 深度抽取引擎
# ==========================================
def extract_full_plan(api_key: str, pdf_file):
    genai.configure(api_key=api_key)
    # 使用 1.5 Pro 以处理长文本和复杂的表格图像
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    你是一个教育专家和数据分析师。请完整识别并抽取上传培养方案PDF中的所有内容。
    必须严格按照以下 11 个标题进行分类，并输出为 JSON 格式：

    【文字部分】
    1. "objectives": 抽取“一、培养目标”的完整文字。
    2. "requirements": 抽取“二、毕业要求”，包含指标点编号和具体描述。
    3. "positioning": 抽取“三、专业定位与特色”。
    4. "core_elements": 抽取“四、主干学科、专业核心课程和主要实践性教学环节”。
    5. "degree": 抽取“五、标准学制与授予学位”。
    6. "graduation_conditions": 抽取“六、毕业条件”。

    【表格部分 - 需转化为结构化列表】
    7. "appendix_1_plan": “七、专业教学计划表（附表1）”，包含课程代码、名称、学分、各学期学时等。
    8. "appendix_2_credits": “八、学分统计表（附表2）”，分类统计各模块学分。
    9. "appendix_3_process": “九、教学进程表（附表3）”。
    10. "appendix_4_matrix": “十、课程设置对毕业要求支撑关系表（附表4）”，提取课程对指标点的支撑强度（H/M/L）。

    【图形部分】
    11. "appendix_5_logic": “十一、课程设置逻辑思维导图(附表5)”，请根据图片逻辑，输出一套符合 Graphviz DOT 格式的绘图代码。

    要求：
    - 不要总结，要原文提取。
    - 表格务必保持行列对应的逻辑。
    - 只返回纯 JSON，不要包含 Markdown 标记。
    """
    
    pdf_content = pdf_file.getvalue()
    response = model.generate_content([
        prompt,
        {"mime_type": "application/pdf", "data": pdf_content}
    ])
    
    # 清理返回的 JSON 字符串
    clean_json = response.text.strip().replace("```json", "").replace("```", "")
    return json.loads(clean_json)

# ==========================================
# 3. Streamlit UI 界面
# ==========================================
def main():
    st.sidebar.title("⚙️ 控制面板")
    
    #api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")
    # 优先从 Streamlit Secrets 读取，如果没有则显示输入框
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        api_key = st.sidebar.text_input("输入 Gemini API Key", type="password", help="未在 Secrets 中检测到 Key，请手动输入")    
    uploaded_file = st.sidebar.file_uploader("上传 2024 级培养方案 PDF", type=['pdf'])
    
    if "data" not in st.session_state:
        st.session_state.data = None

    if st.sidebar.button("🚀 开始全量识别", type="primary"):
        if not api_key or not uploaded_file:
            st.error("请确保已输入 API Key 并上传文件")
        else:
            with st.spinner("Gemini 正在深度解析 11 个模块，请稍候..."):
                try:
                    result = extract_full_plan(api_key, uploaded_file)
                    st.session_state.data = result
                    st.success("识别成功！请切换标签页进行校对。")
                except Exception as e:
                    st.error(f"解析出错: {e}")

    st.title("📖 培养方案全要素校对与管理平台")
    st.info("说明：此页面数据为后续所有教学文件（教学大纲、任务书等）的基准源，请仔细校对。")

    if st.session_state.data:
        d = st.session_state.data
        
        # 按照用户需求的标题建立标签页
        tabs = st.tabs([
            "1-3 目标/要求/特色", 
            "4-6 课程/学位/毕业", 
            "7 教学计划表(附表1)", 
            "8-9 学分/进程(附2-3)", 
            "10 支撑矩阵(附表4)", 
            "11 逻辑导图(附表5)"
        ])

        with tabs[0]:
            st.header("一、二、三部分")
            d['objectives'] = st.text_area("一、培养目标", d.get('objectives', ''), height=150)
            
            st.subheader("二、毕业要求")
            req_df = pd.DataFrame(d.get('requirements', []))
            d['requirements'] = st.data_editor(req_df, num_rows="dynamic", use_container_width=True).to_dict('records')
            
            d['positioning'] = st.text_area("三、专业定位与特色", d.get('positioning', ''), height=150)

        with tabs[1]:
            st.header("四、五、六部分")
            d['core_elements'] = st.text_area("四、主干学科/核心课程/实践环节", d.get('core_elements', ''), height=200)
            d['degree'] = st.text_input("五、标准学制与授予学位", d.get('degree', ''))
            d['graduation_conditions'] = st.text_area("六、毕业条件", d.get('graduation_conditions', ''), height=150)

        with tabs[2]:
            st.header("七、专业教学计划表（附表1）")
            plan_df = pd.DataFrame(d.get('appendix_1_plan', []))
            d['appendix_1_plan'] = st.data_editor(plan_df, num_rows="dynamic", use_container_width=True).to_dict('records')

        with tabs[3]:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("八、学分统计表（附表2）")
                credit_df = pd.DataFrame(d.get('appendix_2_credits', []))
                d['appendix_2_credits'] = st.data_editor(credit_df, num_rows="dynamic").to_dict('records')
            with col2:
                st.subheader("九、教学进程表（附表3）")
                process_df = pd.DataFrame(d.get('appendix_3_process', []))
                d['appendix_3_process'] = st.data_editor(process_df, num_rows="dynamic").to_dict('records')

        with tabs[4]:
            st.header("十、课程设置对毕业要求支撑关系表（附表4）")
            matrix_df = pd.DataFrame(d.get('appendix_4_matrix', []))
            d['appendix_4_matrix'] = st.data_editor(matrix_df, num_rows="dynamic", use_container_width=True).to_dict('records')

        with tabs[5]:
            st.header("十一、课程设置逻辑思维导图(附表5)")
            dot_code = st.text_area("Graphviz 代码校对", d.get('appendix_5_logic', ''), height=200)
            if dot_code:
                try:
                    st.graphviz_chart(dot_code)
                    d['appendix_5_logic'] = dot_code
                except:
                    st.error("Graphviz 语法错误，请检查。")

        # 保存持久化
        if st.button("💾 确认校对并保存到权威数据库", type="primary", use_container_width=True):
            conn = init_db()
            c = conn.cursor()
            for key, val in d.items():
                c.execute("INSERT INTO training_plan (section_id, content_json, status) VALUES (?, ?, ?)",
                          (key, json.dumps(val, ensure_ascii=False), "Verified"))
            conn.commit()
            st.success("所有数据已成功封存！后续模块可直接调用。")

    else:
        st.write("---")
        st.info("👈 请在左侧侧边栏上传 PDF 培养方案并点击“开始全量识别”")

if __name__ == "__main__":
    main()