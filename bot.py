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
moedas_revolut = set()
ultima_atualizacao_revolut = 0
ultimo_erro_revolut = ""

HEADERS_NAVEGADOR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

@app.route('/')
def home():
    return f"Radar Revolut X Ativo! Moedas USD: {len(moedas_revolut)} | Status: {ultimo_erro_revolut or 'OK'}"

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

def extrair_moedas_usd(dados):
    """Procura pares USD em qualquer formato de resposta JSON da Revolut X"""
    encontradas = set()
    
    if isinstance(dados, dict):
        # Caso os símbolos venham como chaves do dicionário (ex: {"BTC/USD": {...}})
        for chave, valor in dados.items():
            if isinstance(chave, str) and (chave.endswith("/USD") or chave.endswith("-USD")):
                encontradas.add(chave.replace("/USD", "").replace("-USD", ""))
            elif isinstance(valor, (list, dict)):
                encontradas.update(extrair_moedas_usd(valor))
                
    elif isinstance(dados, list):
        for item in dados:
            if isinstance(item, str) and (item.endswith("/USD") or item.endswith("-USD")):
                encontradas.add(item.replace("/USD", "").replace("-USD", ""))
            elif isinstance(item, dict):
                for campo in ("symbol", "pair", "instrument", "name", "id"):
                    val = item.get(campo, "")
                    if isinstance(val, str) and (val.endswith("/USD") or val.endswith("-USD")):
                        encontradas.add(val.replace("/USD", "").replace("-USD", ""))
    return encontradas

def atualizar_lista_revolut():
    """Tenta obter os pares USD nos endpoints públicos oficiais da Revolut X"""
    global moedas_revolut, ultima_atualizacao_revolut, ultimo_erro_revolut
    
    endpoints = [
        "https://revolut.com",
        "https://revolut.com"
    ]
    
    for url in endpoints:
        try:
            resposta = requests.get(url, headers=HEADERS_NAVEGADOR, timeout=15)
            if resposta.status_code == 200:
                dados = resposta.json()
                novas_moedas = extrair_moedas_usd(dados)
                if novas_moedas:
                    moedas_revolut = novas_moedas
                    ultima_atualizacao_revolut = time.time()
                    ultimo_erro_revolut = ""
                    return True
                else:
                    ultimo_erro_revolut = "Resposta 200 mas 0 pares USD encontrados"
            else:
                ultimo_erro_revolut = f"HTTP {resposta.status_code}"
        except Exception as e:
            ultimo_erro_revolut = str(type(e).__name__)
            
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
    sucesso = atualizar_lista_revolut()
    total = len(moedas_revolut)
    
    if sucesso:
        enviar_telegram(f"🚀 Radar Revolut X Iniciado!\nMoedas USD Revolut X: {total}\nJanela: {JANELA_MINUTOS} min | Gatilho: +{PERCENTUAL_ALERTA}%")
    else:
        enviar_telegram(f"⚠️ Radar Iniciado sem filtro Revolut ({ultimo_erro_revolut}). A usar todas as moedas da Coinbase.")

    while True:
        inicio_ciclo = time.time()

        # Atualiza a lista da Revolut X uma vez a cada 24 horas
        if time.time() - ultima_atualizacao_revolut > 86400:
            atualizar_lista_revolut()

        precos_atuais = obter_precos_coinbase()

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
                mensagem_final = f"⚠️ Subidas Revolut X (Janela {JANELA_MINUTOS}m):\n\n" + "\n".join(alertas_do_minuto[:35])
                enviar_telegram(mensagem_final)

        tempo_decorrido = time.time() - inicio_ciclo
        tempo_espera = max(1, INTERVALO_LEITURA - tempo_decorrido)
        time.sleep(tempo_espera)

if __name__ == "__main__":
    threading.Thread(target=loop_radar, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
