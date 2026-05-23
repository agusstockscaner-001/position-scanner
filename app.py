"""
AI Position Scanner - Investasi 1-2 Bulan (Target ~20%)
Sistem TERPISAH dari swing scanner. Data Yahoo Finance lewat Cloudflare Worker.
Fokus: fundamental sehat + tren menengah naik + potensi upside besar.
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import quote

st.set_page_config(page_title="Position Scanner", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# ============================================================
PROXY = "https://yahoo-proxy.agusstockscaner.workers.dev/?url="
# ============================================================

st.markdown("""
<style>
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1rem !important; max-width: 100%; }
    .stock-card { background: linear-gradient(135deg,#0f1a14,#13291d); border:1px solid #1a352a; border-radius:12px; padding:14px; margin-bottom:10px; }
    .top-card { border:1px solid #2d7a4d; box-shadow:0 0 15px rgba(0,255,136,0.15); }
    .badge { display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:700; font-family:monospace; }
    .stButton button { width:100%; border-radius:8px; font-weight:600; }
    @media (max-width:768px){ .stock-card{padding:12px;font-size:13px;} h1{font-size:22px!important;} }
</style>
""", unsafe_allow_html=True)

SEKTOR = {
    "BANK": ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","BBTN.JK","BRIS.JK"],
    "TELCO": ["TLKM.JK","ISAT.JK","EXCL.JK","TOWR.JK"],
    "TAMBANG": ["ADRO.JK","ITMG.JK","PTBA.JK","ANTM.JK","INCO.JK","MDKA.JK","AMMN.JK"],
    "KONSUMER": ["ICBP.JK","INDF.JK","CPIN.JK","JPFA.JK","AMRT.JK","UNVR.JK","MYOR.JK"],
    "ENERGI": ["PGAS.JK","MEDC.JK","ADMR.JK"],
    "INDUSTRI": ["ASII.JK","UNTR.JK","AKRA.JK","SMGR.JK","INTP.JK"],
    "PROPERTI": ["CTRA.JK","SMRA.JK","PWON.JK"],
    "KESEHATAN": ["KLBF.JK","SIDO.JK"],
    "RITEL": ["ACES.JK","MAPI.JK","MAPA.JK"],
    "TEKNOLOGI": ["GOTO.JK"],
}
WATCHLIST = [s for l in SEKTOR.values() for s in l]

@st.cache_data(ttl=600)
def fetch_chart(symbol, rng="2y"):
    yahoo = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval=1d"
    try:
        r = requests.get(PROXY + quote(yahoo, safe=""), timeout=15)
        if r.status_code != 200: return None
        result = r.json()["chart"]["result"][0]
        q = result["indicators"]["quote"][0]
        clean = []
        for o,h,l,c,v in zip(q["open"],q["high"],q["low"],q["close"],q["volume"]):
            if all(x is not None for x in [o,h,l,c,v]) and o>0:
                clean.append((o,h,l,c,v))
        if len(clean) < 120: return None
        o,h,l,c,v = zip(*clean)
        return {"open":list(o),"high":list(h),"low":list(l),"close":list(c),"volume":list(v)}
    except Exception:
        return None

@st.cache_data(ttl=3600)
def fetch_fundamental(symbol):
    yahoo = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules=defaultKeyStatistics,financialData,summaryDetail"
    try:
        r = requests.get(PROXY + quote(yahoo, safe=""), timeout=15)
        if r.status_code != 200: return None
        result = r.json()["quoteSummary"]["result"][0]
        ks = result.get("defaultKeyStatistics",{}); fd = result.get("financialData",{}); sd = result.get("summaryDetail",{})
        def safe(d,k):
            v = d.get(k,{}); return v.get("raw") if isinstance(v,dict) else None
        return {"per":safe(sd,"trailingPE") or safe(ks,"trailingPE"),"pbv":safe(ks,"priceToBook"),
                "roe":safe(fd,"returnOnEquity"),"der":safe(fd,"debtToEquity"),
                "eps_growth":safe(ks,"earningsQuarterlyGrowth"),"rev_growth":safe(fd,"revenueGrowth")}
    except Exception:
        return None

def ema(d,p):
    if len(d)<p: return []
    out=[sum(d[:p])/p]; m=2/(p+1)
    for x in d[p:]: out.append((x-out[-1])*m+out[-1])
    return out
def rsi(d,p=14):
    if len(d)<p+1: return 50
    g=l=0
    for i in range(1,p+1):
        x=d[-i]-d[-i-1]
        if x>=0: g+=x
        else: l+=abs(x)
    ag,al=g/p,l/p
    if al==0: return 100
    return 100-(100/(1+ag/al))

def fund_detail(f):
    """Return skor + label + detail PBV/ROE/PER untuk position trading."""
    if not f: return 50,"N/A",{}
    sc,n=0,0; det={}
    if f.get("per") and f["per"]>0:
        per=f["per"]; det["PER"]=f"{per:.1f}x"
        sc+=90 if per<10 else 80 if per<15 else 65 if per<20 else 45 if per<30 else 25; n+=1
    if f.get("pbv") and f["pbv"]>0:
        pbv=f["pbv"]; det["PBV"]=f"{pbv:.2f}x"
        sc+=95 if pbv<1 else 80 if pbv<2 else 60 if pbv<3 else 40 if pbv<5 else 20; n+=1
    if f.get("roe") is not None:
        roe=f["roe"]*100; det["ROE"]=f"{roe:.1f}%"
        sc+=95 if roe>20 else 80 if roe>15 else 60 if roe>10 else 40 if roe>5 else 25 if roe>0 else 5; n+=1
    if f.get("der") is not None:
        der=f["der"]; det["DER"]=f"{der:.0f}%"
        sc+=90 if der<50 else 75 if der<100 else 55 if der<150 else 35 if der<200 else 15; n+=1
    if f.get("rev_growth") is not None:
        rg=f["rev_growth"]*100; det["Rev Growth"]=f"{rg:+.1f}%"
    if n==0: return 50,"N/A",det
    fin=sc/n
    lbl="💎 EXCELLENT" if fin>=75 else "✅ GOOD" if fin>=60 else "⚠️ FAIR" if fin>=45 else "❌ POOR"
    return fin,lbl,det

def analyze_position(symbol):
    d = fetch_chart(symbol)
    if not d: return None
    op,hi,lo,cl,vol = d["open"],d["high"],d["low"],d["close"],d["volume"]
    harga = cl[-1]
    e20,e50,e100 = ema(cl,20),ema(cl,50),ema(cl,100)
    if not e50 or not e100: return None
    rv = rsi(cl)

    # Tren menengah-panjang (untuk 1-2 bulan)
    score = 0
    above50 = harga > e50[-1]
    above100 = harga > e100[-1]
    if above50: score += 4
    if above100: score += 4
    if e50[-1] > e100[-1]: score += 5  # golden alignment

    # Momentum menengah: harga 20 hari lalu vs sekarang
    mom_20 = (cl[-1]-cl[-20])/cl[-20]*100 if len(cl)>=20 else 0
    mom_60 = (cl[-1]-cl[-60])/cl[-60]*100 if len(cl)>=60 else 0

    # Posisi dalam tren
    posisi = ""
    if above50 and above100 and mom_20 > 0 and mom_20 < 15:
        score += 5; posisi = "🌱 Awal Uptrend"
    elif above100 and -8 < mom_20 < 2 and e50[-1] > e100[-1]:
        score += 4; posisi = "💧 Koreksi Sehat"  # diskon di tren naik
    elif above50 and above100:
        score += 2; posisi = "📈 Uptrend Berjalan"
    else:
        posisi = "⏳ Belum Tren"

    # RSI: hindari overbought (untuk masuk posisi baru)
    if 40 <= rv <= 60: score += 4  # zona ideal masuk
    elif 60 < rv <= 70: score += 1
    elif rv > 72: score -= 4  # sudah overbought
    elif rv < 35: score += 2  # oversold, potensi pantul

    # Volume tren (akumulasi jangka menengah)
    avgv_recent = sum(vol[-20:])/20
    avgv_old = sum(vol[-60:-20])/40
    vol_trend_up = avgv_recent > avgv_old * 1.1
    if vol_trend_up: score += 3

    # Potensi upside: jarak ke resistance 6 bulan
    res_6m = max(hi[-120:]) if len(hi)>=120 else max(hi)
    sup_3m = min(lo[-60:]) if len(lo)>=60 else min(lo)
    upside = (res_6m - harga)/harga*100
    downside = (harga - sup_3m)/harga*100
    rr = upside/downside if downside > 0 else 0

    # Fundamental (lebih berbobot untuk position)
    fund = fetch_fundamental(symbol)
    fs, fl, fdet = fund_detail(fund)

    # Skor gabungan: teknikal + fundamental seimbang
    total = score + (fs-50)*0.3

    # Bonus kalau fundamental bagus DAN upside besar
    if fs >= 60 and upside >= 15: total += 5

    # Keputusan
    if total >= 22 and fs >= 55 and upside >= 12 and rv < 70:
        dec = "🌟 TOP PICK"
    elif total >= 16 and fs >= 45 and upside >= 10:
        dec = "✅ LAYAK PANTAU"
    elif total >= 10:
        dec = "👀 WATCH"
    else:
        dec = "🚫 SKIP"

    conf = max(0, min(95, int(total*2.5 + (fs-50)*0.3)))
    sector = next((s for s,l in SEKTOR.items() if symbol in l),"LAINNYA")
    return {"symbol":symbol.replace(".JK",""),"sector":sector,"harga":harga,
            "change":(cl[-1]-cl[-2])/cl[-2]*100 if len(cl)>1 else 0,
            "fs":fs,"fl":fl,"fdet":fdet,"upside":upside,"downside":downside,"rr":rr,
            "mom20":mom_20,"mom60":mom_60,"rsi":rv,"posisi":posisi,"dec":dec,"conf":conf,
            "res":res_6m,"sup":sup_3m,"total":total}

@st.cache_data(ttl=3600)
def backtest_position(symbol, target_pct=20, sl_pct=10, hold_days=40):
    """Backtest: berapa % sinyal naik >=20% dalam ~40 hari (2 bulan trading)."""
    d = fetch_chart(symbol, rng="2y")
    if not d: return None
    cl,hi,lo,vol = d["close"],d["high"],d["low"],d["volume"]
    wins=total=0
    for i in range(120, len(cl)-hold_days):
        sub = cl[:i]; subhi = hi[:i]; sublo = lo[:i]
        e50,e100 = ema(sub,50),ema(sub,100)
        if not e50 or not e100: continue
        rv = rsi(sub)
        above50 = sub[-1]>e50[-1]; above100 = sub[-1]>e100[-1]
        mom20 = (sub[-1]-sub[-20])/sub[-20]*100 if len(sub)>=20 else 0
        # Sinyal position: tren naik + RSI belum overbought + momentum positif tipis
        sig = (above50 and above100 and e50[-1]>e100[-1] and 40<=rv<=68 and 0<mom20<20)
        if sig:
            entry = cl[i]
            fhigh = max(hi[i+1:i+1+hold_days])
            flow = min(lo[i+1:i+1+hold_days])
            gain = (fhigh-entry)/entry*100
            loss = (flow-entry)/entry*100
            total+=1
            if gain>=target_pct: wins+=1
    if total==0: return None
    return {"symbol":symbol.replace(".JK",""),"total":total,"wins":wins,"win_rate":wins/total*100}

fmtp = lambda p:"Rp "+format(round(p),",")

c1,c2 = st.columns([3,1])
with c1:
    st.markdown("# 📈 Position Scanner")
    st.caption(f"Investasi 1-2 Bulan · Target ~20% · Fundamental + Tren Menengah · {datetime.now().strftime('%d %b %Y · %H:%M')}")
with c2:
    if st.button("🔄 Refresh", use_container_width=True, type="primary"):
        st.cache_data.clear(); st.rerun()

st.info("💡 Sistem ini TERPISAH dari swing scanner. Fokus: saham sehat + tren naik + potensi upside besar untuk ditahan 1-2 bulan.")

if 'pos_results' not in st.session_state:
    st.session_state.pos_results=None
if st.session_state.pos_results is None:
    prog = st.progress(0,text="Memindai saham...")
    res=[]
    for i,s in enumerate(WATCHLIST):
        prog.progress((i+1)/len(WATCHLIST),text=f"Scanning {s}... ({i+1}/{len(WATCHLIST)})")
        r = analyze_position(s)
        if r: res.append(r)
    prog.empty()
    st.session_state.pos_results = sorted(res,key=lambda x:x["conf"],reverse=True)
results = st.session_state.pos_results or []

def card(s,cls="stock-card"):
    color = {"🌟 TOP PICK":"#00ff88","✅ LAYAK PANTAU":"#4da6ff","👀 WATCH":"#ffd32a","🚫 SKIP":"#ff4757"}.get(s["dec"],"#888")
    tp = s["res"]; sl = s["sup"]
    cc = "#00ff88" if s["change"]>=0 else "#ff4757"; cs = "+" if s["change"]>=0 else ""
    fd = s["fdet"]
    fund_html = " ".join([f'<span class="badge" style="background:#1a3a2a;color:#9fe;">{k}: {v}</span>' for k,v in fd.items()])
    st.markdown(f"""<div class="stock-card {cls}">
    <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
    <div><div style="font-size:20px;font-weight:800;color:#fff;">{s['symbol']}</div>
    <div style="font-size:11px;color:#888;">{s['sector']} · {s['posisi']}</div></div>
    <div style="text-align:right;"><div style="font-size:18px;font-weight:700;color:#fff;">{fmtp(s['harga'])}</div>
    <div style="font-size:12px;color:{cc};">{cs}{s['change']:.2f}%</div></div></div>
    <div style="background:#0a140d;border-radius:8px;padding:10px;margin-bottom:10px;">
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;text-align:center;">
    <div><div style="font-size:10px;color:#666;">CONFIDENCE</div><div style="font-size:18px;font-weight:700;color:{color};">{s['conf']}%</div></div>
    <div><div style="font-size:10px;color:#666;">UPSIDE</div><div style="font-size:16px;font-weight:700;color:#00ff88;">+{s['upside']:.0f}%</div></div>
    <div><div style="font-size:10px;color:#666;">R/R</div><div style="font-size:16px;font-weight:700;color:#ffd32a;">{s['rr']:.1f}x</div></div></div></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;font-size:12px;">
    <div style="background:#0a140d;padding:6px 10px;border-radius:6px;"><span style="color:#666;">🎯 Target:</span> <span style="color:#fff;">{fmtp(tp)}</span></div>
    <div style="background:#0a140d;padding:6px 10px;border-radius:6px;"><span style="color:#666;">🛑 Stop:</span> <span style="color:#fff;">{fmtp(sl)}</span></div></div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px;">
    <span class="badge" style="background:{color}22;color:{color};border:1px solid {color}66;">{s['dec']}</span>
    <span class="badge" style="background:#2a4060;color:#ccc;">Fund: {s['fl']}</span></div>
    <div style="margin-bottom:6px;">{fund_html}</div>
    <div style="font-size:11px;color:#666;">RSI: {s['rsi']:.0f} · Mom 1bln: {s['mom20']:+.1f}% · Mom 3bln: {s['mom60']:+.1f}%</div></div>""",unsafe_allow_html=True)

t1,t2,t3,t4 = st.tabs(["🌟 Top Picks","📊 Semua","🧪 Backtest","ℹ️ Info"])
with t1:
    top = [s for s in results if "TOP PICK" in s["dec"] or "LAYAK PANTAU" in s["dec"]]
    st.markdown(f"### 🌟 {len(top)} Kandidat Position")
    st.caption("Saham sehat (fundamental) + tren menengah naik + potensi upside ≥10-12%.")
    if not top: st.info("Tidak ada kandidat kuat saat ini. Saat market lemah, wajar sedikit/kosong.")
    for s in top: card(s,"top-card")
with t2:
    st.markdown(f"### 📊 Semua ({len(results)})")
    mc = st.slider("Min Confidence",0,95,30,5)
    fil = [s for s in results if s["conf"]>=mc]
    if fil:
        df = pd.DataFrame([{"Saham":s["symbol"],"Sektor":s["sector"],"Harga":fmtp(s["harga"]),
            "Conf%":s["conf"],"Upside%":f"+{s['upside']:.0f}","R/R":f"{s['rr']:.1f}x",
            "PBV":s["fdet"].get("PBV","-"),"ROE":s["fdet"].get("ROE","-"),
            "Posisi":s["posisi"],"Sinyal":s["dec"]} for s in fil])
        st.dataframe(df,use_container_width=True,hide_index=True,height=500)
with t3:
    st.markdown("### 🧪 Backtest Position (Target 20% / 2 Bulan)")
    st.caption("Uji: berapa % sinyal historis BENAR naik ≥20% dalam ~40 hari trading (data 2 tahun). Win rate JUJUR.")
    st.warning("⏳ Backtest ini lebih lama (~2 menit) karena pakai data 2 tahun.")
    if st.button("▶️ Jalankan Backtest"):
        prog2 = st.progress(0,text="Backtesting...")
        bt=[]
        for i,s in enumerate(WATCHLIST):
            prog2.progress((i+1)/len(WATCHLIST),text=f"Backtest {s}...")
            r = backtest_position(s)
            if r and r["total"]>=2: bt.append(r)
        prog2.empty()
        if bt:
            tt = sum(r["total"] for r in bt); tw = sum(r["wins"] for r in bt)
            wr = tw/tt*100 if tt else 0
            st.metric("📊 Win Rate Keseluruhan", f"{wr:.1f}%", f"{tw}/{tt} sinyal")
            st.caption(f"Dari {tt} sinyal historis, {tw} berhasil naik ≥20% dalam ~2 bulan.")
            df_bt = pd.DataFrame([{"Saham":r["symbol"],"Total Sinyal":r["total"],
                "Menang":r["wins"],"Win Rate":f"{r['win_rate']:.0f}%"} for r in sorted(bt,key=lambda x:x["win_rate"],reverse=True)])
            st.dataframe(df_bt,use_container_width=True,hide_index=True,height=400)
            st.info("Catatan: target 20% itu ambisius, jadi win rate wajar lebih rendah dari swing. Yang penting R/R: untung 20% vs rugi ~10% = R/R 2:1.")
with t4:
    st.markdown("""
    ### ℹ️ Position Scanner (1-2 Bulan)
    
    **Bedanya dengan Swing Scanner:**
    | | Swing Scanner | Position Scanner |
    |--|--|--|
    | Tahan | 1-6 hari | 1-2 bulan |
    | Target | +5% | +20% |
    | Fokus | Teknikal cepat | Fundamental + tren menengah |
    | EMA | 20/50 | 50/100 |
    
    **Logika sistem ini:**
    - 📊 **Fundamental berbobot** — PBV, ROE, DER, PER ditampilkan jelas
    - 📈 **Tren menengah** — EMA 50 & 100, golden alignment
    - 🌱 **Posisi dalam tren** — cari "Awal Uptrend" atau "Koreksi Sehat" (diskon)
    - 🎯 **Upside besar** — jarak ke resistance 6 bulan (potensi ~20%)
    - 🛑 **RSI filter** — hindari masuk saat sudah overbought
    
    **Arti Posisi:**
    - 🌱 **Awal Uptrend** — baru mulai naik, potensi paling besar
    - 💧 **Koreksi Sehat** — diskon sementara di tren naik (beli saat murah)
    - 📈 **Uptrend Berjalan** — sudah naik, masih ok tapi upside berkurang
    
    ### 🎯 Cara Pakai
    1. Cek **Top Picks** — fokus 🌟 TOP PICK dengan Fund GOOD/EXCELLENT
    2. Lihat **PBV & ROE** — PBV rendah + ROE tinggi = murah tapi sehat (ideal)
    3. Pilih **R/R ≥ 1.5** dan upside ≥15%
    4. **Stop loss lebih lebar** (~8-10%) karena timeframe panjang
    5. **Position size lebih kecil** — karena stop lebih lebar, risiko per lembar lebih besar
    
    ### ⚠️ Disclaimer Penting
    - Target 20% dalam 1-2 bulan = **ambisius**, win rate wajar 30-45%
    - Tapi R/R bagus (20% untung vs 10% rugi) bikin tetap bisa profit
    - **TIDAK ADA** prediksi pasti — ini probabilitas
    - Data fundamental Yahoo untuk IDX kadang "N/A" — cek juga sumber resmi
    - Selalu pakai stop loss · jangan investasi uang yang tak siap rugi
    - Untuk corporate action (dividen/RUPS), cek langsung IDX & sekuritas kamu
    - Tools edukasi · keputusan & risiko di tangan kamu
    """)
