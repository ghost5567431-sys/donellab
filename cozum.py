# -*- coding: utf-8 -*-
"""
cozum.py  -  "Beyin" dosyası (ekranla ilgisi yok, sadece hesap ve model üretimi)

İçindekiler:
  1. f(x), a, b yazısını sayıya/ifadeye çevirmek
  2. Sembolik + sayısal hacim ve alan
  3. Dönel cismi üçgenlerden oluşturmak (mesh)
  4. İnce diskler
  5. Braille + dokunsal eksen plakası, dokunsal 2B grafik plakası
  6. STL dosyası yazmak
"""
import math
import struct
import numpy as np
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application, convert_xor)

x = sp.Symbol("x")

# Kullanıcının "2x", "x^2", "sin x" gibi yazmasına izin veren kurallar
DONUSUM = standard_transformations + (implicit_multiplication_application, convert_xor)
IZINLI = {"pi": sp.pi, "e": sp.E, "x": x, "sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos,
          "tan": sp.tan, "exp": sp.exp, "ln": sp.log, "log": sp.log, "abs": sp.Abs}


def ifade_oku(metin):
    """'x^2+1' gibi yazıyı sympy ifadesine çevirir."""
    metin = metin.replace("π", "pi").replace("²", "^2").replace("³", "^3")
    return parse_expr(metin, local_dict=IZINLI, transformations=DONUSUM)


def sayi_oku(metin):
    """'3', 'pi', '2*pi' gibi sınır yazısını sympy sayısına çevirir."""
    return sp.sympify(ifade_oku(str(metin)))


# --------------------------------------------------------------------------
# 2. HESAP
# --------------------------------------------------------------------------
def hesapla(f_metin, a_metin, b_metin, n_disk=6):
    """Bütün sayısal ve sembolik sonuçları bir sözlükte toplar."""
    f = ifade_oku(f_metin)
    a = sayi_oku(a_metin)
    b = sayi_oku(b_metin)
    af, bf = float(a), float(b)
    if not bf > af:
        raise ValueError("b, a'dan büyük olmalı.")

    fn = sp.lambdify(x, f, "numpy")           # sympy ifadesini hızlı sayısal fonksiyona çevir

    def F(xs):                                  # dizi de, tek sayı da kabul eden güvenli sürüm
        v = np.asarray(fn(np.asarray(xs, dtype=float)), dtype=float)
        return np.broadcast_to(v, np.shape(xs)).copy()

    # Profil: eğriyi 101 noktada örnekle. Yarıçap = |f(x)| (yarıçap negatif olamaz)
    xs = np.linspace(af, bf, 101)
    ys = F(xs)
    if not np.all(np.isfinite(ys)):
        raise ValueError("f(x) bu aralıkta tanımsız (sonsuz ya da karmaşık değer).")
    r = np.abs(ys)
    if r.max() <= 0:
        raise ValueError("f(x) her yerde 0.")

    # Sembolik hacim:  V = pi * integral(f^2)
    hacim_sem = alan_sem = None
    try:
        hacim_sem = sp.simplify(sp.integrate(sp.pi * f**2, (x, a, b)))
        if hacim_sem.has(sp.Integral) or hacim_sem.has(sp.zoo) or hacim_sem.has(sp.nan):
            hacim_sem = None
    except Exception:
        hacim_sem = None
    try:
        alan_sem = sp.simplify(sp.integrate(f, (x, a, b)))
        if alan_sem.has(sp.Integral) or alan_sem.has(sp.zoo) or alan_sem.has(sp.nan):
            alan_sem = None
    except Exception:
        alan_sem = None
    try:
        ters_turev = sp.integrate(sp.pi * f**2, x)
    except Exception:
        ters_turev = None

    # Sayısal hacim: Simpson kuralı (sembolik bulunamazsa yedek + doğrulama)
    K = 2000
    xk = np.linspace(af, bf, K + 1)
    w = np.ones(K + 1); w[1:-1:2] = 4; w[2:-1:2] = 2
    h = (bf - af) / K
    hacim_say = float(np.sum(w * np.pi * F(xk) ** 2) * h / 3)
    alan_say = float(np.sum(w * F(xk)) * h / 3)

    # İnce diskler (orta nokta kuralı): disk k'nın yarıçapı = |f(orta nokta)|
    dh = (bf - af) / n_disk
    orta = af + (np.arange(n_disk) + 0.5) * dh
    disk_r = np.abs(F(orta))
    disk_toplam = float(np.sum(np.pi * disk_r**2 * dh))

    return dict(f=f, f_metin=f_metin, a=af, b=bf, a_sem=a, b_sem=b, xs=xs, r=r,
                rmax=float(r.max()), hacim_sem=hacim_sem, hacim_say=hacim_say,
                alan_sem=alan_sem, alan_say=alan_say, ters_turev=ters_turev,
                n=n_disk, dh=dh, disk_r=disk_r, disk_toplam=disk_toplam)


