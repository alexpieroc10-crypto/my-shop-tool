import streamlit as st
import pandas as pd
import os
from PIL import Image

# 1. 网页基础设置
st.set_page_config(page_title="我的选品库", layout="wide")
st.title("🛍️ 选品展示系统")

# 2. 读取数据函数
@st.cache_data
def load_data():
    if not os.path.exists('product_database_master.csv'):
        return None
    df = pd.read_csv('product_database_master.csv')
    return df

df = load_data()

if df is None:
    st.error("找不到数据文件，请检查 product_database_master.csv 是否上传。")
else:
    # --- 核心配置 (根据你的截图填写的) ---
    img_col = '图片路径'  # 你的图片列名
    name_col = '商品'     # 你的商品名列名
    price_col = '真实售价' # 你的价格列名
    
    # 搜索框
    search_term = st.text_input("🔍 搜索商品...", "")
    
    # 过滤数据
    if search_term:
        filtered_df = df[df[name_col].astype(str).str.contains(search_term, case=False, na=False)]
    else:
        filtered_df = df

    # --- 展示画廊 ---
    st.write(f"共找到 {len(filtered_df)} 款商品")
    
    # 设置每行显示 3 列
    cols = st.columns(3)
    
    for index, row in filtered_df.iterrows():
        col = cols[index % 3] # 循环放入 3 列中
        
        with col:
            # --- 🛠️ 路径超级修复大法 ---
            raw_path = str(row[img_col])
            
            # 1. 把反斜杠 \ 变成正斜杠 /
            clean_path = raw_path.replace("\\", "/")
            
            # 2. 如果路径里包含 'db_images'，只保留 'db_images' 后面的部分
            # 这样可以去掉 'E:/.../...' 这种本地绝对路径
            if "db_images" in clean_path:
                parts = clean_path.split("db_images")
                # 重新组合，确保是 db_images/xxx.png
                final_path = "db_images" + parts[-1]
            else:
                final_path = clean_path
                
            # --- 显示图片 ---
            if os.path.exists(final_path):
                try:
                    image = Image.open(final_path)
                    st.image(image, use_container_width=True)
                except:
                    st.caption("🖼️ 图片无法打开")
            else:
                # 如果找不到，显示一个灰色的框和路径名字，方便排查
                st.warning("⚠️ 路径不对")
                st.caption(f"系统在找: {final_path}")
            
            # --- 显示文字信息 ---
            st.subheader(str(row[name_col]))
            
            # 显示价格和利润
            if price_col in row:
                st.info(f"💰 售价: {row[price_col]}")
            
            # 显示其他信息 (如果有)
            if '文案' in row and pd.notna(row['文案']):
                with st.expander("查看文案"):
                    st.write(row['文案'])
                    
            st.markdown("---")


