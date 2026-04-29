import streamlit as st
import os, fitz, requests, json, numpy as np, easyocr

st.set_page_config(page_title="Máy Ép Kiến Thức V6.0", page_icon="🧠", layout="wide")

LANG_DICT = {
    "Tiếng Việt": {
        "title": "🧠 Máy Ép Kiến Thức V6.0",
        "subheader": "Biến Slide thành bộ phao học thuật cực chất",
        "config": "⚙️ Cấu hình máy ép",
        "lang_select": "Chọn ngôn ngữ đầu ra",
        "subject": "Chọn chuyên ngành",
        "btn_start": "🚀 BẮT ĐẦU ÉP",
        "free_msg": "🎁 Chế độ dùng thử: Ép 10 trang đầu.",
        "success": "✅ Đã ép xong!",
        "system_msg": "Bạn là chuyên gia phân tích bài giảng. Hãy trích xuất kiến thức bằng Tiếng Việt."
    },
    "English": {
        "title": "🧠 Knowledge Compressor V6.0",
        "subheader": "Turn Slides into high-quality academic cheat sheets",
        "config": "⚙️ Configuration",
        "lang_select": "Select output language",
        "subject": "Select Subject",
        "btn_start": "🚀 START COMPRESSING",
        "free_msg": "🎁 Trial Mode: First 10 pages only.",
        "success": "✅ Finished!",
        "system_msg": "You are an academic expert. Extract key knowledge and explain in English."
    }
}

# --- SIDEBAR---
with st.sidebar:
    st.header("⚙️ Settings")
    
    # CHỌN NGÔN NGỮ (SWAP)
    lang_choice = st.selectbox("🌐 Language / Ngôn ngữ", ["Tiếng Việt", "English"])
    L = LANG_DICT[lang_choice] # Lấy bộ từ điển tương ứng
    
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
        st.success("✅ API Connected")
    else:
        api_key = st.text_input("DeepSeek API Key", type="password")

    subject_type = st.selectbox(L["subject"], ["General", "Math/Engineering", "Law/Medical", "Literature"])
    max_t = st.slider("Max Tokens", 1000, 4000, 3000)
    temp = st.slider("Temperature", 0.0, 1.0, 0.2)

# --- MENU ---
st.title(L["title"])
st.subheader(L["subheader"])

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

# --- AI ---
def summarize_page(text, page_num, api_key, subject, max_tokens, temperature, system_prompt_lang):
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}".strip(),
        "Content-Type": "application/json; charset=utf-8"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": f"{system_prompt_lang}. Subject: {subject}."},
            {"role": "user", "content": f"CONTENT OF SLIDE {page_num}:\n{text}"}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    try:
        binary_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        res = requests.post(url, data=binary_data, headers=headers, timeout=120)
        if res.status_code == 200:
            return res.json()['choices'][0]['message']['content']
        return f"Error {res.status_code}"
    except Exception as e:
        return str(e)

# --- PROCESSING ---
if uploaded_file is not None:
    if st.button(L["btn_start"]):
        if not api_key:
            st.error("Missing API Key!")
        else:
            with open("temp_upload.pdf", "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            doc = fitz.open("temp_upload.pdf")
            total = len(doc)
            
            # Giới hạn 10 trang cho khách vãng lai (không có Key riêng)
            is_pro = True if "DEEPSEEK_API_KEY" in st.secrets or len(api_key) > 30 else False
            limit = total if is_pro else min(total, 10)
            
            if not is_pro: st.warning(L["free_msg"])

            with st.status("🏗️ Processing...", expanded=True) as status:
                reader = easyocr.Reader(['vi', 'en'], gpu=False)
                final_summary = ""
                
                for i in range(limit):
                    st.write(f"⏳ Page {i+1}/{limit}...")
                    page = doc.load_page(i)
                    text = page.get_text().strip()
                    
                    if len(text) < 40:
                        pix = page.get_pixmap(dpi=120)
                        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                        text = " ".join(reader.readtext(img, detail=0))
                    
                    # Truyền system prompt theo ngôn ngữ đã chọn
                    summary = summarize_page(text, i+1, api_key, subject_type, max_t, temp, L["system_msg"])
                    final_summary += f"## PAGE {i+1}\n\n{summary}\n\n---\n\n"
                
                status.update(label=L["success"], state="complete", expanded=False)
            
            st.markdown(final_summary)
            st.download_button("📥 Download (.md)", final_summary, file_name="cheat_sheet.md")
