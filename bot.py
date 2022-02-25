#!/usr/bin/env python
# pylint: disable=C0116,W0613

import logging, requests, _thread, time, os, sys, signal, json, dateparser

from datetime import datetime
import pytz

from requests.exceptions import HTTPError
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

node_list = []
test_node_list = []
cache_lu = ""

try:
    with open("config.json") as json_data_file:
        settings = json.load(json_data_file)
    TOKENS = settings['TOKENS']
    CMC_PRO_API_KEY = TOKENS['coinmarketcap']
    COTIdiscussion_bot_TOKEN = TOKENS['COTIdiscussion_bot']
    coticomm_bot_TOKEN = TOKENS['coticomm_bot']
    crypto_sharktank_bot_TOKEN = TOKENS['crypto_sharktank_bot']
    
    core_admins = settings['core_admins']
except:
    print("Error reading config file. Exiting..")
    sys.exit()

def cacheNodes():
    print("caching nodes...")
    global node_list, test_node_list, cache_lu
    while 1:
        try:
            URLs = [
                "https://mainnet-nodemanager.coti.io/wallet/nodes",
                "https://testnet-nodemanager.coti.io/wallet/nodes"
            ]
            for index in range(len(URLs)):
                URL = URLs[index]
                response = requests.get(URL)
                response.raise_for_status()
                # access JSOn content
                jsonResponse = response.json()
                status = jsonResponse['status']
                
                if status.lower() == "success":
                    FullNodes = jsonResponse['nodes']['FullNodes']
                    #print(FullNodes)
                    if index == 0:
                        node_list.clear()
                        for node in FullNodes:
                            node_list.append(node['url'].replace('https://', ''))
                    else:
                        test_node_list.clear()
                        for node in FullNodes:
                            test_node_list.append(node['url'].replace('https://', ''))
                else:
                    pass
                time.sleep(1)
            cache_lu = datetime.now(tz=pytz.UTC).strftime("%H:%M:%S")
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as err:
            print(f'Other error occurred: {err}')
            
        time.sleep(300)

try:
   _thread.start_new_thread( cacheNodes, () )
except:
   print("Error: unable to start cacheNodes thread")


def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_markdown_v2(
        fr'Hi {user.mention_markdown_v2()}\!',
        reply_markup=ForceReply(selective=True),
    )


def coti_price():
    URL = "https://treasury-app.coti.io/get-coti-price"
    res = requests.get(URL)
    status = res.status_code
    json_res = res.json()
    if status == 200 and json_res["price"]:
        return float(json_res["price"])
    else:
        return


