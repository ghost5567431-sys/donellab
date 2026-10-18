# -*- coding: utf-8 -*-
"""DönelLab — yerel, API anahtarı gerektirmeyen dönel cisim hesaplayıcısı."""
from __future__ import annotations
import io, re, zipfile
import numpy as np
import plotly.graph_objects as go
import streamlit as st
import sympy as sp
import cozum as c

st.set_page_config(page_title="DönelLab | Dönel Cisim Atölyesi", page_icon="◉", layout="wide", initial_sidebar_state="collapsed")

st.markdown(r"""
<style>
:root { --ink:#eaf0f6; --muted:#9aabc0; --panel:#111d2b; --line:rgba(169,193,216,.15); --accent:#66e0c2; }
html, body, [class*="css"] { font-family:Inter,Segoe UI,Arial,sans-serif; }
.stApp { background: radial-gradient(ellipse at 15% 0%, #17334a 0%, #0b1420 42%, #080f18 100%); color:var(--ink); }
.block-container { max-width:1320px; padding-top:1.4rem; padding-bottom:3rem; }
h1,h2,h3 { font-family:Inter,Segoe UI,Arial,sans-serif !important; letter-spacing:-.035em; }
.hero { padding:1.35rem 1.5rem; border:1px solid var(--line); border-radius:22px; background:linear-gradient(120deg,rgba(102,224,194,.11),rgba(40,80,111,.16)); margin-bottom:1.2rem; }
.eyebrow { color:#66e0c2; font-size:.75rem; font-weight:700; text-transform:uppercase; letter-spacing:.16em; }
.hero h1 { font-size:clamp(1.8rem,4vw,3rem); line-height:1.05; margin:.45rem 0 .6rem; }
.hero p { color:#aebfd0; margin:0; max-width:760px; }
.panel { background:rgba(17,29,43,.82); border:1px solid var(--line); border-radius:18px; padding:1rem 1.1rem; }
.kpi { background:linear-gradient(145deg,rgba(24,43,60,.95),rgba(14,25,38,.95)); border:1px solid var(--line); border-radius:16px; padding:1rem 1.1rem; min-height:112px; }
.kpi-label { color:#9aabc0; font-size:.78rem; font-weight:600; margin-bottom:.4rem; }
.kpi-value { font-family:Inter,Segoe UI,Arial,sans-serif; font-size:clamp(1.15rem,2.2vw,1.75rem); color:#f2f7fb; font-weight:700; overflow-wrap:anywhere; }
.kpi-note { color:#66e0c2; font-size:.78rem; margin-top:.35rem; }
div[data-testid="stForm"] { background:rgba(17,29,43,.82); border:1px solid var(--line); padding:1rem 1.1rem; border-radius:18px; }
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] { background:#0c1723 !important; }
.stButton button, .stFormSubmitButton button, .stDownloadButton button { border-radius:12px; font-weight:700; min-height:2.7rem; }
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"] { background:#66e0c2; border:0; color:#07151b; }
.stTabs [data-baseweb="tab-list"] { gap:.4rem; border-bottom:1px solid var(--line); }
.stTabs [data-baseweb="tab"] { border-radius:10px 10px 0 0; padding:.7rem 1rem; }
hr { border-color:var(--line); }
div[data-testid="stAlert"] { border-radius:12px; }
.small-muted { color:#9aabc0; font-size:.86rem; }
@media(max-width:640px) {
  .block-container { padding:.65rem .65rem 1.6rem !important; }
  .hero { padding:1rem; border-radius:15px; }
  .hero h1 { font-size:1.85rem; }
  .kpi { padding:.75rem; min-height:auto; }
  .kpi-value { font-size:1.25rem; }
  .stTabs [data-baseweb="tab"] { padding:.5rem .55rem; font-size:.82rem; }
  /* Streamlit columns become readable, full-width sections on narrow screens. */
  div[data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; gap:.65rem !important; }
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    flex:1 1 100% !important; width:100% !important; min-width:100% !important;
  }
  div[data-testid="stForm"] { padding:.8rem; }
  .stButton button, .stFormSubmitButton button, .stDownloadButton button { width:100%; min-height:2.9rem; }
  div[data-testid="stPlotlyChart"] { width:100% !important; min-width:0 !important; }
  .stPlotlyChart iframe { max-width:100% !important; }
}
</style>
<div class="hero">
  <div class="eyebrow">MATEMATİK · GÖRSELLEŞTİRME · 3B ÜRETİM</div>
  <h1>DönelLab<span style="color:#66e0c2">.</span></h1>
  <p>Bir fonksiyon gir, dönel cismini incele, hacmi hesapla ve 3B yazıcıya uygun STL dosyalarını hazırla. Tamamen yerel çalışır; API anahtarı gerekmez.</p>
</div>
""", unsafe_allow_html=True)

