import time
import threading
import requests
from flask import Flask

# ==========================================
# CONFIGURAÇÕES DO RADAR (ALTERAR AQUI)
# ==========================================
TELEGRAM_TOKEN = "9185644092:AAGBuvJwqs3XnFQ2r8I1nN70kZYQkTOaZqg"
CHAT_ID = 9290388900  # Coloca o teu número de Chat ID sem aspas

PERCENTUAL_ALERTA = 3.0  # Subida mínima (%) para disparar alerta
INTERVALO_LEITURA = 60   # Tempo entre leituras (60 segundos = 1 minuto)
# ==========================================

app = Flask(__name__)
historico_precos = {}

@app.route('/')
def home():
    return "Radar Revolut X Ativo e a Monitorizar!"

def enviar_telegram(x):
    base_url = "https://" + "api.telegram.org"
    url_final = base_url + f"/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": x,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url_final, json=payload, timeout=10)
    except Exception:
        pass

def obter_precos_coinbase():
    url = "https://coinbase.com"
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            dados = resposta.json()
            taxas = dados.get("data", {}).get("rates", {})
            precos = {}
            for moeda, taxa in taxas.items():
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
    enviar_telegram("🚀 *Radar Revolut X/Coinbase Iniciado no Render!*")
    while True:
        inicio_ciclo = time.time()
        precos_atuais = obter_precos_coinbase()

        if precos_atuais:
            alertas_do_minuto = []
            for moeda, preco_atual in precos_atuais.items():
                if moeda in historico_precos:
                    preco_anterior = historico_precos[moeda]
                    if preco_anterior > 0:
                        variacao = ((preco_atual - preco_anterior) / preco_anterior) * 100
                        if variacao >= PERCENTUAL_ALERTA:
                            alertas_do_minuto.append(f"🟢 *{moeda}*: +{variacao:.2f}% (Agora: ${preco_atual:.4f})")
                historico_precos[moeda] = preco_atual

            if alertas_do_minuto:
                mensagem_final = "⚠️ *Movimentação Rápida de Mercado:*\n\n" + "\n".join(alertas_do_minuto)
                enviar_telegram(mensagem_final)

        tempo_decorrido = time.time() - inicio_ciclo
        tempo_espera = max(1, INTERVALO_LEITURA - tempo_decorrido)
        time.sleep(tempo_espera)

if __name__ == "__main__":
    # Inicia o radar em segundo plano
    threading.Thread(target=loop_radar, daemon=True).start()
    # Inicia o servidor web para o Render e o UptimeRobot manterem o bot acordado
    app.run(host="0.0.0.0", port=10000)
