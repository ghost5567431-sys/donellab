# -*- coding: utf-8 -*-
"""
app.py - Arayüz dosyası.
Çalıştırmak için proje klasöründe: python -m streamlit run app.py
Hesaplama ve STL üretim işlevleri cozum.py dosyasındadır.
"""

import io
import re
import zipfile

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import sympy as sp

import cozum as c


st.set_page_config(page_title="Dönel Cisim Hacmi → STL", layout="wide")
st.title("Dönel Cisim Hacmi → Sembolik Hesap + 3B Baskı (STL)")
st.caption("V = π∫ f(x)² dx — değerleri girin, sonuç anında görünür.")

# ---------------------------------------------------------------------------
# Başlangıç değerleri
# ---------------------------------------------------------------------------
for anahtar, ilk in {
    "f_in": "x",
    "a_in": "0",
    "b_in": "3",
    "tur": "",
    "mesaj": "",
}.items():
    st.session_state.setdefault(anahtar, ilk)

# Metin alanı başlangıç değeri. Dosya yükleyicisinin anahtarını Streamlit yönetir.
st.session_state.setdefault("soru_metni", "")


# ---------------------------------------------------------------------------
# CLAUDE / HARİCİ API GEREKTİRMEYEN YEREL SORU OKUMA
# ---------------------------------------------------------------------------
def metinden_soruyu_ayikla(metin):
    """Uzun soru metninden f(x), a, b değerlerini API kullanmadan ayıklar.

    Bu bir sezgisel ayrıştırıcıdır; serbest biçimli tüm matematik sorularını
    çözmez. Tanınmayan veya belirsiz durumlarda kullanıcıdan kontrol ister.
    """
    metin = (metin or "").strip()
    # OCR'da sık görülen karakterleri normalleştir.
    metin = (metin.replace("−", "-").replace("–", "-").replace("×", "*")
             .replace("·", "*").replace("²", "^2").replace("³", "^3")
             .replace("π", "pi").replace("\\", " "))
    metin = re.sub(r"\s+", " ", metin)
    if not metin:
        raise ValueError("Önce soru fotoğrafı yükleyin veya soru metnini yazın.")

    # Fonksiyonu hem f(x)=... hem de 'fonksiyonu ... olan' biçiminde bul.
    fonksiyon = None
    mf = re.search(r"(?:f\s*\(\s*x\s*\)|y)\s*=\s*(.+?)(?=(?:[,;.]?\s*(?:a\s*=|b\s*=|x\s*=|a\s*\u003d|alt sınır|üst sınır))|$)", metin, re.I)
    if mf:
        fonksiyon = mf.group(1).strip(" ,;:.()[]")

    # f(x)=... ile x=0 ve x=2 sınırlarının yazıldığı uzun problem metni.
    # Açık a/b tanımları varsa öncelik onlarda.
    ma = re.search(r"(?:alt\s*sınır|başlangıç\s*noktası|a)\s*(?:=|:|\s)\s*(-?\d+(?:[.,]\d+)?|pi)", metin, re.I)
    mb = re.search(r"(?:üst\s*sınır|bitiş\s*noktası|b)\s*(?:=|:|\s)\s*(-?\d+(?:[.,]\d+)?|pi)", metin, re.I)
    a = ma.group(1).replace(",", ".") if ma else None
    b = mb.group(1).replace(",", ".") if mb else None

    # 'x=0 ve x=2 doğruları arasında', 'x=0 ile x=2 arasında'.
    xs = re.findall(r"x\s*=\s*(-?\d+(?:[.,]\d+)?|pi)", metin, re.I)
    if len(xs) >= 2:
        a = a or xs[0].replace(",", ".")
        b = b or xs[1].replace(",", ".")

    # '0 ile 2 arasında', '0'dan 2'ye kadar' gibi doğal dil sınırları.
    if a is None or b is None:
        sinir = re.search(
            r"(-?\d+(?:[.,]\d+)?|pi)\s*(?:ile|[-–]|'dan|'den|'tan|'ten)\s*"
            r"(-?\d+(?:[.,]\d+)?|pi)\s*(?:arasında|arasındaki|aralığında|araligi|ye kadar|a kadar)?",
            metin, re.I)
        if sinir:
            a = a or sinir.group(1).replace(",", ".")
            b = b or sinir.group(2).replace(",", ".")

    # 'integral 0 ile 2 arasında: x^2+1' veya ∫_0^2 (x^2+1) dx.
    integral = re.search(r"∫\s*_\s*\{?(-?\d+(?:\.\d+)?|pi)\}?\s*\^\s*\{?(-?\d+(?:\.\d+)?|pi)\}?\s*(?:\((.*?)\)|(.*?))\s*d\s*x", metin, re.I)
    if integral:
        f_int = integral.group(3) if integral.group(3) is not None else integral.group(4)
        return f_int.strip().strip("() "), integral.group(1), integral.group(2)

    # '0 ile 2 arasında: x^2+1' ifadesinde fonksiyon sınırdan sonra gelebilir.
    if fonksiyon is None:
        mf2 = re.search(r"(?:arasında|aralığında|araligi)\s*[:,]?\s*(?:f\s*\(\s*x\s*\)\s*=\s*)?(.+?)(?:\s+(?:eğrisi|fonksiyonu|grafiği|ile sınırlı|etrafında döndürülür|etrafında döndürülüyor|hacmini|hacmi bulun|hesaplayın|bulunuz).*)?$", metin, re.I)
        if mf2:
            aday = mf2.group(1).strip(" ,;:.()[]")
            if re.search(r"\bx\b", aday, re.I) and not re.search(r"\b(?:bulun|hesapla|döndür|arasında)\b", aday, re.I):
                fonksiyon = aday

    # 'f(x)=...' sonrası metin bazen OCR ile sınırları içerebilir; gereksiz dili temizle.
    if fonksiyon:
        fonksiyon = re.sub(r"\s+(?:eğrisi|fonksiyonu|grafiği|ile sınırlı.*|x ekseni.*|etrafında.*|oluşan.*|hacmini.*|hacmi.*)$", "", fonksiyon, flags=re.I).strip(" ,;:.()[]")
        # f(x) alanına yalnızca matematik ifadesi gitsin.
        fonksiyon = re.sub(r"\s+ve\s+x\s*=.*$", "", fonksiyon, flags=re.I).strip()

    # En açık biçim: f(x)=..., a=..., b=...
    if fonksiyon and a is not None and b is not None:
        return fonksiyon.replace("**", "^").strip(), a, b

    # Sınırdan sonra iki nokta ile verilen fonksiyon.
    if a is not None and b is not None:
        sonra = re.search(r"(?:arasında|aralığında)\s*:\s*(.+?)(?:\s+(?:eğrisi|fonksiyonu|grafiği|x ekseni|etrafında|hacmini|hacmi bulun|hesaplayın).*)?$", metin, re.I)
        if sonra:
            aday = sonra.group(1).strip(" ,;:.()[]")
            if re.search(r"\bx\b", aday, re.I):
                return aday.replace("**", "^"), a, b

    raise ValueError(
        "Sorudan fonksiyon ve sınırları kesin çıkaramadım. Fotoğrafı daha net yükleyin; "
        "uygulama f(x), a ve b alanlarını doldurmak için şu tür bilgileri arar: "
        "f(x)=x^2+1 ve x=0, x=2. Bulunan değerleri hesaplamadan önce kontrol edin."
    )

