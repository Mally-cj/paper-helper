import re  # 新增导入
from typing import List, Dict, Optional
import arxiv
import datetime
from arxiv import SortCriterion

def search_arxiv(
    query: str = None,  # 改为可选参数
    category: str = None,  # 改为可选参数
    date: str = "all",
    selectivityrule: str = "date",
    max_results: int = 4,
    get_tex: bool = False,
    paper_id: str = None
) -> Optional[List[Dict]]:
    """
    在arXiv上搜索论文并返回格式化的结果
    
    参数:
        query (str): 搜索关键词
        category (str): 关键词查询类别
        date (str): 时间范围 ('all', 'week', 'month', 'year')
        selectivityrule (str): 排序规则 ('date' 或 'correlation')
        max_results (int): 最大返回结果数
    
    返回:
        Optional[List[Dict]]: 论文结果列表，每个结果包含标题、摘要、作者、日期和PDF链接
                             如果出错返回None
    """
    # 初始化arXiv客户端
    client = arxiv.Client()
    
    # 定义排序规则字典
    sort_rules = {
        "date": SortCriterion.SubmittedDate,
        "correlation": SortCriterion.Relevance
    }
    
    # 验证和处理排序规则
    sort_by = sort_rules.get(selectivityrule, SortCriterion.SubmittedDate)
    
    # 处理日期范围
    now = datetime.datetime.now()
    date_query = ""
    date_ranges = {
        "week": datetime.timedelta(weeks=1),
        "month": datetime.timedelta(days=30),
        "year": datetime.timedelta(days=365)
    }
    
    if date in date_ranges:
        start_date = (now - date_ranges[date]).strftime("%Y%m%d%H%M%S")
        end_date = now.strftime("%Y%m%d%H%M%S")
        date_query = f" AND submittedDate:[{start_date} TO {end_date}]"
    
    # 构造搜索查询
    if paper_id:  # 优先处理论文ID
        search = arxiv.Search(
            id_list=[paper_id],  # 使用arxiv的ID搜索功能
            max_results=1
        )
    else:
        full_query = f"{category}:{query}{date_query}"
        search = arxiv.Search(
            query=full_query,
            max_results=max_results,
            sort_by=sort_by
        )
    
    # 执行搜索并格式化结果
    try:
        results=[]
        for paper in client.results(search):
            result = {
                "title": paper.title,
                "abstract": paper.summary,
                "authors": [author.name for author in paper.authors],
                "date": paper.published.isoformat(),  # 将 datetime 转为 ISO 格式字符串
                "pdfUrl": f"https://arxiv.org/pdf/{paper.entry_id.split('/')[-1]}.pdf",
                "sourceUrl": f"https://arxiv.org/e-print/{paper.entry_id.split('/')[-1]}"  # 新增源码URL
            }
            if get_tex:
                try:
                    # 修复1：指定下载路径并保存文件名
                    paper.download_source(filename="downloaded_source.tar.gz")
                    result["has_tex"] = True
                    result["tex_source_path"] = "downloaded_source.tar.gz"  # 明确指定文件名
                except Exception as e:
                    result["has_tex"] = False
                    print(f"无法获取TeX源码: {e}")
            results.append(result)

        return results
    
    except arxiv.HTTPError as e:
        print(f"arXiv API请求出错：{e}")
        return None
    except Exception as e:
        print(f"发生未知错误：{e}")
        return None


def extract_sections(content: str) -> List[str]:
    """提取TeX文档中的章节结构"""
    return re.findall(r'\\section\*?{(.*?)}', content)

def extract_section_content(content: str, section_title: str) -> Optional[str]:
    """通用章节内容提取函数"""
    pattern = re.compile(
        r'\\section\*?{\s*%s\s*}(.*?)(?=\\section|\\end{document})' % re.escape(section_title),
        flags=re.DOTALL | re.IGNORECASE
    )
    match = pattern.search(content)
    return match.group(1).strip()[:1000] if match else None

def process_tex_content(file_path: str):
    """处理并打印TeX文件内容"""
    import tarfile
    import os
    
    print("\nTeX源码内容:")
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError("源码文件未找到")
            
        with tarfile.open(file_path, "r:gz") as tar:
            # 查找主TeX文件
            main_tex = sorted(
                [m for m in tar.getmembers() 
                 if m.name.endswith('.tex') 
                 and 'example' not in m.name],
                key=lambda x: x.size,
                reverse=True
            )
            
            if not main_tex:
                raise ValueError("未找到主TeX文件")
                
            largest_tex = main_tex[0]
            print(f"使用最大TeX文件: {largest_tex.name} ({largest_tex.size} bytes)")
            
            # 提取内容
            f = tar.extractfile(largest_tex)
            if f:
                content = f.read().decode('utf-8', errors='replace')
                sections = extract_sections(content)
                
                # 打印章节结构
                if sections:
                    print("\n章节结构:")
                    for i, sec in enumerate(sections, 1):
                        print(f"{i}. {sec}")
                else:
                    print("未找到章节定义")
                
                # 修复1：使用新函数并移除重复代码
                methods_content = extract_section_content(content, "Methods")
                if methods_content:
                    print("\nMethods 章节内容摘要:")
                    print(methods_content)
                else:
                    print("\n未识别到Methods章节")
                
                # 打印文件内容
                print("\n文件内容预览:")
                print(content[:1000])
                
    except Exception as e:
        print(f"处理TeX源码出错: {str(e)}")
        raise

# 修复2：移除文件末尾的无效示例代码
if __name__ == "__main__":
    results = search_arxiv(
        paper_id="2303.14081",
        get_tex=True
    )
    if results:
        for result in results:
            print(f"标题: {result['title']}")
            print(f"PDF: {result['pdfUrl']}")
            if result.get('has_tex'):
                try:
                    process_tex_content(result["tex_source_path"])
                except Exception as e:
                    print(f"处理失败: {e}")
                    print(f"请尝试手动下载: {result['sourceUrl']}")
    # 示例：提取 Introduction 章节
    # intro_content = extract_section_content(content, "Introduction")