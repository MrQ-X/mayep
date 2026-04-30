import streamlit as st
import pandas as pd
import os, fitz, requests, json, numpy as np, easyocr
from language import LANGUAGES
from calculator import SYSTEM_CORE, SUBJECT_PROMPTS


# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Máy Ép Kiến Thức V1.36", page_icon="🧠", layout="wide")

df_info = pd.DataFrame(L["product_info"], columns=[L["table_feature"], L["table_detail"]])
st.table(df_info)

# Hiển thị hướng dẫn sử dụng nhanh
with st.expander(L["guide_title"], expanded=True):
    st.info(f"{L['guide_step1']}\n\n{L['guide_step2']}\n\n{L['guide_finish']}")

st.divider()

# --- 2. SIDEBAR & ĐA NGÔN NGỮ ---
with st.sidebar:
    # 1. Chọn ngôn ngữ
    lang_choice = st.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"], key="lang_picker")
    L = LANGUAGES[lang_choice]
    
    st.header(L["header_config"])
    
    # 2. Nhập API Key
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
        st.success("✅ Connected via Secrets")
    else:
        api_key = st.text_input(L["api_label"], type="password", key="api_input_key")

    # 3. Chọn chuyên ngành (Đã dịch)
    translated_subjects = L["subject_list"]
    selected_subject_key = st.selectbox(
        L["subject_label"], 
        options=list(translated_subjects.keys()), 
        format_func=lambda x: translated_subjects[x], 
        key="subject_selector_unique"
    )
    
    # 4. Các Slider (Đảm bảo các dòng này thẳng hàng với dòng translated_subjects ở trên)
    max_t = st.slider(L["detail_label"], 1000, 4000, 3000, key="max_t_slider")
    temp = st.slider(L["creative_label"], 0.0, 1.0, 0.2, key="temp_slider")
    

# --- 3. TIÊU ĐỀ CHÍNH ---
st.title(L["title"])
with st.expander(L["guide_title"], expanded=True):
    st.write(L["guide_step1"])
    st.write(L["guide_step2"])
    st.write(L["guide_finish"])

st.divider()

# --- 4. LOGIC GỌI AI ---
def summarize_page(text, page_num, api_key, subject_key, max_tokens, temperature, lang):
    url = "https://api.deepseek.com/chat/completions"
    
    if not api_key:
        return "❌ API Key Missing!", 0
    if not text or len(str(text).strip()) < 5:
        return "⚠️ Empty Slide Content", 0

    specific_instruction = SUBJECT_PROMPTS.get(subject_key, list(SUBJECT_PROMPTS.values())[0])
    
    # Ép AI trả về đúng ngôn ngữ giao diện đang chọn
    full_system_prompt = f"{SYSTEM_CORE}\n\n{specific_instruction}\n\nIMPORTANT: Respond in {lang} language."
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": f"DATA SLIDE {page_num}:\n{text}"}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    headers = {
        "Authorization": f"Bearer {api_key.strip()}", 
        "Content-Type": "application/json; charset=utf-8"
    }
    
    try:
        binary_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        res = requests.post(url, data=binary_data, headers=headers, timeout=60)
        
        if res.status_code == 200:
            res_json = res.json()
            return res_json['choices'][0]['message']['content'], res_json.get('usage', {}).get('total_tokens', 0)
        else:
            return f"❌ Error {res.status_code}: {res.text[:100]}", 0
    except Exception as e:
        return f"☣️ System Error: {str(e)}", 0

# --- XỬ LÝ FILE (V7.0: PDF + IMAGE) ---
uploaded_file = st.file_uploader(L["upload_label"], type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file is not None:
    file_type = uploaded_file.type
    
    if st.button(L["btn_start"]):
        if not api_key:
            st.error(L["error_api"])
            st.stop()

        final_summary = ""
        # Khởi tạo OCR Reader một lần duy nhất để tiết kiệm RAM
        reader = easyocr.Reader(['vi', 'en'], gpu=False)

        # TRƯỜNG HỢP 1: FILE LÀ ẢNH
        if file_type in ["image/png", "image/jpeg", "image/jpg"]:
            with st.status("📷 Đang xử lý ảnh...", expanded=True) as status:
                # Chuyển file upload thành mảng numpy để EasyOCR đọc
                file_bytes = np.frombuffer(uploaded_file.read(), np.uint8)
                import cv2
                img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                
                text = " ".join(reader.readtext(img, detail=0))
                summary, tokens = summarize_page(text, "IMAGE", api_key, selected_subject_key, max_t, temp, lang_choice)
                
                final_summary = f"## 🖼️ KẾT QUẢ ÉP ẢNH\n\n{summary}"
                status.update(label="✅ Đã ép xong ảnh!", state="complete")

        # TRƯỜNG HỢP 2: FILE LÀ PDF
        else:
            with open("temp.pdf", "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            doc = fitz.open("temp.pdf")
            total = len(doc)
            progress_bar = st.progress(0)

            with st.status(f"{L['status_processing']}...", expanded=True) as status:
                for i in range(total):
                    page = doc.load_page(i)
                    text = page.get_text().strip()
                    
                    if len(text) < 40: # Nếu trang PDF là ảnh hoặc ít chữ
                        pix = page.get_pixmap(dpi=120)
                        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                        text = " ".join(reader.readtext(img, detail=0))
                    
                    summary, tokens = summarize_page(text, i+1, api_key, selected_subject_key, max_t, temp, lang_choice)
                    final_summary += f"## 📚 SLIDE {i+1}\n\n{summary}\n\n---\n\n"
                    progress_bar.progress((i + 1) / total)
                
                status.update(label=L["success_msg"], state="complete")

        # Hiển thị kết quả cuối cùng
        st.markdown(final_summary)
        st.download_button(L["btn_download"], final_summary, file_name=f"crushed_content.md")