with st.form("hesap_formu", clear_on_submit=False):
    st.markdown("### Fonksiyon ve aralık")
    a1, a2, a3 = st.columns([2.1, 1, 1])
    with a1:
        f_in = st.text_input("Fonksiyon  f(x)", value=st.session_state.get("f_in", "x^2 + 1"), help="Örnek: x^2, sqrt(x), sin(x), 2x+1. Üs için ^ veya ** kullanabilirsin.")
    with a2:
        a_in = st.text_input("Alt sınır  a", value=st.session_state.get("a_in", "0"))
    with a3:
        b_in = st.text_input("Üst sınır  b", value=st.session_state.get("b_in", "2"))
    b1, b2, b3 = st.columns([1, 1, 1.5])
    with b1:
        n_disk = st.number_input("Disk sayısı", min_value=4, max_value=120, value=int(st.session_state.get("n_disk", 24)), step=4)
    with b2:
        birim_mm = st.number_input("Ölçek (mm/birim)", min_value=0.0, max_value=1000.0, value=float(st.session_state.get("birim_mm", 10.0)), step=1.0, help="0 girersen model seçilen boyuta sığdırılır.")
    with b3:
        sigdir_mm = st.number_input("Otomatik sığdırma (mm)", min_value=20, max_value=250, value=int(st.session_state.get("sigdir_mm", 80)), step=10)
    submitted = st.form_submit_button("Hesapla ve modeli oluştur  →", type="primary", use_container_width=True)

if "hesap_verisi" not in st.session_state:
    st.session_state.hesap_verisi = None
if submitted or st.session_state.hesap_verisi is None:
    try:
        if not f_in.strip(): raise ValueError("Fonksiyon alanı boş bırakılamaz.")
        s_new = c.hesapla(f_in.strip(), a_in.strip(), b_in.strip(), int(n_disk))
        scale_new, shrunk_new = c.olcek_bul(s_new, float(birim_mm), int(sigdir_mm))
        st.session_state.hesap_verisi = {"s": s_new, "olcek": scale_new, "kucultuldu": shrunk_new,
                                         "f_in": f_in, "a_in": a_in, "b_in": b_in, "n_disk": int(n_disk),
                                         "birim_mm": float(birim_mm), "sigdir_mm": int(sigdir_mm)}
        for k, v in [("f_in",f_in),("a_in",a_in),("b_in",b_in),("n_disk",int(n_disk)),("birim_mm",float(birim_mm)),("sigdir_mm",int(sigdir_mm))]: st.session_state[k] = v
    except Exception as e:
        st.error(f"Hesaplama yapılamadı: {e}")
        st.stop()

D = st.session_state.hesap_verisi
s, olcek, kucultuldu = D["s"], D["olcek"], D["kucultuldu"]
V = float(s["hacim_say"])
V_ml = V * olcek**3 / 1000

def fmt_expr(expr, fallback):
    try:
        if expr is None: return f"≈ {fallback:.5g}"
        return f"{sp.sstr(expr)}  ≈  {fallback:.5g}"
    except Exception: return f"≈ {fallback:.5g}"

