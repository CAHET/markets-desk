# ALL STRATEGIES – one page (v3, 25-Nov-2026) · Capital ₹20,000
Status: LIVE-OK · TEST (positive but thin/small sample) · FAIL · FILTER · PENDING.

| ID | Strategy | Vehicle | Side | Tested on | Result (net) | Status |
|---|---|---|---|---|---|---|
| S04 | Nifty>EMA200 + RSI(10)<30, exit RSI>40/7d (Anant) | NIFTY weekly ATM CE | Long | INDEX 2016–26 | 23 trades, 74% win; option ≈ ₹3,050/trade, 57% win, worst −₹14.5k | TEST – alert live |
| S04-stk | RSI(4)<10 variant, Nifty 50 stocks | Delivery | Long | STOCKS 2019–26 | OOS PF 1.77, ~14%/yr, DD −19% | TEST |
| HC-RSI | RSI(14) 30/70 mean reversion | Delivery | Long | STOCKS | beats buy-and-hold on ~21–32 of 50 | TEST (same family as S04) |
| S03 | Life-High Pullback | Delivery | Long | STOCKS 2010–26 | CAGR 13.5%, DD −19.8% | TEST (positional) |
| S02 | 9-21 EMA, 15-min first cross | NIFTY option | L/S | INDEX | PF 1.27–1.42; ₹20k ruined in sequence test | TEST – paper only |
| A2s | Anant 5 EMA alert candle, short 15m | (futures) | Short | INDEX | points PF 1.09/1.15; options lose | TEST |
| G2 | Gap-down day, 45-min range breakout (Ghanshyam) | NIFTY (points) | L/S | INDEX 2021–26 | 26 trades, 81% win, PF 6.5, ~60 pts/trade; small sample | TEST |
| M01 | Month-of-year off-switch | Filter | – | INDEX 2010–26 | no month negative in both IS and OOS | FAIL – no month switched off |
| G6 | Real-vs-fake breakout filter (Ghanshyam) | Filter | – | STOCKS | lifts breakout PF ~0.84 → ~1.03 | FILTER (weak) |
| F01 | Distribution days ≥5 in 25 sessions = skip | Filter | – | STOCKS | small help both periods | FILTER (weak) |
| S05 | 9:30 Opening Range Breakout | – | L/S | INDEX+STOCKS | loses after costs | FAIL |
| A1 | Anant 10 EMA continuation | – | L/S | INDEX | options PF 0.56–0.89 | FAIL |
| A3 | Anant 2.5-day funda | – | L/S | STOCKS | OOS PF 0.5–0.9 | FAIL |
| G3 | NR4 breakout | – | Long | STOCKS | PF 0.84 | FAIL |
| HC-trend | EMA / Donchian / Supertrend / MACD | – | L/S | INDEX+STOCKS | below buy-and-hold | FAIL |
| S01 | RSI W/N + ATM CE | – | Long | STOCKS | −₹21.1L | FAIL |
| S06 | Bank pairs | futures | Neutral | – | margin > ₹20k | PARKED |

Bottom line: only RSI mean-reversion (S04 family) has held up across index and stocks (G2 is promising but has only 26 trades); every short and every trend-following system tested lost or lagged buy-and-hold. Max loss ₹400–₹1,000 per trade (see the Trading Rulebook). Live paper-trade scoreboard on the dashboard switches a strategy OFF after 10+ paper trades with PF < 1. Research only, not advice.
