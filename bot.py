import time
import threading
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask

# ==============================================================================
# 1. CREDENCIAIS DO TELEGRAM (Cole aqui os seus dados)
# ==============================================================================
TELEGRAM_TOKEN = "9185644092:AAGBuvJwqs3XnFQ2r8I1nN70kZYQkTOaZqg"
CHAT_ID = 9290388900

# ==============================================================================
# 2. INTERRUPTORES DOS PADRÕES (True = Ligado | False = Desligado)
# ==============================================================================
PROCURAR_ESTRELA_MANHA = True       # Padrão 1: Vermelha -> Pequena -> Verde
PROCURAR_TRES_SOLDADOS = True       # Padrão 2: 3 Verdes seguidas de força
PROCURAR_TRES_POR_DENTRO = True     # Padrão 3: Vermelha -> Verde dentro -> Verde rompe topo

# ==============================================================================
# 3. RADAR INDEPENDENTE DO BITCOIN (Avisa movimentos bruscos do BTC)
# ==============================================================================
ALERTA_INDEPENDENTE_BTC = True      # True = Envia alerta próprio quando o BTC mexe muito
VARIACAO_ALERTA_BTC = 0.80          # Avisa se o BTC subir ou cair mais de 0.80% numa vela de 15m

# ==============================================================================
# 4. PAINEL DE RIGOR E FILTROS (Altere apenas os valores à direita do =)
# ==============================================================================
MODO_ESTRITO = False                # False = Envia todos com nota | True = Só Alta Probabilidade (4/4)
MOVIMENTO_MINIMO_PCT = 1.5          # Suba para 2.0 para menos alertas; baixe para 1.2 para mais alertas
LIMITE_ESTICADO_SOLDADOS = 4.5      # Se 3 Soldados subirem mais que isto, avisa que está esticado
TAMANHO_MAX_ESTRELA = 0.35          # Tamanho máximo da 2.ª vela na Estrela da Manhã (35% da 1.ª)
LIMITE_QUEDA_BTC = -0.50            # Se o BTC cair mais que isto, rebaixa a nota das altcoins

SILENCIO_NOTURNO = False            # Mude para True para silenciar à noite
SILENCIO_INICIO = "01:00"
SILENCIO_FIM = "07:30"

RELATORIO_DIARIO = True             # Confirmação diária de que o bot está ativo
HORA_RELATORIO = "09:00"

# ==============================================================================
# 5. LISTA DE MOEDAS DA REVOLUT X (Cole aqui as suas 289 moedas)
# ==============================================================================
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
]

# ==============================================================================
# MOTOR DO BOT (Não precisa de alterar nada daqui para baixo)
# ==============================================================================
app = Flask(__name__)
FUSO_PT = ZoneInfo("Europe/Lisbon")
PERMITIDAS_LISTA = sorted({m.strip().upper() for m in MOEDAS_PERMITIDAS if m.strip()})
ultimo_dia_relatorio = ""

@app.route('/')
def home():
    modo_txt = "ESTRITO (Só 4/4)" if MODO_ESTRITO else "COMPLETO (Com Conselho)"
    return f"Radar 15m Triplo + BTC Ativo | Moedas: {len(PERMITIDAS_LISTA)} | Modo: {modo_txt}"

def enviar_telegram(texto):
    host_tg = ".".join(["api", "telegram", "org"])
    url_final = f"https://{host_tg}/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto}
    try:
        requests.post(url_final, json=payload, timeout=10)
    except Exception:
        pass

def esta_em_silencio_noturno():
    if not SILENCIO_NOTURNO:
        return False
    agora_str = datetime.now(FUSO_PT).strftime("%H:%M")
    if SILENCIO_INICIO <= SILENCIO_FIM:
        return SILENCIO_INICIO <= agora_str < SILENCIO_FIM
    return agora_str >= SILENCIO_INICIO or agora_str < SILENCIO_FIM

def obter_velas_15m(moeda):
    host_cb = ".".join(["api", "exchange", "coinbase", "com"])
    url = f"https://{host_cb}/products/{moeda}-USD/candles?granularity=900"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resposta = requests.get(url, headers=headers, timeout=10)
        if resposta.status_code == 200:
            dados = resposta.json()
            if isinstance(dados, list) and len(dados) >= 12:
                return dados
    except Exception:
        pass
    return None

