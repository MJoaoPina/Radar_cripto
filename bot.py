import time
import threading
import requests
from collections import deque
from flask import Flask

# ==========================================
# CONFIGURAÇÕES DO RADAR (ALTERAR AQUI)
# ==========================================
TELEGRAM_TOKEN = "9185644092:AAGBuvJwqs3XnFQ2r8I1nN70kZYQkTOaZqg"
CHAT_ID = 9290388900   # Coloca o teu número de Chat ID sem aspas

PERCENTUAL_ALERTA = 3.0  # Subida acumulada mínima (%) para disparar alerta
JANELA_MINUTOS = 5       # Número máximo de velas de 1 minuto (Ex: 5 minutos)
INTERVALO_LEITURA = 60   # 60 segundos = 1 minuto
# ==========================================

app = Flask(__name__)

historico_precos = {}
moedas_revolut = set()
ultima_atualizacao_revolut = 0
ultimo_erro_revolut = ""

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

def atualizar_lista_revolut():
    """Obtém dinamicamente os pares USD da Revolut X via agregadores públicos sem bloqueio 403"""
    global moedas_revolut, ultima_atualizacao_revolut, ultimo_erro_revolut
    
    # Fonte 1: API Pública do CoinGecko para a exchange Revolut X
    try:
        novas_moedas = set()
        for pagina in range(1, 5):  # Lê até 400 pares ativos da Revolut X
            url_cg = f"https://coingecko.com{pagina}"
            resp = requests.get(url_cg, timeout=15)
            if resp.status_code == 200:
                tickers = resp.json().get("tickers", [])
                if not tickers:
                    break
                for t in tickers:
                    base = t.get("base", "").upper()
                    target = t.get("target", "").upper()
                    if target == "USD" and base:
                        novas_moedas.add(base)
            else:
                ultimo_erro_revolut = f"CG HTTP {resp.status_code}"
                break
                
        if novas_moedas:
            moedas_revolut = novas_moedas
            ultima_atualizacao_revolut = time.time()
            ultimo_erro_revolut = ""
            return True
    except Exception as e:
        ultimo_erro_revolut = str(type(e).__name__)

    # Fonte 2 (Alternativa): API Pública da CoinPaprika para a Revolut X
    try:
        url_cp = "https://coinpaprika.com"
        resp = requests.get(url_cp, timeout=15)
        if resp.status_code == 200:
            mercados = resp.json()
            novas_moedas = set()
            for m in mercados:
                par = m.get("pair", "").upper()
                if par.endswith("/USD"):
                    base = par.split("/")[0]
                    novas_moedas.add(base)
            if novas_moedas:
                moedas_revolut = novas_moedas
                ultima_atualizacao_revolut = time.time()
                ultimo_erro_revolut = ""
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
                # Filtra estritamente apenas pelas moedas listadas na Revolut X
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
        enviar_telegram(f"🚀 Radar Revolut X Iniciado!\nMoedas USD Revolut X carregadas: {total}\nJanela: {JANELA_MINUTOS} min | Gatilho: +{PERCENTUAL_ALERTA}%")
    else:
        enviar_telegram(f"⚠️ Radar Iniciado sem filtro Revolut ({ultimo_erro_revolut}). A usar todas as moedas da Coinbase.")

    while True:
        inicio_ciclo = time.time()

        # Atualiza o catálogo da Revolut X uma vez a cada 24 horas
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
