import streamlit as st
import os, fitz, requests, re, numpy as np, easyocr

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Máy Ép Kiến Thức V6.0", page_icon="🧠", layout="wide")

st.title("🧠 Máy Ép Kiến Thức V6.0")
st.info("Kéo thả file PDF bài giảng vào đây để bắt đầu 'nhấu nghiến' kiến thức.")

# --- SIDEBAR: BẢO MẬT ---
with st.sidebar:
    st.header("⚙️ Cấu hình máy ép")
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
        st.success("✅ Đã kết nối API bảo mật")
    else:
        api_key = st.text_input("DeepSeek API Key", type="password")

    subject_type = st.selectbox("Chọn chuyên ngành", ["Vạn năng", "Toán học", "Kỹ thuật", "Văn học"])
    max_t = st.slider("Độ chi tiết (Tokens)", 1000, 4000, 3000)
    temp = st.slider("Độ sáng tạo", 0.0, 1.0, 0.2)

# --- LOGIC XỬ LÝ AI ---
def summarize_page(text, page_num, api_key, subject, max_tokens, temperature):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": f"Bạn là chuyên gia phân tích bài giảng môn {subject}. Hãy trích xuất toàn bộ kiến thức quan trọng nhất."},
            {"role": "user", "content": f"NỘI DUNG SLIDE {page_num}:\n{text}"}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=120)
        return res.json()['choices'][0]['message']['content']
    except:
        return "⚠️ Lỗi kết nối với trí tuệ nhân tạo."

# --- GIAO DIỆN CHÍNH ---
uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"])

if uploaded_file is not None:
    if st.button("🚀 BẮT ĐẦU ÉP"):
        if not api_key:
            st.error("Bạn chưa nhập API Key!")
        else:
            # Lưu tạm file để xử lý
            with open("temp_upload.pdf", "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            doc = fitz.open("temp_upload.pdf")
            total = len(doc)
            
            # Sử dụng st.status để tạo hiệu ứng chuyên nghiệp trên web
            with st.status("🏗️ Máy ép đang hoạt động...", expanded=True) as status:
                st.write("🔍 Đang khởi động bộ giải mã hình ảnh (OCR)...")
                reader = easyocr.Reader(['vi', 'en'], gpu=False)
                
                final_summary = ""
                for i in range(total):
                    st.write(f"正在 nhấu nghiến Slide {i+1}/{total}...")
                    page = doc.load_page(i)
                    text = page.get_text().strip()
                    
                    # Nếu slide là ảnh (ít chữ) thì dùng OCR
                    if len(text) < 40:
                        pix = page.get_pixmap(dpi=120)
                        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                        text = " ".join(reader.readtext(img, detail=0))
                    
                    summary = summarize_page(text, i+1, api_key, subject_type, max_t, temp)
                    final_summary += f"## 📚 PHÂN TÍCH SLIDE {i+1}\n\n{summary}\n\n---\n\n"
                
                status.update(label="✅ Đã ép xong!", state="complete", expanded=False)
            
            # Hiển thị kết quả và nút tải về
            st.markdown(final_summary)
            st.download_button("📥 Tải bộ phao (.md)", final_summary, file_name="phao_hoc_tap.md")
