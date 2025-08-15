import os
import sys
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from logging.handlers import RotatingFileHandler

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
import smtplib


class Config:
    """配置常量类，包含网络请求、解析、日志、邮件等配置及扩展的交易相关关键词库"""
    # 网络请求配置
    BASE_URL = "http://mrxwlb.com/"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive'
    }
    TIMEOUT = 15  # 请求超时时间（秒）
    RETRY_TIMES = 3  # 请求重试次数
    RETRY_BACKOFF = 1  # 重试间隔系数

    # 网页解析配置
    CONTENT_SELECTOR = {'name': 'div', 'attrs': {'class': 'entry-content'}}
    NEWS_LINK_KEYWORD = "{date_str}新闻联播文字版"

    # 日志配置
    LOG_DIR = r"C:\Users\ljy\Desktop\news_logs"  # 日志目录
    LOG_FILE = os.path.join(LOG_DIR, "news_crawler.log")  # 日志文件路径
    LOG_MAX_BYTES = 1024 * 1024 * 5  # 5MB
    LOG_BACKUP_COUNT = 5

    # 邮件配置
    SENDER_EMAIL = "850224177@qq.com"  # 发件人邮箱
    SENDER_PASSWORD = "gzirjsmlhjdebcdi"  # 发件人邮箱密码（或授权码）
    RECEIVER_EMAIL = "15999018650@163.com"  # 收件人邮箱
    SMTP_SERVER = 'smtp.qq.com'  # SMTP服务器地址
    SMTP_PORT = 587  # SMTP服务器端口

    # 【扩展】交易相关关键词库（股票交易者核心关注维度）
    # 政策导向关键词（力度分级）
    POLICY_KEYWORDS = {
        '强力度': ['加快', '大力支持', '重点推进', '全面深化', '试点', '政策落地', 
                  '专项资金', '减税降费', '重大部署', '战略规划', '优先发展',
                  '突破性进展', '加大投入', '全面实施', '顶层设计', '立法保障'],
        '中力度': ['推进', '支持', '引导', '鼓励', '规划', '发展', '培育',
                  '完善', '优化', '促进', '提升', '加强', '建设', '拓展', '扶持'],
        '风险提示': ['规范', '监管', '整治', '调控', '限制', '整顿', '核查',
                   '约束', '收紧', '抑制', '管控', '治理', '清理', '查处']
    }

    # 行业赛道关键词（当前热点赛道）
    INDUSTRY_KEYWORDS = {
        '新质生产力': ['人工智能', '人形机器人', '半导体', '量子计算', '生物制造',
                     '脑机接口', '空天科技', '6G', '下一代互联网', '智能驾驶', '算力'],
        '新能源': ['光伏', '储能', '新能源汽车', '氢能', '风电', '核电', 
                 '新型电池', '新能源材料', '特高压', '智能电网', '虚拟电厂'],
        '高端制造': ['数控机床', '工业母机', '航空航天', '海洋工程', '机器人',
                   '精密仪器', '智能装备', '高端芯片', '航空发动机', '工业软件'],
        '消费': ['智能家居', '新能源汽车', '跨境电商', '文旅消费', '健康消费',
               '绿色消费', '数字消费', '服务消费', '品牌消费', '农村消费'],
        '生物医药': ['创新药', '疫苗', '医疗器械', '基因治疗', '细胞治疗',
                   '中医药', '生物制剂', '医疗设备', '精准医疗', 'CXO'],
        '数字经济': ['数据中心', '云计算', '大数据', '区块链', '数字货币',
                   '工业互联网', '数字孪生', '元宇宙', '算力网络', 'AI'],
        '基建与房地产': ['新型城镇化', '保障房', '城市更新', '水利工程',
                       '交通建设', '一带一路', '区域协调', '绿色建筑']
    }

    # 企业相关关键词（龙头企业及信号）
    ENTERPRISE_KEYWORDS = {
        '龙头企业': ['华为', '比亚迪', '宁德时代', '中芯国际', '隆基绿能', '迈瑞医疗',
                   '贵州茅台', '招商银行', '长江电力', '中国建筑', '腾讯', '阿里',
                   '京东', '美团', '药明康德', '恒瑞医药', '三一重工', '万华化学'],
        '企业信号': ['量产', '研发突破', '订单增长', '战略合作', '扩产', '技术转化',
                   '业绩预增', '新产品发布', '市场份额扩大', '专利突破', '并购重组',
                   '产能提升', '出口增长', '合作协议', '技术引进']
    }

    # 宏观经济指标与政策工具
    MACRO_KEYWORDS = ['GDP', 'PMI', 'CPI', 'PPI', '社融', '利率', '汇率', '进出口',
                    '失业率', '财政政策', '货币政策', '准备金率', '国债收益率',
                    'M2', '固定资产投资', '社会消费品零售', '工业增加值', '贸易顺差',
                    '外汇储备', 'PMI新订单', '信贷规模']

    # 区域经济关键词
    REGIONAL_KEYWORDS = ['京津冀', '长三角', '粤港澳', '成渝', '雄安新区', '海南自贸港',
                       '浦东新区', '自贸区', '经济特区', '一带一路', '西部大开发',
                       '东北振兴', '中部崛起', '粤港澳大湾区']

    # 国际经贸关键词
    GLOBAL_TRADE_KEYWORDS = ['关税', '自贸协定', '一带一路', '进口博览会', '出口数据',
                           '贸易伙伴', '跨境电商', 'RCEP', 'WTO', '国际合作',
                           '海外投资', '大宗商品', '供应链', '产业链']


