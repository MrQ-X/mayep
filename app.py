import streamlit as st
import os, fitz, requests, json, numpy as np, easyocr
from language import LANGUAGES
from calculator import SYSTEM_CORE, SUBJECT_PROMPTS

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Máy Ép Kiến Thức V6.0", page_icon="🧠", layout="wide")

# --- 2. SIDEBAR & ĐA NGÔN NGỮ ---
with st.sidebar:
    lang_choice = st.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"])
    L = LANGUAGES[lang_choice] # Sau dòng này L đã có dữ liệu

    # Bây giờ gọi dòng này mới không bị lỗi
    translated_subjects = L["subject_list"] 
    
selected_subject_key = st.selectbox(
        L["subject_label"], 
        options=list(translated_subjects.keys()), 
        format_func=lambda x: translated_subjects[x], 
        key="unique_subject_selector_v6"  # Đổi từ subject_sel sang cái này
    )

    # Widget cấu hình sử dụng Key để tránh lỗi Duplicate
    max_t = st.slider(L["detail_label"], 1000, 4000, 3000, key="max_t_slider")
    temp = st.slider(L["creative_label"], 0.0, 1.0, 0.2, key="temp_slider")
    
# 1. Lấy danh sách tên chuyên ngành đã được dịch
translated_subjects = L["subject_list"] 
    
    # 2. Hiển thị tên đã dịch nhưng lưu giá trị chọn là tên gốc (Key)
selected_subject_label = st.selectbox(
        L["subject_label"], 
        options=list(translated_subjects.keys()), # Đây là tên gốc (dùng để xử lý logic)
        format_func=lambda x: translated_subjects[x], # Đây là tên hiển thị (đã dịch)
        key="subject_sel"
    )

# --- 3. TIÊU ĐỀ CHÍNH ---
st.title(L["title"])
st.subheader(f"📍 {selected_subject}")

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

# --- 5. XỬ LÝ FILE PDF & OCR ---
uploaded_file = st.file_uploader(L["upload_label"], type=["pdf"])

if uploaded_file is not None:
    if st.button(L["btn_start"]):
        if not api_key:
            st.error(L["error_api"])
            st.stop()

        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        doc = fitz.open("temp.pdf")
        total = len(doc)
        
        # Reader OCR (Tải model nếu chưa có)
        reader = easyocr.Reader(['vi', 'en'], gpu=False)
        
        progress_bar = st.progress(0)
        final_summary = ""
        
        # Hiển thị trạng thái xử lý
        with st.status(f"{L['status_processing']}...", expanded=True) as status:
            for i in range(total):
                page = doc.load_page(i)
                text = page.get_text().strip()
                
                # Nếu text quá ít -> Dùng OCR xử lý ảnh
                if len(text) < 40:
                    pix = page.get_pixmap(dpi=120)
                    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                    text = " ".join(reader.readtext(img, detail=0))
                
                summary, tokens = summarize_page(text, i+1, api_key, selected_subject, max_t, temp, lang_choice)
                final_summary += f"## 📚 SLIDE {i+1}\n\n{summary}\n\n---\n\n"
                
                progress_bar.progress((i + 1) / total)
                st.write(f"✅ Done Page {i+1}")
            
            status.update(label=L["success_msg"], state="complete")

        # Hiển thị kết quả & Nút tải về
        st.markdown(final_summary)
        st.download_button(L["btn_download"], final_summary, file_name=f"crushed_{selected_subject}.md")
