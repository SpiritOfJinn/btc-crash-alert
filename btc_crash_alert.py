"""Bitcoin ultra-crash alert.

Runs hourly on GitHub Actions. Pulls hourly BTC-USD prices from Coinbase (free, no key)
and pushes an urgent ntfy notification to your phone when bitcoin is:
  - down 20%+ from its high in the last 24 hours, or
  - down 30%+ from its high in the last 7 days.

It alerts once when a threshold is first crossed, not every hour while it stays crashed.
On a push to the repo (or a manual run) it sends a test notification instead.
"""
import json
import os
import urllib.request

NTFY_TOPIC = os.environ["NTFY_TOPIC"]   # stored as a GitHub secret, not in the code
DAY_DROP = 0.20                   # 20% in 24 hours
WEEK_DROP = 0.30                  # 30% in 7 days
COINBASE = "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600"


def get_hourly_candles():
    """Return hourly candles oldest-first as (time, low, high, open, close)."""
    req = urllib.request.Request(COINBASE, headers={"User-Agent": "btc-crash-alert"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    data.sort(key=lambda c: c[0])
    return [(c[0], c[1], c[2], c[3], c[4]) for c in data]


def drop_from_high(candles, end, hours):
    """Percent drop of the close at index `end` from the highest high in the prior `hours` candles."""
    window = candles[max(0, end - hours + 1): end + 1]
    peak = max(c[2] for c in window)
    close = candles[end][4]
    return 1 - close / peak, peak, close


def notify(title, message, priority="urgent", tags="rotating_light"):
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": title, "Priority": priority, "Tags": tags},
    )
    urllib.request.urlopen(req, timeout=30)


def check(candles):
    """Return alert messages for thresholds crossed in the latest hour."""
    now, prev = len(candles) - 1, len(candles) - 2
    alerts = []
    for hours, limit, label in ((24, DAY_DROP, "24 hours"), (168, WEEK_DROP, "7 days")):
        drop_now, peak, close = drop_from_high(candles, now, hours)
        drop_prev, _, _ = drop_from_high(candles, prev, hours)
        print(f"{label}: down {drop_now:.1%} from high (alert at {limit:.0%})")
        if drop_now >= limit and drop_prev < limit:
            alerts.append(
                f"Bitcoin is down {drop_now:.0%} in {label}: "
                f"${peak:,.0f} -> ${close:,.0f}."
            )
    return alerts


def main():
    candles = get_hourly_candles()
    if os.environ.get("TEST") == "true":
        price = candles[-1][4]
        notify("BTC alert is set up", f"Test only. Bitcoin is ${price:,.0f}. "
               "You'll get an urgent alert on a 20%/24h or 30%/week drop.",
               priority="default", tags="white_check_mark")
        print("Test notification sent.")
        return
    for msg in check(candles):
        notify("BITCOIN CRASH", msg)
        print("ALERT SENT:", msg)


if __name__ == "__main__":
    main()
