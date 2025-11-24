import streamlit as st
import pandas as pd
import os
from PIL import Image

# 设置网页标题和布局
st.set_page_config(page_title="我的商品展示工具", layout="wide")

# 1. 读取数据
@st.cache_data
def load_data():
    # 尝试读取 csv，如果找不到文件则提示
    if not os.path.exists('product_database_master.csv'):
        return None
    df = pd.read_csv('product_database_master.csv')
    return df

df = load_data()

# 侧边栏
st.sidebar.title("导航栏")
page = st.sidebar.radio("去往", ["商品主页", "商品详情页"])

if df is None:
    st.error("错误：找不到 product_database_master.csv 文件，请检查上传是否完整。")
else:
    # --- 页面 1：商品主页 (画廊模式) ---
    if page == "商品主页":
        st.title("🛒 商品展示主页")
        
        # 搜索框
        search_term = st.text_input("搜索商品名称...", "")
        
        # 筛选数据
        if search_term:
            filtered_df = df[df['name'].str.contains(search_term, case=False, na=False)]
        else:
            filtered_df = df

        # 展示图片网格 (每行 3 个)
        cols = st.columns(3)
        for index, row in filtered_df.iterrows():
            col = cols[index % 3] # 决定放在第几列
            
            with col:
                # 构建图片路径
                img_path = row['image_path']
                # 简单处理路径分隔符问题，确保云端能读
                img_path = img_path.replace("\\", "/") 
                
                if os.path.exists(img_path):
                    image = Image.open(img_path)
                    st.image(image, use_container_width=True)
                else:
                    st.text("暂无图片")
                
                st.subheader(row['name'])
                st.write(f"价格: ¥{row['price']}")
                st.info(f"ID: {row['id']}")
                st.markdown("---")

    # --- 页面 2：商品详情页 ---
    elif page == "商品详情页":
        st.title("📄 商品详细信息")
        
        # 下拉选择商品
        product_names = df['name'].tolist()
        selected_product_name = st.selectbox("请选择一个商品查看详情：", product_names)
        
        # 获取该商品数据
        product_data = df[df['name'] == selected_product_name].iloc[0]
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # 显示大图
            img_path = product_data['image_path'].replace("\\", "/")
            if os.path.exists(img_path):
                image = Image.open(img_path)
                st.image(image, caption=product_data['name'], use_container_width=True)
            else:
                st.warning("图片文件丢失")
                
        with col2:
            st.header(product_data['name'])
            st.write(f"**商品 ID:** {product_data['id']}")
            st.success(f"**价格:** ¥{product_data['price']}")
            
            st.markdown("### 📝 商品描述")
            # 假设 CSV 里有 description 列，如果没有就显示默认文案
            if 'description' in product_data:
                st.write(product_data['description'])
            else:
                st.write("暂无详细描述信息...")
            
            st.markdown("### ⚙️ 规格参数")
            st.json({
                "库存": "充足",
                "分类": "家居/饰品",
                "上架时间": "2023-11-24"
            })

