"""
=============================================================================
H-SQLi Projesi - Makine Öğrenmesi Model Eğitim Betiği (train.py)
=============================================================================
Bu betik, Modified_SQL_Dataset.csv dosyasını okuyarak bir SQL Enjeksiyon
tespit modeli eğitir. İş akışı:
  1. Veri setini yükle ve ön işlemden geçir.
  2. TF-IDF ile metinleri sayısal vektörlere dönüştür.
  3. Karar Ağacı (DecisionTreeClassifier) ile modeli eğit.
  4. Test seti üzerinde performans metriklerini raporla.
  5. Eğitilmiş modeli ve vectorizer'ı diske kaydet.

Kullanım:
  python train.py
=============================================================================
"""

import os
import sys

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    f1_score,
    confusion_matrix,
    classification_report,
)
import joblib


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
DATASET_PATH = os.path.join(os.path.dirname(__file__), "Modified_SQL_Dataset.csv")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
VECTORIZER_PATH = os.path.join(os.path.dirname(__file__), "vectorizer.pkl")
TEST_SIZE = 0.30        # %30 test, %70 eğitim
RANDOM_STATE = 42       # Tekrarlanabilirlik için sabit rastgelelik tohumu


def veri_yukle(dosya_yolu: str) -> pd.DataFrame:
    """
    CSV dosyasını okur, temel kontrolleri yapar ve DataFrame döndürür.

    Args:
        dosya_yolu: Veri setinin tam dosya yolu.

    Returns:
        Temizlenmiş pandas DataFrame.
    """
    if not os.path.exists(dosya_yolu):
        print(f"[HATA] Veri seti bulunamadı: {dosya_yolu}")
        sys.exit(1)

    df = pd.read_csv(dosya_yolu, encoding="utf-8")

    # Gerekli sütunların varlığını kontrol et
    gerekli_sutunlar = {"Query", "Label"}
    if not gerekli_sutunlar.issubset(df.columns):
        print(f"[HATA] Veri setinde şu sütunlar bekleniyor: {gerekli_sutunlar}")
        sys.exit(1)

    # Boş sorguları temizle
    bos_sayisi = df["Query"].isna().sum()
    if bos_sayisi > 0:
        print(f"[BİLGİ] {bos_sayisi} adet boş sorgu satırı silindi.")
        df = df.dropna(subset=["Query"])

    # Query sütununu string tipine zorla
    df["Query"] = df["Query"].astype(str)

    return df


def veri_ozeti_yazdir(df: pd.DataFrame) -> None:
    """Veri setinin temel istatistiklerini ekrana yazdırır."""
    toplam = len(df)
    temiz = (df["Label"] == 0).sum()
    saldiri = (df["Label"] == 1).sum()

    print("=" * 60)
    print("           VERİ SETİ ÖZETİ")
    print("=" * 60)
    print(f"  Toplam kayıt       : {toplam:,}")
    print(f"  Temiz (Label=0)    : {temiz:,}  ({temiz / toplam * 100:.1f}%)")
    print(f"  Saldırı (Label=1)  : {saldiri:,}  ({saldiri / toplam * 100:.1f}%)")
    print("=" * 60)


