import time
import threading
import requests
from collections import deque
from flask import Flask

# ==========================================
# CONFIGURAÇÕES DO RADAR (ALTERAR AQUI)
# ==========================================
TELEGRAM_TOKEN = "9185644092:AAGBuvJwqs3XnFQ2r8I1nN70kZYQkTOaZqg"
CHAT_ID = 9290388900 # Coloca o teu número de Chat ID sem aspas

PERCENTUAL_ALERTA = 0.05  # Subida acumulada mínima (%) para disparar alerta
JANELA_MINUTOS = 5       # Número máximo de velas de 1 minuto (Ex: 5 minutos)
INTERVALO_LEITURA = 60   # 60 segundos = 1 minuto
# ==========================================

app = Flask(__name__)

historico_precos = {}
criptos_validas = set()
ultima_atualizacao_lista = 0

@app.route('/')
def home():
    return f"Radar Ativo! A monitorizar {len(criptos_validas)} criptomoedas USD."

def enviar_telegram(x):
    host_tg = ".".join(["api", "telegram", "org"])
    url_final = f"https://{host_tg}/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": x
    }
    try:
        requests.post(url_final, json=payload, timeout=10)
    except Exception:
        pass

def formatar_preco(valor):
    """Formata o preço com as casas decimais adequadas para não mostrar $0.0000"""
    if valor >= 100:
        return f"${valor:.2f}"
    elif valor >= 1:
        return f"${valor:.4f}"
    elif valor >= 0.01:
        return f"${valor:.5f}"
    else:
        return f"${valor:.8f}"

def atualizar_lista_criptos():
    """Obtém dinamicamente todos os pares de criptomoedas ativos contra USD na Kraken"""
    global criptos_validas, ultima_atualizacao_lista
    host_kraken = ".".join(["api", "kraken", "com"])
    url = f"https://{host_kraken}/0/public/AssetPairs"
    
    # Ignora moedas tradicionais (Forex) caso apareçam em pares USD
    fiat_ignorar = {"EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "USD", "USDT", "USDC", "DAI", "PYUSD"}
    
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            dados = resposta.json()
            if not dados.get("error"):
                pares = dados.get("result", {})
                novas_criptos = set()
                for info in pares.values():
                    wsname = info.get("wsname", "")  # Formato padrão ex: "BTC/USD", "SOL/USD"
                    if wsname.endswith("/USD"):
                        base = wsname.split("/")[0].upper()
                        # Normaliza o símbolo antigo XBT da Kraken para BTC
                        if base == "XBT":
                            base = "BTC"
                        if base not in fiat_ignorar:
                            novas_criptos.add(base)
                            
                if novas_criptos:
                    criptos_validas = novas_criptos
                    ultima_atualizacao_lista = time.time()
                    return True, ""
        return False, f"HTTP {resposta.status_code}"
    except Exception as e:
        return False, str(type(e).__name__)

def obter_precos_usd():
    """Lê os preços atuais em USD na Coinbase e filtra pelas criptomoedas ativas"""
    host_cb = ".".join(["api", "coinbase", "com"])
    url = f"https://{host_cb}/v2/exchange-rates?currency=USD"
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            dados = resposta.json()
            taxas = dados.get("data", {}).get("rates", {})
            precos = {}
            for moeda, taxa in taxas.items():
                if criptos_validas and moeda not in criptos_validas:
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
    sucesso, erro = atualizar_lista_criptos()
    total = len(criptos_validas)

    if sucesso:
        enviar_telegram(
            f"🚀 Radar Revolut X / Cripto USD Iniciado!\n"
            f"Criptomoedas USD ativas: {total}\n"
            f"Janela: {JANELA_MINUTOS} min | Gatilho: +{PERCENTUAL_ALERTA}%"
        )
    else:
        enviar_telegram(f"⚠️ Radar Iniciado em modo geral ({erro}).")

    while True:
        inicio_ciclo = time.time()

        # Atualiza a lista de criptomoedas uma vez a cada 24 horas
        if time.time() - ultima_atualizacao_lista > 86400:
            atualizar_lista_criptos()

        precos_atuais = obter_precos_usd()

        if precos_atuais:
            alertas_do_minuto = []

            for moeda, preco_atual in precos_atuais.items():
                if moeda not in historico_precos:
                    historico_precos[moeda] = deque(maxlen=JANELA_MINUTOS)

                fila_precos = historico_precos[moeda]

                if len(fila_precos) > 0:
                    menor_preco_janela = min(fila_precos)

                    if menor_preco_janela > 0:
                        variacao = ((preco_atual - menor_preco_janela) / menor_preco_janela) * 100

                        if variacao >= PERCENTUAL_ALERTA:
                            preco_txt = formatar_preco(preco_atual)
                            alertas_do_minuto.append(f"🟢 {moeda}: +{variacao:.2f}% ({preco_txt})")
                            # Limpa o histórico anterior e o preco_atual entra logo abaixo como nova base
                            fila_precos.clear()

                fila_precos.append(preco_atual)

            if alertas_do_minuto:
                mensagem_final = f"⚠️ Subidas Rápidas USD (Janela {JANELA_MINUTOS}m):\n\n" + "\n".join(alertas_do_minuto[:35])
                enviar_telegram(mensagem_final)

        tempo_decorrido = time.time() - inicio_ciclo
        tempo_espera = max(1, INTERVALO_LEITURA - tempo_decorrido)
        time.sleep(tempo_espera)

if __name__ == "__main__":
    threading.Thread(target=loop_radar, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
