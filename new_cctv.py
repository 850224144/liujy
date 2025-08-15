import os
import sys
import re
from datetime import datetime, timedelta
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
    """配置常量类：包含所有程序所需的配置参数"""
    # 网络请求配置
    BASE_URL = "http://mrxwlb.com/"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive'
    }
    TIMEOUT = 20
    RETRY_TIMES = 4
    RETRY_BACKOFF = 2

    # 网页解析配置
    CONTENT_SELECTORS = [
        {'name': 'div', 'attrs': {'class': 'entry-content'}},
        {'name': 'div', 'attrs': {'class': 'article-content'}},
        {'name': 'div', 'id': 'content'}
    ]
    NEWS_LINK_KEYWORD = "{date_str}新闻联播文字版"

    # 日志配置
    LOG_DIR = os.path.join(os.path.expanduser("~"), "news_analysis_logs")
    LOG_FILE = os.path.join(LOG_DIR, "news_crawler_trade.log")
    LOG_MAX_BYTES = 1024 * 1024 * 10  # 10MB
    LOG_BACKUP_COUNT = 5

    # 邮件配置 - 根据实际情况修改
    SENDER_EMAIL = "850224177@qq.com"
    SENDER_PASSWORD = "gzirjsmlhjdebcdi"  # 注意：QQ邮箱使用授权码而非密码
    RECEIVER_EMAIL = "15999018650@163.com"
    SMTP_SERVER = 'smtp.qq.com'
    SMTP_PORT = 587

    # 关键词-板块映射表（精准关联A股板块）
    KEYWORD_TO_SECTOR = {
        # 新质生产力
        '人工智能': '人工智能板块',
        '人形机器人': '机器人板块',
        '半导体': '半导体板块',
        '量子计算': '量子科技板块',
        '生物制造': '生物制品板块',
        '脑机接口': '脑机接口板块',
        '6G': '通信设备板块',
        '智能驾驶': '智能驾驶板块',
        '商业航天': '航天航空板块',
        '低空经济': '通用航空板块',
        '卫星互联网': '卫星导航板块',

        # 新能源
        '光伏': '光伏板块',
        '储能': '储能板块',
        '新能源汽车': '新能源汽车板块',
        '氢能': '氢能板块',
        '风电': '风电板块',
        '核电': '核电板块',
        '钙钛矿电池': '光伏板块',
        '固态电池': '锂电池板块',

        # 高端制造
        '数控机床': '机床设备板块',
        '工业母机': '工业母机板块',
        '航空航天': '航天航空板块',
        '工业机器人': '机器人板块',
        '激光制造': '激光设备板块',

        # 生物医药
        '创新药': '创新药板块',
        '疫苗': '生物疫苗板块',
        '医疗器械': '医疗器械板块',
        '基因治疗': '基因测序板块',
        'CAR-T疗法': '细胞治疗板块',

        # 政策相关
        '减税降费': '全市场普益',
        '专项资金': '对应受益行业',
        '专项债': '基建/新能源板块',
        '超长期特别国债': '基建/金融板块',
        '试点': '对应试点行业',
        '政策落地': '对应政策行业',

        # 金融科技
        '金融科技': '金融科技板块',
        '互联网金融': '金融科技板块',

        # 区域经济
        '京津冀': '京津冀本地股',
        '长三角': '长三角本地股',
        '粤港澳大湾区': '粤港澳本地股',
        '雄安新区': '雄安新区板块',
        '海南自贸港': '海南板块'
    }

    # 利好力度评分标准（1-10分，越高影响越强）
    STRENGTH_SCORING = {
        # 政策力度
        '强力度（红）': 9,
        '中力度（橙）': 6,
        '风险提示（紫）': -7,  # 负值表示利空

        # 关键词强度
        '加快': 8, '大力支持': 9, '重点推进': 8, '全面深化': 8,
        '试点': 7, '政策落地': 8, '专项资金': 9, '减税降费': 9,
        '推进': 6, '支持': 6, '引导': 5, '鼓励': 5,
        '规范': -5, '监管': -6, '整治': -7, '限制': -8,

        # 企业信号
        '量产': 7, '研发突破': 8, '订单增长': 7, '业绩预增': 8,
        '战略合作': 6, '扩产': 6, '新产品发布': 5, '签订大单': 8
    }

    # 交易关键词库（保留分类，关联力度评分）
    POLICY_KEYWORDS = {
        '强力度（红）': {
            'words': [
                '加快', '大力支持', '重点推进', '全面深化', '试点', '政策落地',
                '专项资金', '减税降费', '重大部署', '战略规划', '优先发展',
                '突破性进展', '加大投入', '全面实施', '顶层设计', '立法保障',
                '迅速落地', '加速落地', '集中攻坚', '超常规推进', '先行先试',
                '顶格支持', '超长期特别国债', '专项债', '政策性开发性金融工具'
            ],
            'color': '#E53E3E',  # 强利好红色
            'strength': 9  # 基础力度分
        },
        '中力度（橙）': {
            'words': [
                '推进', '支持', '引导', '鼓励', '规划', '发展', '培育',
                '完善', '优化', '促进', '提升', '加强', '建设', '深化', '强化'
            ],
            'color': '#ED8936',  # 中等利好橙色
            'strength': 6
        },
        '风险提示（紫）': {
            'words': [
                '规范', '监管', '整治', '调控', '限制', '整顿', '核查',
                '约束', '收紧', '抑制', '管控', '治理', '清理', '查处',
                '顶格处罚', '联合惩戒', '市场禁入', '零容忍'
            ],
            'color': '#805AD5',  # 利空紫色
            'strength': -7
        }
    }

    INDUSTRY_KEYWORDS = {
        '新质生产力（蓝）': {
            'words': ['人工智能', '人形机器人', '半导体', '量子计算', '生物制造',
                      '脑机接口', '空天科技', '6G', '智能驾驶', '商业航天', '低空经济', '卫星互联网'],
            'color': '#1E90FF',  # 蓝色
            'strength': 7
        },
        '新能源（绿）': {
            'words': ['光伏', '储能', '新能源汽车', '氢能', '风电', '核电',
                      '钙钛矿电池', '固态电池', '钠离子电池', '海上风电', '光储充'],
            'color': '#38A169',  # 绿色
            'strength': 7
        },
        '高端制造（青）': {
            'words': ['数控机床', '工业母机', '航空航天', '工业机器人', '精密仪器',
                      '增材制造', '激光制造', '超精密制造'],
            'color': '#20B2AA',  # 青色
            'strength': 6
        },
        '生物医药（粉）': {
            'words': ['创新药', '疫苗', '医疗器械', '基因治疗', '细胞治疗',
                      'ADC药物', '双抗药物', 'CAR-T疗法', 'AI药物发现', '数字疗法'],
            'color': '#FF69B4',  # 粉色
            'strength': 6
        }
    }

    ENTERPRISE_KEYWORDS = {
        '龙头企业（红）': {
            'words': [
                # 金融
                '工商银行', '建设银行', '农业银行', '中国银行', '招商银行',
                '中国平安', '中国人寿', '中信证券', '东方财富',
                # 消费
                '贵州茅台', '五粮液', '泸州老窖', '山西汾酒', '美的集团', '格力电器',
                '伊利股份', '中国中免',
                # 医药
                '恒瑞医药', '迈瑞医疗', '药明康德', '爱尔眼科',
                # 新能源
                '宁德时代', '隆基绿能', '比亚迪', '阳光电源', '通威股份',
                # 高端制造/半导体
                '中芯国际', '北方华创', '立讯精密', '京东方A', '海康威视', '中兴通讯'
            ],
            'color': '#E53E3E',  # 红色
            'strength': 8
        },
        '企业信号（橙）': {
            'words': [
                '量产', '研发突破', '订单增长', '战略合作', '扩产', '技术转化',
                '业绩预增', '新产品发布', '专利突破', '并购重组', '中标', '签订大单',
                '通过认证', 'FDA认证', '产能爬坡', '满产满销', '提价'
            ],
            'color': '#ED8936',  # 橙色
            'strength': 6
        }
    }

    MACRO_KEYWORDS = {
        '核心指标（蓝）': {
            'words': [
                'GDP', 'PMI', 'CPI', 'PPI', '社融', '利率', '汇率', '进出口',
                '失业率', '财政政策', '货币政策', '准备金率', '国债收益率'
            ],
            'color': '#1E90FF',  # 蓝色
            'strength': 5
        }
    }

    REGIONAL_KEYWORDS = {
        '重点区域（青）': {
            'words': [
                '京津冀', '长三角', '粤港澳大湾区', '成渝', '雄安新区', '海南自贸港',
                '浦东新区', '深圳先行示范区'
            ],
            'color': '#20B2AA',  # 青色
            'strength': 5
        }
    }

    ALL_KEYWORD_TYPES = {
        '政策导向': POLICY_KEYWORDS,
        '行业赛道': INDUSTRY_KEYWORDS,
        '企业动态': ENTERPRISE_KEYWORDS,
        '宏观指标': MACRO_KEYWORDS,
        '区域经济': REGIONAL_KEYWORDS
    }


