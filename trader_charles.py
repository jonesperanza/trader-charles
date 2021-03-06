## MAIN DRIVER FILE
import flask
from flask import request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from flask_cors import CORS, cross_origin
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy import desc
import alpaca_trade_api as tradeapi
import pandas as pd
import pandas_datareader as pdr
import numpy as np
import datetime as dt
from datetime import datetime, tzinfo
from pytz import timezone
import bmemcached
import os
from os.path import join, dirname
from dotenv import load_dotenv
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

from algo_charles import entry_algo, exit_algo
from screener_charles import screen
from stock import Stock

api = tradeapi.REST(os.getenv('Alpaca_ID'), os.getenv('Alpaca_Secret'), "https://paper-api.alpaca.markets")
todayString = datetime.now(timezone('US/Eastern')).strftime('%Y-%m-%d')

#account management
Alpaca_Watchlist = os.environ.get('Alpaca_Watchlist')
def equity():
    return api.get_account().equity
def last_equity():
    return api.get_account().last_equity
def buying_power():
    return api.get_account().buying_power
def positions():
    return api.list_positions()
def orders():
    return api.list_orders()
def canTrade():
    if int(float(buying_power())) >= 300:
        return True
    else:
        return False

#trade management
def submitOrder(qty, stock, side):
    resp = False
    if (qty > 0):
        try:
            api.submit_order(stock, qty, side, 'market', 'day')
            print("///!! Market order of | " + str(qty) + " " + stock + " " + side.upper() + " | submitted.")
            resp = True
        except:
            print("///!! Order of | " + str(qty) + " " + stock + " " + side.upper() + " | did not go through.")
            resp = False
    else:
        print("Quantity is 0, order of | " + str(qty) + " " + stock.upper() + " " + side + " | not completed.") 
        resp = False
    return resp
def sortEntries(df):
    cols = ['Ticker', 'Desired Shares']
    data = pd.DataFrame(columns=cols, index=range(0,len(df)))
    x = 0
    amount = int(float(buying_power()))
    while (x < len(df)):
        if (amount >= 300):
            fifteen_pct = amount * .15
            possibleSharesAmount = round(fifteen_pct / df['Close'][x], None) * df['Close'][x]
            if (amount - possibleSharesAmount >= 300):
                data['Desired Shares'][x] = round(fifteen_pct / df['Close'][x], None)
                data['Ticker'][x] = df['Ticker'][x]
                amount = amount - (data['Desired Shares'][x] * df['Close'][x])
        x += 1
    
    return data.dropna()
def placeEntries(df):
    if canTrade():
        for x in range(0, len(df)):
            ticker = df['Ticker'][x]
            qty = df['Desired Shares'][x]
            submitOrder(qty, ticker, 'buy')
    else:
        print("Charles is broke. $" + buying_power)
def runEntries():
    print("}----- Charles is looking for good plays -----{")
    stocks = screen()
    print("}----- Charles is now looking for entries -----{")
    buy_stocks = entry_algo(stocks)
    print("}----- Charles is checking if he can trade -----{")
    can_buy = sortEntries(buy_stocks)
    print("}----- Charles is placing buy orders -----{")
    placeEntries(can_buy)
def sortExits(df):
    stocks = []
    for position in df:
        stock = Stock(position.symbol)
        stock.getTechnicals()
        stock.exchange = position.exchange
        stock.marketvalue = float(position.market_value)
        stock.cost_basis = float(position.cost_basis)
        stock.entry_price = float(position.avg_entry_price)
        stock.shares = int(float(position.qty))
        stock.pl = float(position.unrealized_pl)
        stock.plpc = float(position.unrealized_plpc)
        stocks.append(stock)
    sell_stocks = exit_algo(stocks)
    return sell_stocks
def placeExits(df):
    for x in df:
        submitOrder(x.shares, x.ticker, 'sell')
        exitStock = Trades(date= todayString, ticker= x.ticker, exchange= x.exchange, close= x.close, shares= x.shares, entry_price= x.entry_price, cost_basis= x.cost_basis, marketvalue= x.marketvalue, pl= x.pl, plpc= x.plpc)
        db.session.add(exitStock)
    db.session.commit()
def runExits():
    print("}----- Charles is checking his positions -----{")
    sell_stocks = sortExits(positions())
    print("}----- Charles is placing sell orders -----{")
    if (len(sell_stocks) > 0):
        placeExits(sell_stocks)


