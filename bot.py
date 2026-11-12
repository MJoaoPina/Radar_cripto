import time
import threading
import urllib.parse
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

PERCENTUAL_ALERTA = 3.0       # Subida acumulada mínima (%) para disparar alerta
JANELA_MINUTOS = 5            # Janela deslizante máxima em minutos (Ex: 5 velas)
INTERVALO_LEITURA = 60        # Tempo entre leituras em segundos (60 = 1 minuto)

SILENCIO_NOTURNO = False      # Muda para True para ativar o silêncio noturno
SILENCIO_INICIO = "01:00"     # Hora de início do silêncio (formato HH:MM)
SILENCIO_FIM = "07:30"        # Hora de fim do silêncio (formato HH:MM)

RELATORIO_DIARIO = True       # Muda para False se não quiseres o resumo diário
HORA_RELATORIO = "09:00"      # Hora de envio da confirmação diária (formato HH:MM)
# ==============================================================================

app = Flask(__name__)
FUSO_PT = ZoneInfo("Europe/Lisbon")

historico_precos = {}
moedas_ativas = set()
fonte_atual = "Nenhuma"
ultima_atualizacao_lista = 0
ultimo_dia_relatorio = ""

@app.route('/')
def home():
    return f"Radar Ativo | Fonte: {fonte_atual} | Moedas USD: {len(moedas_ativas)}"

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

def extrair_pares_usd_revolut(dados):
    encontradas = set()
    if isinstance(dados, dict):
        for chave, valor in dados.items():
            if isinstance(chave, str) and (chave.endswith("/USD") or chave.endswith("-USD")):
                encontradas.add(chave.replace("/USD", "").replace("-USD", "").upper())
            elif isinstance(valor, (list, dict)):
                encontradas.update(extrair_pares_usd_revolut(valor))
    elif isinstance(dados, list):
        for item in dados:
            if isinstance(item, str) and (item.endswith("/USD") or item.endswith("-USD")):
                encontradas.add(item.replace("/USD", "").replace("-USD", "").upper())
            elif isinstance(item, dict):
                for campo in ("symbol", "pair", "instrument", "name", "id"):
                    val = item.get(campo, "")
                    if isinstance(val, str) and (val.endswith("/USD") or val.endswith("-USD")):
                        encontradas.add(val.replace("/USD", "").replace("-USD", "").upper())
    return encontradas

def obter_lista_revolut_via_proxy():
    host_rev = ".".join(["revx", "revolut", "com"])
    alvos = [
        f"https://{host_rev}/api/1.0/public/pairs",
        f"https://{host_rev}/api/1.0/public/tickers"
    ]
    proxies = [
        lambda u: "https://" + ".".join(["api", "allorigins", "win"]) + "/raw?url=" + urllib.parse.quote(u, safe=""),
        lambda u: "https://" + ".".join(["corsproxy", "io"]) + "/?" + urllib.parse.quote(u, safe="")
    ]
    for alvo in alvos:
        for construir_proxy in proxies:
            try:
                resp = requests.get(construir_proxy(alvo), timeout=15)
                if resp.status_code == 200:
                    moedas = extrair_pares_usd_revolut(resp.json())
                    if len(moedas) > 10:
                        return moedas
            except Exception:
                continue
    return None

