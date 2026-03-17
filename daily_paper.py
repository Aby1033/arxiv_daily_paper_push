import arxiv
import requests
import json
from datetime import datetime, timedelta
import time

# --- 配置区 ---
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/your_webhook"
DEEPSEEK_API_KEY = "sk-0dafa5bf8afc46dda30a951a58971d11"  
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
SERVER_CHAN_KEY = "SCT324763TekomcN4copo04lCDYE7gMzzM" # 从 sct.ftqq.com 获取
PWC_BASE_URL = "https://arxiv.paperswithcode.com/api/v0/papers/"

def get_code_link(arxiv_url):
    """从 PapersWithCode 获取代码链接"""
    arxiv_id = arxiv_url.split('/')[-1].split('v')[0]
    try:
        r = requests.get(f"{PWC_BASE_URL}{arxiv_id}", timeout=10).json()
        if "official" in r and r["official"]:
            return r["official"]["url"]
    except:
        pass
    return None

def summarize_with_deepseek(paper):
    """使用 DeepSeek 进行论文摘要深度总结"""
    # 构造 Prompt
    prompt_text = f"""你是一个学术分析专家。请根据以下论文的标题和摘要提供中文深度分析。
    论文标题: {paper['title']}
    论文摘要: {paper['summary']}
    
    请严格按此格式输出：
    【快速抓要点】: （简练的语言说明该研究解决了什么问题？提出了什么新的方法？得出了什么结果结论？）
    【逻辑推导】：  (不要堆砌技术细节，而是还原作者的思考路径，请按“起承转合”的结构讲解：**背景（context）**：为什么大家之前解决不好这个问题？**破局（insight）**：作者是怎么灵光一现的？他的核心直觉是什么？怎么把问题拆解为更具体的子问题的？**拆解**：这个方法具体分几步实现？用1，2，3列表简洁描述输入到输出的过程。）
    【技术细节】: （补充论文中最关键的1-2个技术实现细节（比如某个特殊的Loss Function或数据处理技巧）
    【局限性】: （潜在不足）
    【专业知识解释】: （解释论文中核心实验方法涉及的专业名词概念（比如SFT微调、ResNet架构、推理等）
    """

    payload = {
        "model": "deepseek-chat", 
        "messages": [
            {"role": "system", "content": "你是一个资深天体物理学家，擅长解释引力波、黑洞和高红移星系领域的最新研究。"},
            {"role": "user", "content": prompt_text}
        ],
        "stream": False
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

      
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        res_json = response.json()
        
        # 增加这部分调试代码
        if 'error' in res_json:
            return f"DeepSeek API 报错: {res_json['error']['message']}"
        
        if 'choices' not in res_json:
            return f"API 未预期响应: {json.dumps(res_json)}"

        return res_json['choices'][0]['message']['content']
    except Exception as e:
        return f"网络或系统错误: {str(e)}"

def push_to_feishu(report_content):
    """发送飞书富文本卡片"""
    header = { "Content-Type": "application/json" }
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": { "tag": "plain_text", "content": f"🚀 ArXiv {datetime.now().strftime('%m-%d')}" },
                "template": "orange" 
            },
            "elements": [
                {"tag": "markdown", "content": report_content},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "基于 DeepSeek-V3 自动生成"}]}
            ]
        }
    }
    requests.post(FEISHU_WEBHOOK, headers=header, json=payload)

def push_to_wechat(report_content):
    """发送微信推送 (Server酱)"""
    url = f"https://sctapi.ftqq.com/{SERVER_CHAN_KEY}.send"
    data = {
        "title": f"今日arXiv天文学进展 {datetime.now().strftime('%m-%d')}",
        "desp": report_content
    }
    requests.post(url, data=data)

if __name__ == "__main__":
    print("正在搜集最新论文...")
    client = arxiv.Client()
    search = arxiv.Search(
        # 建议使用 arXiv 的分类标签结合关键词，更加精准
        query='(cat:astro-ph.HE OR cat:astro-ph.GA) AND (abs:"gravitational waves" OR abs:"binary black hole" OR abs:"Little Red Dots")', 
        max_results=3, 
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    
    full_report = ""
    results = list(client.results(search))
    
    if not results:
        print("今日暂无新论文。")
    else:
        for i, res in enumerate(results):
            print(f"正在分析第 {i+1}/{len(results)} 篇: {res.title}")
            
            code_url = get_code_link(res.entry_id)
            code_md = f" | [💻 代码]({code_url})" if code_url else ""
            
            paper_info = {
                "title": res.title,
                "summary": res.summary.replace('\n', ' '),
                "url": res.entry_id
            }
            
            summary = summarize_with_deepseek(paper_info)
            full_report += f"### {i+1}. {res.title}\n🔗 [原文]({res.entry_id}){code_md}\n{summary}\n\n---\n"
        
        push_to_wechat(full_report)
        print("推送成功！")