# API
Postgres_URI = os.environ.get('Postgres_URI')
app = flask.Flask(__name__)
cors = CORS(app)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SQLALCHEMY_DATABASE_URI"] = Postgres_URI
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# DB
class Trades(db.Model):
    __tablename__ = 'trades'
    date = db.Column(db.String, primary_key=True, nullable=False)
    ticker = db.Column(db.String, primary_key=True, nullable=False)
    exchange = db.Column(db.String)
    close = db.Column(db.Float)
    shares = db.Column(db.Integer)
    entry_price = db.Column(db.Float)
    cost_basis = db.Column(db.Float)
    marketvalue = db.Column(db.Float)
    pl = db.Column(db.Float)
    plpc = db.Column(db.Float, nullable=True)
    @property
    def serialize(self):
       """Return object data in easily serializable format"""
       return {
           'date'           : self.date,
           'ticker'         : self.ticker,
           'exchange'       : self.exchange,
           'close'          : self.close,
           'shares'         : self.shares,
           'entry_price'    : self.entry_price,
           'cost_basis'     : self.cost_basis,
           'marketvalue'    : self.marketvalue,
           'pl'             : self.pl,
           'plpc'           : self.plpc
       }

# CACHE
servers = os.environ.get('MEMCACHIER_SERVERS', '').split(',')
user = os.environ.get('MEMCACHIER_USERNAME', '')
passw = os.environ.get('MEMCACHIER_PASSWORD', '')
mc = bmemcached.Client(servers, username=user, password=passw)
mc.enable_retry_delay(True)

def calc_profits_exchange(arr):
    hash_exc = dict()
    for i in arr:
        if i.exchange in hash_exc:
            hash_exc[i.exchange] += i.pl
        else:
            hash_exc[i.exchange] = i.pl
    return hash_exc
def load_history():
    history = [i.serialize for i in Trades.query.all()]
    mc.set("history", history)
    return history
def load_best():
    best = [i.serialize for i in Trades.query.order_by(desc(Trades.pl)).limit(5)]
    mc.set("best", best)
    return best
def load_worst():
    worst = [i.serialize for i in Trades.query.order_by(Trades.pl).limit(5)]
    mc.set("worst", worst)
    return worst
def load_record():
    wins = Trades.query.filter(Trades.pl > 0).count()
    losses = Trades.query.filter(Trades.pl < 0).count()
    record = {'wins' : wins,
              'losses' : losses,
              'win_percentage' : round((float)(wins/(wins+losses)), 2)}
    mc.set("record", record)
    return record
def load_exchange():
    hash_exc = calc_profits_exchange(Trades.query.all())
    keys = list(hash_exc.keys())
    vals = list(hash_exc.values())
    exchange = {'exchanges' : keys,
                'profits'   : vals}
    mc.set("exchange", exchange)
    return exchange
def load_cache():
    load_history()
    load_best()
    load_worst()
    load_record()
    load_exchange()
def market_opens_tomorrow():
    openingTime = api.get_clock().next_open.replace(tzinfo=dt.timezone.utc).timestamp()
    currTime = api.get_clock().timestamp.replace(tzinfo=dt.timezone.utc).timestamp()
    timeToOpen = int((openingTime - currTime) / 60)
    if (timeToOpen < 1200):
        return True
    else:
        return False

def login():
    if (market_opens_tomorrow()):
        runExits()
        runEntries()
        load_cache()
    else:
        print("Charles is taking the day off until market opens.")

def init_app():
    db.create_all()
    load_cache()
    
## ENDPOINTS
@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404
@app.route('/', methods=['GET'])
def home():
    return '''<h1>This is Trader Charles' API</h1>
    <p>A prototype API for Charles' paper trading account.</p> 
    <p><strong>/trades</strong> - returns all trades in database</p>
    <p><strong>/trades/best</strong> - returns the 5 most profitable trades in database</p>
    <p><strong>/trades/worst</strong> - returns the 5 least profitable trades in database</p>
    <p><strong>/trades/record</strong> - returns charles' trading record</p>'''


@app.route('/trades', methods=['GET'])
@cross_origin()
def trades_history():
    history = mc.get("history")
    if history is None:
        history = load_history()
    return jsonify(history)
@app.route('/trades/best', methods=['GET'])
@cross_origin()
def trades_best():
    best = mc.get("best")
    if best is None:
        best = load_best()
    return jsonify(best)
@app.route('/trades/worst', methods=['GET'])
@cross_origin()
def trades_worst():
    worst = mc.get("worst")
    if worst is None:
        worst = load_worst()
    return jsonify(worst)
@app.route('/trades/record', methods=['GET'])
@cross_origin()
def trades_record():
    record = mc.get("record")
    if record is None:
        record = load_record()
    return jsonify(record)
@app.route('/trades/byexchange', methods=['GET'])
@cross_origin()
def profit_by_exchange():
    exchange = mc.get("exchange")
    if exchange is None:
        exchange = load_exchange()
    return jsonify(exchange)

if __name__ == "__main__":
    init_app()
    app.run()
