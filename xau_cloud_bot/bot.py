#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XAU/USD Telegram Signal Bot - Cloud version (pure stdlib)
Chạy 24/7 trên Railway / Render / PythonAnywhere
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH = os.path.join(BASE_DIR, "bot_state.json")
LOG_PATH = os.path.join(BASE_DIR, "xau_bot.log")


def load_config() -> dict:
    default = {
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN"),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID"),
        "gold_symbol": "GC=F",
        "poll_interval_sec": 300,
        "risk_usd_per_trade": 30.0,
        "atr_sl_mult": 1.5,
        "rr_ratio": 1.8,
        "min_sl_price": 4.0,
        "min_readiness_score": 3,
        "news_rss_urls": [
            "https://feeds.marketwatch.com/marketwatch/marketpulse/",
            "https://www.investing.com/rss/news_25.rss",
        ],
        "high_impact_keywords": [
            "fed", "fomc", "cpi", "inflation", "powell", "payroll", "nfp",
            "rate", "treasury", "yield", "gold", "xau", "geopolitical", "war", "tariff",
        ],
    }
    # Ưu tiên biến môi trường (an toàn hơn khi deploy cloud)
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        default["telegram_bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN")
    if os.getenv("TELEGRAM_CHAT_ID"):
        default["telegram_chat_id"] = os.getenv("TELEGRAM_CHAT_ID")

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            default.update(user)
        except Exception:
            pass
    return default


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("xau_bot")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    try:
        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass
    return logger


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"last_alert_key": "", "last_run_utc": None}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last_alert_key": "", "last_run_utc": None}