def analisar_contexto_btc():
    velas_btc = obter_velas_15m("BTC")
    if not velas_btc:
        return True, 0.0, None

    _, ultima_fechada, anterior_fechada, *_ = velas_btc
    _, _, _, abertura, fecho, vol_atual = map(float, ultima_fechada)
    _, _, _, _, _, vol_anterior = map(float, anterior_fechada)

    alerta_btc = None
    if abertura > 0:
        variacao_btc = ((fecho - abertura) / abertura) * 100
        btc_saudavel = variacao_btc >= LIMITE_QUEDA_BTC

        if ALERTA_INDEPENDENTE_BTC and abs(variacao_btc) >= VARIACAO_ALERTA_BTC:
            forca_vol = "Volume Forte 🔥" if vol_atual > vol_anterior else "Volume Normal"
            if variacao_btc <= -VARIACAO_ALERTA_BTC:
                alerta_btc = (
                    f"🚨 RADAR BITCOIN (15m): QUEDA BRUSCA\n"
                    f"📉 Variação: {variacao_btc:.2f}% (Preço: ${fecho:,.0f})\n"
                    f"📊 Força: {forca_vol}\n"
                    f"💡 Conselho: Evite comprar Altcoins agora; o BTC está a puxar o mercado para baixo."
                )
            else:
                alerta_btc = (
                    f"🚀 RADAR BITCOIN (15m): SUBIDA FORTE\n"
                    f"📈 Variação: +{variacao_btc:.2f}% (Preço: ${fecho:,.0f})\n"
                    f"📊 Força: {forca_vol}\n"
                    f"💡 Conselho: BTC a ganhar força; bom ambiente para procurar entradas em Altcoins."
                )

        return btc_saudavel, variacao_btc, alerta_btc
    return True, 0.0, None

def gerar_conselho_e_risco(pontos, risco_pct, vol_bom, btc_saudavel, esticado=False):
    if pontos == 4:
        etiqueta = "🟢 ALTA PROBABILIDADE (4/4)"
    elif pontos == 3:
        etiqueta = "🟡 MÉDIA PROBABILIDADE (3/4)"
    else:
        etiqueta = f"⚪ BAIXA PROBABILIDADE ({pontos}/4)"

    if risco_pct <= 2.2:
        txt_risco = f"🛡️ Risco Curto/Ideal: -{risco_pct:.2f}% até ao fundo das 3 velas"
    elif risco_pct <= 3.5:
        txt_risco = f"⚖️ Risco Moderado: -{risco_pct:.2f}% até ao fundo das 3 velas"
    else:
        txt_risco = f"⚠️ Risco Alto (Stop Longo): -{risco_pct:.2f}% até ao fundo das 3 velas"

    if not btc_saudavel:
        conselho = "💡 Conselho: Cuidado! O BTC está a cair e pode anular este padrão. Melhor só observar."
    elif esticado:
        conselho = "💡 Conselho: O preço já subiu demasiado nas 3 velas. Não persiga; espere um recuo."
    elif pontos == 4 and risco_pct <= 2.8:
        conselho = "💡 Conselho: Cenário muito limpo (volume + contexto). Boa candidata para Ordem Limite na Revolut X."
    elif pontos >= 3 and not vol_bom:
        conselho = "💡 Conselho: Desenho bonito mas pouco volume. Confirme no livro de ordens da Revolut X antes de entrar."
    elif risco_pct > 3.5:
        conselho = "💡 Conselho: Padrão válido, mas o Stop Loss fica muito longe. Entre com valor reduzido se arriscar."
    else:
        conselho = "💡 Conselho: Sinal intermédio. Use este alerta para treinar a leitura no gráfico de 15m."

    return etiqueta, txt_risco, conselho