def olcek_bul(s, birim_mm, sigdir_mm, max_mm=250.0):
    """1 birim kaç mm olacak? birim_mm>0 ise onu kullan, değilse sigdir_mm'ye sığdır.
    250 mm'yi aşarsa otomatik küçült. (olcek, kucultuldu_mu) döner."""
    uzun = max(s["b"] - s["a"], 2 * s["rmax"])
    o = birim_mm if birim_mm and birim_mm > 0 else sigdir_mm / uzun
    kucult = uzun * o > max_mm
    if kucult:
        o = max_mm / uzun
    return o, kucult


# --------------------------------------------------------------------------
# 3. MESH (üçgen) ÜRETİMİ
# --------------------------------------------------------------------------
def _ekle(liste, p, q, r):
    """Üçgeni listeye ekler; alanı sıfır olan (çökmüş) üçgenleri atar."""
    p, q, r = np.array(p), np.array(q), np.array(r)
    if np.linalg.norm(np.cross(q - p, r - p)) > 1e-7:
        liste.append((p, q, r))


def dondur(profil, parca=64, liste=None):
    """profil = [(x0,r0),(x1,r1),...]. Bu eğriyi x ekseni etrafında döndürüp
    kapalı (uçları kapaklı) bir katı cisim yapar."""
    if liste is None:
        liste = []
    P = np.asarray(profil, dtype=float)
    t = 2 * np.pi * np.arange(parca + 1) / parca

    def V(i, j):
        return (P[i, 0], P[i, 1] * np.cos(t[j]), P[i, 1] * np.sin(t[j]))

    son = len(P) - 1
    for i in range(son):
        for j in range(parca):
            a_, b_, c_, d_ = V(i, j), V(i + 1, j), V(i + 1, j + 1), V(i, j + 1)
            _ekle(liste, a_, c_, b_)      # sıra, yüzeyin DIŞA bakmasını sağlar
            _ekle(liste, a_, d_, c_)
    c0, c1 = (P[0, 0], 0, 0), (P[son, 0], 0, 0)
    for j in range(parca):                # iki ucu kapat
        _ekle(liste, c0, V(0, j + 1), V(0, j))
        _ekle(liste, c1, V(son, j), V(son, j + 1))
    return liste


def govde_ucgenleri(s, olcek):
    profil = [(xx * olcek, rr * olcek) for xx, rr in zip(s["xs"], s["r"])]
    return dondur(profil, 64)


def disk_ucgenleri(s, olcek, bosluk_mm=0.3):
    """Her disk ayrı kapalı bir silindir. Aralarında 'bosluk_mm' kadar boşluk
    bırakılır ki dilimleyici (slicer) onları tek parça yapmasın."""
    liste = []
    for k in range(s["n"]):
        x0 = (s["a"] + k * s["dh"]) * olcek + bosluk_mm / 2
        x1 = (s["a"] + (k + 1) * s["dh"]) * olcek - bosluk_mm / 2
        rr = s["disk_r"][k] * olcek
        dondur([(x0, rr), (x1, rr)], 48, liste)
    return liste


