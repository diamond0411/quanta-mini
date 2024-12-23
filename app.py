from datetime import datetime
import requests
import pandas_market_calendars as mcal
from dateutil.relativedelta import relativedelta
import pandas as pd
import traceback
import csv
from flask import Flask, make_response, request, render_template
from flask_cors import CORS
from io import StringIO
tiingo = "4cb65d8af8f3aa3b4a073ea219027773a29fbbcd"
nyse = mcal.get_calendar('NYSE')
headers = {
    'Content-Type': 'application/json'
}
app = Flask(__name__)
CORS(app)
@app.route("/")
def index():
    return render_template('index.html')

def findprevioustradingday(date_index: pd.DatetimeIndex, target_date: datetime):
    if target_date.tzinfo is None:
        target_date = pd.Timestamp(target_date).tz_localize('UTC')
    try:
        pos = date_index.get_indexer([target_date], method="nearest")[0]
        if pos >= 0 and pos >= 20:
            return date_index[pos-20]
    except:
        traceback.print_exc()
        return None
    return None
@app.route('/get-report')
def op():
    try:
        ticker = request.args.get('ticker',type=str)
        start = request.args.get('start_date',type=str)
        end = request.args.get('end_date',type=str)
        pvbt = request.args.get('pvbt',type=float) 
        dct = request.args.get('dct',type=float)
        holding = request.args.get('holding',type=int)
        startdt = datetime.strptime(start, "%Y-%m-%d")
        tempstart = (startdt - relativedelta(months=2)).date()
        querystart = findprevioustradingday(mcal.date_range(nyse.schedule(tempstart, end), frequency="1D"), startdt)
        url = "https://api.tiingo.com/tiingo/daily/{}/prices?startDate={}&endDate={}&token=4cb65d8af8f3aa3b4a073ea219027773a29fbbcd".format(ticker, querystart, end)
        x = requests.get(url).json()
    except:
        traceback.print_exc()
        return "Bad Args", 400
    dates = []
    info = {}
    non_buy_day_total = 0
    non_buy_days = 0
    volumes = []
    avg_volume = float("inf")
    for i, entry in enumerate(x):
        if len(volumes) != 20:
            volumes.append(entry['volume'])
            continue
        else:
            avg_volume = sum(volumes)/20
            volumes.pop(0)
            volumes.append(entry['volume'])
        dates.append(entry['date'])
        percent_diff = (entry['close']/x[i-1]['close'] * 100) - 100
        buy_day = "YES" if entry['volume'] > (pvbt/100 + 1) * avg_volume and percent_diff>dct else "NO"
        profit = x[i + holding]['close']-entry['close'] if buy_day == "YES" and i + holding < len(x) else "N/A"
        if buy_day == "NO" and i + holding < len(x):
            non_buy_day_total += x[i + holding]['close']-entry['close'] 
            non_buy_days += 1
        info[entry['date']] = [entry['close'], percent_diff, entry['volume'], avg_volume, buy_day, profit]
    si = StringIO()
    writer = csv.writer(si, delimiter=",")

    writer.writerow(["date", "close_price", "price_diff_percent", "volume", "avg_volume", "buy_day", "profit", "diff_vs_nb_avg"])
    for date in dates:
        if info[date][4] == "YES":
            writer.writerow([date[0:10].replace("-","/")] + info[date] + [info[date][5]-(non_buy_day_total/non_buy_days) if info[date][5] != "N/A" else "N/A"])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename={}-{}-{}-{}-{}-{}.csv".format(ticker,start,end,pvbt,dct,holding)
    output.headers["Content-type"] = "text/csv"
    return output

if __name__ == '__main__':
    app.run()