def oku_tiklandi():
    """Metin sorusunu internet/API olmadan yerel olarak ayrıştırır."""
    metin = st.session_state.get("soru_metni", "").strip()
    gorsel = st.session_state.get("gorsel")

    if metin:
        try:
            f, a, b = metinden_soruyu_ayikla(metin)
            # Girdi widget'ları callback sırasında güncellenebilir.
            st.session_state.f_in = f.replace("**", "^")
            st.session_state.a_in = a
            st.session_state.b_in = b
            st.session_state.tur = "integral"
            st.session_state.mesaj = f"✓ Soru yerel olarak ayrıştırıldı: f(x)={f}, sınırlar [{a}, {b}]."
        except Exception as hata:
            st.session_state.mesaj = str(hata)
        return

    if gorsel is not None:
        try:
            import pytesseract
            from PIL import Image
            import io as _io
            resim = Image.open(_io.BytesIO(gorsel.getvalue())).convert("RGB")
            # Kontrastı artır; matematik sembolleri için tek blok OCR dene.
            from PIL import ImageEnhance, ImageOps
            gri = ImageOps.grayscale(resim)
            gri = ImageEnhance.Contrast(gri).enhance(2.0)
            metin_ocr = pytesseract.image_to_string(gri, config="--psm 6", lang="eng")
            try:
                f, a, b = metinden_soruyu_ayikla(metin_ocr)
            except ValueError:
                metin_ocr_satir = pytesseract.image_to_string(gri, config="--psm 11", lang="eng")
                f, a, b = metinden_soruyu_ayikla(metin_ocr_satir)
            st.session_state.f_in = f.replace("**", "^")
            st.session_state.a_in = a
            st.session_state.b_in = b
            st.session_state.tur = "integral"
            st.session_state.mesaj = f"✓ Görsel yerel OCR ile okundu: f(x)={f}, sınırlar [{a}, {b}]. Sonucu kontrol edin."
        except ImportError:
            st.session_state.mesaj = "OCR kütüphaneleri kurulu değil. requirements.txt ve packages.txt dosyalarının güncel olduğundan emin olun."
        except Exception as hata:
            st.session_state.mesaj = f"Görsel otomatik okunamadı: {hata}. f(x), a ve b alanlarını elle doldurabilirsiniz."
        return

    st.session_state.mesaj = "Bir soru yazın veya görsel yükleyin. Ayrıca f(x), a ve b alanlarını doğrudan doldurabilirsiniz."


