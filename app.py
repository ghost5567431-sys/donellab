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


st.set_page_config(page_title="Dönel Cisim Hacmi → STL", layout="centered")
st.markdown("""<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1100px;}
[data-testid="stMetricValue"] {font-size: 1.35rem;}
@media (max-width: 600px) { .block-container {padding-left: 0.8rem; padding-right: 0.8rem;} h1 {font-size: 1.65rem !important;} }
</style>""", unsafe_allow_html=True)
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
st.session_state.setdefault("ocr_okunan", "")


# ---------------------------------------------------------------------------
# CLAUDE / HARİCİ API GEREKTİRMEYEN YEREL SORU OKUMA
# ---------------------------------------------------------------------------
def metinden_soruyu_ayikla(metin):
    """Desteklenen metin biçimlerinden f(x), a ve b değerlerini çıkarır.

    Örnekler:
      f(x)=x^2+1, a=0, b=2
      integral 0 ile 2 arasında: x^2+1
      ∫_0^2 (x^2+1) dx
    """
    metin = (metin or "").replace("\n", " ").replace("\r", " ").strip()
    metin = metin.replace("−", "-").replace("–", "-").replace("×", "*").replace("·", "*").replace("²", "^2").replace("³", "^3")
    metin = re.sub(r"\s+", " ", metin)
    if not metin:
        raise ValueError("Soruyu yazın veya soldaki f(x), a ve b alanlarını elle doldurun.")

    # En güvenilir ve açık biçim: f(x)=..., a=..., b=...
    mf = re.search(r"f\s*\(\s*x\s*\)\s*=\s*(.+?)(?=\s*[,;]?\s*(?:a|alt sınır)\s*=|$)", metin, re.I)
    ma = re.search(r"(?:\ba\b|alt\s*sınır)\s*=\s*([^,;\s]+)", metin, re.I)
    mb = re.search(r"(?:\bb\b|üst\s*sınır)\s*=\s*([^,;\s]+)", metin, re.I)
    if mf and ma and mb:
        return mf.group(1).strip().strip("() "), ma.group(1), mb.group(1)

    # Yaygın matematik yazımı: ∫_0^2 (x^2+1) dx
    integral = re.search(r"∫\s*_\s*\{?(-?\d+(?:\.\d+)?|pi)\}?\s*\^\s*\{?(-?\d+(?:\.\d+)?|pi)\}?\s*(?:\((.*?)\)|(.*?))\s*d\s*x", metin, re.I)
    if integral:
        f = integral.group(3) if integral.group(3) is not None else integral.group(4)
        return f.strip().strip("() "), integral.group(1), integral.group(2)

    # Basit doğal dil kalıbı: "0 ile 2 arasında: x^2+1"
    sinir = re.search(r"(-?\d+(?:\.\d+)?)\s*ile\s*(-?\d+(?:\.\d+)?)\s*arasında\s*:?\s*(.+)", metin, re.I)
    if sinir:
        return sinir.group(3).strip().strip("() "), sinir.group(1), sinir.group(2)

    raise ValueError("Soruyu anlayamadım. Şu biçimde yazın: f(x)=x^2+1, a=0, b=2")


def oku_tiklandi():
    """Fotoğraf/kamera OCR'si veya elle yazılan metinden f(x), a, b çıkarır."""
    gorsel = st.session_state.get("gorsel")
    if gorsel is None:
        gorsel = st.session_state.get("kamera_gorsel")

    # Fotoğraf varsa onu öncelikli oku.
    if gorsel is not None:
        try:
            import pytesseract
            from PIL import Image, ImageEnhance, ImageOps

            resim = Image.open(io.BytesIO(gorsel.getvalue())).convert("RGB")
            resim = ImageOps.grayscale(resim)
            resim = ImageEnhance.Contrast(resim).enhance(2.0)
            # Küçük telefon fotoğraflarında karakterleri OCR için büyüt.
            resim = resim.resize((resim.width * 2, resim.height * 2))
            metin_ocr = pytesseract.image_to_string(resim, config="--oem 3 --psm 6", lang="eng")
            st.session_state.ocr_okunan = metin_ocr.strip()
            f, a, b = metinden_soruyu_ayikla(metin_ocr)
            st.session_state.f_in = f.replace("**", "^")
            st.session_state.a_in = a
            st.session_state.b_in = b
            st.session_state.tur = "integral"
            st.session_state.mesaj = f"✓ Fotoğraf okundu: f(x)={f}, sınırlar [{a}, {b}]. Lütfen değerleri kontrol edin; sonra Hesapla bölümünü kontrol edin."
        except ImportError:
            st.session_state.mesaj = "OCR paketleri bulunamadı. GitHub deposunda requirements.txt ve packages.txt dosyalarının bulunduğundan emin olun."
        except Exception as hata:
            st.session_state.mesaj = f"Fotoğraftaki soru otomatik okunamadı: {hata}. Fotoğrafı daha net/kırpılmış yükleyin veya soruyu metin alanına yazın."
        return

    metin = st.session_state.get("soru_metni", "").strip()
    if metin:
        try:
            f, a, b = metinden_soruyu_ayikla(metin)
            st.session_state.f_in = f.replace("**", "^")
            st.session_state.a_in = a
            st.session_state.b_in = b
            st.session_state.tur = "integral"
            st.session_state.mesaj = f"✓ Soru metinden ayrıştırıldı: f(x)={f}, sınırlar [{a}, {b}]. Değerleri kontrol edin."
        except Exception as hata:
            st.session_state.mesaj = str(hata)
        return

    st.session_state.mesaj = "Fotoğraf yükleyin/çekin ya da soruyu metin alanına yazın."


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
    st.subheader("📷 Fotoğraftan soru oku")
    st.caption("Galeriden fotoğraf yükleyin veya telefon kamerasıyla çekin. API anahtarı gerekmez.")
    st.file_uploader(
        "Galeriden soru fotoğrafı seç",
        type=["png", "jpg", "jpeg", "webp"],
        key="gorsel",
    )
    st.camera_input("Veya kamerayla fotoğraf çek", key="kamera_gorsel")
    st.text_area(
        "Soruyu yazın",
        key="soru_metni",
        height=100,
        placeholder="f(x)=x^2+1, a=0, b=2  veya  ∫_0^2 (x^2+1) dx",
    )
    st.button(
        "Soruyu oku → hesapla",
        on_click=oku_tiklandi,
        type="primary",
    )

    yuklenen = st.session_state.get("gorsel") or st.session_state.get("kamera_gorsel")
    if yuklenen is not None:
        st.image(yuklenen, caption="Soru fotoğrafı", use_container_width=True)
    if st.session_state.get("ocr_okunan"):
        with st.expander("Fotoğraftan okunan ham metni gör"):
            st.code(st.session_state.ocr_okunan)
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
