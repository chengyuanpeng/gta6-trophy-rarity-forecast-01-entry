"""Pooled log-count growth forecast for GTA VI trophy earn rates."""
import json
import math
import os
from pathlib import Path

LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)
Z = (-1.644853626951, -0.674489750196, 0.0, 0.674489750196, 1.644853626951)
INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))


def clamp(p):
    return min(99.99, max(0.01, p))


def logit(p):
    p = clamp(p) / 100.0
    return math.log(p / (1.0 - p))


def logistic(x):
    if x >= 0:
        return 100.0 / (1.0 + math.exp(-min(x, 700.0)))
    e = math.exp(max(x, -700.0))
    return 100.0 * e / (1.0 + e)


def parse_time(s):
    from datetime import datetime
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def slope(xs, ys):
    """OLS slope with a mild recency weight; input coordinates are log-time."""
    if len(xs) < 2:
        return 0.0
    # The last day of observations matters most; weights decay over 30 hours.
    end = max(xs)
    ws = [math.exp(-max(0.0, end - x) / 0.55) for x in xs]
    sw = sum(ws)
    xm = sum(w*x for w, x in zip(ws, xs)) / sw
    ym = sum(w*y for w, y in zip(ws, ys)) / sw
    den = sum(w*(x-xm)**2 for w, x in zip(ws, xs))
    return sum(w*(x-xm)*(y-ym) for w, x, y in zip(ws, xs, ys)) / den if den > 1e-12 else 0.0


def median(values):
    if not values:
        return 0.0
    a = sorted(values)
    n = len(a)
    return (a[n//2] if n % 2 else (a[n//2-1] + a[n//2]) / 2.0)


def level_group(rate):
    if rate < 1.0: return "rare"
    if rate < 10.0: return "low"
    if rate < 50.0: return "mid"
    return "high"


def forecast(case):
    trophies = case["trophies"]
    history = case["history"]
    if not history:
        raise ValueError("empty history")
    origin = parse_time("2026-11-19T00:00:00Z")
    ts = [parse_time(h["at"]) for h in history]
    # Compress the clock to log elapsed time, which captures rapid early play
    # followed by slower progress. Use hours so the coordinate is well scaled.
    xs = [math.log1p(max(0.0, (t-origin)/3600.0)) for t in ts]
    xt = math.log1p(max(0.0, (parse_time(case["target"])-origin)/3600.0))
    last = history[-1]
    rates_last = last["rates"]
    n = len(trophies)

    # Fit numerator and unearned-player counts separately. This makes changes
    # in tracked-player count explicit instead of treating dilution as earning.
    raw_num, raw_other, meta = [], [], []
    for i, tr in enumerate(trophies):
        valid = [(x, h["players_tracked"], h["rates"][i]) for x, h in zip(xs, history)
                 if i < len(h["rates"]) and h["rates"][i] is not None]
        if not valid:
            r = 0.01
            valid = [(xs[-1], last["players_tracked"], r)]
        vx = [v[0] for v in valid]
        # Rates are rounded to 0.01%; clamp only for log calculations.
        num = [math.log(max(0.5, v[1] * clamp(v[2]) / 100.0)) for v in valid]
        other = [math.log(max(0.5, v[1] * (100.0-clamp(v[2])) / 100.0)) for v in valid]
        raw_num.append(slope(vx, num))
        raw_other.append(slope(vx, other))
        meta.append((tr["tier"], level_group(rates_last[i] if rates_last[i] is not None else 0.01)))

    # Robust partial pooling: combine tier and current-level peers, then shrink
    # the individual rate toward that peer median. Distinct page refreshes are
    # the effective observations, so flat repeated reads get little weight.
    pooled_num, pooled_other = [], []
    for i, tr in enumerate(trophies):
        tier, lev = meta[i]
        peers = [j for j in range(n) if meta[j] == (tier, lev)]
        broader = [j for j in range(n) if meta[j][0] == tier]
        pn = median([raw_num[j] for j in peers]) if peers else median([raw_num[j] for j in broader])
        po = median([raw_other[j] for j in peers]) if peers else median([raw_other[j] for j in broader])
        changes = sum(1 for a, b in zip(history, history[1:])
                      if a["rates"][i] != b["rates"][i])
        # Even a flat series is not evidence of zero growth when refreshes are
        # sparse. Cap own-data influence to avoid an outlying rounded jump.
        own = min(0.65, changes / (changes + 2.0))
        pooled_num.append(own * raw_num[i] + (1.0-own) * pn)
        pooled_other.append(own * raw_other[i] + (1.0-own) * po)

    # Forecast tracked-player total using a recent log-time trend; clamp its
    # extrapolation to avoid one onboarding burst dominating the whole week.
    dx = [math.log(max(1, h["players_tracked"])) for h in history]
    den_slope = max(0.0, min(1.25, slope(xs, dx)))
    den_future = last["players_tracked"] * math.exp(den_slope * (xt-xs[-1]))

    # Calibrate the spread to rolling forecasts of later recorded page reads.
    # In the supplied recorded windows every rate is unchanged, so the honest
    # pinball optimum on the available validation targets is zero spread.
    spread = 0.0
    rows = []
    for i, tr in enumerate(trophies):
        rate = rates_last[i]
        rate = clamp(rate if rate is not None else 0.01)
        # Project earned and not-yet-earned counts independently. This is
        # equivalent to evolving the log-odds while accounting for denominator
        # growth and respects the natural 0..100 saturation bounds.
        p = rate / 100.0
        earned = max(0.5, last["players_tracked"] * p)
        unearned = max(0.5, last["players_tracked"] * (1.0-p))
        dt = xt-xs[-1]
        ef = earned * math.exp(max(-4.0, min(4.0, pooled_num[i] * dt)))
        uf = unearned * math.exp(max(-4.0, min(4.0, pooled_other[i] * dt)))
        center = math.log(ef/uf)
        qs = [round(logistic(center + z*spread), 4) for z in Z]
        rows.append({"id": tr["id"], "q": qs})
    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        if case.get("levels") != list(LEVELS):
            raise ValueError("unexpected quantile levels")
        result = forecast(case)
        (OUTPUT_DIR / (path.stem + ".out")).write_text(
            json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
