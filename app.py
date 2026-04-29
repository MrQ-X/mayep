import streamlit as st
import os, fitz, requests, json, numpy as np, easyocr
from language import LANGUAGES
from calculator import SYSTEM_CORE, SUBJECT_PROMPTS

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Máy Ép Kiến Thức V6.0", page_icon="🧠", layout="wide")

with st.sidebar:
    lang_choice = st.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"])
    L = LANGUAGES[lang_choice] # Gán bộ từ điển tương ứng vào biến L

# 2. Sử dụng biến L để thay thế các dòng chữ cứng
st.title(L["title"])

with st.sidebar:
    st.header(L["header_config"])
    api_key = st.text_input(L["api_label"], type="password")
    # Tương tự cho các phần khác...
    max_t = st.slider(L["detail_label"], 1000, 4000, 3000)

# --- DANH SÁCH CHUYÊN NGÀNH & PROMPT CHUYÊN SÂU ---

st.title("🧠 Máy Ép Kiến Thức V6.0")
st.subheader("Bản cập nhật chuyên ngành: Ép sâu hơn, nhớ lâu hơn")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Cấu hình máy ép")
    
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
        st.success("✅ Đã kết nối API bảo mật")
    else:
        api_key = st.text_input("DeepSeek API Key", type="password")

    # Chọn chuyên ngành để lấy Prompt tương ứng
    selected_subject = st.selectbox("🎯 Chuyên ngành tài liệu", list(SUBJECT_PROMPTS.keys()))
    
    max_t = st.slider("Độ chi tiết", 1000, 4000, 3000)
    temp = st.slider("Độ sáng tạo", 0.0, 1.0, 0.2)

# --- LOGIC GỌI AI ---
def summarize_page(text, page_num, api_key, subject_key, max_tokens, temperature):
    url = "https://api.deepseek.com/chat/completions"
    
    # --- 1. KIỂM TRA ĐẦU VÀO ---
    if not api_key:
        return "❌ LỖI: Thiếu API Key. Hãy nhập Key ở Sidebar!", 0
    if not text or len(str(text).strip()) < 5:
        return "⚠️ CẢNH BÁO: Slide này không có chữ hoặc nội dung quá ngắn để phân tích.", 0

    # --- 2. KẾT HỢP PROMPT TỪ CALCULATOR.PY ---
    # Lấy prompt ngành, nếu không thấy thì dùng Vạn năng
    specific_instruction = SUBJECT_PROMPTS.get(subject_key, list(SUBJECT_PROMPTS.values())[0])
    full_system_prompt = f"{SYSTEM_CORE}\n\n{specific_instruction}"
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": f"DỮ LIỆU SLIDE {page_num}:\n{text}"}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    headers = {
        "Authorization": f"Bearer {api_key.strip()}", 
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # --- 3. GỬI REQUEST VÀ XỬ LÝ LỖI TẬN RĂNG ---
    try:
        # Encode UTF-8 để tránh lỗi font khi gửi
        binary_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        res = requests.post(url, data=binary_data, headers=headers, timeout=60)
        
        # Kiểm tra mã trạng thái HTTP
        if res.status_code == 200:
            res_json = res.json()
            content = res_json['choices'][0]['message']['content']
            tokens = res_json.get('usage', {}).get('total_tokens', 0)
            return content, tokens
            
        elif res.status_code == 401:
            return "❌ LỖI 401: API Key không hợp lệ. Hãy kiểm tra lại Key DeepSeek của bạn.", 0
        elif res.status_code == 402:
            return "❌ LỖI 402: Tài khoản DeepSeek hết tiền (Insufficient Balance).", 0
        elif res.status_code == 429:
            return "⏳ LỖI 429: Rate Limit - Bạn đang gửi yêu cầu quá nhanh.", 0
        elif res.status_code == 500:
            return "🏗️ LỖI 500: Server DeepSeek đang quá tải hoặc bảo trì.", 0
        else:
            return f"❓ LỖI LẠ ({res.status_code}): {res.text[:100]}...", 0

    # --- 4. XỬ LÝ LỖI KỸ THUẬT NGOẠI VI ---
    except requests.exceptions.Timeout:
        return "🐌 LỖI: Timeout - DeepSeek phản hồi quá lâu (hơn 60s).", 0
    except requests.exceptions.ConnectionError:
        return "🌐 LỖI: Mạng không ổn định hoặc không thể kết nối tới server DeepSeek.", 0
    except Exception as e:
        return f"☣️ LỖI HỆ THỐNG: {str(e)}", 0

# --- XỬ LÝ FILE ---
uploaded_file = st.file_uploader(L["upload_label"], type=["pdf"])

if st.button(L["btn_start"]):
    if not api_key:
        st.error(L["error_api"])
    # ... logic xử lý ...
    status_text.text(f"{L['status_processing']} {i+1}/{total_pages}...")
    
uploaded_file = st.file_uploader("Kéo thả PDF bài giảng", type=["pdf"])

if uploaded_file is not None:
    if st.button("🚀 BẮT ĐẦU ÉP KIẾN THỨC"):
        if not api_key:
            st.error("Vui lòng nhập API Key!")
            st.stop()

        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        doc = fitz.open("temp.pdf")
        total = len(doc)
        
        # Reader OCR
        reader = easyocr.Reader(['vi', 'en'], gpu=False)
        
        progress_bar = st.progress(0)
        final_summary = ""
        
        with st.status(f" sedang ép tài liệu chuyên ngành {selected_subject}...", expanded=True) as status:
            for i in range(total):
                page = doc.load_page(i)
                text = page.get_text().strip()
                
                if len(text) < 40: # Xử lý Slide dạng ảnh
                    pix = page.get_pixmap(dpi=120)
                    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                    text = " ".join(reader.readtext(img, detail=0))
                
                summary = summarize_page(text, i+1, api_key, selected_subject, max_t, temp)
                final_summary += f"## 📚 SLIDE {i+1}\n\n{summary}\n\n---\n\n"
                progress_bar.progress((i + 1) / total)
            
            status.update(label="✅ Đã ép xong!", state="complete")

        st.markdown(final_summary)
        st.download_button("📥 Tải bản đầy đủ (.md)", final_summary, file_name="phao_chuyen_nganh.md")