def ep_cmd(update: Update, context: CallbackContext) -> None:
    def coti_tx(tx_hash):
        URL = "https://mainnet-fullnode1.coti.io/transaction"
        json_data = {"transactionHash": tx_hash}
        req = requests.post(URL, json = json_data)
        res_data = req.json()
        res_status = req.status_code
        
        if res_status == 200 and res_data['status'] == "Success":
            timestamp = res_data['transactionData']["createTime"]
            amount = res_data['transactionData']["amount"]
            #timestamp = (timestamp)
            return(timestamp,amount)
        else:
            return(False)

    def cex_data(timestamp):
        timeend = float(timestamp) + 60
        
        btimestamp = int(float(timestamp) * 1000.0)
        btimeend = int(float(timeend) * 1000.0)
        
        ktimestamp = round(float(timestamp))
        ktimeend = round(float(timestamp))
        
        URLs = {
            "binance": f"https://api1.binance.com/api/v3/klines?symbol=COTIUSDT&interval=1m&startTime={btimestamp}&endTime={btimeend}",
            "kucoin": f"https://api.kucoin.com/api/v1/market/candles?type=1min&symbol=COTI-USDT&startAt={ktimestamp}&endAt={ktimeend}"
        }
        
        for endpoint in URLs:
            URL = URLs[endpoint]
            response = requests.get(URL)
            jsonResponse = response.json()
            status = response.status_code
            
            if endpoint == 'binance':
                if  status == 200:
                    binance_price = round(float(jsonResponse[0][4]),8)
                else:
                    binance_price = '--'
            elif endpoint == 'kucoin':
                if  status == 200 and jsonResponse['data']:
                    #kucoin_price = round(float(jsonResponse['data'][0][2]),8)
                    kucoin_price = '--'
                else:
                    kucoin_price = '--'
            else:
                return
        
        all_cexdata = (binance_price, kucoin_price)
        valid_cexdata = []
        total_results = 0
        
        for cexdata in all_cexdata:
            if cexdata != '--':
                valid_cexdata.insert(0,cexdata)
                total_results += 1
                
        if total_results == 0: return(False)
        
        avgprice = round(float(sum([vcex for vcex in valid_cexdata]) / total_results),8)
        return(avgprice)

    args_ = context.args
    resperr_ = (
"""Wrong or missing arguments.

To estimate <b>Entry Price</b> please use as follows:

<b><i>/ep treasury_tx_hash</i></b>

e.g.
<code>/ep fd6c314a56f6d4894d6373327b3d6326eeafb9893df9c9a372d67e4f2f566f31</code>"""
    )
    
    if len(args_) == 1:
        tx_hash = args_[0]
        timestamp, amount = coti_tx(tx_hash)
        print(timestamp, amount)
        if timestamp:
            avgprice = cex_data(timestamp)
            if avgprice:
                resp_ = (
f"""<b>TX-hash: </b><code>{tx_hash}</code>

<b>Entry Price : </b><pre>{avgprice}</pre>
<b>Amount      : </b><pre>{amount}</pre> COTI
<b>Deposit Date: </b><pre>{datetime.utcfromtimestamp(timestamp).strftime('%d-%m-%y %H:%M:%S')}</pre>"""
                )
                update.message.reply_html(resp_, disable_web_page_preview=True)
            else: return
    else:
        update.message.reply_html(resperr_, disable_web_page_preview=True)
        return


def lp_cmd(update: Update, context: CallbackContext) -> None:
    """custom test command"""
    args_ = context.args
    resperr_ = (
"""Wrong or missing arguments.

To calculate <b>Liquidation Price</b> please use as follows:

<b><i>/lp leverage original_deposit_price liquidation_hf(optional, default is 1.0)</i></b>

e.g.
<code>/lp 4x 0.31</code>"""
    )
    
    if len(args_) == 2 or len(args_) == 3:
        try:
            lev = int(args_[0].replace('x',''))
            iprice = float(args_[1])
            if len(args_) == 3:
                liq_hf = float(args_[2])
            else:
                liq_hf = 1
            #liq_hf / lev / ((lev / ( lev - 1 * (iprice / liq_hf) )) / lev)
            #result = round((liq_hf / lev / ((lev / ( (lev - 1) * (iprice / liq_hf) )) / lev)),4)
            math_equation = liq_hf / (lev / ( (lev - 1) * iprice ) )
            result = round(math_equation,8)
        except:
            update.message.reply_html(resperr_, disable_web_page_preview=True)
            return
        
        resp_ = (
f"""<pre><b>Leverage         :</b> {lev}x
<b>Entry Price      :</b> {iprice}
<b>Liquidation Price:</b> {result}
<b>Liquidation HF   :</b> {liq_hf}</pre>"""
        )
        update.message.reply_html(resp_, disable_web_page_preview=True)
    else:
        update.message.reply_html(resperr_, disable_web_page_preview=True)