# --------------------------------------------------------------------------
# 5. BRAILLE + DOKUNSAL PLAKALAR
# --------------------------------------------------------------------------
# Nokta numaraları: 1,2,3 sol sütun (yukarıdan aşağı), 4,5,6 sağ sütun.
# Bit değerleri: nokta1=1, 2=2, 3=4, 4=8, 5=16, 6=32
_AJ = {"a": 1, "b": 3, "c": 9, "d": 25, "e": 17, "f": 11, "g": 27, "h": 19, "i": 10, "j": 26}
BRAILLE = dict(_AJ)
for _i, _h in enumerate("klmnopqrst"):
    BRAILLE[_h] = _AJ["abcdefghij"[_i]] | 4          # a-j'ye 3. nokta eklenir
BRAILLE.update({"u": 37, "v": 39, "x": 45, "y": 61, "z": 53, "w": 58})
SAYI_ISARETI, ONDALIK, EKSI = 60, 50, 36


def braille_hucreleri(metin):
    """'v 28.27' -> hücre listesi (her hücre 0-63 arası bir sayı)."""
    c, sayi_modu = [], False
    for ch in metin.lower():
        if ch.isdigit():
            if not sayi_modu:
                c.append(SAYI_ISARETI); sayi_modu = True
            c.append(BRAILLE["jabcdefghi"[int(ch)]])     # 1..9 -> a..i, 0 -> j
        elif ch == ".":
            c.append(ONDALIK)
        elif ch == "-":
            c.append(EKSI); sayi_modu = False
        elif ch == " ":
            c.append(0); sayi_modu = False
        else:
            c.append(BRAILLE.get(ch, 0)); sayi_modu = False
    return c


def braille_unicode(metin):
    """Ekranda göstermek için ⠁⠃⠉ biçimi."""
    return "".join(chr(0x2800 + m) for m in braille_hucreleri(metin))


def _kutu(l, x0, y0, z0, x1, y1, z1):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    for q in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]:
        _ekle(l, v[q[0]], v[q[1]], v[q[2]])
        _ekle(l, v[q[0]], v[q[2]], v[q[3]])


def _silindir(l, cx, cy, z0, z1, r, n=10):
    p = lambda k, z: (cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), z)
    for k in range(n):
        _ekle(l, (cx, cy, z0), p(k + 1, z0), p(k, z0))
        _ekle(l, (cx, cy, z1), p(k, z1), p(k + 1, z1))
        _ekle(l, p(k, z0), p(k + 1, z0), p(k + 1, z1))
        _ekle(l, p(k, z0), p(k + 1, z1), p(k, z1))


def guzel_adim(aralik):
    """Eksende en çok ~10-12 çentik olacak 'güzel' adım (1, 2, 5, 10, 20, 50 ...)."""
    for k in range(-3, 7):
        for m in (1, 2, 5):
            if aralik / (m * 10.0**k) <= 10:
                return m * 10.0**k
    return 1.0


def etiket_satirlari(s, olcek):
    v_mL = s["hacim_say"] * olcek**3 / 1000
    return ["a " + f"{s['a']:g}", "b " + f"{s['b']:g}",
            "v " + f"{s['hacim_say']:.2f}", "ml " + f"{v_mL:.1f}"]


