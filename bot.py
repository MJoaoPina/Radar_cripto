import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import deque
import requests
from flask import Flask

# ==============================================================================
# CONFIGURAÇÕES DO RADAR (ALTERAR APENAS AQUI)
# ==============================================================================
TELEGRAM_TOKEN = "9185644092:AAGBuvJwqs3XnFQ2r8I1nN70kZYQkTOaZqg"
CHAT_ID = 9290388900  # Coloca o teu número de Chat ID sem aspas

# Regras de Mercado
PERCENTUAL_ALERTA = 3.0       # Subida acumulada mínima (%) para disparar alerta
JANELA_MINUTOS = 5            # Janela deslizante máxima em minutos (Ex: 5 velas)
INTERVALO_LEITURA = 60        # Tempo entre leituras em segundos (60 = 1 minuto)

# Silêncio Noturno (Hora de Portugal - Europe/Lisbon)
SILENCIO_NOTURNO = False      # Muda para True para ativar o silêncio noturno
SILENCIO_INICIO = "01:00"     # Hora de início do silêncio (formato HH:MM)
SILENCIO_FIM = "07:30"        # Hora de fim do silêncio (formato HH:MM)

# Relatório Diário de "Pulso" (Hora de Portugal - Europe/Lisbon)
RELATORIO_DIARIO = True       # Muda para False se não quiseres o resumo diário
HORA_RELATORIO = "09:00"      # Hora de envio da confirmação diária (formato HH:MM)

# Lista Branca Oficial Revolut X (289 pares USD)
MOEDAS_PERMITIDAS = [
    "1INCH", "2Z", "A8", "AAVE", "ABT", "ACH", "ACS", "ADA", "AERGO", "AERO",
    "AGLD", "AI", "AIOZ", "AKT", "ALCX", "ALEO", "ALEPH", "ALGO", "ALICE", "AMP",
    "ANKR", "APE", "API3", "APT", "ARB", "ARKM", "ARPA", "ASM", "AST", "ATH",
    "ATOM", "AUCTION", "AUDIO", "AURORA", "AVAX", "AVNT", "AVT", "AWE", "AXS", "B3",
    "BAL", "BAND", "BAT", "BCH", "BEAM", "BENJI", "BERA", "BICO", "BIGTIME", "BLUR",
    "BLZ", "BNB", "BNT", "BOBA", "BONK", "BTC", "BTRST", "C98", "CC", "CELO",
    "CELR", "CHZ", "CLANKER", "COMP", "COOKIE", "COTI", "COW", "CRO", "CRV", "CTSI",
    "CVC", "CVX", "DASH", "DEGEN", "DIA", "DIMO", "DOGE", "DOGINME", "DOGS", "DOT",
    "DRIFT", "DYDX", "EDGE", "EGLD", "EIGEN", "ELA", "ENA", "ENS", "ETC", "ETH",
    "EUL", "FAI", "FARM", "FET", "FIDA", "FIL", "FLOKI", "FLOW", "FLR", "FORT",
    "GALA", "GFI", "GHST", "GIGA", "GLM", "GMT", "GODS", "GRASS", "GRT", "GTC",
    "GUN", "HBAR", "HFT", "HIGH", "HNT", "HONEY", "HOPR", "HYPE", "ICP", "IDOS",
    "ILV", "IMU", "IMX", "INIT", "INJ", "IO", "IP", "JASMY", "JTO", "JUP",
    "KAITO", "KARRAT", "KAVA", "KERNEL", "KNC", "KRL", "KSM", "KTA", "L3", "LA",
    "LAYER", "LCX", "LDO", "LINK", "LMWR", "LPT", "LQTY", "LRC", "LRDS", "LTC",
    "MAGIC", "MANA", "MASK", "MATH", "MDT", "ME", "MELANIA", "METIS", "MEW", "MINA",
    "MLN", "MNDE", "MOG", "MON", "MOODENG", "MORPHO", "MSOL", "NCT", "NEAR", "NEIRO",
    "NKN", "NMR", "NOT", "OCEAN", "OFC", "OGN", "ONDO", "OP", "ORCA", "OSMO",
    "OXT", "PARTI", "PENDLE", "PENGU", "PEPE", "PERP", "PLUME", "PNG", "PNUT", "POL",
    "POLS", "POND", "PONKE", "POPCAT", "POWR", "PRCL", "PRIME", "PRO", "PROMPT", "PROVE",
    "PUMP", "PUNDIX", "PYTH", "QI", "QNT", "RAD", "RARE", "RARI", "RAY", "RED",
    "RENDER", "REQ", "REZ", "RLC", "RLS", "ROSE", "RPL", "RSC", "RSR", "SAFE",
    "SAND", "SD", "SEI", "SENT", "SHDW", "SHIB", "SHPING", "SKL", "SKY", "SNX",
    "SOL", "SPA", "SPELL", "SPK", "SPX", "SQD", "STG", "STORJ", "STRK", "STX",
    "SUI", "SUKU", "SUPER", "SUSHI", "SWELL", "SWFTC", "SXT", "SYRUP", "TAIKO", "TIA",
    "TNSR", "TOKEN", "TON", "TOSHI", "TRAC", "TRB", "TREE", "TRU", "TRUMP", "TRX",
    "TURBO", "UMA", "UNI", "USDC", "VET", "VTHO", "VVV", "WAL", "WIF", "WLD",
    "WLFI", "WOO", "XAN", "XCN", "XDC", "XLM", "XPL", "XRP", "XTZ", "XYO",
    "YFI", "ZAMA", "ZEN", "ZK", "ZKC", "ZKJ", "ZORA", "ZRO", "ZRX"
]
# ==============================================================================

