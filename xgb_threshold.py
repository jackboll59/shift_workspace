"""Offline OBI backtest; hypothetical P&L per share, no SHIFT orders."""
import sys
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

H = 5
thresholds = np.arange(1, 10) / 10
path = sys.argv[1] if len(sys.argv) > 1 else 'data_AAPL.csv'
df = pd.read_csv(path)
# Keep original observation order.
df = df[(df.bid_volume + df.ask_volume > 0) &
        (df.best_bid <= df.best_ask)].copy().reset_index(drop=True)
df['obi'] = (df.bid_volume - df.ask_volume) / (df.bid_volume + df.ask_volume)
df['mid'] = (df.best_bid + df.best_ask) / 2
df['spread'] = df.best_ask - df.best_bid
df['volume'] = df.bid_volume + df.ask_volume
df['lag_obi'] = df.obi.shift(1)
df['mean_abs_obi'] = df.obi.abs().shift(1).rolling(10).mean()
df['volatility'] = df.mid.diff().rolling(10).std()
df['momentum'] = df.mid.diff(5)
df['fwd'] = df.mid.shift(-H) - df.mid
features = ['spread', 'volume', 'lag_obi', 'mean_abs_obi', 'volatility', 'momentum']
df = df.dropna(subset=features + ['fwd']).reset_index(drop=True)
# Chronological split with a five-row gap.
split = int(len(df) * .7)
train = df.iloc[:split-H].copy()
test = df.iloc[split:].copy()

def reward(d, threshold):
    side = np.where(d.obi > threshold, 1, np.where(d.obi < -threshold, -1, 0))
    return side, side * d.fwd.to_numpy() - np.abs(side) * d.spread.to_numpy()

# Fixed-threshold benchmark.
scores = {}
for t in thresholds:
    side, pnl = reward(train, t)
    if np.any(side):
        scores[t] = pnl[side != 0].mean()
fixed = max(scores, key=scores.get)

# Fit one reward model per threshold; current OBI triggers trades separately.
models = []
for t in thresholds:
    _, pnl = reward(train, t)
    model = XGBRegressor(n_estimators=60, max_depth=2, learning_rate=.05,
                         reg_lambda=5, n_jobs=1, random_state=42)
    model.fit(train[features], pnl)
    models.append(model)

pred = np.column_stack([m.predict(test[features]) for m in models])
chosen = thresholds[pred.argmax(axis=1)]
# Skip trades when predicted reward is nonpositive.
chosen = np.where(pred.max(axis=1) > 0, chosen, 1.0)

def report(name, side, pnl):
    n = np.count_nonzero(side)
    print(name, '| trades:', n, '| total:', round(pnl.sum(), 5),
          '| avg per trade:', round(pnl[side != 0].mean(), 5) if n else 'N/A',
          '| avg per observation:', round(pnl.mean(), 7))

print('Training rows:', len(train), '| Test rows:', len(test))
print('Fixed threshold:', fixed)
report('Fixed', *reward(test, fixed))
report('XGBoost', *reward(test, chosen))
print('Chosen thresholds (1.0 = no trade):')
print(pd.Series(chosen).value_counts().sort_index())
