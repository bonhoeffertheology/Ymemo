import streamlit as st
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pypdf import PdfReader
import openai

st.set_page_config(page_title="스마트 AI 독서 노트", page_icon="📚", layout="wide")

st.title("📚 스마트 AI 독서 노트 & 발췌 리포트")
st.write("EPUB 또는 PDF 전자책을 업로드하면 4가지 핵심 내용과 정확한 출처를 추출해 드립니다.")

# 사이드바: OpenAI API 키 입력 및 기기 설정
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input("OpenAI API Key를 입력하세요", type="password")
    st.markdown("---")
    st.caption("태블릿, 스마트폰, 노트북 어디서나 웹으로 사용할 수 있습니다.")

# PDF/EPUB 텍스트 및 메타데이터 파싱 함수
def extract_book_data(uploaded_file):
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    chapters_content = []
    
    if file_ext == ".pdf":
        reader = PdfReader(uploaded_file)
        title = reader.metadata.title if (reader.metadata and reader.metadata.title) else uploaded_file.name.replace(".pdf", "")
        author = reader.metadata.author if (reader.metadata and reader.metadata.author) else "저자 미상"
        
        for idx, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if text:
                chapters_content.append({"location": f"p. {idx + 1}", "text": text})
                
    elif file_ext == ".epub":
        title = uploaded_file.name.replace(".epub", "")
        author = "저자 미상"
        
        with zipfile.ZipFile(uploaded_file, 'r') as z:
            container_xml = ET.fromstring(z.read('META-INF/container.xml'))
            rootfile_path = container_xml.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile').attrib['full-path']
            opf_xml = ET.fromstring(z.read(rootfile_path))
            
            t_elem = opf_xml.find('.//{http://purl.org/dc/elements/1.1/}title')
            if t_elem is not None and t_elem.text: title = t_elem.text
            a_elem = opf_xml.find('.//{http://purl.org/dc/elements/1.1/}creator')
            if a_elem is not None and a_elem.text: author = a_elem.text

            manifest = {item.attrib['id']: item.attrib['href'] for item in opf_xml.findall('.//{http://www.idpf.org/2007/opf}manifest/{http://www.idpf.org/2007/opf}item')}
            base_dir = os.path.dirname(rootfile_path)
            
            chap_idx = 1
            for itemref in opf_xml.findall('.//{http://www.idpf.org/2007/opf}spine/{http://www.idpf.org/2007/opf}itemref'):
                idref = itemref.attrib['idref']
                if idref in manifest:
                    file_path = os.path.normpath(os.path.join(base_dir, manifest[idref])).replace('\\', '/')
                    try:
                        raw_html = z.read(file_path).decode('utf-8', errors='ignore')
                        clean_text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', raw_html)).strip()
                        if len(clean_text) > 50:
                            chapters_content.append({"location": f"Chapter {chap_idx}", "text": clean_text})
                            chap_idx += 1
                    except Exception:
                        continue
                        
    return {"title": title, "author": author, "content": chapters_content}

# 파일 업로드 화면
uploaded_file = st.file_uploader("전자책 파일(EPUB, PDF)을 업로드하세요", type=["pdf", "epub"])

if uploaded_file and api_key:
    st.success(f"'{uploaded_file.name}' 업로드 완료!")
    
    if st.button("🚀 AI 분석 및 독서 노트 추출 시작"):
        with st.spinner("책 내용을 분석하고 출처를 정리하는 중입니다..."):
            book_info = extract_book_data(uploaded_file)
            st.subheader(f"📖 《{book_info['title']}》 ({book_info['author']}) 독서 노트")
            
            # AI 추출 프롬프트
            client = openai.OpenAI(api_key=api_key)
            
            # 첫 부분 텍스트 샘플 분석 예시
            sample_text = book_info['content'][0]['text'] if book_info['content'] else ""
            location = book_info['content'][0]['location'] if book_info['content'] else "본문"
            
            prompt = f"""
            책 제목: {book_info['title']}
            저자: {book_info['author']}
            위치: {location}
            본문: {sample_text[:2000]}
            
            위 본문에서 아래 4가지 카테고리로 중요 내용을 발췌하거나 요약하세요:
            1. 📌 핵심 줄거리 & 중요 메모
            2. 💖 마음에 와닿는 문장
            3. 💬 인용하기 좋은 문장
            4. 📖 예화 / 에피소드 / 스토리
            
            각 항목 끝에는 반드시 "출처: 《{book_info['title']}》 ({book_info['author']}) - {location}" 형식을 추가하세요.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            
            st.markdown(response.choices[0].message.content)

elif uploaded_file and not api_key:
    st.warning("왼쪽 사이드바에 OpenAI API Key를 입력해주세요.")