def hf_cmd(update: Update, context: CallbackContext) -> None:
    """custom test command"""
    args_ = context.args
    resperr_ = (
"""Wrong or missing arguments.

To calculate <b>Health Factor</b> please use as follows:

<b><i>/hf leverage original_deposit_price current_coti_price(optional)</i></b>

e.g.
<code>/hf 2x 0.31</code>"""
    )
    
    if len(args_) == 3 or len(args_) == 2:
        try:
            lev = int(args_[0].replace('x',''))
            iprice = float(args_[1])
            if len(args_) == 3:
                nprice = float(args_[2])
            else:
                _coti_price = coti_price()
                if _coti_price:
                    nprice = _coti_price
                else:
                   update.message.reply_html(resperr_+"<pre>[Error getting price!]</pre>", disable_web_page_preview=True) 
            result = round((lev / ((lev - 1)*(iprice/nprice))),3)
        except Exception as err:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            errln = exc_tb.tb_lineno
            print(f'Other error occurred: {err} , line: {errln}')
            
            update.message.reply_html(resperr_, disable_web_page_preview=True)
            return
        
        resp_ = (
"""<pre><b>Leverage:       </b> {lev}x
<b>Entry Price:    </b> {iprice}
<b>Current Price:  </b> {nprice}
<b>Current HF:     </b> {result}</pre>"""
        ).format(lev=str(lev), iprice=str(iprice), nprice=str(nprice), result=str(result))
        update.message.reply_html(resp_, disable_web_page_preview=True)
    else:
        update.message.reply_html(resperr_, disable_web_page_preview=True)


def newhf_cmd(update: Update, context: CallbackContext) -> None:
    """custom test command"""
    args_ = context.args
    resperr_ = (
"""Wrong or missing arguments.

To calculate <b>Health Factor</b> please use as follows:

<b><i>/newhf leverage initial_deposit_amount new_deposit_amount original_deposit_price current_coti_price(optional)</i></b>

e.g.
<code>/newhf 2x 1000 500 0.31</code>"""
    )
    
    if len(args_) == 5 or len(args_) == 4:
        try:
            lev = int(args_[0].replace('x',''))
            deposit = int(float(args_[1]))
            ndeposit = int(float(args_[2]))
            iprice = float(args_[3])
            if len(args_) == 5:
                nprice = float(args_[4])
            else:
                _coti_price = coti_price()
                if _coti_price:
                    nprice = _coti_price
                else:
                   update.message.reply_html(resperr_+"<pre>[Error getting price!]</pre>", disable_web_page_preview=True)
            HFR = lev / (lev -1)
            result = round((HFR/((deposit*iprice+ndeposit*nprice)/(deposit*nprice+ndeposit*nprice))),3)
        except Exception as err:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            errln = exc_tb.tb_lineno
            print(f'Other error occurred: {err} , line: {errln}')
            update.message.reply_html(resperr_, disable_web_page_preview=True)
            return
        
        resp_ = (
f"""<pre><b>Leverage:       </b> {lev}x
<b>Init. Deposit:  </b> {deposit}
<b>New Deposit:    </b> {ndeposit}
<b>Entry Price:    </b> {iprice}
<b>Current Price:  </b> {nprice}
<b>New HF:         </b> {result}</pre>"""
        )
        update.message.reply_html(resp_, disable_web_page_preview=True)
    else:
        update.message.reply_html(resperr_, disable_web_page_preview=True)