def setup_logger():
    """配置日志系统，同时输出到控制台和文件"""
    if not os.path.exists(Config.LOG_DIR):
        os.makedirs(Config.LOG_DIR, exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()


def validate_email_config():
    """验证邮件配置是否完整"""
    required_configs = [
        Config.SENDER_EMAIL,
        Config.SENDER_PASSWORD,
        Config.RECEIVER_EMAIL,
        Config.SMTP_SERVER
    ]

    if not all(required_configs) or Config.SMTP_PORT <= 0:
        logger.error("邮件配置不完整，请检查Config类中的邮件设置")
        return False
    return True


if not validate_email_config():
    sys.exit(1)


def create_session():
    """创建带有重试机制的requests会话"""
    session = requests.Session()

    retry_strategy = Retry(
        total=Config.RETRY_TIMES,
        backoff_factor=Config.RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504]
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update(Config.HEADERS)

    return session


session = create_session()


def get_today_str():
    """获取当前日期，格式为 yyyy年mm月dd日"""
    #return datetime.now().strftime("%Y年%m月%d日")
    return "2025年08月14日"  # 可根据需要修改为动态获取


def format_date_for_url(date_str):
    """将 "yyyy年mm月dd日" 转换为 URL 中的格式（yyyy/mm/dd）"""
    return date_str.replace('年', '/').replace('月', '/').replace('日', '')


def fetch_news_content(date_str):
    """抓取指定日期的新闻联播文字版内容"""
    try:
        formatted_date = format_date_for_url(date_str)
        search_path = f"search/{formatted_date}/{date_str}新闻联播文字版/"
        search_url = urljoin(Config.BASE_URL, search_path)

        logger.debug(f"尝试访问搜索页面: {search_url}")
        response = session.get(search_url, timeout=Config.TIMEOUT)
        response.raise_for_status()
        logger.info(f"成功访问搜索页面: {search_url}")

    except requests.RequestException as e:
        logger.error(f"访问搜索页面失败: {str(e)}", exc_info=True)
        return None

    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        news_link = None
        target_text = Config.NEWS_LINK_KEYWORD.format(date_str=date_str)

        for a in soup.find_all('a', href=True):
            if target_text in a.text.strip():
                news_link = urljoin(Config.BASE_URL, a['href'])
                break

        if not news_link:
            logger.warning(f"未找到 {date_str} 的新闻联播文字版链接")
            return None

        logger.info(f"找到新闻链接: {news_link}")

    except Exception as e:
        logger.error(f"解析搜索页面失败: {str(e)}", exc_info=True)
        return None

    try:
        detail_response = session.get(news_link, timeout=Config.TIMEOUT)
        detail_response.raise_for_status()
        logger.info(f"成功访问详情页面: {news_link}")

    except requests.RequestException as e:
        logger.error(f"访问详情页面失败: {str(e)}", exc_info=True)
        return None

    try:
        detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
        content_div = detail_soup.find(** Config.CONTENT_SELECTOR)

        if content_div:
            news_content = content_div.get_text(strip=True, separator='\n')
            news_content = '\n'.join([line.strip() for line in news_content.split('\n') if line.strip()])
            logger.info("成功提取新闻联播文字内容")
            return news_content
        else:
            logger.warning("未能找到新闻联播的文字内容区块")
            return None

    except Exception as e:
        logger.error(f"解析详情页面失败: {str(e)}", exc_info=True)
        return None


def analyze_news_for_trading(news_content):
    """从股票交易视角解析新闻内容，提取关键信息并结构化"""
    analysis_result = {
        'policy': {'强力度': [], '中力度': [], '风险提示': []},  # 政策导向
        'industry': {},  # 涉及行业
        'enterprise': {'龙头企业': [], '企业信号': []},  # 企业相关
        'macro': [],  # 宏观指标
        'regional': [],  # 区域经济
        'global_trade': []  # 国际经贸
    }

    # 1. 政策导向分析（按力度分级）
    for level, keywords in Config.POLICY_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf'\b{kw}\b', news_content):
                sentences = re.split(r'[。？！；,.?!;]', news_content)
                related_sentences = [s for s in sentences if kw in s]
                analysis_result['policy'][level].extend(related_sentences)

    # 2. 行业赛道分析
    for industry, keywords in Config.INDUSTRY_KEYWORDS.items():
        related_info = []
        for kw in keywords:
            if re.search(rf'\b{kw}\b', news_content):
                sentences = re.split(r'[。？！；,.?!;]', news_content)
                related_sentences = [s for s in sentences if kw in s]
                related_info.extend(related_sentences)
        if related_info:
            analysis_result['industry'][industry] = list(set(related_info))

    # 3. 企业相关分析
    for ent in Config.ENTERPRISE_KEYWORDS['龙头企业']:
        if ent in news_content:
            sentences = re.split(r'[。？！；,.?!;]', news_content)
            related_sentences = [s for s in sentences if ent in s]
            analysis_result['enterprise']['龙头企业'].extend(related_sentences)
            
    for sig in Config.ENTERPRISE_KEYWORDS['企业信号']:
        if sig in news_content:
            sentences = re.split(r'[。？！；,.?!;]', news_content)
            related_sentences = [s for s in sentences if sig in s]
            analysis_result['enterprise']['企业信号'].extend(related_sentences)

    # 4. 宏观经济指标
    for macro in Config.MACRO_KEYWORDS:
        if re.search(rf'\b{macro}\b', news_content):
            sentences = re.split(r'[。？！；,.?!;]', news_content)
            related_sentences = [s for s in sentences if macro in s]
            analysis_result['macro'].extend(related_sentences)

    # 5. 区域经济分析
    for region in Config.REGIONAL_KEYWORDS:
        if region in news_content:
            sentences = re.split(r'[。？！；,.?!;]', news_content)
            related_sentences = [s for s in sentences if region in s]
            analysis_result['regional'].extend(related_sentences)

    # 6. 国际经贸分析
    for trade in Config.GLOBAL_TRADE_KEYWORDS:
        if trade in news_content:
            sentences = re.split(r'[。？！；,.?!;]', news_content)
            related_sentences = [s for s in sentences if trade in s]
            analysis_result['global_trade'].extend(related_sentences)

    return analysis_result