def setup_logger():
    """配置日志系统"""
    if not os.path.exists(Config.LOG_DIR):
        os.makedirs(Config.LOG_DIR, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(module)s - %(levelname)s - %(message)s')

    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 文件日志
    file_handler = RotatingFileHandler(
        Config.LOG_FILE, maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()


def validate_email_config():
    """验证邮件配置是否完整"""
    required_configs = [
        Config.SENDER_EMAIL, Config.SENDER_PASSWORD,
        Config.RECEIVER_EMAIL, Config.SMTP_SERVER
    ]
    if not all(required_configs) or Config.SMTP_PORT <= 0:
        logger.error("邮件配置不完整：请检查发件人邮箱、授权码、收件人邮箱、SMTP服务器")
        return False
    if "qq.com" in Config.SENDER_EMAIL and len(Config.SENDER_PASSWORD) != 16:
        logger.warning("QQ邮箱授权码应为16位，当前可能是密码，请替换为授权码")
    return True


# 验证邮件配置
if not validate_email_config():
    sys.exit(1)


def create_session():
    """创建带有重试机制的请求会话"""
    session = requests.Session()
    retry_strategy = Retry(
        total=Config.RETRY_TIMES,
        backoff_factor=Config.RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(Config.HEADERS)
    return session


# 创建请求会话
session = create_session()


def get_date_str(days_ago=0):
    """获取指定日期的字符串表示，默认今天"""
    target_date = datetime.now() - timedelta(days=days_ago)
    #return target_date.strftime("%Y年%m月%d日")
    return "2025年08月14日"

def format_date_for_url(date_str):
    """将日期字符串格式化为URL所需格式"""
    return re.sub(r'年|月', '/', date_str).replace('日', '')


def fetch_news_content(date_str):
    """爬取指定日期的新闻联播内容"""
    try:
        formatted_date = format_date_for_url(date_str)
        search_path = f"search/{formatted_date}/{date_str}新闻联播文字版/"
        search_url = urljoin(Config.BASE_URL, search_path)
        logger.debug(f"尝试访问搜索页：{search_url}")

        response = session.get(search_url, timeout=Config.TIMEOUT)
        response.raise_for_status()
        logger.info(f"成功访问搜索页：{search_url}")

    except requests.RequestException as e:
        logger.error(f"搜索页访问失败：{str(e)}", exc_info=True)
        return None

    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        target_text = Config.NEWS_LINK_KEYWORD.format(date_str=date_str)
        news_link = None

        # 查找新闻链接
        for a in soup.find_all('a', href=True, string=re.compile(target_text)):
            news_link = urljoin(Config.BASE_URL, a['href'])
            break
        if not news_link:
            for a in soup.find_all('a', href=True):
                if target_text in a.get_text(strip=True):
                    news_link = urljoin(Config.BASE_URL, a['href'])
                    break

        # 如果没找到，尝试从首页查找
        if not news_link:
            logger.warning(f"未找到{date_str}新闻联播链接，尝试从首页查找")
            try:
                index_response = session.get(Config.BASE_URL, timeout=Config.TIMEOUT)
                index_soup = BeautifulSoup(index_response.text, 'html.parser')
                for a in index_soup.find_all('a', href=True):
                    if target_text in a.get_text(strip=True):
                        news_link = urljoin(Config.BASE_URL, a['href'])
                        break
            except Exception as e:
                logger.error(f"首页查找失败：{str(e)}", exc_info=True)
            if not news_link:
                logger.error(f"最终未找到{date_str}新闻联播链接")
                return None

        logger.info(f"找到新闻详情页：{news_link}")

    except Exception as e:
        logger.error(f"解析搜索页失败：{str(e)}", exc_info=True)
        return None

    try:
        # 获取新闻详情页内容
        detail_response = session.get(news_link, timeout=Config.TIMEOUT)
        detail_response.raise_for_status()
        detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
        news_content = None

        # 尝试多种选择器提取内容
        for selector in Config.CONTENT_SELECTORS:
            content_div = detail_soup.find(**selector)
            if content_div:
                news_content = content_div.get_text(strip=True, separator='\n')
                news_content = '\n'.join([line.strip() for line in news_content.split('\n') if line.strip()])
                logger.info(f"通过选择器{selector}提取到内容（长度：{len(news_content)}字符）")
                break

        # 如果所有选择器都失败，尝试提取<body>内文本
        if not news_content:
            logger.warning("所有选择器均未提取到内容，尝试提取<body>内文本")
            body_text = detail_soup.body.get_text(strip=True, separator='\n')
            news_content = '\n'.join([line.strip() for line in body_text.split('\n') if line.strip()][:50])
            if not news_content:
                logger.error("最终未提取到任何新闻内容")
                return None

        return news_content

    except requests.RequestException as e:
        logger.error(f"详情页访问失败：{str(e)}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"解析详情页失败：{str(e)}", exc_info=True)
        return None


def get_related_info(news_content, keywords):
    """提取与关键词相关的句子和统计信息"""
    related_sentences = []
    hit_count = 0
    sentences = re.split(r'[。？！；,.?!;]', news_content)
    # 构建关键词正则表达式，确保全词匹配
    kw_pattern = re.compile(r'\b(' + '|'.join(re.escape(kw) for kw in keywords) + r')\b')

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 5:
            continue
        if kw_pattern.search(sentence):
            related_sentences.append(sentence)
            hit_count += len(kw_pattern.findall(sentence))

    return {
        'sentences': list(set(related_sentences)),  # 去重
        'hit_count': hit_count,
        'kw_count': len([kw for kw in keywords if kw_pattern.search(news_content)]),
        'words': keywords  # 保存匹配的关键词列表，用于后续高亮
    }


def analyze_news_for_trading(news_content):
    """分析新闻内容，提取交易相关信息"""
    analysis_result = {}
    # 汇总板块利好评分
    sector_strength = {}

    for type_name, type_keywords in Config.ALL_KEYWORD_TYPES.items():
        analysis_result[type_name] = {}
        for sub_type, sub_info in type_keywords.items():
            kw_list = sub_info['words']
            if not kw_list:
                continue

            related_info = get_related_info(news_content, kw_list)
            if related_info['hit_count'] > 0:
                # 计算综合力度分（基础分 + 关键词加权）
                base_strength = sub_info['strength']
                keyword_strength = 0
                for kw in kw_list:
                    if re.search(r'\b' + re.escape(kw) + r'\b', news_content):
                        keyword_strength += Config.STRENGTH_SCORING.get(kw, 0)

                # 平均力度分（基础分 + 关键词分平均）
                total_strength = round((base_strength + keyword_strength) / (1 + len(kw_list)), 1)

                # 映射关联板块
                related_sectors = set()
                keywords_found = []
                for kw in kw_list:
                    if re.search(r'\b' + re.escape(kw) + r'\b', news_content):
                        sector = Config.KEYWORD_TO_SECTOR.get(kw, f"关联{type_name}板块")
                        related_sectors.add(sector)
                        keywords_found.append(kw)

                        # 累计板块力度分
                        if sector not in sector_strength:
                            sector_strength[sector] = {
                                'total': 0,
                                'count': 0,
                                'keywords': set()
                            }
                        sector_strength[sector]['total'] += total_strength
                        sector_strength[sector]['count'] += 1
                        sector_strength[sector]['keywords'].update(keywords_found)

                # 保存分析结果
                analysis_result[type_name][sub_type] = {
                    'related_sentences': related_info['sentences'],
                    'hit_count': related_info['hit_count'],
                    'kw_count': related_info['kw_count'],
                    'color': sub_info['color'],
                    'strength': total_strength,
                    'related_sectors': list(related_sectors),
                    'words': kw_list,
                    'keywords_found': keywords_found  # 实际找到的关键词
                }
                logger.debug(f"{type_name}-{sub_type}：力度{total_strength}分，关联板块{related_sectors}")

    # 计算板块平均力度分并排序（降序）
    sector_summary = []
    for sector, data in sector_strength.items():
        avg_strength = round(data['total'] / data['count'], 1)
        # 转换关键词集合为逗号分隔的字符串
        keywords_str = ', '.join(list(data['keywords'])[:5])  # 最多显示5个关键词
        sector_summary.append({
            'sector': sector,
            'avg_strength': avg_strength,
            'mention_count': data['count'],
            'keywords': keywords_str
        })
    sector_summary.sort(key=lambda x: x['avg_strength'], reverse=True)

    return {
        'detailed_analysis': analysis_result,
        'sector_summary': sector_summary
    }


def highlight_keywords(text, keyword_groups):
    """高亮文本中的关键词"""
    highlighted_text = text
    for sub_type, group_info in keyword_groups.items():
        # 确保'words'键存在，避免KeyError
        if 'words' not in group_info:
            continue

        keywords = group_info['words']
        color = group_info.get('color', '#000000')  # 提供默认颜色
        if not keywords:
            continue

        # 过滤掉空字符串或None的关键词
        valid_keywords = [kw for kw in keywords if kw and isinstance(kw, str)]
        if not valid_keywords:
            continue

        # 使用正则表达式进行全词匹配并高亮
        kw_pattern = re.compile(r'\b(' + '|'.join(re.escape(kw) for kw in valid_keywords) + r')\b')
        highlighted_text = kw_pattern.sub(
            rf'<span class="highlighted bg-opacity-20" style="background-color:{color};color:{color}">\1</span>',
            highlighted_text
        )
    return highlighted_text


def generate_html_report(raw_content, analysis_result, date_str):
    """生成符合设计的HTML报告"""
    detailed = analysis_result['detailed_analysis']
    sector_summary = analysis_result['sector_summary']
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 高亮原始内容
    highlighted_raw = raw_content
    for type_name, type_keywords in Config.ALL_KEYWORD_TYPES.items():
        highlighted_raw = highlight_keywords(highlighted_raw, type_keywords)
    highlighted_raw = highlighted_raw.replace('\n', '<br>')

    # 提取核心摘要信息
    top_sector = sector_summary[0] if sector_summary else None
    policy_highlights = []
    risk_highlights = []

    # 提取政策重点和风险提示
    if '政策导向' in detailed:
        for sub_type, sub_data in detailed['政策导向'].items():
            if sub_type == '强力度（红）' and sub_data['strength'] > 0:
                policy_highlights.extend(sub_data['related_sentences'])
            elif sub_type == '风险提示（紫）' and sub_data['strength'] < 0:
                risk_highlights.extend(sub_data['related_sentences'])

    # 构建HTML报告
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>新闻联播交易分析报告</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/css/font-awesome.min.css" rel="stylesheet">
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        primary: '#165DFF',
                        strong: '#E53E3E',     // 强利好 - 红色
                        medium: '#ED8936',    // 中等利好 - 橙色
                        weak: '#38A169',      // 弱利好 - 绿色
                        negative: '#805AD5',  // 利空 - 紫色
                        neutral: '#718096',   // 中性 - 灰色
                    }},
                    fontFamily: {{
                        sans: ['Inter', 'system-ui', 'sans-serif'],
                    }},
                }}
            }}
        }}
    </script>
    <style type="text/tailwindcss">
        @layer utilities {{
            .content-auto {{
                content-visibility: auto;
            }}
            .card-shadow {{
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            }}
            .highlighted {{
                padding: 0 2px;
                border-radius: 2px;
                font-weight: 600;
            }}
        }}
    </style>