app = Flask(__name__)
FUSO_PT = ZoneInfo("Europe/Lisbon")
PERMITIDAS_SET = {m.strip().upper() for m in MOEDAS_PERMITIDAS if m.strip()}

historico_precos = {}
ultimo_dia_relatorio = ""

@app.route('/')
def home():
    return f"Radar Revolut X Ativo | Moedas USD monitorizadas: {len(PERMITIDAS_SET)}"

def enviar_telegram(texto):
    host_tg = ".".join(["api", "telegram", "org"])
    url_final = f"https://{host_tg}/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto}
    try:
        requests.post(url_final, json=payload, timeout=10)
    except Exception:
        pass

def formatar_preco(valor):
    if valor >= 100:
        return f"${valor:.2f}"
    elif valor >= 1:
        return f"${valor:.4f}"
    elif valor >= 0.01:
        return f"${valor:.5f}"
    else:
        return f"${valor:.8f}"

def esta_em_silencio_noturno():
    if not SILENCIO_NOTURNO:
        return False
    agora_str = datetime.now(FUSO_PT).strftime("%H:%M")
    if SILENCIO_INICIO <= SILENCIO_FIM:
        return SILENCIO_INICIO <= agora_str < SILENCIO_FIM
    return agora_str >= SILENCIO_INICIO or agora_str < SILENCIO_FIM

def obter_precos_usd():
    host_cb = ".".join(["api", "coinbase", "com"])
    url = f"https://{host_cb}/v2/exchange-rates?currency=USD"
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            taxas = resposta.json().get("data", {}).get("rates", {})
            precos = {}
            for moeda, taxa in taxas.items():
                if moeda not in PERMITIDAS_SET:
                    continue
                try:
                    valor_taxa = float(taxa)
                    if valor_taxa > 0:
                        precos[moeda] = 1.0 / valor_taxa
                except ValueError:
                    continue
            return precos
    except Exception:
        return None
    return None

def loop_radar():
    global ultimo_dia_relatorio
    enviar_telegram(
        f"🚀 Radar Revolut X Iniciado!\n"
        f"Moedas USD na lista branca: {len(PERMITIDAS_SET)}\n"
        f"Janela: {JANELA_MINUTOS} min | Gatilho: +{PERCENTUAL_ALERTA}%"
    )

    while True:
        inicio_ciclo = time.time()
        agora_pt = datetime.now(FUSO_PT)

        if RELATORIO_DIARIO:
            hoje_str = agora_pt.strftime("%Y-%m-%d")
            hora_atual_str = agora_pt.strftime("%H:%M")
            if hoje_str != ultimo_dia_relatorio and hora_atual_str == HORA_RELATORIO:
                ultimo_dia_relatorio = hoje_str
                enviar_telegram(f"✅ Radar Revolut X Ativo ({len(PERMITIDAS_SET)} moedas USD monitorizadas)")

        precos_atuais = obter_precos_usd()

        if precos_atuais:
            alertas_do_minuto = []
            for moeda, preco_atual in precos_atuais.items():
                if moeda not in historico_precos:
                    historico_precos[moeda] = deque(maxlen=JANELA_MINUTOS)

                fila_precos = historico_precos[moeda]
                if len(fila_precos) > 0:
                    lista_valores = list(fila_precos)
                    menor_preco_janela = min(lista_valores)
                    indice_minimo = lista_valores.index(menor_preco_janela)
                    minutos_decorridos = len(lista_valores) - indice_minimo

                    if menor_preco_janela > 0:
                        variacao = ((preco_atual - menor_preco_janela) / menor_preco_janela) * 100
                        if variacao >= PERCENTUAL_ALERTA:
                            preco_txt = formatar_preco(preco_atual)
                            alertas_do_minuto.append(f"🟢 {moeda}: +{variacao:.2f}% em {minutos_decorridos} min ({preco_txt})")
                            fila_precos.clear()

                fila_precos.append(preco_atual)

            if alertas_do_minuto and not esta_em_silencio_noturno():
                mensagem_final = f"⚠️ Subidas Rápidas Revolut X (Janela {JANELA_MINUTOS}m):\n\n" + "\n".join(alertas_do_minuto[:35])
                enviar_telegram(mensagem_final)

        tempo_decorrido = time.time() - inicio_ciclo
        tempo_espera = max(1, INTERVALO_LEITURA - tempo_decorrido)
        time.sleep(tempo_espera)

if __name__ == "__main__":
    threading.Thread(target=loop_radar, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
