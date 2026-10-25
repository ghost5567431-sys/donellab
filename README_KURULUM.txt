DONEL CISMİ UYGULAMASI - FOTOĞRAFTAN SORU OKUMA

Bu sürüm fotoğraf yükleme ve telefon kamerası desteği içerir. Harici API anahtarı istemez.
Fotoğraftan yazıyı okumak için Tesseract OCR kullanır. Basılı ve net matematik yazılarında daha iyi çalışır; el yazısı veya karmaşık formüller yanlış okunabilir. Okunan f(x), a, b değerlerini hesaplamadan önce kontrol edin.

GITHUB'A YÜKLEME:
1. Bu ZIP dosyasını bilgisayarınızda açın.
2. GitHub deponuzda eski Python dosyanızı açın (dosya adınız donellab.py ise onu).
3. Dosyayı düzenleyip tüm içeriğini donellab.py içindeki yeni kodla değiştirin veya yeni donellab.py dosyasını yükleyin.
4. cozum.py dosyasını da aynı depoda tutun. Mevcut cozum.py'niz aynıysa yeniden yüklemek şart değil.
5. requirements.txt ve packages.txt dosyalarını depo ana dizinine yükleyin.
6. Streamlit Cloud -> Manage app -> Reboot app yapın veya GitHub'a commit attıktan sonra otomatik yeniden başlatılmasını bekleyin.
7. Streamlit Cloud uygulama ayarlarında Main file path alanı donellab.py olmalı.

Gerekli ana dosyalar aynı klasörde olmalı:
- donellab.py
- cozum.py
- requirements.txt
- packages.txt

TEST:
Fotoğrafın üzerinde mümkünse şu biçimde net yazı bulunsun:
f(x)=x^2+1, a=0, b=2

OCR matematiksel gösterimi her zaman doğru okuyamaz. Okunan değerleri gözden geçirin.
