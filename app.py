from flask import Flask, render_template, request, redirect, url_for, jsonify
from models import db, StockTransaction, StockPriceHistory
from utils import get_stock_data
from datetime import datetime

app = Flask(__name__)

# 配置数据库
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stock_trading.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# 创建数据库表
with app.app_context():
    db.create_all()

# 渲染首页
@app.route('/')
def index():
    transactions = StockTransaction.query.all()
    return render_template('index.html', transactions=transactions)

# 处理股票交易记录的添加
@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    # 获取表单数据
    date_str = request.form.get('date')
    stock_code = request.form.get('stock_code')
    stock_name = request.form.get('stock_name')
    buy_price = request.form.get('buy_price')
    sell_price = request.form.get('sell_price')
    daily_profit = request.form.get('daily_profit')
    final_profit = request.form.get('final_profit')
    remarks = request.form.get('remarks')

    # 将日期字符串转换为 datetime 对象
    date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # 获取当日涨幅和收盘价
    stock_data = get_stock_data(stock_code)
    if stock_data:
        close_price = stock_data['close_price']
        daily_change = stock_data['daily_change']
    else:
        close_price = None
        daily_change = None

    # 计算当日收益和最终收益
    if buy_price and close_price:
        daily_profit = float(close_price) - float(buy_price)
    if sell_price and buy_price:
        final_profit = float(sell_price) - float(buy_price)

    # 创建新的交易记录
    new_transaction = StockTransaction(
        date=date,
        stock_code=stock_code,
        stock_name=stock_name,
        buy_price=buy_price,
        sell_price=sell_price,
        daily_change=daily_change,
        close_price=close_price,
        daily_profit=daily_profit,
        final_profit=final_profit,
        remarks=remarks
    )

    # 保存到数据库
    db.session.add(new_transaction)
    db.session.commit()

    return redirect(url_for('index'))

# 删除交易记录
@app.route('/delete_transaction/<int:id>', methods=['POST'])
def delete_transaction(id):
    transaction = StockTransaction.query.get_or_404(id)
    db.session.delete(transaction)
    db.session.commit()
    return redirect(url_for('index'))

# 获取股票数据的 API
@app.route('/api/get_stock_data', methods=['GET'])
def api_get_stock_data():
    stock_code = request.args.get('stock_code')
    stock_data = get_stock_data(stock_code)
    if stock_data:
        return jsonify(stock_data)
    else:
        return jsonify({'error': 'Stock data not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)