def analisar_padroes(moeda, velas, btc_saudavel, variacao_btc):
    v0, v3, v2, v1, a1, a2, a3, a4, a5, a6, *_ = velas

    _, v1_low, v1_high, v1_open, v1_close, v1_vol = map(float, v1)
    _, v2_low, v2_high, v2_open, v2_close, v2_vol = map(float, v2)
    _, v3_low, v3_high, v3_open, v3_close, v3_vol = map(float, v3)

    _, _, _, _, _, vol_a1 = map(float, a1)
    _, _, _, _, _, vol_a2 = map(float, a2)
    _, _, _, _, _, vol_a3 = map(float, a3)
    _, _, _, _, _, vol_a4 = map(float, a4)
    _, _, _, _, _, vol_a5 = map(float, a5)
    _, _, _, _, preco_90m_antes, vol_a6 = map(float, a6)

    if v1_open <= 0 or v2_open <= 0 or v3_open <= 0 or preco_90m_antes <= 0:
        return None

    queda_previa = ((preco_90m_antes - v1_open) / preco_90m_antes) * 100
    if queda_previa < 1.0:
        return None

    fundo_padrao = min(v1_low, v2_low, v3_low)
    risco_pct = ((v3_close - fundo_padrao) / v3_close) * 100

    media_vol = (vol_a1 + vol_a2 + vol_a3 + vol_a4 + vol_a5 + vol_a6) / 6.0
    vol_bom = (v3_vol > v2_vol) and (v3_vol > media_vol)

    # PADRÃO 1: ESTRELA DA MANHÃ
    if PROCURAR_ESTRELA_MANHA:
        queda_v1 = ((v1_open - v1_close) / v1_open) * 100
        corpo_v1 = abs(v1_open - v1_close)
        corpo_v2 = abs(v2_open - v2_close)
        meio_v1 = v1_close + (corpo_v1 * 0.50)

        if (v1_close < v1_open and queda_v1 >= MOVIMENTO_MINIMO_PCT and
            corpo_v2 <= (corpo_v1 * TAMANHO_MAX_ESTRELA) and
            v3_close > v3_open and v3_close >= meio_v1):

            pontos = 0
            detalhes = []
            if queda_previa >= 2.5:
                pontos += 1
                detalhes.append(f"✅ Queda forte antes (-{queda_previa:.2f}%)")
            else:
                detalhes.append(f"➖ Queda ligeira antes (-{queda_previa:.2f}%)")

            if v3_close >= v1_close + (corpo_v1 * 0.70):
                pontos += 1
                detalhes.append("✅ Recuperação forte (>70% da V1)")
            else:
                detalhes.append("➖ Recuperação moderada (>50% da V1)")

            if vol_bom:
                pontos += 1
                detalhes.append("✅ Volume comprador acima da média")
            else:
                detalhes.append("⚠️ Volume fraco na 3.ª vela")

            if btc_saudavel:
                pontos += 1
                detalhes.append(f"✅ BTC estável ({variacao_btc:+.2f}%)")
            else:
                detalhes.append(f"🚨 BTC em queda ({variacao_btc:+.2f}%)")

            if MODO_ESTRITO and pontos < 4:
                return None

            subida_v3 = ((v3_close - v3_open) / v3_open) * 100
            etiqueta, txt_risco, conselho = gerar_conselho_e_risco(pontos, risco_pct, vol_bom, btc_saudavel)
            return (
                f"{etiqueta}\n⭐ Padrão: ESTRELA DA MANHÃ\n🪙 Moeda: {moeda} (15m)\n"
                f"📊 V1: -{queda_v1:.2f}% | V3: +{subida_v3:.2f}%\n{txt_risco}\n"
                + "\n".join(detalhes) + f"\n{conselho}"
            )
                
    # PADRÃO 2: TRÊS POR DENTRO PARA CIMA
    if PROCURAR_TRES_POR_DENTRO:
        queda_v1 = ((v1_open - v1_close) / v1_open) * 100
        if (v1_close < v1_open and queda_v1 >= MOVIMENTO_MINIMO_PCT and
            v2_close > v2_open and v2_open >= v1_close and v2_close <= v1_open and
            v3_close > v3_open and v3_close > v1_open):

            pontos = 0
            detalhes = []
            if queda_previa >= 2.5:
                pontos += 1
                detalhes.append(f"✅ Queda forte antes (-{queda_previa:.2f}%)")
            else:
                detalhes.append(f"➖ Queda ligeira antes (-{queda_previa:.2f}%)")

            if v3_close > v1_high:
                pontos += 1
                detalhes.append("✅ Rompeu até o pavio máximo da V1")
            else:
                detalhes.append("➖ Rompeu o corpo da V1")

            if vol_bom:
                pontos += 1
                detalhes.append("✅ Volume comprador acima da média")
            else:
                detalhes.append("⚠️ Volume fraco no rompimento")

            if btc_saudavel:
                pontos += 1
                detalhes.append(f"✅ BTC estável ({variacao_btc:+.2f}%)")
            else:
                detalhes.append(f"🚨 BTC em queda ({variacao_btc:+.2f}%)")

            if MODO_ESTRITO and pontos < 4:
                return None

            subida_v3 = ((v3_close - v3_open) / v3_open) * 100
            etiqueta, txt_risco, conselho = gerar_conselho_e_risco(pontos, risco_pct, vol_bom, btc_saudavel)
            return (
                f"{etiqueta}\n🛡️ Padrão: TRÊS POR DENTRO P/ CIMA\n🪙 Moeda: {moeda} (15m)\n"
                f"📊 V1: -{queda_v1:.2f}% | V3: +{subida_v3:.2f}%\n{txt_risco}\n"
                + "\n".join(detalhes) + f"\n{conselho}"
            )

    # PADRÃO 3: TRÊS SOLDADOS BRANCOS
    if PROCURAR_TRES_SOLDADOS:
        subida_total = ((v3_close - v1_open) / v1_open) * 100
        if (v1_close > v1_open and v2_close > v2_open and v3_close > v3_open and
            v2_close > v1_close and v3_close > v2_close and
            v2_open >= v1_open and v3_open >= v2_open and
            subida_total >= MOVIMENTO_MINIMO_PCT):

            pontos = 0
            detalhes = []
            esticado = subida_total > LIMITE_ESTICADO_SOLDADOS

            if not esticado:
                pontos += 1
                detalhes.append(f"✅ Subida saudável (+{subida_total:.2f}%)")
            else:
                detalhes.append(f"⚠️ Movimento esticado (+{subida_total:.2f}%)")

            corpo_v3 = v3_close - v3_open
            pavio_sup_v3 = v3_high - v3_close
            if pavio_sup_v3 <= (corpo_v3 * 0.30):
                pontos += 1
                detalhes.append("✅ Fecho forte no topo (sem rejeição)")
            else:
                detalhes.append("⚠️ Pavio superior longo na 3.ª vela")

            if vol_bom and v2_vol > v1_vol:
                pontos += 1
                detalhes.append("✅ Volume crescente nos 3 soldados")
            else:
                detalhes.append("⚠️ Volume irregular")

            if btc_saudavel:
                pontos += 1
                detalhes.append(f"✅ BTC estável ({variacao_btc:+.2f}%)")
            else:
                detalhes.append(f"🚨 BTC em queda ({variacao_btc:+.2f}%)")

            if MODO_ESTRITO and pontos < 4:
                return None

            etiqueta, txt_risco, conselho = gerar_conselho_e_risco(pontos, risco_pct, vol_bom, btc_saudavel, esticado)
            return (
                f"{etiqueta}\n🪖 Padrão: TRÊS SOLDADOS BRANCOS\n🪙 Moeda: {moeda} (15m)\n"
                f"📉 Queda antes: -{queda_previa:.2f}% | 📈 Subida 3v: +{subida_total:.2f}%\n{txt_risco}\n"
                + "\n".join(detalhes) + f"\n{conselho}"
            )

    return None

