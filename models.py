from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class StockTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)  # 交易日期
    stock_code = db.Column(db.String(10), nullable=False)  # 公司代码
    stock_name = db.Column(db.String(50), nullable=False)  # 公司简称
    buy_price = db.Column(db.Float, nullable=True)  # 买入价格
    sell_price = db.Column(db.Float, nullable=True)  # 卖出价格
    daily_change = db.Column(db.Float, nullable=True)  # 当日涨幅
    close_price = db.Column(db.Float, nullable=True)  # 收盘价
    daily_profit = db.Column(db.Float, nullable=True)  # 当日收益
    final_profit = db.Column(db.Float, nullable=True)  # 最终收益
    remarks = db.Column(db.Text, nullable=True)  # 备注
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StockPriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(10), nullable=False)  # 公司代码
    date = db.Column(db.Date, nullable=False)  # 日期
    close_price = db.Column(db.Float, nullable=False)  # 收盘价
    daily_change = db.Column(db.Float, nullable=False)  # 当日涨幅