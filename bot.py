import time
import threading
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask

# ==============================================================================
# 1. CREDENCIAIS DO TELEGRAM (Cole aqui os seus dados do código anterior)
# ==============================================================================
TELEGRAM_TOKEN = "9185644092:AAGBuvJwqs3XnFQ2r8I1nN70kZYQkTOaZqg"
CHAT_ID = 9290388900

# ==============================================================================
# 2. PAINEL DE CONTROLO FÁCIL (Altere apenas os valores à direita do sinal =)
# ==============================================================================

# MODO DE FILTRAGEM:
# False = Envia TODOS os padrões encontrados e diz se é Alta, Média ou Baixa probabilidade.
# True  = Só envia mensagens se o sinal for de ALTA PROBABILIDADE (4/4 pontos).
MODO_ESTRITO = False

# RIGOR DA QUEDA INICIAL (Vela 1):
# Percentagem mínima que a 1.ª vela vermelha tem de cair para o padrão contar.
# Exemplo: 1.5 significa queda de pelo menos 1.5%.
QUEDA_MINIMA_VELA1 = 1.5

# TAMANHO DA VELA DE TRAVÃO (Vela 2 - O meio da Estrela):
# Tamanho máximo do corpo da 2.ª vela comparado com a 1.ª vela.
# 0.35 significa que a 2.ª vela tem de ser pequena (no máximo 35% do tamanho da 1.ª).
TAMANHO_MAX_ESTRELA = 0.35

# ALERTA DE QUEDA DO BITCOIN:
# Se o Bitcoin cair mais do que esta percentagem nos últimos 15 min, o bot rebaixa a nota e avisa-o.
LIMITE_QUEDA_BTC = -0.5

# SILÊNCIO NOTURNO (Hora de Portugal - Europe/Lisbon):
SILENCIO_NOTURNO = False        # Mude para True se não quiser mensagens enquanto dorme
SILENCIO_INICIO = "01:00"       # Hora de início do silêncio
SILENCIO_FIM = "07:30"          # Hora de fim do silêncio

# RELATÓRIO DIÁRIO DE VIDA (Hora de Portugal - Europe/Lisbon):
RELATORIO_DIARIO = True         # Envia 1 mensagem por dia para confirmar que o bot está ligado
HORA_RELATORIO = "09:00"        # Hora do aviso diário

# ==============================================================================
# 3. LISTA DE MOEDAS DA REVOLUT X (Cole aqui a sua lista das 289 moedas)
# ==============================================================================
MOEDAS_PERMITIDAS = [
    "ETH", "SOL", "XRP", "ADA", "AVAX", "LINK", "DOT", "SUI"
    # APAGUE ESTA LINHA DE EXEMPLO E COLE AQUI AS SUAS 289 MOEDAS
]

# ==============================================================================
# DAQUI PARA BAIXO É O MOTOR DO BOT (Não precisa de alterar nada)
# ==============================================================================

app = Flask(__name__)
FUSO_PT = ZoneInfo("Europe/Lisbon")
PERMITIDAS_LISTA = sorted({m.strip().upper() for m in MOEDAS_PERMITIDAS if m.strip()})
ultimo_dia_relatorio = ""

@app.route('/')
def home():
    modo_txt = "ESTRITO (Só Alta Prob.)" if MODO_ESTRITO else "TODOS OS SINAIS (Com Nota)"
    return f"Radar 15m Estrela da Manhã Ativo | Moedas: {len(PERMITIDAS_LISTA)} | Modo: {modo_txt}"

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
    """Vai buscar as últimas velas de 15 minutos à Coinbase Exchange."""
    host_cb = ".".join(["api", "exchange", "coinbase", "com"])
    url = f"https://{host_cb}/products/{moeda}-USD/candles?granularity=900"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resposta = requests.get(url, headers=headers, timeout=10)
        if resposta.status_code == 200:
            dados = resposta.json()
            if isinstance(dados, list) and len(dados) >= 25:
                return dados
    except Exception:
        pass
    return None
    
def analisar_contexto_btc():
    """Verifica se o Bitcoin caiu com força na última vela fechada de 15 min."""
    velas_btc = obter_velas_15m("BTC")
    if not velas_btc:
        return True, 0.0

    # Estrutura Coinbase: [0:timestamp, 1:low, 2:high, 3:open, 4:close, 5:volume]
    ultima_fechada = velas_btc[1]
    abertura = float(ultima_fechada[3])
    fecho = float(ultima_fechada[4])

    if abertura > 0:
        variacao_btc = ((fecho - abertura) / abertura) * 100
        btc_saudavel = variacao_btc >= LIMITE_QUEDA_BTC
        return btc_saudavel, variacao_btc
    return True, 0.0