</head>
<body class="bg-gray-50 font-sans text-gray-800">
    <!-- 报告头部 -->
    <header class="bg-white shadow-sm border-b border-gray-200">
        <div class="container mx-auto px-4 py-6">
            <div class="flex flex-col md:flex-row md:justify-between md:items-center">
                <div>
                    <h1 class="text-[clamp(1.5rem,3vw,2.5rem)] font-bold text-gray-900">
                        {date_str} 新闻联播交易分析报告
                    </h1>
                    <p class="text-gray-500 mt-1">
                        <i class="fa fa-clock-o mr-1"></i> 生成时间: {current_time}
                    </p>
                </div>
                <div class="mt-4 md:mt-0 flex items-center">
                    <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-primary">
                        <i class="fa fa-bar-chart mr-1"></i> 交易参考
                    </span>
                </div>
            </div>
        </div>
    </header>

    <main class="container mx-auto px-4 py-8">
        <!-- 核心摘要卡片 -->
        <section class="mb-10">
            <div class="bg-gradient-to-r from-primary/90 to-primary rounded-xl shadow-md overflow-hidden">
                <div class="p-6 md:p-8 text-white">
                    <h2 class="text-xl md:text-2xl font-bold mb-4 flex items-center">
                        <i class="fa fa-lightbulb-o mr-2"></i> 核心交易摘要
                    </h2>
                    <div class="grid md:grid-cols-3 gap-6">
                        <div class="bg-white/10 backdrop-blur-sm rounded-lg p-4">
                            <h3 class="text-lg font-semibold mb-2">最强利好板块</h3>
                            <div class="flex items-center flex-wrap">
                                <span class="text-2xl font-bold">{top_sector['sector'] if top_sector else '无'}</span>
                                {f'<span class="ml-3 px-2 py-1 bg-strong/20 text-white rounded-full text-sm">{top_sector["avg_strength"]}分</span>' if top_sector else ''}
                            </div>
                            <p class="mt-2 text-white/80 text-sm">
                                {f'提及次数: {top_sector["mention_count"]}次 | 关联关键词: {top_sector["keywords"]}' if top_sector else '无显著利好板块'}
                            </p>
                        </div>
                        <div class="bg-white/10 backdrop-blur-sm rounded-lg p-4">
                            <h3 class="text-lg font-semibold mb-2">政策重点</h3>
                            <p class="text-white">
                                {policy_highlights[0] if policy_highlights else '无显著政策动向'}
                            </p>
                            <p class="mt-2 text-white/80 text-sm">
                                <i class="fa fa-flag mr-1"></i> 强力度政策提及: {len(policy_highlights)}次
                            </p>
                        </div>
                        <div class="bg-white/10 backdrop-blur-sm rounded-lg p-4">
                            <h3 class="text-lg font-semibold mb-2">风险提示</h3>
                            <p class="text-white">
                                {risk_highlights[0] if risk_highlights else '无显著风险提示'}
                            </p>
                            <p class="mt-2 text-white/80 text-sm">
                                <i class="fa fa-exclamation-triangle mr-1"></i> 利空关键词: {', '.join(detailed.get('政策导向', {}).get('风险提示（紫）', {}).get('keywords_found', [])) if risk_highlights else '无'}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- 板块利好排名 -->
        <section class="mb-10">
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                <div class="p-6 border-b border-gray-100">
                    <h2 class="text-xl font-bold text-gray-900 flex items-center">
                        <i class="fa fa-trophy text-yellow-500 mr-2"></i> 板块利好强度排名
                    </h2>
                    <p class="text-gray-500 mt-1">按利好力度评分排序（1-10分，越高影响越强）</p>
                </div>
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    排名
                                </th>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    板块名称
                                </th>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    利好力度
                                </th>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    提及次数
                                </th>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    核心关键词
                                </th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            {''.join([f'''
                            <tr>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm font-medium text-gray-900">{i + 1}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm text-gray-900 font-medium">{sector['sector']}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                                        {'bg-strong/10 text-strong' if sector['avg_strength'] >= 7
    else 'bg-medium/10 text-medium' if sector['avg_strength'] >= 4
    else 'bg-weak/10 text-weak' if sector['avg_strength'] > 0
    else 'bg-negative/10 text-negative'}">
                                        {sector['avg_strength']}
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm text-gray-900">{sector['mention_count']}</div>
                                </td>
                                <td class="px-6 py-4">
                                    <div class="text-sm text-gray-500">{sector['keywords']}</div>
                                </td>
                            </tr>''' for i, sector in enumerate(sector_summary[:5])]) if sector_summary else '<tr><td colspan="5" class="px-6 py-4 text-center">无相关板块数据</td></tr>'}
                        </tbody>
                    </table>
                </div>
                <div class="px-6 py-4 bg-gray-50 border-t border-gray-200 text-sm text-gray-500">
                    显示前5名 / 共{len(sector_summary)}个相关板块
                </div>
            </div>
        </section>

        <!-- 详细分析 -->
        <section class="mb-10">
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                <div class="p-6 border-b border-gray-100">
                    <h2 class="text-xl font-bold text-gray-900 flex items-center">
                        <i class="fa fa-search-plus mr-2"></i> 详细分析
                    </h2>
                    <p class="text-gray-500 mt-1">按类别展示的关键信息提取与分析</p>
                </div>

                {''.join([f'''
                <!-- {type_name}分析 -->
                <div class="p-6 border-b border-gray-100">
                    <h3 class="text-lg font-semibold text-primary mb-4">{type_name}</h3>

                    {''.join([f'''
                    <div class="mb-6">
                        <div class="flex items-center mb-3 flex-wrap">
                            <span class="font-medium" style="color:{sub_data['color']}">{sub_type}</span>
                            <span class="ml-3 px-2 py-0.5 rounded text-xs" 
                                style="background-color:{sub_data['color']}20; color:{sub_data['color']}">
                                力度: {sub_data['strength']}分
                            </span>
                            {f'<span class="ml-3 text-sm text-gray-500">关联板块: {", ".join(sub_data["related_sectors"])}</span>' if sub_data['related_sectors'] else ''}
                        </div>
                        <div class="pl-4 border-l-2" style="border-color:{sub_data['color']}">
                            <div class="space-y-3">
                                {''.join([f'''
                                <div class="bg-gray-50 p-3 rounded-lg">
                                    <p class="text-gray-800">
                                        {highlight_keywords(sentence, {sub_type: sub_data})}
                                    </p>
                                </div>''' for sentence in sub_data['related_sentences']])}
                            </div>
                        </div>
                    </div>''' for sub_type, sub_data in sorted(type_data.items(), key=lambda x: abs(x[1]['strength']), reverse=True)])}
                </div>''' for type_name, type_data in detailed.items() if type_data])}
            </div>
        </section>

        <!-- 原始新闻内容 -->
        <section>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                <div class="p-6 border-b border-gray-100">
                    <h2 class="text-xl font-bold text-gray-900 flex items-center">
                        <i class="fa fa-file-text-o mr-2"></i> 原始新闻内容（节选）
                    </h2>
                    <p class="text-gray-500 mt-1">已高亮显示关键交易信息</p>
                </div>
                <div class="p-6 text-gray-800 leading-relaxed">
                    {highlighted_raw}
                    <div class="mt-6 text-gray-500 text-sm italic">
                        （内容有删减，仅展示与交易相关的核心部分）
                    </div>
                </div>
            </div>
        </section>
    </main>

    <footer class="bg-white border-t border-gray-200 mt-12">
        <div class="container mx-auto px-4 py-6">
            <div class="text-center text-gray-500 text-sm">
                <p>免责声明：本报告基于新闻联播内容自动分析生成，仅供参考，不构成任何投资建议。</p>
                <p class="mt-2">数据更新时间: {current_time}</p>
            </div>
        </div>
    </footer>
