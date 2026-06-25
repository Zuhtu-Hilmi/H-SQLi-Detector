"""
=============================================================================
H-SQLi Projesi - İmza Motoru ve Hibrit Dedektör (detector.py)
=============================================================================
Bu modül, SQL Enjeksiyon tespiti için iki katmanlı bir hibrit boru hattı
sunar:

  Katman 1 (İmza Tabanlı):
    - Bilinen SQLi kalıplarını Regex ile anında tespit eder.
    - Hızlıdır, sıfır gecikme ile bilinen saldırıları bloklar.

  Katman 2 (ML Tabanlı):
    - İmza filtresinden geçen sorguları, önceden eğitilmiş
      DecisionTree + TF-IDF modeli ile analiz eder.
    - Bilinmeyen / sofistike saldırıları yakalayabilir.

Dönüş Değerleri:
  "BLOCKED_BY_SIGNATURE" → İmza motoru tarafından engellendi.
  "BLOCKED_BY_ML"        → ML modeli tarafından saldırı olarak sınıflandırıldı.
  "SAFE"                 → Her iki katmandan da temiz geçti.
=============================================================================
"""

import os
import re
from typing import Tuple

import joblib


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
# Ana proje dizinini buluyoruz
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Modelleri 'models' klasörü içinden çekiyoruz
MODEL_PATH = os.path.join(BASE_DIR, "models", "model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "models", "vectorizer.pkl")


# ---------------------------------------------------------------------------
# İmza Tabanlı Kurallar (Regex Kalıpları)
# ---------------------------------------------------------------------------
# Her kural bir (isim, regex_pattern) çiftidir.
# re.IGNORECASE bayrağı ile büyük/küçük harf duyarsız eşleşme sağlanır.

SIGNATURE_RULES: list[Tuple[str, re.Pattern]] = [
    # -------------------------------------------------------------------
    # 1) Totoloji Saldırıları  (OR 1=1, OR 'a'='a', OR ""="" vb.)
    # -------------------------------------------------------------------
    (
        "Totoloji (OR x=x)",
        re.compile(
            r"""\bOR\s+          # OR anahtar kelimesi
                (['"]?)          # Opsiyonel tırnak
                (.+?)            # Değer
                \1               # Aynı tırnak kapanışı
                \s*=\s*          # Eşittir işareti
                \1               # Aynı tırnak açılışı
                \2               # Aynı değer
                \1               # Aynı tırnak kapanışı
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    ),
    # -------------------------------------------------------------------
    # 2) UNION SELECT Saldırıları
    # -------------------------------------------------------------------
    (
        "UNION SELECT",
        re.compile(
            r"\bUNION\s+(ALL\s+)?SELECT\b",
            re.IGNORECASE,
        ),
    ),
    # -------------------------------------------------------------------
    # 3) Yorum Satırı İstismarı  (--, #, /* ... */)
    # -------------------------------------------------------------------
    (
        "SQL Yorum Satırı (--)",
        re.compile(r"--\s*$|--\s+", re.MULTILINE),
    ),
    (
        "SQL Yorum Satırı (#)",
        re.compile(r"#\s*$|#\s+", re.MULTILINE),
    ),
    (
        "SQL Blok Yorum (/* */)",
        re.compile(r"/\*.*?\*/", re.DOTALL),
    ),
    # -------------------------------------------------------------------
    # 4) Stacked Queries (Yığılmış Sorgular)  → ; ile birden fazla sorgu
    # -------------------------------------------------------------------
    (
        "Stacked Query (;)",
        re.compile(
            r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC)\b",
            re.IGNORECASE,
        ),
    ),
    # -------------------------------------------------------------------
    # 5) DROP / ALTER / TRUNCATE → Yıkıcı DDL komutları
    # -------------------------------------------------------------------
    (
        "Tehlikeli DDL (DROP/ALTER/TRUNCATE)",
        re.compile(
            r"\b(DROP|ALTER|TRUNCATE)\s+(TABLE|DATABASE|SCHEMA|INDEX)\b",
            re.IGNORECASE,
        ),
    ),
    # -------------------------------------------------------------------
    # 6) Zaman Tabanlı Kör Enjeksiyon  (SLEEP, BENCHMARK, WAITFOR, PG_SLEEP)
    # -------------------------------------------------------------------
    (
        "Zaman Tabanlı Enjeksiyon (SLEEP/WAITFOR)",
        re.compile(
            r"\b(SLEEP|BENCHMARK|WAITFOR\s+DELAY|PG_SLEEP)\s*\(",
            re.IGNORECASE,
        ),
    ),
    # -------------------------------------------------------------------
    # 7) Bilgi Sızdırma Fonksiyonları  (VERSION, @@VERSION, USER(), DATABASE())
    # -------------------------------------------------------------------
    (
        "Bilgi Sızdırma (VERSION/USER/DATABASE)",
        re.compile(
            r"\b(VERSION|USER|DATABASE|CURRENT_USER|SESSION_USER)\s*\(\s*\)"
            r"|@@VERSION\b",
            re.IGNORECASE,
        ),
    ),
    # -------------------------------------------------------------------
    # 8) LOAD_FILE / INTO OUTFILE / INTO DUMPFILE → Dosya erişimi
    # -------------------------------------------------------------------
    (
        "Dosya Erişimi (LOAD_FILE/OUTFILE)",
        re.compile(
            r"\b(LOAD_FILE|INTO\s+OUTFILE|INTO\s+DUMPFILE)\b",
            re.IGNORECASE,
        ),
    ),
    # -------------------------------------------------------------------
    # 9) Hex Kodlama İstismarı  (0x... uzun hex dizileri)
    # -------------------------------------------------------------------
    (
        "Hex Kodlama İstismarı",
        re.compile(r"0x[0-9a-fA-F]{8,}"),
    ),
    # -------------------------------------------------------------------
    # 10) CHAR() / CONCAT() ile Obfuscation
    # -------------------------------------------------------------------
    (
        "CHAR/CONCAT Obfuscation",
        re.compile(
            r"\b(CHAR|CONCAT)\s*\(\s*\d+",
            re.IGNORECASE,
        ),
    ),
]


# ---------------------------------------------------------------------------
# Model Önbelleği (Lazy Loading)
# ---------------------------------------------------------------------------
_model_cache = {}


def _model_yukle():
    """
    ML modelini ve vectorizer'ı tembel (lazy) olarak yükler.
    İlk çağrıda diskten okur, sonraki çağrılarda önbellekten döner.

    Returns:
        Tuple[model, vectorizer] veya hata durumunda None.
    """
    if "model" not in _model_cache:
        if not os.path.exists(MODEL_PATH):
            print(f"[UYARI] Model dosyası bulunamadı: {MODEL_PATH}")
            print("        Lütfen önce 'python train.py' komutunu çalıştırın.")
            return None, None

        if not os.path.exists(VECTORIZER_PATH):
            print(f"[UYARI] Vectorizer dosyası bulunamadı: {VECTORIZER_PATH}")
            print("        Lütfen önce 'python train.py' komutunu çalıştırın.")
            return None, None

        _model_cache["model"] = joblib.load(MODEL_PATH)
        _model_cache["vectorizer"] = joblib.load(VECTORIZER_PATH)

    return _model_cache["model"], _model_cache["vectorizer"]


# ---------------------------------------------------------------------------
# İmza Tabanlı Kontrol
# ---------------------------------------------------------------------------
def signature_check(query: str) -> Tuple[bool, str]:
    """
    Verilen sorguyu tüm Regex imza kurallarına karşı kontrol eder.

    Args:
        query: Kontrol edilecek SQL sorgusu veya kullanıcı girdisi.

    Returns:
        (True, kural_adi)  → Bir imza eşleşmesi bulundu (saldırı).
        (False, "")        → Hiçbir imza eşleşmedi (temiz).
    """
    for kural_adi, pattern in SIGNATURE_RULES:
        if pattern.search(query):
            return True, kural_adi
    return False, ""


# ---------------------------------------------------------------------------
# Hibrit Analiz (İmza + ML)
# ---------------------------------------------------------------------------
def hybrid_analyze(query: str) -> dict:
    """
    İki katmanlı hibrit analiz boru hattı.

    İş Akışı:
      1. İmza motoru kontrolü → eşleşme varsa anında BLOCKED_BY_SIGNATURE.
      2. İmza temiz → ML modeli ile tahmin → saldırı ise BLOCKED_BY_ML.
      3. Her iki katman da temiz → SAFE.

    Args:
        query: Analiz edilecek SQL sorgusu veya kullanıcı girdisi.

    Returns:
        dict: Analiz sonucunu içeren sözlük.
            - "karar": "BLOCKED_BY_SIGNATURE" | "BLOCKED_BY_ML" | "SAFE"
            - "katman": Kararın hangi katmandan geldiğini belirtir.
            - "detay": Ek bilgi (eşleşen kural adı, ML olasılığı vb.)
            - "query": Analiz edilen sorgu.
    """
    sonuc = {
        "query": query,
        "karar": "",
        "katman": "",
        "detay": "",
    }

    # -----------------------------------------------------------------------
    # Katman 1: İmza (Regex) Kontrolü
    # -----------------------------------------------------------------------
    imza_bulundu, kural_adi = signature_check(query)
    if imza_bulundu:
        sonuc["karar"] = "BLOCKED_BY_SIGNATURE"
        sonuc["katman"] = "Katman 1 - İmza Motoru (Regex)"
        sonuc["detay"] = f"Eşleşen kural: {kural_adi}"
        return sonuc

    # -----------------------------------------------------------------------
    # Katman 2: Makine Öğrenmesi (ML) Kontrolü
    # -----------------------------------------------------------------------
    model, vectorizer = _model_yukle()

    # Model yüklenemediyse güvenli tarafta kal ve uyar
    if model is None or vectorizer is None:
        sonuc["karar"] = "SAFE"
        sonuc["katman"] = "Yalnızca Katman 1 (ML modeli yüklenemedi)"
        sonuc["detay"] = "ML modeli bulunamadığı için sadece imza kontrolü yapıldı."
        return sonuc

    # Sorguyu TF-IDF ile vektörleştir ve tahmin yap
    query_vector = vectorizer.transform([query])
    tahmin = model.predict(query_vector)[0]

    if tahmin == 1:
        # Model saldırı diyor
        sonuc["karar"] = "BLOCKED_BY_ML"
        sonuc["katman"] = "Katman 2 - Makine Öğrenmesi (DecisionTree)"
        sonuc["detay"] = "ML modeli bu sorguyu saldırı olarak sınıflandırdı."
    else:
        # Her iki katman da temiz
        sonuc["karar"] = "SAFE"
        sonuc["katman"] = "Her iki katman (İmza + ML)"
        sonuc["detay"] = "Sorgu güvenli olarak değerlendirildi."

    return sonuc


# ---------------------------------------------------------------------------
# Modül doğrudan çalıştırılırsa hızlı test yap
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_sorgulari = [
        "SELECT * FROM users WHERE id = 1",
        "' OR 1=1 --",
        "1 UNION SELECT username, password FROM users",
        "SELECT name FROM products WHERE category = 'electronics'",
        "admin'; DROP TABLE users; --",
        "1' AND SLEEP(5) --",
    ]

    print("\n" + "=" * 70)
    print("  H-SQLi Hibrit Dedektör - Hızlı Test")
    print("=" * 70)

    for sorgu in test_sorgulari:
        sonuc = hybrid_analyze(sorgu)
        print(f"\n  Sorgu  : {sorgu}")
        print(f"  Karar  : {sonuc['karar']}")
        print(f"  Katman : {sonuc['katman']}")
        print(f"  Detay  : {sonuc['detay']}")
        print("  " + "-" * 66)