def generate_trading_email_content(raw_content, analysis_result):
    """生成带高亮和结构化分析的HTML邮件内容"""
    def highlight_keywords(text, keywords):
        for kw in keywords:
            text = re.sub(rf'\b({kw})\b', r'<span style="color:red;font-weight:bold">\1</span>', text)
        return text

    # 提取所有关键词用于全局高亮
    all_keywords = []
    for kw_list in Config.POLICY_KEYWORDS.values():
        all_keywords.extend(kw_list)
    for kw_list in Config.INDUSTRY_KEYWORDS.values():
        all_keywords.extend(kw_list)
    all_keywords.extend(Config.ENTERPRISE_KEYWORDS['龙头企业'])
    all_keywords.extend(Config.ENTERPRISE_KEYWORDS['企业信号'])
    all_keywords.extend(Config.MACRO_KEYWORDS)
    all_keywords.extend(Config.REGIONAL_KEYWORDS)
    all_keywords.extend(Config.GLOBAL_TRADE_KEYWORDS)
    all_keywords = list(set(all_keywords))

    # 原始内容高亮处理
    highlighted_raw = highlight_keywords(raw_content, all_keywords)
    highlighted_raw = highlighted_raw.replace('\n', '<br>')

    # 结构化分析板块HTML
    analysis_html = '<div style="margin:20px 0;padding:15px;border:1px solid #eee;border-radius:5px;background:#f9f9f9">'
    analysis_html += '<h3 style="color:#2c3e50">【交易视角分析】</h3>'

    # 政策导向板块
    policy_html = '<div style="margin:10px 0">'
    policy_html += '<h4 style="color:#3498db">1. 政策导向</h4>'
    for level, contents in analysis_result['policy'].items():
        if contents:
            policy_html += f'<p><strong>{level}:</strong><br>'
            policy_html += '<br>'.join([highlight_keywords(c, Config.POLICY_KEYWORDS[level]) for c in list(set(contents))])
            policy_html += '</p>'
    policy_html += '</div>'
    analysis_html += policy_html

    # 行业赛道板块
    industry_html = '<div style="margin:10px 0">'
    industry_html += '<h4 style="color:#3498db">2. 行业赛道</h4>'
    for industry, contents in analysis_result['industry'].items():
        if contents:
            industry_kw = Config.INDUSTRY_KEYWORDS[industry]
            industry_html += f'<p><strong>{industry}:</strong><br>'
            industry_html += '<br>'.join([highlight_keywords(c, industry_kw) for c in contents])
            industry_html += '</p>'
    industry_html += '</div>'
    analysis_html += industry_html

    # 企业相关板块
    enterprise_html = '<div style="margin:10px 0">'
    enterprise_html += '<h4 style="color:#3498db">3. 企业动态</h4>'
    if analysis_result['enterprise']['龙头企业']:
        enterprise_html += '<p><strong>龙头企业提及:</strong><br>'
        enterprise_html += '<br>'.join([highlight_keywords(c, Config.ENTERPRISE_KEYWORDS['龙头企业']) for c in list(set(analysis_result['enterprise']['龙头企业']))])
        enterprise_html += '</p>'
    if analysis_result['enterprise']['企业信号']:
        enterprise_html += '<p><strong>关键信号（量产/研发等）:</strong><br>'
        enterprise_html += '<br>'.join([highlight_keywords(c, Config.ENTERPRISE_KEYWORDS['企业信号']) for c in list(set(analysis_result['enterprise']['企业信号']))])
        enterprise_html += '</p>'
    enterprise_html += '</div>'
    analysis_html += enterprise_html

    # 宏观经济指标板块
    macro_html = '<div style="margin:10px 0">'
    macro_html += '<h4 style="color:#3498db">4. 宏观经济指标</h4>'
    if analysis_result['macro']:
        macro_html += '<p>'
        macro_html += '<br>'.join([highlight_keywords(c, Config.MACRO_KEYWORDS) for c in list(set(analysis_result['macro']))])
        macro_html += '</p>'
    else:
        macro_html += '<p>无显著宏观指标提及</p>'
    macro_html += '</div>'
    analysis_html += macro_html

    # 区域经济板块
    regional_html = '<div style="margin:10px 0">'
    regional_html += '<h4 style="color:#3498db">5. 区域经济动态</h4>'
    if analysis_result['regional']:
        regional_html += '<p>'
        regional_html += '<br>'.join([highlight_keywords(c, Config.REGIONAL_KEYWORDS) for c in list(set(analysis_result['regional']))])
        regional_html += '</p>'
    else:
        regional_html += '<p>无显著区域经济动态</p>'
    regional_html += '</div>'
    analysis_html += regional_html

    # 国际经贸板块
    global_html = '<div style="margin:10px 0">'
    global_html += '<h4 style="color:#3498db">6. 国际经贸动态</h4>'
    if analysis_result['global_trade']:
        global_html += '<p>'
        global_html += '<br>'.join([highlight_keywords(c, Config.GLOBAL_TRADE_KEYWORDS) for c in list(set(analysis_result['global_trade']))])
        global_html += '</p>'
    else:
        global_html += '<p>无显著国际经贸动态</p>'
    global_html += '</div>'
    analysis_html += global_html

    analysis_html += '</div>'

    # 拼接完整邮件内容
    full_html = f'''
    <html>
        <body>
            <h2 style="color:#2c3e50">{get_today_str()} 新闻联播文字版（交易视角分析）</h2>
            <div style="margin:20px 0">{highlighted_raw}</div>
            {analysis_html}
            <p style="color:#999;font-size:12px">注：红色加粗内容为交易关键信息，仅供参考</p>
        </body>
    </html>
    '''
    return full_html


