# -*- coding: utf-8 -*-
"""
app.py - Arayüz dosyası.
Gemini API ile fotoğraf/metin sorusu anlama; dönel cisim ve STL işlevleri korunur.
Çalıştırmak için: python -m streamlit run app.py
"""
import io
import re
import zipfile
import json

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import sympy as sp
from google import genai
from google.genai import types

import cozum as c

st.set_page_config(page_title="Dönel Cisim Hacmi → STL", layout="centered")
st.markdown("""<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1100px;}
[data-testid="stMetricValue"] {font-size: 1.35rem;}
@media (max-width: 600px) { .block-container {padding-left: 0.8rem; padding-right: 0.8rem;} h1 {font-size: 1.65rem !important;} }
</style>""", unsafe_allow_html=True)
st.title("Dönel Cisim Hacmi → Sembolik Hesap + 3B Baskı (STL)")
st.caption("Fotoğraftan veya metinden matematik sorusu çözümü + dönel cisim/STL hesapları.")

for anahtar, ilk in {
    "f_in": "x",
    "a_in": "0",
    "b_in": "3",
    "tur": "",
    "mesaj": "",
    "genel_cevap": "",
}.items():
    st.session_state.setdefault(anahtar, ilk)

st.session_state.setdefault("soru_metni", "")
st.session_state.setdefault("ocr_okunan", "")


def oku_tiklandi():
    """Gemini ile yazılı veya fotoğraflı soruyu çözer."""
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        st.session_state.mesaj = (
            'GEMINI_API_KEY bulunamadı. Streamlit Cloud > Settings > Secrets '
            'bölümüne GEMINI_API_KEY = "..." ekleyin.'
        )
        return

    gorsel = st.session_state.get("gorsel")
    if gorsel is None:
        gorsel = st.session_state.get("kamera_gorsel")
    metin = st.session_state.get("soru_metni", "").strip()

    if gorsel is None and not metin:
        st.session_state.mesaj = "Fotoğraf yükleyin/çekin veya soruyu metin olarak yazın."
        return

    talimat = """
Sen Türkçe konuşan dikkatli bir matematik öğretmenisin.
Verilen soruyu çöz ve çözümü Türkçe, adım adım açıkla.
Fotoğraftaki metni, sembolleri, verilenleri ve sorulanı dikkatle oku.
Okunmayan bilgi varsa tahmin etmek yerine açıkça belirt.
İşlemleri ve sonucu kontrol et. Genel matematik sorularını çözmeye çalış:
integral, türev, limit, denklem, fonksiyon ve sözel matematik problemleri.
En sonda, eğer soru dönel cisim hacmi için mevcut uygulamaya aktarılabilecek
bir fonksiyon ve sınır içeriyorsa, cevabın sonuna şu biçimde bir satır ekle:
<DATA>{"fx":"x^2+1","a":"0","b":"2","is_volume":true}</DATA>
Buradaki örnek değerleri sorudan çıkarılan gerçek değerlerle değiştir.
Yalnızca sorudan güvenle çıkarabildiğin değerleri yaz. Dönel cisim hacmi
sorusu değilse is_volume false yaz. Fonksiyon ve iki sınır kesin değilse
fx, a ve b alanlarına boş metin yaz. JSON bloğundan önce normal çözümü yaz.
"""
    try:
        client = genai.Client(api_key=api_key)
        icerik = [talimat]
        if metin:
            icerik.append("Kullanıcının yazdığı soru:\n" + metin)
        if gorsel is not None:
            mime = getattr(gorsel, "type", None) or "image/jpeg"
            icerik.append(types.Part.from_bytes(data=gorsel.getvalue(), mime_type=mime))

        yanit = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=icerik,
        )
        cevap = (yanit.text or "").strip()
        if not cevap:
            raise ValueError("Gemini boş yanıt döndürdü.")
        st.session_state.genel_cevap = cevap

        es = re.search(r"<DATA>\s*(\{.*?\})\s*</DATA>", cevap, re.S)
        if es:
            try:
                data = json.loads(es.group(1))
                fx = str(data.get("fx", "")).strip()
                aa = str(data.get("a", "")).strip()
                bb = str(data.get("b", "")).strip()
                if fx and aa and bb and fx.lower() not in ("boş", "null", "none"):
                    st.session_state.f_in = fx.replace("**", "^")
                    st.session_state.a_in = aa
                    st.session_state.b_in = bb
                    st.session_state.tur = "integral" if data.get("is_volume") else ""
                    st.session_state.mesaj = (
                        f"Gemini fonksiyonu ve sınırları çıkardı: f(x)={fx}, "
                        f"[{aa}, {bb}]. Hesaplamadan önce alanları kontrol et."
                    )
                else:
                    st.session_state.mesaj = "Gemini çözümü hazırladı; aşağıda görüntüleniyor."
            except (ValueError, TypeError, json.JSONDecodeError):
                st.session_state.mesaj = "Gemini çözümü hazırladı; aşağıda görüntüleniyor."
        else:
            st.session_state.mesaj = "Gemini çözümü hazırladı; aşağıda görüntüleniyor."
    except Exception as hata:
        st.session_state.mesaj = (
            f"Gemini isteği başarısız oldu: {hata}. API anahtarını, model erişimini "
            "ve ücretsiz kullanım limitini kontrol edin."
        )


