"""
=============================================================================
H-SQLi Projesi - İnteraktif Test Arayüzü (main.py)
=============================================================================
Kullanıcının terminal üzerinden sorgu girerek hibrit SQL enjeksiyon
tespit sistemini canlı olarak test edebileceği CLI (Komut Satırı Arayüzü).

Kullanım:
  python main.py

Komutlar:
  - Herhangi bir SQL sorgusu veya metin girin → Analiz sonucu gösterilir.
  - 'q', 'quit', 'exit' veya 'çıkış' → Programı sonlandırır.
  - 'temizle' veya 'clear' → Ekranı temizler.
=============================================================================
"""

import os
import sys

# colorama, Windows'ta ANSI renk kodlarını etkinleştirir
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
    RENK_AKTIF = True
except ImportError:
    # colorama yüklü değilse renksiz çalış
    RENK_AKTIF = False

    class _Dummy:
        """colorama yoksa boş string döndüren sahte sınıf."""
        def __getattr__(self, name):
            return ""

    Fore = _Dummy()
    Style = _Dummy()

from detector import hybrid_analyze


# ---------------------------------------------------------------------------
# Yardımcı Fonksiyonlar
# ---------------------------------------------------------------------------
def banner_yazdir() -> None:
    """Hoş geldiniz banner'ını ekrana yazdırır."""
    banner = f"""
{Fore.CYAN}{Style.BRIGHT}╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ██╗  ██╗      ███████╗ ██████╗ ██╗     ██╗                     ║
║   ██║  ██║      ██╔════╝██╔═══██╗██║     ██║                     ║
║   ███████║█████╗███████╗██║   ██║██║     ██║                     ║
║   ██╔══██║╚════╝╚════██║██║▄▄ ██║██║     ██║                     ║
║   ██║  ██║      ███████║╚██████╔╝███████╗██║                     ║
║   ╚═╝  ╚═╝      ╚══════╝ ╚══▀▀═╝ ╚══════╝╚═╝                     ║
║                                                                  ║
║   {Fore.YELLOW}Hibrit Yaklaşımlı SQL Enjeksiyon Tespit Sistemi{Fore.CYAN}                ║
║   {Fore.WHITE}İmza Motoru (Regex) + Makine Öğrenmesi (DecisionTree){Fore.CYAN}          ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def yardim_yazdir() -> None:
    """Kullanım talimatlarını ekrana yazdırır."""
    print(f"""
{Fore.WHITE}{Style.BRIGHT}  Kullanım Kılavuzu:{Style.RESET_ALL}
  {Fore.CYAN}─────────────────────────────────────────────────{Style.RESET_ALL}
  {Fore.GREEN}•{Style.RESET_ALL} Herhangi bir SQL sorgusu veya metin girin.
  {Fore.GREEN}•{Style.RESET_ALL} Sistem sorgunuzu iki katmanlı hibrit
    pipeline ile analiz edecektir.
  {Fore.CYAN}─────────────────────────────────────────────────{Style.RESET_ALL}
  {Fore.YELLOW}Komutlar:{Style.RESET_ALL}
    {Fore.WHITE}q / quit / exit / çıkış{Style.RESET_ALL}  →  Programdan çık
    {Fore.WHITE}temizle / clear{Style.RESET_ALL}            →  Ekranı temizle
    {Fore.WHITE}yardım / help{Style.RESET_ALL}              →  Bu mesajı göster
  {Fore.CYAN}─────────────────────────────────────────────────{Style.RESET_ALL}
""")


def sonuc_yazdir(sonuc: dict) -> None:
    """
    Analiz sonucunu renkli formatta ekrana yazdırır.

    Args:
        sonuc: hybrid_analyze() fonksiyonundan dönen sözlük.
    """
    karar = sonuc["karar"]

    # Karara göre renk ve sembol belirle
    if karar == "BLOCKED_BY_SIGNATURE":
        renk = Fore.RED
        sembol = "🛑"
        durum_metni = "ENGELLENDİ (İMZA)"
        kutu_renk = Fore.RED
    elif karar == "BLOCKED_BY_ML":
        renk = Fore.YELLOW
        sembol = "⚠️ "
        durum_metni = "ENGELLENDİ (ML MODELİ)"
        kutu_renk = Fore.YELLOW
    else:  # SAFE
        renk = Fore.GREEN
        sembol = "✅"
        durum_metni = "GÜVENLİ"
        kutu_renk = Fore.GREEN

    print(f"""
  {kutu_renk}┌─────────────────────────────────────────────────────┐{Style.RESET_ALL}
  {kutu_renk}│{Style.RESET_ALL}  {sembol}  Sonuç: {renk}{Style.BRIGHT}{durum_metni}{Style.RESET_ALL}
  {kutu_renk}│{Style.RESET_ALL}
  {kutu_renk}│{Style.RESET_ALL}  {Fore.WHITE}Katman :{Style.RESET_ALL} {sonuc['katman']}
  {kutu_renk}│{Style.RESET_ALL}  {Fore.WHITE}Detay  :{Style.RESET_ALL} {sonuc['detay']}
  {kutu_renk}└─────────────────────────────────────────────────────┘{Style.RESET_ALL}
""")


def ekrani_temizle() -> None:
    """İşletim sistemine uygun ekran temizleme komutu çalıştırır."""
    os.system("cls" if os.name == "nt" else "clear")


# ---------------------------------------------------------------------------
# Ana Döngü
# ---------------------------------------------------------------------------
def main() -> None:
    """
    İnteraktif CLI döngüsü. Kullanıcı sorgu girer, sistem analiz eder
    ve sonucu ekrana yazdırır. 'q' ile çıkılır.
    """
    banner_yazdir()
    yardim_yazdir()

    sayac = 0  # Analiz edilen sorgu sayacı

    while True:
        try:
            # Kullanıcıdan sorgu al
            sorgu = input(
                f"{Fore.CYAN}{Style.BRIGHT}  H-SQLi > {Style.RESET_ALL}"
            ).strip()

            # Boş girdi kontrolü
            if not sorgu:
                print(
                    f"  {Fore.YELLOW}[!] Lütfen bir sorgu girin veya "
                    f"'q' ile çıkın.{Style.RESET_ALL}"
                )
                continue

            # Çıkış komutları
            if sorgu.lower() in ("q", "quit", "exit", "çıkış"):
                print(f"\n  {Fore.CYAN}Toplam {sayac} sorgu analiz edildi.")
                print(
                    f"  {Fore.GREEN}Güle güle! H-SQLi sistemi "
                    f"kapatılıyor...{Style.RESET_ALL}\n"
                )
                break

            # Ekran temizleme
            if sorgu.lower() in ("temizle", "clear"):
                ekrani_temizle()
                banner_yazdir()
                continue

            # Yardım
            if sorgu.lower() in ("yardım", "help"):
                yardim_yazdir()
                continue

            # Hibrit analiz yap
            sayac += 1
            print(
                f"\n  {Fore.WHITE}[{sayac}] Analiz ediliyor: "
                f"{Fore.CYAN}\"{sorgu}\"{Style.RESET_ALL}"
            )
            sonuc = hybrid_analyze(sorgu)
            sonuc_yazdir(sonuc)

        except KeyboardInterrupt:
            # Ctrl+C ile çıkış
            print(
                f"\n\n  {Fore.YELLOW}[!] Ctrl+C algılandı. "
                f"Çıkılıyor...{Style.RESET_ALL}\n"
            )
            break
        except EOFError:
            # Pipe/dosya girdi sonu
            break


# ---------------------------------------------------------------------------
# Ana giriş noktası
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
