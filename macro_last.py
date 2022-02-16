import ccxt
import time
import threading
import talib
import numpy as np
from binance import ThreadedWebsocketManager
from binance.client import Client
import telegram
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler
from functools import partial

#=================================예외처리 목록=============================================================
class OrderCancel(Exception):    # 구매 안될 시 오류
    def __init__(self):
        super().__init__('주문이 체결되지 않음')
        
class ThreadCancel(Exception):    # 스레드 죽이기
    def __init__(self):
        super().__init__('스레드 종료')
#=================================예외처리 목록 끝=============================================================


#=================================기본 함수 목록=============================================================
def trend_flow(arr):
    count = 0
    for i in arr:
        count += i
    if count > 1:
        return 1
    elif count < -1:
        return -1
    else:
        return 0

def arr_print(arr,title = ""):
    msg = ""
    if len(title) !=0:
        msg = "===="+title+"===="
    for sub in arr:
        msg = msg + "\n"
        count = 0
        for j in sub:
            if count % 2 == 0 and len(sub)-1 != count:
                msg = msg + str(j) + " = "
            elif len(sub)-1 != count:
                msg = msg + str(j) + ", "
            else:
                msg = msg + str(j)
            count += 1
    return msg
            

def decimal(num):
    if num >= 10:
        return round(num) - 1
    elif num >= 1:
        return round(num,1)
    elif num >= 0.1:
        return round(num,2)
    elif num >= 0.01:
        return round(num,3) 
    elif num >= 0.001:
        return round(num,3)
    else:
        return round(num,4)
        
#매수 기준 함수
def rsiCheck(ticker):
    lev = 1
    binance = ccxt.binance(config={
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future'
        }
    })
    time.sleep(0.7)
    try:
        ohlcv = binance.fetch_ohlcv(ticker)
        df = [row[4] for row in ohlcv]
        #fastk, fastd = talib.STOCHRSI(np.asarray(df), timeperiod=5, fastk_period=3, fastd_period=3, fastd_matype=0,)
        rsi = talib.RSI(np.asarray(df),7)
        rsi2 = talib.RSI(np.asarray(df),14)
        ema1 = talib.EMA(np.asarray(df),5)
        ema2 = talib.EMA(np.asarray(df),10)
        ema3 = talib.EMA(np.asarray(df),20)
        ema4 = talib.EMA(np.asarray(df),30)
        #diff1 = fastk[-1] - fastd[-1]
        
        if ema1[-1] >= ema2[-1] and ema2[-1] >= ema3[-1] and ema3[-1] >= ema4[-1]:
            if rsi[-1] >= 78 and rsi2[-1] >= 78:
                print('rsi체크',ticker,'rsi 78이상')
                return -1, lev
            else:
                for i in range(2,9):
                    if not (ema1[-i] >= ema2[-i] and ema2[-i] >= ema3[-i] and ema3[-i] >= ema4[-i]):
                        break
                    if i == 6:
                        if ema1[-1] -ema3[-1] >= ema1[-2] -ema3[-2] and ema1[-2] -ema3[-2] <= ema1[-3] -ema3[-3] and ema1[-2] -ema3[-2] <= ema1[-4] -ema3[-4]:
                            if rsi[-1] < 45:
                                print('rsi체크',ticker,'rsi 45미만')
                                return 1, lev
                    if i == 8:
                        if ema1[-1] -ema3[-1] >= ema1[-3] -ema3[-3] and ema1[-3] -ema3[-3] >= ema1[-5] -ema3[-5] and ema1[-5] -ema3[-5] >= ema1[-8] -ema3[-8]:
                            if rsi[-1] >= 72:
                                print('rsi체크',ticker,'rsi 72이상')
                                return -1, lev
            
        if ema1[-1] <= ema2[-1] and ema2[-1] <= ema3[-1] and ema3[-1] <= ema4[-1]:
            if rsi[-1] <= 22 and rsi[-1] <= 22:
                print('rsi체크',ticker,'rsi 22이하')
                return 1, lev
            else:
                for i in range(2,9):
                    if not (ema1[-i] <= ema2[-i] and ema2[-i] <= ema3[-i] and ema3[-i] <= ema4[-i]):
                        break
                    if i == 6:
                        if ema1[-1] - ema3[-1] <= ema1[-2] -ema3[-2] and ema1[-2] -ema3[-2] >= ema1[-3] -ema3[-3] and ema1[-2] -ema3[-2] >= ema1[-4] -ema3[-4]:
                            if rsi[-1] > 55:
                                print('rsi체크',ticker,'rsi 55초과')
                                return -1, lev
                    if i == 8:
                        if ema1[-1] -ema3[-1] <= ema1[-3] -ema3[-3] and ema1[-3] -ema3[-3] <= ema1[-5] -ema3[-5] and ema1[-5] -ema3[-5] <= ema1[-8] -ema3[-8]:
                            if rsi[-1] <= 28:
                                print('rsi체크',ticker,'rsi 28이하')
                                return 1, lev
        print('rsi체크',ticker,'실패')
        return 0, lev
            
    except Exception as e:
        print('너무 많은 요청',e)
        time.sleep(5)
        return 0,lev
