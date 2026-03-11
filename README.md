# Market AI Bot

Market AI Bot, Investing.com bağlantısından enstrüman türünü çözümleyip uygun veri sağlayıcısından günlük OHLCV verisi çekerek çoklu teknik indikatör hesaplayan Python tabanlı bir analiz aracıdır.

Bu proje eğitim, araştırma ve teknik analiz pratiği amacıyla geliştirilmiştir. Üretilen çıktılar yatırım tavsiyesi değildir.

## Özellikler

- Investing.com URL çözümleme
- Equity ve currency pair desteği
- Stooq ve Yahoo Finance üzerinden veri çekme
- Günlük OHLCV veri temizleme ve standardizasyon
- Çoklu teknik indikatör hesaplama
- Rule-based sinyal özeti üretme
- AI araçlarına verilebilecek JSON çıktı üretme
- Teknik analiz prompt çıktısı üretme

## Desteklenen Varlık Türleri

- Hisse senetleri  
  Örnek: `https://www.investing.com/equities/cloudflare-inc`

- Döviz / emtia pariteleri  
  Örnek:  
  `https://www.investing.com/currencies/eur-usd`  
  `https://www.investing.com/currencies/usd-jpy`  
  `https://www.investing.com/currencies/xau-usd`

## Hesaplanan İndikatörler

- RSI (Wilder)
- EMA 20 / 50 / 200
- MACD
- Bollinger Bands
- ATR
- ADX
- +DI / -DI
- OBV
- StochRSI
- MFI
- SuperTrend

## Nasıl Çalışır

Script çalıştırıldığında kullanıcıdan bir Investing.com linki ister.  
Ardından:

1. URL içinden varlık türünü çözümler
2. Uygun sembol adaylarını oluşturur
3. Veri sağlayıcısından günlük fiyat verisini çeker
4. OHLCV verisini temizler
5. Teknik indikatörleri hesaplar
6. Son bar için özet snapshot çıkarır
7. Piyasa rejimini yorumlar
8. Rule-based sinyal özeti üretir
9. AI kullanımına uygun JSON ve prompt çıktısı verir

## Kurulum

Önce gerekli paketleri yükleyin:

```bash
pip install -r requirements.txt