def etiket_eksen_plakasi(s, olcek):
    """Taban plaka + kabartma x ekseni + çentikler + Braille satırları."""
    l, satirlar = [], etiket_satirlari(s, olcek)
    hucre = max(len(braille_hucreleri(t)) for t in satirlar)
    xa, xb = s["a"] * olcek - 6, s["b"] * olcek + 6
    x0, x1 = xa, max(xb, xa + hucre * 6.2 + 8)
    yT, yB = 8, -10 - (len(satirlar) - 1) * 11 - 9
    _kutu(l, x0, yB, 0, x1, yT, 2)                                      # taban
    _kutu(l, s["a"] * olcek, -.75, 2, s["b"] * olcek, .75, 3.5)         # eksen çizgisi
    adim = guzel_adim(s["b"] - s["a"])
    v = math.ceil(s["a"] / adim - 1e-9)
    while v * adim <= s["b"] + 1e-9:
        px = v * adim * olcek
        boy = 5 if v == 0 else 3                                         # sıfır çentiği daha uzun
        _kutu(l, px - .5, -boy, 2, px + .5, boy, 3.5)
        v += 1
    for px in (s["a"] * olcek, s["b"] * olcek):                          # uç çentikleri
        _kutu(l, px - .5, -4, 2, px + .5, 4, 3.5)
    for i, satir in enumerate(satirlar):                                 # Braille noktaları
        for c, m in enumerate(braille_hucreleri(satir)):
            for d in range(6):
                if m & (1 << d):
                    sutun, sira = (0, d) if d < 3 else (1, d - 3)
                    _silindir(l, x0 + 4 + c * 6.2 + sutun * 2.5, -10 - i * 11 - sira * 2.5, 2, 2.7, .8)
    return l


def grafik2d_plakasi(s, olcek):
    """Dokunsal 2B grafik: eğrinin altındaki alan kabartma, eksenler daha yüksek."""
    l = []
    x0, x1 = s["a"] * olcek - 8, s["b"] * olcek + 8
    yT = s["rmax"] * olcek + 8
    _kutu(l, x0, -9, 0, x1, yT, 2)
    xs, r = s["xs"] * olcek, s["r"] * olcek
    for i in range(len(xs) - 1):
        h = (r[i] + r[i + 1]) / 2
        if h > .05:
            _kutu(l, xs[i], 0, 2, xs[i + 1], h, 3.2)
    _kutu(l, xs[0] - 1, -.6, 2, xs[-1] + 1, .6, 4)                       # x ekseni
    _kutu(l, xs[0] - .6, 0, 2, xs[0] + .6, s["rmax"] * olcek + 2, 4)     # y ekseni
    adim = guzel_adim(s["b"] - s["a"])
    v = math.ceil(s["a"] / adim - 1e-9)
    while v * adim <= s["b"] + 1e-9:
        _kutu(l, v * adim * olcek - .5, -4, 2, v * adim * olcek + .5, 4, 3.6); v += 1
    ya = guzel_adim(s["rmax"]); k = 1
    while k * ya <= s["rmax"] + 1e-9:
        _kutu(l, xs[0] - 4, k * ya * olcek - .5, 2, xs[0] + 4, k * ya * olcek + .5, 3.6); k += 1
    return l


# --------------------------------------------------------------------------
# 6. STL YAZMA (ikili / binary STL)
# --------------------------------------------------------------------------
def stl_bayt(ucgenler):
    """Üçgen listesi -> binary STL baytları. Birim: mm."""
    out = bytearray(b"Donel cisim STL".ljust(80, b" "))
    out += struct.pack("<I", len(ucgenler))
    for p, q, r in ucgenler:
        n = np.cross(q - p, r - p)
        L = np.linalg.norm(n)
        n = n / L if L else n
        out += struct.pack("<12fH", *n, *p, *q, *r, 0)
    return bytes(out)


def zip_icerigi(s, olcek):
    """ZIP'e girecek dosyalar: {ad: bayt}."""
    tum_diskler = disk_ucgenleri(s, olcek)
    return {
        "donel_cisim.stl": stl_bayt(govde_ucgenleri(s, olcek)),
        "diskler.stl": stl_bayt(tum_diskler),
        "etiket_eksen.stl": stl_bayt(etiket_eksen_plakasi(s, olcek)),
        "grafik_2d.stl": stl_bayt(grafik2d_plakasi(s, olcek)),
    }
