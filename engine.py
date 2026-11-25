"""Markets Desk robot: free daily signals, scans, news, paper-trade scoreboard and dashboard data.
Runs on GitHub Actions. No AI, no Claude. Research only, not advice. Orders are placed by you in Kite.
Usage: python engine.py news | signals
Optional secrets (set in GitHub > Settings > Secrets > Actions): GMAIL_USER, GMAIL_APP_PASSWORD, ALERT_TO,
TELEGRAM_TOKEN, TELEGRAM_CHAT_ID.
"""
import json, os, sys, smtplib, datetime as dt, re, html
from email.mime.text import MIMEText
import xml.etree.ElementTree as ET
import requests, pandas as pd, numpy as np

UA = {"User-Agent": "Mozilla/5.0"}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
STOCKS = ("ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BAJAJ-AUTO BAJAJFINSV BAJFINANCE BEL BHARTIARTL BSE CIPLA "
          "COALINDIA DRREDDY EICHERMOT ETERNAL GRASIM HCLTECH HDFCBANK HDFCLIFE HINDALCO HINDUNILVR ICICIBANK INDIGO INFY "
          "ITC JIOFIN JSWSTEEL KOTAKBANK LT M&M MARUTI MAXHEALTH NESTLEIND NTPC ONGC POWERGRID RELIANCE SBILIFE SBIN "
          "SHRIRAMFIN SUNPHARMA TATACONSUM TATASTEEL TCS TECHM TITAN TMPV TRENT ULTRACEMCO").split()
NAMES = {"HDFCBANK": "HDFC Bank", "ICICIBANK": "ICICI Bank", "SBIN": "SBI", "KOTAKBANK": "Kotak", "AXISBANK": "Axis Bank",
         "RELIANCE": "Reliance", "INFY": "Infosys", "TCS": "TCS", "HCLTECH": "HCL", "TECHM": "Tech Mahindra", "LT": "L&T",
         "ITC": "ITC", "BHARTIARTL": "Airtel", "M&M": "Mahindra", "MARUTI": "Maruti", "TATASTEEL": "Tata Steel",
         "TMPV": "Tata Motors", "SUNPHARMA": "Sun Pharma", "CIPLA": "Cipla", "DRREDDY": "Dr Reddy", "TITAN": "Titan",
         "TRENT": "Trent", "ADANIENT": "Adani Enterprises", "ADANIPORTS": "Adani Ports", "BAJFINANCE": "Bajaj Finance",
         "BAJAJFINSV": "Bajaj Finserv", "BAJAJ-AUTO": "Bajaj Auto", "ASIANPAINT": "Asian Paints", "NTPC": "NTPC",
         "ONGC": "ONGC", "POWERGRID": "Power Grid", "COALINDIA": "Coal India", "JSWSTEEL": "JSW Steel", "HINDALCO": "Hindalco",
         "HINDUNILVR": "HUL", "NESTLEIND": "Nestle", "ULTRACEMCO": "UltraTech", "GRASIM": "Grasim", "EICHERMOT": "Eicher",
         "APOLLOHOSP": "Apollo Hospitals", "MAXHEALTH": "Max Health", "HDFCLIFE": "HDFC Life", "SBILIFE": "SBI Life",
         "SHRIRAMFIN": "Shriram Finance", "BEL": "Bharat Electronics", "BSE": "BSE", "INDIGO": "IndiGo", "JIOFIN": "Jio Financial",
         "ETERNAL": "Zomato", "TATACONSUM": "Tata Consumer"}
FEEDS = ["https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
         "https://www.moneycontrol.com/rss/marketreports.xml",
         "https://www.moneycontrol.com/rss/buzzingstocks.xml",
         "https://www.business-standard.com/rss/markets-106.rss",
         "https://www.livemint.com/rss/markets"]


def yahoo(sym, rng="10y"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(sym)}?range={rng}&interval=1d"
    r = requests.get(url, headers=UA, timeout=30); r.raise_for_status()
    res = r.json()["chart"]["result"][0]; q = res["indicators"]["quote"][0]
    df = pd.DataFrame({"o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"], "v": q["volume"]},
                      index=pd.to_datetime(res["timestamp"], unit="s") + pd.Timedelta(hours=5, minutes=30))
    df.index = df.index.normalize()
    return df.dropna(subset=["c"]).groupby(level=0).last()


def rsi(c, n):
    d = c.diff(); g = d.clip(lower=0); l = -d.clip(upper=0)
    ag = g.ewm(alpha=1 / n, adjust=False, min_periods=n).mean(); al = l.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + ag / al)