st.markdown("### Sonuç özeti")
k1,k2,k3,k4 = st.columns(4)
with k1: st.markdown(f'<div class="kpi"><div class="kpi-label">DÖNEL CİSMİN HACMİ</div><div class="kpi-value">{V:.4g}</div><div class="kpi-note">birim³</div></div>',unsafe_allow_html=True)
with k2: st.markdown(f'<div class="kpi"><div class="kpi-label">KESİT ALANI İNTEGRALİ</div><div class="kpi-value">{float(s["alan_say"]):.4g}</div><div class="kpi-note">birim²</div></div>',unsafe_allow_html=True)
with k3: st.markdown(f'<div class="kpi"><div class="kpi-label">MODEL ÖLÇEĞİ</div><div class="kpi-value">{olcek:.3g} mm</div><div class="kpi-note">her 1 birim için</div></div>',unsafe_allow_html=True)
with k4: st.markdown(f'<div class="kpi"><div class="kpi-label">TAHMİNİ KAPASİTE</div><div class="kpi-value">{V_ml:.3g} mL</div><div class="kpi-note">tam dolu model varsayımı</div></div>',unsafe_allow_html=True)

with st.expander("Sembolik çözüm ve hesap ayrıntıları", expanded=True):
    st.latex(r"V=\pi\int_a^b [f(x)]^2\,dx")
    st.write(f"**Fonksiyon:**  `f(x) = {s['f_metin']}`  ·  **Aralık:**  [{s['a']:g}, {s['b']:g}]")
    st.write("**Sembolik hacim:**", fmt_expr(s.get("hacim_sem"), V))
    st.write("**Alan integrali:**", fmt_expr(s.get("alan_sem"), float(s["alan_say"])))
    err = abs(s["disk_toplam"] - V) / max(abs(V), 1e-12) * 100
    st.write(f"**Disk yaklaşımı:** {s['disk_toplam']:.6g} birim³ · sembolik/nümerik hacme göre fark %{err:.3g} · {s['n']} disk")
    if kucultuldu: st.info("Modelin uzunluğu 250 mm sınırını aşmaması için ölçek otomatik küçültüldü.")

