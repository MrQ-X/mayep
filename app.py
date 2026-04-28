import streamlit as st
import os, fitz, requests, re, numpy as np, easyocr
from tqdm import tqdm

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Máy Ép Kiến Thức V6.0", page_icon="🧠", layout="wide")

st.title("🧠 Máy Ép Kiến Thức V6.0")
st.subheader("Biến Slide bài giảng thành bộ phao học thuật 'nhấu nghiến' nhất")

# --- SIDEBAR: CẤU HÌNH BẢO MẬT ---
with st.sidebar:
    st.header("⚙️ Cấu hình máy ép")
    
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
        st.success("✅ Đã kết nối API bảo mật")
    else:
        api_key = st.text_input("Nhập DeepSeek API Key", type="password", help="Dán Key của bạn vào đây để sử dụng")

    subject_type = st.selectbox("Chọn chuyên ngành", ["Vạn năng (Tự động)", "Toán học/Kỹ thuật", "Văn học/Nghệ thuật", "Luật pháp/Y tế"])
    max_t = st.slider("Độ chi tiết (Max Tokens)", 1000, 4000, 3000)
    temp = st.slider("Độ sáng tạo (Temperature)", 0.0, 1.0, 0.2)

# --- LOGIC XỬ LÝ ---
def summarize_page(text, page_num, api_key, subject, max_tokens, temperature):
    if not api_key:
        return "⚠️ Lỗi: Chưa có API Key. Vui lòng kiểm tra lại cấu hình."
        
    url = "https://api.deepseek.com/chat/completions"
    
    system_prompt = f"""
    Bạn là một Siêu AI Phân Tích Đa Nhiệm. Nhiệm vụ: "NHẤU NGHIẾN" Slide này.
    Chuyên ngành ưu tiên: {subject}.
    
    QUY TẮC:
    1. KHÔNG ĐƯỢC TÓM TẮT: Liệt kê TẤT CẢ định nghĩa, công thức [ngoặc vuông].
    2. VÍ DỤ: Lấy toàn bộ ví dụ gốc và GIẢI CHI TIẾT từng bước.
    3. HÌNH HỌC: Mô tả đặc điểm hình dạng, tính chất.
    4. KHÔNG LAN MAN: Chỉ tập trung vào Slide hiện tại.
    Viết cực dài, sâu sắc bằng Markdown.
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"NỘI DUNG SLIDE {page_num}:\n{text}"}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=120)
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Lỗi ở Slide {page_num}: {str(e)}"

# --- GIAO DIỆN CHÍNH ---
uploaded_file = st.file_uploader("Kéo thả file PDF vào đây", type=["pdf"])

if uploaded_file is not None:
    if st.button("🚀 BẮT ĐẦU ÉP KIẾN THỨC"):
        if not api_key:
            st.error("Vui lòng cung cấp API Key ở Sidebar trước khi bắt đầu!")
            st.stop()

        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        doc = fitz.open("temp.pdf")
        total_pages = len(doc)
        
        final_summary = ""
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Reader cho OCR (Giữ nguyên logic của bạn)
        reader = easyocr.Reader(['vi', 'en'], gpu=False)
        
        for i in range(total_pages):
            status_text.text(f"⚡ Đang ép Slide {i+1}/{total_pages}...")
            
            page = doc.load_page(i)
            text = page.get_text().strip()
            
            if len(text) < 40:
                pix = page.get_pixmap(dpi=120)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                text = " ".join(reader.readtext(img, detail=0))
            
            page_summary = summarize_page(text, i+1, api_key, subject_type, max_t, temp)
            
            header = f"## 📚 PHÂN TÍCH CHI TIẾT SLIDE {i+1}\n\n"
            final_summary += header + page_summary + "\n\n---\n\n"
            
            progress_bar.progress((i + 1) / total_pages)
            
        st.success("🎉 Đã ép xong toàn bộ tài liệu!")
        st.markdown(final_summary)
        
        st.download_button(
            label="📥 Tải bộ phao (.md)",
            data=final_summary,
            file_name=f"phao_{uploaded_file.name.split('.')[0]}.md",
            mime="text/markdown"
        )