</body>
</html>'''

    return html


def send_email(subject, body, is_html=False):
    """发送邮件通知"""
    server = None
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = Config.SENDER_EMAIL
        msg['To'] = Config.RECEIVER_EMAIL
        msg['Subject'] = Header(subject, 'utf-8')

        if is_html:
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            # 添加纯文本版本作为备选
            plain_text = BeautifulSoup(body, 'html.parser').get_text(strip=True, separator='\n')
            msg.attach(MIMEText(plain_text, 'plain', 'utf-8'))
        else:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        server.starttls()
        server.login(Config.SENDER_EMAIL, Config.SENDER_PASSWORD)
        server.sendmail(Config.SENDER_EMAIL, Config.RECEIVER_EMAIL, msg.as_string())
        logger.info("邮件发送成功")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("邮件认证失败：请检查发件人邮箱和授权码是否正确")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP错误：{str(e)}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"邮件发送异常：{str(e)}", exc_info=True)
        return False
    finally:
        if server:
            try:
                server.quit()
            except:
                server.close()
                logger.warning("SMTP会话强制关闭")


def send_error_notification(date_str, error_msg):
    """发送错误通知邮件"""
    subject = f"【交易爬虫错误】{date_str} 新闻联播抓取失败"
    body = f"""
    日期：{date_str}
    错误信息：{error_msg}
    建议排查：
    1. 目标网站URL结构是否变更
    2. 网络是否正常（可手动访问{Config.BASE_URL}验证）
    3. 邮件配置是否正确（尤其是授权码）
    """
    return send_email(subject, body)


def save_report_to_file(html_content, date_str):
    """保存报告到本地文件"""
    report_dir = os.path.join(os.path.expanduser("~"), "news_trading_reports")
    os.makedirs(report_dir, exist_ok=True)

    file_name = f"{date_str.replace('年', '').replace('月', '').replace('日', '')}_news_trading_report.html"
    file_path = os.path.join(report_dir, file_name)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    logger.info(f"报告已保存到本地：{file_path}")
    return file_path


def run_task(days_ago=0):
    """运行主要任务流程"""
    date_str = get_date_str(days_ago)
    logger.info(f"===== 启动{date_str}新闻联播交易信息提取任务 =====")

    # 获取新闻内容
    news_content = fetch_news_content(date_str)
    if not news_content:
        send_error_notification(date_str, "未能获取新闻联播内容（抓取或解析失败）")
        return
    logger.info(f"成功获取新闻内容（长度：{len(news_content)}字符）")

    # 分析新闻内容
    logger.info("开始交易视角分析...")
    analysis_result = analyze_news_for_trading(news_content)

    # 生成HTML报告
    html_report = generate_html_report(news_content, analysis_result, date_str)

    # 保存报告到本地
    save_report_to_file(html_report, date_str)

    # 发送邮件
    top_sector = analysis_result['sector_summary'][0]['sector'] if analysis_result['sector_summary'] else '无'
    subject = f"{date_str} 新闻联播交易核心分析（利好板块：{top_sector}）"
    if send_email(subject, html_report, is_html=True):
        logger.info("===== 任务执行成功：交易分析邮件已发送 =====")
    else:
        logger.error("===== 任务执行失败：邮件发送失败 =====")


def main():
    """主函数"""
    logger.info("交易视角新闻爬虫程序启动")
    try:
        # 可以通过命令行参数指定获取几天前的新闻，默认为0（今天）
        days_ago = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0
        run_task(days_ago)
    except Exception as e:
        logger.error(f"程序异常终止：{str(e)}", exc_info=True)
        send_error_notification(get_date_str(), f"程序异常：{str(e)}")
    finally:
        logger.info("程序退出")


if __name__ == "__main__":
    main()
