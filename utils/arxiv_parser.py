import requests
import tarfile
import io
import re
from bs4 import BeautifulSoup

async def get_arxiv_sections(pdf_title: str) -> list:
    """通过arXiv获取TeX源码解析章节结构"""
    try:
        # 第一步：搜索arxiv获取论文ID
        # 修正查询参数（原search_title参数无效）
        search_url = f"http://export.arxiv.org/api/query?search_all={urllib.parse.quote(pdf_title)}&max_results=1"
        response = requests.get(search_url)
        soup = BeautifulSoup(response.content, 'xml')
        entry = soup.find('entry')
        if not entry:
            return []
            
        arxiv_id = entry.id.text.split('/')[-1]
        
        # 第二步：下载源码包
        src_url = f"http://arxiv.org/e-print/{arxiv_id}"
        src_response = requests.get(src_url, stream=True)
        
        # 第三步：解压并解析TeX文件
        sections = []
        with tarfile.open(fileobj=io.BytesIO(src_response.content), mode="r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith('.tex'):
                    f = tar.extractfile(member)
                    content = f.read().decode('utf-8')
                    # 提取章节结构
                    # 改进后的正则表达式
                    section_pattern = re.compile(
                        r'\\section\*?{(.*?)(?=\\section|\\subsection|$)|'  # 匹配section直到遇到下个section/subsection或结束
                        r'\\subsection\*?{(.*?)(?=\\section|\\subsection|$)', 
                        re.DOTALL  # 允许跨行匹配
                    )
                    sections += re.findall(
                        r'\\section\*?{(.*?)}|\\subsection\*?{(.*?)}',
                        content
                    )
        
        # 过滤空值并去重
        return list(set(
            [s[0] or s[1] for s in sections if any(s)]
        ))
    
    except Exception as e:
        print(f"arXiv解析失败: {str(e)}")
        return []
