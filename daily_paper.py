import arxiv
import requests
import json
from datetime import datetime, timedelta
import time
import os

# --- 配置区 ---
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/your_webhook"
# 建议在 daily_paper.py 顶部这样改，这样最安全
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
SERVER_CHAN_KEY = os.environ.get("SERVER_CHAN_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
PWC_BASE_URL = "https://arxiv.paperswithcode.com/api/v0/papers/"

# 定义三个主题及其对应的精准搜索词
TOPICS = [
    {
        "name": "小红点 (Little Red Dots)",
        "query": 'abs:"Little Red Dots" AND (cat:astro-ph.GA OR cat:astro-ph.CO)',
        "max": 8
    },
    {
        "name": "引力波 (Gravitational Waves)",
        "query": 'abs:"gravitational waves" AND cat:astro-ph.HE',
        "max": 5
    },
    {
        "name": "超大质量双黑洞 (Supermassive Binary Black Holes)",
        "query": 'abs:supermassive AND abs:binary AND abs:"black hole" AND (cat:astro-ph.GA OR cat:astro-ph.CO OR cat:astro-ph.HE)',
        "max": 8
    }
]

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

def summarize_with_deepseek(paper, topic_name):
    """使用 DeepSeek 进行论文摘要深度总结"""
    # 构造 Prompt
    prompt_text = f"""你是一个学术分析专家。请根据以下论文的标题和摘要提供中文深度分析。
    论文标题: {paper['title']}
    论文摘要: {paper['summary']}
    
    请严格按此格式输出：
    【快速抓要点】: （简练的语言说明该研究解决了什么问题？提出了什么新的方法？得出了什么结果结论？）
    【逻辑推导】：  (不要堆砌技术细节，而是还原作者的思考路径，请按"起承转合"的结构讲解：**背景（context）**：为什么大家之前解决不好这个问题？**破局（insight）**：作者是怎么灵光一现的？他的核心直觉是什么？怎么把问题拆解为更具体的子问题的？**拆解**：这个方法具体分几步实现？用1，2，3列表简洁描述输入到输出的过程。）
    【技术细节】: （补充论文中最关键的1-2个技术实现细节（比如某个特殊的Loss Function或数据处理技巧）
    【局限性】: （潜在不足）
    【专业知识解释】: （解释论文中核心实验方法涉及的专业名词概念）
    """

    payload = {
        "model": "deepseek-chat", 
        "messages": [
            {"role": "system", "content": "你是一个资深天体物理学家，擅长精炼地总结引力波、黑洞和高红移星系领域的最新研究。"},
            {"role": "user", "content": prompt_text}
        ],
        "stream": False
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    try:
        # --- 核心修正：补全请求逻辑 ---
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=90)
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

def push_to_wechat(title, report_content):
    """发送微信推送 (Server酱)"""
    url = f"https://sctapi.ftqq.com/{SERVER_CHAN_KEY}.send"
    data = {
        "title": f"今日arXiv天文学进展 {datetime.now().strftime('%m-%d')}",
        "desp": report_content
    }
    requests.post(url, data=data)

if __name__ == "__main__":
    client = arxiv.Client()
    
    for topic in TOPICS:
        print(f"正在搜集主题：{topic['name']}...")
        
        # 1. 扩大搜索范围以确认今日总数（例如设定上限 50）
        search_all = arxiv.Search(
            query=topic['query'],
            max_results=50, 
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        all_results = list(client.results(search_all))
        total_count = len(all_results)
        
        if total_count == 0:
            print(f"{topic['name']} 今日无新论文。")
            continue
            
        # 2. 仅对设定的 max 数量（或更少）进行总结
        display_results = all_results[:topic['max']] 
        actual_display_count = len(display_results)
        
        # 初始化报告页眉，展示统计数据
        topic_report = f"📊 今日共发现 {total_count} 篇相关论文，为您深度解析前 {actual_display_count} 篇：\n\n"
        
        for i, res in enumerate(display_results):
            print(f"分析中: {res.title}")
            
            # 获取代码链接（保留你原有的函数逻辑）
            code_url = get_code_link(res.entry_id)
            code_md = f" | [💻 代码]({code_url})" if code_url else ""
            
            paper_info = {"title": res.title, "summary": res.summary.replace('\n', ' ')}
            summary = summarize_with_deepseek(paper_info, topic['name'])
            
            topic_report += f"### {i+1}. {res.title}\n🔗 [原文]({res.entry_id}){code_md}\n{summary}\n\n---\n"
        
        # 3. 如果总数超过了展示数，在结尾添加提醒
        if total_count > topic['max']:
            topic_report += f"⚠️ 注：今日还有 {total_count - topic['max']} 篇论文未在此展示，请点击 arXiv 官网查看更多。"

        # 4. 推送
        # 修改推送标题，加入 (当前展示数/总数) 的标识
        push_header = f"🔭 {topic['name']} ({actual_display_count}/{total_count}) {datetime.now().strftime('%m-%d')}"
        push_to_wechat(push_header, topic_report)
        print(f"{topic['name']} 推送成功！({actual_display_count}/{total_count})")
        
        # 每个主题之间停顿以避开频率限制
        time.sleep(5)