def save_state(state: dict) -> None:
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def send_telegram(token: str, chat_id: str, text: str, logger: logging.Logger) -> bool:
    if not token or not chat_id or "YOUR_BOT_TOKEN" in token or "YOUR_CHAT_ID" in str(chat_id):
        logger.warning("Chua cau hinh TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
        logger.info("Noi dung goi y:\n%s", text)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": str(chat_id),
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        return True
    except Exception as exc:
        logger.error("Loi gui Telegram: %s", exc)
        return False


def http_get_json(url: str, retries: int = 2) -> Optional[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; XAUBot/1.0)"}
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_err  # type: ignore


def fetch_candles(symbol: str, limit: int = 150) -> List[dict]:
    encoded = urllib.parse.quote(symbol)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range=1mo&interval=1h"
    data = http_get_json(url)
    if not data or "chart" not in data or not data["chart"].get("result"):
        raise RuntimeError("Yahoo Finance tra ve du lieu rong")
    result = data["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    quote = result["indicators"]["quote"][0]
    volumes = quote.get("volume") or [None] * len(timestamps)
    candles = []
    for i, ts in enumerate(timestamps):
        o = quote["open"][i]
        h = quote["high"][i]
        l = quote["low"][i]
        c = quote["close"][i]
        v = volumes[i]
        if None not in (o, h, l, c):
            candles.append({
                "ts": ts, "open": float(o), "high": float(h),
                "low": float(l), "close": float(c),
                "volume": float(v) if v is not None else 0.0,
            })
    return candles[-limit:]


def ema_series(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    out = [values[0]]
    for x in values[1:]:
        out.append(alpha * x + (1.0 - alpha) * out[-1])
    return out


def calc_rsi_wilder(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calc_atr_wilder(candles: List[dict], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 5.0
    trs = []
    for i in range(1, len(candles)):
        cur = candles[i]
        prev = candles[i - 1]["close"]
        tr = max(cur["high"] - cur["low"], abs(cur["high"] - prev), abs(cur["low"] - prev))
        trs.append(tr)
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr


def fetch_headlines(rss_urls: List[str], keywords: List[str], logger: logging.Logger) -> List[str]:
    matched = []
    headers = {"User-Agent": "Mozilla/5.0"}
    kw = [k.lower() for k in keywords]
    for url in rss_urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                root = ET.fromstring(resp.read())
            for item in root.findall(".//item")[:25]:
                title_el = item.find("title")
                if title_el is not None and title_el.text:
                    title = title_el.text.strip()
                    if any(k in title.lower() for k in kw) and title not in matched:
                        matched.append(title)
        except Exception as e:
            logger.warning("RSS loi %s: %s", url, e)
    return matched[:5]


def evaluate(cfg: dict, logger: logging.Logger) -> Tuple[Optional[str], Optional[int]]:
    try:
        candles = fetch_candles(cfg.get("gold_symbol", "GC=F"))
    except Exception as e:
        logger.error("Loi lay gia: %s", e)
        return None, None

    if len(candles) < 80:
        logger.info("Chua du du lieu H1")
        return None, None

    closed = candles[:-1]
    closes = [c["close"] for c in closed]
    volumes = [c["volume"] for c in closed]

    ema20 = ema_series(closes, 20)
    ema50 = ema_series(closes, 50)
    rsi = calc_rsi_wilder(closes, 14)
    atr = calc_atr_wilder(closed, 14)

    last_price = candles[-1]["close"]
    last_closed = closed[-1]["close"]
    e20, e50 = ema20[-1], ema50[-1]
    closed_ts = closed[-1]["ts"]

    vol_avg = sum(volumes[-20:]) / 20.0 if len(volumes) >= 20 else 0.0
    volume_ok = vol_avg > 0 and volumes[-1] >= vol_avg * 0.65

    headlines = fetch_headlines(
        cfg.get("news_rss_urls", []),
        cfg.get("high_impact_keywords", []),
        logger,
    )

    score = 0
    direction = None
    reasons = []

    if e20 > e50 and last_closed > e20:
        direction = "BUY"
        score += 1
        reasons.append("Xu huong tang (EMA20 > EMA50)")
    elif e20 < e50 and last_closed < e20:
        direction = "SELL"
        score += 1
        reasons.append("Xu huong giam (EMA20 < EMA50)")

    if direction == "BUY" and 42 <= rsi <= 68:
        score += 1
        reasons.append(f"RSI phu hop ({rsi:.1f})")
    elif direction == "SELL" and 32 <= rsi <= 58:
        score += 1
        reasons.append(f"RSI phu hop ({rsi:.1f})")

    if atr > 0 and direction and abs(last_closed - e20) >= atr * 0.15:
        score += 1
        reasons.append(f"ATR={atr:.2f}")

    if volume_ok:
        score += 1
        reasons.append("Volume OK")

    if headlines and score >= 2:
        score += 1
        reasons.append(f"Co {len(headlines)} tin quan trong")

    logger.info(
        "Gia %.2f | EMA20 %.2f | EMA50 %.2f | RSI %.1f | ATR %.2f | %s | Diem %d/5",
        last_price, e20, e50, rsi, atr, direction or "NONE", score
    )

    min_score = int(cfg.get("min_readiness_score", 3))
    if not direction or score < min_score:
        return None, closed_ts

    atr_mult = float(cfg.get("atr_sl_mult", 1.5))
    rr = float(cfg.get("rr_ratio", 1.8))
    min_sl = float(cfg.get("min_sl_price", 4.0))
    risk = float(cfg.get("risk_usd_per_trade", 30.0))

    sl_dist = max(atr * atr_mult, min_sl)
    tp_dist = sl_dist * rr
    lot = max(0.01, round(risk / (sl_dist * 100.0), 2))

    if direction == "BUY":
        sl = round(last_price - sl_dist, 2)
        tp = round(last_price + tp_dist, 2)
    else:
        sl = round(last_price + sl_dist, 2)
        tp = round(last_price - tp_dist, 2)

    news = "\n".join(f"- {h}" for h in headlines) if headlines else "- Khong co tin noi bat"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    msg = (
        f"[GOI Y XAU/USD - DIEM {score}/5]\n"
        f"Thoi gian: {now}\n"
        f"- Huong: {direction}\n"
        f"- Gia: ~{last_price:.2f}\n"
        f"- SL: {sl:.2f} (~{sl_dist:.2f})\n"
        f"- TP: {tp:.2f} (~{tp_dist:.2f} | R:R 1:{rr:.1f})\n"
        f"- Lot goi y (rui ro ~{risk:.0f}$): {lot:.2f}\n"
        f"- Ly do: {'; '.join(reasons)}\n"
        f"- Tin:\n{news}\n"
        f"(Chi la goi y tham khao)"
    )
    return msg, closed_ts


def run_once(cfg: dict, state: dict, logger: logging.Logger) -> dict:
    msg, closed_ts = evaluate(cfg, logger)
    if msg and closed_ts is not None:
        key = f"{closed_ts}_{msg[:50]}"
        if key != state.get("last_alert_key", ""):
            if send_telegram(cfg["telegram_bot_token"], cfg["telegram_chat_id"], msg, logger):
                state["last_alert_key"] = key
                logger.info("Da gui tin hieu ve Telegram")
            else:
                logger.info("Co tin hieu nhung chua gui duoc (kiem tra token)")
        else:
            logger.info("Tin hieu trung, bo qua")
    else:
        logger.info("Chua du diem de xuat lenh")
    state["last_run_utc"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    return state


def main():
    cfg = load_config()
    logger = setup_logger()
    state = load_state()

    once = "--once" in sys.argv
    logger.info("=== XAU Signal Bot (Cloud) khoi dong ===")
    logger.info("Mode: %s | Interval: %ss", "once" if once else "background", cfg.get("poll_interval_sec", 300))

    if once:
        run_once(cfg, state, logger)
        return

    interval = max(60, int(cfg.get("poll_interval_sec", 300)))
    while True:
        try:
            state = run_once(cfg, state, logger)
        except Exception as e:
            logger.error("Loi vong lap: %s", e)
        time.sleep(interval)


if __name__ == "__main__":
    main()
