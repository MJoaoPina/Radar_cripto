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

# Guarda uma fila de até 5 preços para cada moeda
historico_precos = {}
moedas_revolut = set()
ultima_atualizacao_revolut = 0

@app.route('/')
def home():
    return f"Radar Revolut X Ativo! A monitorizar {len(moedas_revolut)} moedas USD."

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

def atualizar_lista_revolut():
    """Obtém dinamicamente todas as moedas transacionáveis contra USD na Revolut X"""
    global moedas_revolut, ultima_atualizacao_revolut
    url = "https://revolut.com"
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            dados = resposta.json()
            lista_tickers = dados.get("data", dados) if isinstance(dados, dict) else dados
            novas_moedas = set()
            
            if isinstance(lista_tickers, list):
                for item in lista_tickers:
                    simbolo = item.get("symbol", "") or item.get("pair", "")
                    if simbolo.endswith("/USD") or simbolo.endswith("-USD"):
                        base = simbolo.replace("/USD", "").replace("-USD", "")
                        novas_moedas.add(base)
                        
            if novas_moedas:
                moedas_revolut = novas_moedas
                ultima_atualizacao_revolut = time.time()
                return True
    except Exception:
        pass
    return False

def obter_precos_coinbase():
    """Lê os preços atuais em USD na Coinbase"""
    url = "https://coinbase.com"
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            dados = resposta.json()
            taxas = dados.get("data", {}).get("rates", {})
            precos = {}
            for moeda, taxa in taxas.items():
                # Filtra apenas pelas moedas que existem na Revolut X
                if moedas_revolut and moeda not in moedas_revolut:
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
    # Atualiza a lista de moedas da Revolut X logo ao arrancar
    sucesso = atualizar_lista_revolut()
    total = len(moedas_revolut)
    
    if sucesso:
        enviar_telegram(f"🚀 Radar Revolut X Iniciado!\nMoedas USD encontradas na Revolut: {total}\nJanela: {JANELA_MINUTOS} min | Gatilho: +{PERCENTUAL_ALERTA}%")
    else:
        enviar_telegram("⚠️ Radar Iniciado (Aviso: Não foi possível ler a lista da Revolut X, a usar todas as criptos da Coinbase).")

    while True:
        inicio_ciclo = time.time()

        # Atualiza a lista da Revolut X uma vez a cada 24 horas (86400 segundos)
        if time.time() - ultima_atualizacao_revolut > 86400:
            atualizar_lista_revolut()

        precos_atuais = obter_precos_coinbase()

        if precos_atuais:
            alertas_do_minuto = []

            for moeda, preco_atual in precos_atuais.items():
                if moeda not in historico_precos:
                    # Cria a fila que apaga automaticamente o 6º item mais antigo
                    historico_precos[moeda] = deque(maxlen=JANELA_MINUTOS)

                fila_precos = historico_precos[moeda]

                if len(fila_precos) > 0:
                    # Compara o preço atual com o menor preço dentro das últimas 5 velas
                    # Isto apanha subidas acumuladas em 1, 2, 3, 4 ou 5 minutos!
                    menor_preco_janela = min(fila_precos)
                    
                    if menor_preco_janela > 0:
                        variacao = ((preco_atual - menor_preco_janela) / menor_preco_janela) * 100

                        if variacao >= PERCENTUAL_ALERTA:
                            alertas_do_minuto.append(f"🟢 {moeda}: +{variacao:.2f}% (${preco_atual:.4f})")
                            # Limpa a fila desta moeda após o alerta para não repetir a mesma subida no minuto seguinte
                            fila_precos.clear()

                # Adiciona o preço atual à fila (se já tiver 5, o mais antigo sai sozinho)
                fila_precos.append(preco_atual)

            if alertas_do_minuto:
                mensagem_final = f"⚠️ Subidas Revolut X (Janela {JANELA_MINUTOS}m):\n\n" + "\n".join(alertas_do_minuto[:35])
                enviar_telegram(mensagem_final)

        tempo_decorrido = time.time() - inicio_ciclo
        tempo_espera = max(1, INTERVALO_LEITURA - tempo_decorrido)
        time.sleep(tempo_espera)

if __name__ == "__main__":
    threading.Thread(target=loop_radar, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