def obter_lista_kraken():
    host_kraken = ".".join(["api", "kraken", "com"])
    url = f"https://{host_kraken}/0/public/AssetPairs"
    fiat_ignorar = {"EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "USD", "USDT", "USDC", "DAI", "PYUSD"}
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            dados = resposta.json()
            if not dados.get("error"):
                pares = dados.get("result", {})
                novas_criptos = set()
                for info in pares.values():
                    wsname = info.get("wsname", "")
                    if wsname.endswith("/USD"):
                        base = wsname.split("/").upper()
                        if base == "XBT":
                            base = "BTC"
                        if base not in fiat_ignorar:
                            novas_criptos.add(base)
                if novas_criptos:
                    return novas_criptos
    except Exception:
        pass
    return None

def gerir_atualizacao_catalogo(eh_arranque=False):
    global moedas_ativas, fonte_atual, ultima_atualizacao_lista
    novas_revolut = obter_lista_revolut_via_proxy()

    if eh_arranque:
        if novas_revolut:
            moedas_ativas = novas_revolut
            fonte_atual = "Revolut X"
            ultima_atualizacao_lista = time.time()
            enviar_telegram(
                f"🚀 Radar Iniciado (Lista Oficial Revolut X)!\n"
                f"Moedas USD ativas: {len(moedas_ativas)}\n"
                f"Janela: {JANELA_MINUTOS} min | Gatilho: +{PERCENTUAL_ALERTA}%"
            )
        else:
            lista_backup = obter_lista_kraken()
            if lista_backup:
                moedas_ativas = lista_backup
                fonte_atual = "Kraken (Plano B)"
                ultima_atualizacao_lista = time.time()
                enviar_telegram(
                    f"⚠️ Falha ao ler Revolut X no arranque. A usar lista Kraken ({len(moedas_ativas)} moedas) temporariamente.\n"
                    f"Janela: {JANELA_MINUTOS} min | Gatilho: +{PERCENTUAL_ALERTA}%"
                )
            else:
                fonte_atual = "Coinbase Geral"
                enviar_telegram("⚠️ Radar Iniciado em modo geral (falha nas listas externas).")
    else:
        if novas_revolut:
            if fonte_atual == "Revolut X" and moedas_ativas:
                recem_listadas = sorted(list(novas_revolut - moedas_ativas))
                if recem_listadas:
                    enviar_telegram(f"🆕 Nova(s) moeda(s) listada(s) na Revolut X: {', '.join(recem_listadas)}/USD")
            moedas_ativas = novas_revolut
            fonte_atual = "Revolut X"
            ultima_atualizacao_lista = time.time()
        else:
            ultima_atualizacao_lista = time.time()
            enviar_telegram(
                f"⚠️ Aviso: A atualização diária da lista Revolut X falhou hoje.\n"
                f"O bot continua a trabalhar normalmente com a lista anterior ({fonte_atual}: {len(moedas_ativas)} moedas)."
            )

def obter_precos_usd():
    host_cb = ".".join(["api", "coinbase", "com"])
    url = f"https://{host_cb}/v2/exchange-rates?currency=USD"
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            taxas = resposta.json().get("data", {}).get("rates", {})
            precos = {}
            for moeda, taxa in taxas.items():
                if moedas_ativas and moeda not in moedas_ativas:
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
    gerir_atualizacao_catalogo(eh_arranque=True)

    while True:
        inicio_ciclo = time.time()
        agora_pt = datetime.now(FUSO_PT)

        if RELATORIO_DIARIO:
            hoje_str = agora_pt.strftime("%Y-%m-%d")
            hora_atual_str = agora_pt.strftime("%H:%M")
            if hoje_str != ultimo_dia_relatorio and hora_atual_str == HORA_RELATORIO:
                ultimo_dia_relatorio = hoje_str
                enviar_telegram(f"✅ Radar Ativo | Fonte: {fonte_atual} ({len(moedas_ativas)} moedas USD)")

        if time.time() - ultima_atualizacao_lista > 86400:
            gerir_atualizacao_catalogo(eh_arranque=False)

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
                mensagem_final = f"⚠️ Subidas Rápidas ({fonte_atual} | Janela {JANELA_MINUTOS}m):\n\n" + "\n".join(alertas_do_minuto[:35])
                enviar_telegram(mensagem_final)

        tempo_decorrido = time.time() - inicio_ciclo
        tempo_espera = max(1, INTERVALO_LEITURA - tempo_decorrido)
        time.sleep(tempo_espera)

if __name__ == "__main__":
    threading.Thread(target=loop_radar, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