def getprice_cmd(update: Update, context: CallbackContext) -> None:
    """custom test command"""
    args_ = context.args
    
    try:
        if len(args_) == 1:
            ticker = args_[0].upper()
        elif len(args_) > 1:
            return
        else:
            ticker = "BTC"
        
        use_cmc = False
        
        URLs = (
            #24h data
            f"https://api1.binance.com/api/v3/ticker/24hr?symbol={ticker}USDT",
            #mcap
            f"https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?symbol={ticker}&CMC_PRO_API_KEY={CMC_PRO_API_KEY}"
        )
        
        for index in range(len(URLs)):
            URL = URLs[index]
            response = requests.get(URL)
            #response.raise_for_status()
            # access JSOn content
            jsonResponse = response.json()
            
            if index == 0:
                binance_status = response.status_code
                if binance_status == 200:
                    price = round(float(jsonResponse['lastPrice']),4)
                    hprice = round(float(jsonResponse['highPrice']),4)
                    lprice = round(float(jsonResponse['lowPrice']),4)
                    _24hCH = round(float(jsonResponse['priceChangePercent']),2)
                    volume = round(float(jsonResponse['volume']))
                else: use_cmc = True
            elif index == 1:
                cmc_status = response.status_code
                if cmc_status == 200:
                    tree = jsonResponse['data'][ticker][0]
                    total_supply = int(tree['total_supply'])
                    circulating_supply = int(tree['circulating_supply'])
                    #--
                    if use_cmc == True:
                        price = round(float(tree['quote']['USD']['price']),4)
                        hprice = '?'
                        lprice = '?'
                        _24hCH = round(float(tree['quote']['USD']['percent_change_24h']),2)
                        volume = round(float(tree['quote']['USD']['volume_24h']))
                elif cmc_status != 200 & binance_status != 200:
                    print("#no results from either api's")
                    return
                else:
                    total_supply = 0
                    circulating_supply = 0
            else:
                return
                
        print(f'cmc{cmc_status} & binance{binance_status} & use_cmc:{use_cmc}')
        cap = round(price*circulating_supply)
        fdv = round(price*total_supply)
        
        cap = '{:,}'.format(cap)
        circulating_supply = '{:,}'.format(circulating_supply)
        total_supply = '{:,}'.format(total_supply)
        
        resp_ = (
f"""<b>{ticker}</b> $ <pre>{price}</pre>
<pre>
H|L  : {hprice} | {lprice}
24h  : {_24hCH}%
Cap  : {cap}
Circ.: {circulating_supply}
Total: {total_supply}</pre>
"""
        )
        update.message.reply_html(resp_, disable_web_page_preview=True)
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except Exception as err:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        errln = exc_tb.tb_lineno
        print(f'Other error occurred: {err} , line: {errln}')


def getnodes_cmd(update: Update, context: CallbackContext) -> None:
    global node_list, cache_lu
    try:
        index = 1
        joined_node_list = ""
        
        for node in node_list:
            joined_node_list += (
"{i}) <pre>{node}</pre>\n"
            ).format(i = index, node = node)
            index += 1
        #joined_node_list = "\n".join(node_list)
        total_nodes = str(len(node_list))
        resp_ = (
"""<b><i>{total}</i> Total Nodes</b>

{nodes}

<u><i>Last updated: {cache_lu} UTC</i></u>
"""
        ).format(total = total_nodes, nodes = joined_node_list, cache_lu = cache_lu)
        update.message.reply_html(resp_, disable_web_page_preview=True)
    except Exception as e:
        #print(e.message, e.args)
        return

def gettestnodes_cmd(update: Update, context: CallbackContext) -> None:
    global test_node_list, cache_lu
    
    try:
        index = 1
        joined_node_list = ""
        
        for node in test_node_list:
            joined_node_list += (
"{i}) <pre>{node}</pre>\n"
            ).format(i = index, node = node)
            index += 1
            
        total_nodes = str(len(test_node_list))
        resp_ = (
"""<b><i>{total}</i> Total Testnet Nodes</b>

{nodes}

<u><i>Last updated: {cache_lu} UTC</i></u>
"""
        ).format(total = total_nodes, nodes = joined_node_list, cache_lu = cache_lu)
        update.message.reply_html(resp_, disable_web_page_preview=True)
    except Exception as e:
        #print(e.message, e.args)
        return