def ema(c, n): return c.ewm(span=n, adjust=False).mean()


def r1(x): return None if x is None or not np.isfinite(x) else round(float(x), 1)


def index_state():
    n = yahoo("^NSEI"); b = yahoo("^NSEBANK"); v = yahoo("^INDIAVIX", "2y")
    c = n.c; e200 = ema(c, 200); r10 = rsi(c, 10); r3 = rsi(c, 3)
    s = {"date": str(c.index[-1].date()), "nifty": r1(c.iloc[-1]), "ema200": r1(e200.iloc[-1]), "rsi10": r1(r10.iloc[-1]),
         "rsi3": r1(r3.iloc[-1]), "trend_up": bool(c.iloc[-1] > e200.iloc[-1]), "vix": r1(v.c.iloc[-1]),
         "vix_med20": r1(v.c.tail(20).median()), "banknifty": r1(b.c.iloc[-1]),
         "nifty_chg": r1((c.iloc[-1] / c.iloc[-2] - 1) * 100)}
    s["s04_entry"] = s["trend_up"] and s["rsi10"] < 30
    s["s04_near"] = s["trend_up"] and s["rsi10"] < 35
    s["s04_exit_zone"] = s["rsi10"] > 40
    vol = n.v.fillna(0)
    if vol.tail(30).gt(0).all():  # distribution days (IBD) only when Yahoo has index volume
        ch = c.pct_change(); dd = (ch < -0.002) & (vol > vol.shift())
        s["distribution_days_25"] = int(dd.tail(25).sum())
    return s


def stock_scan(frames=None):
    rows = []
    for sym in STOCKS:
        try:
            d = yahoo(sym + ".NS")
        except Exception as ex:
            rows.append({"sym": sym, "error": str(ex)[:80]}); continue
        if frames is not None: frames[sym] = d
        c = d.c; e200 = ema(c, 200)
        row = {"sym": sym, "close": r1(c.iloc[-1]), "chg": r1((c.iloc[-1] / c.iloc[-2] - 1) * 100),
               "above200": bool(c.iloc[-1] > e200.iloc[-1]), "rsi4": r1(rsi(c, 4).iloc[-1]), "rsi10": r1(rsi(c, 10).iloc[-1]),
               "rsi14": r1(rsi(c, 14).iloc[-1])}
        row["s04_rsi4"] = row["above200"] and row["rsi4"] < 10
        row["s04_base"] = row["above200"] and row["rsi10"] < 30
        row["hc_rsi"] = row["rsi14"] < 30
        row["near"] = row["above200"] and (row["rsi4"] < 20 or row["rsi10"] < 35)
        row.update(life_high(d))
        rows.append(row)
    return rows


def life_high(d):
    """S03 Life-High Pullback setup (approximation on Yahoo daily data, up to 10 years)."""
    try:
        m = d.c.resample("ME").last(); mh = d.h.resample("ME").max()
        ath = mh.cummax(); last_ath_month = mh[mh == ath].index[-1]
        months_since = (m.index[-1].year - last_ath_month.year) * 12 + m.index[-1].month - last_ath_month.month
        trend = months_since <= 24 and m.iloc[-1] >= 0.8 * ath.iloc[-1]
        w = d.c.resample("W-FRI").last(); wr = rsi(w, 14)
        weekly = bool((wr.tail(6) <= 50).any())
        tail = d.tail(30); low_i = tail.l.idxmin(); since = len(d.loc[low_i:]) - 1
        base = d.loc[low_i:]
        base_high = base.h.iloc[:-1].max() if since >= 1 else np.nan
        o, c, h, l = base.o.values, base.c.values, base.h.values, base.l.values
        rev = False
        for k in range(1, len(base) - 1):
            body = abs(c[k] - o[k]); rng = h[k] - l[k] + 1e-9
            hammer = (min(o[k], c[k]) - l[k]) >= 2 * body and body / rng < 0.4
            engulf = c[k] > o[k] and c[k - 1] < o[k - 1] and c[k] >= o[k - 1] and o[k] <= c[k - 1]
            harami = c[k] > o[k] and c[k - 1] < o[k - 1] and c[k] < o[k - 1] and o[k] > c[k - 1]
            rev = rev or hammer or engulf or harami
        tr = pd.concat([d.h - d.l, (d.h - d.c.shift()).abs(), (d.l - d.c.shift()).abs()], axis=1).max(axis=1)
        atr14 = tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1]
        setup = trend and weekly and since >= 5 and rev
        trig = bool(setup and d.c.iloc[-1] > base_high and d.c.iloc[-2] <= base_high)
        return {"lh_setup": bool(setup), "lh_trigger": trig, "lh_base_high": r1(base_high), "lh_stop": r1(tail.l.min() - atr14)}
    except Exception:
        return {"lh_setup": False, "lh_trigger": False}


