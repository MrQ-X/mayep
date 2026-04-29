import streamlit as st
import os, fitz, requests, json, numpy as np, easyocr
from calculator import SYSTEM_CORE, SUBJECT_PROMPTS

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Máy Ép Kiến Thức V6.0", page_icon="🧠", layout="wide")

# --- DANH SÁCH CHUYÊN NGÀNH & PROMPT CHUYÊN SÂU ---
SUBJECTS = {
    "Vạn năng (Tổng hợp)": "Bạn là chuyên gia phân tích nội dung. Hãy trích xuất mọi thông tin quan trọng nhất, trình bày khoa học bằng Markdown.",
    
    "Kỹ thuật & Công nghệ": "Bạn là kỹ sư cấp cao. Tập trung tối đa vào: THÔNG SỐ KỸ THUẬT, QUY TRÌNH VẬN HÀNH, SƠ ĐỒ HỆ THỐNG và các CÔNG THỨC [ngoặc vuông]. Giải thích rõ đơn vị đo lường.",
    
    "Y khoa & Dược phẩm": "Bạn là bác sĩ chuyên khoa. Chú trọng: TRIỆU CHỨNG, CƠ CHẾ BỆNH SINH, CHỈ ĐỊNH/CHỐNG CHỈ ĐỊNH, LIỀU LƯỢNG và TÊN THUỐC. Đảm bảo độ chính xác thuật ngữ y khoa 100%.",
    
    "Luật & Chính trị": "Bạn là luật sư dày dạn kinh nghiệm. Tập trung vào: CĂN CỨ PHÁP LÝ, ĐIỀU KHOẢN, NGHĨA VỤ, TRÁCH NHIỆM PHÁP LÝ và các MỐC THỜI GIAN. Trình bày dưới dạng luận điểm chặt chẽ.",
    
    "Kinh tế & Tài chính": "Bạn là chuyên gia tài chính. Phân tích sâu: CHỈ SỐ KINH TẾ, BIỂU ĐỒ, CÔNG THỨC TÍNH TOÁN, CHI PHÍ/LỢI NHUẬN và CHIẾN LƯỢC KINH DOANH. Làm nổi bật các con số.",
    
    "Ngôn ngữ & Văn học": "Bạn là tiến sĩ ngôn ngữ. Phân tích: NGỮ CẢNH, BIỆN PHÁP NGHỆ THUẬT, Ý NGHĨA BIỂU TƯỢNG, CẤU TRÚC NGỮ PHÁP và TÁC GIẢ/TÁC PHẨM. Viết văn phong trau chuốt."
}

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
    selected_subject = st.selectbox("🎯 Chuyên ngành tài liệu", list(SUBJECTS.keys()))
    
    max_t = st.slider("Độ chi tiết", 1000, 4000, 3000)
    temp = st.slider("Độ sáng tạo", 0.0, 1.0, 0.2)

# --- LOGIC GỌI AI ---
def summarize_page(text, page_num, api_key, subject_key, max_tokens, temperature):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json; charset=utf-8"}
    
    # Lấy Prompt cụ thể cho chuyên ngành đã chọn
    specific_prompt = SUBJECTS[subject_key]
    
    system_instruction = f"""
    {specific_prompt}
    QUY TẮC BẮT BUỘC:
    1. Liệt kê đầy đủ định nghĩa và thuật ngữ chuyên môn.
    2. Nếu có ví dụ, hãy phân tích từng bước một cách tường minh.
    3. Trình bày bằng Markdown sạch sẽ, sử dụng Bullet points và Bolding để dễ đọc.
    4. Ngôn ngữ: Tiếng Việt.
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"NỘI DUNG SLIDE {page_num}:\n{text}"}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    try:
        binary_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        res = requests.post(url, data=binary_data, headers=headers, timeout=120)
        return res.json()['choices'][0]['message']['content']
    except:
        return "⚠️ Lỗi kết nối AI hoặc hết Token."

# --- XỬ LÝ FILE ---
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
