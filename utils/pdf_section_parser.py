import pdfplumber
import requests
from io import BytesIO
import re

async def extract_sections(url: str) -> list:
    print(f"[DEBUG] 正在解析URL: {url}")  # 添加调试输出
    try:
        # 增加User-Agent避免被拒绝
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            raise RuntimeError(f"HTTP请求失败: {response.status_code}")
            
        response = requests.get(url)
        pdf_bytes = BytesIO(response.content)
        
        sections = []
        with pdfplumber.open(pdf_bytes) as pdf:
            for page in pdf.pages:
                # 使用布局分析识别标题
                words = page.extract_words(keep_blank_chars=True, extra_attrs=["size", "fontname"])
                
                # 识别章节标题规则：
                # 1. 包含章节关键词
                # 2. 字号大于12pt
                # 3. 位于页面顶部区域（前20%）
                for word in words:
                    text = word['text'].strip()
                    y_pos = word['top'] / page.height
                    if (
                        re.search(r'(section|chapter|part|§)\s*\d+', text, re.IGNORECASE) and
                        word['size'] > 12 and
                        y_pos < 0.2
                    ):
                        sections.append(text)
        
        return list(set(sections))  # 去重后返回
    
    except Exception as e:
        raise RuntimeError(f"PDF解析失败: {str(e)}")