def news():
    items, seen = [], set()
    for f in FEEDS:
        try:
            r = requests.get(f, headers=UA, timeout=20); root = ET.fromstring(r.content)
            for it in root.iter("item"):
                t = (it.findtext("title") or "").strip(); link = (it.findtext("link") or "").strip()
                if not t or t.lower() in seen: continue
                seen.add(t.lower())
                hits = [s for s, nm in NAMES.items() if re.search(r"\b" + re.escape(nm) + r"\b", t, re.I)]
                items.append({"title": html.unescape(t), "link": link, "src": re.sub(r"https?://(www\.)?([^/]+).*", r"\2", f),
                              "stocks": hits, "pub": (it.findtext("pubDate") or "")[:25]})
        except Exception:
            continue
    items.sort(key=lambda x: (len(x["stocks"]) == 0,))
    return items[:40]


def send(subject, body):
    user, pw, to = os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD"), os.getenv("ALERT_TO") or os.getenv("GMAIL_USER")
    if user and pw:
        msg = MIMEText(body); msg["Subject"] = subject; msg["From"] = user; msg["To"] = to
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pw); s.send_message(msg)
    tok, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if tok and chat:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", data={"chat_id": chat, "text": f"{subject}\n\n{body}"[:4000]}, timeout=20)


RULES = {"S04-NIFTY": "RSI(10)<30 above 200-EMA; exit RSI(10)>40 or 7 days",
         "S04-STK-RSI4": "RSI(4)<10 above 200-EMA; exit RSI(4)>40 or 10 days",
         "S04-STK-BASE": "RSI(10)<30 above 200-EMA; exit RSI(10)>40 or 7 days",
         "LH": "Life-High Pullback; stop pivot low - 1 ATR, trail highest high - 10 ATR(22)"}


def paper_update(data, frames, idx_frame, rows, idx):
    """Paper-trades every signal (entry and exit at next open) and keeps live stats per strategy
    (closed trades plus open trades at today's price). With 10+ trades and profit factor below 1 it is marked OFF."""
    p = data.setdefault("paper", {"open": [], "closed": []})
    get = lambda sym: idx_frame if sym == "NIFTY" else frames.get(sym)
    still = []
    for t in p["open"]:
        d = get(t["sym"])
        if d is None: still.append(t); continue
        after = d[d.index > pd.Timestamp(t["signal"])]
        if t.get("entry") is None:
            if len(after) == 0: still.append(t); continue
            t["entry_date"] = str(after.index[0].date()); t["entry"] = r1(after.o.iloc[0]); t["peak"] = t["entry"]
        held = d[d.index >= pd.Timestamp(t["entry_date"])]
        if t.get("exit_signal"):
            nxt = d[d.index > pd.Timestamp(t["exit_signal"])]
            if len(nxt):
                t["exit_date"] = str(nxt.index[0].date()); t["exit"] = r1(nxt.o.iloc[0])
                t["ret"] = round((t["exit"] / t["entry"] - 1) * 100 - 0.24, 2); p["closed"].append(t); continue
            still.append(t); continue
        c = d.c; n = len(held); last = str(d.index[-1].date())
        if t["strat"] == "LH":
            t["peak"] = max(t["peak"], float(held.h.max()))
            tr = pd.concat([d.h - d.l, (d.h - c.shift()).abs(), (d.l - c.shift()).abs()], axis=1).max(axis=1)
            trail = t["peak"] - 10 * float(tr.ewm(alpha=1 / 22, adjust=False).mean().iloc[-1])
            if c.iloc[-1] < max(t["stop"], trail): t["exit_signal"] = last
        else:
            k, lvl, hmax = (4, 40, 10) if t["strat"] == "S04-STK-RSI4" else (10, 40, 7)
            if rsi(c, k).iloc[-1] > lvl or n >= hmax: t["exit_signal"] = last
        still.append(t)
    p["open"] = still
    have = {(t["strat"], t["sym"]) for t in p["open"]}
    new = []
    if idx["s04_entry"]: new.append(("S04-NIFTY", "NIFTY", None))
    for r in rows:
        if r.get("s04_rsi4"): new.append(("S04-STK-RSI4", r["sym"], None))
        if r.get("s04_base"): new.append(("S04-STK-BASE", r["sym"], None))
        if r.get("lh_trigger"): new.append(("LH", r["sym"], r.get("lh_stop")))
    for strat, sym, stop in new:
        if (strat, sym) not in have:
            p["open"].append({"strat": strat, "sym": sym, "signal": idx["date"], "entry": None, "stop": stop})
    for t in p["open"]:
        d = get(t["sym"])
        if d is not None and t.get("entry"): t["mtm"] = round((float(d.c.iloc[-1]) / t["entry"] - 1) * 100, 2)
    stats = {}
    for strat in RULES:
        rr = [t["ret"] for t in p["closed"] if t["strat"] == strat] + [t["mtm"] for t in p["open"] if t["strat"] == strat and t.get("mtm") is not None]
        w = [x for x in rr if x > 0]; l = [x for x in rr if x <= 0]
        pf = round(sum(w) / -sum(l), 2) if l and sum(l) < 0 else None
        status = "OFF - losing on paper" if len(rr) >= 10 and pf is not None and pf < 1 else ("ON" if len(rr) >= 10 else "collecting trades")
        stats[strat] = {"rule": RULES[strat], "closed": sum(t["strat"] == strat for t in p["closed"]), "counted": len(rr), "open": sum(t["strat"] == strat for t in p["open"]),
                        "win_pct": round(100 * len(w) / len(rr)) if rr else None, "avg_pct": round(sum(rr) / len(rr), 2) if rr else None,
                        "pf": pf, "status": status}
    p["closed"] = p["closed"][-500:]
    data["paper_stats"] = stats


