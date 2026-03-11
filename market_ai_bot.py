import re
import sys
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests


# ============================================================
# 0) Güvenlik / Uyarı
# ============================================================
DISCLAIMER = """
[Uyarı]
Bu script yalnızca eğitim/analiz amaçlı teknik indikatör hesaplar.
Yatırım tavsiyesi değildir. Her veri kaynağı farklı kapanış/oturum
tanımına sahip olabilir; sonuçlar platforma göre küçük farklılık gösterebilir.
""".strip()


# ============================================================
# 1) URL / Enstrüman çözümleme
# ============================================================
def normalize_url(url: str) -> str:
    url = url.strip()
    url = url.replace("tr.investing.com", "www.investing.com")
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    if not url.startswith("https://"):
        url = "https://" + url
    return url


def parse_investing_url(url: str) -> Dict[str, str]:
    """
    Supports:
      https://www.investing.com/equities/<slug>
      https://www.investing.com/currencies/<slug>  (xau-usd, eur-usd, usd-jpy)
    """
    url = normalize_url(url)
    m = re.search(r"investing\.com/([^/?#]+)/([^/?#]+)", url)
    if not m:
        return {"kind": "unknown", "slug": ""}

    section = m.group(1).lower()
    slug = m.group(2).lower()

    if section == "equities":
        return {"kind": "equity", "slug": slug}
    if section == "currencies":
        return {"kind": "currency_pair", "slug": slug}

    return {"kind": "unknown", "slug": slug}


def try_extract_equity_ticker(url: str, timeout: int = 15) -> Optional[str]:
    """
    Best-effort: Investing equity HTML içinden ticker yakala.
    Bloklanırsa None döner.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        html = r.text
    except Exception:
        return None

    # Örn: "Cloudflare Inc (NET) ..."
    m = re.search(r"\(([A-Z0-9.\-]{1,15})\)", html)
    if m and m.group(1).isupper():
        return m.group(1).strip()

    # json içinde ticker/symbol geçebiliyor
    m = re.search(r'"ticker"\s*:\s*"([A-Z0-9.\-]{1,15})"', html)
    if m:
        return m.group(1).strip()

    m = re.search(r'"symbol"\s*:\s*"([A-Z0-9.\-]{1,15})"', html)
    if m:
        return m.group(1).strip()

    return None


def resolve_symbols(info: Dict[str, str], investing_url: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Returns:
      display_name,
      candidates = [(provider, symbol), ...]  provider: "stooq" | "yfinance"
    """
    kind = info["kind"]
    slug = info["slug"]

    if kind == "equity":
        ticker = try_extract_equity_ticker(investing_url)
        if not ticker:
            ticker = input(
                "Ticker bulunamadı. Ticker yaz (örn NET, AAPL):\n> ").strip().upper()
        if not ticker:
            raise RuntimeError("Ticker boş olamaz.")

        # Stooq: net.us, aapl.us (US varsayımı)
        stooq_sym = f"{ticker.lower()}.us"
        # yfinance: NET, AAPL
        yf_sym = ticker
        return f"Equity {ticker}", [("stooq", stooq_sym), ("yfinance", yf_sym)]

    if kind == "currency_pair":
        if "-" not in slug:
            raise RuntimeError(
                "Currency slug formatı bekleniyor (örn xau-usd, eur-usd).")

        base, quote = slug.split("-", 1)
        base_u, quote_u = base.upper(), quote.upper()

        # yfinance FX:
        # USDJPY -> "JPY=X"
        # EURUSD -> "EURUSD=X"
        # XAUUSD -> "XAUUSD=X"
        if base_u == "USD":
            yf_sym = f"{quote_u}=X"
        else:
            yf_sym = f"{base_u}{quote_u}=X"

        # Stooq: eurusd, usdjpy, xauusd (best-effort)
        stooq_sym = f"{base.lower()}{quote.lower()}"

        return f"Pair {base_u}/{quote_u}", [("stooq", stooq_sym), ("yfinance", yf_sym)]

    raise RuntimeError(
        "Desteklenmeyen link. Sadece /equities/ ve /currencies/ destekleniyor.")


