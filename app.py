import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide")

st.title("2024级材料成型及控制工程（焊接方向）课程逻辑 - 完整版")

# 补全后的 Mermaid 逻辑代码
full_mermaid_code = """
graph TD
    %% 第一学年：基础夯实
    subgraph S1 [第1学期]
        C1_Math[高等数学D1★]
        C1_Draw[工程制图与CAD II*]
        C1_Smart[数据科学与智能技术概论]
        C1_Eng[大学外语1*]
    end

    subgraph S2 [第2学期]
        C2_Math[高等数学D2★]
        C2_Phys[大学物理F1★]
        C2_Py[Python语言程序设计*]
        C2_Chem[普通化学]
        C2_Draw2[二维材料成型计算机绘图]
    end

    %% 第二学年：学科转接
    subgraph S3 [第3学期]
        C3_Lin[线性代数B*]
        C3_Phys[大学物理F2★]
        C3_Mech[工程力学B2★]
        C3_PChem[材料物理化学*]
        C3_Draw3[三维材料成型计算机绘图]
    end

    subgraph S4 [第4学期]
        C4_MS[材料科学基础★]
        C4_Elec[电工与电子技术C★]
        C4_Prob[概率论与数理统计B*]
        C4_Proj[工程项目管理与经济决策]
    end

    %% 第三学年：专业核心与实验 (您图中缺失的部分开始)
    subgraph S5 [第5学期]
        C5_Proc[材料成型方法及工艺★]
        C5_MDes[机械设计基础*]
        C5_Heat[工程材料及热处理]
        C5_Ctrl[材料成型智能控制基础*]
        C5_Exp[工程材料基础实验]
        C5_Prac[认识实习]
    end

    subgraph S6 [第6学期]
        C6_Meth[焊接方法及工艺★]
        C6_Struct[焊接结构★]
        C6_Metal[焊接冶金与金属焊接性]
        C6_Test[焊接质量检验与评价*]
        C6_Exp2[焊接原理及工艺实验]
        C6_CD[焊接结构课程设计]
    end

    %% 第四学年：工程出口 (您图中完全缺失的部分)
    subgraph S7 [第7学期]
        C7_Add[增材制造技术]
        C7_Rob[工业机器人]
        C7_New[绿色智能焊接新技术]
        C7_CD[焊接工艺课程设计]
        C7_Exp3[绿色智能交叉焊接综合实验]
        C7_Prac2[生产实习]
    end

    subgraph S8 [第8学期]
        C8_GD[毕业设计★]
    end

    %% 定义核心依赖链条
    C1_Math --> C2_Math --> C3_Lin --> C4_Prob
    C1_Draw --> C2_Draw2 --> C3_Draw3
    C2_Phys --> C3_Phys --> C4_Elec
    C2_Chem --> C3_PChem --> C4_MS --> C5_Heat
    C4_MS --> C6_Metal
    C3_Mech --> C5_MDes --> C6_Struct
    C5_Proc --> C6_Meth
    C6_Meth & C6_Struct --> C7_CD
    C5_Ctrl --> C7_Rob
    
    %% 指向最终毕业出口
    C6_CD & C7_CD & C7_Prac2 --> C8_GD
    C6_Exp2 & C7_Exp3 --> C8_GD

    %% 样式美化
    style C8_GD fill:#f96,stroke:#333,stroke-width:4px
    style C4_MS fill:#bbf,stroke:#333
    style S7 fill:#fff2cc,stroke:#d6b656
    style S8 fill:#d5e8d4,stroke:#82b366
"""

def render_mermaid(code):
    components.html(
        f"""
        <div class="mermaid" style="background-color: white;">
            {code}
        </div>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ 
                startOnLoad: true,
                theme: 'default',
                flowchart: {{ useMaxWidth: false, htmlLabels: true }}
            }});
        </script>
        """,
        height=1200, # 调高高度以容纳 4 学年内容
        scrolling=True
    )

render_mermaid(full_mermaid_code)