FOOT = "\n\nRule outputs from backtests and public headlines, not advice. You place orders yourself in Kite. Dashboard: https://cahet.github.io/markets-desk/"


def main(mode):
    now = dt.datetime.now(IST)
    data = {}
    if os.path.exists("data.json"):
        try: data = json.load(open("data.json"))
        except Exception: data = {}
    idx = index_state(); data["index"] = idx; data["updated"] = now.strftime("%d-%b-%Y %H:%M IST")
    if mode == "news":
        nw = news(); data["news"] = nw; data["news_time"] = data["updated"]
        lines = [f"Nifty {idx['nifty']} ({idx['nifty_chg']}%) | above 200-EMA: {idx['trend_up']} | RSI(10) {idx['rsi10']} | VIX {idx['vix']}", ""]
        lines += [f"- {n['title']}" + (f"  [{', '.join(n['stocks'])}]" if n['stocks'] else "") + f"\n  {n['link']}" for n in nw[:12]]
        send(f"Markets news - {now:%d %b %Y}", "\n".join(lines) + FOOT)
    else:
        frames = {}
        rows = stock_scan(frames); data["stocks"] = rows; data["scan_time"] = data["updated"]
        sig = [r for r in rows if r.get("s04_rsi4") or r.get("s04_base")]
        near = [r for r in rows if r.get("near") and r not in sig]
        lh = [r for r in rows if r.get("lh_trigger")]
        parts = []
        if idx["s04_entry"]: parts.append(f"NIFTY S04 ENTRY SIGNAL: RSI(10) {idx['rsi10']} < 30, Nifty {idx['nifty']} above 200-EMA {idx['ema200']}. Entry next open; exit when RSI(10) > 40 or after 7 days.")
        elif idx["s04_near"]: parts.append(f"NIFTY S04 near signal: RSI(10) {idx['rsi10']} (entry needs < 30).")
        if sig: parts.append("Stock S04 signals (above 200-EMA, RSI dip): " + ", ".join(f"{r['sym']} {r['close']} RSI4 {r['rsi4']}" for r in sig))
        if lh: parts.append("Life-High Pullback triggers: " + ", ".join(f"{r['sym']} close {r['close']} > base high {r['lh_base_high']}, stop {r['lh_stop']}" for r in lh))
        if near: parts.append("Near a signal: " + ", ".join(r["sym"] for r in near))
        hist = data.get("signal_log", [])
        hist.append({"date": idx["date"], "nifty": idx["nifty"], "rsi10": idx["rsi10"], "entry": idx["s04_entry"],
                     "stocks": [r["sym"] for r in sig], "lh": [r["sym"] for r in lh]})
        data["signal_log"] = hist[-250:]
        try:
            paper_update(data, frames, yahoo("^NSEI"), rows, idx)
        except Exception as ex:
            data["paper_error"] = str(ex)[:200]
        if idx["s04_entry"] or sig or lh:
            send(f"Markets signal - {now:%d %b %Y}", "\n\n".join(parts) + "\n\nRulebook: max loss Rs 400 per trade; stop goes in with the order." + FOOT)
    json.dump(data, open("data.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "signals")
