import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide", page_title="焊接专业完整课程逻辑图")

st.title("2024级材料成型及控制工程（焊接方向）完整课程逻辑导图")
st.caption("依据辽宁石油化工大学2024版培养方案绘制 [cite: 6, 135]")

# 完整 Mermaid 脚本：包含 8 个学期及全部 74 个课程节点
mermaid_code = """
graph LR
    %% 方向定义：从左往右展示 8 个学期
    
    %% 第一学年
    subgraph S1 [第1学期 - 11门]
        C1_1[大学外语1★]
        C1_2[高等数学D1★]
        C1_3[数据科学与智能技术概论]
        C1_4[工程制图与CAD II★]
        C1_5[劳动教育1]
        C1_6[军事理论]
        C1_7[军事技能训练]
        C1_8[雷锋精神概论]
        C1_9[思想道德与法治]
        C1_10[体育1]
        C1_11[形势与政策1]
    end

    subgraph S2 [第2学期 - 13门]
        C2_1[大学外语2★]
        C2_2[高等数学D2★]
        C2_3[大学物理F1★]
        C2_4[物理实验1]
        C2_5[Python语言程序设计★]
        C2_6[普通化学]
        C2_7[二维材料成型计算机绘图]
        C2_8[心理健康教育]
        C2_9[大学生职业生涯规划]
        C2_10[国家安全教育]
        C2_11[中国近现代史纲要]
        C2_12[体育2]
        C2_13[形势与政策2]
    end

    %% 第二学年
    subgraph S3 [第3学期 - 14门]
        C3_1[大学外语3★]
        C3_2[线性代数B★]
        C3_3[大学物理F2★]
        C3_4[物理实验2]
        C3_5[材料物理化学★]
        C3_6[工程力学B2★]
        C3_7[石油化工与智能制造概论C]
        C3_8[科技文献检索与写作]
        C3_9[三维材料成型计算机绘图]
        C3_10[工程导论]
        C3_11[工程训练B]
        C3_12[毛中特概论]
        C3_13[体育3]
        C3_14[形势与政策3]
    end

    subgraph S4 [第4学期 - 15门]
        C4_1[大学外语4★]
        C4_2[概率论与数理统计B★]
        C4_3[数值代数和计算方法]
        C4_4[数学建模]
        C4_5[电工与电子技术C★]
        C4_6[电工与电子技术C实验]
        C4_7[材料科学基础★]
        C4_8[热流体★]
        C4_9[劳动教育2]
        C4_10[养成教育]
        C4_11[创新创业基础]
        C4_12[工程项目管理与经济决策]
        C4_13[马克思主义基本原理★]
        C4_14[体育4]
        C4_15[形势与政策4]
    end

    %% 第三学年
    subgraph S5 [第5学期 - 12门]
        C5_1[数值模拟在材料成型中的应用]
        C5_2[弧焊电源及智能控制基础]
        C5_3[材料成型智能控制基础★]
        C5_4[材料成型方法及工艺★]
        C5_5[工程材料及热处理★]
        C5_6[工程材料基础实验]
        C5_7[金属凝固原理及技术]
        C5_8[工程材料冷加工基础★]
        C5_9[机械设计基础★]
        C5_10[机械设计基础课程设计]
        C5_11[模具设计]
        C5_12[认识实习]
        C5_13[习近平新时代中国特色思想概论]
    end

    subgraph S6 [第6学期 - 12门]
        C6_1[材料力学性能]
        C6_2[现代材料分析技术]
        C6_3[无损检测]
        C6_4[焊接方法及工艺★]
        C6_5[焊接质量检验与评价★]
        C6_6[焊接质量检验基础实验]
        C6_7[焊接冶金与金属焊接性★]
        C6_8[焊接结构★]
        C6_9[焊接结构课程设计]
        C6_10[焊接原理及工艺实验]
        C6_11[激光增材制造基础实验]
        C6_12[压力容器制造工艺及标准]
        C6_13[劳动教育3]
        C6_14[大学生就业指导]
    end

    %% 第四学年
    subgraph S7 [第7学期 - 10门]
        C7_1[专业外语]
        C7_2[增材制造技术]
        C7_3[焊接工艺课程设计]
        C7_4[绿色智能焊接新技术-双语]
        C7_5[绿色智能交叉焊接综合实验]
        C7_6[工业机器人]
        C7_7[智能化无损检测新技术]
        C7_8[公选课-8分5门]
        C7_9[创新创业/社会实践]
        C7_10[焊接生产管理及经济决策]
        C7_11[生产实习]
    end

    subgraph S8 [第8学期 - 2门]
        C8_1[毕业设计★]
        C8_2[形势与政策5-8]
    end

    %% 核心逻辑关系连线 (依据原图箭头还原)
    C1_1 --> C2_1 --> C3_1 --> C4_1 --> C7_1
    C1_2 --> C2_2 --> C3_2 --> C4_2 --> C5_1
    C1_4 --> C2_7 --> C3_9 --> C5_9
    C2_3 --> C2_4 --> C3_3 --> C3_4 --> C4_5
    C2_6 --> C3_5 --> C4_7 --> C5_5
    C4_7 --> C6_7
    C3_6 --> C5_9 --> C6_8
    C5_4 --> C6_4 --> C7_3
    C5_3 --> C6_4
    C6_8 --> C6_9
    C5_12 --> C7_11 --> C8_1
    C6_4 & C6_7 & C6_8 --> C7_3 --> C8_1
    C5_2 & C5_3 & C7_6 --> C8_1

    %% 样式美化
    style C8_1 fill:#f96,stroke:#333,stroke-width:4px
    style S7 fill:#fff2cc,stroke:#d6b656
    style S8 fill:#d5e8d4,stroke:#82b366
"""

# Streamlit 渲染函数
def render_mermaid(code):
    components.html(
        f\"\"\"
        <div class="mermaid">
            {code}
        </div>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ 
                startOnLoad: true,
                theme: 'base',
                themeVariables: {{
                    'primaryColor': '#e1f5fe',
                    'edgeLabelBackground':'#ffffff',
                    'tertiaryColor': '#eeeeee'
                }},
                flowchart: {{ 
                    useMaxWidth: false, 
                    htmlLabels: true,
                    curve: 'basis' 
                }}
            }});
        </script>
        \"\"\",
        height=1500,  # 增加高度以容纳所有课程
        scrolling=True
    )

render_mermaid(mermaid_code)