with st.sidebar:
    st.header("Girdiler")
    st.text_input("f(x)", key="f_in", help="Örnek: x, x^2, sqrt(x), sin(x), 2*x+1")
    k1, k2 = st.columns(2)
    k1.text_input("a", key="a_in")
    k2.text_input("b", key="b_in", help="pi yazabilirsiniz")
    n_disk = st.number_input("Disk sayısı (n)", min_value=1, max_value=60, value=6, step=1)
    birim_mm = st.number_input("1 birim = … mm (0 = sığdır)", min_value=0.0, max_value=1000.0, value=10.0)
    sigdir_mm = st.number_input("Sığdırma boyutu (mm)", min_value=20, max_value=250, value=80)
    st.divider()
    st.subheader("📷 Matematik sorusunu çöz")
    st.caption("Fotoğraf veya metinle soru çözümü Gemini API kullanır.")
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
        placeholder="Örnek: integral 0 ile 2 arasında (x^2+1) dx",
    )
    st.button("Soruyu oku ve çöz →", on_click=oku_tiklandi, type="primary")

    yuklenen = st.session_state.get("gorsel") or st.session_state.get("kamera_gorsel")
    if yuklenen is not None:
        st.image(yuklenen, caption="Soru fotoğrafı", use_container_width=True)
    if st.session_state.get("mesaj"):
        st.info(st.session_state.mesaj)

if st.session_state.get("genel_cevap"):
    st.subheader("Yapay zekânın çözümü")
    # İçerik kullanıcı sorusundan ve model yanıtından gelir; HTML çalıştırılmaz.
    cevap_goster = re.sub(r"<DATA>\s*\{.*?\}\s*</DATA>", "", st.session_state.genel_cevap, flags=re.S).strip()
    st.markdown(cevap_goster)

st.divider()
st.subheader("Dönel cisim hesabı ve 3B model")
st.caption("Aşağıdaki bölüm mevcut cozum.py hesaplama ve STL işlevlerini kullanır.")

try:
    s = c.hesapla(
        st.session_state.f_in,
        st.session_state.a_in,
        st.session_state.b_in,
        int(n_disk),
    )
    olcek, kucultuldu = c.olcek_bul(s, birim_mm, sigdir_mm)
except Exception as hata:
    st.error(f"Dönel cisim hesaplanamadı: {hata}")
    st.stop()

V = float(s["hacim_say"])
V_mL = V * olcek**3 / 1000
integral_sorusu = st.session_state.tur == "integral"


def yaz(sem, sayi):
    return (f"{sp.pretty(sem, use_unicode=True)} ≈ " if sem is not None else "") + f"{sayi:.4f}"


if integral_sorusu:
    st.success(f"**Dönel cisim sorusu:** ∫ f(x) dx = {yaz(s['alan_sem'], s['alan_say'])} birim²")
    st.caption(f"Eğri x-ekseni etrafında dönerse V = {yaz(s['hacim_sem'], V)} birim³")