def send_email(subject, body, is_html=False):
    """发送邮件，支持纯文本和HTML格式"""
    server = None
    try:
        msg = MIMEMultipart()
        msg['From'] = Config.SENDER_EMAIL
        msg['To'] = Config.RECEIVER_EMAIL
        msg['Subject'] = Header(subject, 'utf-8')

        content_type = 'html' if is_html else 'plain'
        msg.attach(MIMEText(body, content_type, 'utf-8'))

        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        server.starttls()
        server.login(Config.SENDER_EMAIL, Config.SENDER_PASSWORD)

        send_result = server.sendmail(Config.SENDER_EMAIL, Config.RECEIVER_EMAIL, msg.as_string())

        if not send_result:
            logger.info("邮件发送成功")
            return True
        else:
            logger.error(f"邮件发送失败：{send_result}")
            return False

    except smtplib.SMTPResponseException as e:
        if 'sendmail' in str(e.__traceback__):
            logger.error(f"邮件发送失败（发送阶段）: {str(e)}", exc_info=True)
            return False
        else:
            logger.warning(f"SMTP会话关闭异常，但邮件可能已发送: {str(e)}", exc_info=True)
            return True

    except Exception as e:
        logger.error(f"邮件发送失败: {str(e)}", exc_info=True)
        return False

    finally:
        if server:
            try:
                server.quit()
            except:
                server.close()