#=================================기본 함수 목록 끝=============================================================
    
#=================================Account클래스(Coin서브클래스)=============================================================
class Account:
    def __init__(self,client,profile,ticker_list,botToken,chatId):
        self.initial_balance = 0
        self.activate = 0
        self.web = 0
        self.my = client
        self.flow = [0,0,0,0,0,0]
        self.binance = profile
        self.all = ticker_list
        self.list = dict()  #{ticker:[object,twm,socket],}
        self.temp = set()
        self.botToken = botToken
        self.chatId = chatId
        self.bot = telegram.Bot(token=botToken)
        self.updater = Updater(token=botToken, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.dispatcher.add_handler(CommandHandler('start',self.onoff_switch))
        self.dispatcher.add_handler(CommandHandler('webmsg',self.webmsg_switch))
        self.dispatcher.add_handler(CommandHandler('bring',self.print_balance))
        self.dispatcher.add_handler(CommandHandler('end',self.onoff_switch))
        self.dispatcher.add_handler(CommandHandler('self',self.manual_trans,pass_args=True))
        self.updater.start_polling()
        
    class Coin:
        def __init__(self,ticker,price,amount,kind,lev,timestamp):
            self.price_change = False
            self.kind = kind
            self.ticker = ticker
            self.lev = lev
            self.price = price
            self.origin_price = price
            self.amount = amount
            self.precision = self.price
            self.time = timestamp
            self.p_price = self.price+0.003*self.price/self.lev if kind == 1 else (self.price+0.0035*self.price/self.lev)
            self.n_price = self.price-0.003*self.price/self.lev if kind == -1 else (self.price-0.0035*self.price/self.lev)
            self.warn_price = self.origin_price-0.0018*self.origin_price/self.lev if kind == 1 else (self.origin_price+0.0018*self.origin_price/self.lev)
            self.defense = 0
            self.exist = True
            self.manual = False
    #=============================클래스 제어==========================    
    def onoff_switch(self,update, context):
        if self.activate == 0:
            self.activate = 1
        else:
            self.activate = 0
        
    def webmsg_switch(self,update, context):
        if self.web == 0:
            self.web = 1
        else:
            self.web = 0    
    
    def manual_trans(self,update,context):
        for arg in context.args:
            try:
                ticker = arg +'USDT'
                self.list[ticker][0].manual = True
                print('수동조정 성공',arg)
            except:
                self.bot_print('수동조정 실패: '+arg)
        
            
    def start(self):
        #=============================이미있는 자산 체크==========================
        custom_keyboard = [['/bring', '/end'],  ['/start', '/webmsg']]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        self.bot.send_message(chat_id=self.chatId, text="매크로가 시작되었습니다.",  reply_markup=reply_markup)
        balance = self.binance.fetch_balance()
        self.initial_balance = float(balance['info']['totalWalletBalance'])
        positions = balance['info']['positions']
        count = 0
        for position in positions:
            if float(position["positionAmt"]) != 0:
                count += 1
                twm = ThreadedWebsocketManager()
                twm.start()
                self.addCoin(position['symbol'],twm)
        #========================================================================
        
        
        #============================초기 n개 맞춰주기===========================
        try:
            while count < 6:
                print('initial setting')
                twm = ThreadedWebsocketManager()
                twm.start()
                self.findCoin(twm)   
                count += 1
        except Exception as e:
            print(e)
            self.bot_print('검색중단')
            
        while self.activate == 1:
            balance = self.binance.fetch_balance()
            total_money = float(balance['info']['totalWalletBalance'])
            self.bot_print('실행중 -> 잔고: '+str(round(total_money,2))+'수익률: '+str(round((total_money -self.initial_balance)/self.initial_balance*100,3)))
            time.sleep(15)
        self.bot_print('=====매크로종료 대기중======')

        for ob in self.list:
            self.list[ob][1].join()
            print('조인')
        self.list = dict()
        self.temp = set()
        self.bot_print('매크로를 종료합니다.')
        print('finish')
        #========================================================================
        
        

        
        
    def bot_print(self,msg):
        self.bot.send_message(chat_id=self.chatId, text=msg)
    
    def print_balance(self,update, context):
        try:
            balance = self.binance.fetch_balance()
            positions = balance['info']['positions']
            total_wallet = balance['info']['totalWalletBalance']
            total_coin = [['전액',total_wallet]]
            for position in positions:
                if float(position["positionAmt"]) != 0:
                    ticker = position['symbol']
                    price = self.list[ticker][0].origin_price*self.list[ticker][0].amount/self.list[ticker][0].lev
                    profit = round(float(position['unrealizedProfit'])/price*100,3)
                    total_coin.append(['코인',ticker,'투자금',round(price,4),'손익률',profit])
            self.bot_print(arr_print(total_coin,"전체 계좌 조회"))
            
        except Exception as e:
            print('전체계좌 출력실패',e)
            self.bot_print('전체계좌 출력실패')
                
                
    def precision(self,ticker,price):
        return round(price,self.all[ticker])
    
    def addCoin(self,ticker,twm):
        balance = self.binance.fetch_balance()
        positions = balance['info']['positions']
        for position in positions:
            if position["symbol"] == ticker:
                lev = int(position['leverage'])
                price = float(position['entryPrice'])
                amount = float(position['positionAmt'])
                timestamp = int(position['updateTime'])
                if amount > 0:
                    kind = 1
                else:
                    amount = -amount
                    kind = -1 
        print('코인추가',ticker,kind,(price+0.002*price/lev) if kind == 1 else (price-0.002*price/lev))
        socket = twm.start_symbol_ticker_futures_socket(callback=partial(self.checkCoin,sym = ticker,twm = twm), symbol=ticker)
        if not socket in twm._socket_running:
            socket = twm.start_symbol_ticker_futures_socket(callback=partial(self.checkCoin,sym = ticker,twm = twm), symbol=ticker)
        elif not twm._socket_running[socket]:
            socket = twm.start_symbol_ticker_futures_socket(callback=partial(self.checkCoin,sym = ticker,twm = twm), symbol=ticker)
        self.list[ticker] = [self.Coin(ticker,price,amount,kind,lev,timestamp), twm, socket]
        self.temp.discard(ticker)
        
    def removeCoin(self,ticker):
        print('코인삭제',ticker)
        twm = self.list[ticker][1]
        socket = self.list[ticker][2]
        del(self.list[ticker])
        twm.stop_socket(socket)
        
    
    def buyCoin(self,ticker,kind,lev):
        self.my.futures_change_leverage(symbol=ticker, leverage=lev)
        balance = self.binance.fetch_balance()
        size = float(balance['info']['totalWalletBalance'])/6*0.8
        price = float(self.my.futures_symbol_ticker(symbol=ticker)['price'])
        amount = size/price*lev
        print('구매주문예정',ticker,kind,'가격=',price,'갯수=',decimal(amount))
        order = self.my.futures_create_order(
            symbol=ticker,
            type="LIMIT",
            timeInForce='GTC',
            price=self.precision(ticker,price*1.0002) if kind == 1 else self.precision(ticker,price*0.9998),
            side = 'BUY' if kind == 1 else 'SELL',
            quantity = decimal(amount)
        )
        print('구매주문',ticker,kind)
        time.sleep(3)
        order_check = self.my.futures_get_order(
            symbol=ticker,
            orderId=order['orderId'])
        if order_check['status'] == 'NEW':
            self.my.futures_cancel_order(
                symbol=ticker,
                orderId=order['orderId'])
            raise OrderCancel
        else:
            print('주문 체결',ticker)
            self.bot_print('주문체결:'+ticker+', 종류:'+str(kind)+',전체잔고: '+balance['info']['totalWalletBalance'])
        
        
        
    def findCoin(self,twm):
        stop = True
        print(self.list.keys())
        print(self.temp)
        while stop:
            for ticker in self.all:
                if self.activate == 0:
                    raise ThreadCancel
                if ticker not in self.list and ticker not in self.temp:
                    self.temp.add(ticker)
                    kind,lev = rsiCheck(ticker)
                    self.flow.append(kind)
                    del self.flow[0]
                    if kind:
                        try:
                            self.buyCoin(ticker,kind,lev)
                        except Exception as e:
                            print('구매실패',e)
                            self.bot_print('구매실패: '+ticker)
                            self.temp.discard(ticker)
                            continue
                        self.addCoin(ticker,twm)
                        stop = False
                        break
                    self.temp.discard(ticker)
                    
    def sellCoin(self,coin,lastprice):
        order = self.my.futures_create_order(
            symbol=coin.ticker,
            type="LIMIT", #시장가로 할 지 아니면 주문가로 할 지 고민
            timeInForce='GTC',
            price=self.precision(coin.ticker,lastprice*0.9997) if coin.kind == 1 else self.precision(coin.ticker,lastprice*1.0003),
            side = 'SELL' if coin.kind == 1 else 'BUY',
            quantity = coin.amount
        )
        print('판매주문',coin.ticker,coin.kind)
        
        kind, lev = rsiCheck(coin.ticker)
        if kind*coin.kind >= 0:
            time.sleep(7)
        order_check = self.my.futures_get_order(
            symbol=coin.ticker,
            orderId=order['orderId'])
        print(order_check)
        if order_check['status'] == 'NEW':
            try:
                self.my.futures_cancel_order(
                    symbol=coin.ticker,
                    orderId=order['orderId'])
                
                self.my.futures_create_order(
                    symbol=coin.ticker,
                    type="MARKET", #시장가로 할 지 아니면 주문가로 할 지 고민
                    side = 'SELL' if coin.kind == 1 else 'BUY',
                    quantity = coin.amount
                )
                print('시장가 판매',coin.ticker)
                self.bot_print(arr_print([['시장가 판매완료',coin.ticker]]))
            except Exception as e:
                print('이미 판매됨',coin.ticker,e)
                
        elif order_check['status'] == 'FILLED':
            print('지정가 판매',coin.ticker)
            self.bot_print(arr_print([['지정가 판매완료',coin.ticker]]))
        else:
            try:
                order_check = self.my.futures_get_order(
                    symbol=coin.ticker,
                    orderId=order['orderId'])
                self.my.futures_cancel_order(
                    symbol=coin.ticker,
                    orderId=order['orderId'])
                order_decimal = len(order_check['executedQty']) - order_check['executedQty'].find('.') - 1
                amount = coin.amount - float(order_check['executedQty'])
                
                self.my.futures_create_order(
                    symbol=coin.ticker,
                    type="MARKET", #시장가로 할 지 아니면 주문가로 할 지 고민
                    side = 'SELL' if coin.kind == 1 else 'BUY',
                    quantity = round(amount,order_decimal)
                )
            except Exception as e:
                self.bot_print(arr_print([['코인 수동 판매 요청',coin.ticker]]))
                print('코인 수동 판매 요청',coin.ticker,e)
        coin.exist = False
        
    def defendFunc(self,ob,price):
        if ob.defense < 8:
            if ob.kind == 1:
                if price >= ob.price+(0.0015+ ob.defense*0.0002)*ob.price/ob.lev:
                    ob.n_price = ob.price+(ob.defense*0.0003)*ob.price/ob.lev
                    ob.defense += 1
                    self.bot_print(arr_print([['가격방어선',ob.ticker,'퍼센트',ob.defense*0.03]]))
                    print('가격방어',ob.ticker)
            elif ob.kind == -11:
                if price <= ob.price-(0.0015+ ob.defense*0.0002)*ob.price/ob.lev:
                    ob.p_price = ob.price-(ob.defense*0.0003)*ob.price/ob.lev
                    ob.defense += 1
                    self.bot_print(arr_print([['가격방어선',ob.ticker,'퍼센트',ob.defense*0.03]]))
                    print('가격방어',ob.ticker)
                    
    #twm에서 callback하는 함수 
    def checkCoin(self,msg,sym=None,twm=None):
        try:
            ticker = msg['data']['s']
            ob = self.list[ticker][0]
            if not ob.exist:
                twm.stop_socket(sym)
        except Exception as e:
            print('소켓데이터 오류',e,msg)
            self.bot_print('소켓데이터 오류')
            twm.start_symbol_ticker_futures_socket(callback=partial(self.checkCoin, sym = sym,twm = twm), symbol=sym)
            return None
        if self.web == 1:
            sell_price = ob.p_price if ob.kind == 1 else ob.n_price
            print(arr_print([[ticker,ob.kind,'현재흐름',self.flow[-1],'진입',ob.time,'판매퍼센트',(sell_price-ob.origin_price)/ob.origin_price*ob.lev]],'웹소켓 콜백'))
            self.bot_print(arr_print([[ticker,ob.kind,'현재흐름',self.flow[-1],'진입',ob.time,'판매퍼센트',(sell_price-ob.origin_price)/ob.origin_price*ob.lev]],'웹소켓 콜백'))
            time.sleep(0.5)
        if ob.manual:
            if ob.kind == 1:
                ob.n_price = float(msg['data']['a'])
            elif ob.kind == -1:
                ob.p_price = float(msg['data']['b'])
        if ob.kind == 1:
            if trend_flow(self.flow) == -1 and not ob.price_change:
                if time.time() - ob.time > 300:
                    print('가격 조정',ob.ticker)
                    ob.price_change = True
                    ob.p_price = ob.price+0.0006*ob.price/ob.lev
                    ob.n_price = ob.price - 0.002*ob.price/ob.lev
            self.defendFunc(ob,float(msg['data']['a']))
            if ob.p_price < float(msg['data']['a']):
                ob.p_price = float(msg['data']['a'])
                ob.n_price = ob.price + (ob.p_price - ob.price)*0.85
                print('상한가진입',ticker,ob.kind,'최고가=', ob.p_price,'판매가',ob.n_price)
            elif ob.n_price >= float(msg['data']['a']):
                self.bot_print(arr_print([[ticker,ob.kind,'퍼센트',round((ob.n_price-ob.origin_price)/ob.origin_price,4)*100,'이익실현' if ob.n_price > ob.origin_price else '손해판매']],'매도시작'))
                print('매도시작',ticker,ob.kind,'퍼센트=',round((ob.n_price-ob.origin_price)/ob.origin_price,4)*100,'%','이익실현' if ob.n_price > ob.origin_price else '손해판매')
                self.sellCoin(ob,float(msg['data']['a']))
                if self.activate == 0: 
                    self.list[ticker][1].stop()
                    print('진행종료')
                    return None
                try:
                    self.findCoin(self.list[ticker][1])
                except Exception as e:
                    self.bot_print('검색중단')
                    print(e)
                    self.list[ticker][1].stop()
                    return None
                self.removeCoin(ticker)
            elif ob.warn_price >= float(msg['data']['a']):
                ob.warn_price = ob.warn_price-0.0005*ob.origin_price/ob.lev
                ob.price = float(msg['data']['a'])
                percent = abs(round((ob.price-ob.origin_price)/ob.origin_price,3))
                self.bot_print(arr_print([[ticker,ob.kind,'구매가', ob.origin_price,'현재가',ob.price,'퍼센트',percent]],"경고가 진입"))
                print('경고가진입',ticker,ob.kind,'구매가', ob.origin_price,'현재가',ob.price,'퍼센트',percent)
                ob.p_price = ob.price+(0.001+percent*0.35)*ob.price/ob.lev
                
        elif ob.kind == -1:
            if trend_flow(self.flow) == 1 and not ob.price_change:
                if time.time() - ob.time > 300:
                    print('가격 조정',ob.ticker)
                    ob.price_change = True
                    ob.n_price = ob.origin_price-0.0006*ob.origin_price/ob.lev
                    ob.p_price = ob.origin_price + 0.002*ob.origin_price/ob.lev
            self.defendFunc(ob,float(msg['data']['a']))
            if ob.n_price > float(msg['data']['b']):
                ob.n_price = float(msg['data']['b'])
                ob.p_price = ob.price - (ob.price - ob.n_price)*0.85
                print('하한가진입',ticker,ob.kind,'최저가=', ob.n_price,'판매가',ob.p_price)
            elif ob.p_price <= float(msg['data']['b']):
                self.bot_print(arr_print([[ticker,ob.kind,'퍼센트',round((ob.origin_price-ob.p_price)/ob.origin_price,4)*100,'이익실현' if ob.p_price < ob.origin_price else '손해판매']],'매도시작'))
                print('매도시작',ticker,ob.kind,'퍼센트=',round((ob.origin_price-ob.p_price)/ob.origin_price,4)*100,'%','이익실현' if ob.p_price < ob.origin_price else '손해판매')
                self.sellCoin(ob,float(msg['data']['b']))
                if self.activate == 0: 
                    self.list[ticker][1].stop()
                    print('진행종료')
                    return None
                try:
                    self.findCoin(self.list[ticker][1])
                except Exception as e:
                    self.bot_print('검색종료')
                    print(e)
                    self.list[ticker][1].stop()
                    return None
                self.removeCoin(ticker)
            elif ob.warn_price <= float(msg['data']['b']):
                ob.warn_price = ob.warn_price+0.0005*ob.origin_price/ob.lev
                ob.price = float(msg['data']['b'])
                percent = abs(round((ob.price-ob.origin_price)/ob.origin_price,3))
                self.bot_print(arr_print([[ticker,ob.kind,'구매가', ob.origin_price,'현재가',ob.price,'퍼센트',percent]],'경고가 진입'))
                print('경고가진입',ticker,ob.kind,'구매가=', ob.origin_price,'현재가',ob.price,'퍼센트',percent)  
                ob.n_price = ob.price-(0.001+percent*0.35)*ob.price/ob.lev
#=================================Account클래스(Coin서브클래스) 끝=============================================================


def main():
    #==========================기초 세팅=============================
    
    with open("./api.txt") as f:
            lines = f.readlines()
            apiKey = lines[0].strip()
            secret  = lines[1].strip()
            botToken  = lines[2].strip()
            chatId  = lines[3].strip()
            
    profile = ccxt.binance(config={
                                    'apiKey': apiKey, 
                                    'secret': secret,
                                    'enableRateLimit': True,
                                    'options': {
                                        'defaultType': 'future'
                                    }
                                })
    client = Client(api_key=apiKey, api_secret=secret)
    ticker_list = {'FTMUSDT':4, 'EOSUSDT':3, 'DOTUSDT':3, 'DOGEUSDT':5,
                   'BCHUSDT':2, 'XRPUSDT':4, 'ADAUSDT':4, 'ATOMUSDT':3, 'TRXUSDT':5,
                   'BNBUSDT':2, 'LTCUSDT':2, 'ETCUSDT':3}
     #[SOLUSDT':2,  'LUNAUSDT':3,'BTCUSDT':2, 'ETHUSDT':2,'AVAXUSDT':2,]

    account = Account(client,profile,ticker_list,botToken,chatId)
    while True:
        time.sleep(3)
        if account.activate == 1:
            account.start()


if __name__ == "__main__":
    
	main()