def get_multicexdata(ticker):
    URLs = {
        'binance': f"https://api1.binance.com/api/v3/ticker/price?symbol={ticker.upper()}USDT",
        'kucoin': f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={ticker.upper()}-USDT",
        'huobi': f"https://api.huobi.pro/market/trade?symbol={ticker.lower()}usdt",
        'coinbase': f"https://api.coinbase.com/v2/prices/{ticker.upper()}-USD/spot",
        'gateio': f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={ticker.upper()}_USDT"
    }
    
    for endpoint in URLs:
        URL = URLs[endpoint]
        response = requests.get(URL)
        #response.raise_for_status()
        # access JSOn content
        jsonResponse = response.json()
        status = response.status_code
        
        if endpoint == 'binance':
            if  status == 200:
                binance_price = round(float(jsonResponse['price']),4)
            else:
                binance_price = '--'
        elif endpoint == 'kucoin':
            if  status == 200 and jsonResponse['data']:
                kucoin_price = round(float(jsonResponse['data']['price']),4)
            else:
                kucoin_price = '--'
        elif endpoint == 'huobi':
            if  status == 200 and jsonResponse['status'] == "ok":
                huobi_price = round(float(jsonResponse['tick']['data'][0]['price']),4)
            else:
                huobi_price = '--'
        elif endpoint == 'coinbase':
            if  status == 200:
                coinbase_price = round(float(jsonResponse['data']['amount']),4)
            else:
                coinbase_price = '--'
        elif endpoint == 'gateio':
            if  status == 200:
                gateio_price = round(float(jsonResponse[0]['last']),4)
            else:
                gateio_price = '--'
        else:
            return
            
    all_cexdata = {'binance': binance_price, 'kucoin': kucoin_price, 'huobi': huobi_price, 'coinbase': coinbase_price, 'gate.io': gateio_price}
    valid_cexdata = {}
    total_results = 0
    
    for cex in all_cexdata:
        cexdata = all_cexdata[cex]
        if cexdata != '--':
            valid_cexdata.update({cex: cexdata})
            total_results += 1
            
    if total_results == 0: return
        
    avgprice = round(float(sum([valid_cexdata[vcex] for vcex in valid_cexdata]) / total_results),4)
    
    import operator
    highcex = max(valid_cexdata.items(), key=operator.itemgetter(1))[0]
    lowcex = min(valid_cexdata.items(), key=operator.itemgetter(1))[0]
    price_dif = (valid_cexdata[highcex] - valid_cexdata[lowcex])
    lowper = round((price_dif / valid_cexdata[highcex] * 100), 4)
    higper = round((price_dif / valid_cexdata[lowcex] * 100), 4)
    
    return(binance_price, kucoin_price, huobi_price, coinbase_price, gateio_price, avgprice, price_dif, lowcex, highcex, lowper, higper)
    
    #a,b,c,d = binance_price,kucoin_price,huobi_price,coinbase_price
    #total_results = (1 if a!= '?' else 0) + (1 if a!= '?' else 0) + (1 if a!= '?' else 0) + (1 if a!= '?' else 0)
    #avgprice = round(float(((a + b + c + d) / total_results)),4)


