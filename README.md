# 🛡️ H-SQLi: Hibrit Yaklaşımlı SQL Enjeksiyon Tespit Sistemi

![Python](https://img.shields.io/badge/Python-3.x-blue.svg)
![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-1.3.0-orange.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

## 📌 Projeye Genel Bakış
Günümüzde web uygulamalarının veritabanlarına yönelik en büyük siber tehditlerden biri **SQL Enjeksiyonu (SQLi)** saldırılarıdır. Geleneksel imza tabanlı (signature-based) Web Application Firewall (WAF) ve IDS sistemleri bilinen tehditleri yakalamada çok hızlı olmalarına rağmen, şekil değiştirmiş (obfuscated) sıfırıncı gün saldırılarını kaçırabilmektedir. 

Bu proje, **imza tabanlı sistemlerin hızı** ile **makine öğrenmesi (anomali tabanlı) sistemlerin zekasını** ardışık bir boru hattında (pipeline) birleştirerek yenilikçi bir **Hibrit Saldırı Tespit Sistemi (PoC)** sunmaktadır.

## ⚙️ Mimari ve Çalışma Mantığı
Sistem iki katmanlı bir güvenlik duvarı olarak çalışır:
1. **Katman 1 (İmza Motoru - Regex):** Gelen web isteklerindeki klasik saldırı kalıplarını (Totoloji, `UNION SELECT`, Yorum Satırı İstismarı) nanosaniyeler içinde tespit eder ve anında bloklar (`BLOCKED_BY_SIGNATURE`). Yapay zekayı gereksiz yükten kurtarır.
2. **Katman 2 (Yapay Zeka Motoru - Decision Tree):** İlk katmanı (Regex) atlatmak üzere tasarlanmış mantıksal saldırıları (Örn: `admin' OR 5 > 2`) veya gizlenmiş kör (blind) enjeksiyonları anlamsal (semantic) anomali tespitiyle analiz eder ve durdurur (`BLOCKED_BY_ML`).

## 📊 Performans Metrikleri
Model, ~31.000 satırlık temiz ve zararlı web trafiği içeren bir veri seti kullanılarak TF-IDF vektörizasyonu ve **Karar Ağaçları (Decision Tree)** algoritması ile eğitilmiştir. Elde edilen test (unseen data) sonuçları:

* **Accuracy (Doğruluk):** `%99.17`
* **Precision (Kesinlik):** `%99.18`
* **F1-Score:** `%98.87`

*(Not: Performans raporunun tamamına ve akademik detaylara `docs/Proje_Raporu.pdf` üzerinden ulaşabilirsiniz.)*

## 🚀 Kurulum ve Çalıştırma

### 1. Repoyu Klonlayın
```bash
git clone [https://github.com/Zuhtu-Hilmi/H-SQLi-Detector.git](https://github.com/Zuhtu-Hilmi/H-SQLi-Detector.git)
cd H-SQLi-Detector
```

### 2. Gerekli Kütüphaneleri Yükleyin
Sanal ortam (virtual environment) kullanmanız tavsiye edilir.
```bash
pip install -r requirements.txt
```

### 3. Sistemi Başlatın (İnteraktif CLI)
Hazır eğitilmiş modeli (models/model.pkl) kullanarak canlı trafik simülasyonunu başlatmak için:
```bash
python src/main.py
```

## 🧪 Canlı Test Senaryoları (Bypass Denemeleri)

Sistemi çalıştırdığınızda aşağıdaki sorguları terminale girerek katmanların tepkisini test edebilirsiniz:

| Girdi Örneği | Beklenen Karar Katmanı | Açıklama |
| :--- | :--- | :--- |
| `merhaba dunya` | 🟢 **SAFE** | Normal kullanıcı trafiği her iki katmandan da geçer. |
| `admin' OR 1=1 --` | 🔴 **Katman 1 (İmza)** | Klasik totoloji. ML yorulmadan statik olarak engellenir. |
| `admin' OR 5 > 2` | 🟠 **Katman 2 (ML)** | İmza motorunu kör eden zeki atak, anlamsal olarak ML tarafından yakalanır. |
| `1' AND (SELECT count(*) FROM users) > 0` | 🟠 **Katman 2 (ML)** | İmzasız gizli (blind) saldırı anomalisi tespit edilir. |

## 📁 Veri Seti Hakkında

Projede kullanılan modelin eğitimi için Kaggle açık kaynak veri setlerinden faydalanılmıştır. Boyut ve mahremiyet kısıtlamaları nedeniyle orijinal veri seti depoya eklenmemiş, sistemin anında çalışması için eğitilmiş .pkl dosyaları models/ dizinine dahil edilmiştir. Model eğitimini sıfırdan yapmak isterseniz kendi veri setinizi ana dizine ekleyip python src/train.py betiğini çalıştırabilirsiniz.