def model_egit_ve_degerlendir() -> None:
    """
    Ana eğitim boru hattı. Veriyi yükler, TF-IDF vektörleştirir,
    Karar Ağacı modelini eğitir, metrikleri raporlar ve modeli kaydeder.
    """
    # -----------------------------------------------------------------------
    # 1) Veriyi yükle
    # -----------------------------------------------------------------------
    print("\n[1/5] Veri seti yükleniyor...")
    df = veri_yukle(DATASET_PATH)
    veri_ozeti_yazdir(df)

    X = df["Query"]       # Özellik: SQL sorgusu metni
    y = df["Label"]       # Etiket: 0 (Temiz) veya 1 (Saldırı)

    # -----------------------------------------------------------------------
    # 2) Eğitim / Test bölmesi
    # -----------------------------------------------------------------------
    print("[2/5] Veri %70 eğitim - %30 test olarak bölünüyor...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,   # Sınıf dağılımını korumak için stratifiye bölme
    )
    print(f"  Eğitim seti : {len(X_train):,} kayıt")
    print(f"  Test seti   : {len(X_test):,} kayıt")

    # -----------------------------------------------------------------------
    # 3) TF-IDF Vektörleştirme
    # -----------------------------------------------------------------------
    print("[3/5] TF-IDF vektörleştirme uygulanıyor...")
    vectorizer = TfidfVectorizer(
        max_features=10_000,   # En sık kullanılan 10.000 terimle sınırla
        ngram_range=(1, 2),     # Unigram + Bigram (örn: "UNION", "UNION SELECT")
        sublinear_tf=True,      # Logaritmik TF ölçekleme
        strip_accents="unicode",
    )
    X_train_tfidf = vectorizer.fit_transform(X_train)
    X_test_tfidf = vectorizer.transform(X_test)
    print(f"  Özellik boyutu: {X_train_tfidf.shape[1]:,} terim")

    # -----------------------------------------------------------------------
    # 4) Model eğitimi
    # -----------------------------------------------------------------------
    print("[4/5] Karar Ağacı (DecisionTreeClassifier) eğitiliyor...")
    model = DecisionTreeClassifier(
        criterion="gini",       # Bölme kriteri
        max_depth=None,         # Tam derinlik (pruning yok)
        min_samples_split=5,    # Minimum bölme örnek sayısı
        random_state=RANDOM_STATE,
    )
    model.fit(X_train_tfidf, y_train)
    print("  Model eğitimi tamamlandı.")

    # -----------------------------------------------------------------------
    # 5) Değerlendirme
    # -----------------------------------------------------------------------
    print("[5/5] Test seti üzerinde değerlendirme yapılıyor...\n")
    y_pred = model.predict(X_test_tfidf)

    # Temel metrikler
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    print("=" * 60)
    print("           MODEL PERFORMANS METRİKLERİ")
    print("=" * 60)
    print(f"  Accuracy  (Doğruluk)  : {accuracy:.4f}  ({accuracy * 100:.2f}%)")
    print(f"  Precision (Kesinlik)  : {precision:.4f}  ({precision * 100:.2f}%)")
    print(f"  F1-Score              : {f1:.4f}  ({f1 * 100:.2f}%)")
    print("=" * 60)

    # Karmaşıklık Matrisi
    cm = confusion_matrix(y_test, y_pred)
    print("\n  Karmaşıklık Matrisi (Confusion Matrix):")
    print("  " + "-" * 40)
    print(f"                  Tahmin: 0    Tahmin: 1")
    print(f"  Gerçek: 0       {cm[0][0]:>6}       {cm[0][1]:>6}")
    print(f"  Gerçek: 1       {cm[1][0]:>6}       {cm[1][1]:>6}")
    print("  " + "-" * 40)

    # Ayrıntılı sınıflandırma raporu
    print("\n  Ayrıntılı Sınıflandırma Raporu:")
    etiket_isimleri = ["Temiz (0)", "Saldırı (1)"]
    rapor = classification_report(y_test, y_pred, target_names=etiket_isimleri)
    for satir in rapor.split("\n"):
        print(f"  {satir}")

    # -----------------------------------------------------------------------
    # Model ve Vectorizer'ı diske kaydet
    # -----------------------------------------------------------------------
    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)
    print(f"\n[OK] Model kaydedildi       : {MODEL_PATH}")
    print(f"[OK] Vectorizer kaydedildi  : {VECTORIZER_PATH}")
    print("\nEgitim sureci basariyla tamamlandi!\n")


# ---------------------------------------------------------------------------
# Ana giriş noktası
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    model_egit_ve_degerlendir()