def arb_cmd(update: Update, context: CallbackContext) -> None:
    
    args_ = context.args
    
    if len(args_) == 1:
        ticker = args_[0].upper()
    elif len(args_) > 1:
        return
    else:
        ticker = "BTC"
        
    try:
        binance_price, kucoin_price, huobi_price, coinbase_price, gateio_price, avgprice, price_dif, lowcex, highcex, lowper, higper  = get_multicexdata(ticker)
        
        resp_ = (
f"""<b>{ticker}</b> $ <pre>{avgprice}</pre>
<pre>
{lowcex.capitalize()} {lowper}% lower
{highcex.capitalize()} {higper}% higher

Difference $ {round(price_dif, 10)}

Binance : {binance_price}
Kucoin  : {kucoin_price}
Huobi   : {huobi_price}
Coinbase: {coinbase_price}
Gate.io : {gateio_price}</pre>
"""
        )
        
        keyboard = [[InlineKeyboardButton("Refresh", callback_data=f'{ticker}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_html(resp_, disable_web_page_preview=True, reply_markup=reply_markup)
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except Exception as err:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        errln = exc_tb.tb_lineno
        print(f'Other error occurred: {err} , line: {errln}')


def button(update: Update, context: CallbackContext) -> None:
    try:
        query = update.callback_query
        query.answer("Updating data, please wait...")
        ticker = query.data
        binance_price, kucoin_price, huobi_price, coinbase_price, gateio_price, avgprice, price_dif, lowcex, highcex, lowper, higper  = get_multicexdata(ticker)
        lu = datetime.now(tz=pytz.UTC).strftime("%H:%M:%S")
        resp_ = (
f"""<b>{ticker}</b> $ <pre>{avgprice}</pre>
<pre>
{lowcex.capitalize()} {lowper}% lower
{highcex.capitalize()} {higper}% higher

Difference $ {round(price_dif, 10)}

Binance : {binance_price}
Kucoin  : {kucoin_price}
Huobi   : {huobi_price}
Coinbase: {coinbase_price}
Gate.io : {gateio_price}</pre>

<u><i>Last updated: {lu} UTC</i></u>
"""
        )
        
        keyboard = [[InlineKeyboardButton("Refresh", callback_data=f'{ticker}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(text=resp_, parse_mode="html", disable_web_page_preview=True, reply_markup=reply_markup)
    except Exception as err:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        errln = exc_tb.tb_lineno
        print(f'Other error occurred: {err} , line: {errln}')


def sys_cmd(update: Update, context: CallbackContext) -> None:
    global core_admins
    from_user = update.message.from_user
    from_user_id = from_user.id
    args_ = context.args
    
    print("system command from => {from_user}".format(from_user = str(from_user)))
    
    if from_user_id in core_admins:
        if len(args_) == 1:
            arg_ = args_[0]
            if arg_ == 'pid':
                pid = os.getpid()
                update.message.reply_text(str(pid))
            elif arg_ == 'reset':
                #os.execv(sys.argv[0], sys.argv)
                update.message.reply_text("Done!")
                os.execv(sys.executable, ['python3'] + sys.argv)
            elif arg_ == 'kill':
                update.message.reply_text("Done!")
                #_thread.interrupt_main()
                #os.kill(os.getpid(), signal.SIGINT)
                os.system('kill -9 $PPID')
                #sys.exit()


def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    updaters_ = {
        'COTIdiscussion_bot': Updater(COTIdiscussion_bot_TOKEN),
        'coticomm_bot': Updater(coticomm_bot_TOKEN),
        'crypto_sharktank_bot': Updater(crypto_sharktank_bot_TOKEN)
        }
    
    for bot_ in updaters_:
        updater = updaters_[bot_]
        
        # Get the dispatcher to register handlers
        dispatcher = updater.dispatcher
        
        #crypto
        if bot_ in {'COTIdiscussion_bot', 'coticomm_bot', 'crypto_sharktank_bot'}:
            dispatcher.add_handler(CommandHandler("p", getprice_cmd))
            dispatcher.add_handler(CommandHandler("price", getprice_cmd))
        
        #coti specific
        if bot_ in {'COTIdiscussion_bot', 'coticomm_bot'}:
            dispatcher.add_handler(CommandHandler("hf", hf_cmd))
            dispatcher.add_handler(CommandHandler("newhf", newhf_cmd))
            dispatcher.add_handler(CommandHandler("nodes", getnodes_cmd))
            dispatcher.add_handler(CommandHandler("testnodes", gettestnodes_cmd))
            dispatcher.add_handler(CommandHandler("lp", lp_cmd))
            dispatcher.add_handler(CommandHandler("ep", ep_cmd))
            
        #sharktank
        if bot_ in {'crypto_sharktank_bot'}:
            dispatcher.add_handler(CommandHandler("arb", arb_cmd))
            dispatcher.add_handler(CallbackQueryHandler(button))
        
        #universal
        dispatcher.add_handler(CommandHandler("sys", sys_cmd, Filters.chat_type.private))
        dispatcher.add_handler(CommandHandler("start", start, Filters.chat_type.private))
        # on non command i.e message - echo the message on Telegram
        #dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

        # Start the Bot
        updater.start_polling()

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        #updater.idle()


if __name__ == '__main__':
    main()
