

def entry_algo(df):
    data = df[(df['Close'] < df['prev7DayLow']) & (df['RSI(2)'] <= 15) & (df['ADX(5)'] > 35)]
    return data.reset_index(drop=True)

def exit_algo(df):
    data = []
    for x in df:
        print(x.ticker, "Close:", x.close, "7High:", x.prevSevenDayHigh)
        if((x.close > x.prevSevenDayHigh) | (x.plpc > .07) | (x.close <= (x.entry_price - x.sl)) | (x.plpc < -0.05)):
            data.append(x)

    return data