import requests
from datetime import datetime

def get_stock_data(stock_code):
    # 将 stock_code 转换为 symbol 格式 (公司代码+交易所简称)
    if stock_code.endswith('.SZ'):
        symbol = stock_code.replace('.SZ', 'sz')
    elif stock_code.endswith('.SH'):
        symbol = stock_code.replace('.SH', 'sh')
    else:
        return None

    url = f'https://flash-api.xuangubao.cn/api/pool/detail?pool_name=limit_up'
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if 'data' in data:
            for stock in data['data']:
                if 'symbol' in stock and stock['symbol'] == symbol:
                    return {
                        'close_price': float(stock.get('price')),
                        'daily_change': float(stock.get('change_percent', 0).strip('%')) / 100
                    }
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching stock data: {e}")
        return None