# ---------------------------------------------------------------------------
# KENAR ÇUBUĞU
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Girdiler")
    st.text_input(
        "f(x)",
        key="f_in",
        help="Örnek: x, x^2, sqrt(x), sin(x), 2*x+1",
    )
    k1, k2 = st.columns(2)
    k1.text_input("a", key="a_in")
    k2.text_input("b", key="b_in", help="pi yazabilirsiniz")
    n_disk = st.number_input("Disk sayısı (n)", min_value=1, max_value=60, value=6, step=1)
    birim_mm = st.number_input(
        "1 birim = … mm (0 = sığdır)",
        min_value=0.0,
        max_value=1000.0,
        value=10.0,
    )
    sigdir_mm = st.number_input(
        "Sığdırma boyutu (mm)",
        min_value=20,
        max_value=250,
        value=80,
    )
    st.divider()
    st.subheader("📷 Sorunun tamamını oku (API gerekmez)")
    st.file_uploader(
        "Soru fotoğrafı",
        type=["png", "jpg", "jpeg", "webp", "gif"],
        key="gorsel",
    )
    st.text_area(
        "Soruyu yazın",
        key="soru_metni",
        height=100,
        placeholder="Örn: f(x)=x^2+1 eğrisi x=0 ve x=2 doğruları arasında...",
    )
    st.button(
        "Soruyu oku → hesapla",
        on_click=oku_tiklandi,
        type="primary",
    )

    if st.session_state.get("gorsel") is not None:
        st.image(st.session_state.gorsel, caption="Yüklenen görsel")
    if st.session_state.get("mesaj"):
        st.info(st.session_state.mesaj)


# ---------------------------------------------------------------------------
# HESAPLAMA
# ---------------------------------------------------------------------------
try:
    s = c.hesapla(
        st.session_state.f_in,
        st.session_state.a_in,
        st.session_state.b_in,
        int(n_disk),
    )
    olcek, kucultuldu = c.olcek_bul(s, birim_mm, sigdir_mm)
except Exception as hata:
    st.error(f"Hesaplanamadı: {hata}")
    st.stop()

V = float(s["hacim_say"])
V_mL = V * olcek**3 / 1000
integral_sorusu = st.session_state.tur == "integral"


# ---------------------------------------------------------------------------
# CEVAP KUTUSU
# ---------------------------------------------------------------------------
def yaz(sem, sayi):
    return (
        f"{sp.pretty(sem, use_unicode=True)} ≈ "
        if sem is not None
        else ""
    ) + f"{sayi:.4f}"


if integral_sorusu:
    st.success(
        f"**Sorunun cevabı:** ∫ f(x) dx = "
        f"{yaz(s['alan_sem'], s['alan_say'])} birim²"
    )
    st.caption(
        f"Eğri x-ekseni etrafında dönerse V = "
        f"{yaz(s['hacim_sem'], V)} birim³"
    )
else:
    st.success(
        f"**Sorunun cevabı:** V = {yaz(s['hacim_sem'], V)} birim³"
    )
    st.caption(
        f"Eğri altındaki alan ∫ f(x) dx = "
        f"{yaz(s['alan_sem'], s['alan_say'])}"
    )

if s.get("ters_turev") is not None:
    st.caption(f"Ters türev: F(x) = {s['ters_turev']} → F(b) − F(a)")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Hacim (sayısal)", f"{V:.4f}")

if abs(V) > 1e-12:
    hata_yuzdesi = abs(s["disk_toplam"] - V) / abs(V) * 100
    hata_metni = f"hata %{hata_yuzdesi:.2f}"