def analisar_estrela_manha(moeda, velas, btc_saudavel, variacao_btc):
    """Analisa se as últimas 3 velas fechadas formam uma Estrela da Manhã e dá uma nota."""
    # velas[0] é a vela atual ainda aberta (ignoramos)
    v3 = velas[1]  # Vela 3 (Última fechada - Confirmação Verde)
    v2 = velas[2]  # Vela 2 (Penúltima fechada - Estrela / Travão)
    v1 = velas[3]  # Vela 1 (Antepenúltima fechada - Queda Vermelha)

    v1_open, v1_close, v1_vol = float(v1[3]), float(v1[4]), float(v1[5])
    v2_open, v2_close, v2_vol = float(v2[3]), float(v2[4]), float(v2[5])
    v3_open, v3_close, v3_vol = float(v3[3]), float(v3[4]), float(v3[5])

    if v1_open <= 0 or v2_open <= 0 or v3_open <= 0:
        return None

    # 1. Vela 1 tem de ser VERMELHA e cair pelo menos QUEDA_MINIMA_VELA1 %
    queda_v1 = ((v1_open - v1_close) / v1_open) * 100
    if v1_close >= v1_open or queda_v1 < QUEDA_MINIMA_VELA1:
        return None

    corpo_v1 = abs(v1_open - v1_close)
    corpo_v2 = abs(v2_open - v2_close)

    # 2. Vela 2 tem de ser PEQUENA (no máximo TAMANHO_MAX_ESTRELA do corpo da Vela 1)
    if corpo_v2 > (corpo_v1 * TAMANHO_MAX_ESTRELA):
        return None

    # 3. Vela 3 tem de ser VERDE e fechar acima da METADE do corpo da Vela 1
    meio_v1 = v1_close + (corpo_v1 * 0.50)
    if v3_close <= v3_open or v3_close < meio_v1:
        return None

    # --- AVALIAÇÃO DE QUALIDADE (0 a 4 pontos) ---
    pontos = 0
    detalhes = []

    # Critério 1: Tendência Prévia (abaixo da média das últimas 20 velas)
    fechos_anteriores = [float(v[4]) for v in velas[4:24]]
    media_20 = sum(fechos_anteriores) / len(fechos_anteriores)
    if v1_close < media_20:
        pontos += 1
        detalhes.append("✅ Após queda (abaixo média 20v)")
    else:
        detalhes.append("⚠️ Mercado lateral/topo")

    # Critério 2: Força da Vela 3 (Fechou acima de 70% da Vela 1?)
    setenta_v1 = v1_close + (corpo_v1 * 0.70)
    if v3_close >= setenta_v1:
        pontos += 1
        detalhes.append("✅ Recuperação muito forte (>70%)")
    else:
        detalhes.append("➖ Recuperação moderada (>50%)")

    # Critério 3: Volume (Vela 3 tem mais volume que a Vela 2?)
    if v3_vol > v2_vol:
        pontos += 1
        detalhes.append("✅ Volume comprador a subir")
    else:
        detalhes.append("⚠️ Volume fraco na 3.ª vela")

    # Critério 4: Contexto do Bitcoin
    if btc_saudavel:
        pontos += 1
        detalhes.append(f"✅ BTC estável ({variacao_btc:+.2f}%)")
    else:
        detalhes.append(f"🚨 ATENÇÃO: BTC em queda ({variacao_btc:+.2f}%)")

    if pontos == 4:
        etiqueta = "🟢 ALTA PROBABILIDADE (4/4)"
    elif pontos == 3:
        etiqueta = "🟡 MÉDIA PROBABILIDADE (3/4)"
    else:
        etiqueta = f"⚪ BAIXA PROBABILIDADE ({pontos}/4)"

    if MODO_ESTRITO and pontos < 4:
        return None

    subida_v3 = ((v3_close - v3_open) / v3_open) * 100
    texto_alerta = (
        f"{etiqueta}\n"
        f"🪙 Moeda: {moeda} (15m)\n"
        f"📉 Queda V1: -{queda_v1:.2f}% | 📈 Subida V3: +{subida_v3:.2f}%\n"
        + "\n".join(detalhes)
    )
    return texto_alerta

def aguardar_proximo_fecho_15m():
    """Calcula quantos segundos faltam para o próximo minuto :00, :15, :30 ou :45 (+5 seg margem)."""
    agora = datetime.now(FUSO_PT)
    minutos_atuais = agora.minute
    segundos_atuais = agora.second

    minutos_para_proximo = 15 - (minutos_atuais % 15)
    segundos_espera = (minutos_para_proximo * 60) - segundos_atuais + 5
    if segundos_espera <= 5:
        segundos_espera += 900
    return segundos_espera

def loop_radar():
    global ultimo_dia_relatorio
    modo_str = "ESTRITO (Só 4/4)" if MODO_ESTRITO else "COMPLETO (Todos com Nota)"
    enviar_telegram(
        f"🚀 Radar 15m (Estrela da Manhã) Iniciado!\n"
        f"Moedas Revolut X: {len(PERMITIDAS_LISTA)}\n"
        f"Modo: {modo_str} | Queda Mín. V1: {QUEDA_MINIMA_VELA1}%"
    )

    while True:
        espera = aguardar_proximo_fecho_15m()
        time.sleep(espera)

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

        btc_saudavel, variacao_btc = analisar_contexto_btc()
        time.sleep(0.15)

        for moeda in PERMITIDAS_LISTA:
            velas = obter_velas_15m(moeda)
            if velas:
                alerta = analisar_estrela_manha(moeda, velas, btc_saudavel, variacao_btc)
                if alerta:
                    enviar_telegram(alerta)

            time.sleep(0.15)

if __name__ == "__main__":
    threading.Thread(target=loop_radar, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