def aguardar_proximo_fecho_15m():
    agora = datetime.now(FUSO_PT)
    minutos_para_proximo = 15 - (agora.minute % 15)
    segundos_espera = (minutos_para_proximo * 60) - agora.second + 5
    if segundos_espera <= 5:
        segundos_espera += 900
    return segundos_espera

def loop_radar():
    global ultimo_dia_relatorio
    modo_str = "ESTRITO (Só 4/4)" if MODO_ESTRITO else "COMPLETO (Com Conselho)"
    enviar_telegram(
        f"🚀 Radar 15m Triplo + BTC Iniciado!\n"
        f"Moedas Revolut X: {len(PERMITIDAS_LISTA)}\n"
        f"Modo: {modo_str} | Alerta BTC: ±{VARIACAO_ALERTA_BTC}%"
    )

    while True:
        time.sleep(aguardar_proximo_fecho_15m())
        agora_pt = datetime.now(FUSO_PT)

        if RELATORIO_DIARIO:
            hoje_str = agora_pt.strftime("%Y-%m-%d")
            hora_atual_str = agora_pt.strftime("%H:%M")
            if hoje_str != ultimo_dia_relatorio and hora_atual_str.startswith(HORA_RELATORIO[:3]):
                if int(hora_atual_str[3:]) >= int(HORA_RELATORIO[3:]):
                    ultimo_dia_relatorio = hoje_str
                    enviar_telegram(f"✅ Radar 15m Ativo ({len(PERMITIDAS_LISTA)} moedas vigiadas)")

        if esta_em_silencio_noturno():
            continue

        btc_saudavel, variacao_btc, alerta_btc = analisar_contexto_btc()
        if alerta_btc:
            enviar_telegram(alerta_btc)
        time.sleep(0.15)

        for moeda in PERMITIDAS_LISTA:
            velas = obter_velas_15m(moeda)
            if velas:
                alerta = analisar_padroes(moeda, velas, btc_saudavel, variacao_btc)
                if alerta:
                    enviar_telegram(alerta)
            time.sleep(0.15)

if __name__ == "__main__":
    threading.Thread(target=loop_radar, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