# ============================================================
# 2) Veri çekme (OHLCV)
# ============================================================
def clean_ohlcv_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Date + OHLCV temizliği:
      - Date parse
      - OHLC numeric
      - Close>0 filtre
      - duplicate Date temizle
    """
    out = df.copy()

    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # Zorunlu OHLC
    out = out.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    out = out[out["Close"] > 0]
    out = out.sort_values("Date")
    out = out.drop_duplicates(
        subset=["Date"], keep="last").reset_index(drop=True)

    # Volume yoksa 0 yap
    if "Volume" not in out.columns:
        out["Volume"] = 0.0
    else:
        out["Volume"] = out["Volume"].fillna(0.0)

    return out


def fetch_stooq_daily(symbol: str) -> pd.DataFrame:
    """
    Stooq daily CSV:
      equities: net.us
      fx/commod: xauusd, eurusd, usdjpy
    """
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    df = pd.read_csv(url)
    needed = {"Date", "Open", "High", "Low", "Close"}
    if df.empty or not needed.issubset(set(df.columns)):
        raise RuntimeError("Stooq veri boş/uyumsuz.")
    # Volume bazen var
    cols = [c for c in ["Date", "Open", "High",
                        "Low", "Close", "Volume"] if c in df.columns]
    return clean_ohlcv_df(df[cols])


def fetch_yfinance_daily(symbol: str, period: str = "2y") -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as e:
        raise RuntimeError("yfinance yok. `pip install yfinance`") from e

    data = yf.download(symbol, period=period, interval="1d",
                       auto_adjust=False, progress=False)
    if data is None or data.empty:
        raise RuntimeError("yfinance veri döndürmedi.")

    df = data.reset_index()
    if "Date" not in df.columns and "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})

    # yfinance kolon isimleri standart
    cols = ["Date", "Open", "High", "Low", "Close"]
    if "Volume" in df.columns:
        cols.append("Volume")
    df = df[cols]
    return clean_ohlcv_df(df)


def fetch_ohlcv_series(candidates: List[Tuple[str, str]]) -> Tuple[str, pd.DataFrame]:
    errors = []
    for provider, symbol in candidates:
        try:
            if provider == "stooq":
                return f"Stooq ({symbol})", fetch_stooq_daily(symbol)
            if provider == "yfinance":
                return f"Yahoo Finance ({symbol})", fetch_yfinance_daily(symbol)
            errors.append(f"Unknown provider: {provider}")
        except Exception as e:
            errors.append(f"{provider}:{symbol} -> {e}")
    raise RuntimeError("Veri çekilemedi:\n" +
                       "\n".join(" - " + x for x in errors))


# ============================================================
# 3) İndikatörler
# ============================================================
def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).mean()


def rsi_wilder(close: pd.Series, length: int = 14) -> pd.Series:
    """
    Wilder RSI (RMA smoothing):
      AvgGain/AvgLoss: ewm(alpha=1/length) ile aynı mantık
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    # RMA/Wilder smoothing
    avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Edge cases
    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(avg_gain != 0, 0.0)
    both_zero = (avg_gain == 0) & (avg_loss == 0)
    rsi = rsi.where(~both_zero, 50.0)

    return rsi


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(close: pd.Series, length: int = 20, stdev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    mid = sma(close, length)
    sd = close.rolling(length).std()
    upper = mid + stdev * sd
    lower = mid - stdev * sd
    # %B = (Close - Lower)/(Upper-Lower)
    pb = (close - lower) / (upper - lower)
    return mid, upper, lower, pb


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr


def atr_wilder(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    tr = true_range(high, low, close)
    # Wilder ATR = RMA(TR)
    return tr.ewm(alpha=1/length, adjust=False).mean()


def adx_wilder(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    ADX (Wilder):
      +DM, -DM, TR -> RMA
      +DI, -DI, DX -> ADX (RMA(DX))
    """
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    tr = true_range(high, low, close)

    atr = tr.ewm(alpha=1/length, adjust=False).mean()
    plus_dm_rma = plus_dm.ewm(alpha=1/length, adjust=False).mean()
    minus_dm_rma = minus_dm.ewm(alpha=1/length, adjust=False).mean()

    plus_di = 100 * (plus_dm_rma / atr)
    minus_di = 100 * (minus_dm_rma / atr)

    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
    adx = dx.ewm(alpha=1/length, adjust=False).mean()

    return adx, plus_di, minus_di


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = close.diff().fillna(0)
    sign = direction.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (sign * volume).cumsum()


def stoch_rsi(rsi: pd.Series, length: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    StochRSI:
      StochRSI = (RSI - min(RSI,n)) / (max(RSI,n) - min(RSI,n)) * 100
      K = SMA(StochRSI, smooth_k)
      D = SMA(K, smooth_d)
    """
    rsi_min = rsi.rolling(length).min()
    rsi_max = rsi.rolling(length).max()
    denom = (rsi_max - rsi_min)

    stoch = (rsi - rsi_min) / denom
    stoch = (stoch * 100).where(denom != 0, 0.0)

    k = stoch.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return stoch, k, d


def mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, length: int = 14) -> pd.Series:
    """
    Money Flow Index (MFI) - hacim varsa anlamlı.
    Tipik fiyat: TP = (H+L+C)/3
    Para akışı: MF = TP * Volume
    TP artarsa positive MF, azalırsa negative MF
    MFI = 100 - 100/(1 + (posMFsum/negMFsum))
    """
    if volume.fillna(0).sum() == 0:
        # Hacim yoksa (FX/spot gibi) MFI anlamsız => NA
        return pd.Series([pd.NA] * len(close), index=close.index, dtype="float64")

    tp = (high + low + close) / 3.0
    mf = tp * volume

    tp_delta = tp.diff()

    pos_mf = mf.where(tp_delta > 0, 0.0)
    neg_mf = mf.where(tp_delta < 0, 0.0).abs()

    pos_sum = pos_mf.rolling(length).sum()
    neg_sum = neg_mf.rolling(length).sum()

    mfr = pos_sum / neg_sum
    mfi_val = 100 - (100 / (1 + mfr))

    # edge cases
    mfi_val = mfi_val.where(neg_sum != 0, 100.0)
    mfi_val = mfi_val.where(pos_sum != 0, 0.0)
    both_zero = (pos_sum == 0) & (neg_sum == 0)
    mfi_val = mfi_val.where(~both_zero, 50.0)

    return mfi_val


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    """
    SuperTrend (ATR tabanlı trend filtresi)
    Dönenler:
      supertrend_line: fiyatın altında/üstünde giden çizgi
      supertrend_dir:  +1 (up) / -1 (down)
    """
    atr = atr_wilder(high, low, close, length)
    hl2 = (high + low) / 2.0

    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    final_upper = upper.copy()
    final_lower = lower.copy()

    st = pd.Series(index=close.index, dtype="float64")
    direction = pd.Series(index=close.index, dtype="float64")  # +1 / -1

    for i in range(len(close)):
        if i == 0:
            st.iat[i] = pd.NA
            direction.iat[i] = pd.NA
            continue

        # band "final" kuralları
        if pd.isna(final_upper.iat[i-1]):
            final_upper.iat[i] = upper.iat[i]
        else:
            if (upper.iat[i] < final_upper.iat[i-1]) or (close.iat[i-1] > final_upper.iat[i-1]):
                final_upper.iat[i] = upper.iat[i]
            else:
                final_upper.iat[i] = final_upper.iat[i-1]

        if pd.isna(final_lower.iat[i-1]):
            final_lower.iat[i] = lower.iat[i]
        else:
            if (lower.iat[i] > final_lower.iat[i-1]) or (close.iat[i-1] < final_lower.iat[i-1]):
                final_lower.iat[i] = lower.iat[i]
            else:
                final_lower.iat[i] = final_lower.iat[i-1]

        # yön flip kuralı
        prev_dir = direction.iat[i-1]
        if pd.isna(prev_dir):
            # ilk anlamlı yönü fiyat konumuna göre kur
            if close.iat[i] >= final_lower.iat[i]:
                direction.iat[i] = 1.0
            else:
                direction.iat[i] = -1.0
        elif prev_dir == 1.0:
            direction.iat[i] = - \
                1.0 if close.iat[i] < final_lower.iat[i] else 1.0
        else:
            direction.iat[i] = 1.0 if close.iat[i] > final_upper.iat[i] else -1.0

        st.iat[i] = final_lower.iat[i] if direction.iat[i] == 1.0 else final_upper.iat[i]

    return st, direction


# ============================================================
# 4) Rejim + sinyal özetleri (rule-based)
# ============================================================
@dataclass
class Snapshot:
    date: str
    close: float
    rsi: float
    ema20: float
    ema50: float
    ema200: float
    macd: float
    macd_signal: float
    macd_hist: float
    bb_mid: float
    bb_upper: float
    bb_lower: float
    bb_pb: float
    atr: float
    adx: float
    plus_di: float
    minus_di: float
    volume: float
    obv: float
    stochrsi_k: float
    stochrsi_d: float
    mfi: float
    supertrend: float
    supertrend_dir: float


def regime_from_adx_ema(s: Snapshot) -> Dict[str, str]:
    # Trend gücü
    if s.adx >= 25:
        strength = "trending"
    elif s.adx >= 20:
        strength = "weak_trend"
    else:
        strength = "ranging"

    # Trend yönü (basit): EMA50/EMA200 + Close konumu
    if s.ema50 > s.ema200 and s.close > s.ema50:
        direction = "up"
    elif s.ema50 < s.ema200 and s.close < s.ema50:
        direction = "down"
    else:
        direction = "mixed"

    return {"regime": strength, "trend_direction": direction}


def rsi_band_by_regime(regime: Dict[str, str]) -> Tuple[int, int]:
    """
    Güçlü trendlerde RSI eşikleri kayabilir:
      Uptrend: 40-80
      Downtrend: 20-60
      Range: 30-70
    """
    if regime["regime"] in ("trending", "weak_trend"):
        if regime["trend_direction"] == "up":
            return 40, 80
        if regime["trend_direction"] == "down":
            return 20, 60
    return 30, 70


def build_signals(df: pd.DataFrame, snap: Snapshot, regime: Dict[str, str], period: int) -> List[str]:
    signals = []

    low_thr, high_thr = rsi_band_by_regime(regime)
    if snap.rsi >= high_thr:
        signals.append(
            f"RSI yüksek bölgede (>= {high_thr}). Momentum güçlü olabilir ama kısa vadede aşırılaşma riski var.")
    elif snap.rsi <= low_thr:
        signals.append(
            f"RSI düşük bölgede (<= {low_thr}). Satış baskısı yüksek olabilir ama tepki ihtimali artabilir.")
    else:
        signals.append(f"RSI nötr bölgede ({low_thr}-{high_thr}).")

    # MACD durumları
    if snap.macd_hist > 0 and snap.macd > snap.macd_signal:
        signals.append(
            "MACD pozitif: MACD > Signal ve histogram > 0 (momentum yukarı).")
    elif snap.macd_hist < 0 and snap.macd < snap.macd_signal:
        signals.append(
            "MACD negatif: MACD < Signal ve histogram < 0 (momentum aşağı).")
    else:
        signals.append("MACD kararsız bölgede (çapraz / zayıf histogram).")

    # --- SuperTrend filtresi (trend yön teyidi) ---
    if pd.notna(snap.supertrend_dir) and pd.notna(snap.supertrend):
        if snap.supertrend_dir == 1.0 and snap.close > snap.supertrend:
            signals.append(
                "SuperTrend yukarı: trend filtresi pozitif (RSI sinyalleri daha 'trend-follow' yorumlanır).")
        elif snap.supertrend_dir == -1.0 and snap.close < snap.supertrend:
            signals.append(
                "SuperTrend aşağı: trend filtresi negatif (RSI sinyalleri daha 'trend-follow' yorumlanır).")
        else:
            signals.append(
                "SuperTrend geçiş bölgesi: trend flip/kararsızlık ihtimali var (false signal riski).")

    # --- StochRSI (RSI'nin kısa vadeli hızını ölçer) ---
    if pd.notna(snap.stochrsi_k) and pd.notna(snap.stochrsi_d):
        if snap.stochrsi_k >= 80:
            signals.append(
                "StochRSI yüksek (>=80): kısa vadede aşırılaşma/yorulma riski artabilir.")
        elif snap.stochrsi_k <= 20:
            signals.append(
                "StochRSI düşük (<=20): kısa vadede tepki ihtimali artabilir.")

        # K/D kesişim (son 2 bar ile)
        prev_k = df["STOCHRSI_K"].iloc[-2]
        prev_d = df["STOCHRSI_D"].iloc[-2]
        if pd.notna(prev_k) and pd.notna(prev_d):
            if prev_k <= prev_d and snap.stochrsi_k > snap.stochrsi_d:
                signals.append(
                    "StochRSI K, D’yi yukarı kesti: kısa vadeli momentum dönüş işareti olabilir.")
            elif prev_k >= prev_d and snap.stochrsi_k < snap.stochrsi_d:
                signals.append(
                    "StochRSI K, D’yi aşağı kesti: kısa vadeli momentum zayıflıyor olabilir.")

    # --- MFI (hacim bazlı RSI benzeri) ---
    # Not: Volume 0 olan enstrümanlarda (FX/spot) MFI zaten NaN döner.
    if snap.volume > 0 and pd.notna(snap.mfi):
        if snap.mfi >= 80:
            signals.append(
                "MFI yüksek (>=80): para akışı tarafında aşırı alım benzeri bölge.")
        elif snap.mfi <= 20:
            signals.append(
                "MFI düşük (<=20): para akışı tarafında aşırı satım benzeri bölge.")

    # Bollinger %B
    if snap.bb_pb >= 1.0:
        signals.append(
            "Bollinger üst band dışı/teması (%B >= 1). Volatil aşırılık olabilir.")
    elif snap.bb_pb <= 0.0:
        signals.append(
            "Bollinger alt band dışı/teması (%B <= 0). Volatil aşırılık olabilir.")
    else:
        signals.append(f"Bollinger içinde (%B={snap.bb_pb:.2f}).")

    # Trend rejimi
    signals.append(
        f"Rejim: {regime['regime']} | Trend yönü: {regime['trend_direction']} (ADX={snap.adx:.1f}).")

    # ATR artıyor mu? (son 10 bar eğilim)
    atr_slope = df["ATR"].tail(10).diff().mean()
    if pd.notna(atr_slope) and atr_slope > 0:
        signals.append(
            "ATR yükseliyor: volatilite artış eğiliminde (stop/pozisyon boyutu dikkat).")
    elif pd.notna(atr_slope) and atr_slope < 0:
        signals.append("ATR düşüyor: volatilite azalma eğiliminde.")

    # Volume/OBV (volume anlamlıysa)
    if snap.volume > 0:
        vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
        if pd.notna(vol_sma) and snap.volume > 1.2 * vol_sma:
            signals.append(
                "Hacim ortalamanın üstünde: hareket daha 'ciddi' olabilir.")
        if df["OBV"].tail(5).diff().mean() > 0:
            signals.append(
                "OBV artış eğiliminde: alım baskısı destekleniyor olabilir.")
        elif df["OBV"].tail(5).diff().mean() < 0:
            signals.append(
                "OBV düşüş eğiliminde: satış baskısı destekleniyor olabilir.")
    else:
        signals.append(
            "Hacim verisi yok/0 (FX/spot endekslerde normal olabilir).")

    return signals


# ============================================================
# 5) AI için çıktı (JSON + Prompt)
# ============================================================
def build_ai_payload(display: str, source: str, period: int, snap: Snapshot, regime: Dict[str, str], signals: List[str]) -> Dict:
    payload = {
        "instrument": display,
        "data_source": source,
        "timeframe": "1D",
        "rsi_period": period,
        "latest": {
            "date": snap.date,
            "close": snap.close,
            "volume": snap.volume,
            "indicators": {
                "rsi": snap.rsi,
                "ema20": snap.ema20,
                "ema50": snap.ema50,
                "ema200": snap.ema200,
                "macd": snap.macd,
                "macd_signal": snap.macd_signal,
                "macd_hist": snap.macd_hist,
                "bb_mid": snap.bb_mid,
                "bb_upper": snap.bb_upper,
                "bb_lower": snap.bb_lower,
                "bb_percent_b": snap.bb_pb,
                "atr": snap.atr,
                "adx": snap.adx,
                "plus_di": snap.plus_di,
                "minus_di": snap.minus_di,
                "obv": snap.obv,
                "stochrsi_k": snap.stochrsi_k,
                "stochrsi_d": snap.stochrsi_d,
                "mfi": snap.mfi,
                "supertrend": snap.supertrend,
                "supertrend_dir": snap.supertrend_dir,

            },
            "regime": regime,
        },
        "signals": signals,
        "notes": [
            "Bu çıktı teknik göstergelerden türetilmiş özet sinyallerdir. Yatırım tavsiyesi değildir.",
            "Farklı veri sağlayıcıları (Investing vs Stooq vs Yahoo) kapanış değerlerinde küçük fark yaratabilir."
        ],
    }
    return payload


def build_ai_prompt(payload: Dict) -> str:
    # LLM’e vereceğin prompt (Türkçe)
    return f"""
Sen bir piyasa analisti gibi çalış ama YATIRIM TAVSİYESİ VERME.
Aşağıdaki teknik göstergelerden yola çıkarak:

1) Piyasa rejimini (trend mi range mi) ve bunun RSI yorumunu açıkla.
2) RSI, MACD, Bollinger, EMA yapısı birbirini teyit ediyor mu? Çelişiyor mu?
3) 2-3 senaryo üret:
   - trend devam
   - düzeltme/pullback
   - yataylaşma (mean reversion)
4) Riskleri söyle: volatilite (ATR), zayıf teyit (ADX düşük vb.), yanlış sinyal ihtimali.
5) Son olarak “izlenmesi gereken” 3-5 madde çıkar (ör: RSI 50 altına iner mi, MACD hist yön değiştirir mi, BB dışına taşma vb.)
Not: Nihai karar kullanıcıya ait. Tavsiye yok.

TEKNİK VERİ (JSON):
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


# ============================================================
# 6) İndikatör bilgileri (bot içinden de yazdırıyoruz)
# ============================================================
INDICATOR_GUIDE = """
İndikatör Kısa Rehberi

- RSI (Wilder):
  Son N barın (genelde 14) kapanış değişimlerinden momentum ölçer (0-100).
  Range piyasada 30/70 işe yarar; güçlü trendde eşikler kayabilir (ör: uptrend 40/80).

- EMA (20/50/200):
  Trend filtresi ve dinamik destek/direnç. EMA50>EMA200 genelde uzun vadeli yukarı rejim izlenimi.

- MACD (12,26,9):
  EMA farkı üzerinden momentum/trend geçişi. Histogram yön değişimi “momentum zayıflıyor mu?” için yararlı.

- Bollinger Bands (20,2):
  Volatilite bandı. Üst/alt band temasları aşırılık gösterebilir. %B ile 0-1 dışına taşma takip edilir.

- ATR (14):
  Volatilite ölçer. ATR yükseliyorsa stop mesafesi/pozisyon boyutu daha dikkatli ayarlanır.

- ADX (14) +DI/-DI:
  Trend gücü ölçer. ADX>25 trend güçlü sayılır. +DI > -DI genelde yukarı baskı.

- OBV (hacim varsa):
  Hacim akışı. Fiyat + OBV uyumu/uyumsuzluğu teyit için kullanılabilir.

Not:
FX/Emtia spot verilerinde “Volume” çoğu zaman anlamlı olmayabilir.
""".strip()


# ============================================================
# 7) Main
# ============================================================
def main():
    print(DISCLAIMER)
    print("\n--- Market AI Bot (RSI + Multi-Indicator) ---")

    url = input(
        "Investing linki yapıştır (/equities/ veya /currencies/):\n> ").strip()
    if not url:
        print("Link boş olamaz.")
        sys.exit(1)

    url = normalize_url(url)
    info = parse_investing_url(url)

    try:
        display, candidates = resolve_symbols(info, url)
    except Exception as e:
        print(f"HATA: {e}")
        sys.exit(1)

    p_in = input("RSI periyodu? (varsayılan 14):\n> ").strip()
    rsi_len = int(p_in) if p_in else 14

    try:
        source, ohlcv = fetch_ohlcv_series(candidates)
    except Exception as e:
        print(f"HATA: {e}")
        sys.exit(1)

    # İndikatörleri hesapla
    df = ohlcv.copy()
    df["RSI"] = rsi_wilder(df["Close"], rsi_len)

    df["EMA20"] = ema(df["Close"], 20)
    df["EMA50"] = ema(df["Close"], 50)
    df["EMA200"] = ema(df["Close"], 200)

    macd_line, macd_sig, macd_hist = macd(df["Close"], 12, 26, 9)
    df["MACD"] = macd_line
    df["MACD_SIGNAL"] = macd_sig
    df["MACD_HIST"] = macd_hist

    bb_mid, bb_upper, bb_lower, bb_pb = bollinger(df["Close"], 20, 2.0)
    df["BB_MID"] = bb_mid
    df["BB_UPPER"] = bb_upper
    df["BB_LOWER"] = bb_lower
    df["BB_PB"] = bb_pb

    df["ATR"] = atr_wilder(df["High"], df["Low"], df["Close"], 14)

    adx, plus_di, minus_di = adx_wilder(df["High"], df["Low"], df["Close"], 14)
    df["ADX"] = adx
    df["PLUS_DI"] = plus_di
    df["MINUS_DI"] = minus_di

    df["OBV"] = obv(df["Close"], df["Volume"])
    # --- EK İNDİKATÖRLER (RSI ile iyi çalışanlar) ---
    # StochRSI (RSI serisinden türetilir)
    df["STOCHRSI"], df["STOCHRSI_K"], df["STOCHRSI_D"] = stoch_rsi(
        df["RSI"], length=14, smooth_k=3, smooth_d=3)

    # MFI (hacim varsa anlamlı)
    df["MFI"] = mfi(df["High"], df["Low"], df["Close"],
                    df["Volume"], length=14)

    # SuperTrend (trend filtresi)
    df["SUPERTREND"], df["SUPERTREND_DIR"] = supertrend(
        df["High"], df["Low"], df["Close"], length=10, multiplier=3.0)

    # Son snapshot
    required = ["RSI", "EMA20", "EMA50", "EMA200",
                "MACD", "MACD_SIGNAL", "MACD_HIST",
                "BB_MID", "BB_UPPER", "BB_LOWER", "BB_PB",
                "ATR", "ADX", "PLUS_DI", "MINUS_DI",
                "OBV", "SUPERTREND", "SUPERTREND_DIR", "STOCHRSI_K", "STOCHRSI_D"]

    last = df.dropna(subset=required).iloc[-1]

    snap = Snapshot(
        date=str(pd.to_datetime(last["Date"]).date()),
        close=float(last["Close"]),
        rsi=float(last["RSI"]),
        ema20=float(last["EMA20"]),
        ema50=float(last["EMA50"]),
        ema200=float(last["EMA200"]) if pd.notna(
            last["EMA200"]) else float("nan"),
        macd=float(last["MACD"]),
        macd_signal=float(last["MACD_SIGNAL"]),
        macd_hist=float(last["MACD_HIST"]),
        bb_mid=float(last["BB_MID"]),
        bb_upper=float(last["BB_UPPER"]),
        bb_lower=float(last["BB_LOWER"]),
        bb_pb=float(last["BB_PB"]),
        atr=float(last["ATR"]),
        adx=float(last["ADX"]),
        plus_di=float(last["PLUS_DI"]),
        minus_di=float(last["MINUS_DI"]),
        volume=float(last["Volume"]),
        obv=float(last["OBV"]),
        stochrsi_k=float(last["STOCHRSI_K"]) if pd.notna(
            last["STOCHRSI_K"]) else float("nan"),
        stochrsi_d=float(last["STOCHRSI_D"]) if pd.notna(
            last["STOCHRSI_D"]) else float("nan"),
        mfi=float(last["MFI"]) if pd.notna(last["MFI"]) else float("nan"),
        supertrend=float(last["SUPERTREND"]) if pd.notna(
            last["SUPERTREND"]) else float("nan"),
        supertrend_dir=float(last["SUPERTREND_DIR"]) if pd.notna(
            last["SUPERTREND_DIR"]) else float("nan"),

    )

    regime = regime_from_adx_ema(snap)
    signals = build_signals(df, snap, regime, rsi_len)

    # Özet ekran
    print("\n==============================")
    print(f"Enstrüman: {display}")
    print(f"Veri Kaynağı: {source}")
    print(f"Son Tarih: {snap.date}")
    print(f"Close: {snap.close:.4f} | RSI({rsi_len}): {snap.rsi:.2f}")
    print(
        f"EMA20: {snap.ema20:.4f} | EMA50: {snap.ema50:.4f} | EMA200: {snap.ema200:.4f}")
    print(
        f"MACD: {snap.macd:.4f} | Signal: {snap.macd_signal:.4f} | Hist: {snap.macd_hist:.4f}")
    print(
        f"BB: mid {snap.bb_mid:.4f} | upper {snap.bb_upper:.4f} | lower {snap.bb_lower:.4f} | %B {snap.bb_pb:.2f}")
    print(
        f"ATR(14): {snap.atr:.4f} | ADX(14): {snap.adx:.2f} | +DI {snap.plus_di:.2f} | -DI {snap.minus_di:.2f}")
    print(
        f"Regime: {regime['regime']} | Trend direction: {regime['trend_direction']}")
    print(
        f"StochRSI(K/D): {snap.stochrsi_k:.2f}/{snap.stochrsi_d:.2f} | MFI(14): {snap.mfi:.2f}")
    print(f"SuperTrend: {snap.supertrend:.4f} | ST Dir: {snap.supertrend_dir}")
    print("==============================\n")

    print("--- Sinyal Özeti (rule-based) ---")
    for s in signals:
        print("•", s)

    # Son 30 satır tablo
    show_n_in = input(
        "\nTabloda kaç satır gösterilsin? (varsayılan 30):\n> ").strip()
    show_n = int(show_n_in) if show_n_in else 30

    cols = [
        "Date", "Open", "High", "Low", "Close", "Volume",
        "RSI", "EMA20", "EMA50", "EMA200",
        "MACD", "MACD_SIGNAL", "MACD_HIST",
        "BB_MID", "BB_UPPER", "BB_LOWER", "BB_PB",
        "ATR", "ADX", "PLUS_DI", "MINUS_DI", "OBV",
        "STOCHRSI_K", "STOCHRSI_D", "MFI", "SUPERTREND", "SUPERTREND_DIR"
    ]
    view = df[cols].tail(show_n).copy()

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.float_format", lambda x: f"{x:,.4f}")

    print("\n--- Son Barlar Tablosu ---")
    print(view.to_string(index=False))

    # AI payload + prompt
    payload = build_ai_payload(display, source, rsi_len, snap, regime, signals)
    prompt = build_ai_prompt(payload)

    print("\n--- AI için JSON (kopyala) ---")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    print("\n--- AI Prompt (kopyala) ---")
    print(prompt)

    # Mini rehber
    print("\n--- İndikatör Rehberi ---")
    print(INDICATOR_GUIDE)

    print("\nBitti.")


if __name__ == "__main__":
    main()
