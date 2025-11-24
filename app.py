import streamlit as st
import pandas as pd
import os
from PIL import Image

# 设置网页配置
st.set_page_config(page_title="我的商品展示工具", layout="wide")

st.title("🛒 商品展示系统 (自动修复版)")

# 1. 读取数据
@st.cache_data
def load_data():
    if not os.path.exists('product_database_master.csv'):
        return None
    # 读取 CSV，所有列名转为小写以避免大小写不一致的问题
    df = pd.read_csv('product_database_master.csv')
    return df

df = load_data()

if df is None:
    st.error("❌ 错误：找不到 product_database_master.csv 文件。")
else:
    # --- 🔍 自动侦测列名 ---
    # 打印出当前的列名，方便调试
    st.info(f"📊 表格中的列名检测结果: {df.columns.tolist()}")
    
    # 尝试寻找包含 'image', 'path', 'img', 'pic' 字眼的列
    image_col = None
    possible_names = ['image_path', 'image', 'path', 'img_path', 'pic', '图片', '照片']
    
    # 1. 先精确匹配
    for name in possible_names:
        if name in df.columns:
            image_col = name
            break
            
    # 2. 如果没找到，找包含关键字的
    if image_col is None:
        for col in df.columns:
            if 'image' in col.lower() or 'path' in col.lower():
                image_col = col
                break
    
    # --- 🛠️ 核心逻辑 ---
    if image_col:
        st.success(f"✅ 成功匹配到图片列：'{image_col}'")
        
        # 搜索框
        search_term = st.text_input("🔍 搜索商品名称...", "")
        
        # 确保 name 列存在，如果不存在就用第一列代替
        name_col = 'name' if 'name' in df.columns else df.columns[0]
        
        if search_term:
            filtered_df = df[df[name_col].astype(str).str.contains(search_term, case=False, na=False)]
        else:
            filtered_df = df

        # 展示网格
        cols = st.columns(3)
        for index, row in filtered_df.iterrows():
            col = cols[index % 3]
            with col:
                # 获取路径
                raw_path = str(row[image_col])
                # 修复路径格式 (把 Windows 的 \ 换成 /)
                img_path = raw_path.replace("\\", "/")
                
                # 为了调试，如果图片显示不出来，可以把 img_path 打印出来看看
                # st.caption(img_path) 
                
                if os.path.exists(img_path):
                    try:
                        image = Image.open(img_path)
                        st.image(image, use_container_width=True)
                    except:
                        st.error("图片损坏")
                else:
                    st.warning(f"⚠️ 找不到图")
                
                st.subheader(str(row[name_col]))
                
                # 尝试显示价格
                if 'price' in df.columns:
                    st.write(f"💰 ¥{row['price']}")
                
                st.markdown("---")
                