tab1, tab2, tab3 = st.tabs(["◉ 3B model", "⌁ 2B profil", "↓ STL dışa aktar"])
with tab1:
    v1,v2 = st.columns([3,1])
    with v2:
        model_mode = st.radio("Model tipi", ["Düz yüzey", "Disk yaklaşımı"], index=0)
        st.markdown("<div class='small-muted'>Modeli fareyle sürükleyerek döndürebilir, yakınlaştırabilir ve farklı açılardan inceleyebilirsin.</div>",unsafe_allow_html=True)
    tris = c.govde_ucgenleri(s, 1) if model_mode == "Düz yüzey" else c.disk_ucgenleri(s, 1, s["dh"]*0.12)
    if tris:
        P = np.asarray([v for tri in tris for v in tri], dtype=float)
        I = np.arange(len(P)).reshape(-1,3)
        fig3 = go.Figure(go.Mesh3d(x=P[:,0], y=P[:,1], z=P[:,2], i=I[:,0], j=I[:,1], k=I[:,2], color="#66e0c2", flatshading=False, opacity=1, name="Dönel cisim", lighting=dict(ambient=0.55,diffuse=0.8,specular=0.35,roughness=0.35)))
        fig3.add_trace(go.Scatter3d(x=[s["a"],s["b"]],y=[0,0],z=[0,0],mode="lines",line=dict(color="#f6bd60",width=5),name="Dönme ekseni"))
        fig3.update_layout(height=530, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#dce7f0"), scene=dict(aspectmode="data", bgcolor="rgba(0,0,0,0)", xaxis=dict(gridcolor="rgba(150,180,200,.12)",title="x"), yaxis=dict(gridcolor="rgba(150,180,200,.12)",title="y"), zaxis=dict(gridcolor="rgba(150,180,200,.12)",title="z")), legend=dict(orientation="h",yanchor="bottom",y=1.02,x=0))
        st.plotly_chart(fig3, use_container_width=True, config={"displaylogo":False,"responsive":True,"scrollZoom":True})
    else: st.warning("Bu fonksiyon için üç boyutlu ağ üretilemedi.")
with tab2:
    show_disks = st.toggle("Disk yaklaşımını göster", value=True)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=s["xs"],y=s["r"],name="Yarıçap |f(x)|",line=dict(color="#66e0c2",width=3),fill="tozeroy",fillcolor="rgba(102,224,194,.12)"))
    fig2.add_trace(go.Scatter(x=s["xs"],y=-s["r"],name="Alt profil",line=dict(color="#66e0c2",width=2,dash="dash")))
    if show_disks:
        for i, rr in enumerate(s["disk_r"]):
            x0=s["a"]+i*s["dh"]
            fig2.add_shape(type="rect",x0=x0,x1=x0+s["dh"],y0=-rr,y1=rr,line=dict(color="rgba(246,189,96,.7)",width=1),fillcolor="rgba(246,189,96,.09)")
    fig2.update_layout(height=470,margin=dict(l=10,r=10,t=20,b=10),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(color="#dce7f0"),xaxis=dict(title="x",gridcolor="rgba(150,180,200,.12)",zerolinecolor="rgba(150,180,200,.25)"),yaxis=dict(title="f(x)",gridcolor="rgba(150,180,200,.12)",zerolinecolor="rgba(150,180,200,.25)"),legend=dict(orientation="h",yanchor="bottom",y=1.02,x=0))
    st.plotly_chart(fig2,use_container_width=True,config={"displaylogo":False,"responsive":True})
    st.caption("Kesit yarıçapı |f(x)| olarak alınır. Hacim, π∫[f(x)]²dx ile hesaplanır.")
with tab3:
    st.markdown("### 3B baskı dosyaları")
    st.write("Dosyalar STL biçimindedir. ZIP paketi ana gövdeyi, disk modelini ve dokunsal yardımcı parçaları içerir.")
    files = c.zip_icerigi(s, olcek)
    out = io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as zf:
        for name,data in files.items(): zf.writestr(name,data)
        zf.writestr("BILGI.txt", f"DonelLab\nFonksiyon: f(x)={s['f_metin']}\nAralik: [{s['a']:g}, {s['b']:g}]\nHacim: {V:.8g} birim^3\nOlcek: 1 birim = {olcek:.6g} mm\nTahmini kapasite: {V_ml:.6g} mL\nSTL koordinat birimi: mm\n")
    safe = re.sub(r"[^A-Za-z0-9_-]+","_",s["f_metin"]).strip("_")[:24] or "fonksiyon"
    d1,d2 = st.columns([2,1])
    with d1:
        st.download_button("Tüm STL dosyalarını indir (.ZIP)",out.getvalue(),file_name=f"donellab_{safe}.zip",mime="application/zip",type="primary",use_container_width=True)
    with d2:
        st.metric("Paket boyutu", f"{len(out.getvalue())/1024:.1f} KB")
    st.markdown("**Paket içeriği**")
    for name,data in files.items():
        st.write(f"- `{name}` · {len(data)/1024:.1f} KB")
    st.warning("Baskıdan önce STL'yi dilimleyici yazılımında açıp ölçüleri ve taban temasını kontrol et. Gerçek sıvı kapasitesi baskı kalınlığı ve doluluk oranına bağlıdır.")

st.divider()
st.markdown("<div class='small-muted'>DönelLab · Yerel matematik motoru · API anahtarı gerekmez. Sonuçlar, girilen fonksiyonun x-ekseni etrafında döndürüldüğü varsayımıyla hesaplanır.</div>",unsafe_allow_html=True)