def send_error_notification(date_str, error_msg):
    """发送抓取失败的提醒邮件"""
    subject = f"【错误】{date_str} 新闻联播抓取失败"
    body = f"日期：{date_str}\n\n错误信息：{error_msg}\n\n请检查程序运行状态"
    return send_email(subject, body)


def run_task():
    """执行任务：抓取新闻联播并发送带交易视角分析的增强版邮件"""
    today = get_today_str()
    logger.info(f"===== 开始抓取 {today} 的新闻联播文字版 =====")

    # 抓取新闻内容
    news_content = fetch_news_content(today)
    if not news_content:
        error_msg = "未能获取新闻联播内容"
        logger.error(error_msg)
        send_error_notification(today, error_msg)
        return

    # 从交易视角分析新闻
    logger.info("开始从交易视角解析新闻内容...")
    analysis_result = analyze_news_for_trading(news_content)

    # 生成带分析的HTML邮件内容
    email_content = generate_trading_email_content(news_content, analysis_result)

    # 发送带交易分析的增强版邮件（仅发送这一封）
    subject = f"{today} 新闻联播文字版（交易视角分析）"
    logger.info(f"准备发送带交易分析的增强版邮件，内容已包含关键信息提取")
    if send_email(subject, email_content, is_html=True):
        logger.info("任务执行成功：带交易视角分析的增强版邮件已发送")
    else:
        logger.error("带交易视角分析的邮件发送失败")


def main():
    """主函数，执行新闻联播抓取和分析任务"""
    logger.info("程序启动，准备执行新闻联播抓取任务（交易视角版）")
    run_task()
    logger.info("任务执行完毕，程序退出")


if __name__ == "__main__":
    main()
