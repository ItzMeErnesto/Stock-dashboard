import streamlit as st
import pandas as pd
import yfinance as yf
import time

# Bestandspad van je originele BUX-export
BESTAND = "bux_export.csv"  # Zet hier de bestandsnaam van je eigen export

# == Pagina-instellingen ==
st.set_page_config(page_title="Mijn Aandelen Dashboard", layout="wide")
st.title("📈 Mijn Live Aandelen Dashboard")

# == Instellingen ==
REFRESH_INTERVAL = 60

st.caption(f"🔄 Dashboard wordt automatisch vernieuwd elke {REFRESH_INTERVAL} seconden.")

if st.button("🔁 Ververs data"):
    st.rerun()

# == Data inladen ==
@st.cache_data(ttl=0)
def laad_bux_data(pad):
    df = pd.read_csv(pad)
    df["Transaction Time (CET)"] = pd.to_datetime(df["Transaction Time (CET)"])
    return df

try:
    data = laad_bux_data(BESTAND)
except FileNotFoundError:
    st.error(f"❌ Bestand '{BESTAND}' niet gevonden.")
    st.stop()

# == Wisselkoers ophalen ==
try:
    usd_to_eur = 1 / yf.Ticker("EURUSD=X").history(period="1d")["Close"].iloc[-1]
except:
    usd_to_eur = 0.92
st.caption(f"💱 Wisselkoers USD → EUR: {usd_to_eur:.4f}")

# == Portfolio opbouwen ==
trades = data[data["Transaction Type"].isin(["Buy Trade", "Sell Trade"])].copy()
trades["Signed Quantity"] = trades.apply(
    lambda row: -row["Trade Quantity"] if row["Transaction Type"] == "Sell Trade" else row["Trade Quantity"], axis=1)
trades["Signed Amount"] = trades.apply(
    lambda row: -row["Trade Amount"] if row["Transaction Type"] == "Sell Trade" else row["Trade Amount"], axis=1)

portfolio = trades.groupby(["Asset Id", "Asset Name"], as_index=False).agg({
    "Signed Quantity": "sum",
    "Signed Amount": "sum"
})
portfolio = portfolio[portfolio["Signed Quantity"] > 0].copy()
portfolio["Aankoopprijs"] = portfolio["Signed Amount"] / portfolio["Signed Quantity"]

# Mapping naar yfinance tickers (handmatig uitbreiden indien nodig)
isin_to_ticker = {
    "NL0011540547": "ABN.AS", "NL0010273215": "ASML.AS", "FR001400J770": "AF.PA",
    "US0231351067": "AMZN", "US0378331005": "AAPL", "NL0011821202": "INGA.AS",
    "US30303M1027": "META", "NL0010773842": "NN.AS", "NL0009739416": "PNL.AS",
    "GB00BP6MXD84": "SHELL.AS", "US88160R1014": "TSLA", "IE000YYE6WK5": "DFEN.DE",
    "IE00B3XXRP09": "VUSA.AS", "NL0011794037": "AD.AS", "IE00B0M62Y33": "IDVY.AS"
}
portfolio["Ticker"] = portfolio["Asset Id"].map(isin_to_ticker)
portfolio = portfolio.dropna(subset=["Ticker"])
portfolio = portfolio[portfolio["Signed Quantity"] >= 0.001].copy()

# == Koersen ophalen ==
usd_tickers = ["AAPL", "AMZN", "META", "TSLA"]
prijzen = []
waarden = []
winst = []
winst_pct = []

for _, row in portfolio.iterrows():
    ticker = row["Ticker"]
    aantal = row["Signed Quantity"]
    aankoop = row["Aankoopprijs"]
    is_usd = ticker in usd_tickers

    try:
        koers = yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1]
        if is_usd:
            koers *= usd_to_eur
    except:
        koers = 0

    waarde = koers * aantal
    verschil = (koers - aankoop) * aantal
    verschil_pct = ((koers - aankoop) / aankoop) * 100 if aankoop > 0 else 0

    prijzen.append(koers)
    waarden.append(waarde)
    winst.append(verschil)
    winst_pct.append(verschil_pct)

portfolio["Aantal"] = portfolio["Signed Quantity"]
portfolio["Huidige Prijs (€)"] = prijzen
portfolio["Totale Waarde (€)"] = waarden
portfolio["Winst/Verlies (€)"] = winst
portfolio["Winst/Verlies (%)"] = winst_pct

# == Totaalwaarden ==
totaalwaarde = portfolio["Totale Waarde (€)"].sum()
totaalwinst = portfolio["Winst/Verlies (€)"].sum()

col1, col2 = st.columns(2)
col1.metric("💰 Totale Portfolio Waarde", f"€{totaalwaarde:,.2f}")
col2.metric("📈 Totale Winst/Verlies", f"€{totaalwinst:,.2f}", delta=f"{(totaalwinst / (totaalwaarde - totaalwinst) * 100):.2f}%" if totaalwaarde > 0 else None)

if totaalwinst > 0:
    st.balloons()
else:
    st.snow()

# == Portfolio tabel ==
st.subheader("📋 Portfolio Details")
st.dataframe(portfolio[["Asset Name", "Aantal", "Aankoopprijs", "Huidige Prijs (€)", "Totale Waarde (€)", "Winst/Verlies (€)", "Winst/Verlies (%)"]], use_container_width=True)

# == Dividendmatrix ==
div = data[data["Transaction Type"] == "Cash Dividend"].copy()
div["Jaar"] = div["Transaction Time (CET)"].dt.year
pivot = pd.pivot_table(
    div, index="Asset Name", columns="Jaar", values="Transaction Amount", aggfunc="sum", fill_value=0
).abs()
pivot.loc["Totaal"] = pivot.sum()
pivot["Totaal per Bedrijf"] = pivot.sum(axis=1)

st.subheader("💸 Ontvangen Dividend per Jaar")
st.dataframe(pivot, use_container_width=True)

# == Verdeling als grafiek ==
st.subheader("📌 Verdeling per Aandeel")
st.bar_chart(portfolio.set_index("Asset Name")["Totale Waarde (€)"])

# == Automatisch herladen ==
time.sleep(REFRESH_INTERVAL)
st.rerun()