else:
    st.success(f"**Dönel cisim hacmi:** V = {yaz(s['hacim_sem'], V)} birim³")
    st.caption(f"Eğri altındaki alan ∫ f(x) dx = {yaz(s['alan_sem'], s['alan_say'])}")

if s.get("ters_turev") is not None:
    st.caption(f"Ters türev: F(x) = {s['ters_turev']} → F(b) − F(a)")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Hacim (sayısal)", f"{V:.4f}")
if abs(V) > 1e-12:
    hata_yuzdesi = abs(s["disk_toplam"] - V) / abs(V) * 100
    hata_metni = f"hata %{hata_yuzdesi:.2f}"
else:
    hata_metni = "hacim sıfır"
m2.metric(f"{s['n']} disk toplamı", f"{s['disk_toplam']:.4f}", hata_metni, delta_color="off")
m3.metric("Ölçek", f"1 birim = {olcek:.2f} mm")
m4.metric("Su testi (dolu kap)", f"{V_mL:.1f} mL")
if kucultuldu:
    st.caption("Model 250 mm baskı alanına sığsın diye otomatik küçültüldü.")

sol, sag = st.columns(2)
with sol:
    st.subheader("3B model")
    mod = st.radio("Görünüm", ["Düz cisim", "Diskler"], horizontal=True)
    ucgenler = c.govde_ucgenleri(s, 1) if mod == "Düz cisim" else c.disk_ucgenleri(s, 1, s["dh"] * 0.12)
    if ucgenler:
        P = np.asarray([v for ucgen in ucgenler for v in ucgen], dtype=float)
        I = np.arange(len(P)).reshape(-1, 3)
        fig3 = go.Figure(go.Mesh3d(
            x=P[:, 0], y=P[:, 1], z=P[:, 2],
            i=I[:, 0], j=I[:, 1], k=I[:, 2],
            color="#3b82f6", flatshading=False, opacity=1,
        ))
        fig3.add_trace(go.Scatter3d(
            x=[s["a"], s["b"]], y=[0, 0], z=[0, 0],
            mode="lines", line=dict(color="orange", width=6), name="eksen",
        ))
        fig3.update_layout(scene=dict(aspectmode="data"), margin=dict(l=0, r=0, t=0, b=0), height=420)
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.warning("3B model için üçgen oluşturulamadı.")

with sag:
    st.subheader("2B grafik")
    goster = st.checkbox("Disk kesitlerini göster", True)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=s["xs"], y=s["r"], name="f(x)", line=dict(color="#2563eb", width=3)))
    fig2.add_trace(go.Scatter(
        x=s["xs"], y=-s["r"], name="−f(x)", line=dict(color="#2563eb", dash="dash"),
        fill="tonexty", fillcolor="rgba(59,130,246,0.12)",
    ))
    if goster:
        for k, rr in enumerate(s["disk_r"]):
            x0 = s["a"] + k * s["dh"]
            fig2.add_shape(type="rect", x0=x0, x1=x0 + s["dh"], y0=-rr, y1=rr,
                           line=dict(color="#6366f1"), fillcolor="rgba(99,102,241,0.12)")
    fig2.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="x", yaxis_title="y")
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Braille etiket")
for satir in c.etiket_satirlari(s, olcek):
    st.markdown(
        f"<span style='font-size:1.6rem;letter-spacing:.12em'>{c.braille_unicode(satir)}</span> &nbsp; `{satir}`",
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
        f"V={V:.4f} birim3\nOlcek: 1 birim = {olcek:.3f} mm\n"
        f"Beklenen su hacmi: {V_mL:.1f} mL\nSTL birimi mm.",
    )
ad = re.sub(r"[^A-Za-z0-9]+", "_", f"{s['f_metin']}_{s['a']:g}_{s['b']:g}")[:40]
st.download_button(
    "⬇ STL dosyalarını indir (.zip)", tampon.getvalue(),
    file_name=f"donel_{ad}.zip", mime="application/zip", type="primary",
)
st.caption(
    "ZIP: donel_cisim.stl (düz cisim), diskler.stl, "
    "etiket_eksen.stl (Braille + kabartma eksen), grafik_2d.stl (dokunsal grafik plakası)."
)