else:
    hata_metni = "hacim sıfır"

m2.metric(
    f"{s['n']} disk toplamı",
    f"{s['disk_toplam']:.4f}",
    hata_metni,
    delta_color="off",
)
m3.metric("Ölçek", f"1 birim = {olcek:.2f} mm")
m4.metric("Su testi (dolu kap)", f"{V_mL:.1f} mL")

if kucultuldu:
    st.caption("Model 250 mm baskı alanına sığsın diye otomatik küçültüldü.")


# ---------------------------------------------------------------------------
# 3B ÖNİZLEME + 2B GRAFİK
# ---------------------------------------------------------------------------
sol, sag = st.columns(2)

with sol:
    st.subheader("3B model")
    mod = st.radio("Görünüm", ["Düz cisim", "Diskler"], horizontal=True)
    if mod == "Düz cisim":
        ucgenler = c.govde_ucgenleri(s, 1)
    else:
        ucgenler = c.disk_ucgenleri(s, 1, s["dh"] * 0.12)

    if ucgenler:
        P = np.asarray([v for ucgen in ucgenler for v in ucgen], dtype=float)
        I = np.arange(len(P)).reshape(-1, 3)
        fig3 = go.Figure(
            go.Mesh3d(
                x=P[:, 0],
                y=P[:, 1],
                z=P[:, 2],
                i=I[:, 0],
                j=I[:, 1],
                k=I[:, 2],
                color="#3b82f6",
                flatshading=False,
                opacity=1,
            )
        )
        fig3.add_trace(
            go.Scatter3d(
                x=[s["a"], s["b"]],
                y=[0, 0],
                z=[0, 0],
                mode="lines",
                line=dict(color="orange", width=6),
                name="eksen",
            )
        )
        fig3.update_layout(
            scene=dict(aspectmode="data"),
            margin=dict(l=0, r=0, t=0, b=0),
            height=420,
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.warning("3B model için üçgen oluşturulamadı.")

with sag:
    st.subheader("2B grafik")
    goster = st.checkbox("Disk kesitlerini göster", True)
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(
            x=s["xs"],
            y=s["r"],
            name="f(x)",
            line=dict(color="#2563eb", width=3),
        )
    )
    fig2.add_trace(
        go.Scatter(
            x=s["xs"],
            y=-s["r"],
            name="−f(x)",
            line=dict(color="#2563eb", dash="dash"),
            fill="tonexty",
            fillcolor="rgba(59,130,246,0.12)",
        )
    )

    if goster:
        for k, rr in enumerate(s["disk_r"]):
            x0 = s["a"] + k * s["dh"]
            fig2.add_shape(
                type="rect",
                x0=x0,
                x1=x0 + s["dh"],
                y0=-rr,
                y1=rr,
                line=dict(color="#6366f1"),
                fillcolor="rgba(99,102,241,0.12)",
            )

    fig2.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="x",
        yaxis_title="y",
    )
    st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# BRAILLE ETİKET + İNDİRME
# ---------------------------------------------------------------------------
st.subheader("Braille etiket")
for satir in c.etiket_satirlari(s, olcek):
    st.markdown(
        f"<span style='font-size:1.6rem;letter-spacing:.12em'>"
        f"{c.braille_unicode(satir)}</span> &nbsp; `{satir}`",
        unsafe_allow_html=True,
    )

dosyalar = c.zip_icerigi(s, olcek)
tampon = io.BytesIO()
with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
    for ad, veri in dosyalar.items():
        z.writestr(ad, veri)

    z.writestr(
        "OKU.txt",
        f"f(x)={s['f_metin']}, [{s['a']:g}, {s['b']:g}]\n"
        f"V={V:.4f} birim3\n"
        f"Olcek: 1 birim = {olcek:.3f} mm\n"
        f"Beklenen su hacmi: {V_mL:.1f} mL\n"
        "STL birimi mm.",
    )

ad = re.sub(
    r"[^A-Za-z0-9]+",
    "_",
    f"{s['f_metin']}_{s['a']:g}_{s['b']:g}",
)[:40]

st.download_button(
    "⬇ STL dosyalarını indir (.zip)",
    tampon.getvalue(),
    file_name=f"donel_{ad}.zip",
    mime="application/zip",
    type="primary",
)
st.caption(
    "ZIP: donel_cisim.stl (düz cisim), diskler.stl, "
    "etiket_eksen.stl (Braille + kabartma eksen), "
    "grafik_2d.stl (dokunsal grafik plakası)."
)
