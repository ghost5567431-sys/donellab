DONEL CİSİM UYGULAMASI - GÜNCELLEME

Bu paket API anahtarı gerektirmeyen yerel OCR + kural tabanlı soru ayıklama kullanır.

GitHub / Streamlit Cloud için:
1. Proje deposundaki eski app dosyanızı bu paketteki app.py ile değiştirin.
2. cozum.py dosyasını da bu paketteki cozum.py ile değiştirin.
3. requirements.txt ve packages.txt dosyalarını depo köküne ekleyin/değiştirin.
4. Değişiklikleri GitHub'a yükleyin; Streamlit Cloud uygulamayı yeniden başlatır.
5. Uygulamada fotoğraf yükleyip “Soruyu oku → hesapla” düğmesine basın.

ÖNEMLİ SINIRLAMA:
Bu sürüm API'sizdir. Tesseract fotoğraftaki yazıyı okumaya çalışır; sonra kurallarla f(x), a, b değerlerini ayıklar.
Her türlü serbest biçimli matematik problemini insan gibi anlayamaz. El yazısı, bulanık fotoğraf, karmaşık kesirler,
grafikler ve yalnızca sözel olarak ima edilen sınırlar başarısız olabilir. Hesaplamadan önce çıkarılan değerleri kontrol edin.
