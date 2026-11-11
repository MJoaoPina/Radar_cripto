import time
import threading
import requests
from collections import deque
from flask import Flask

# ==========================================
# CONFIGURAÇÕES DO RADAR (ALTERAR AQUI)
# ==========================================
TELEGRAM_TOKEN = "9185644092:AAGBuvJwqs3XnFQ2r8I1nN70kZYQkTOaZqg"
CHAT_ID = 9290388900  # Coloca o teu número de Chat ID sem aspas

PERCENTUAL_ALERTA = 3.0  # Subida acumulada mínima (%) para disparar alerta
JANELA_MINUTOS = 5       # Número máximo de velas de 1 minuto (Ex: 5 minutos)
INTERVALO_LEITURA = 60   # 60 segundos = 1 minuto
# ==========================================

app = Flask(__name__)

historico_precos = {}
pares_usd_ativos = set()
ultima_atualizacao_pares = 0

@app.route('/')
def home():
    return f"Radar Ativo! A monitorizar {len(pares_usd_ativos)} criptomoedas USD."

def enviar_telegram(x):
    base_url = "https://" + "api.telegram.org"
    url_final = base_url + f"/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": x
    }
    try:
        requests.post(url_final, json=payload, timeout=10)
    except Exception:
        pass

def atualizar_pares_usd():
    """Obtém dinamicamente todos os pares de criptomoedas ativos contra USD"""
    global pares_usd_ativos, ultima_atualizacao_pares
    url = "https://coinbase.com"
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            produtos = resposta.json()
            novos_pares = set()
            for item in produtos:
                if (
                    item.get("quote_currency") == "USD"
                    and item.get("status") == "online"
                    and not item.get("trading_disabled", False)
                ):
                    base = item.get("base_currency", "").upper()
                    if base:
                        novos_pares.add(base)
            if novos_pares:
                pares_usd_ativos = novos_pares
                ultima_atualizacao_pares = time.time()
                return True
    except Exception:
        pass
    return False

def obter_precos_usd():
    """Lê os preços atuais ao milissegundo e filtra pelos pares USD ativos"""
    url = "https://coinbase.com"
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            dados = resposta.json()
            taxas = dados.get("data", {}).get("rates", {})
            precos = {}
            for moeda, taxa in taxas.items():
                if pares_usd_ativos and moeda not in pares_usd_ativos:
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
    sucesso = atualizar_pares_usd()
    total = len(pares_usd_ativos)

    if sucesso:
        enviar_telegram(
            f"🚀 Radar Revolut X / USD Iniciado!\n"
            f"Criptomoedas USD ativas: {total}\n"
            f"Janela: {JANELA_MINUTOS} min | Gatilho: +{PERCENTUAL_ALERTA}%"
        )
    else:
        enviar_telegram("⚠️ Radar Iniciado (Modo de reserva: leitura geral USD).")

    while True:
        inicio_ciclo = time.time()

        # Atualiza a lista de pares ativos uma vez a cada 24 horas
        if time.time() - ultima_atualizacao_pares > 86400:
            atualizar_pares_usd()

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
                            alertas_do_minuto.append(f"🟢 {moeda}: +{variacao:.2f}% (${preco_atual:.4f})")
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
