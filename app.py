import sys, os
if sys.stdout is None: sys.stdout = open(os.devnull, 'w')
if sys.stderr is None: sys.stderr = open(os.devnull, 'w')
# =============================================================================
# CR AGROSTAT BRASIL v9.0 — PARTE 1 DE 3
# Fontes (Chicago SRW + StoneX), Motor de Voz IA (Masc/Fem), Card Stories e Mapas
# =============================================================================
import base64
import csv
from datetime import datetime, timedelta
import hashlib
import json
import math
import os
import socket
import struct
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
import io
import re
import secrets
import time
import threading
from functools import lru_cache
from html import escape as html_escape
from pathlib import Path
import flet as ft
import requests
import yfinance as yf

# Diretório persistente configurável em ambientes com volume de armazenamento.
# Atenção: o disco efêmero de uma hospedagem gratuita NÃO preserva dados após reinícios.
DIRETORIO_DADOS = os.environ.get("CR_AGROSTAT_DATA_DIR", "dados")
ARQUIVO_DB = os.path.join(DIRETORIO_DADOS, "cr_agrostat_brasil_v9.json")
ARQUIVO_USUARIOS = os.path.join(DIRETORIO_DADOS, "cr_usuarios_crm_v9.json")
PASTA_RELATORIOS = "relatorios"
PASTA_ASSETS = "assets"
PASTA_UPLOADS = os.path.join(DIRETORIO_DADOS, "uploads_temporarios")
MAPA_IBGE_CACHE = os.path.join(DIRETORIO_DADOS, "malha_uf_ibge_cache.geojson")
APP_VERSAO = "10.1"
SALT_SEGURANCA = "CRAgroStat_SaoBorja_RS_2026_Salt"

# =============================================================================
# FONTES CLICÁVEIS DE ANÁLISE (PADRÃO CHICAGO SRW + STONEX + PORTAIS NACIONAIS)
# =============================================================================
FONTES_DISPONIVEIS = {
    "Chicago SRW Wheat / CBOT": {
        "nome": "Chicago SRW Wheat Futures (CBOT: ZWW00 / CME Group)",
        "sigla_btn": "🏛️ Chicago SRW (Padrão)",
        "fator_ajuste": 1.000,
        "url": "https://www.google.com/finance/quote/ZWW00:CBOT",
        "resumo_analise": "Bolsa de Chicago opera com foco no ritmo de embarques globais, dólar index e paridade de exportação nos portos sul-americanos.",
    },
    "StoneX Inteligência Agro": {
        "nome": "StoneX Brasil — Inteligência de Mercado, Safra & Paridades",
        "sigla_btn": "💎 StoneX Agro",
        "fator_ajuste": 1.003,
        "url": "https://www.stonex.com/pt-br/inteligencia-de-mercado/",
        "resumo_analise": "StoneX aponta acompanhamento rigoroso da comercialização da safra brasileira, prêmios portuários em Rio Grande/Paranaguá e custos logísticos.",
    },
    "Emater / IRGA - RS": {
        "nome": "Emater/RS-Ascar & Indicador IRGA (Mercado Físico Regional)",
        "sigla_btn": "🟢 Emater / IRGA-RS",
        "fator_ajuste": 0.997,
        "url": "https://www.emater.tche.br/site/servicos/informacoes-agropecuarias.php",
        "resumo_analise": "Levantamento físico nas cooperativas e cerealistas gaúchas mostra trigo na faixa de R$ 73,00/sc e arroz com liquidez firme na Fronteira Oeste.",
    },
    "CEPEA / Esalq - USP": {
        "nome": "Indicadores CEPEA / Esalq - USP (Físico & Portos)",
        "sigla_btn": "📊 CEPEA / Esalq",
        "fator_ajuste": 1.009,
        "url": "https://www.cepea.esalq.usp.br/br",
        "resumo_analise": "Indicadores físicos CEPEA refletem disputa entre indústria doméstica (moinhos e esmagadoras) e paridade de exportação.",
    },
    "Notícias Agrícolas": {
        "nome": "Portal Notícias Agrícolas (Balcão Cooperativas & Bolsas)",
        "sigla_btn": "📰 Notícias Agrícolas",
        "fator_ajuste": 0.995,
        "url": "https://www.noticiasagricolas.com.br/cotacoes/",
        "resumo_analise": "Cotações de balcão reportadas pelos sindicatos rurais e corretoras mostram oscilação diária guiada pelo câmbio comercial.",
    },
    "Agrolink / Deral-PR / IMEA-MT": {
        "nome": "Agrolink + Deral (PR) + Epagri (SC) + IMEA (MT)",
        "sigla_btn": "🌾 Agrolink / Deral / IMEA",
        "fator_ajuste": 1.002,
        "url": "https://www.agrolink.com.br/cotacoes/",
        "resumo_analise": "Painel multiestadual destaca diferencial de frete entre o interior produtor e as praças consumidoras de proteína animal.",
    },
    "B3 — Bolsa do Brasil": {
        "nome": "B3 Brasil — Contratos Futuros Agropecuários em R$",
        "sigla_btn": "🇧🇷 B3 Brasil",
        "fator_ajuste": 1.006,
        "url": "https://www.b3.com.br/",
        "resumo_analise": "Curva futura na B3 precifica a relação de troca para a próxima janela de plantio e o custo financeiro de armazenagem.",
    },
}


def agora_str():
  return datetime.now().strftime("%d/%m/%Y às %H:%M:%S")


def criptografar_senha(senha_limpa):
  """Mantém verificação de senhas v9; novas senhas usam PBKDF2 e sal aleatório."""
  texto = f"{SALT_SEGURANCA}:{senha_limpa.strip()}"
  return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def criar_hash_senha_segura(senha):
  sal = secrets.token_bytes(18)
  derivado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, 310_000)
  return "pbkdf2_sha256$310000$%s$%s" % (sal.hex(), derivado.hex())


def verificar_senha(senha, hash_armazenado):
  if str(hash_armazenado).startswith("pbkdf2_sha256$"):
    try:
      _, iteracoes, sal, valor = hash_armazenado.split("$")
      teste = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), int(iteracoes))
      return secrets.compare_digest(teste, bytes.fromhex(valor))
    except (ValueError, TypeError):
      return False
  return secrets.compare_digest(criptografar_senha(senha), str(hash_armazenado))


def salvar_json_atomico(caminho, objeto):
  """Evita truncar o arquivo original em gravações interrompidas."""
  pasta = os.path.dirname(caminho) or "."
  os.makedirs(pasta, exist_ok=True)
  temporario = f"{caminho}.{secrets.token_hex(6)}.tmp"
  try:
    with open(temporario, "w", encoding="utf-8") as f:
      json.dump(objeto, f, ensure_ascii=False, indent=2)
      f.flush()
      os.fsync(f.fileno())
    os.replace(temporario, caminho)
  finally:
    if os.path.exists(temporario):
      os.remove(temporario)


def dinheiro_br(valor):
  try:
    return "R$ " + f"{float(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
  except (TypeError, ValueError):
    return "Indisponível"


def numero_usuario(valor, minimo=None, maximo=None):
  v = float(str(valor or "").strip().replace(".", "").replace(",", ".")) if "," in str(valor or "") else float(valor)
  if not math.isfinite(v) or (minimo is not None and v < minimo) or (maximo is not None and v > maximo):
    raise ValueError("Valor numérico fora do intervalo permitido")
  return v


def obter_ip_local():
  try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip
  except Exception:
    return "127.0.0.1"


# =============================================================================
# MOTOR DE VOZ (MASCULINA E FEMININA) E INTELIGÊNCIA ARTIFICIAL DO AGRONEGÓCIO
# =============================================================================
def falar_resposta_ia(texto_fala, genero_voz="Feminina"):
  """Aciona o sintetizador de voz nativo do sistema (Voz Masculina ou Feminina em Português)."""
  if os.name != "nt":
    return
  try:
    limpo = (
        texto_fala.replace("*", "")
        .replace("#", "")
        .replace("•", ",")
        .replace("➔", " para ")
        .replace('"', "")
        .replace("'", "")
        .replace("\n", ". ")
    )
    for emoji in ["🌾", "🌧️", "💰", "📊", "🚜", "💎", "🏛️", "🟢", "🔴", "🔵", "🟡", "🤖", "🗣️", "📍"]:
      limpo = limpo.replace(emoji, "")

    genero_sapi = "Female" if "Feminina" in genero_voz else "Male"
    # Tenta selecionar voz em Português (Maria = Feminina / Daniel = Masculina) com ajuste de timbre
    cmd_ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::{genero_sapi}); "
        "$synth.Rate = 1; "
        f"$synth.SpeakAsync('{limpo[:550]}'); "
        "Start-Sleep -Seconds 15"
    )
    subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", cmd_ps],
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
  except Exception:
    pass


def responder_ia_agronegocio(pergunta, dados, uf_sel, regiao_interna_sel, polo_clima_sel, fonte_ativa):
  """Cérebro da IA Especialista em Agronegócio — analisa cotações, StoneX, CBOT, Clima e Barter."""
  p_low = pergunta.lower()
  dolar = dados.get("dolar", 5.35)
  dolar_var = dados.get("dolar_var", 0.0)

  mapa_itens = {it["id"]: it for it in dados.get("itens", [])}
  trigo = mapa_itens.get("trigo_grao", dados["itens"][0])
  soja = mapa_itens.get("soja_grao", dados["itens"][1])
  arroz = mapa_itens.get("arroz_casca", dados["itens"][2])
  milho = mapa_itens.get("milho_grao", dados["itens"][3])

  info_fonte = FONTES_DISPONIVEIS.get(fonte_ativa, list(FONTES_DISPONIVEIS.values())[0])
  fator_f = info_fonte["fator_ajuste"]

  if "trigo" in p_low:
    val_t = round(trigo["preco_atual"] * fator_f, 2)
    return (
        f"🌾 Análise de Trigo Pão ({regiao_interna_sel}): O preço dinâmico atual está em R$ {val_t:.2f} por saca de 60kg "
        f"({trigo['var_dia']:+.2f}% hoje). Na bolsa Chicago SRW Wheat Futures (CBOT: ZWW00), o contrato opera a {trigo['ult_usx']:.2f} USX "
        f"(Abertura: {trigo['abertura_usx']:.2f}, Máxima: {trigo['alta_usx']:.2f}, Mínima: {trigo['baixa_usx']:.2f}). "
        f"No modelo de cenários do aplicativo (fonte de referência: {fonte_ativa}), os valores ilustrativos são R$ {trigo['prev_15d']:.2f} (15 dias) e R$ {trigo['prev_30d']:.2f} (30 dias). Não são projeções oficiais."
    )
  elif "soja" in p_low:
    val_s = round(soja["preco_atual"] * fator_f, 2)
    return (
        f"🌱 Análise de Soja ({regiao_interna_sel}): A saca de 60kg está cotada hoje a R$ {val_s:.2f} ({soja['var_dia']:+.2f}%), "
        f"com Chicago (ZS=F) em {soja['ult_usx']:.2f} USX e Dólar Comercial a R$ {dolar:.2f}. "
        f"É importante acompanhar prêmios de exportação e ritmo de vendas em fontes oficiais, como StoneX e CEPEA. "
        f"A estimativa para 30 dias é de R$ {soja['prev_30d']:.2f}/sc."
    )
  elif "arroz" in p_low:
    val_a = round(arroz["preco_atual"] * fator_f, 2)
    return (
        f"🌾 Análise de Arroz em Casca ({regiao_interna_sel}): Cotação atual em R$ {val_a:.2f} por saca de 50kg ({arroz['var_dia']:+.2f}%). "
        f"Para confirmar o preço da Fronteira Oeste (São Borja/Itaqui) e Zona Sul, consulte os indicadores IRGA/CEPEA e fontes comerciais. "
        f"Projeção IA para 30 dias: R$ {arroz['prev_30d']:.2f}."
    )
  elif "milho" in p_low:
    val_m = round(milho["preco_atual"] * fator_f, 2)
    return (
        f"🌽 Análise de Milho ({regiao_interna_sel}): Preço atual de R$ {val_m:.2f} por saca de 60kg ({milho['var_dia']:+.2f}%). "
        f"O consumo das agroindústrias de proteína animal no Sul e as usinas de etanol no Centro-Oeste sustentam as cotações regionais."
    )
  elif any(k in p_low for k in ["clima", "chuva", "tempo", "plantio", "pulveriza"]):
    return (
        f"🌧️ Orientação Agrometeorológica ({polo_clima_sel}): Confira os dados da aba Clima, que utiliza previsões meteorológicas quando a consulta está disponível. "
        f"Para pulverização e semeadura, aproveite as janelas sem precipitação acima de 5mm e ventos abaixo de 10 km/h. "
        f"Consulte a aba Clima para ver o comparativo completo das estações de 2023 a 2027."
    )
  elif any(k in p_low for k in ["stonex", "chicago", "bolsa", "dolar", "câmbio", "mercado"]):
    return (
        f"💎 Resumo StoneX & Chicago SRW ({agora_str()}): O Dólar Comercial opera a R$ {dolar:.2f} ({dolar_var:+.2f}%). "
        f"A fonte {fonte_ativa} é uma referência para consulta independente, não uma leitura automática da instituição. Os valores modelados para ({regiao_interna_sel}) são: "
        f"Soja a R$ {soja['preco_atual']:.2f}, Trigo a R$ {trigo['preco_atual']:.2f}, Arroz a R$ {arroz['preco_atual']:.2f} e Milho a R$ {milho['preco_atual']:.2f}."
    )
  elif any(k in p_low for k in ["semente", "azevem", "aveia", "hectare", "barter", "troca"]):
    return (
        f"🚜 Consultoria de Sementes e Barter: Com a Soja a R$ {soja['preco_atual']:.2f} e a Semente Certificada a R$ 291,00, "
        f"a relação de troca é de {291.0/max(1, soja['preco_atual']):.2f} sacas de grão para cada saca de semente. "
        f"Para pastagens de inverno, o Azevém está em R$ 6,75/kg (recomendação média de 25 kg/ha) e a Aveia Preta em R$ 3,95/kg (60 kg/ha)."
    )
  else:
    return (
        f"🤖 Olá! Sou a Inteligência Artificial do CR AgroStat na região {regiao_interna_sel}. "
        f"Neste momento ({dados['atualizacao']}), com base em {fonte_ativa}, temos: "
        f"Trigo Pão a R$ {trigo['preco_atual']:.2f}/sc ({trigo['ult_usx']:.2f} USX em Chicago), "
        f"Soja a R$ {soja['preco_atual']:.2f}/sc, Arroz a R$ {arroz['preco_atual']:.2f}/sc, Milho a R$ {milho['preco_atual']:.2f}/sc "
        f"e Dólar a R$ {dolar:.2f}. Pergunte-me sobre qualquer grão, semente, relatório StoneX, clima ou cálculo de frete!"
    )


# =============================================================================
# ESTRUTURA HIERÁRQUICA DE 3 NÍVEIS: MACRO-REGIÃO ➔ ESTADO (UF) ➔ REGIÃO DO ESTADO
# (Cada sub-região possui seu diferencial dinâmico sobre o preço do dia)
# =============================================================================
HIERARQUIA_BRASIL = {
    "Sul": ["RS", "SC", "PR"],
    "Centro-Oeste": ["MT", "MS", "GO"],
    "Sudeste": ["SP", "MG"],
    "Nordeste (MATOPIBA)": ["BA", "MA", "TO", "PI"],
    "Norte": ["RO", "PA", "RR"],
}

NOMES_ESTADOS = {
    "RS": "Rio Grande do Sul (RS)",
    "SC": "Santa Catarina (SC)",
    "PR": "Paraná (PR)",
    "MT": "Mato Grosso (MT)",
    "MS": "Mato Grosso do Sul (MS)",
    "GO": "Goiás / DF (GO)",
    "SP": "São Paulo (SP)",
    "MG": "Minas Gerais (MG)",
    "BA": "Bahia (BA)",
    "MA": "Maranhão (MA)",
    "TO": "Tocantins (TO)",
    "PI": "Piauí (PI)",
    "RO": "Rondônia (RO)",
    "PA": "Pará (PA)",
    "RR": "Roraima (RR)",
}

# Sub-regiões de cada Estado com fator dinâmico local (oscilam junto com o mercado)
SUBREGIOES_ESTADOS = {
    "RS": {
        "Fronteira Oeste (São Borja / Itaqui / Uruguaiana)": 1.000,
        "Missões (Santo Ângelo / São Luiz Gonzaga / Giruá)": 0.995,
        "Planalto e Noroeste (Passo Fundo / Ijuí / Cruz Alta)": 1.012,
        "Campanha e Central (Bagé / Dom Pedrito / Santa Maria)": 0.992,
        "Campos de Cima da Serra (Vacaria / Lagoa Vermelha)": 1.008,
        "Zona Sul e Porto (Pelotas / Rio Grande / Camaquã)": 1.035,
    },
    "SC": {
        "Oeste Catarinense (Chapecó / Xanxerê / Concórdia)": 1.018,
        "Meio-Oeste e Planalto (Campos Novos / Lages / Joaçaba)": 1.022,
        "Planalto Norte (Canoinhas / Mafra)": 1.025,
        "Sul Catarinense (Turvo / Araranguá / Tubarão)": 1.015,
        "Porto de São Francisco do Sul / Vale do Itajaí": 1.042,
    },
    "PR": {
        "Oeste Paranaense (Cascavel / Toledo / Marechal Rondon)": 1.010,
        "Sudoeste e Centro-Sul (Pato Branco / Francisco Beltrão / Guarapuava)": 1.016,
        "Campos Gerais (Ponta Grossa / Castro / Carambeí)": 1.028,
        "Norte e Noroeste (Londrina / Maringá / Campo Mourão)": 1.014,
        "Porto de Paranaguá / Leste Paranaense": 1.048,
    },
    "MT": {
        "Médio-Norte (Sorriso / Sinop / Lucas do Rio Verde)": 0.925,
        "Sul e Sudeste (Rondonópolis / Primavera do Leste / Campo Verde)": 0.948,
        "Vale do Araguaia (Querência / Canarana / Barra do Garças)": 0.932,
        "Noroeste e Parecis (Campo Novo do Parecis / Sapezal / Juína)": 0.918,
    },
    "MS": {
        "Sul e Grande Dourados (Dourados / Ponta Porã / Naviraí)": 0.955,
        "Centro-Sul (Maracaju / Sidrolândia / Rio Brilhante)": 0.962,
        "Norte e Bolsão (Chapadão do Sul / São Gabriel do Oeste)": 0.968,
    },
    "GO": {
        "Sudoeste Goiano (Rio Verde / Jataí / Mineiros)": 0.965,
        "Sul e Centro (Itumbiara / Catalão / Goiânia)": 0.972,
        "Leste Goiano e PAD-DF (Cristalina / Formosa / Unaí)": 0.980,
    },
    "SP": {
        "Sudoeste Paulista (Itapeva / Avaré / Itapetininga)": 1.025,
        "Norte e Mogiana (Ribeirão Preto / Orlândia / Franca)": 1.020,
        "Vale do Paranapanema (Assis / Ourinhos / Presidente Prudente)": 1.015,
        "Porto de Santos / Campinas (Corredor de Exportação)": 1.055,
    },
    "MG": {
        "Triângulo Mineiro (Uberaba / Uberlândia / Ituiutaba)": 0.985,
        "Alto Paranaíba e Noroeste (Patos de Minas / Unaí / Paracatu)": 0.982,
        "Sul de Minas e Campos das Vertentes (Lavras / Varginha)": 1.010,
    },
    "BA": {
        "Oeste da Bahia (Luís Eduardo Magalhães / Barreiras / Correntina)": 0.960,
        "Chapada Diamantina e Irecê (Mucugê / Ibicoara)": 0.985,
    },
    "MA": {
        "Sul Maranhense (Balsas / Tasso Fragoso / Riachão)": 0.952,
        "Corredor Itaqui / Chapadinha (São Luís / Porto do Itaqui)": 1.015,
    },
    "TO": {
        "Sul e Central (Gurupi / Palmas / Porto Nacional / Lagoa da Confusão)": 0.958,
        "Nordeste e Bico do Papagaio (Pedro Afonso / Araguaína)": 0.962,
    },
    "PI": {
        "Cerrados Piauienses (Uruçuí / Bom Jesus / Baixa Grande do Ribeiro)": 0.954,
        "Vale do Parnaíba (Teresina / Floriano)": 0.965,
    },
    "RO": {
        "Cone Sul de Rondônia (Vilhena / Cerejeiras / Corumbiara)": 0.915,
        "Central e Madeira-Mamoré (Ariquemes / Ji-Paraná / Porto Velho)": 0.928,
    },
    "PA": {
        "Sudeste Paraense (Paragominas / Redenção / Marabá)": 0.965,
        "Oeste e Arco Norte (Santarém / Belterra / Porto de Barcarena)": 0.995,
    },
    "RR": {
        "Lavrados de Roraima (Boa Vista / Bonfim / Alto Alegre)": 0.975,
    },
}


def criar_icone_semente_png(largura=192, altura=192):
  linhas_raw = bytearray()
  cx, cy = largura / 2.0, altura / 2.0
  raio_quadrado = largura * 0.44

  for y in range(altura):
    linhas_raw.append(0)
    for x in range(largura):
      dx, dy = abs(x - cx), abs(y - cy)
      dentro_card = (dx <= raio_quadrado) and (dy <= raio_quadrado)
      if dentro_card:
        nx = (x - cx) / (largura * 0.28)
        ny = (y - cy) / (altura * 0.28)
        folha_esq = ((nx + 0.32) ** 2) / 0.28 + ((ny - 0.05) ** 2) / 0.75 <= 1.0
        folha_dir = ((nx - 0.32) ** 2) / 0.28 + ((ny - 0.05) ** 2) / 0.75 <= 1.0
        gota_centro = (nx**2) / 0.16 + ((ny + 0.38) ** 2) / 0.38 <= 1.0

        if gota_centro:
          r, g, b, a = 250, 204, 21, 255
        elif folha_esq or folha_dir:
          r, g, b, a = 16, 185, 129, 255
        elif dx > raio_quadrado - (largura * 0.04) or dy > raio_quadrado - (
            altura * 0.04
        ):
          r, g, b, a = 16, 185, 129, 255
        else:
          r, g, b, a = 15, 23, 42, 255
      else:
        r, g, b, a = 0, 0, 0, 0
      linhas_raw.extend((r, g, b, a))

  def bloco_png(tipo, dados_b):
    crc = zlib.crc32(tipo + dados_b) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(dados_b)) + tipo + dados_b + struct.pack(">I", crc)
    )

  assinatura = b"\x89PNG\r\n\x1a\n"
  ihdr = struct.pack(">IIBBBBB", largura, altura, 8, 6, 0, 0, 0)
  idat = zlib.compress(bytes(linhas_raw), 9)
  return (
      assinatura
      + bloco_png(b"IHDR", ihdr)
      + bloco_png(b"IDAT", idat)
      + bloco_png(b"IEND", b"")
  )


def gerar_arquivos_servidor_e_icones():
  try:
    os.makedirs("dados", exist_ok=True)
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
    os.makedirs(os.path.join(PASTA_ASSETS, "icons"), exist_ok=True)
    caminho_fav = os.path.join(PASTA_ASSETS, "favicon.png")
    if not os.path.exists(caminho_fav):
      png_64 = criar_icone_semente_png(64, 64)
      png_192 = criar_icone_semente_png(192, 192)
      with open(caminho_fav, "wb") as f:
        f.write(png_64)
      with open(os.path.join(PASTA_ASSETS, "icons", "icon-192.png"), "wb") as f:
        f.write(png_192)
      with open(os.path.join(PASTA_ASSETS, "icons", "icon-512.png"), "wb") as f:
        f.write(png_192)
      with open(
          os.path.join(PASTA_ASSETS, "icons", "loading-animation.png"), "wb"
      ) as f:
        f.write(png_192)

      cabecalho_ico = struct.pack("<HHH", 0, 1, 1) + struct.pack(
          "<BBBBHHII", 64, 64, 0, 0, 1, 32, len(png_64), 22
      )
      with open("cr_agrostat.ico", "wb") as f:
        f.write(cabecalho_ico + png_64)
  except Exception:
    pass


# =============================================================================
# GERADOR DE ARTE / PRINT PARA STORIES (INSTAGRAM & WHATSAPP) COM ILUSTRAÇÕES
# =============================================================================
# Quatro fotografias agrícolas originais, incorporadas ao próprio app.py.
# Ciclo diário: trigo, soja, arroz irrigado e colheita mecanizada.
# Não depende de hospedagem de imagens, conexão externa, chaves nem arquivos extras.
FUNDOS_STORIES_EMBUTIDOS = (
    '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',
)


@lru_cache(maxsize=4)
def obter_fundo_fotografico_stories(data_iso):
  indice = datetime.strptime(data_iso, "%Y-%m-%d").date().toordinal() % len(FUNDOS_STORIES_EMBUTIDOS)
  return "data:image/jpeg;base64," + FUNDOS_STORIES_EMBUTIDOS[indice]


def gerar_svg_stories_marketing_b64(dados, uf_sel, regiao_sel, nome_consultor, tel_consultor, chuva_10d_mm, temp_hoje, fonte_ativa):
  """Cria um Card Vertical 9:16 (Stories) rico em ilustrações temáticas de lavoura, clima e cotações."""
  itens = dados.get("itens", [])
  fundo_diario = obter_fundo_fotografico_stories(datetime.now().strftime("%Y-%m-%d"))
  foto_svg = (f'<image x="0" y="0" width="540" height="960" preserveAspectRatio="xMidYMid slice" href="{fundo_diario}" opacity="0.63"/>'
              if fundo_diario else "")
  Linhas_cot = ""
  y_c = 340
  for it in itens[:6]:
    fator_sub = SUBREGIOES_ESTADOS.get(uf_sel, {}).get(regiao_sel, 1.0)
    val_r = round(it["preco_atual"] * fator_sub, 2)
    sinal = "+" if it["var_dia"] >= 0 else ""
    cor_v = "#4ADE80" if it["var_dia"] >= 0 else "#F87171"
    Linhas_cot += f"""
    <rect x="32" y="{y_c}" width="476" height="68" rx="14" fill="#0E2030" stroke="#21394C" stroke-width="1.5"/>
    <circle cx="68" cy="{y_c+34}" r="18" fill="{it['cor']}" fill-opacity="0.12" stroke="{it['cor']}" stroke-width="1"/>
    <path d="M68 {y_c+20} Q55 {y_c+32} 68 {y_c+47} Q81 {y_c+32} 68 {y_c+20}Z" fill="none" stroke="{it['cor']}" stroke-width="1.7"/>
    <path d="M68 {y_c+45} V{y_c+27} M68 {y_c+37} l-7 -6 M68 {y_c+34} l7 -6" fill="none" stroke="{it['cor']}" stroke-width="1.6" stroke-linecap="round"/>
    <text x="100" y="{y_c+29}" fill="#FFFFFF" font-family="Arial" font-size="16" font-weight="bold">{it['nome_curto']}</text>
    <text x="100" y="{y_c+50}" fill="#94A3B8" font-family="Arial" font-size="11">{it['unidade']} • {it['codigo_cbot']} ({it['ult_usx']:.1f} USX)</text>
    <text x="488" y="{y_c+30}" fill="#FFFFFF" font-family="Arial" font-size="20" font-weight="bold" text-anchor="end">R$ {val_r:.2f}</text>
    <text x="488" y="{y_c+51}" fill="{cor_v}" font-family="Arial" font-size="12" font-weight="bold" text-anchor="end">{sinal}{it['var_dia']:.2f}% hoje</text>
    """
    y_c += 78

  svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 960" width="100%" height="100%">
  <defs>
    <linearGradient id="bgStory" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#041E14"/>
      <stop offset="45%" stop-color="#080D16"/>
      <stop offset="100%" stop-color="#0B192C"/>
    </linearGradient>
    <linearGradient id="solAgro" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FACC15" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="#10B981" stop-opacity="0.0"/>
    </linearGradient>
  </defs>
  <rect width="540" height="960" rx="28" fill="url(#bgStory)"/>
  {foto_svg}
  <rect width="540" height="960" rx="28" fill="#06121B" fill-opacity="0.62" stroke="#10B981" stroke-width="3"/>

  <!-- Ilustração Temática de Lavoura, Sol Nascente e Silos no Topo do Story -->
  <circle cx="440" cy="115" r="65" fill="url(#solAgro)"/>
  <path d="M 0,210 Q 140,175 280,198 T 540,182 L 540,245 L 0,245 Z" fill="#064E3B" fill-opacity="0.45"/>
  <path d="M 0,225 Q 190,195 360,215 T 540,202 L 540,255 L 0,255 Z" fill="#10B981" fill-opacity="0.22"/>

  <!-- Cabeçalho da Marca CR AgroStat -->
  <rect x="32" y="28" width="64" height="64" rx="18" fill="#10B981" stroke="#FACC15" stroke-width="2.5"/>
  <path d="M 64,42 C 52,54 50,68 64,78 C 78,68 76,54 64,42 Z" fill="#080D16"/>
  <circle cx="64" cy="54" r="5" fill="#FACC15"/>
  <text x="110" y="56" fill="#FFFFFF" font-family="Arial" font-size="25" font-weight="bold">CR AgroStat Brasil</text>
  <text x="110" y="78" fill="#10B981" font-family="Arial" font-size="13" font-weight="bold">BOLETIM DIÁRIO DE MERCADO &amp; CLIMA AGRÍCOLA</text>
  <text x="110" y="96" fill="#38BDF8" font-family="Arial" font-size="11">{dados.get('atualizacao', agora_str())}  ·  Dólar Spot: R$ {dados.get('dolar', 5.35):.2f} ({dados.get('dolar_var', 0.0):+.2f}%)</text>

  <!-- Faixa da Região Selecionada -->
  <rect x="32" y="114" width="476" height="54" rx="12" fill="#0A1826" stroke="#10B981" stroke-width="1.2"/>
  <path d="M51 123 a6 6 0 0 0 -6 6 c0 5 6 10 6 10 s6 -5 6 -10 a6 6 0 0 0 -6 -6z" fill="none" stroke="#FACC15" stroke-width="1.5"/>
  <circle cx="51" cy="129" r="1.5" fill="#FACC15"/>
  <text x="66" y="135" fill="#FACC15" font-family="Arial" font-size="12" font-weight="bold">PRAÇA / REGIÃO EM DESTAQUE</text>
  <text x="48" y="156" fill="#FFFFFF" font-family="Arial" font-size="15" font-weight="bold">{uf_sel} • {regiao_sel[:44]}</text>

  <!-- Card Duplo de Clima Regional + Câmbio / Bolsas com Ilustração de Nuvem e Chuva -->
  <rect x="32" y="180" width="232" height="118" rx="16" fill="#0A1826" stroke="#38BDF8" stroke-width="1.5"/>
  <text x="48" y="204" fill="#38BDF8" font-family="Arial" font-size="12" font-weight="bold">CLIMA &amp; CHUVA (10 DIAS)</text>
  <text x="48" y="238" fill="#FFFFFF" font-family="Arial" font-size="26" font-weight="bold">{chuva_10d_mm:.1f} mm</text>
  <text x="48" y="260" fill="#CBD5E1" font-family="Arial" font-size="12">Temperatura: {temp_hoje}</text>
  <text x="48" y="280" fill="#10B981" font-family="Arial" font-size="10" font-weight="bold">Satélite Open-Meteo ECMWF/GFS</text>

  <rect x="276" y="180" width="232" height="118" rx="16" fill="#0A1826" stroke="#FACC15" stroke-width="1.5"/>
  <text x="292" y="204" fill="#FACC15" font-family="Arial" font-size="12" font-weight="bold">BOLSAS &amp; CÂMBIO HOJE</text>
  <text x="292" y="238" fill="#FFFFFF" font-family="Arial" font-size="24" font-weight="bold">US$ 1 = R$ {dados.get('dolar', 5.35):.2f}</text>
  <text x="292" y="260" fill="#CBD5E1" font-family="Arial" font-size="12">Trigo CBOT: {itens[0]['ult_usx']:.1f} USX</text>
  <text x="292" y="280" fill="#38BDF8" font-family="Arial" font-size="10" font-weight="bold">Base: {fonte_ativa[:26]}</text>

  <text x="32" y="326" fill="#FACC15" font-family="Arial" font-size="14" font-weight="bold">COTAÇÕES DO DIA · R$ POR SACA OU KG</text>
  {Linhas_cot}

  <!-- Rodapé de Propaganda Oficial do Consultor e Fontes Auditadas -->
  <rect x="32" y="818" width="476" height="114" rx="18" fill="#052E16" stroke="#10B981" stroke-width="2"/>
  <text x="50" y="844" fill="#6EE7B7" font-family="Arial" font-size="12" font-weight="bold">CONSULTORIA &amp; INTELIGÊNCIA COMERCIAL</text>
  <text x="50" y="868" fill="#FFFFFF" font-family="Arial" font-size="18" font-weight="bold">{nome_consultor[:32]}</text>
  <text x="50" y="889" fill="#FACC15" font-family="Arial" font-size="13" font-weight="bold">WhatsApp: {tel_consultor}  |  CR AgroStat Brasil</text>
  <text x="50" y="914" fill="#CBD5E1" font-family="Arial" font-size="10">Fontes de referência: CBOT, StoneX, CEPEA, IRGA, Emater e Open-Meteo.</text>
</svg>"""
  return base64.b64encode(svg.encode("utf-8")).decode("utf-8"), svg
# =============================================================================
# CR AGROSTAT BRASIL v9.0 — PARTE 2 DE 3
# Mapa Geográfico Real, Histórico de Parceria do Cliente e Motor Dinâmico StoneX/CBOT
# =============================================================================

def gerar_svg_geografico_estados_brasil_b64(
    uf_ativa="RS",
    modo_local_cliente=False,
    lat_cli=-28.66,
    lon_cli=-56.00,
    nome_cli="",
    roteiro_cli="",
):
  """Gera o Mapa Geográfico Cartográfico Real do Brasil ou o Mapa Satélite/Topográfico da Fazenda do Cliente."""
  if modo_local_cliente:
    svg_local = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 580 260" width="100%" height="100%">
      <defs>
        <linearGradient id="terrenoSat" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#061610"/>
          <stop offset="50%" stop-color="#0A2319"/>
          <stop offset="100%" stop-color="#071521"/>
        </linearGradient>
        <pattern id="gradeGps" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#21394C" stroke-width="0.7"/>
        </pattern>
      </defs>
      <rect width="580" height="260" rx="16" fill="url(#terrenoSat)" stroke="#10B981" stroke-width="1.5"/>
      <rect width="580" height="260" rx="16" fill="url(#gradeGps)"/>

      <!-- Hidrografia Regional (Rio Uruguai / Bacias Locais) e Curvas Topográficas -->
      <path d="M 12,260 C 58,180 88,110 135,0" fill="none" stroke="#0284C7" stroke-width="6" stroke-opacity="0.45"/>
      <path d="M 0,70 Q 160,110 310,85 T 580,120" fill="none" stroke="#1E3A5F" stroke-width="1.5" stroke-dasharray="5,4"/>

      <!-- Talhões Agrícolas Demarcados via Satélite -->
      <polygon points="365,95 475,82 495,168 380,182" fill="#10B981" fill-opacity="0.22" stroke="#10B981" stroke-width="1.8"/>
      <polygon points="480,92 555,105 545,178 498,168" fill="#EAB308" fill-opacity="0.16" stroke="#FACC15" stroke-width="1.4"/>

      <!-- Rodovia de Acesso e Rota Mais Rápida Calculada -->
      <path d="M 115,105 L 265,135 L 430,138" fill="none" stroke="#475569" stroke-width="4.5"/>
      <path d="M 115,105 L 265,135 L 430,138" fill="none" stroke="#FACC15" stroke-width="2.2" stroke-dasharray="7,5"/>

      <!-- Pino 1: Escritório Comercial (Urbano) -->
      <circle cx="115" cy="105" r="14" fill="#38BDF8" fill-opacity="0.25"/>
      <circle cx="115" cy="105" r="6" fill="#38BDF8" stroke="#FFFFFF" stroke-width="2"/>
      <rect x="28" y="58" width="178" height="32" rx="8" fill="#0A1826" stroke="#38BDF8" stroke-width="1.2"/>
      <text x="40" y="78" fill="#38BDF8" font-family="Arial" font-size="11" font-weight="bold">🏢 Escritório / Sede Urbana</text>

      <!-- Pino 2: Lavoura / Sede da Fazenda no Interior -->
      <circle cx="430" cy="138" r="18" fill="#FACC15" fill-opacity="0.28"/>
      <circle cx="430" cy="138" r="7" fill="#FACC15" stroke="#080D16" stroke-width="2"/>
      <rect x="285" y="192" width="275" height="52" rx="10" fill="#0A1826" stroke="#FACC15" stroke-width="1.4"/>
      <text x="298" y="212" fill="#FACC15" font-family="Arial" font-size="12" font-weight="bold">🚜 Lavoura: {nome_cli[:26]}</text>
      <text x="298" y="230" fill="#E2E8F0" font-family="Arial" font-size="10">📍 {roteiro_cli[:36]} (GPS: {lat_cli:.3f}, {lon_cli:.3f})</text>

      <rect x="18" y="212" width="245" height="30" rx="8" fill="#052E16" stroke="#10B981" stroke-width="1"/>
      <text x="30" y="231" fill="#6EE7B7" font-family="Arial" font-size="11" font-weight="bold">🛰️ Georreferenciamento Ativo (Rota Rápida)</text>
    </svg>"""
    return base64.b64encode(svg_local.encode("utf-8")).decode("utf-8")

  def cor_uf(sigla, cor_padrao):
    return "#10B981" if uf_ativa == sigla else cor_padrao

  svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 650 580" width="100%" height="100%">
  <defs>
    <radialGradient id="oceano Atlántico" cx="55%" cy="50%" r="68%">
      <stop offset="0%" stop-color="#0E1E32"/>
      <stop offset="100%" stop-color="#060B14"/>
    </radialGradient>
    <pattern id="gradeCartografica" width="65" height="58" patternUnits="userSpaceOnUse">
      <path d="M 65 0 L 0 0 0 58" fill="none" stroke="#21394C" stroke-width="0.8" stroke-dasharray="3,3"/>
    </pattern>
    <filter id="relevoTerreno" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="5" stdDeviation="6" flood-color="#000000" flood-opacity="0.7"/>
    </filter>
  </defs>
  <rect width="650" height="580" rx="22" fill="url(#oceano Atlántico)"/>
  <rect width="650" height="580" rx="22" fill="url(#gradeCartografica)"/>

  <!-- Coordenadas Geográficas Oficiais -->
  <text x="14" y="76" fill="#475569" font-family="Arial" font-size="9">0° Equador</text>
  <text x="14" y="192" fill="#475569" font-family="Arial" font-size="9">10° S</text>
  <text x="14" y="310" fill="#475569" font-family="Arial" font-size="9">20° S</text>
  <text x="14" y="362" fill="#475569" font-family="Arial" font-size="9">23.5° Capricórnio</text>
  <text x="14" y="472" fill="#10B981" font-family="Arial" font-size="9" font-weight="bold">28.6° S (São Borja - RS)</text>

  <!-- Países Limítrofes da América do Sul (Argentina, Uruguai, Paraguai, Bolívia) -->
  <path d="M 125,240 L 182,292 L 235,315 L 252,380 L 265,435 L 245,495 L 295,548 L 328,538 L 285,578 L 95,578 L 82,310 Z"
        fill="#0B1320" stroke="#21394C" stroke-width="1.4"/>
  <text x="195" y="495" fill="#334155" font-family="Arial" font-size="10" font-weight="bold">ARGENTINA</text>
  <text x="295" y="572" fill="#334155" font-family="Arial" font-size="9" font-weight="bold">URUGUAI</text>
  <text x="215" y="395" fill="#334155" font-family="Arial" font-size="9" font-weight="bold">PARAGUAI</text>

  <!-- MAPA GEOGRÁFICO REAL DOS ESTADOS BRASILEIROS -->
  <g filter="url(#relevoTerreno)" stroke="#94A3B8" stroke-width="1.3" stroke-linejoin="round">
    <!-- NORTE -->
    <path d="M 38,162 L 62,118 L 112,92 L 158,84 L 182,58 L 208,68 L 238,105 L 248,162 L 222,198 L 158,205 L 92,195 L 42,188 Z" fill="{cor_uf('AM', '#162A22')}" stroke="#64748B"/>
    <path d="M 182,58 L 205,28 L 238,36 L 242,78 L 208,68 Z" fill="{cor_uf('RR', '#1B3228')}" stroke="#64748B"/>
    <path d="M 248,162 L 238,105 L 242,78 L 308,58 L 348,42 L 372,78 L 385,112 L 368,188 L 342,218 L 268,215 L 248,162 Z" fill="{cor_uf('PA', '#1B352C')}" stroke="#6EE7B7"/>
    <path d="M 158,205 L 222,198 L 248,225 L 228,255 L 178,242 Z" fill="{cor_uf('RO', '#213B32')}" stroke="#6EE7B7"/>
    <path d="M 342,218 L 368,188 L 392,185 L 395,258 L 352,262 Z" fill="{cor_uf('TO', '#284238')}" stroke="#FACC15"/>

    <!-- NORDESTE / MATOPIBA -->
    <path d="M 385,112 L 432,115 L 448,158 L 415,212 L 392,185 L 368,188 Z" fill="{cor_uf('MA', '#3E2C18')}" stroke="#FB923C"/>
    <path d="M 432,115 L 468,125 L 472,185 L 435,222 L 415,212 L 448,158 Z" fill="{cor_uf('PI', '#46311A')}" stroke="#FB923C"/>
    <path d="M 468,125 L 528,142 L 578,178 L 572,225 L 528,248 L 472,185 Z" fill="{cor_uf('NE', '#382614')}" stroke="#F97316"/>
    <path d="M 395,258 L 435,222 L 472,185 L 528,248 L 512,322 L 478,332 L 408,308 L 392,282 Z" fill="{cor_uf('BA', '#52361B')}" stroke="#FB923C"/>

    <!-- CENTRO-OESTE -->
    <path d="M 222,198 L 248,162 L 268,215 L 342,218 L 352,262 L 335,312 L 262,310 L 228,255 L 248,225 Z" fill="{cor_uf('MT', '#3B3414')}" stroke="#FACC15"/>
    <path d="M 352,262 L 395,258 L 392,282 L 408,308 L 378,342 L 335,332 L 335,312 Z" fill="{cor_uf('GO', '#473F18')}" stroke="#FACC15"/>
    <path d="M 262,310 L 335,312 L 335,332 L 345,368 L 312,402 L 268,388 L 255,345 Z" fill="{cor_uf('MS', '#3E3816')}" stroke="#FACC15"/>

    <!-- SUDESTE -->
    <path d="M 378,342 L 408,308 L 478,332 L 492,368 L 458,395 L 402,388 L 368,365 Z" fill="{cor_uf('MG', '#0F385A')}" stroke="#38BDF8"/>
    <path d="M 478,332 L 512,322 L 502,382 L 458,395 L 492,368 Z" fill="{cor_uf('RJ', '#0C2D48')}" stroke="#38BDF8"/>
    <path d="M 312,402 L 345,368 L 368,365 L 402,388 L 442,405 L 402,428 L 362,418 Z" fill="{cor_uf('SP', '#12456E')}" stroke="#38BDF8"/>

    <!-- SUL (PR, SC, RS) -->
    <path d="M 302,425 L 312,402 L 362,418 L 392,432 L 378,455 L 315,448 Z" fill="{cor_uf('PR', '#0B523F')}" stroke="#34D399" stroke-width="1.9"/>
    <path d="M 315,448 L 378,455 L 385,482 L 345,485 L 312,468 Z" fill="{cor_uf('SC', '#0E634C')}" stroke="#34D399" stroke-width="1.9"/>
    <path d="M 255,495 L 288,465 L 312,468 L 345,485 L 378,485 L 358,528 L 322,555 L 292,535 Z" fill="{cor_uf('RS', '#059669')}" stroke="#A7F3D0" stroke-width="2.6"/>
  </g>

  <!-- Bacias Hidrográficas Reais (Amazonas, São Francisco, Paraná e Rio Uruguai) -->
  <path d="M 65,135 Q 180,138 325,95" fill="none" stroke="#38BDF8" stroke-width="2.2" stroke-opacity="0.5"/>
  <path d="M 345,368 L 302,425 L 288,465 L 255,495" fill="none" stroke="#38BDF8" stroke-width="2.5" stroke-opacity="0.85"/>

  <!-- Siglas Geográficas e Estado Selecionado -->
  <g fill="#E2E8F0" font-family="Arial" font-size="10" font-weight="bold" text-anchor="middle">
    <text x="145" y="150">AM</text><text x="215" y="55">RR</text><text x="305" y="145">PA</text>
    <text x="202" y="228">RO</text><text x="372" y="232">TO</text><text x="412" y="168">MA</text>
    <text x="448" y="182">PI</text><text x="458" y="282">BA</text>
    <text x="288" y="268">MT</text><text x="368" y="305">GO</text><text x="298" y="362">MS</text>
    <text x="435" y="362">MG</text><text x="375" y="405">SP</text><text x="348" y="436">PR</text>
    <text x="355" y="472">SC</text><text x="318" y="516" fill="#FFFFFF" font-size="12">RS</text>
  </g>

  <rect x="445" y="495" width="188" height="68" rx="12" fill="#0A1826" stroke="#10B981" stroke-width="1.5"/>
  <text x="458" y="516" fill="#10B981" font-family="Arial" font-size="11" font-weight="bold">ESTADO EM DESTAQUE: {uf_ativa}</text>
  <text x="458" y="534" fill="#E2E8F0" font-family="Arial" font-size="10">Clique nos pinos ou selecione</text>
  <text x="458" y="549" fill="#38BDF8" font-family="Arial" font-size="10">a Região Interna do Estado</text>
</svg>"""
  return base64.b64encode(svg.encode("utf-8")).decode("utf-8")


# =============================================================================
# CARTOGRAFIA DAS UFs: GeoJSON original derivado das malhas do IBGE
# Fonte pública CC0: github.com/henriquemalvar/br-geojson (estados.geojson)
# Um único app.py; o arquivo cartográfico é baixado e colocado no cache na 1ª carga.
# =============================================================================
MAPA_GEODADOS_URLS = (
    "https://raw.githubusercontent.com/henriquemalvar/br-geojson/main/dist/estados.geojson",
    "https://cdn.jsdelivr.net/gh/henriquemalvar/br-geojson@main/dist/estados.geojson",
)


def coordenada_mapa(lat, lon):
  """Projeção geográfica com mesma escala de longitude e latitude (sem distorcer as UFs)."""
  return 28 + (float(lon) + 74.25) * 16.4, 23 + (5.4 - float(lat)) * 16.4


def _distancia_segmento(p, a, b):
  dx, dy = b[0] - a[0], b[1] - a[1]
  if dx == dy == 0:
    return math.hypot(p[0] - a[0], p[1] - a[1])
  t = max(0.0, min(1.0, ((p[0]-a[0])*dx + (p[1]-a[1])*dy) / (dx*dx+dy*dy)))
  return math.hypot(p[0]-(a[0]+t*dx), p[1]-(a[1]+t*dy))


def simplificar_linha(pontos, tolerancia=0.85):
  """Reduz pontos sem deslocar significativamente os limites dos estados."""
  if len(pontos) < 4:
    return pontos
  maior, indice = 0, 0
  for i in range(1, len(pontos)-1):
    dist = _distancia_segmento(pontos[i], pontos[0], pontos[-1])
    if dist > maior:
      maior, indice = dist, i
  if maior > tolerancia:
    return simplificar_linha(pontos[:indice+1], tolerancia)[:-1] + simplificar_linha(pontos[indice:], tolerancia)
  return [pontos[0], pontos[-1]]


@lru_cache(maxsize=1)
def carregar_estados_geojson():
  try:
    if os.path.isfile(MAPA_IBGE_CACHE):
      with open(MAPA_IBGE_CACHE, "r", encoding="utf-8") as f:
        cache = json.load(f)
      if cache.get("type") == "FeatureCollection" and len(cache.get("features", [])) >= 26:
        return cache
  except (OSError, ValueError, TypeError):
    pass
  for url in MAPA_GEODADOS_URLS:
    try:
      resp = requests.get(url, timeout=9, headers={"User-Agent": "CRAgroStat/10.0 (IBGE GeoJSON map)"})
      resp.raise_for_status()
      if len(resp.content) > 32_000_000:
        continue
      cache = resp.json()
      if cache.get("type") == "FeatureCollection" and len(cache.get("features", [])) >= 26:
        salvar_json_atomico(MAPA_IBGE_CACHE, cache)
        return cache
    except (requests.RequestException, ValueError, OSError):
      continue
  return None


_CENTROS_UF = {
 "AC":(-9.0,-70.6), "AL":(-9.7,-36.6), "AP":(1.3,-51.7), "AM":(-3.8,-63.2),
 "BA":(-12.5,-41.7), "CE":(-5.3,-39.3), "DF":(-15.8,-47.9), "ES":(-19.6,-40.6),
 "GO":(-16.3,-49.2), "MA":(-5.0,-45.3), "MT":(-12.9,-55.9), "MS":(-20.6,-54.5),
 "MG":(-18.6,-44.3), "PA":(-4.6,-52.3), "PB":(-7.1,-36.8), "PR":(-24.7,-51.3),
 "PE":(-8.3,-37.9), "PI":(-7.7,-42.6), "RJ":(-22.2,-42.8), "RN":(-5.8,-36.7),
 "RS":(-30.0,-53.2), "RO":(-10.9,-63.1), "RR":(2.0,-61.1), "SC":(-27.4,-50.9),
 "SP":(-22.6,-48.7), "SE":(-10.6,-37.4), "TO":(-10.2,-48.0)
}


def mapa_brasil_ibge_b64(uf_ativa="RS"):
  """Desenha todas as 27 UFs utilizando as coordenadas reais de seus polígonos."""
  geo = carregar_estados_geojson()
  if not geo:
    return None
  regioes = {uf: nome for nome, ufs in HIERARQUIA_BRASIL.items() for uf in ufs}
  cor_regiao = {"Sul":"#0D816D", "Centro-Oeste":"#9F751F", "Sudeste":"#28608C",
                "Nordeste (MATOPIBA)":"#96663B", "Norte":"#286D62"}
  partes = []
  for ft_geo in geo["features"]:
    prop = ft_geo.get("properties", {})
    sigla = str(prop.get("sigla") or prop.get("uf") or "").upper()
    if len(sigla) != 2:
      continue
    geom = ft_geo.get("geometry", {})
    tipo = geom.get("type")
    coords = geom.get("coordinates", [])
    grupos = [coords] if tipo == "Polygon" else coords if tipo == "MultiPolygon" else []
    caminhos = []
    for poly in grupos:
      for anel in poly:
        if len(anel) < 3:
          continue
        pontos = [coordenada_mapa(lat, lon) for lon, lat in anel]
        if pontos[0] != pontos[-1]:
          pontos.append(pontos[0])
        for_x = simplificar_linha(pontos, 0.52)
        caminhos.append("M" + " L".join(f"{x:.1f},{y:.1f}" for x,y in for_x) + " Z")
    ativo = sigla == uf_ativa
    cor = "#20C997" if ativo else cor_regiao.get(regioes.get(sigla), "#334E65")
    if caminhos:
      partes.append(f'<path d="{" ".join(caminhos)}" fill="{cor}" stroke="{"#D9F99D" if ativo else "#9AB5BF"}" stroke-width="{"2.1" if ativo else "0.75"}" stroke-linejoin="round" fill-rule="evenodd"/>')
  rotulos=[]
  for sigla,(lat,lon) in _CENTROS_UF.items():
    x,y=coordenada_mapa(lat,lon)
    rotulos.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" fill="{"#07111C" if sigla==uf_ativa else "#EAF4F3"}" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{sigla}</text>')
  svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="700" viewBox="0 0 720 700">
  <defs><linearGradient id="sea" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#102940"/><stop offset="1" stop-color="#06101C"/></linearGradient></defs>
  <rect width="720" height="700" rx="18" fill="url(#sea)"/>
  <g stroke="#294258" stroke-opacity=".45">{''.join(f'<line x1="{x}" x2="{x}" y1="12" y2="688" stroke-dasharray="3 6"/>' for x in range(70,720,90))}{''.join(f'<line y1="{y}" y2="{y}" x1="12" x2="708" stroke-dasharray="3 6"/>' for y in range(70,700,90))}</g>
  <g>{''.join(partes)}</g><g>{''.join(rotulos)}</g>
  <rect x="20" y="650" width="245" height="35" rx="9" fill="#07151F" stroke="#1CB08C"/>
  <text x="31" y="673" font-family="Arial,sans-serif" fill="#C9F7E9" font-size="12">Malha cartográfica IBGE • UF: {html_escape(str(uf_ativa))}</text>
  </svg>"""
  return base64.b64encode(svg.encode("utf-8")).decode("ascii")


def url_mapa_osm_cliente(lat,lon):
  """Mapa de ruas por coordenadas, não simulação de satélite/talhão."""
  # OpenStreetMap StaticMap (serviço externo gratuito sujeito a disponibilidade).
  params = {"center": f"{float(lat):.5f},{float(lon):.5f}",
            "zoom": 12, "size": "600x260", "maptype": "mapnik",
            "markers": f"{float(lat):.5f},{float(lon):.5f},red-pushpin"}
  return "https://staticmap.openstreetmap.de/staticmap.php?" + urllib.parse.urlencode(params)


def sintetizar_tts_ptbr(texto, voz="Feminina"):
  """Gera MP3 usando serviço disponível; não depende do áudio do servidor Windows.

  Edge neural é opcional. Plano B: uma fala curta pelo Google TTS. Se ambos
  não estiverem acessíveis, devolve None; a UI nunca afirma que tocou áudio.
  """
  texto = re.sub(r"[^\w\s.,;:!?()áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ/+-]", " ", texto)
  texto = " ".join(texto.split())[:1200]
  if not texto:
    return None
  try:
    import edge_tts
    import asyncio
    async def montar_audio():
      voz_nome = "pt-BR-AntonioNeural" if "Masc" in voz else "pt-BR-FranciscaNeural"
      audio = bytearray()
      async for pedaço in edge_tts.Communicate(texto, voz_nome).stream():
        if pedaço.get("type") == "audio":
          audio.extend(pedaço["data"])
      return bytes(audio)
    mp3 = asyncio.run(montar_audio())
    if mp3:
      return mp3
  except Exception:
    pass
  # Uma única requisição para evitar concatenar diversos MP3 inválidos.
  try:
    trecho = texto[:180].rsplit(" ", 1)[0] if len(texto) > 180 else texto
    r = requests.get("https://translate.google.com/translate_tts", params={
        "ie": "UTF-8", "client": "tw-ob", "tl": "pt-BR", "q": trecho},
        headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
    if r.ok and "audio" in r.headers.get("Content-Type", "") and len(r.content) > 100:
      return r.content
  except requests.RequestException:
    pass
  return None


def resposta_ia_com_api_opcional(pergunta, dados, uf, subregiao, resposta_local):
  """API é opcional. Não envia base de clientes nem dados pessoais do CRM."""
  chave = os.getenv("OPENAI_API_KEY", "").strip()
  if not chave:
    return resposta_local
  itens_resumidos = [{"produto":i.get("nome_curto"), "preco_estimado":i.get("preco_atual"),
                     "unidade":i.get("unidade"), "variacao_estimada":i.get("var_dia")}
                    for i in dados.get("itens", [])]
  contexto = {"estado": uf, "regiao":subregiao, "data_atualizacao":dados.get("atualizacao"),
              "estimativas_regionais":itens_resumidos, "dolar":dados.get("dolar"),
              "observacao":"Os preços regionais não são cotações oficiais e as projeções são cenários ilustrativos."}
  try:
    r = requests.post("https://api.openai.com/v1/chat/completions",
        headers={"Authorization": "Bearer " + chave},
        json={"model":os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "temperature":0.3,
              "max_tokens":360,
              "messages":[{"role":"system", "content": "Você é assistente agrícola no Brasil. Seja preciso. Nunca transforme preços simulados em cotações oficiais ou dados ao vivo. Não atribua a entidades externas análises não consultadas. Responda em português claro; se faltarem dados diga explicitamente."},
                          {"role":"user", "content": "Dados do sistema: "+json.dumps(contexto,ensure_ascii=False)+"\nPergunta: "+pergunta}]}, timeout=14)
    if r.ok:
      txt = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
      if txt:
        return txt.strip()
  except (requests.RequestException, ValueError, TypeError, IndexError):
    pass
  return resposta_local + "\n\n(A IA online não respondeu; resultado obtido pelo analisador local.)"


# =============================================================================
# GERADOR NATIVO DE ARQUIVO .PDF OFICIAL
# =============================================================================
def limpar_texto_pdf(texto):
  substituicoes = {
      "•": "-",
      "—": "-",
      "➔": "->",
      "🟢": "[RS/SUL]",
      "🔴": "[SC]",
      "🔵": "[PR]",
      "🟡": "[CO]",
      "🟠": "[NE]",
      "🟣": "[NO]",
      "🌎": "[BR]",
      "↓": "-",
      "↑": "+",
  }
  for k, v in substituicoes.items():
    texto = str(texto).replace(k, v)
  limpo = "".join(c for c in texto if ord(c) < 256)
  return limpo.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def criar_pdf_nativo(caminho_pdf, titulo_doc, subtitulo_doc, linhas_conteudo):
  linhas_por_pag = 46
  paginas_linhas = [
      linhas_conteudo[i : i + linhas_por_pag]
      for i in range(0, max(1, len(linhas_conteudo)), linhas_por_pag)
  ]

  objetos = []
  objetos.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
  objetos.append(b"")
  objetos.append(
      b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n"
  )
  objetos.append(
      b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n"
  )

  ids_paginas = []
  prox_id = 5

  for num_p, bloco in enumerate(paginas_linhas):
    id_pag = prox_id
    id_stream = prox_id + 1
    prox_id += 2
    ids_paginas.append(id_pag)

    comandos = []
    comandos.append("0.05 0.09 0.16 rg 30 765 535 50 re f")
    comandos.append("0.06 0.72 0.50 rg 30 762 535 4 re f")
    comandos.append("BT /F2 14 Tf 1 1 1 rg 42 793 Td")
    comandos.append(f"({limpar_texto_pdf(titulo_doc)}) Tj ET")
    comandos.append("BT /F1 9 Tf 0.65 0.95 0.82 rg 42 776 Td")
    comandos.append(
        f"({limpar_texto_pdf(subtitulo_doc + f'  |  Pag. {num_p+1}/{len(paginas_linhas)}')}) Tj ET"
    )

    y_pos = 740
    for linha in bloco:
      eh_titulo = (
          str(linha).startswith("===")
          or str(linha).startswith(">>>")
          or str(linha).startswith("[")
      )
      fonte_uso = "/F2 10 Tf" if eh_titulo else "/F1 9.5 Tf"
      cor_txt = "0.05 0.25 0.45 rg" if eh_titulo else "0.12 0.16 0.22 rg"
      comandos.append(f"BT {fonte_uso} {cor_txt} 36 {y_pos} Td")
      comandos.append(f"({limpar_texto_pdf(str(linha)[:108])}) Tj ET")
      y_pos -= 15

    comandos.append("0.85 0.88 0.92 rg 30 38 535 1 re f")
    comandos.append("BT /F1 8 Tf 0.4 0.45 0.52 rg 36 25 Td")
    comandos.append(
        f"({limpar_texto_pdf('CR AgroStat Brasil - Fontes: Chicago SRW Wheat Futures (CBOT), StoneX, CEPEA, IRGA/Emater e Open-Meteo.')}) Tj ET"
    )

    stream_bytes = "\n".join(comandos).encode("cp1252", errors="replace")
    obj_pag = (
        f"{id_pag} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {id_stream} 0 R >>\nendobj\n"
    ).encode("ascii")
    obj_str = (
        f"{id_stream} 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode(
            "ascii"
        )
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )
    objetos.append(obj_pag)
    objetos.append(obj_str)

  kids_str = " ".join(f"{pid} 0 R" for pid in ids_paginas)
  objetos[1] = (
      f"2 0 obj\n<< /Type /Pages /Kids [{kids_str}] /Count {len(ids_paginas)} >>\nendobj\n".encode(
          "ascii"
      )
  )

  pdf_final = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
  offsets = [0]
  for obj in objetos:
    offsets.append(len(pdf_final))
    pdf_final.extend(obj)

  pos_xref = len(pdf_final)
  total_objs = len(objetos) + 1
  pdf_final.extend(f"xref\n0 {total_objs}\n".encode("ascii"))
  pdf_final.extend(b"0000000000 65535 f \n")
  for off in offsets[1:]:
    pdf_final.extend(f"{off:010d} 00000 n \n".encode("ascii"))

  pdf_final.extend(
      f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{pos_xref}\n%%EOF\n".encode(
          "ascii"
      )
  )

  with open(caminho_pdf, "wb") as f:
    f.write(pdf_final)


# =============================================================================
# BANCO DE UTILIZADORES COM ESTATÍSTICAS DE PARCERIA DO CLIENTE E PREFERÊNCIA DE VOZ
# =============================================================================
def usuario_inicial_carlise():
  """Conta inicial. Nunca substituir uma conta existente, senha ou dados cadastrados."""
  return {
      "login": "carlise", "nome": "Carlise da Rosa",
      "cargo": "Administradora & Inteligência Estatística",
      "bio": "Análise estatística de mercado agrícola, cotações regionais e gestão de relatórios.",
      "email": "carlise@cragrostat.com.br", "telefone": "",
      "crea_cfta": "", "cidade_padrao": "São Borja - RS",
      "polo_padrao": "RS • Fronteira Oeste (São Borja / Itaqui)",
      "uf_padrao": "RS", "subregiao_padrao": "Fronteira Oeste (São Borja / Itaqui / Uruguaiana)",
      "lat_padrao": -28.66, "lon_padrao": -56.00,
      "fonte_preferida": "Chicago SRW Wheat / CBOT",
      "site_extra_usuario": "https://www.stonex.com/pt-br/inteligencia-de-mercado/",
      "voz_ia": "Feminina (Analista Agro)",
      "senha_hash": criar_hash_senha_segura(os.getenv("CR_CARLISE_SENHA_INICIAL", "Agro@2026")),
      "papel": "admin", "autorizado": True, "foto_b64": "",
      "comissao_padrao_pct": 1.5, "clientes": [], "agenda_vendas": [], "alertas_preco": [],
  }


def situacao_lembrete_cliente(lembrete, hoje=None):
  """Calcula os vencimentos do CRM sem alterar os dados salvos."""
  if lembrete.get("concluido"):
    return "Concluído", "#6EE7B7"
  hoje = hoje or datetime.now().date()
  try:
    vencimento = datetime.strptime(str(lembrete.get("data", "")), "%d/%m/%Y").date()
  except (TypeError, ValueError):
    return "Sem data válida", "#94A3B8"
  dias = (vencimento - hoje).days
  if dias < 0:
    return f"Atrasado {abs(dias)} dia(s)", "#FB7185"
  if dias == 0:
    return "Vence hoje", "#FACC15"
  if dias <= 7:
    return f"Em {dias} dia(s)", "#FACC15"
  return f"Para {vencimento.strftime('%d/%m')}", "#38BDF8"


def inicializar_banco_usuarios():
  os.makedirs(DIRETORIO_DADOS, exist_ok=True)
  if os.path.exists(ARQUIVO_USUARIOS):
    try:
      with open(ARQUIVO_USUARIOS, "r", encoding="utf-8") as f:
        db_u = json.load(f)
        if "usuarios" in db_u and "marcio" in db_u["usuarios"]:
          # Migração segura: versões antigas continham só Márcio em algumas instalações.
          # Não modificar senha, perfil nem clientes de contas já existentes.
          if "carlise" not in db_u["usuarios"]:
            db_u["usuarios"]["carlise"] = usuario_inicial_carlise()
            salvar_banco_usuarios(db_u)
          return db_u
    except Exception:
      pass

  senha_padrao_hash = criptografar_senha("Agro@2026")
  fonte_padrao_chave = "Chicago SRW Wheat / CBOT"

  db_inicial = {
      "config_supabase": {
          "ativo": False,
          "url": "",
          "anon_key": "",
          "ultimo_sync": "Modo Local Ativo (Pronto para Supabase)",
      },
      "usuarios": {
          "marcio": {
              "login": "marcio",
              "nome": "Márcio Luis Ávila da Silva",
              "cargo": "Administrador Mestre & Consultor Comercial",
              "bio": "Gestão comercial de grãos, sementes certificadas e inteligência climática na Fronteira Oeste (RS) e Brasil.",
              "email": "marcio@cragrostat.com.br",
              "telefone": "5555999999999",
              "crea_cfta": "Admin-Master-RS",
              "cidade_padrao": "São Borja - RS",
              "polo_padrao": "RS • Fronteira Oeste (São Borja / Itaqui)",
              "uf_padrao": "RS",
              "subregiao_padrao": "Fronteira Oeste (São Borja / Itaqui / Uruguaiana)",
              "lat_padrao": -28.66,
              "lon_padrao": -56.00,
              "fonte_preferida": fonte_padrao_chave,
              "site_extra_usuario": "https://www.stonex.com/pt-br/inteligencia-de-mercado/",
              "voz_ia": "Feminina (Analista Agro)",
              "senha_hash": senha_padrao_hash,
              "papel": "admin",
              "autorizado": True,
              "foto_b64": "",
              "comissao_padrao_pct": 1.5,
              "clientes": [
                  {
                      "id": "cli_1",
                      "nome": "Fazenda São João (Produtor Exemplo)",
                      "tipo": "Produtor Rural",
                      "propriedade": "Estância São João do Uruguai",
                      "cidade_uf": "São Borja - RS",
                      "cpf_cnpj": "000.000.000-00",
                      "whatsapp": "5555999887766",
                      "hectares_soja": 450,
                      "hectares_arroz": 300,
                      "hectares_inverno": 200,
                      "tem_silo": "Sim (Capacidade 30.000 sc)",
                      "endereco_escritorio": "Centro, São Borja - RS",
                      "lat_escritorio": -28.659,
                      "lon_escritorio": -56.004,
                      "roteiro_lavoura": "BR-472 km 18, entrada à esquerda 4 km",
                      "lat_lavoura": -28.725,
                      "lon_lavoura": -55.910,
                      "anos_parceria": "4 Safras Consecutivas (Desde 2022)",
                      "indice_fidelidade": "96% (Cliente Ouro — Pagamento Pontual)",
                      "total_acumulado_sacas": 4850,
                      "total_acumulado_reais": 642500.00,
                      "historico_parceria": [
                          "Safra 2023/24: 1.400 sc Soja + 180 sc Semente Certificada (R$ 198.400)",
                          "Safra 2024/25: 1.850 sc Arroz + 220 sc Semente Soja TSI (R$ 245.100)",
                          "Safra 2025/26: 1.600 sc Trigo/Soja + 3.500 kg Azevém (R$ 199.000)",
                      ],
                  },
                  {
                      "id": "cli_2",
                      "nome": "Agropecuária Fronteira & Grãos",
                      "tipo": "Escritório Agrícola / Cooperativa",
                      "propriedade": "Unidade Recebimento Itaqui / São Borja",
                      "cidade_uf": "Itaqui - RS",
                      "cpf_cnpj": "12.345.678/0001-99",
                      "whatsapp": "5555998765432",
                      "hectares_soja": 1200,
                      "hectares_arroz": 850,
                      "hectares_inverno": 500,
                      "tem_silo": "Sim (Unidade Graneleira 120.000 sc)",
                      "endereco_escritorio": "Av. Industrial, Itaqui - RS",
                      "lat_escritorio": -29.125,
                      "lon_escritorio": -56.553,
                      "roteiro_lavoura": "Acesso RS-529, Granja Santa Maria",
                      "lat_lavoura": -29.080,
                      "lon_lavoura": -56.420,
                      "anos_parceria": "6 Safras Consecutivas (Desde 2020)",
                      "indice_fidelidade": "99% (Parceiro Estratégico Regional)",
                      "total_acumulado_sacas": 12400,
                      "total_acumulado_reais": 1580000.00,
                      "historico_parceria": [
                          "Safra 2023/24: 3.800 sc Arroz Irrigado + 400 sc Sem. Arroz IRGA (R$ 490.000)",
                          "Safra 2024/25: 4.200 sc Soja Grão + 500 sc Sem. Soja (R$ 565.000)",
                          "Safra 2025/26: 4.400 sc Soja/Trigo + Forrageiras (R$ 525.000)",
                      ],
                  },
              ],
              "agenda_vendas": [
                  {
                      "id": "ag_1",
                      "data_visita": (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y"),
                      "cliente_nome": "Fazenda São João (Produtor Exemplo)",
                      "produto": "Trigo Pão",
                      "quantidade": 1000,
                      "preco_unitario": 73.00,
                      "tem_frete": "Com Frete (CIF)",
                      "km_frete": 85,
                      "custo_frete_saca": 2.20,
                      "preco_liquido_saca": 70.80,
                      "valor_total_liquido": 70800.00,
                      "comissao_pct": 1.5,
                      "comissao_reais": 1062.00,
                      "status": "Em Negociação",
                      "obs": "Cotação dinâmica atual na faixa de R$ 73,00/sc na Fronteira Oeste.",
                  }
              ],
              "alertas_preco": [
                  {
                      "id": "al_1",
                      "cliente_nome": "Fazenda São João (Produtor Exemplo)",
                      "whatsapp": "5555999887766",
                      "produto": "Soja em Grão",
                      "uf": "RS",
                      "tipo_gatilho": "Alta (Venda de Grão >= Alvo)",
                      "valor_alvo": 134.50,
                      "lote_sacas": 1000,
                      "criado_em": agora_str(),
                  }
              ],
          },
          "carlise": {
              "login": "carlise",
              "nome": "Carlise da Rosa",
              "cargo": "Administradora & Inteligência Estatística",
              "bio": "Análise estatística de mercado agrícola, cotações regionais e gestão de relatórios.",
              "email": "carlise@cragrostat.com.br",
              "telefone": "5555999999998",
              "crea_cfta": "Admin-CR-RS",
              "cidade_padrao": "São Borja - RS",
              "polo_padrao": "RS • Fronteira Oeste (São Borja / Itaqui)",
              "uf_padrao": "RS",
              "subregiao_padrao": "Fronteira Oeste (São Borja / Itaqui / Uruguaiana)",
              "lat_padrao": -28.66,
              "lon_padrao": -56.00,
              "fonte_preferida": fonte_padrao_chave,
              "site_extra_usuario": "https://www.stonex.com/pt-br/inteligencia-de-mercado/",
              "voz_ia": "Feminina (Analista Agro)",
              "senha_hash": senha_padrao_hash,
              "papel": "admin",
              "autorizado": True,
              "foto_b64": "",
              "comissao_padrao_pct": 1.5,
              "clientes": [],
              "agenda_vendas": [],
              "alertas_preco": [],
          },
      },
  }
  salvar_banco_usuarios(db_inicial)
  return db_inicial


def salvar_banco_usuarios(db_u):
  os.makedirs(DIRETORIO_DADOS, exist_ok=True)
  salvar_json_atomico(ARQUIVO_USUARIOS, db_u)


# =============================================================================
# POLOS CLIMÁTICOS E COORDENADAS NO MAPA GEOGRÁFICO DO BRASIL
# =============================================================================
POLOS_CLIMA_BRASIL = {
    "RS • Fronteira Oeste (São Borja / Itaqui)": {
        "regiao": "Sul",
        "uf": "RS",
        "lat": -28.66,
        "lon": -56.00,
        "mapa_x": 270,
        "mapa_y": 505,
        "estacao_inmet": "Estação Automática São Borja (A830) + Satélite ECMWF/GFS",
        "perfil": "Polo Arroz Irrigado, Soja, Trigo e Sementes Forrageiras",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 680, "2024": 510, "2025": 465, "2026_est": 490, "media_hist": 480},
            "Verão (Dez-Fev)": {"2023": 290, "2024": 495, "2025": 380, "2026_est": 430, "media_hist": 420},
            "Outono (Mar-Mai)": {"2023": 410, "2024": 640, "2025": 440, "2026_est": 460, "media_hist": 450},
            "Inverno (Jun-Ago)": {"2023": 360, "2024": 390, "2025": 340, "2026_est": 355, "media_hist": 350},
        },
    },
    "RS • Planalto e Noroeste (Passo Fundo / Ijuí)": {
        "regiao": "Sul",
        "uf": "RS",
        "lat": -28.26,
        "lon": -52.40,
        "mapa_x": 335,
        "mapa_y": 488,
        "estacao_inmet": "Estação Passo Fundo / Embrapa Trigo + Satélite ECMWF/GFS",
        "perfil": "Polo Soja, Trigo, Milho e Sementes Certificadas",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 720, "2024": 540, "2025": 495, "2026_est": 520, "media_hist": 510},
            "Verão (Dez-Fev)": {"2023": 310, "2024": 520, "2025": 410, "2026_est": 465, "media_hist": 460},
            "Outono (Mar-Mai)": {"2023": 395, "2024": 690, "2025": 430, "2026_est": 445, "media_hist": 440},
            "Inverno (Jun-Ago)": {"2023": 420, "2024": 450, "2025": 390, "2026_est": 415, "media_hist": 410},
        },
    },
    "SC • Oeste e Planalto (Chapecó / Campos Novos)": {
        "regiao": "Sul",
        "uf": "SC",
        "lat": -27.10,
        "lon": -52.61,
        "mapa_x": 350,
        "mapa_y": 455,
        "estacao_inmet": "Epagri/Ciram Chapecó & Campos Novos + ECMWF/GFS",
        "perfil": "Polo Milho, Soja, Sementes de Altitude e Proteína Animal",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 740, "2024": 560, "2025": 520, "2026_est": 545, "media_hist": 535},
            "Verão (Dez-Fev)": {"2023": 420, "2024": 530, "2025": 470, "2026_est": 505, "media_hist": 495},
            "Outono (Mar-Mai)": {"2023": 380, "2024": 550, "2025": 435, "2026_est": 455, "media_hist": 450},
            "Inverno (Jun-Ago)": {"2023": 395, "2024": 410, "2025": 375, "2026_est": 395, "media_hist": 390},
        },
    },
    "PR • Oeste e Campos Gerais (Cascavel / Ponta Grossa)": {
        "regiao": "Sul",
        "uf": "PR",
        "lat": -24.95,
        "lon": -53.45,
        "mapa_x": 325,
        "mapa_y": 418,
        "estacao_inmet": "Simepar / INMET Cascavel & Ponta Grossa + NOAA GFS",
        "perfil": "Polo Soja 1ª Safra, Milho Safrinha, Trigo e Sementes",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 590, "2024": 530, "2025": 505, "2026_est": 525, "media_hist": 520},
            "Verão (Dez-Fev)": {"2023": 480, "2024": 540, "2025": 510, "2026_est": 535, "media_hist": 530},
            "Outono (Mar-Mai)": {"2023": 390, "2024": 430, "2025": 405, "2026_est": 420, "media_hist": 415},
            "Inverno (Jun-Ago)": {"2023": 290, "2024": 270, "2025": 285, "2026_est": 295, "media_hist": 290},
        },
    },
    "MT • Norte e Médio-Norte (Sorriso / Sinop / Rondonópolis)": {
        "regiao": "Centro-Oeste",
        "uf": "MT",
        "lat": -12.54,
        "lon": -55.72,
        "mapa_x": 255,
        "mapa_y": 248,
        "estacao_inmet": "INMET Sorriso / IMEA-MT + Satélite ECMWF/GFS",
        "perfil": "Maior Polo Nacional de Soja e Milho 2ª Safra",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 460, "2024": 540, "2025": 560, "2026_est": 550, "media_hist": 545},
            "Verão (Dez-Fev)": {"2023": 820, "2024": 890, "2025": 910, "2026_est": 900, "media_hist": 895},
            "Outono (Mar-Mai)": {"2023": 380, "2024": 410, "2025": 425, "2026_est": 415, "media_hist": 410},
            "Inverno (Jun-Ago)": {"2023": 25, "2024": 30, "2025": 28, "2026_est": 30, "media_hist": 30},
        },
    },
    "MS & GO • Sul MS e Sudoeste GO (Dourados / Rio Verde)": {
        "regiao": "Centro-Oeste",
        "uf": "GO",
        "lat": -17.79,
        "lon": -50.92,
        "mapa_x": 310,
        "mapa_y": 332,
        "estacao_inmet": "INMET Rio Verde & Dourados + Satélite Open-Meteo",
        "perfil": "Polo Agroindustrial Soja, Milho Safrinha e Sorgo",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 420, "2024": 480, "2025": 490, "2026_est": 485, "media_hist": 480},
            "Verão (Dez-Fev)": {"2023": 690, "2024": 740, "2025": 755, "2026_est": 750, "media_hist": 745},
            "Outono (Mar-Mai)": {"2023": 290, "2024": 320, "2025": 310, "2026_est": 315, "media_hist": 310},
            "Inverno (Jun-Ago)": {"2023": 45, "2024": 50, "2025": 48, "2026_est": 50, "media_hist": 50},
        },
    },
    "SP & MG • Sudeste (Uberaba / Ribeirão Preto / Santos)": {
        "regiao": "Sudeste",
        "uf": "SP",
        "lat": -19.74,
        "lon": -47.93,
        "mapa_x": 405,
        "mapa_y": 362,
        "estacao_inmet": "INMET Triângulo Mineiro & Interior SP + ECMWF",
        "perfil": "Polo Grãos, Sementes, Café, Cana e Corredor Exportação Santos",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 390, "2024": 450, "2025": 440, "2026_est": 445, "media_hist": 440},
            "Verão (Dez-Fev)": {"2023": 680, "2024": 720, "2025": 710, "2026_est": 715, "media_hist": 710},
            "Outono (Mar-Mai)": {"2023": 240, "2024": 260, "2025": 255, "2026_est": 260, "media_hist": 255},
            "Inverno (Jun-Ago)": {"2023": 40, "2024": 35, "2025": 38, "2026_est": 40, "media_hist": 40},
        },
    },
    "MATOPIBA • Nordeste (Luís Eduardo Magalhães-BA / Balsas-MA)": {
        "regiao": "Nordeste (MATOPIBA)",
        "uf": "BA",
        "lat": -12.09,
        "lon": -45.79,
        "mapa_x": 430,
        "mapa_y": 215,
        "estacao_inmet": "INMET Oeste da Bahia & Balsas + Satélite NOAA GFS",
        "perfil": "Fronteira Agrícola de Alta Produtividade em Soja, Milho e Algodão",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 310, "2024": 370, "2025": 385, "2026_est": 380, "media_hist": 375},
            "Verão (Dez-Fev)": {"2023": 620, "2024": 680, "2025": 690, "2026_est": 685, "media_hist": 680},
            "Outono (Mar-Mai)": {"2023": 310, "2024": 340, "2025": 350, "2026_est": 345, "media_hist": 340},
            "Inverno (Jun-Ago)": {"2023": 10, "2024": 12, "2025": 10, "2026_est": 12, "media_hist": 12},
        },
    },
    "Norte • Fronteira Amazônica (Vilhena-RO / Santarém & Paragominas-PA)": {
        "regiao": "Norte",
        "uf": "PA",
        "lat": -12.74,
        "lon": -60.14,
        "mapa_x": 195,
        "mapa_y": 145,
        "estacao_inmet": "INMET Vilhena & Paragominas + Arco Norte Barcarena",
        "perfil": "Expansão de Soja, Milho, Arroz e Escoamento pelo Arco Norte",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 520, "2024": 580, "2025": 590, "2026_est": 585, "media_hist": 580},
            "Verão (Dez-Fev)": {"2023": 890, "2024": 940, "2025": 950, "2026_est": 945, "media_hist": 940},
            "Outono (Mar-Mai)": {"2023": 490, "2024": 520, "2025": 530, "2026_est": 525, "media_hist": 520},
            "Inverno (Jun-Ago)": {"2023": 55, "2024": 60, "2025": 58, "2026_est": 60, "media_hist": 60},
        },
    },
}


def buscar_previsao_tempo_openmeteo(nome_polo):
  info_p = POLOS_CLIMA_BRASIL.get(nome_polo, list(POLOS_CLIMA_BRASIL.values())[0])
  lat, lon = info_p["lat"], info_p["lon"]
  previsao_dias = []
  horario_consulta = agora_str()
  modo_coleta = "Satélite Ao Vivo — API Open-Meteo (ECMWF + NOAA GFS)"

  try:
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max"
        "&timezone=America%2FSao_Paulo&forecast_days=14"
    )
    resp = requests.get(url, timeout=5)
    if resp.status_code == 200:
      d = resp.json().get("daily", {})
      datas = d.get("time", [])
      tmax = d.get("temperature_2m_max", [])
      tmin = d.get("temperature_2m_min", [])
      chuva = d.get("precipitation_sum", [])
      prob = d.get("precipitation_probability_max", [])

      for i in range(len(datas)):
        dt_fmt = datetime.strptime(datas[i], "%Y-%m-%d").strftime("%d/%m")
        previsao_dias.append({
            "data": dt_fmt,
            "data_completa": datetime.strptime(datas[i], "%Y-%m-%d").strftime("%d/%m/%Y"),
            "chuva_mm": round(float(chuva[i] or 0.0), 1),
            "prob": int(prob[i] or 0),
            "tmin": round(float(tmin[i] or 15.0), 1),
            "tmax": round(float(tmax[i] or 26.0), 1),
        })
  except Exception:
    pass

  if not previsao_dias:
    modo_coleta = "Base Climatológica de Contingência (ECMWF/ERA5)"
    hoje = datetime.now()
    padrao_mm = [0.0, 4.5, 18.2, 6.0, 0.0, 0.0, 12.4, 22.0, 3.5, 0.0, 8.0, 15.0, 2.0, 0.0]
    padrao_pr = [10, 55, 85, 60, 15, 10, 75, 90, 45, 15, 65, 80, 30, 10]
    for i in range(14):
      dt_obj = hoje + timedelta(days=i)
      previsao_dias.append({
          "data": dt_obj.strftime("%d/%m"),
          "data_completa": dt_obj.strftime("%d/%m/%Y"),
          "chuva_mm": padrao_mm[i],
          "prob": padrao_pr[i],
          "tmin": round(16.0 + math.sin(i) * 2.5, 1),
          "tmax": round(27.5 + math.cos(i) * 3.0, 1),
      })

  est_estacoes = list(info_p["historico_estacoes"].values())[0]
  media_diaria_est = round(est_estacoes["2026_est"] / 90.0, 1)
  serie_futura_clima = [
      {"data": "+15 Dias", "data_completa": "Acumulado Próximos 15 Dias", "chuva_mm": round(sum(d["chuva_mm"] for d in previsao_dias[:10]) + media_diaria_est * 5, 1), "prob": 70, "tmin": 17.0, "tmax": 28.0},
      {"data": "+30 Dias", "data_completa": "Estimativa Acumulada 30 Dias", "chuva_mm": round(est_estacoes["2026_est"] * 0.34, 1), "prob": 75, "tmin": 18.0, "tmax": 29.0},
      {"data": "+60 Dias", "data_completa": "Estimativa Acumulada 60 Dias", "chuva_mm": round(est_estacoes["2026_est"] * 0.67, 1), "prob": 75, "tmin": 18.5, "tmax": 29.5},
      {"data": "+90 Dias", "data_completa": "Estimativa Trimestral Safra (90d)", "chuva_mm": float(est_estacoes["2026_est"]), "prob": 80, "tmin": 19.0, "tmax": 30.0},
  ]

  return previsao_dias, serie_futura_clima, horario_consulta, modo_coleta


# =============================================================================
# ITENS DE MERCADO COM TRIGO CALIBRADO (~R$ 73,00 MAS DINÂMICO) + STONEX & CBOT
# =============================================================================
ITENS_PADRAO = [
    {
        "id": "trigo_grao",
        "nome": "Trigo Pão (Chicago SRW & StoneX)",
        "nome_curto": "Trigo Pão",
        "nome_bolsa": "Chicago SRW Wheat Futures",
        "codigo_cbot": "CBOT: ZWW00",
        "sigla": "TRIGO",
        "categoria": "Grãos",
        "unidade": "Saca 60kg",
        "ticker": "ZW=F",
        "usx_padrao": 611.00,
        "abertura_padrao": 616.75,
        "alta_padrao": 618.50,
        "baixa_padrao": 609.75,
        "fech_ant_padrao": 616.00,
        "volume_padrao": "65.762",
        "contratos_abertos": "242.409",
        "fonte_oficial": (
            "Chicago SRW Wheat Futures (CBOT: ZWW00) + StoneX Inteligência Agro +"
            " Emater/IRGA-RS + CEPEA/Esalq"
        ),
        "nota_stonex": (
            "Relatório StoneX & Físico: Trigo no RS acompanha paridade de"
            " importação e compras dos moinhos na faixa de R$ 73,00/sc, oscilando"
            " diariamente com o contrato ZWW00 em Chicago e o Dólar."
        ),
        "url_fonte": "https://www.google.com/finance/quote/ZWW00:CBOT",
        "preco_base": 73.00,  # Referência dinâmica calibrada que oscila ao vivo com CBOT/Câmbio
        "contrato_empresa": 72.00,
        "cor": "#F59E0B",
        "icone": "BAKERY_DINING_ROUNDED",
        "sazonalidade": (
            "Paridade física calibrada na faixa de R$ 73,00/sc no RS com"
            " oscilação em tempo real via Chicago SRW Wheat (CBOT: ZWW00) e StoneX."
        ),
        "fatores_oscilacao": [
            "Oscilação intradiária do Chicago SRW Wheat Futures (CBOT: ZWW00) e Dólar PTAX.",
            "Boletins de oferta/demanda da StoneX e paridade do trigo argentino.",
            "Qualidade de PH e força de glúten W nos moinhos do RS, SC e PR.",
        ],
        "regioes_sul": {
            "RS": {
                "Fronteira Oeste (São Borja / Itaqui / Uruguaiana)": 73.00,
                "Missões (Santo Ângelo / São Luiz Gonzaga / Giruá)": 72.60,
                "Planalto e Noroeste (Passo Fundo / Ijuí / Cruz Alta)": 73.90,
                "Zona Sul e Porto (Pelotas / Rio Grande / Camaquã)": 76.20,
            },
            "SC": {
                "Oeste Catarinense (Chapecó / Xanxerê / Concórdia)": 74.50,
                "Meio-Oeste e Planalto (Campos Novos / Lages / Joaçaba)": 75.00,
            },
            "PR": {
                "Oeste Paranaense (Cascavel / Toledo / Marechal Rondon)": 75.80,
                "Campos Gerais (Ponta Grossa / Castro / Carambeí)": 76.90,
            },
            "CO": {"Sudoeste Goiano e Sul MS (Rio Verde / Dourados)": 75.50},
            "SE": {"Sudoeste Paulista e Triângulo Mineiro": 79.20},
            "NE": {"Oeste da Bahia (Trigo Irrigado Cerrado)": 81.00},
            "NO": {"Polos Portuários Norte": 83.50},
        },
    },
    {
        "id": "soja_grao",
        "nome": "Soja em Grão (CBOT & StoneX)",
        "nome_curto": "Soja em Grão",
        "nome_bolsa": "Chicago Soybean Futures",
        "codigo_cbot": "CBOT: ZS=F",
        "sigla": "SOJA",
        "categoria": "Grãos",
        "unidade": "Saca 60kg",
        "ticker": "ZS=F",
        "usx_padrao": 1028.50,
        "abertura_padrao": 1032.00,
        "alta_padrao": 1039.25,
        "baixa_padrao": 1021.00,
        "fech_ant_padrao": 1031.50,
        "volume_padrao": "142.890",
        "contratos_abertos": "389.120",
        "fonte_oficial": (
            "Chicago Soybean Futures (CBOT: ZS=F) + StoneX Brasil + CEPEA/Esalq"
            " + Emater-RS"
        ),
        "nota_stonex": (
            "Relatório StoneX: Comercialização da safra de soja segue atenta"
            " aos prêmios nos portos de Rio Grande, Paranaguá e Santos e à"
            " demanda de exportação."
        ),
        "url_fonte": "https://www.google.com/finance/quote/ZS=F",
        "preco_base": 134.24,
        "contrato_empresa": 132.00,
        "cor": "#10B981",
        "icone": "GRAIN_ROUNDED",
        "sazonalidade": (
            "Monitoramento de chuvas no Sul e Cerrado, prêmios portuários e"
            " curva Chicago ZS=F."
        ),
        "fatores_oscilacao": [
            "Oscilação diária na CBOT Chicago (ZS=F) e Dólar Comercial Spot.",
            "Estimativas de safra da StoneX, USDA e CONAB.",
        ],
        "regioes_sul": {
            "RS": {
                "Fronteira Oeste (São Borja / Itaqui / Uruguaiana)": 134.24,
                "Planalto e Noroeste (Passo Fundo / Ijuí / Cruz Alta)": 135.50,
                "Zona Sul e Porto (Pelotas / Rio Grande / Camaquã)": 138.80,
            },
            "SC": {"Oeste Catarinense (Chapecó / Xanxerê / Concórdia)": 136.20},
            "PR": {"Oeste Paranaense (Cascavel / Toledo / Marechal Rondon)": 135.40},
            "CO": {"Médio-Norte MT e Sudoeste GO (Sorriso / Rio Verde)": 124.80},
            "SE": {"Interior Paulista e Triângulo Mineiro": 135.80},
            "NE": {"Oeste da Bahia e Balsas (MATOPIBA)": 126.90},
            "NO": {"Cone Sul RO e Santarém/Barcarena PA": 125.20},
        },
    },
    {
        "id": "arroz_casca",
        "nome": "Arroz em Casca (IRGA/CEPEA & CBOT)",
        "nome_curto": "Arroz em Casca",
        "nome_bolsa": "Chicago Rough Rice Futures",
        "codigo_cbot": "CBOT: ZR=F",
        "sigla": "ARROZ",
        "categoria": "Grãos",
        "unidade": "Saca 50kg",
        "ticker": "ZR=F",
        "usx_padrao": 1512.00,
        "abertura_padrao": 1518.00,
        "alta_padrao": 1525.50,
        "baixa_padrao": 1504.00,
        "fech_ant_padrao": 1516.50,
        "volume_padrao": "18.420",
        "contratos_abertos": "44.810",
        "fonte_oficial": (
            "Indicador Esalq/CEPEA-IRGA RS + Chicago Rough Rice (CBOT: ZR=F) +"
            " StoneX"
        ),
        "nota_stonex": (
            "Análise de Mercado: Fronteira Oeste do RS (São Borja/Itaqui) mantém"
            " liderança na oferta de arroz irrigado com suporte na indústria."
        ),
        "url_fonte": "https://www.cepea.esalq.usp.br/br/indicador/arroz.aspx",
        "preco_base": 115.80,
        "contrato_empresa": 114.00,
        "cor": "#0EA5E9",
        "icone": "GRASS_ROUNDED",
        "sazonalidade": "Fronteira Oeste do RS e Sul de SC concentram a produção nacional.",
        "fatores_oscilacao": ["Compras da indústria e paridade Mercosul."],
        "regioes_sul": {
            "RS": {"Fronteira Oeste (São Borja / Itaqui / Uruguaiana)": 115.80},
            "SC": {"Sul Catarinense (Turvo / Araranguá / Tubarão)": 117.00},
            "PR": {"Noroeste e Atacado Curitiba": 119.20},
            "CO": {"Várzeas de GO e MT": 113.80},
            "SE": {"Centros Distribuidores SP/MG": 123.00},
            "NE": {"Polo Irrigado Lagoa da Confusão-TO": 114.50},
            "NO": {"Lavrados de Roraima e Sul do PA": 113.90},
        },
    },
    {
        "id": "milho_grao",
        "nome": "Milho em Grão (CBOT, B3 & StoneX)",
        "nome_curto": "Milho em Grão",
        "nome_bolsa": "Chicago Corn Futures",
        "codigo_cbot": "CBOT: ZC=F",
        "sigla": "MILHO",
        "categoria": "Grãos",
        "unidade": "Saca 60kg",
        "ticker": "ZC=F",
        "usx_padrao": 418.25,
        "abertura_padrao": 420.00,
        "alta_padrao": 423.50,
        "baixa_padrao": 415.75,
        "fech_ant_padrao": 419.50,
        "volume_padrao": "215.640",
        "contratos_abertos": "512.300",
        "fonte_oficial": (
            "Chicago Corn Futures (CBOT: ZC=F) + StoneX + B3/CEPEA + Epagri-SC"
        ),
        "nota_stonex": (
            "Relatório StoneX Milho: Demanda firme das integradoras de proteína"
            " animal no Sul e das usinas de etanol de milho no Centro-Oeste."
        ),
        "url_fonte": "https://www.cepea.esalq.usp.br/br/indicador/milho.aspx",
        "preco_base": 68.50,
        "contrato_empresa": 67.00,
        "cor": "#EAB308",
        "icone": "AGRICULTURE_ROUNDED",
        "sazonalidade": "Forte consumo regional de ração em SC, PR e RS.",
        "fatores_oscilacao": ["Safrinha nacional, etanol de milho e exportações."],
        "regioes_sul": {
            "RS": {"Fronteira Oeste (São Borja / Itaqui / Uruguaiana)": 68.50},
            "SC": {"Oeste Catarinense (Chapecó / Xanxerê / Concórdia)": 73.20},
            "PR": {"Oeste Paranaense (Cascavel / Toledo / Marechal Rondon)": 68.00},
            "CO": {"Sorriso-MT / Dourados-MS / Rio Verde-GO": 58.20},
            "SE": {"Campinas-SP / Uberaba-MG": 69.50},
            "NE": {"Oeste da Bahia e Balsas-MA": 64.50},
            "NO": {"Vilhena-RO / Santarém-PA": 59.50},
        },
    },
    {
        "id": "semente_soja",
        "nome": "Semente de Soja Certificada",
        "nome_curto": "Semente Soja",
        "nome_bolsa": "Indexador Semente Soja / CBOT",
        "codigo_cbot": "CBOT: ZS=F / TSI",
        "sigla": "SEM. SOJA",
        "categoria": "Sementes",
        "unidade": "Saca 40kg",
        "ticker": "ZS=F",
        "usx_padrao": 1028.50,
        "abertura_padrao": 1032.00,
        "alta_padrao": 1039.25,
        "baixa_padrao": 1021.00,
        "fech_ant_padrao": 1031.50,
        "volume_padrao": "42.100",
        "contratos_abertos": "98.400",
        "fonte_oficial": "Indexador Soja CBOT (ZS=F) + Apassul-RS / Aprossul / Abrates",
        "nota_stonex": "Sementes de alto vigor com tratamento industrial (TSI) acompanham o indexador da soja comercial.",
        "url_fonte": "https://www.conab.gov.br/",
        "preco_base": 291.00,
        "contrato_empresa": 288.00,
        "cor": "#22C55E",
        "icone": "SPA_ROUNDED",
        "sazonalidade": "Alta procura na janela de plantio.",
        "fatores_oscilacao": ["Vigor, germinação, royalties e TSI."],
        "regioes_sul": {
            "RS": {"Fronteira Oeste (São Borja / Itaqui / Uruguaiana)": 291.00},
            "SC": {"Meio-Oeste e Planalto (Campos Novos / Lages / Joaçaba)": 289.50},
            "PR": {"Campos Gerais (Ponta Grossa / Castro / Carambeí)": 292.00},
            "CO": {"Primavera do Leste-MT / Cristalina-GO": 298.00},
            "SE": {"Uberaba-MG / Interior SP": 296.00},
            "NE": {"Luís Eduardo Magalhães-BA / Balsas-MA": 302.00},
            "NO": {"Vilhena-RO / Paragominas-PA": 305.00},
        },
    },
    {
        "id": "semente_arroz",
        "nome": "Semente de Arroz Certificada",
        "nome_curto": "Semente Arroz",
        "nome_bolsa": "Indexador Semente Arroz IRGA / CBOT",
        "codigo_cbot": "CBOT: ZR=F / IRGA",
        "sigla": "SEM. ARROZ",
        "categoria": "Sementes",
        "unidade": "Saca 40kg",
        "ticker": "ZR=F",
        "usx_padrao": 1512.00,
        "abertura_padrao": 1518.00,
        "alta_padrao": 1525.50,
        "baixa_padrao": 1504.00,
        "fech_ant_padrao": 1516.50,
        "volume_padrao": "15.300",
        "contratos_abertos": "31.200",
        "fonte_oficial": "Referência IRGA (RS) / Epagri (SC) + CBOT (ZR=F)",
        "nota_stonex": "Cultivares certificadas IRGA e Epagri garantem produtividade e controle de invasoras.",
        "url_fonte": "https://irga.rs.gov.br/",
        "preco_base": 208.00,
        "contrato_empresa": 205.00,
        "cor": "#06B6D4",
        "icone": "ECO_ROUNDED",
        "sazonalidade": "Implantação das lavouras irrigadas no RS, SC e TO.",
        "fatores_oscilacao": ["Pureza genética e relação de troca Barter."],
        "regioes_sul": {
            "RS": {"Fronteira Oeste (São Borja / Itaqui / Uruguaiana)": 208.00},
            "SC": {"Sul Catarinense (Turvo / Araranguá / Tubarão)": 214.00},
            "PR": {"Noroeste Paranaense": 218.00},
            "CO": {"Várzeas Irrigadas MT/GO": 216.00},
            "SE": {"Vale do Paraíba-SP": 220.00},
            "NE": {"Lagoa da Confusão-TO": 215.00},
            "NO": {"Boa Vista-RR": 219.00},
        },
    },
    {
        "id": "semente_azevem",
        "nome": "Semente de Azevém",
        "nome_curto": "Semente Azevém",
        "nome_bolsa": "Indexador Forrageiras Sul / CBOT",
        "codigo_cbot": "FORR: AZV-SUL",
        "sigla": "AZEVÉM",
        "categoria": "Sementes",
        "unidade": "Quilo (kg)",
        "ticker": "ZC=F",
        "usx_padrao": 418.25,
        "abertura_padrao": 420.00,
        "alta_padrao": 423.50,
        "baixa_padrao": 415.75,
        "fech_ant_padrao": 419.50,
        "volume_padrao": "12.800",
        "contratos_abertos": "28.900",
        "fonte_oficial": "Sementeiras Forrageiras Sul (RS/SC/PR) + Emater/Deral",
        "nota_stonex": "Demanda aquecida para pastagens de inverno e integração lavoura-pecuária (ILP).",
        "url_fonte": "https://www.emater.tche.br/",
        "preco_base": 6.75,
        "contrato_empresa": 6.50,
        "cor": "#84CC16",
        "icone": "PARK_ROUNDED",
        "sazonalidade": "Pecuária de corte e leite no Sul.",
        "fatores_oscilacao": ["Chuvas de outono e arroba do boi gordo."],
        "regioes_sul": {
            "RS": {"Fronteira Oeste (São Borja / Itaqui / Uruguaiana)": 6.75},
            "SC": {"Oeste e Serra Catarinense": 7.15},
            "PR": {"Campos Gerais e Sudoeste": 7.35},
            "CO": {"Sul do MS (ILP)": 7.60},
            "SE": {"Bacias Leiteiras SP/MG": 7.80},
            "NE": {"Regiões de Altitude BA": 8.10},
            "NO": {"Cone Sul RO": 8.20},
        },
    },
    {
        "id": "semente_aveia",
        "nome": "Semente de Aveia Preta",
        "nome_curto": "Semente Aveia",
        "nome_bolsa": "Chicago Oats / Cereais Inverno",
        "codigo_cbot": "CBOT: ZO=F / AVP",
        "sigla": "AVEIA",
        "categoria": "Sementes",
        "unidade": "Quilo (kg)",
        "ticker": "ZW=F",
        "usx_padrao": 611.00,
        "abertura_padrao": 616.75,
        "alta_padrao": 618.50,
        "baixa_padrao": 609.75,
        "fech_ant_padrao": 616.00,
        "volume_padrao": "19.500",
        "contratos_abertos": "41.200",
        "fonte_oficial": "Sementeiras de Inverno (RS/SC/PR/MS) + Chicago SRW (ZW=F)",
        "nota_stonex": "Cobertura essencial para formação de palhada no plantio direto.",
        "url_fonte": "https://www.agricultura.pr.gov.br/Pagina/Deral",
        "preco_base": 3.95,
        "contrato_empresa": 3.75,
        "cor": "#A3E635",
        "icone": "LOCAL_FLORIST_ROUNDED",
        "sazonalidade": "Cobertura de solo e pastejo hibernal.",
        "fatores_oscilacao": ["Demanda de plantio direto e frete."],
        "regioes_sul": {
            "RS": {"Fronteira Oeste (São Borja / Itaqui / Uruguaiana)": 3.95},
            "SC": {"Oeste e Planalto SC": 4.10},
            "PR": {"Oeste e Campos Gerais PR": 3.90},
            "CO": {"Dourados-MS / Rio Verde-GO": 4.35},
            "SE": {"Assis-SP / Uberaba-MG": 4.45},
            "NE": {"Oeste da Bahia": 4.70},
            "NO": {"Vilhena-RO": 4.80},
        },
    },
]


def obter_icone_flet(nome_str):
  mapa = {
      "GRAIN_ROUNDED": ft.icons.GRAIN_ROUNDED,
      "GRASS_ROUNDED": ft.icons.GRASS_ROUNDED,
      "AGRICULTURE_ROUNDED": ft.icons.AGRICULTURE_ROUNDED,
      "BAKERY_DINING_ROUNDED": ft.icons.BAKERY_DINING_ROUNDED,
      "SPA_ROUNDED": ft.icons.SPA_ROUNDED,
      "ECO_ROUNDED": ft.icons.ECO_ROUNDED,
      "PARK_ROUNDED": ft.icons.PARK_ROUNDED,
      "LOCAL_FLORIST_ROUNDED": ft.icons.LOCAL_FLORIST_ROUNDED,
  }
  return mapa.get(str(nome_str), ft.icons.SPA_ROUNDED)


def calcular_medias_estados(regioes_dict):
  medias = {}
  todos_valores = []
  chaves = ["RS", "SC", "PR", "CO", "SE", "NE", "NO"]
  for k in chaves:
    vals = list(regioes_dict.get(k, {}).values())
    if vals:
      medias[k] = round(sum(vals) / len(vals), 2)
      todos_valores.extend(vals)
    else:
      medias[k] = 0.0
  vals_sul = [
      v
      for uf in ["RS", "SC", "PR"]
      for v in regioes_dict.get(uf, {}).values()
  ]
  medias["SUL"] = round(sum(vals_sul) / len(vals_sul), 2) if vals_sul else 0.0
  medias["BR"] = (
      round(sum(todos_valores) / len(todos_valores), 2)
      if todos_valores
      else 0.0
  )
  return medias


def gerar_series_com_datas_reais(
    preco_atual, var_dia, historico_bolsa, prev_15, prev_30, prev_60, prev_90
):
  """Gera a curva de oscilação diária (intradia hora a hora) e o histórico de 60 dias dinâmico."""
  hoje = datetime.now()
  fator_v = var_dia / 100.0
  abertura = round(preco_atual / (1 + fator_v * 0.85), 2)

  # Curva de Oscilação Diária Atualizada (8 horários do pregão)
  serie_diaria = [
      {"rotulo": "03:00", "data_completa": hoje.strftime("%d/%m/%Y 03:00 (Sessão Noturna CBOT)"), "valor": round(abertura * 1.002, 2)},
      {"rotulo": "06:00", "data_completa": hoje.strftime("%d/%m/%Y 06:00 (Pré-Abertura)"), "valor": round(abertura * 1.005, 2)},
      {"rotulo": "09:00", "data_completa": hoje.strftime("%d/%m/%Y 09:00 (Abertura Físico/B3)"), "valor": abertura},
      {"rotulo": "10:30", "data_completa": hoje.strftime("%d/%m/%Y 10:30 (Pregão Manhã)"), "valor": round(abertura * 0.65 + preco_atual * 0.35, 2)},
      {"rotulo": "12:00", "data_completa": hoje.strftime("%d/%m/%Y 12:00 (Boletim StoneX/CEPEA)"), "valor": round(abertura * 0.45 + preco_atual * 0.55, 2)},
      {"rotulo": "13:30", "data_completa": hoje.strftime("%d/%m/%Y 13:30 (Oscilação Chicago)"), "valor": round(preco_atual * 0.996, 2)},
      {"rotulo": "15:30", "data_completa": hoje.strftime("%d/%m/%Y 15:30 (Fechamento Parcial)"), "valor": round(preco_atual * 1.001, 2)},
      {"rotulo": "Agora", "data_completa": hoje.strftime("%d/%m/%Y Cotação Dinâmica Atual"), "valor": preco_atual},
  ]

  historico_60d = []
  n_dias = 60
  if historico_bolsa and len(historico_bolsa) >= 10:
    ult_b = historico_bolsa[-1][1] if historico_bolsa[-1][1] > 0 else 1.0
    for idx in range(n_dias):
      dt_dia = hoje - timedelta(days=(n_dias - 1 - idx))
      pos_b = int((idx / max(1, n_dias - 1)) * (len(historico_bolsa) - 1))
      val_b = historico_bolsa[pos_b][1]
      fator = val_b / ult_b if ult_b > 0 else 1.0
      oscilacao_suave = math.sin(idx * 0.45) * 0.004
      val_calc = round(preco_atual * (0.65 + 0.35 * fator + oscilacao_suave), 2)
      if idx == n_dias - 1:
        val_calc = preco_atual
      historico_60d.append({
          "rotulo": dt_dia.strftime("%d/%m"),
          "data_completa": dt_dia.strftime("%d/%m/%Y"),
          "valor": val_calc,
      })
  else:
    for idx in range(n_dias):
      dt_dia = hoje - timedelta(days=(n_dias - 1 - idx))
      onda = math.sin(idx * 0.35) * 0.018 + math.cos(idx * 0.2) * 0.01
      val_calc = round(preco_atual * (0.985 + onda), 2)
      if idx == n_dias - 1:
        val_calc = preco_atual
      historico_60d.append({
          "rotulo": dt_dia.strftime("%d/%m"),
          "data_completa": dt_dia.strftime("%d/%m/%Y"),
          "valor": val_calc,
      })

  dt_15 = (hoje + timedelta(days=15)).strftime("%d/%m")
  dt_30 = (hoje + timedelta(days=30)).strftime("%d/%m")
  dt_60 = (hoje + timedelta(days=60)).strftime("%d/%m")
  dt_90 = (hoje + timedelta(days=90)).strftime("%d/%m")

  serie_90d = [
      {"rotulo": f"Hoje ({hoje.strftime('%d/%m')})", "data_completa": hoje.strftime("%d/%m/%Y"), "valor": preco_atual},
      {"rotulo": f"+15d ({dt_15})", "data_completa": (hoje + timedelta(days=15)).strftime("%d/%m/%Y"), "valor": prev_15},
      {"rotulo": f"+30d ({dt_30})", "data_completa": (hoje + timedelta(days=30)).strftime("%d/%m/%Y"), "valor": prev_30},
      {"rotulo": f"+60d ({dt_60})", "data_completa": (hoje + timedelta(days=60)).strftime("%d/%m/%Y"), "valor": prev_60},
      {"rotulo": f"+90d ({dt_90})", "data_completa": (hoje + timedelta(days=90)).strftime("%d/%m/%Y"), "valor": prev_90},
  ]

  return {"diario": serie_diaria, "historico_60d": historico_60d, "90d": serie_90d}


def coletar_mercado(dados_existentes=None):
  """Busca cotações ao vivo (Yahoo Finance CBOT + Câmbio) e aplica oscilação dinâmica (não fixa)."""
  os.makedirs("dados", exist_ok=True)
  os.makedirs(PASTA_RELATORIOS, exist_ok=True)
  gerar_arquivos_servidor_e_icones()

  horario_coleta = agora_str()
  dolar = 5.34
  dolar_var = 0.25
  try:
    h = yf.Ticker("USDBRL=X").history(period="5d")
    if not h.empty and len(h["Close"]) >= 2:
      dolar = float(h["Close"].iloc[-1])
      ant_d = float(h["Close"].iloc[-2])
      dolar_var = ((dolar - ant_d) / ant_d) * 100
      # Limita distorções de feriados na API para manter paridade física real
      dolar_var = max(-2.5, min(2.5, dolar_var))
  except Exception:
    pass

  bolsa = {}
  for tk in ["ZW=F", "ZS=F", "ZR=F", "ZC=F"]:
    try:
      h = yf.Ticker(tk).history(period="3mo")
      if not h.empty and len(h["Close"]) >= 2:
        pares = []
        for dt_idx, val_c in zip(h.index, h["Close"].tolist()):
          pares.append((dt_idx.strftime("%d/%m/%Y"), float(val_c)))
        fechamentos = [p[1] for p in pares]
        ult = float(h["Close"].iloc[-1])
        ant = float(h["Close"].iloc[-2])
        abert = float(h["Open"].iloc[-1]) if "Open" in h else ant
        alta_d = float(h["High"].iloc[-1]) if "High" in h else max(ult, ant)
        baixa_d = float(h["Low"].iloc[-1]) if "Low" in h else min(ult, ant)
        vol_d = int(h["Volume"].iloc[-1]) if "Volume" in h and h["Volume"].iloc[-1] > 0 else 65762
        m30 = sum(fechamentos[-22:]) / len(fechamentos[-22:])
        var = ((ult - ant) / ant) * 100
        var = max(-3.5, min(3.5, var))
        desvio = ((ult - m30) / m30) * 100
        bolsa[tk] = {
            "var": var,
            "desvio": desvio,
            "pares": pares,
            "ult_usx": round(ult, 2),
            "fech_ant_usx": round(ant, 2),
            "abertura_usx": round(abert, 2),
            "alta_usx": round(alta_d, 2),
            "baixa_usx": round(baixa_d, 2),
            "volume_str": f"{vol_d:,}".replace(",", "."),
        }
    except Exception:
      bolsa[tk] = {"var": -0.45, "desvio": 0.0, "pares": []}

  itens = []
  for i in ITENS_PADRAO:
    preco_base_item = float(i["preco_base"])
    contrato_emp = float(i["contrato_empresa"])
    regioes_salvas = i["regioes_sul"]

    b = bolsa.get(i["ticker"], {})
    ult_usx = b.get("ult_usx", i["usx_padrao"])
    fech_ant_usx = b.get("fech_ant_usx", i["fech_ant_padrao"])
    abertura_usx = b.get("abertura_usx", i["abertura_padrao"])
    alta_usx = b.get("alta_usx", i["alta_padrao"])
    baixa_usx = b.get("baixa_usx", i["baixa_padrao"])
    vol_str = b.get("volume_str", i["volume_padrao"])
    var_usx_pts = round(ult_usx - fech_ant_usx, 2)
    var_usx_pct = round(((ult_usx - fech_ant_usx) / fech_ant_usx) * 100, 2) if fech_ant_usx else -0.45
    var_usx_pct = max(-3.5, min(3.5, var_usx_pct))

    # Oscilação diária dinâmica combinando CBOT + Câmbio + Micro-oscilação intradiária
    micro_tick = math.sin(datetime.now().minute * 0.25) * 0.12
    var_comb = (var_usx_pct * 0.45) + (dolar_var * 0.35) + micro_tick
    preco_atual = round(preco_base_item * (1 + (var_comb / 100)), 2)
    pre_fechamento_brl = round(preco_base_item, 2)

    desvio_tot = b.get("desvio", 0.0) * 0.5 + dolar_var
    if desvio_tot >= 0.8:
      semaforo = "VERDE"
      msg_semaforo = "Momento Favorável para Venda (Acima da Média)"
      cor_sem = "#22C55E"
    elif desvio_tot <= -0.8:
      semaforo = "VERMELHO"
      msg_semaforo = "Pressão de Baixa em Chicago (Oportunidade p/ Compra)"
      cor_sem = "#EF4444"
    else:
      semaforo = "AMARELO"
      msg_semaforo = "Mercado Firme / Oscilação Normal nas Praças"
      cor_sem = "#FACC15"

    prev_15d = round(preco_atual * (1 + 0.008), 2)
    prev_30d = round(preco_atual * (1 + 0.016), 2)
    prev_60d = round(preco_atual * (1 + 0.025), 2)
    prev_90d = round(preco_atual * (1 + 0.034), 2)

    series = gerar_series_com_datas_reais(
        preco_atual, var_comb, b.get("pares", []), prev_15d, prev_30d, prev_60d, prev_90d
    )
    valores_30d = [p["valor"] for p in series["historico_60d"][-30:]]
    media_per = round(sum(valores_30d) / len(valores_30d), 2)
    medias_uf = calcular_medias_estados(regioes_salvas)

    itens.append({
        **i,
        "preco_base": preco_base_item,
        "contrato_empresa": contrato_emp,
        "regioes_sul": regioes_salvas,
        "medias_uf": medias_uf,
        "preco_atual": preco_atual,
        "pre_fechamento_brl": pre_fechamento_brl,
        "media_periodo": media_per,
        "var_dia": round(var_comb, 2),
        "ult_usx": ult_usx,
        "fech_ant_usx": fech_ant_usx,
        "abertura_usx": abertura_usx,
        "alta_usx": alta_usx,
        "baixa_usx": baixa_usx,
        "var_usx_pts": var_usx_pts,
        "var_usx_pct": var_usx_pct,
        "volume_str": vol_str,
        "semaforo": semaforo,
        "msg_semaforo": msg_semaforo,
        "cor_sem": cor_sem,
        "horario_busca_item": horario_coleta,
        "motivo": (
            f"Base {i['nome_bolsa']} ({i['codigo_cbot']}): {ult_usx:.2f} USX"
            f" ({var_usx_pct:+.2f}% / {var_usx_pts:+.2f} hoje) | StoneX & Câmbio R$"
            f" {dolar:.2f}."
        ),
        "explicacao_previsao": (
            f"{i.get('nota_stonex', '')} Projeção calculada sobre {i['nome_bolsa']}"
            f" ({i['codigo_cbot']} = {ult_usx:.2f} USX, Pré-fechamento"
            f" {fech_ant_usx:.2f} USX) e Dólar Comercial (R$ {dolar:.2f})."
        ),
        "prev_15d": prev_15d,
        "prev_30d": prev_30d,
        "prev_60d": prev_60d,
        "prev_90d": prev_90d,
        "series": series,
    })

  pacote = {
      "atualizacao": horario_coleta,
      "tipo_precificacao": "Estimativa regional calculada a partir de bases e índices; NÃO equivale a cotação oficial de balcão.",
      "fontes_consultadas": {"cambio_yahoo": bool(dolar != 5.34), "tickers_yahoo": [k for k, v in bolsa.items() if v.get("pares")]},
      "modelo_previsao": "Cenários ilustrativos (+15/+30/+60/+90 dias), não previsões estatísticas validadas.",
      "dolar": round(dolar, 2),
      "dolar_var": round(dolar_var, 2),
      "itens": itens,
      "registros_planilha": dados_existentes.get("registros_planilha", []) if dados_existentes else [],
  }
  salvar_db(pacote)
  return pacote


def salvar_db(pacote):
  os.makedirs("dados", exist_ok=True)
  salvar_json_atomico(ARQUIVO_DB, pacote)


def carregar_db():
  gerar_arquivos_servidor_e_icones()
  if os.path.exists(ARQUIVO_DB):
    try:
      with open(ARQUIVO_DB, "r", encoding="utf-8") as f:
        d = json.load(f)
        if "dolar" in d and "itens" in d and "nota_stonex" in d["itens"][0]:
          return d
    except Exception:
      pass
  return coletar_mercado()
# =============================================================================
# CR AGROSTAT BRASIL v9.0 — PARTE 3 DE 3 (FINAL)
# Interface Principal, Seletor Triplo de Regiões, IA com Voz (Masc/Fem) e Stories
# =============================================================================

def main(page: ft.Page):
  page.title = "CR AgroStat Brasil v10.1 • Inteligência Agrícola"
  page.bgcolor = "#07111C"
  page.padding = 10
  page.theme = ft.Theme(color_scheme_seed="#10B981", font_family="Roboto")
  page.scroll = None

  ip_local = obter_ip_local()
  dados = carregar_db()
  db_usuarios = inicializar_banco_usuarios()

  usuario_logado_key = None
  tentativas_falhas = 0
  ultimo_bloqueio_login = 0.0
  menu_mobile_ativo = False

  # Estado de Navegação e Hierarquia de 3 Níveis (Macro-Região -> Estado UF -> Sub-Região)
  aba_atual = "painel"
  macro_regiao_sel = "Sul"
  uf_selecionada = "RS"
  subregiao_selecionada = "Fronteira Oeste (São Borja / Itaqui / Uruguaiana)"
  fonte_analise_ativa = "Chicago SRW Wheat / CBOT"

  polo_clima_sel = "RS • Fronteira Oeste (São Borja / Itaqui)"
  item_grafico_idx = 0
  periodo_grafico = "diario"
  estilo_grafico = "area"
  data_ini_idx = 30
  data_fim_idx = 59
  item_regional_idx = 0
  estacao_clima_sel = "Primavera (Set-Nov)"
  periodo_clima_grafico = "10d"
  estilo_clima_grafico = "area"
  sub_aba_perfil = "clientes"
  cliente_em_edicao_id = None

  # Estado da IA de Voz e Texto
  voz_selecionada = "Feminina (Analista Agro)"
  alar_automatico_ia = True
  historico_chat_ia = [
      {
          "autor": "IA CR AgroStat",
          "hora": agora_str(),
          "texto": (
              "Olá! Sou a Inteligência Artificial do CR AgroStat Brasil. "
              "Posso ajudar a interpretar preços regionais estimados, indicadores de bolsa, clima, fretes e barter. "
              "O sistema distingue dados consultados de simulações. Use Ouvir para reproduzir a resposta no navegador."
          ),
      }
  ]

  pino_mapa_selecionado = {
      "titulo": "📍 Localização Padrão: São Borja - RS (Fronteira Oeste)",
      "subtitulo": "Polo Arroz Irrigado, Soja, Trigo e Sementes Certificadas",
      "lat": -28.66,
      "lon": -56.00,
      "uf": "RS",
      "tipo": "Padrao",
      "whatsapp": "",
  }
  horario_ultima_selecao = agora_str()

  raiz_pagina = ft.Container(expand=True)
  coluna_lateral_menu = ft.Column(spacing=7, scroll=ft.ScrollMode.AUTO, expand=True)
  area_conteudo_direita = ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)
  # Áudio Flet 0.24.x: player local + link para reprodutor nativo do navegador.
  import wave
  buffer_silencio = io.BytesIO()
  with wave.open(buffer_silencio, "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(8000)
    wav.writeframes(b"\x00\x00" * 800)
  audio_da_ia = ft.Audio(src_base64=base64.b64encode(buffer_silencio.getvalue()).decode("ascii"), autoplay=False, volume=1.0)
  page.overlay.append(audio_da_ia)
  audio_geracao = 0
  audio_ultimo_link = {"url": "", "gerado": False}

  def falar_navegador(texto, voz=None):
    """Sintetiza no servidor e entrega o MP3 ao navegador, com replay manual."""
    nonlocal audio_geracao
    audio_geracao += 1
    versao = audio_geracao
    voz_ativa = voz or voz_selecionada
    audio_ultimo_link["gerado"] = False

    def carregar_audio():
      mp3 = sintetizar_tts_ptbr(texto, voz_ativa)
      if versao != audio_geracao:
        return
      if not mp3:
        mostrar_aviso("Serviço de voz indisponível no servidor. Confira conexão ou instale edge-tts.", "#EAB308")
        return
      try:
        os.makedirs(os.path.join(PASTA_ASSETS, "audio_ia"), exist_ok=True)
        # Nome individual por reprodução evita problema de cache no Chrome.
        nome = f"audio_{secrets.token_hex(9)}.mp3"
        caminho = os.path.join(PASTA_ASSETS, "audio_ia", nome)
        with open(caminho, "wb") as f:
          f.write(mp3)
        # URL absoluta no Render para o reprodutor nativo do Chrome e Edge.
        base_publica = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
        audio_ultimo_link.update({"url": f"{base_publica}/audio_ia/{nome}", "gerado": True})
        # Descarta áudios antigos; eles são arquivos temporários, não registros do CRM.
        try:
          for arquivo_antigo in Path(PASTA_ASSETS, "audio_ia").glob("audio_*.mp3"):
            if time.time() - arquivo_antigo.stat().st_mtime > 3600:
              arquivo_antigo.unlink(missing_ok=True)
        except OSError:
          pass
        audio_da_ia.src_base64 = base64.b64encode(mp3).decode("ascii")
        audio_da_ia.update()
        # Chrome pode não permitir play automático após uma requisição de rede.
        audio_da_ia.play()
      except Exception:
        mostrar_aviso("MP3 preparado. Use 'Abrir áudio no navegador' se o som não tocar.", "#38BDF8")
    page.run_thread(carregar_audio)

  def ouvir_arquivo_externo(e):
    url = audio_ultimo_link.get("url")
    if not url:
      mostrar_aviso("Primeiro clique em 'Ouvir' para gerar o MP3 da resposta.", "#EAB308")
      return
    try:
      # Link para o áudio estático servido pelo Flet; navegador abre controles nativos.
      page.launch_url(url)
    except Exception:
      mostrar_aviso("Não foi possível abrir o reprodutor. Use o botão Ouvir novamente.", "#EF4444")

  def parar_audio(e=None):
    nonlocal audio_geracao
    audio_geracao += 1
    try:
      audio_da_ia.pause()
    except Exception:
      pass

  def mostrar_aviso(texto, cor="#10B981"):
    page.snack_bar = ft.SnackBar(
        ft.Text(texto, color="#080D16", weight=ft.FontWeight.BOLD),
        bgcolor=cor,
    )
    page.snack_bar.open = True
    page.update()

  def copiar_para_area_transferencia(titulo_copia, texto_copiar):
    page.set_clipboard(texto_copiar)
    mostrar_aviso(f"📋 '{titulo_copia}' copiado para a área de transferência!")

  # Upload de imagem compatível com desktop e navegador Flet/Render.
  # Não depende de caminho local do usuário no servidor.
  upload_pendente = {}

  def finalizar_foto(bytes_foto):
    if not usuario_logado_key:
      return
    if len(bytes_foto) > 4 * 1024 * 1024:
      mostrar_aviso("Imagem muito grande. Escolha uma foto de até 4 MB.", "#F97316")
      return
    # JPG, PNG, WEBP ou GIF; impede arquivos arbitrários disfarçados de imagem.
    assinaturas = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"RIFF")
    if not bytes_foto.startswith(assinaturas) or (bytes_foto.startswith(b"RIFF") and bytes_foto[8:12] != b"WEBP"):
      mostrar_aviso("Selecione uma imagem JPG, PNG, WEBP ou GIF válida.", "#EF4444")
      return
    db_usuarios["usuarios"][usuario_logado_key]["foto_b64"] = base64.b64encode(bytes_foto).decode("ascii")
    salvar_banco_usuarios(db_usuarios)
    mostrar_aviso("Foto do perfil atualizada e salva!")
    montar_sistema()

  def ao_escolher_foto_perfil(e: ft.FilePickerResultEvent):
    if not e.files or not usuario_logado_key:
      return
    arq = e.files[0]
    if arq.size and arq.size > 4 * 1024 * 1024:
      mostrar_aviso("Foto maior que 4 MB. Escolha outra imagem.", "#F97316")
      return
    if not str(arq.name).lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
      mostrar_aviso("A foto deve ser PNG, JPG, WEBP ou GIF.", "#F97316")
      return
    if arq.path and os.path.isfile(arq.path):
      try:
        with open(arq.path, "rb") as f:
          finalizar_foto(f.read())
      except OSError:
        mostrar_aviso("Não foi possível abrir a foto.", "#EF4444")
      return
    # Em navegadores, FilePickerFile.path é None. Faça upload assinado ao servidor.
    os.makedirs(PASTA_UPLOADS, exist_ok=True)
    destino = secrets.token_hex(18) + Path(arq.name).suffix.lower()
    upload_pendente.clear()
    upload_pendente.update({"original": arq.name, "destino": os.path.join(PASTA_UPLOADS, destino), "login": usuario_logado_key})
    try:
      url = page.get_upload_url(destino, 600)
      seletor_foto.upload([ft.FilePickerUploadFile(arq.name, upload_url=url)])
      mostrar_aviso("Enviando foto de perfil...")
    except Exception:
      mostrar_aviso("Falha no upload. Confira permissão de gravação no servidor.", "#EF4444")

  def ao_subir_foto_perfil(e: ft.FilePickerUploadEvent):
    if e.error:
      mostrar_aviso("Não foi possível enviar a foto: " + str(e.error)[:90], "#EF4444")
      return
    if e.progress < 1 or not upload_pendente:
      return
    caminho = upload_pendente.get("destino")
    titular = upload_pendente.get("login")
    upload_pendente.clear()
    if titular != usuario_logado_key:
      mostrar_aviso("Troca de sessão durante o envio. Selecione a foto novamente.", "#EF4444")
      return
    try:
      with open(caminho, "rb") as f:
        conteudo = f.read(4 * 1024 * 1024 + 1)
      finalizar_foto(conteudo)
    except OSError:
      mostrar_aviso("A foto não chegou ao servidor. Refaça a seleção e confira se o Render permite uploads.", "#EF4444")
    finally:
      try:
        os.remove(caminho)
      except (OSError, TypeError):
        pass

  seletor_foto = ft.FilePicker(on_result=ao_escolher_foto_perfil, on_upload=ao_subir_foto_perfil)
  page.overlay.append(seletor_foto)

  def escolher_foto(e):
    seletor_foto.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)

  def obter_avatar_quadrado_grande(u_dict, largura=108, altura=108, raio=24):
    """Cria o avatar em formato quadrado com cantos arredondados bem maior e destacado."""
    foto_b64 = u_dict.get("foto_b64", "")
    iniciais = "".join([p[0] for p in u_dict.get("nome", "ML").split()[:2]]).upper()
    if foto_b64:
      return ft.Container(
          width=largura,
          height=altura,
          border_radius=raio,
          border=ft.border.all(3, "#10B981"),
          clip_behavior=ft.ClipBehavior.HARD_EDGE,
          content=ft.Image(src_base64=foto_b64, fit=ft.ImageFit.COVER),
      )
    return ft.Container(
        width=largura,
        height=altura,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=["#10B981", "#059669", "#047857"],
        ),
        border_radius=raio,
        border=ft.border.all(3, "#FACC15"),
        alignment=ft.alignment.center,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
            controls=[
                ft.Icon(ft.icons.PERSON_ROUNDED, color="#080D16", size=int(largura * 0.34)),
                ft.Text(
                    iniciais,
                    color="#080D16",
                    size=int(largura * 0.24),
                    weight=ft.FontWeight.BOLD,
                ),
            ],
        ),
    )

  def calcular_preco_dinamico_atual(item_dict, uf_cod, subregiao_nome, fonte_chave):
    """Calcula o preço dinâmico exato combinando Estado, Sub-região interna e Fonte Clicável."""
    fator_sub = SUBREGIOES_ESTADOS.get(uf_cod, {}).get(subregiao_nome, 1.000)
    fator_fonte = FONTES_DISPONIVEIS.get(fonte_chave, {"fator_ajuste": 1.0})["fator_ajuste"]
    return round(item_dict["preco_atual"] * fator_sub * fator_fonte, 2)

  def avaliar_alertas_usuario():
    if not usuario_logado_key:
      return []
    u_atual = db_usuarios["usuarios"][usuario_logado_key]
    alertas = u_atual.get("alertas_preco", [])
    resultados = []
    for al in alertas:
      prod_nome = al.get("produto", "Soja em Grão")
      uf_al = al.get("uf", "RS")
      alvo = float(al.get("valor_alvo", 134.50))
      tipo_g = al.get("tipo_gatilho", "Alta")

      preco_hoje = 134.24
      for it in dados["itens"]:
        if prod_nome in it["nome"] or it["nome_curto"] in prod_nome:
          preco_hoje = calcular_preco_dinamico_atual(it, uf_al, subregiao_selecionada, fonte_analise_ativa)
          break

      eh_alta = "Alta" in tipo_g
      dif = preco_hoje - alvo if eh_alta else alvo - preco_hoje
      dist_abs = abs(preco_hoje - alvo)

      if dif >= 0:
        status_al = "🟢 ALVO ATINGIDO! HORA DE FECHAR"
        cor_al = "#22C55E"
        nivel = 2
      elif dist_abs <= 2.0:
        status_al = f"🟡 MUITO PRÓXIMO! (Faltam R$ {dist_abs:.2f})"
        cor_al = "#FACC15"
        nivel = 1
      else:
        status_al = f"🔵 Monitorando (Distância: R$ {dist_abs:.2f})"
        cor_al = "#38BDF8"
        nivel = 0

      resultados.append({
          **al,
          "preco_hoje": preco_hoje,
          "status_al": status_al,
          "cor_al": cor_al,
          "nivel": nivel,
      })
    return resultados

  def gerar_pdf_completo_usuario(contexto_relatorio="Relatorio Oficial"):
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%Hh%Mm%Ss")
    nome_pdf = f"CRAgroStat_{stamp}_{secrets.token_urlsafe(16)}.pdf"
    pasta_publica = os.path.join(PASTA_ASSETS, "relatorios_temp")
    os.makedirs(pasta_publica, exist_ok=True)
    # Limpa relatórios temporários antigos (24h) sem tocar nos dados do CRM.
    for arquivo_antigo in Path(pasta_publica).glob("CRAgroStat_*.pdf"):
      try:
        if time.time() - arquivo_antigo.stat().st_mtime > 86400:
          arquivo_antigo.unlink()
      except OSError:
        pass
    caminho_pdf = os.path.join(pasta_publica, nome_pdf)
    u_info = db_usuarios["usuarios"].get(usuario_logado_key, {}) if usuario_logado_key else {}

    linhas = [
        f"=== RELATORIO EXECUTIVO CR AGROSTAT BRASIL ({contexto_relatorio.upper()}) ===",
        f"Consultor / Responsavel: {u_info.get('nome', 'Márcio Luis Ávila da Silva')}",
        f"Recorte Selecionado: Macro-Regiao {macro_regiao_sel} -> Estado {uf_selecionada} -> {subregiao_selecionada}",
        f"Fonte de Analise Ativa: {fonte_analise_ativa} | Data/Hora: {agora_str()}",
        f"Cambio Dolar Comercial Spot: R$ {dados['dolar']:.2f} ({dados['dolar_var']:+.2f}%)",
        "",
        "ATENCAO: precos de pracas e diferencas por fonte sao calculados pelo aplicativo, nao cotacoes oficiais.",
        "Projecoes de 15 a 90 dias sao cenarios de referencia, nao previsoes estatisticas validadas.",
        "Consulte fonte e data da cotacao antes de realizar qualquer negociacao.",
        "",
        "=== INDICADORES DE MERCADO E ESTIMATIVAS REGIONAIS ===",
    ]
    for it in dados["itens"]:
      val_reg = calcular_preco_dinamico_atual(it, uf_selecionada, subregiao_selecionada, fonte_analise_ativa)
      m_u = calcular_medias_estados(it["regioes_sul"])
      linhas.append(
          f"[{it['sigla']}] {it['nome']} ({it['codigo_cbot']}) -> Preco na Sub-Regiao: R$ {val_reg:.2f} ({it['var_dia']:+.2f}%)"
      )
      linhas.append(
          f"   Medias -> RS: R$ {m_u['RS']:.2f} | Sul: R$ {m_u['SUL']:.2f} | Brasil: R$ {m_u['BR']:.2f} | Bolsa: {it['ult_usx']:.2f} USX"
      )
      linhas.append(
          f"   StoneX & Fundamentos: {it.get('nota_stonex', '')}"
      )
      linhas.append("-" * 98)

    criar_pdf_nativo(
        caminho_pdf,
        "CR AgroStat Brasil - Relatorio Chicago SRW, StoneX, Clima & CRM",
        f"Consultor: {u_info.get('nome', 'Admin')} ({uf_selecionada} - {subregiao_selecionada[:28]})",
        linhas,
    )
    if os.name == "nt":
      try:
        os.startfile(os.path.abspath(caminho_pdf))
      except Exception:
        pass
    mostrar_aviso("Relatório PDF gerado. Abrindo o arquivo no navegador...")
    try:
      page.launch_url("/relatorios_temp/" + urllib.parse.quote(nome_pdf))
    except Exception:
      mostrar_aviso(f"PDF salvo localmente: {caminho_pdf}")

  # =========================================================================
  # COMPONENTE: SELETOR HIERÁRQUICO DE 3 NÍVEIS (MACRO-REGIÃO ➔ ESTADO ➔ REGIÃO INTERNA)
  # =========================================================================
  def construir_seletor_triplo_regioes():
    nonlocal macro_regiao_sel, uf_selecionada, subregiao_selecionada

    def escolher_macro(nova_m):
      nonlocal macro_regiao_sel, uf_selecionada, subregiao_selecionada
      macro_regiao_sel = nova_m
      ufs_disp = HIERARQUIA_BRASIL.get(nova_m, ["RS"])
      uf_selecionada = ufs_disp[0]
      subregioes_disp = list(SUBREGIOES_ESTADOS.get(uf_selecionada, {}).keys())
      subregiao_selecionada = subregioes_disp[0] if subregioes_disp else ""
      renderizar()

    def escolher_estado(nova_uf):
      nonlocal uf_selecionada, subregiao_selecionada
      uf_selecionada = nova_uf
      subregioes_disp = list(SUBREGIOES_ESTADOS.get(nova_uf, {}).keys())
      subregiao_selecionada = subregioes_disp[0] if subregioes_disp else ""
      renderizar()

    def escolher_subregiao(nova_sub):
      nonlocal subregiao_selecionada
      subregiao_selecionada = nova_sub
      renderizar()

    # Nível 1: Botões das 5 Macro-Regiões do Brasil
    row_macros = ft.Row(wrap=True, spacing=6)
    row_macros.controls.append(ft.Text("1º Região do Brasil:", color="#94A3B8", size=12, weight=ft.FontWeight.BOLD))
    for m_nome in HIERARQUIA_BRASIL.keys():
      at_m = macro_regiao_sel == m_nome
      row_macros.controls.append(
          ft.ElevatedButton(
              f"✓ {m_nome}" if at_m else m_nome,
              bgcolor="#10B981" if at_m else "#21394C",
              color="#080D16" if at_m else "#FFFFFF",
              height=32,
              on_click=lambda e, m=m_nome: escolher_macro(m),
          )
      )

    # Nível 2: Botões dos Estados (UF) dentro da Macro-Região escolhida
    ufs_da_macro = HIERARQUIA_BRASIL.get(macro_regiao_sel, ["RS"])
    row_estados = ft.Row(wrap=True, spacing=6)
    row_estados.controls.append(ft.Text("2º Estado (UF):", color="#38BDF8", size=12, weight=ft.FontWeight.BOLD))
    for sigla_u in ufs_da_macro:
      at_u = uf_selecionada == sigla_u
      nome_ext = NOMES_ESTADOS.get(sigla_u, sigla_u)
      row_estados.controls.append(
          ft.ElevatedButton(
              f"✓ 📍 {nome_ext}" if at_u else f"📍 {nome_ext}",
              bgcolor="#38BDF8" if at_u else "#21394C",
              color="#080D16" if at_u else "#E2E8F0",
              height=32,
              on_click=lambda e, u=sigla_u: escolher_estado(u),
          )
      )

    # Nível 3: Botões das Regiões Internas dentro do Estado selecionado
    subs_do_estado = list(SUBREGIOES_ESTADOS.get(uf_selecionada, {}).keys())
    if subregiao_selecionada not in subs_do_estado and subs_do_estado:
      subregiao_selecionada = subs_do_estado[0]

    row_subregioes = ft.Row(wrap=True, spacing=6)
    row_subregioes.controls.append(ft.Text(f"3º Região Interna ({uf_selecionada}):", color="#FACC15", size=12, weight=ft.FontWeight.BOLD))
    for s_nome in subs_do_estado:
      at_s = subregiao_selecionada == s_nome
      row_subregioes.controls.append(
          ft.ElevatedButton(
              f"✓ 🌾 {s_nome}" if at_s else f"🌾 {s_nome}",
              bgcolor="#FACC15" if at_s else "#0A1826",
              color="#080D16" if at_s else "#CBD5E1",
              height=32,
              on_click=lambda e, s=s_nome: escolher_subregiao(s),
          )
      )

    return ft.Container(
        bgcolor="#0A1826",
        padding=14,
        border_radius=16,
        border=ft.border.all(1, "#21394C"),
        content=ft.Column(spacing=8, controls=[row_macros, row_estados, row_subregioes]),
    )

  # =========================================================================
  # TELA DE LOGIN
  # =========================================================================
  def construir_tela_autenticacao():
    nonlocal tentativas_falhas, usuario_logado_key, uf_selecionada, subregiao_selecionada, polo_clima_sel, fonte_analise_ativa, voz_selecionada, ultimo_bloqueio_login

    largura_login = min(540, max(265, (page.width or 850) - 30))
    largura_campo_login = min(360, largura_login - (48 if (page.width or 850) < 600 else 74))
    inp_user = ft.TextField(label="👤 Usuário", value="", bgcolor="#0A1826", color="#FFFFFF", border_radius=14, border_color="#10B981", width=largura_campo_login)
    inp_pass = ft.TextField(label="🔒 Senha", value="", password=True, can_reveal_password=True, bgcolor="#0A1826", color="#FFFFFF", border_radius=14, width=largura_campo_login)
    txt_erro_login = ft.Text("", color="#EF4444", size=13, weight=ft.FontWeight.BOLD)

    def fazer_login(e):
      nonlocal tentativas_falhas, usuario_logado_key, uf_selecionada, subregiao_selecionada, polo_clima_sel, fonte_analise_ativa, voz_selecionada, ultimo_bloqueio_login
      if tentativas_falhas >= 5 and time.monotonic() - ultimo_bloqueio_login < 90:
        txt_erro_login.value = "Muitas tentativas. Aguarde 90 segundos e tente novamente."
        page.update()
        return
      u_dig = inp_user.value.strip().lower()
      s_dig = inp_pass.value.strip()
      usuarios_cad = db_usuarios.get("usuarios", {})
      if u_dig in usuarios_cad and verificar_senha(s_dig, usuarios_cad[u_dig].get("senha_hash", "")):
        u_obj = usuarios_cad[u_dig]
        usuario_logado_key = u_dig
        tentativas_falhas = 0
        ultimo_bloqueio_login = 0.0
        if usuarios_cad[u_dig].get("senha_hash") == criptografar_senha("Agro@2026"):
          mostrar_aviso("IMPORTANTE: senha inicial de exemplo em uso. Altere em Perfil > Configurações.", "#EAB308")
        uf_selecionada = u_obj.get("uf_padrao", "RS")
        subregiao_selecionada = u_obj.get("subregiao_padrao", "Fronteira Oeste (São Borja / Itaqui / Uruguaiana)")
        polo_clima_sel = u_obj.get("polo_padrao", "RS • Fronteira Oeste (São Borja / Itaqui)")
        fonte_analise_ativa = u_obj.get("fonte_preferida", "Chicago SRW Wheat / CBOT")
        voz_selecionada = u_obj.get("voz_ia", "Feminina (Analista Agro)")
        mostrar_aviso(f"Bem-vindo(a), {u_obj['nome']}! Praça ativa: {uf_selecionada} • {subregiao_selecionada}.")
        montar_sistema()
      else:
        tentativas_falhas += 1
        if tentativas_falhas >= 5:
          ultimo_bloqueio_login = time.monotonic()
        txt_erro_login.value = "❌ Utilizador ou palavra-passe incorretos."
        page.update()

    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        content=ft.Container(
            width=largura_login,
            bgcolor="#0E2030",
            padding=18 if (page.width or 850) < 600 else 34,
            border_radius=28,
            border=ft.border.all(2, "#10B981"),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
                spacing=16,
                controls=[
                    ft.Container(
                        width=92,
                        height=92,
                        bgcolor="#10B981",
                        border_radius=26,
                        border=ft.border.all(3, "#FACC15"),
                        alignment=ft.alignment.center,
                        content=ft.Icon(ft.icons.SPA_ROUNDED, color="#080D16", size=54),
                    ),
                    ft.Text("CR AgroStat • Intelligence", color="#FFFFFF", size=22 if (page.width or 850) < 600 else 29, weight=ft.FontWeight.BOLD),
                    ft.Text("Chicago SRW Wheat Futures • StoneX • Mapa Geográfico • IA com Voz & Stories", color="#10B981", size=13, text_align=ft.TextAlign.CENTER),
                    inp_user,
                    inp_pass,
                    txt_erro_login,
                    ft.ElevatedButton("🚀 Entrar no Sistema", bgcolor="#10B981", color="#080D16", width=largura_campo_login, height=48, on_click=fazer_login),
                    ft.Text("Acesso privado. Seus dados comerciais pertencem à sua conta.", color="#94A3B8", size=12),
                ],
            ),
        ),
    )

  # =========================================================================
  # COMPONENTE: PAINEL LATERAL DE GRÁFICO COMPACTO (PARA OS MAPAS)
  # =========================================================================
  def construir_mini_painel_grafico_mapa(modo_clima=False):
    nonlocal item_grafico_idx, estilo_grafico, periodo_grafico, estilo_clima_grafico, periodo_clima_grafico

    if not modo_clima:
      item_sel = dados["itens"][item_grafico_idx]
      preco_sub = calcular_preco_dinamico_atual(item_sel, uf_selecionada, subregiao_selecionada, fonte_analise_ativa)
      fator_escala = preco_sub / max(0.01, item_sel["preco_atual"])
      series_item = item_sel["series"]
      if periodo_grafico == "diario":
        pts_raw = series_item["diario"]
        rot_per = "Oscilação Diária (Hoje)"
      elif periodo_grafico == "7d":
        pts_raw = series_item["historico_60d"][-7:]
        rot_per = "Últimos 7 Dias"
      elif periodo_grafico == "30d":
        pts_raw = series_item["historico_60d"][-30:]
        rot_per = "Últimos 30 Dias"
      elif periodo_grafico == "60d":
        pts_raw = series_item["historico_60d"]
        rot_per = "Últimos 60 Dias"
      else:
        pts_raw = series_item["90d"]
        rot_per = "Estimativa Futura +90 Dias"

      pts = [{"rotulo": p["rotulo"], "data_completa": p["data_completa"], "valor": round(p["valor"] * fator_escala, 2)} for p in pts_raw]
      cor_linha = item_sel["cor"]
      unidade_txt = "R$"
      titulo_mini = f"📊 {item_sel['nome_curto']} ({uf_selecionada}) — R$ {pts[-1]['valor']:.2f}"
      sub_mini = f"{subregiao_selecionada[:34]} | {fonte_analise_ativa}"
      est_atual = estilo_grafico
    else:
      prev_14d, serie_fut_clima, _, _ = buscar_previsao_tempo_openmeteo(polo_clima_sel)
      info_p = POLOS_CLIMA_BRASIL.get(polo_clima_sel, list(POLOS_CLIMA_BRASIL.values())[0])
      if periodo_clima_grafico == "10d":
        pts = [{"rotulo": d["data"], "data_completa": f"{d['data_completa']} (Prob {d['prob']}%)", "valor": d["chuva_mm"]} for d in prev_14d[:10]]
        rot_per = "Previsão Diária Satélite (10 Dias)"
      elif periodo_clima_grafico == "futuro_ia":
        pts = [{"rotulo": d["data"], "data_completa": d["data_completa"], "valor": d["chuva_mm"]} for d in serie_fut_clima]
        rot_per = "Estimativa Futura de Chuva (+15d a +90d)"
      else:
        d_est = info_p["historico_estacoes"][estacao_clima_sel]
        pts = [
            {"rotulo": "2023", "data_completa": "Ano 2023", "valor": float(d_est["2023"])},
            {"rotulo": "2024", "data_completa": "Ano 2024", "valor": float(d_est["2024"])},
            {"rotulo": "2025", "data_completa": "Ano 2025", "valor": float(d_est["2025"])},
            {"rotulo": "Média", "data_completa": "Média 30 Anos", "valor": float(d_est["media_hist"])},
            {"rotulo": "26/27", "data_completa": "Previsão 2026/27", "valor": float(d_est["2026_est"])},
        ]
        rot_per = f"Comparativo — {estacao_clima_sel}"
      cor_linha = "#38BDF8"
      unidade_txt = "mm"
      titulo_mini = f"🌧️ Chuva: {polo_clima_sel.split('(')[0].strip()}"
      sub_mini = f"{rot_per} | Acumulado: {sum(p['valor'] for p in pts):.1f} mm"
      est_atual = estilo_clima_grafico

    valores = [p["valor"] for p in pts]
    media_v = sum(valores) / max(1, len(valores))
    min_v = min(valores)
    max_v = max(valores)
    amp = max(max_v - min_v, 1.0)

    def mudar_est_mini(novo_e):
      nonlocal estilo_grafico, estilo_clima_grafico
      if modo_clima:
        estilo_clima_grafico = novo_e
      else:
        estilo_grafico = novo_e
      renderizar()

    def mudar_per_mini(novo_p):
      nonlocal periodo_grafico, periodo_clima_grafico
      if modo_clima:
        periodo_clima_grafico = novo_p
      else:
        periodo_grafico = novo_p
      renderizar()

    def mudar_item_mini(idx_i):
      nonlocal item_grafico_idx
      item_grafico_idx = idx_i
      renderizar()

    if est_atual in ["area", "linha"]:
      passo = max(1, len(pts) // 6)
      rotulos_x = [
          ft.ChartAxisLabel(value=i, label=ft.Container(ft.Text(p["rotulo"], size=10, color="#94A3B8"), padding=ft.padding.only(top=4)))
          for i, p in enumerate(pts)
          if i % passo == 0 or i == len(pts) - 1
      ]
      cor_hex = cor_linha.lstrip("#")
      grafico_widget = ft.Container(
          height=190,
          padding=ft.padding.only(right=14, top=10),
          content=ft.LineChart(
              data_series=[
                  ft.LineChartData(
                      data_points=[ft.LineChartDataPoint(i, p["valor"], tooltip=f"{p['data_completa']}: {p['valor']:.2f} {unidade_txt}") for i, p in enumerate(pts)],
                      stroke_width=3.5,
                      color=cor_linha,
                      curved=(est_atual == "area"),
                      below_line_bgcolor=f"#33{cor_hex}" if est_atual == "area" else None,
                  ),
                  ft.LineChartData(
                      data_points=[ft.LineChartDataPoint(i, round(media_v, 2), tooltip=f"Média: {media_v:.2f} {unidade_txt}") for i in range(len(pts))],
                      stroke_width=2,
                      color="#FACC15",
                      dash_pattern=[5, 4],
                  ),
              ],
              min_y=round(max(0, min_v - amp * 0.2), 2) if modo_clima else round(min_v - amp * 0.25, 2),
              max_y=round(max_v + amp * 0.25, 2),
              left_axis=ft.ChartAxis(labels_size=46),
              bottom_axis=ft.ChartAxis(labels=rotulos_x, labels_size=28),
              horizontal_grid_lines=ft.ChartGridLines(interval=max(0.5, round(amp / 4, 1)), color="#21394C", width=1),
              tooltip_bgcolor="#0F172A",
              interactive=True,
          ),
      )
    elif est_atual == "colunas":
      cols = ft.Row(alignment=ft.MainAxisAlignment.SPACE_AROUND, vertical_alignment=ft.CrossAxisAlignment.END, height=180)
      for p in pts[:10]:
        prop = (p["valor"] - min_v) / amp if amp > 0 else 0.5
        alt_b = int(35 + prop * 100)
        cols.controls.append(
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.END,
                spacing=3,
                controls=[
                    ft.Text(f"{p['valor']:.1f}", color="#FFFFFF", size=10, weight=ft.FontWeight.BOLD),
                    ft.Container(width=26, height=alt_b, bgcolor=cor_linha, border_radius=6),
                    ft.Text(p["rotulo"], color="#94A3B8", size=10),
                ],
            )
        )
      grafico_widget = cols
    else:
      linhas_t = ft.Column(spacing=5)
      for p in pts[:7]:
        prop = max(0.08, (p["valor"] - min_v) / amp)
        linhas_t.controls.append(
            ft.Row(
                spacing=8,
                controls=[
                    ft.Text(p["rotulo"], color="#CBD5E1", size=11, width=70),
                    ft.Container(expand=True, bgcolor="#131E32", height=16, border_radius=6, content=ft.Row([ft.Container(width=int(prop * 200), height=16, bgcolor=cor_linha, border_radius=6)])),
                    ft.Text(f"{p['valor']:.1f} {unidade_txt}", color="#10B981", size=11, weight=ft.FontWeight.BOLD, width=75),
                ],
            )
        )
      grafico_widget = linhas_t

    botoes_formato = ft.Row(
        wrap=True,
        spacing=6,
        controls=[
            ft.ElevatedButton("✓ 📈 Área" if est_atual == "area" else "📈 Área", bgcolor="#10B981" if est_atual == "area" else "#21394C", color="#080D16" if est_atual == "area" else "#FFFFFF", height=28, on_click=lambda e: mudar_est_mini("area")),
            ft.ElevatedButton("✓ 📐 Linha" if est_atual == "linha" else "📐 Linha", bgcolor="#10B981" if est_atual == "linha" else "#21394C", color="#080D16" if est_atual == "linha" else "#FFFFFF", height=28, on_click=lambda e: mudar_est_mini("linha")),
            ft.ElevatedButton("✓ 📊 Colunas" if est_atual == "colunas" else "📊 Colunas", bgcolor="#10B981" if est_atual == "colunas" else "#21394C", color="#080D16" if est_atual == "colunas" else "#FFFFFF", height=28, on_click=lambda e: mudar_est_mini("colunas")),
            ft.ElevatedButton("✓ 📉 Termómetro" if est_atual == "horizontal" else "📉 Termómetro", bgcolor="#10B981" if est_atual == "horizontal" else "#21394C", color="#080D16" if est_atual == "horizontal" else "#FFFFFF", height=28, on_click=lambda e: mudar_est_mini("horizontal")),
        ],
    )

    if not modo_clima:
      chips_seletor = ft.Row(
          wrap=True,
          spacing=5,
          controls=[
              ft.ElevatedButton(
                  f"✓ {it['sigla']}" if i == item_grafico_idx else it["sigla"],
                  bgcolor=it["cor"] if i == item_grafico_idx else "#21394C",
                  color="#080D16" if i == item_grafico_idx else "#E2E8F0",
                  height=28,
                  on_click=lambda e, idx=i: mudar_item_mini(idx),
              )
              for i, it in enumerate(dados["itens"])
          ],
      )
      botoes_periodo_mini = ft.Row(
          wrap=True,
          spacing=5,
          controls=[
              ft.ElevatedButton("✓ 1D" if periodo_grafico == "diario" else "1D", bgcolor="#38BDF8" if periodo_grafico == "diario" else "#21394C", color="#080D16" if periodo_grafico == "diario" else "#FFFFFF", height=28, on_click=lambda e: mudar_per_mini("diario")),
              ft.ElevatedButton("✓ 7D" if periodo_grafico == "7d" else "7D", bgcolor="#38BDF8" if periodo_grafico == "7d" else "#21394C", color="#080D16" if periodo_grafico == "7d" else "#FFFFFF", height=28, on_click=lambda e: mudar_per_mini("7d")),
              ft.ElevatedButton("✓ 30D" if periodo_grafico == "30d" else "30D", bgcolor="#38BDF8" if periodo_grafico == "30d" else "#21394C", color="#080D16" if periodo_grafico == "30d" else "#FFFFFF", height=28, on_click=lambda e: mudar_per_mini("30d")),
              ft.ElevatedButton("✓ 🔮 +90D" if periodo_grafico == "90d" else "🔮 +90D", bgcolor="#FACC15" if periodo_grafico == "90d" else "#21394C", color="#080D16" if periodo_grafico == "90d" else "#FACC15", height=28, on_click=lambda e: mudar_per_mini("90d")),
          ],
      )
    else:
      chips_seletor = ft.Row(
          wrap=True,
          spacing=5,
          controls=[
              ft.ElevatedButton("✓ 📅 10 Dias" if periodo_clima_grafico == "10d" else "📅 10 Dias", bgcolor="#38BDF8" if periodo_clima_grafico == "10d" else "#21394C", color="#080D16" if periodo_clima_grafico == "10d" else "#FFFFFF", height=28, on_click=lambda e: mudar_per_mini("10d")),
              ft.ElevatedButton("✓ 🔮 Previsão Futura (+90d)" if periodo_clima_grafico == "futuro_ia" else "🔮 Previsão Futura (+90d)", bgcolor="#FACC15" if periodo_clima_grafico == "futuro_ia" else "#21394C", color="#080D16" if periodo_clima_grafico == "futuro_ia" else "#FACC15", height=28, on_click=lambda e: mudar_per_mini("futuro_ia")),
              ft.ElevatedButton("✓ 📊 Anos Anteriores" if periodo_clima_grafico == "estacoes_anos" else "📊 Anos Anteriores", bgcolor="#10B981" if periodo_clima_grafico == "estacoes_anos" else "#21394C", color="#080D16" if periodo_clima_grafico == "estacoes_anos" else "#FFFFFF", height=28, on_click=lambda e: mudar_per_mini("estacoes_anos")),
          ],
      )
      botoes_periodo_mini = ft.Container()

    return ft.Container(
        bgcolor="#0A1826",
        padding=14,
        border_radius=18,
        border=ft.border.all(1.5, "#21394C"),
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Text(titulo_mini, color="#FFFFFF", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(sub_mini, color="#38BDF8", size=11),
                chips_seletor,
                botoes_formato,
                botoes_periodo_mini,
                ft.Container(bgcolor="#0E2030", padding=10, border_radius=14, content=grafico_widget),
            ],
        ),
    )

  # =========================================================================
  # COMPONENTE: MAPA GEOGRÁFICO REAL DO BRASIL COM ESTADOS E PINOS CLICÁVEIS
  # =========================================================================
  def construir_widget_mapa_brasil_real():
    nonlocal pino_mapa_selecionado, uf_selecionada, subregiao_selecionada, polo_clima_sel
    u_atual = db_usuarios["usuarios"].get(usuario_logado_key, {})
    clientes_u = u_atual.get("clientes", [])
    svg_b64 = mapa_brasil_ibge_b64(uf_selecionada)
    mapa_oficial = bool(svg_b64)
    if not svg_b64:
      # Modo de contingência sem internet: desenho antigo só como esquema ilustrativo.
      svg_b64 = gerar_svg_geografico_estados_brasil_b64(uf_selecionada)

    def selecionar_polo_mapa(nome_p, info_p):
      nonlocal pino_mapa_selecionado, uf_selecionada, subregiao_selecionada, polo_clima_sel
      uf_selecionada = info_p["uf"]
      subs = list(SUBREGIOES_ESTADOS.get(uf_selecionada, {}).keys())
      if subs:
        subregiao_selecionada = subs[0]
      polo_clima_sel = nome_p
      pino_mapa_selecionado = {
          "titulo": f"📍 {nome_p}",
          "subtitulo": f"{info_p['perfil']} | Estação: {info_p['estacao_inmet']}",
          "lat": info_p["lat"],
          "lon": info_p["lon"],
          "uf": info_p["uf"],
          "tipo": "Polo",
          "whatsapp": "",
      }
      renderizar()

    def selecionar_cliente_mapa(cli):
      nonlocal pino_mapa_selecionado
      pino_mapa_selecionado = {
          "titulo": f"🚜 Cliente: {cli['nome']}",
          "subtitulo": f"{cli['propriedade']} ({cli['cidade_uf']}) | Roteiro: {cli['roteiro_lavoura']}",
          "lat": cli["lat_lavoura"],
          "lon": cli["lon_lavoura"],
          "uf": "RS",
          "tipo": "Cliente",
          "whatsapp": cli.get("whatsapp", ""),
      }
      renderizar()

    largura_base = 720 if mapa_oficial else 650
    altura_base = 700 if mapa_oficial else 580
    # Ajusta desenho e pinos juntos: nenhum elemento perde a posição GPS.
    tela_largura = page.width or 1200
    if tela_largura < 825:
      largura_disponivel = max(260, tela_largura - 62)
    elif tela_largura < 1350:
      largura_disponivel = max(330, (tela_largura - 365) * 0.55)
    else:
      largura_disponivel = min(650, (tela_largura - 370) * 0.55)
    escala_mapa = min(1.0, largura_disponivel / largura_base)
    largura_mapa = round(largura_base * escala_mapa)
    altura_mapa = round(altura_base * escala_mapa)
    controles_stack = [
        ft.Image(src_base64=svg_b64, width=largura_mapa, height=altura_mapa, fit=ft.ImageFit.CONTAIN),
    ]

    for nome_p, info_p in POLOS_CLIMA_BRASIL.items():
      ativo_p = nome_p == polo_clima_sel
      eh_sb = "São Borja" in nome_p
      cor_bg = "#10B981" if ativo_p else ("#059669" if eh_sb else "#0F172A")
      cor_txt = "#080D16" if ativo_p or eh_sb else "#38BDF8"
      sigla_pino = info_p["uf"] + " • " + nome_p.split("(")[1].split("/")[0].replace(")", "").strip()

      x, y = coordenada_mapa(info_p["lat"], info_p["lon"]) if mapa_oficial else (info_p["mapa_x"], info_p["mapa_y"])
      controles_stack.append(
          ft.Container(
              left=max(2, (x - 11) * escala_mapa),
              top=max(2, (y - 11) * escala_mapa),
              tooltip=nome_p,
              content=ft.IconButton(
                  icon=ft.icons.LOCATION_ON_ROUNDED,
                  icon_color="#FACC15" if ativo_p else "#38BDF8",
                  icon_size=(22 if ativo_p else 17) if escala_mapa < 0.75 else (26 if ativo_p else 20),
                  bgcolor="#164E43" if ativo_p else "#0B2334",
                  on_click=lambda e, np=nome_p, ip=info_p: selecionar_polo_mapa(np, ip),
              ),
          )
      )

    if mapa_oficial:
      for idx_c, cli in enumerate(clientes_u):
        try:
          x,y = coordenada_mapa(float(cli["lat_lavoura"]), float(cli["lon_lavoura"]))
          x, y = x * escala_mapa, y * escala_mapa
          if not (5 < x < largura_mapa - 5 and 5 < y < altura_mapa - 5):
            continue
          controles_stack.append(ft.Container(left=x-12, top=y-12, tooltip=cli.get("nome", "Cliente"),
              content=ft.IconButton(icon=ft.icons.AGRICULTURE_ROUNDED,
                  icon_color="#FACC15", icon_size=24, bgcolor="#3F3412",
                  on_click=lambda e, c=cli: selecionar_cliente_mapa(c))))
        except (ValueError, TypeError, KeyError):
          continue

    return ft.Container(
        bgcolor="#060B14",
        border_radius=22,
        border=ft.border.all(1.5, "#21394C"),
        alignment=ft.alignment.center,
        content=ft.Column(spacing=6, controls=[
            ft.Text("Malha IBGE • pinos posicionados por GPS • zoom e arraste" if mapa_oficial else
                    "Mapa ilustrativo offline. Conecte à internet para baixar a malha IBGE.",
                    size=11, color="#A7F3D0" if mapa_oficial else "#FACC15"),
            ft.InteractiveViewer(min_scale=0.42, max_scale=4.0, constrained=False,
                content=ft.Stack(width=largura_mapa, height=altura_mapa, controls=controles_stack),
                height=min(510, altura_mapa + 8)),
        ]),
    )

  # =========================================================================
  # ABA 1: TERMINAL PRINCIPAL (CHICAGO SRW + STONEX + 3 NÍVEIS + GRÁFICO DIÁRIO)
  # =========================================================================
  def construir_bloco_terminal_chicago():
    nonlocal data_ini_idx, data_fim_idx, horario_ultima_selecao, fonte_analise_ativa
    item_sel = dados["itens"][item_grafico_idx]
    medias_uf = calcular_medias_estados(item_sel["regioes_sul"])
    item_sel["medias_uf"] = medias_uf

    # Preço Dinâmico Calculado pela Sub-Região do Estado + Fonte Clicável (ex: Trigo ~R$ 73,00 no RS oscilando ao vivo)
    preco_foco_brl = calcular_preco_dinamico_atual(item_sel, uf_selecionada, subregiao_selecionada, fonte_analise_ativa)
    fator_escala = preco_foco_brl / max(0.01, item_sel["preco_atual"])
    pre_fech_brl = round(item_sel["pre_fechamento_brl"] * fator_escala, 2)
    var_hoje_brl = round(preco_foco_brl - pre_fech_brl, 2)
    var_hoje_pct = round(((preco_foco_brl - pre_fech_brl) / max(0.01, pre_fech_brl)) * 100, 2)

    series_item = item_sel["series"]
    hist_60 = series_item["historico_60d"]

    if periodo_grafico == "diario":
      pontos_base = series_item["diario"]
      titulo_per = "Oscilação Diária Ao Vivo (Pregão Intradia CBOT / StoneX / Físico)"
    elif periodo_grafico == "7d":
      pontos_base = hist_60[-7:]
      titulo_per = f"Últimos 7 Dias ({pontos_base[0]['data_completa']} a {pontos_base[-1]['data_completa']})"
    elif periodo_grafico == "15d":
      pontos_base = hist_60[-15:]
      titulo_per = f"Últimos 15 Dias ({pontos_base[0]['data_completa']} a {pontos_base[-1]['data_completa']})"
    elif periodo_grafico == "30d":
      pontos_base = hist_60[-30:]
      titulo_per = f"Últimos 30 Dias ({pontos_base[0]['data_completa']} a {pontos_base[-1]['data_completa']})"
    elif periodo_grafico == "60d":
      pontos_base = hist_60
      titulo_per = f"Últimos 60 Dias ({pontos_base[0]['data_completa']} a {pontos_base[-1]['data_completa']})"
    elif periodo_grafico == "90d":
      pontos_base = series_item["90d"]
      titulo_per = "Curva de Estimativa Futura +15d, +30d, +60d e +90d (IA)"
    else:
      ini = min(data_ini_idx, data_fim_idx)
      fim = max(data_ini_idx, data_fim_idx)
      if fim - ini < 1:
        fim = min(len(hist_60) - 1, ini + 1)
      pontos_base = hist_60[ini : fim + 1]
      titulo_per = f"Período Personalizado: {pontos_base[0]['data_completa']} a {pontos_base[-1]['data_completa']}"

    pontos = [
        {"rotulo": p["rotulo"], "data_completa": p["data_completa"], "valor": round(p["valor"] * fator_escala, 2)}
        for p in pontos_base
    ]

    valores = [p["valor"] for p in pontos]
    media_val = sum(valores) / len(valores)
    min_val = min(valores + [pre_fech_brl])
    max_val = max(valores + [pre_fech_brl])
    amplitude = max(max_val - min_val, 0.35)

    def sel_item_graf(idx):
      nonlocal item_grafico_idx, horario_ultima_selecao
      item_grafico_idx = idx
      horario_ultima_selecao = agora_str()
      renderizar()

    def sel_fonte_clicavel(f_key):
      nonlocal fonte_analise_ativa, horario_ultima_selecao
      fonte_analise_ativa = f_key
      if usuario_logado_key:
        db_usuarios["usuarios"][usuario_logado_key]["fonte_preferida"] = f_key
        salvar_banco_usuarios(db_usuarios)
      horario_ultima_selecao = agora_str()
      mostrar_aviso(f"🔎 Fonte de análise alterada para: {FONTES_DISPONIVEIS[f_key]['nome']}")
      renderizar()

    def sel_periodo_graf(per):
      nonlocal periodo_grafico
      periodo_grafico = per
      renderizar()

    def sel_estilo_graf(est):
      nonlocal estilo_grafico
      estilo_grafico = est
      renderizar()

    # 1. Chips de Seleção de Grão / Semente (Mostrando o preço dinâmico real)
    chips_itens = ft.Row(wrap=True, spacing=8)
    for idx, it in enumerate(dados["itens"]):
      ativo = idx == item_grafico_idx
      pr_it = calcular_preco_dinamico_atual(it, uf_selecionada, subregiao_selecionada, fonte_analise_ativa)
      chips_itens.controls.append(
          ft.ElevatedButton(
              f"✓ {it['sigla']} (R$ {pr_it:.2f})" if ativo else f"{it['sigla']} (R$ {pr_it:.2f})",
              bgcolor=it["cor"] if ativo else "#21394C",
              color="#080D16" if ativo else "#E2E8F0",
              height=38,
              on_click=lambda e, i=idx: sel_item_graf(i),
          )
      )

    # 2. Barra Clicável de Múltiplas Fontes de Análise (Chicago SRW + StoneX + Emater/IRGA + CEPEA + B3)
    barra_fontes_clicaveis = ft.Row(wrap=True, spacing=6)
    barra_fontes_clicaveis.controls.append(ft.Text("📚 Fonte Clicável de Análise:", color="#10B981", size=12, weight=ft.FontWeight.BOLD))
    for ch_f, info_f in FONTES_DISPONIVEIS.items():
      at_f = fonte_analise_ativa == ch_f
      barra_fontes_clicaveis.controls.append(
          ft.ElevatedButton(
              f"✓ {info_f['sigla_btn']}" if at_f else info_f["sigla_btn"],
              bgcolor="#10B981" if at_f else "#21394C",
              color="#080D16" if at_f else "#38BDF8",
              height=32,
              on_click=lambda e, k=ch_f: sel_fonte_clicavel(k),
          )
      )

    # 3. Painel de Valor Gigante Estilo Chicago SRW Wheat Futures + StoneX
    em_alta = var_hoje_brl >= 0
    cor_pilula_bg = "#14532D" if em_alta else "#F87171"
    cor_pilula_txt = "#4ADE80" if em_alta else "#1E1B18"
    seta_var = "↑" if em_alta else "↓"
    info_fonte_atual = FONTES_DISPONIVEIS.get(fonte_analise_ativa, list(FONTES_DISPONIVEIS.values())[0])

    bloco_valor_gigante = ft.Container(
        bgcolor="#0A1826",
        padding=20,
        border_radius=20,
        border=ft.border.all(1.5, "#21394C"),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    controls=[
                        ft.Text(
                            f"Resumo do mercado > {info_fonte_atual['nome']} • {uf_selecionada} ({subregiao_selecionada})",
                            color="#94A3B8",
                            size=13,
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Container(
                                    bgcolor="#21394C",
                                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                                    border_radius=8,
                                    content=ft.Text(item_sel["codigo_cbot"], color="#FACC15", size=13, weight=ft.FontWeight.BOLD),
                                ),
                                ft.ElevatedButton(
                                    "🌐 Abrir Portal Oficial",
                                    bgcolor="#0E2030",
                                    color="#38BDF8",
                                    height=30,
                                    on_click=lambda e: page.launch_url(info_fonte_atual["url"]),
                                ),
                            ],
                        ),
                    ],
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    wrap=True,
                    controls=[
                        ft.Row(
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            spacing=14,
                            wrap=True,
                            controls=[
                                ft.Text(f"R$ {preco_foco_brl:.2f}", color="#FFFFFF", size=50, weight=ft.FontWeight.BOLD),
                                ft.Text(f"/ {item_sel['unidade']} ({subregiao_selecionada.split('(')[0].strip()})", color="#94A3B8", size=15),
                                ft.Container(
                                    bgcolor=cor_pilula_bg,
                                    padding=ft.padding.symmetric(horizontal=12, vertical=6),
                                    border_radius=10,
                                    content=ft.Text(
                                        f"{seta_var} {abs(var_hoje_pct):.2f}%",
                                        color=cor_pilula_txt,
                                        size=16,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ),
                                ft.Text(
                                    f"{var_hoje_brl:+.2f} R$ hoje (Dinâmico)",
                                    color="#4ADE80" if em_alta else "#F87171",
                                    size=15,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                        ),
                        # Médias Comparativas Simultâneas + Pontos Chicago
                        ft.Row(
                            wrap=True,
                            spacing=10,
                            controls=[
                                ft.Container(
                                    bgcolor="#0E2030",
                                    padding=10,
                                    border_radius=12,
                                    border=ft.border.all(1, "#10B981"),
                                    content=ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text("MÉDIAS REGIONAIS & BRASIL", color="#10B981", size=10, weight=ft.FontWeight.BOLD),
                                            ft.Text(
                                                f"Média {uf_selecionada}: R$ {medias_uf.get(uf_selecionada, preco_foco_brl):.2f} | Sul: R$ {medias_uf['SUL']:.2f} | BR: R$ {medias_uf['BR']:.2f}",
                                                color="#FFFFFF",
                                                size=12,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                        ],
                                    ),
                                ),
                                ft.Container(
                                    bgcolor="#0E2030",
                                    padding=10,
                                    border_radius=12,
                                    border=ft.border.all(1, "#FACC15"),
                                    content=ft.Column(
                                        horizontal_alignment=ft.CrossAxisAlignment.END,
                                        spacing=2,
                                        controls=[
                                            ft.Text("CHICAGO SRW / CBOT", color="#94A3B8", size=10, weight=ft.FontWeight.BOLD),
                                            ft.Text(
                                                f"{item_sel['ult_usx']:.2f} USX ({item_sel['var_usx_pts']:+.2f})",
                                                color="#FACC15",
                                                size=16,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                        ],
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
                # Destaque Informativo StoneX & Inteligência de Mercado
                ft.Container(
                    bgcolor="#0E2030",
                    padding=10,
                    border_radius=10,
                    border=ft.border.all(1, "#38BDF8"),
                    content=ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.icons.INSIGHTS_ROUNDED, color="#38BDF8", size=20),
                            ft.Text(
                                f"💎 Boletim StoneX & {fonte_analise_ativa}: {item_sel.get('nota_stonex', '')} {info_fonte_atual['resumo_analise']}",
                                color="#E2E8F0",
                                size=12,
                                expand=True,
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )

    opcoes_per = [
        ("diario", "1 D (Oscilação Diária)"),
        ("7d", "5 D / 7 D"),
        ("15d", "15 D"),
        ("30d", "1 M (30D)"),
        ("60d", "6 M (60D)"),
        ("90d", "🔮 Previsão Futura +90D"),
    ]
    botoes_per = ft.Row(wrap=True, spacing=6)
    for cod_p, rot_p in opcoes_per:
      at_p = periodo_grafico == cod_p
      cor_p = "#FACC15" if cod_p == "90d" else "#38BDF8"
      botoes_per.controls.append(
          ft.ElevatedButton(
              f"✓ {rot_p}" if at_p else rot_p,
              bgcolor=cor_p if at_p else "#21394C",
              color="#080D16" if at_p else "#FFFFFF",
              height=32,
              on_click=lambda e, pe=cod_p: sel_periodo_graf(pe),
          )
      )

    opcoes_est = [
        ("area", "📈 Curva de Área + Pré-fech."),
        ("linha", "📐 Linha Técnica"),
        ("colunas", "📊 Colunas Verticais"),
        ("horizontal", "📉 Termómetro por Data"),
    ]
    botoes_estilo = ft.Row(wrap=True, spacing=6)
    for cod_e, rot_e in opcoes_est:
      at_e = estilo_grafico == cod_e
      botoes_estilo.controls.append(
          ft.ElevatedButton(
              f"✓ {rot_e}" if at_e else rot_e,
              bgcolor="#10B981" if at_e else "#21394C",
              color="#080D16" if at_e else "#FFFFFF",
              height=32,
              on_click=lambda e, es=cod_e: sel_estilo_graf(es),
          )
      )

    if estilo_grafico in ["area", "linha"]:
      passo_rotulo = max(1, len(pontos) // 8)
      rotulos_x = [
          ft.ChartAxisLabel(value=i, label=ft.Container(ft.Text(p["rotulo"], size=11, color="#94A3B8"), padding=ft.padding.only(top=6)))
          for i, p in enumerate(pontos)
          if len(pontos) <= 10 or i % passo_rotulo == 0 or i == len(pontos) - 1
      ]
      cor_hex_limpa = item_sel["cor"].lstrip("#")
      widget_grafico = ft.Container(
          height=230,
          padding=ft.padding.only(right=20, top=14, bottom=4),
          content=ft.LineChart(
              data_series=[
                  ft.LineChartData(
                      data_points=[
                          ft.LineChartDataPoint(i, p["valor"], tooltip=f"{p['data_completa']}: R$ {p['valor']:.2f}")
                          for i, p in enumerate(pontos)
                      ],
                      stroke_width=3.5,
                      color=item_sel["cor"],
                      curved=(estilo_grafico == "area"),
                      below_line_bgcolor=f"#33{cor_hex_limpa}" if estilo_grafico == "area" else None,
                  ),
                  ft.LineChartData(
                      data_points=[
                          ft.LineChartDataPoint(
                              i,
                              pre_fech_brl if periodo_grafico == "diario" else round(media_val, 2),
                              tooltip=f"Pré-fechamento: R$ {pre_fech_brl:.2f} | Média: R$ {media_val:.2f}",
                          )
                          for i in range(len(pontos))
                      ],
                      stroke_width=2,
                      color="#94A3B8" if periodo_grafico == "diario" else "#38BDF8",
                      dash_pattern=[5, 4],
                  ),
              ],
              min_y=round(min_val - amplitude * 0.25, 2),
              max_y=round(max_val + amplitude * 0.25, 2),
              left_axis=ft.ChartAxis(labels_size=56),
              bottom_axis=ft.ChartAxis(labels=rotulos_x, labels_size=30),
              horizontal_grid_lines=ft.ChartGridLines(interval=max(0.15, round(amplitude / 4, 2)), color="#21394C", width=1),
              tooltip_bgcolor="#0F172A",
              interactive=True,
          ),
      )
    elif estilo_grafico == "colunas":
      passo_c = max(1, math.ceil(len(pontos) / 12))
      pontos_col = pontos[::passo_c]
      colunas_grafico = ft.Row(alignment=ft.MainAxisAlignment.SPACE_AROUND, vertical_alignment=ft.CrossAxisAlignment.END, height=215)
      for p in pontos_col:
        prop = (p["valor"] - min_val) / amplitude
        alt_b = int(42 + prop * 115)
        colunas_grafico.controls.append(
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.END,
                spacing=3,
                controls=[
                    ft.Text(f"R$ {p['valor']:.2f}", color="#FFFFFF", size=10, weight=ft.FontWeight.BOLD),
                    ft.Container(width=34, height=alt_b, bgcolor=item_sel["cor"], border_radius=8),
                    ft.Text(p["rotulo"], color="#94A3B8", size=10),
                ],
            )
        )
      widget_grafico = colunas_grafico
    else:
      passo_h = max(1, math.ceil(len(pontos) / 8))
      pontos_h = pontos[::passo_h]
      linhas_h = ft.Column(spacing=6)
      for p in pontos_h:
        prop = max(0.08, (p["valor"] - min_val) / amplitude)
        dif_m = p["valor"] - media_val
        linhas_h.controls.append(
            ft.Row(
                spacing=10,
                controls=[
                    ft.Text(p["data_completa"][:22], color="#CBD5E1", size=11, width=155),
                    ft.Container(expand=True, bgcolor="#131E32", height=18, border_radius=8, content=ft.Row([ft.Container(width=int(prop * 360), height=18, bgcolor=item_sel["cor"], border_radius=8)])),
                    ft.Text(f"R$ {p['valor']:.2f} ({dif_m:+.2f})", color="#22C55E" if dif_m >= 0 else "#EF4444", size=12, weight=ft.FontWeight.BOLD, width=135),
                ],
            )
        )
      widget_grafico = linhas_h

    # Grelha dos 6 Indicadores Oficiais Chicago SRW
    grelha_6_indicadores_cbot = ft.Container(
        bgcolor="#0A1826",
        padding=14,
        border_radius=16,
        border=ft.border.all(1, "#21394C"),
        content=ft.ResponsiveRow(
            spacing=14,
            run_spacing=8,
            controls=[
                ft.Container(
                    col={"xs": 6, "md": 4},
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text("Abertura", color="#94A3B8", size=12), ft.Text(f"{item_sel['abertura_usx']:.2f} USX (R$ {pontos[0]['valor']:.2f})", color="#E2E8F0", size=12, weight=ft.FontWeight.BOLD)]),
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text("Alta (Máx. Dia)", color="#94A3B8", size=12), ft.Text(f"{item_sel['alta_usx']:.2f} USX (R$ {max_val:.2f})", color="#22C55E", size=12, weight=ft.FontWeight.BOLD)]),
                        ],
                    ),
                ),
                ft.Container(
                    col={"xs": 6, "md": 4},
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text("Baixa (Mín. Dia)", color="#94A3B8", size=12), ft.Text(f"{item_sel['baixa_usx']:.2f} USX (R$ {min_val:.2f})", color="#F87171", size=12, weight=ft.FontWeight.BOLD)]),
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text("Fech. ant.", color="#94A3B8", size=12), ft.Text(f"{item_sel['fech_ant_usx']:.2f} USX (R$ {pre_fech_brl:.2f})", color="#E2E8F0", size=12, weight=ft.FontWeight.BOLD)]),
                        ],
                    ),
                ),
                ft.Container(
                    col={"xs": 12, "md": 4},
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text("Volume", color="#94A3B8", size=12), ft.Text(item_sel["volume_str"], color="#38BDF8", size=12, weight=ft.FontWeight.BOLD)]),
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text("Contratos em aberto", color="#94A3B8", size=12), ft.Text(item_sel["contratos_abertos"], color="#FACC15", size=12, weight=ft.FontWeight.BOLD)]),
                        ],
                    ),
                ),
            ],
        ),
    )

    p15_uf = round(item_sel["prev_15d"] * fator_escala, 2)
    p30_uf = round(item_sel["prev_30d"] * fator_escala, 2)
    p60_uf = round(item_sel["prev_60d"] * fator_escala, 2)
    p90_uf = round(item_sel["prev_90d"] * fator_escala, 2)

    return ft.Container(
        bgcolor="#0E2030",
        padding=20,
        border_radius=24,
        border=ft.border.all(1.5, "#21394C"),
        content=ft.Column(
            spacing=12,
            controls=[
                chips_itens,
                construir_seletor_triplo_regioes(),
                barra_fontes_clicaveis,
                bloco_valor_gigante,
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True, controls=[botoes_per, botoes_estilo]),
                ft.Container(bgcolor="#0A1826", padding=14, border_radius=18, border=ft.border.all(1, "#21394C"), content=widget_grafico),
                grelha_6_indicadores_cbot,
                ft.Container(
                    bgcolor="#0A1826",
                    padding=14,
                    border_radius=16,
                    border=ft.border.all(1.5, "#FACC15"),
                    content=ft.ResponsiveRow(
                        spacing=10,
                        controls=[
                            ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0E2030", padding=10, border_radius=10, content=ft.Column([ft.Text("ESTIMATIVA +15 DIAS", color="#94A3B8", size=10), ft.Text(f"R$ {p15_uf:.2f}", color="#38BDF8", size=18, weight=ft.FontWeight.BOLD)])),
                            ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0E2030", padding=10, border_radius=10, content=ft.Column([ft.Text("ESTIMATIVA +30 DIAS", color="#94A3B8", size=10), ft.Text(f"R$ {p30_uf:.2f}", color="#A855F7", size=18, weight=ft.FontWeight.BOLD)])),
                            ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0E2030", padding=10, border_radius=10, content=ft.Column([ft.Text("ESTIMATIVA +60 DIAS", color="#94A3B8", size=10), ft.Text(f"R$ {p60_uf:.2f}", color="#10B981", size=18, weight=ft.FontWeight.BOLD)])),
                            ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0E2030", padding=10, border_radius=10, content=ft.Column([ft.Text("ESTIMATIVA +90 DIAS", color="#FACC15", size=10), ft.Text(f"R$ {p90_uf:.2f}", color="#FACC15", size=18, weight=ft.FontWeight.BOLD)])),
                        ],
                    ),
                ),
            ],
        ),
    )

  # =========================================================================
  # ABA 2: MAPA GEOGRÁFICO REAL DO BRASIL + SELETOR TRIPLO + GRÁFICO AO LADO
  # =========================================================================
  def construir_aba_mapa_clicavel():
    lat_sel = pino_mapa_selecionado["lat"]
    lon_sel = pino_mapa_selecionado["lon"]
    url_gmaps_rota = f"https://www.google.com/maps/dir/?api=1&destination={lat_sel},{lon_sel}&travelmode=driving"
    url_waze_rota = f"https://waze.com/ul?ll={lat_sel},{lon_sel}&navigate=yes"

    return ft.Container(
        bgcolor="#0E2030",
        padding=20,
        border_radius=24,
        border=ft.border.all(1.5, "#21394C"),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Text("🗺️ Brasil Cartográfico | Estados & Lavouras", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("Limites de estados com malha IBGE • pinos georreferenciados conforme coordenadas cadastradas.", color="#94A3B8", size=12),
                construir_seletor_triplo_regioes(),
                ft.ResponsiveRow(
                    spacing=16,
                    controls=[
                        ft.Container(col={"xs": 12, "lg": 6.5}, content=construir_widget_mapa_brasil_real()),
                        ft.Container(
                            col={"xs": 12, "lg": 5.5},
                            content=ft.Column(
                                spacing=12,
                                controls=[
                                    construir_mini_painel_grafico_mapa(modo_clima=False),
                                    ft.Container(
                                        bgcolor="#0A1826",
                                        padding=16,
                                        border_radius=18,
                                        border=ft.border.all(1.5, "#10B981"),
                                        content=ft.Column(
                                            spacing=8,
                                            controls=[
                                                ft.Text(pino_mapa_selecionado["titulo"], color="#10B981", size=15, weight=ft.FontWeight.BOLD),
                                                ft.Text(pino_mapa_selecionado["subtitulo"], color="#E2E8F0", size=12),
                                                ft.Text(f"📡 Coordenadas Satélite: Lat {lat_sel:.4f} | Lon {lon_sel:.4f}", color="#38BDF8", size=12, weight=ft.FontWeight.BOLD),
                                                ft.Row(
                                                    wrap=True,
                                                    spacing=8,
                                                    controls=[
                                                        ft.ElevatedButton("🚗 Caminho Mais Rápido (Google Maps)", bgcolor="#10B981", color="#080D16", height=36, on_click=lambda e: page.launch_url(url_gmaps_rota)),
                                                        ft.ElevatedButton("🚜 Abrir Waze GPS", bgcolor="#38BDF8", color="#080D16", height=36, on_click=lambda e: page.launch_url(url_waze_rota)),
                                                    ],
                                                ),
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ],
        ),
    )

  # =========================================================================
  # ABA 3: PERFIL ESTILO FACEBOOK + HISTÓRICO DA PARCERIA + MAPA GPS NO CLIENTE
  # =========================================================================
  def construir_aba_perfil_facebook():
    nonlocal sub_aba_perfil, usuario_logado_key, fonte_analise_ativa, cliente_em_edicao_id
    u_atual = db_usuarios["usuarios"][usuario_logado_key]
    clientes_u = u_atual.setdefault("clientes", [])
    agenda_u = u_atual.setdefault("agenda_vendas", [])
    alertas_u = u_atual.setdefault("alertas_preco", [])
    alertas_avaliados = avaliar_alertas_usuario()

    total_vendido_rs = sum(v.get("valor_total_liquido", 0.0) for v in agenda_u)
    total_comissao_rs = sum(v.get("comissao_reais", 0.0) for v in agenda_u)

    def mudar_sub_perfil(nova_sub):
      nonlocal sub_aba_perfil
      sub_aba_perfil = nova_sub
      renderizar()

    def sair_logout(e):
      nonlocal usuario_logado_key
      usuario_logado_key = None
      montar_sistema()

    # Cabeçalho Estilo Facebook com Foto Quadrada Arredondada Gigante (142x142)
    header_facebook = ft.Container(
        bgcolor="#0E2030",
        border_radius=24,
        border=ft.border.all(1.5, "#21394C"),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        content=ft.Column(
            spacing=0,
            controls=[
                ft.Container(
                    height=115,
                    width=float("inf"),
                    gradient=ft.LinearGradient(
                        begin=ft.alignment.top_left,
                        end=ft.alignment.bottom_right,
                        colors=["#064E3B", "#0F172A", "#1E3A8A"],
                    ),
                    padding=16,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Container(bgcolor="#0A1826", padding=8, border_radius=10, content=ft.Text(f"📍 Praça Padrão: {u_atual.get('cidade_padrao', 'São Borja - RS')}", color="#10B981", size=12, weight=ft.FontWeight.BOLD)),
                            ft.Container(bgcolor="#0A1826", padding=8, border_radius=10, content=ft.Text(f"📚 Fonte Base: {fonte_analise_ativa}", color="#FACC15", size=12, weight=ft.FontWeight.BOLD)),
                        ],
                    ),
                ),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=22, vertical=16),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                        controls=[
                            ft.Row(
                                spacing=20,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    obter_avatar_quadrado_grande(u_atual, largura=142, altura=142, raio=28),
                                    ft.Column(
                                        spacing=4,
                                        controls=[
                                            ft.Text(u_atual["nome"], color="#FFFFFF", size=26, weight=ft.FontWeight.BOLD),
                                            ft.Text(u_atual.get("cargo", "Consultor Comercial"), color="#10B981", size=14, weight=ft.FontWeight.W_600),
                                            ft.Text(u_atual.get("bio", ""), color="#94A3B8", size=12),
                                            ft.Row(
                                                spacing=16,
                                                controls=[
                                                    ft.Text(f"👥 {len(clientes_u)} Clientes Parceiros", color="#38BDF8", size=13, weight=ft.FontWeight.BOLD),
                                                    ft.Text(f"💰 R$ {total_vendido_rs:,.2f} na Agenda", color="#10B981", size=13, weight=ft.FontWeight.BOLD),
                                                    ft.Text(f"🏆 Comissão: R$ {total_comissao_rs:,.2f}", color="#FACC15", size=13, weight=ft.FontWeight.BOLD),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=8,
                                wrap=True,
                                controls=[
                                    ft.ElevatedButton("📸 Escolher Minha Foto Pessoal", bgcolor="#10B981", color="#080D16", height=40, on_click=escolher_foto),
                                    ft.ElevatedButton("⚙️ Fontes & Sites", bgcolor="#21394C", color="#FACC15", height=40, on_click=lambda e: mudar_sub_perfil("admin_supa")),
                                    ft.ElevatedButton("🔒 Sair", bgcolor="#450A0A", color="#FCA5A5", height=40, on_click=sair_logout),
                                ],
                            ),
                        ],
                    ),
                ),
                ft.Divider(height=1, color="#21394C"),
                ft.Container(
                    bgcolor="#0A1826",
                    padding=ft.padding.symmetric(horizontal=20, vertical=10),
                    content=ft.Row(
                        wrap=True,
                        spacing=10,
                        controls=[
                            ft.ElevatedButton("✓ 🚜 Clientes, Histórico de Parceria & Mapa GPS" if sub_aba_perfil == "clientes" else "🚜 Clientes, Histórico de Parceria & Mapa GPS", bgcolor="#10B981" if sub_aba_perfil == "clientes" else "#21394C", color="#080D16" if sub_aba_perfil == "clientes" else "#FFFFFF", height=38, on_click=lambda e: mudar_sub_perfil("clientes")),
                            ft.ElevatedButton("✓ 📰 Mural & Agenda de Vendas" if sub_aba_perfil == "agenda" else "📰 Mural & Agenda de Vendas", bgcolor="#10B981" if sub_aba_perfil == "agenda" else "#21394C", color="#080D16" if sub_aba_perfil == "agenda" else "#FFFFFF", height=38, on_click=lambda e: mudar_sub_perfil("agenda")),
                            ft.ElevatedButton(f"✓ 🔔 Alertas de Preço ({len(alertas_u)})" if sub_aba_perfil == "alertas" else f"🔔 Alertas de Preço ({len(alertas_u)})", bgcolor="#FACC15" if sub_aba_perfil == "alertas" else "#21394C", color="#080D16" if sub_aba_perfil == "alertas" else "#FACC15", height=38, on_click=lambda e: mudar_sub_perfil("alertas")),
                            ft.ElevatedButton("✓ ⚙️ Fontes Padrão, StoneX & Senha" if sub_aba_perfil == "admin_supa" else "⚙️ Fontes Padrão, StoneX & Senha", bgcolor="#38BDF8" if sub_aba_perfil == "admin_supa" else "#21394C", color="#080D16" if sub_aba_perfil == "admin_supa" else "#FFFFFF", height=38, on_click=lambda e: mudar_sub_perfil("admin_supa")),
                        ],
                    ),
                ),
            ],
        ),
    )

    coluna_apresentacao_esq = ft.Container(
        bgcolor="#0E2030",
        padding=18,
        border_radius=20,
        border=ft.border.all(1, "#21394C"),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Text("📌 Apresentação & Estatísticas da Carteira", color="#FFFFFF", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(u_atual.get("bio", ""), color="#CBD5E1", size=12),
                ft.Divider(color="#21394C"),
                ft.Text(f"📍 Sede Padrão: {u_atual.get('cidade_padrao', 'São Borja - RS')}", color="#10B981", size=13, weight=ft.FontWeight.BOLD),
                ft.Text(f"🌾 Área Total Assistida: {sum(c.get('hectares_soja', 0)+c.get('hectares_arroz', 0) for c in clientes_u):,.0f} ha", color="#38BDF8", size=13, weight=ft.FontWeight.BOLD),
                ft.Text(f"🤝 Volume Histórico Parcerias: R$ {sum(c.get('total_acumulado_reais', 0) for c in clientes_u):,.2f}", color="#FACC15", size=13, weight=ft.FontWeight.BOLD),
                ft.Divider(color="#21394C"),
                ft.Text("🚀 Ações Rápidas:", color="#FFFFFF", size=13, weight=ft.FontWeight.BOLD),
                ft.ElevatedButton("📸 Gerar Card Stories do Dia", bgcolor="#21394C", color="#10B981", width=float("inf"), on_click=lambda e: mudar_aba("stories")),
                ft.ElevatedButton("🤖 Consultar IA com Voz", bgcolor="#21394C", color="#FACC15", width=float("inf"), on_click=lambda e: mudar_aba("ia_voz")),
            ],
        ),
    )

    feed_direita = ft.Container()

    # SUB-ABA CLIENTES: COM ESTATÍSTICAS DE PARCERIA, HISTÓRICO DE SAFRAS E MAPA LOCAL INTEGRADO
    if sub_aba_perfil == "clientes":
      c_nome = ft.TextField(label="Nome do Produtor / Escritório", bgcolor="#0A1826", color="#FFFFFF", width=230)
      c_prop = ft.TextField(label="Fazenda / Sede no Interior", bgcolor="#0A1826", color="#FFFFFF", width=210)
      c_cid = ft.TextField(label="Município - UF", value="São Borja - RS", bgcolor="#0A1826", color="#FFFFFF", width=150)
      c_zap = ft.TextField(label="WhatsApp", value="", bgcolor="#0A1826", color="#FFFFFF", width=150)
      c_soja = ft.TextField(label="Soja (ha)", value="0", bgcolor="#0A1826", color="#FFFFFF", width=105)
      c_arroz = ft.TextField(label="Arroz (ha)", value="0", bgcolor="#0A1826", color="#FFFFFF", width=105)
      c_rot = ft.TextField(label="Roteiro da Lavoura no Interior", value="BR-472 km 18, entrada à esquerda", bgcolor="#0A1826", color="#FFFFFF", width=250)
      c_lat = ft.TextField(label="Latitude GPS", value="-28.725", bgcolor="#0A1826", color="#FFFFFF", width=125)
      c_lon = ft.TextField(label="Longitude GPS", value="-55.910", bgcolor="#0A1826", color="#FFFFFF", width=125)
      c_hist = ft.TextField(label="Resumo Histórico da Parceria / Safras Anteriores", value="", bgcolor="#0A1826", color="#FFFFFF", width=380)

      def salvar_cli(e):
        if not c_nome.value.strip():
          return
        try:
          lat_in = numero_usuario(c_lat.value, -35, 6)
          lon_in = numero_usuario(c_lon.value, -75, -30)
          ha_soja = numero_usuario(c_soja.value or 0, 0)
          ha_arroz = numero_usuario(c_arroz.value or 0, 0)
        except (TypeError, ValueError):
          mostrar_aviso("Confira hectares e coordenadas GPS (latitude/longitude).", "#EF4444")
          return
        clientes_u.insert(0, {
            "id": f"cli_{len(clientes_u)+1}",
            "nome": c_nome.value.strip(),
            "tipo": "Produtor Parceiro",
            "propriedade": c_prop.value.strip() or "Sede Principal",
            "cidade_uf": c_cid.value.strip(),
            "cpf_cnpj": "",
            "whatsapp": "".join(ch for ch in c_zap.value if ch.isdigit()),
            "hectares_soja": ha_soja,
            "hectares_arroz": ha_arroz,
            "hectares_inverno": 200,
            "tem_silo": "Sim (Silo Próprio)",
            "endereco_escritorio": f"Centro, {c_cid.value.strip()}",
            "lat_escritorio": -28.66,
            "lon_escritorio": -56.00,
            "roteiro_lavoura": c_rot.value.strip(),
            "lat_lavoura": lat_in,
            "lon_lavoura": lon_in,
            "anos_parceria": "Parceria Ativa Registrada",
            "indice_fidelidade": "100% (Cliente Fidelizado)",
            "total_acumulado_sacas": 0,
            "total_acumulado_reais": 0.00,
            "historico_parceria": [c_hist.value.strip()],
        })
        salvar_banco_usuarios(db_usuarios)
        mostrar_aviso("🚜 Cliente cadastrado com Estatísticas de Parceria e Mapa GPS!")
        renderizar()

      def abrir_pasta_cliente(ident):
        nonlocal sub_aba_perfil, cliente_em_edicao_id
        cliente_em_edicao_id = ident
        sub_aba_perfil = "ficha_cliente"
        renderizar()

      cards_clientes_completos = ft.Column(spacing=14)
      campo_pesquisa_clientes = ft.TextField(label="🔎 Buscar cliente / fazenda / cidade", hint_text="Digite para filtrar sua carteira", width=410)
      index_clientes = []
      def filtrar_clientes(e):
        busca = (campo_pesquisa_clientes.value or "").casefold().strip()
        for controle, texto in index_clientes:
          controle.visible = busca in texto
        page.update()
      campo_pesquisa_clientes.on_change = filtrar_clientes
      for c in clientes_u:
        lat_l = float(c.get("lat_lavoura", -28.725))
        lon_l = float(c.get("lon_lavoura", -55.910))
        sacas_sem_soja = int((c.get("hectares_soja", 0) * 65) / 40)
        sacas_sem_arroz = int((c.get("hectares_arroz", 0) * 100) / 40)

        linhas_hist_ui = ft.Column(spacing=4)
        for h_str in c.get("historico_parceria", ["Safra Atual em andamento"]):
          linhas_hist_ui.controls.append(
              ft.Row(
                  spacing=6,
                  controls=[
                      ft.Icon(ft.icons.HISTORY_EDU_ROUNDED, color="#FACC15", size=16),
                      ft.Text(h_str, color="#E2E8F0", size=12, expand=True),
                  ],
              )
          )

        cards_clientes_completos.controls.append(
            ft.Container(
                bgcolor="#0E2030",
                padding=20,
                border_radius=22,
                border=ft.border.all(1.5, "#21394C"),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            wrap=True,
                            controls=[
                                ft.Column([
                                    ft.Text(f"👤 {c['nome']} — 🏡 {c['propriedade']} ({c['cidade_uf']})", color="#FFFFFF", size=18, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"🤝 {c.get('anos_parceria', '3 Safras')} • ⭐ Fidelidade: {c.get('indice_fidelidade', '95%')}", color="#10B981", size=13, weight=ft.FontWeight.BOLD),
                                ]),
                                ft.Row(
                                    spacing=8, wrap=True,
                                    controls=[
                                        ft.ElevatedButton("📁 Abrir pasta / Editar Cliente", bgcolor="#FACC15", color="#0A1826", height=36, on_click=lambda e, ident=c.get("id"): abrir_pasta_cliente(ident)),
                                        ft.ElevatedButton("🚗 Rota Rápida p/ Lavoura (Google Maps)", bgcolor="#10B981", color="#080D16", height=36, on_click=lambda e, la=lat_l, lo=lon_l: page.launch_url(f"https://www.google.com/maps/dir/?api=1&destination={la},{lo}&travelmode=driving")),
                                        ft.ElevatedButton("🚜 Waze GPS", bgcolor="#38BDF8", color="#080D16", height=36, on_click=lambda e, la=lat_l, lo=lon_l: page.launch_url(f"https://waze.com/ul?ll={la},{lo}&navigate=yes")),
                                        ft.ElevatedButton("📲 WhatsApp", bgcolor="#052E16", color="#22C55E", height=36, on_click=lambda e, z=c["whatsapp"]: page.launch_url(f"https://wa.me/{z}")),
                                    ],
                                ),
                            ],
                        ),
                        ft.Row(wrap=True, spacing=12, controls=[
                            ft.Text(f"📦 {len(c.get('pedidos', []))} pedidos", color="#38BDF8", size=12),
                            ft.Text(f"📝 {len(c.get('anotacoes', []))} anotações", color="#A5B4FC", size=12),
                            ft.Text(f"🔔 {sum(1 for lemb in c.get('lembretes', []) if not lemb.get('concluido'))} alertas pendentes", color="#FACC15", size=12),
                        ]),
                        # Painel de Estatísticas de Parceria do Cliente
                        ft.ResponsiveRow(
                            spacing=10,
                            controls=[
                                ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0A1826", padding=10, border_radius=12, content=ft.Column([ft.Text("VOLUME ACUMULADO", color="#94A3B8", size=10), ft.Text(f"{c.get('total_acumulado_sacas', 4850):,.0f} Sacas", color="#38BDF8", size=16, weight=ft.FontWeight.BOLD)])),
                                ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0A1826", padding=10, border_radius=12, content=ft.Column([ft.Text("MOVIMENTAÇÃO PARCERIA", color="#94A3B8", size=10), ft.Text(f"R$ {c.get('total_acumulado_reais', 642500):,.2f}", color="#10B981", size=16, weight=ft.FontWeight.BOLD)])),
                                ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0A1826", padding=10, border_radius=12, content=ft.Column([ft.Text("ÁREA SOJA / ARROZ", color="#94A3B8", size=10), ft.Text(f"{c.get('hectares_soja', 450):.0f} ha / {c.get('hectares_arroz', 300):.0f} ha", color="#FACC15", size=15, weight=ft.FontWeight.BOLD)])),
                                ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0A1826", padding=10, border_radius=12, content=ft.Column([ft.Text("DEMANDA DE SEMENTES", color="#94A3B8", size=10), ft.Text(f"~{sacas_sem_soja} sc Soja | ~{sacas_sem_arroz} sc Arroz", color="#A855F7", size=13, weight=ft.FontWeight.BOLD)])),
                            ],
                        ),
                        # Histórico Safra a Safra + Mapa Geográfico Local da Fazenda Lado a Lado
                        ft.ResponsiveRow(
                            spacing=14,
                            controls=[
                                ft.Container(
                                    col={"xs": 12, "md": 5.5},
                                    bgcolor="#0A1826",
                                    padding=14,
                                    border_radius=14,
                                    border=ft.border.all(1, "#21394C"),
                                    content=ft.Column(
                                        spacing=6,
                                        controls=[
                                            ft.Text("📜 Histórico de Parceria & Compras por Safra:", color="#FACC15", size=13, weight=ft.FontWeight.BOLD),
                                            linhas_hist_ui,
                                            ft.Divider(color="#21394C"),
                                            ft.Text(f"🏢 Escritório: {c.get('endereco_escritorio', '')}", color="#94A3B8", size=11),
                                            ft.Text(f"🚜 Roteiro Interior: {c.get('roteiro_lavoura', '')}", color="#38BDF8", size=11),
                                        ],
                                    ),
                                ),
                                ft.Container(
                                    col={"xs": 12, "md": 6.5},
                                    content=ft.Column(spacing=7, controls=[
                                        ft.Image(src=url_mapa_osm_cliente(lat_l, lon_l), height=195,
                                            fit=ft.ImageFit.CONTAIN),
                                        ft.Text("Mapa de ruas (OpenStreetMap). Coordenadas cadastradas, não imagem de satélite nem rota calculada.",
                                            color="#94A3B8", size=10),
                                        ft.TextButton("Abrir mapa real da fazenda", on_click=lambda e, la=lat_l, lo=lon_l:
                                            page.launch_url(f"https://www.google.com/maps?q={la},{lo}")),
                                    ]),
                                ),
                            ],
                        ),
                    ],
                ),
            )
        )

      for indice_cli, cliente in enumerate(clientes_u):
        if indice_cli < len(cards_clientes_completos.controls):
          index_clientes.append((cards_clientes_completos.controls[indice_cli],
              (cliente.get("nome", "") + " " + cliente.get("propriedade", "") + " " + cliente.get("cidade_uf", "")).casefold()))

      feed_direita = ft.Column(
          spacing=14,
          controls=[
              campo_pesquisa_clientes,
              ft.Container(
                  bgcolor="#0E2030",
                  padding=18,
                  border_radius=20,
                  border=ft.border.all(1, "#10B981"),
                  content=ft.Column(
                      spacing=10,
                      controls=[
                          ft.Text("🚜 Cadastrar Produtor / Escritório com Histórico de Parceria & Mapa GPS", color="#FFFFFF", size=17, weight=ft.FontWeight.BOLD),
                          ft.Row(wrap=True, spacing=8, controls=[c_nome, c_prop, c_cid, c_zap, c_soja, c_arroz, c_rot, c_lat, c_lon, c_hist]),
                          ft.ElevatedButton("💾 Guardar Cliente com Mapa & Estatísticas", bgcolor="#10B981", color="#080D16", height=42, on_click=salvar_cli),
                      ],
                  ),
              ),
              ft.Container(bgcolor="#241F16", padding=14, border_radius=14,
                  border=ft.border.all(1, "#FACC15"),
                  content=ft.Column(spacing=7, controls=[
                      ft.Text("🔔 ALERTAS DA CARTEIRA", color="#FACC15", size=14, weight=ft.FontWeight.BOLD),
                      *[ft.Text(f"{cli.get('nome','')}: {lemb.get('texto','')} · {situacao_lembrete_cliente(lemb)[0]}",
                                color=situacao_lembrete_cliente(lemb)[1], size=12)
                        for cli in clientes_u for lemb in cli.get("lembretes", [])
                        if not lemb.get("concluido") and (
                            situacao_lembrete_cliente(lemb)[0].startswith("Atrasado") or
                            situacao_lembrete_cliente(lemb)[0].startswith("Em ") or
                            situacao_lembrete_cliente(lemb)[0] == "Vence hoje")][:15],
                      ft.Text("Abra a pasta de cada cliente para conferir todos os prazos e alertas.", color="#94A3B8", size=11),
                  ])),
              cards_clientes_completos,
          ],
      )

    elif sub_aba_perfil == "ficha_cliente":
      cliente = next((x for x in clientes_u if x.get("id") == cliente_em_edicao_id), None)
      if cliente is None:
        feed_direita = ft.Text("Cliente não encontrado. Volte à carteira.", color="#FB7185")
      else:
        def voltar_lista(e=None):
          nonlocal sub_aba_perfil
          sub_aba_perfil = "clientes"
          renderizar()

        def campo(titulo, chave, largura=220, multiline=False):
          return ft.TextField(label=titulo, value=str(cliente.get(chave, "")), width=largura,
                              bgcolor="#0A1826", color="#FFFFFF", border_radius=10,
                              multiline=multiline, min_lines=2 if multiline else 1, max_lines=5 if multiline else 1)

        f_nome = campo("Nome do cliente / produtor", "nome", 290)
        f_tipo = campo("Tipo de cliente", "tipo", 185)
        f_documento = campo("CPF / CNPJ", "cpf_cnpj", 180)
        f_zap = campo("WhatsApp com DDD", "whatsapp", 190)
        f_email = campo("E-mail", "email", 270)
        f_prop = campo("Nome da propriedade", "propriedade", 280)
        f_cidade = campo("Cidade / UF", "cidade_uf", 190)
        f_endereco = campo("Endereço do escritório", "endereco_escritorio", 300)
        f_rot = campo("Roteiro / acessos à lavoura", "roteiro_lavoura", 430, True)
        f_lat = campo("Latitude", "lat_lavoura", 160)
        f_lon = campo("Longitude", "lon_lavoura", 160)
        f_soja = campo("Soja (ha)", "hectares_soja", 135)
        f_arroz = campo("Arroz (ha)", "hectares_arroz", 135)
        f_inverno = campo("Culturas de inverno (ha)", "hectares_inverno", 200)
        f_silo = campo("Armazenamento / silo", "tem_silo", 270)
        f_parceria = campo("Tempo de parceria", "anos_parceria", 290)
        f_fidel = campo("Avaliação comercial", "indice_fidelidade", 270)
        f_resumo = ft.TextField(label="Observações gerais permanentes", value=cliente.get("observacoes_gerais", ""),
                                multiline=True, min_lines=3, max_lines=6, bgcolor="#0A1826", color="#FFFFFF")

        def salvar_dados_cliente(e):
          if not (f_nome.value or "").strip():
            mostrar_aviso("Informe o nome do cliente.", "#EF4444")
            return
          try:
            novos_num = {"hectares_soja": numero_usuario(f_soja.value or "0", 0),
                         "hectares_arroz": numero_usuario(f_arroz.value or "0", 0),
                         "hectares_inverno": numero_usuario(f_inverno.value or "0", 0),
                         "lat_lavoura": numero_usuario(f_lat.value, -35, 6),
                         "lon_lavoura": numero_usuario(f_lon.value, -75, -30)}
          except (ValueError, TypeError):
            mostrar_aviso("Confira hectares e coordenadas GPS antes de salvar.", "#EF4444")
            return
          mapa_txt = {"nome": f_nome, "tipo": f_tipo, "cpf_cnpj": f_documento,
                      "whatsapp": f_zap, "email": f_email, "propriedade": f_prop,
                      "cidade_uf": f_cidade, "endereco_escritorio": f_endereco,
                      "roteiro_lavoura": f_rot, "tem_silo": f_silo,
                      "anos_parceria": f_parceria, "indice_fidelidade": f_fidel}
          for chave, ctrl in mapa_txt.items():
            cliente[chave] = (ctrl.value or "").strip()[:1200 if chave == "roteiro_lavoura" else 280]
          cliente.update(novos_num)
          cliente["observacoes_gerais"] = (f_resumo.value or "").strip()[:4000]
          salvar_banco_usuarios(db_usuarios)
          mostrar_aviso("Ficha do cliente salva com sucesso!")
          renderizar()

        # PEDIDOS: registro individual, status, data, valor, notas e edição.
        pedidos = cliente.setdefault("pedidos", [])
        pedido_em_edicao = {"id": None}
        p_prod = ft.TextField(label="Produto / serviço", bgcolor="#0A1826", color="#FFFFFF", width=210)
        p_data = ft.TextField(label="Data (dd/mm/aaaa)", value=datetime.now().strftime("%d/%m/%Y"),
                              bgcolor="#0A1826", color="#FFFFFF", width=160)
        p_qtd = ft.TextField(label="Quantidade", value="1", bgcolor="#0A1826", color="#FFFFFF", width=135)
        p_valor = ft.TextField(label="Valor total (R$)", value="0", bgcolor="#0A1826", color="#FFFFFF", width=160)
        p_status = ft.Dropdown(label="Situação", width=180, value="Em negociação", bgcolor="#0A1826", color="#FFFFFF",
                options=[ft.dropdown.Option(v) for v in ("Em negociação", "Confirmado", "Entregue", "Cancelado")])
        p_obs = ft.TextField(label="Observações do pedido", bgcolor="#0A1826", color="#FFFFFF", multiline=True, min_lines=2, max_lines=4)

        def editar_pedido(ident):
          pedido = next((p for p in pedidos if p.get("id") == ident), None)
          if pedido is None:
            return
          pedido_em_edicao["id"] = ident
          p_prod.value = pedido.get("produto", "")
          p_data.value = pedido.get("data", "")
          p_qtd.value = str(pedido.get("quantidade", 0))
          p_valor.value = str(pedido.get("valor", 0))
          p_status.value = pedido.get("status", "Em negociação")
          p_obs.value = pedido.get("obs", "")
          page.update()

        def salvar_pedido(e):
          if not (p_prod.value or "").strip():
            mostrar_aviso("Informe o produto ou serviço do pedido.", "#EF4444")
            return
          try:
            datetime.strptime(p_data.value.strip(), "%d/%m/%Y")
            qtd = numero_usuario(p_qtd.value or 0, 0)
            valor = numero_usuario(p_valor.value or 0, 0)
          except (ValueError, TypeError):
            mostrar_aviso("Confira data, quantidade e valor do pedido.", "#EF4444")
            return
          atual = next((p for p in pedidos if p.get("id") == pedido_em_edicao["id"]), None)
          if atual is None:
            atual = {"id": "ped_" + secrets.token_hex(7), "criado_em": agora_str()}
            pedidos.insert(0, atual)
          atual.update({"produto": p_prod.value.strip()[:250], "data": p_data.value.strip(),
                        "quantidade": qtd, "valor": valor, "status": p_status.value,
                        "obs": (p_obs.value or "").strip()[:2000]})
          salvar_banco_usuarios(db_usuarios)
          mostrar_aviso("Pedido registrado na pasta do cliente!")
          renderizar()

        cards_pedidos = []
        for pedido in pedidos:
          cards_pedidos.append(ft.Container(bgcolor="#0A1826", padding=12, border_radius=10,
              content=ft.Row(wrap=True, spacing=10, controls=[
                  ft.Icon(ft.icons.SHOPPING_BAG_OUTLINED, color="#38BDF8", size=18),
                  ft.Text(f"{pedido.get('data','')} · {pedido.get('produto','')} · {pedido.get('quantidade','')} un · {dinheiro_br(pedido.get('valor',0))}",
                          color="#FFFFFF", size=12),
                  ft.Text(pedido.get("status", ""), color="#6EE7B7", size=12),
                  ft.TextButton("Editar", on_click=lambda e, ident=pedido.get("id"): editar_pedido(ident)),
              ])))

        # ANOTAÇÕES: linha de tempo interna da negociação.
        anotacoes = cliente.setdefault("anotacoes", [])
        anotacao_txt = ft.TextField(label="Anotação / histórico de contato", hint_text="Ex.: visita, preferência, proposta...",
                                   multiline=True, min_lines=3, max_lines=5, bgcolor="#0A1826", color="#FFFFFF")
        def salvar_anotacao(e):
          texto = (anotacao_txt.value or "").strip()
          if not texto:
            mostrar_aviso("Escreva uma anotação antes de salvar.", "#EAB308")
            return
          anotacoes.insert(0, {"id": secrets.token_hex(7), "data": agora_str(), "texto": texto[:3000]})
          salvar_banco_usuarios(db_usuarios)
          mostrar_aviso("Anotação guardada na pasta do cliente.")
          renderizar()

        # ALERTAS e lembretes por cliente, com prazo e conclusão independente.
        lembretes = cliente.setdefault("lembretes", [])
        lemb_txt = ft.TextField(label="Alerta / tarefa", hint_text="Ex.: telefonar, renovar contrato, confirmar entrega",
                               bgcolor="#0A1826", color="#FFFFFF", width=420)
        lemb_data = ft.TextField(label="Vencimento (dd/mm/aaaa)", value=(datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y"),
                                 bgcolor="#0A1826", color="#FFFFFF", width=200)
        lemb_prioridade = ft.Dropdown(label="Prioridade", value="Alta", bgcolor="#0A1826", color="#FFFFFF", width=160,
                            options=[ft.dropdown.Option(v) for v in ("Baixa", "Normal", "Alta", "Urgente")])
        def novo_lembrete(e):
          texto = (lemb_txt.value or "").strip()
          try:
            datetime.strptime(lemb_data.value.strip(), "%d/%m/%Y")
          except (ValueError, TypeError):
            mostrar_aviso("Use data dd/mm/aaaa no alerta.", "#EF4444")
            return
          if not texto:
            mostrar_aviso("Descreva o alerta do cliente.", "#EF4444")
            return
          lembretes.insert(0, {"id": secrets.token_hex(7), "texto": texto[:450], "data": lemb_data.value.strip(),
                               "prioridade": lemb_prioridade.value, "concluido": False, "criado_em": agora_str()})
          salvar_banco_usuarios(db_usuarios)
          mostrar_aviso("Alerta criado. Ele aparecerá na ficha com prazo e situação.")
          renderizar()

        def alternar_lembrete(ident):
          item = next((a for a in lembretes if a.get("id") == ident), None)
          if item:
            item["concluido"] = not item.get("concluido", False)
            salvar_banco_usuarios(db_usuarios)
            renderizar()

        lista_alertas = []
        for lemb in sorted(lembretes, key=lambda a: (bool(a.get("concluido")), datetime.strptime(a.get("data", "31/12/2999"), "%d/%m/%Y") if re.fullmatch(r"\d{2}/\d{2}/\d{4}", a.get("data", "")) else datetime.max)):
          sit, cor = situacao_lembrete_cliente(lemb)
          lista_alertas.append(ft.Container(bgcolor="#0A1826", padding=12, border_radius=11,
              content=ft.Row(wrap=True, spacing=10, controls=[
                  ft.Icon(ft.icons.NOTIFICATIONS_ACTIVE_OUTLINED, color=cor, size=20),
                  ft.Column(spacing=3, controls=[ft.Text(lemb.get("texto", ""), color="#FFFFFF", size=13),
                                             ft.Text(f"{lemb.get('data','')} · {lemb.get('prioridade','Normal')} · {sit}", color=cor, size=11)]),
                  ft.TextButton("Reabrir" if lemb.get("concluido") else "Concluir",
                                on_click=lambda e, ident=lemb.get("id"): alternar_lembrete(ident)),
              ])))

        def secao(titulo, controles, cor="#21394C"):
          return ft.Container(bgcolor="#0E2030", border_radius=16, padding=18,
               border=ft.border.all(1, cor), content=ft.Column(spacing=12,
                   controls=[ft.Text(titulo, size=18, color="#FFFFFF", weight=ft.FontWeight.BOLD)] + controles))

        feed_direita = ft.Column(spacing=16, controls=[
            ft.Row(wrap=True, spacing=10, controls=[
                ft.ElevatedButton("← Voltar à carteira", bgcolor="#21394C", color="#FFFFFF", on_click=voltar_lista),
                ft.Text(f"📁 Pasta do cliente: {cliente.get('nome','')}", color="#6EE7B7", size=20, weight=ft.FontWeight.BOLD),
            ]),
            ft.Text("Dados e pedidos ficam associados somente a esta ficha, sem apagar o histórico anterior.", color="#94A3B8", size=12),
            secao("Dados do cliente e da propriedade", [
                ft.Row(wrap=True, spacing=12, controls=[f_nome, f_tipo, f_documento, f_zap, f_email, f_prop, f_cidade, f_endereco]),
                ft.Row(wrap=True, spacing=12, controls=[f_soja, f_arroz, f_inverno, f_silo, f_lat, f_lon]),
                ft.Row(wrap=True, spacing=12, controls=[f_parceria, f_fidel, f_rot]),
                f_resumo,
                ft.ElevatedButton("Salvar alterações do cliente", bgcolor="#10B981", color="#06121B", on_click=salvar_dados_cliente),
            ], "#10B981"),
            secao(f"Pedidos e negociações ({len(pedidos)})", [
                ft.Row(wrap=True, spacing=10, controls=[p_prod, p_data, p_qtd, p_valor, p_status]),
                p_obs,
                ft.ElevatedButton("Salvar pedido (novo ou editado)", bgcolor="#38BDF8", color="#07111C", on_click=salvar_pedido),
                ft.Column(controls=cards_pedidos) if cards_pedidos else ft.Text("Nenhum pedido registrado.", color="#94A3B8"),
            ]),
            secao(f"Diário de relacionamento ({len(anotacoes)})", [
                anotacao_txt, ft.ElevatedButton("Adicionar anotação", bgcolor="#A5B4FC", color="#07111C", on_click=salvar_anotacao),
                ft.Column(spacing=8, controls=[ft.Container(bgcolor="#0A1826", padding=12, border_radius=10,
                   content=ft.Column(spacing=4, controls=[ft.Text(n.get("data", ""), color="#A5B4FC", size=11),
                     ft.Text(n.get("texto", ""), color="#FFFFFF", size=13)])) for n in anotacoes[:80]]) if anotacoes else ft.Text("Nenhuma anotação registrada.", color="#94A3B8"),
            ]),
            secao(f"Alertas e tarefas do cliente ({len(lembretes)})", [
                ft.Text("Alertas por data aparecem nesta ficha; não enviam mensagens automáticas fora do aplicativo.", color="#94A3B8", size=12),
                ft.Row(wrap=True, spacing=10, controls=[lemb_txt, lemb_data, lemb_prioridade]),
                ft.ElevatedButton("Criar alerta com vencimento", bgcolor="#FACC15", color="#07111C", on_click=novo_lembrete),
                ft.Column(spacing=8, controls=lista_alertas) if lista_alertas else ft.Text("Nenhum alerta definido.", color="#94A3B8"),
            ], "#FACC15"),
        ])

    elif sub_aba_perfil == "agenda":
      opcoes_cli = [c["nome"] for c in clientes_u] if clientes_u else ["Produtor Avulso"]
      ag_cli = ft.Dropdown(label="Cliente", bgcolor="#0A1826", color="#FFFFFF", width=220, options=[ft.dropdown.Option(n) for n in opcoes_cli], value=opcoes_cli[0])
      ag_prod = ft.Dropdown(label="Produto", bgcolor="#0A1826", color="#FFFFFF", width=190, options=[ft.dropdown.Option(i["nome_curto"]) for i in dados["itens"]], value=dados["itens"][0]["nome_curto"])
      ag_qtd = ft.TextField(label="Qtd (Sacas/Kg)", value="1000", bgcolor="#0A1826", color="#FFFFFF", width=125)
      ag_preco = ft.TextField(label="Valor Unit. (R$)", value="73.00", bgcolor="#0A1826", color="#FFFFFF", width=125)
      ag_frete_sc = ft.TextField(label="Frete/Saca (R$)", value="2.20", bgcolor="#0A1826", color="#FFFFFF", width=125)
      ag_obs = ft.TextField(label="Observações da Negociação", value="Entrega programada na sede da fazenda", bgcolor="#0A1826", color="#FFFFFF", expand=True)

      def publicar_venda(e):
        try:
          qtd = float(ag_qtd.value.replace(",", "."))
          pr = float(ag_preco.value.replace(",", "."))
          fr_sc = float(ag_frete_sc.value.replace(",", "."))
          liq_sc = pr - fr_sc
          tot_liq = qtd * liq_sc
          agenda_u.insert(0, {
              "id": f"ag_{len(agenda_u)+1}",
              "data_visita": datetime.now().strftime("%d/%m/%Y"),
              "cliente_nome": ag_cli.value,
              "produto": ag_prod.value,
              "quantidade": qtd,
              "preco_unitario": pr,
              "tem_frete": "Com Frete (CIF)",
              "km_frete": 85,
              "custo_frete_saca": fr_sc,
              "preco_liquido_saca": liq_sc,
              "valor_total_liquido": tot_liq,
              "comissao_pct": 1.5,
              "comissao_reais": tot_liq * 0.015,
              "status": "Venda Fechada",
              "obs": ag_obs.value,
          })
          salvar_banco_usuarios(db_usuarios)
          mostrar_aviso("✅ Venda registada na Agenda Comercial!")
          renderizar()
        except Exception:
          pass

      feed_direita = ft.Column(
          spacing=12,
          controls=[
              ft.Container(
                  bgcolor="#0E2030",
                  padding=18,
                  border_radius=20,
                  content=ft.Column(
                      spacing=10,
                      controls=[
                          ft.Text("✍️ Registar Nova Venda / Agendamento Comercial", color="#FFFFFF", size=17, weight=ft.FontWeight.BOLD),
                          ft.Row(wrap=True, spacing=8, controls=[ag_cli, ag_prod, ag_qtd, ag_preco, ag_frete_sc]),
                          ft.Row(wrap=True, spacing=10, controls=[ag_obs, ft.ElevatedButton("➕ Publicar na Agenda", bgcolor="#10B981", color="#080D16", on_click=publicar_venda)]),
                      ],
                  ),
              ),
              ft.Column(
                  spacing=10,
                  controls=[
                      ft.Container(
                          bgcolor="#0E2030",
                          padding=16,
                          border_radius=18,
                          content=ft.Column([
                              ft.Text(f"📅 {v['data_visita']} • {v['cliente_nome']} — {v['produto']} ({v['quantidade']:,.0f} un)", color="#FFFFFF", size=16, weight=ft.FontWeight.BOLD),
                              ft.Text(f"💰 Líquido: R$ {v['preco_liquido_saca']:.2f}/un ➔ Total: R$ {v['valor_total_liquido']:,.2f} | Comissão: R$ {v['comissao_reais']:,.2f}", color="#10B981", size=14, weight=ft.FontWeight.BOLD),
                          ]),
                      )
                      for v in agenda_u
                  ],
              ),
          ],
      )

    elif sub_aba_perfil == "alertas":
      al_prod = ft.Dropdown(label="Produto", bgcolor="#0A1826", color="#FFFFFF", width=210, options=[ft.dropdown.Option(i["nome_curto"]) for i in dados["itens"]], value=dados["itens"][0]["nome_curto"])
      al_alvo = ft.TextField(label="Preço-Alvo (R$)", value="74.50", bgcolor="#0A1826", color="#FFFFFF", width=150)

      def add_al(e):
        try:
          alvo_novo = numero_usuario(al_alvo.value, 0.01)
        except (ValueError, TypeError):
          mostrar_aviso("Digite um preço-alvo válido.", "#EF4444")
          return
        alertas_u.insert(0, {
            "id": f"al_{len(alertas_u)+1}",
            "cliente_nome": clientes_u[0]["nome"] if clientes_u else "Minha Carteira",
            "whatsapp": "5555999887766",
            "produto": al_prod.value,
            "uf": uf_selecionada,
            "tipo_gatilho": "Alta (Venda >= Alvo)",
            "valor_alvo": alvo_novo,
            "lote_sacas": 1000,
            "criado_em": agora_str(),
        })
        salvar_banco_usuarios(db_usuarios)
        mostrar_aviso("🔔 Alerta adicionado!")
        renderizar()

      feed_direita = ft.Container(
          bgcolor="#0E2030",
          padding=20,
          border_radius=20,
          content=ft.Column(
              spacing=12,
              controls=[
                  ft.Text("🔔 Gatilhos e Alertas de Preço-Alvo", color="#FFFFFF", size=18, weight=ft.FontWeight.BOLD),
                  ft.Row(wrap=True, spacing=10, controls=[al_prod, al_alvo, ft.ElevatedButton("➕ Criar Alerta", bgcolor="#FACC15", color="#080D16", on_click=add_al)]),
                  ft.Column(
                      spacing=8,
                      controls=[
                          ft.Container(bgcolor="#0A1826", padding=14, border_radius=14, border=ft.border.all(1.5, a["cor_al"]), content=ft.Text(f"{a['status_al']} • {a['produto']} ({a['uf']}): Hoje R$ {a['preco_hoje']:.2f} vs Alvo R$ {a['valor_alvo']:.2f}", color=a["cor_al"], size=14, weight=ft.FontWeight.BOLD))
                          for a in alertas_avaliados
                      ],
                  ),
              ],
          ),
      )

    else:
      dd_fonte_padrao = ft.Dropdown(
          label="🌐 Fonte Padrão Inicial (Chicago SRW, StoneX, CEPEA, Emater/IRGA...)",
          bgcolor="#0A1826",
          color="#FFFFFF",
          width=520,
          options=[ft.dropdown.Option(k) for k in FONTES_DISPONIVEIS.keys()],
          value=fonte_analise_ativa,
      )
      inp_site_custom = ft.TextField(label="🔗 Site Adicional Salvo (ex: StoneX / Agrolink)", value=u_atual.get("site_extra_usuario", "https://www.stonex.com/pt-br/inteligencia-de-mercado/"), bgcolor="#0A1826", color="#FFFFFF", width=520)
      inp_nome_perfil = ft.TextField(label="Nome exibido no perfil", value=u_atual.get("nome", ""), width=420)
      inp_bio_perfil = ft.TextField(label="Apresentação profissional", value=u_atual.get("bio", ""), multiline=True, min_lines=2, max_lines=4, width=520)
      senha_antiga = ft.TextField(label="Senha atual", password=True, width=210)
      senha_nova = ft.TextField(label="Nova senha (mínimo 10 caracteres)", password=True, width=275)
      senha_repetir = ft.TextField(label="Repetir nova senha", password=True, width=240)

      def atualizar_perfil(e):
        nome = inp_nome_perfil.value.strip()
        if len(nome) < 2:
          mostrar_aviso("Digite um nome válido para o perfil.", "#EF4444")
          return
        u_atual["nome"] = nome[:100]
        u_atual["bio"] = inp_bio_perfil.value.strip()[:650]
        salvar_banco_usuarios(db_usuarios)
        mostrar_aviso("Dados do perfil atualizados!")
        renderizar()

      def atualizar_senha(e):
        atual = senha_antiga.value or ""
        nova = senha_nova.value or ""
        if not verificar_senha(atual, u_atual.get("senha_hash", "")):
          mostrar_aviso("Senha atual incorreta.", "#EF4444")
          return
        if len(nova) < 10 or not any(c.isdigit() for c in nova) or not any(c.isalpha() for c in nova):
          mostrar_aviso("A senha deve ter 10 caracteres ou mais, letras e números.", "#EF4444")
          return
        if nova != senha_repetir.value:
          mostrar_aviso("As novas senhas não coincidem.", "#EF4444")
          return
        u_atual["senha_hash"] = criar_hash_senha_segura(nova)
        salvar_banco_usuarios(db_usuarios)
        senha_antiga.value = senha_nova.value = senha_repetir.value = ""
        mostrar_aviso("Senha atualizada com proteção PBKDF2!")
        renderizar()

      def guardar_cfg(e):
        nonlocal fonte_analise_ativa
        fonte_analise_ativa = dd_fonte_padrao.value
        u_atual["fonte_preferida"] = dd_fonte_padrao.value
        u_atual["site_extra_usuario"] = inp_site_custom.value.strip()
        salvar_banco_usuarios(db_usuarios)
        mostrar_aviso("✅ Fonte padrão e links guardados!")
        renderizar()

      feed_direita = ft.Container(
          bgcolor="#0E2030",
          padding=22,
          border_radius=20,
          content=ft.Column(
              spacing=12,
              controls=[
                  ft.Text("🌐 Configurar Fonte Padrão (Chicago SRW Wheat Futures, StoneX e Portais)", color="#FFFFFF", size=18, weight=ft.FontWeight.BOLD),
                  dd_fonte_padrao,
                  inp_site_custom,
                  ft.ElevatedButton("💾 Guardar Configurações", bgcolor="#10B981", color="#080D16", on_click=guardar_cfg),
                  ft.Divider(color="#263D52"),
                  ft.Text("👤 Meu perfil", size=18, color="#FFFFFF", weight=ft.FontWeight.BOLD),
                  inp_nome_perfil, inp_bio_perfil,
                  ft.ElevatedButton("Salvar informações do perfil", bgcolor="#38BDF8", color="#07111C", on_click=atualizar_perfil),
                  ft.ElevatedButton("📸 Alterar foto de perfil", bgcolor="#263D52", color="#FFFFFF", on_click=escolher_foto),
                  ft.Divider(color="#263D52"),
                  ft.Text("🔐 Alterar minha senha", color="#FFFFFF", weight=ft.FontWeight.BOLD),
                  ft.Row(wrap=True, spacing=8, controls=[senha_antiga, senha_nova, senha_repetir]),
                  ft.ElevatedButton("Atualizar senha com segurança", bgcolor="#EAB308", color="#07111C", on_click=atualizar_senha),
              ],
          ),
      )

    return ft.Column(
        spacing=16,
        controls=[
            header_facebook,
            ft.ResponsiveRow(
                spacing=16,
                controls=[
                    ft.Container(col={"xs": 12, "lg": 3.8}, content=coluna_apresentacao_esq),
                    ft.Container(col={"xs": 12, "lg": 8.2}, content=feed_direita),
                ],
            ),
        ],
    )

  # =========================================================================
  # ABA 4: CLIMA, MAPA GEOGRÁFICO REAL & PREVISÕES FUTURAS DE CHUVA
  # =========================================================================
  def construir_aba_clima_com_mapa():
    nonlocal polo_clima_sel, estacao_clima_sel
    info_polo = POLOS_CLIMA_BRASIL.get(polo_clima_sel, list(POLOS_CLIMA_BRASIL.values())[0])
    previsao_14d, _, hora_clima, _ = buscar_previsao_tempo_openmeteo(polo_clima_sel)

    def mudar_polo_dd(e):
      nonlocal polo_clima_sel
      polo_clima_sel = dd_polo.value
      renderizar()

    def mudar_est_btn(est):
      nonlocal estacao_clima_sel
      estacao_clima_sel = est
      renderizar()

    dd_polo = ft.Dropdown(
        label="📍 Polo Climático Selecionado",
        bgcolor="#0A1826",
        color="#FFFFFF",
        width=440,
        options=[ft.dropdown.Option(k) for k in POLOS_CLIMA_BRASIL.keys()],
        value=polo_clima_sel,
        on_change=mudar_polo_dd,
    )

    cards_10d = ft.ResponsiveRow(spacing=8, run_spacing=8)
    for d in previsao_14d[:10]:
      chove = d["chuva_mm"] >= 2.0
      cards_10d.controls.append(
          ft.Container(
              col={"xs": 6, "sm": 4, "md": 2.4},
              bgcolor="#0A1826",
              padding=10,
              border_radius=12,
              border=ft.border.all(1, "#38BDF8" if chove else "#21394C"),
              content=ft.Column(
                  horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                  spacing=2,
                  controls=[
                      ft.Text(d["data"], color="#FFFFFF", size=12, weight=ft.FontWeight.BOLD),
                      ft.Icon(ft.icons.WATER_DROP_ROUNDED if chove else ft.icons.WB_SUNNY_ROUNDED, color="#38BDF8" if chove else "#FACC15", size=22),
                      ft.Text(f"{d['chuva_mm']:.1f} mm", color="#38BDF8", size=14, weight=ft.FontWeight.BOLD),
                      ft.Text(f"Prob: {d['prob']}% | {d['tmin']:.0f}°/{d['tmax']:.0f}°C", color="#94A3B8", size=10),
                  ],
              ),
          )
      )

    botoes_estacoes = ft.Row(wrap=True, spacing=8)
    for nome_est in info_polo["historico_estacoes"].keys():
      ativo = nome_est == estacao_clima_sel
      botoes_estacoes.controls.append(
          ft.ElevatedButton(
              f"✓ 🌦️ {nome_est}" if ativo else f"🌦️ {nome_est}",
              bgcolor="#10B981" if ativo else "#21394C",
              color="#080D16" if ativo else "#FFFFFF",
              height=34,
              on_click=lambda e, es=nome_est: mudar_est_btn(es),
          )
      )

    return ft.Container(
        bgcolor="#0E2030",
        padding=20,
        border_radius=24,
        border=ft.border.all(1.5, "#21394C"),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    controls=[
                        ft.Column([
                            ft.Text("🌧️ Inteligência Climática, Mapa Geográfico Real & Previsões Futuras", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD),
                            ft.Text(f"📚 Fonte: {info_polo['estacao_inmet']} | 🕒 Atualizado: {hora_clima}", color="#10B981", size=12),
                        ]),
                        dd_polo,
                    ],
                ),
                ft.ResponsiveRow(
                    spacing=16,
                    controls=[
                        ft.Container(col={"xs": 12, "lg": 6.4}, content=construir_widget_mapa_brasil_real()),
                        ft.Container(
                            col={"xs": 12, "lg": 5.6},
                            content=ft.Column(
                                spacing=10,
                                controls=[
                                    construir_mini_painel_grafico_mapa(modo_clima=True),
                                    ft.Text("🌦️ Estações do Ano (Comparativo 2023 a 2027):", color="#FACC15", size=13, weight=ft.FontWeight.BOLD),
                                    botoes_estacoes,
                                ],
                            ),
                        ),
                    ],
                ),
                cards_10d,
            ],
        ),
    )

  # =========================================================================
  # NOVA ABA 5: ESPAÇO DE PRINT / CARD PARA STORIES (INSTAGRAM & WHATSAPP)
  # =========================================================================
  def construir_aba_stories_marketing():
    u_atual = db_usuarios["usuarios"].get(usuario_logado_key, {})
    prev_10d, _, _, _ = buscar_previsao_tempo_openmeteo(polo_clima_sel)
    chuva_acum = sum(d["chuva_mm"] for d in prev_10d[:10])
    temp_str = f"{prev_10d[0]['tmin']:.0f}°C a {prev_10d[0]['tmax']:.0f}°C" if prev_10d else "17°C a 28°C"

    b64_story, svg_raw = gerar_svg_stories_marketing_b64(
        dados,
        uf_selecionada,
        subregiao_selecionada,
        u_atual.get("nome", "Márcio Luis Ávila da Silva"),
        u_atual.get("telefone", "5555999999999"),
        chuva_acum,
        temp_str,
        fonte_analise_ativa,
    )

    def guardar_arte_stories(e):
      os.makedirs(PASTA_RELATORIOS, exist_ok=True)
      stamp = datetime.now().strftime("%Y-%m-%d_%Hh%Mm")
      arq_html = os.path.join(PASTA_RELATORIOS, f"Card_Stories_CRAgroStat_{stamp}.html")
      html_content = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Card Stories CR AgroStat</title>
      <style>body{{margin:0;background:#05080F;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
      </head><body><div style="width:540px;height:960px;">{svg_raw}</div></body></html>"""
      with open(arq_html, "w", encoding="utf-8") as f:
        f.write(html_content)
      if os.name == "nt":
        try:
          os.startfile(os.path.abspath(arq_html))
        except Exception:
          pass
      mostrar_aviso(f"📸 Card Stories aberto em tela cheia e salvo em '{arq_html}' pronto para Print/Postagem!")

    legenda_pronta = (
        f"🌾📊 BOLETIM DIÁRIO CR AGROSTAT BRASIL ({datetime.now().strftime('%d/%m/%Y')})\n"
        f"📍 Praça: {uf_selecionada} • {subregiao_selecionada}\n"
        f"💰 Trigo Pão: R$ {calcular_preco_dinamico_atual(dados['itens'][0], uf_selecionada, subregiao_selecionada, fonte_analise_ativa):.2f}/sc | "
        f"Soja: R$ {calcular_preco_dinamico_atual(dados['itens'][1], uf_selecionada, subregiao_selecionada, fonte_analise_ativa):.2f}/sc | "
        f"Arroz: R$ {calcular_preco_dinamico_atual(dados['itens'][2], uf_selecionada, subregiao_selecionada, fonte_analise_ativa):.2f}/sc\n"
        f"🌧️ Chuva Prevista (10 dias): {chuva_acum:.1f} mm ({temp_str})\n"
        f"📚 Fontes: {fonte_analise_ativa}, StoneX, CEPEA e Open-Meteo.\n"
        f"📲 Consultoria Comercial: {u_atual.get('nome', 'Márcio Luis Ávila da Silva')}"
    )

    return ft.Container(
        bgcolor="#0E2030",
        padding=22,
        border_radius=24,
        border=ft.border.all(1.5, "#10B981"),
        content=ft.Column(
            spacing=16,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    controls=[
                        ft.Column([
                            ft.Text("📸 Estúdio de Print & Card Diário para Stories (Instagram / WhatsApp Status)", color="#FFFFFF", size=21, weight=ft.FontWeight.BOLD),
                            ft.Text("Tire um Print direto da arte abaixo ou clique em 'Abrir em Tela Cheia' para divulgar seu trabalho e o CR AgroStat.", color="#10B981", size=13),
                        ]),
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.ElevatedButton("🖥️ Abrir Card em Tela Cheia p/ Print", bgcolor="#10B981", color="#080D16", height=42, on_click=guardar_arte_stories),
                                ft.ElevatedButton("📋 Copiar Legenda p/ Postar", bgcolor="#FACC15", color="#080D16", height=42, on_click=lambda e: copiar_para_area_transferencia("Legenda Stories", legenda_pronta)),
                            ],
                        ),
                    ],
                ),
                construir_seletor_triplo_regioes(),
                ft.ResponsiveRow(
                    spacing=20,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        # Arte Vertical 9:16 Pronta para Print
                        ft.Container(
                            col={"xs": 12, "md": 6},
                            bgcolor="#05080F",
                            padding=16,
                            border_radius=24,
                            alignment=ft.alignment.center,
                            content=ft.Image(src_base64=b64_story, width=410, height=730, fit=ft.ImageFit.CONTAIN),
                        ),
                        # Instruções e Legenda de Marketing
                        ft.Container(
                            col={"xs": 12, "md": 6},
                            bgcolor="#0A1826",
                            padding=20,
                            border_radius=20,
                            border=ft.border.all(1, "#21394C"),
                            content=ft.Column(
                                spacing=12,
                                controls=[
                                    ft.Text("🚀 Como Postar nos Seus Stories em 10 Segundos:", color="#FACC15", size=17, weight=ft.FontWeight.BOLD),
                                    ft.Text("1. Escolha acima a Região, o Estado e a Região Interna que deseja destacar no boletim de hoje.", color="#E2E8F0", size=13),
                                    ft.Text("2. No Windows, prima 'Win + Shift + S' para recortar o Card ao lado (ou clique em 'Abrir Card em Tela Cheia').", color="#E2E8F0", size=13),
                                    ft.Text("3. O Card já inclui ilustrações temáticas de lavoura, clima de 10 dias, cotações do dia, fontes auditadas (Chicago SRW / StoneX / CEPEA) e o seu nome + WhatsApp como propaganda oficial!", color="#10B981", size=13),
                                    ft.Divider(color="#21394C"),
                                    ft.Text("📝 Legenda Automática Pronta para Colar:", color="#38BDF8", size=14, weight=ft.FontWeight.BOLD),
                                    ft.Container(bgcolor="#0E2030", padding=14, border_radius=12, content=ft.Text(legenda_pronta, color="#CBD5E1", size=12)),
                                ],
                            ),
                        ),
                    ],
                ),
            ],
        ),
    )

  # =========================================================================
  # NOVA ABA 6: INTELIGÊNCIA ARTIFICIAL AGRO (CONVERSA POR TEXTO E VOZ MASC/FEM)
  # =========================================================================
  def construir_aba_ia_voz():
    nonlocal voz_selecionada, alar_automatico_ia

    def escolher_voz(nova_v):
      nonlocal voz_selecionada
      voz_selecionada = nova_v
      if usuario_logado_key:
        db_usuarios["usuarios"][usuario_logado_key]["voz_ia"] = nova_v
        salvar_banco_usuarios(db_usuarios)
      falar_navegador(f"Voz {nova_v.split()[0]} selecionada no C R AgroStat.", nova_v)
      renderizar()

    inp_pergunta_ia = ft.TextField(
        label="🎙️ Digite ou fale sua pergunta sobre Grãos, Trigo, Soja, Arroz, StoneX, Clima, Frete ou Barter...",
        bgcolor="#0A1826",
        color="#FFFFFF",
        border_radius=14,
        border_color="#10B981",
        expand=True,
    )

    def enviar_pergunta_ia(texto_p=None):
      q = texto_p if isinstance(texto_p, str) else inp_pergunta_ia.value.strip()
      if not q:
        return
      historico_chat_ia.append({"autor": "Você", "hora": agora_str(), "texto": q})
      resp_local = responder_ia_agronegocio(q, dados, uf_selecionada, subregiao_selecionada, polo_clima_sel, fonte_analise_ativa)
      resp_local = "[Analisador local; preços indicativos e cenários, não cotações oficiais] " + resp_local
      resp = resposta_ia_com_api_opcional(q, dados, uf_selecionada, subregiao_selecionada, resp_local)
      historico_chat_ia.append({"autor": f"🤖 IA Agro ({voz_selecionada})", "hora": agora_str(), "texto": resp})
      inp_pergunta_ia.value = ""
      if alar_automatico_ia:
        falar_navegador(resp, voz_selecionada)
      renderizar()

    def instrucoes_ditado(e):
      mostrar_aviso("Para ditar: clique no campo e use o microfone do teclado do celular ou Win+H no Windows.", "#38BDF8")
      inp_pergunta_ia.focus()

    def boletim_mercado(e):
      enviar_pergunta_ia("Resuma os dados estimados de trigo, soja, arroz, milho, dólar e clima, distinguindo fatos e cenários.")

    mensagens_ui = ft.Column(spacing=10)
    for m in historico_chat_ia[-8:]:
      eh_ia = "IA" in m["autor"]
      mensagens_ui.controls.append(
          ft.Container(
              bgcolor="#0A1826" if eh_ia else "#052E16",
              padding=16,
              border_radius=16,
              border=ft.border.all(1.5, "#38BDF8" if eh_ia else "#10B981"),
              content=ft.Column(
                  spacing=6,
                  controls=[
                      ft.Row(
                          alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                          controls=[
                              ft.Text(m["autor"], color="#FACC15" if eh_ia else "#10B981", size=13, weight=ft.FontWeight.BOLD),
                              ft.Row(
                                  spacing=6,
                                  controls=[
                                      ft.Text(m["hora"], color="#64748B", size=11),
                                      ft.ElevatedButton(
                                          "🔊 Ouvir com Voz",
                                          bgcolor="#21394C",
                                          color="#38BDF8",
                                          height=28,
                                          on_click=lambda e, tx=m["texto"]: falar_navegador(tx, voz_selecionada),
                                      ),
                                  ],
                              ),
                          ],
                      ),
                      ft.Text(m["texto"], color="#FFFFFF", size=14),
                  ],
              ),
          )
      )

    perguntas_rapidas = [
        ("🌾 Como está o Trigo e Chicago SRW hoje?", "Qual a análise do trigo hoje em Chicago SRW e na minha região?"),
        ("🌱 Análise da Soja & Relatório StoneX", "Como está a soja hoje segundo Chicago e StoneX?"),
        ("🌾 Mercado do Arroz na Fronteira Oeste", "Qual o panorama do arroz em casca hoje?"),
        ("🌧️ Clima e Janela de Plantio/Pulverização", "Como está a previsão de chuva e clima para a lavoura?"),
        ("⚖️ Relação de Troca (Barter) Sementes", "Vale a pena fazer barter de sementes hoje?"),
    ]

    return ft.Container(
        bgcolor="#0E2030",
        padding=22,
        border_radius=24,
        border=ft.border.all(1.5, "#38BDF8"),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    controls=[
                        ft.Column([
                            ft.Text("🤖 Inteligência Artificial do Agronegócio — Conversa por Escrita e Voz", color="#FFFFFF", size=21, weight=ft.FontWeight.BOLD),
                            ft.Text("Áudio no navegador. Respostas baseadas em estimativas locais; IA generativa opcional com OPENAI_API_KEY.", color="#38BDF8", size=13),
                        ]),
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.ElevatedButton(
                                    "✓ 👩 Voz Feminina (Analista)" if "Feminina" in voz_selecionada else "👩 Voz Feminina (Analista)",
                                    bgcolor="#10B981" if "Feminina" in voz_selecionada else "#21394C",
                                    color="#080D16" if "Feminina" in voz_selecionada else "#FFFFFF",
                                    height=38,
                                    on_click=lambda e: escolher_voz("Feminina (Analista Agro)"),
                                ),
                                ft.ElevatedButton(
                                    "✓ 👨 Voz Masculina (Consultor)" if "Masculina" in voz_selecionada else "👨 Voz Masculina (Consultor)",
                                    bgcolor="#38BDF8" if "Masculina" in voz_selecionada else "#21394C",
                                    color="#080D16" if "Masculina" in voz_selecionada else "#FFFFFF",
                                    height=38,
                                    on_click=lambda e: escolher_voz("Masculina (Consultor Agro)"),
                                ),
                            ],
                        ),
                    ],
                ),
                ft.Row(
                    wrap=True,
                    spacing=8,
                    controls=[
                        ft.ElevatedButton(rot, bgcolor="#21394C", color="#FACC15", height=34, on_click=lambda e, p=perg: enviar_pergunta_ia(p))
                        for rot, perg in perguntas_rapidas
                    ],
                ),
                ft.Row(wrap=True, spacing=8, controls=[
                    ft.ElevatedButton("🔈 Boletim falado", bgcolor="#FACC15", color="#080D16", on_click=boletim_mercado),
                    ft.ElevatedButton("▶ Abrir áudio no navegador", bgcolor="#115E59", color="#FFFFFF", on_click=ouvir_arquivo_externo),
                    ft.ElevatedButton("⏹ Parar áudio", bgcolor="#263D52", color="#FFFFFF", on_click=parar_audio),
                    ft.Text("Se o Chrome bloquear a reprodução automática, use 'Abrir áudio no navegador'. Vozes naturais exigem edge-tts no servidor.", color="#94A3B8", size=11),
                ]),
                mensagens_ui,
                ft.Column(spacing=9, controls=[
                    inp_pergunta_ia,
                    ft.Row(wrap=True, spacing=8, controls=[
                        ft.ElevatedButton("💬 Perguntar & Ouvir", bgcolor="#10B981", color="#080D16", height=44, on_click=lambda e: enviar_pergunta_ia()),
                        ft.ElevatedButton("🎙️ Como ditar", bgcolor="#21394C", color="#FACC15", height=44, on_click=instrucoes_ditado),
                    ]),
                ]),
            ],
        ),
    )

  # =========================================================================
  # ABA EXTRA: COMPARADOR DE PREÇOS, FAVORITOS E TRANSPARÊNCIA DOS DADOS
  # =========================================================================
  def construir_comparador_mercado():
    u = db_usuarios["usuarios"].get(usuario_logado_key, {})
    favoritos = u.setdefault("favoritos_produtos", [])
    produto_selecionado = ft.Dropdown(label="Produto", width=290,
        value=dados["itens"][0]["id"], options=[ft.dropdown.Option(i["id"], i["nome_curto"]) for i in dados["itens"]])
    estados_options = sorted({uf for ufs in HIERARQUIA_BRASIL.values() for uf in ufs})
    estados_comp = ft.Dropdown(label="Comparar com estado", width=200,
        value="PR" if uf_selecionada != "PR" else "SC",
        options=[ft.dropdown.Option(uf) for uf in estados_options])
    tabela_comparacao = ft.Column(spacing=7)

    def montar_comparacao(e=None):
      tabela_comparacao.controls.clear()
      item = next((i for i in dados["itens"] if i["id"] == produto_selecionado.value), dados["itens"][0])
      outros_estados = [uf_selecionada, estados_comp.value]
      for estado in dict.fromkeys(outros_estados):
        for nome_sub in SUBREGIOES_ESTADOS.get(estado, {}):
          valor = calcular_preco_dinamico_atual(item, estado, nome_sub, fonte_analise_ativa)
          tabela_comparacao.controls.append(ft.Container(bgcolor="#0E2531", padding=12, border_radius=11,
             content=ft.Row(wrap=True, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Text(f"{estado} • {nome_sub}", color="#E2E8F0", size=12),
                ft.Text(dinheiro_br(valor), color="#37E0B6", size=15, weight=ft.FontWeight.BOLD)
             ])))
      page.update()

    def alternar_favorito(e):
      codigo = produto_selecionado.value
      if codigo in favoritos: favoritos.remove(codigo)
      else: favoritos.append(codigo)
      salvar_banco_usuarios(db_usuarios)
      mostrar_aviso("Favoritos atualizados.")
      renderizar()

    montar_comparacao()
    return ft.Container(bgcolor="#0E2030", padding=22, border_radius=22,
       content=ft.Column(spacing=14, controls=[
          ft.Text("📊 Comparador de Mercados", color="#FFFFFF", size=23, weight=ft.FontWeight.BOLD),
          ft.Text("Comparação indicativa calculada com multiplicadores regionais. Não representa preços efetivamente coletados nas praças.",
                  color="#FACC15", size=12),
          ft.Row(wrap=True, spacing=10, controls=[produto_selecionado, estados_comp,
             ft.ElevatedButton("Comparar agora", bgcolor="#10B981", color="#07111C", on_click=montar_comparacao),
             ft.ElevatedButton("⭐ Adicionar/remover favorito", bgcolor="#263D52", color="#FFFFFF", on_click=alternar_favorito)]),
          ft.Text("🌟 Meus favoritos: " + (", ".join(next((i["nome_curto"] for i in dados["itens"] if i["id"]==a), a) for a in favoritos) or "Nenhum"),
                  color="#38BDF8", size=12),
          tabela_comparacao,
          ft.Divider(color="#263D52"),
          ft.Text("🔎 Entenda seus indicadores", color="#FFFFFF", size=17, weight=ft.FontWeight.BOLD),
          ft.Text("Câmbio e contratos de Chicago são consultados no Yahoo Finance quando a rede e o mercado permitem. "
                  "Os preços regionais, diferenças entre fontes e tendências são modelos indicativos calculados no aplicativo. "
                  "Não equivalem a dados licenciados da StoneX, CEPEA ou Emater.", color="#CBD5E1", size=12),
          ft.Text(f"Última referência de dados: {dados.get('atualizacao','Não informado')}", color="#94A3B8", size=12),
          ft.ElevatedButton("Consultar fonte oficial CEPEA", bgcolor="#263D52", color="#E2E8F0",
              on_click=lambda e: page.launch_url("https://www.cepea.esalq.usp.br/br")),
       ]))

  # =========================================================================
  # RENDERIZAÇÃO GERAL COM BARRA LATERAL ESQUERDA E FOTO GRANDE
  # =========================================================================
  def renderizar():
    u_atual = db_usuarios["usuarios"].get(usuario_logado_key, {})
    alertas_av = avaliar_alertas_usuario()
    qtd_quentes = sum(1 for a in alertas_av if a["nivel"] >= 1)
    avisos_crm_proximos = [(cli, al, situacao_lembrete_cliente(al))
        for cli in u_atual.get("clientes", []) for al in cli.get("lembretes", [])
        if not al.get("concluido")]
    avisos_crm_proximos = [item for item in avisos_crm_proximos
        if item[2][0].startswith("Atrasado") or item[2][0].startswith("Em ") or item[2][0] == "Vence hoje"]
    qtd_alertas_menu = qtd_quentes + len(avisos_crm_proximos)

    definicao_abas = [
        ("painel", "Painel, Chicago & StoneX", ft.icons.SHOW_CHART_ROUNDED),
        ("mapa", "Mapa Geográfico & Gráficos", ft.icons.PUBLIC_ROUNDED),
        ("perfil", f"Perfil, Clientes & GPS ({qtd_alertas_menu}🔔)" if qtd_alertas_menu else "Perfil, Clientes & GPS", ft.icons.PERSON_ROUNDED),
        ("clima", "Clima, Mapa & Chuvas", ft.icons.THUNDERSTORM_ROUNDED),
        ("stories", "📸 Card Stories & Print", ft.icons.PHOTO_CAMERA_ROUNDED),
        ("ia_voz", "🤖 IA Agro (Voz & Texto)", ft.icons.RECORD_VOICE_OVER_ROUNDED),
        ("regional", "Contratos & Praças BR", ft.icons.MAP_ROUNDED),
        ("frete", "Estudo de Fretes (KM)", ft.icons.LOCAL_SHIPPING_ROUNDED),
        ("barter", "Simulador Barter", ft.icons.CALCULATE_ROUNDED),
        ("comparador", "Comparador & Favoritos", ft.icons.COMPARE_ARROWS_ROUNDED),
    ]

    coluna_lateral_menu.controls.clear()
    # Topo da Coluna Lateral Esquerda com FOTO QUADRADA ARREDONDADA BEM MAIOR (112x112)
    coluna_lateral_menu.controls.append(
        ft.Container(
            bgcolor="#0A1826",
            padding=16,
            border_radius=22,
            border=ft.border.all(1.5, "#21394C"),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                controls=[
                    obter_avatar_quadrado_grande(u_atual, largura=112, altura=112, raio=24),
                    ft.Text("CR AgroStat", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(u_atual.get("nome", "Márcio Luis Ávila da Silva"), color="#10B981", size=13, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Text(f"📍 {uf_selecionada} • {subregiao_selecionada[:24]}", color="#FACC15", size=11, text_align=ft.TextAlign.CENTER),
                    ft.ElevatedButton(
                        "📸 Trocar Foto",
                        bgcolor="#21394C",
                        color="#38BDF8",
                        height=28,
                        on_click=escolher_foto,
                    ),
                    ft.Container(
                        bgcolor="#0E2030",
                        padding=8,
                        border_radius=10,
                        width=float("inf"),
                        content=ft.Text(
                            f"💵 Dólar: R$ {dados['dolar']:.2f} ({dados['dolar_var']:+.2f}%)\n📚 {fonte_analise_ativa[:22]}",
                            color="#38BDF8",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                ],
            ),
        )
    )

    for chave_aba, texto_aba, icone_aba in definicao_abas:
      esta_ativa = aba_atual == chave_aba
      coluna_lateral_menu.controls.append(
          ft.ElevatedButton(
              text=f"✓  {texto_aba}" if esta_ativa else f"   {texto_aba}",
              icon=icone_aba,
              width=250,
              height=41,
              bgcolor="#10B981" if esta_ativa else "#0E2030",
              color="#080D16" if esta_ativa else "#E2E8F0",
              style=ft.ButtonStyle(
                  alignment=ft.alignment.center_left,
                  side={"": ft.BorderSide(2 if esta_ativa else 1, "#FACC15" if esta_ativa else "#21394C")},
                  shape=ft.RoundedRectangleBorder(radius=13),
              ),
              on_click=lambda e, k=chave_aba: mudar_aba(k),
          )
      )

    coluna_lateral_menu.controls.append(
        ft.ElevatedButton("🔄 Atualizar Mercado Dinâmico", bgcolor="#38BDF8", color="#080D16", width=250, height=38, on_click=acao_atualizar)
    )
    coluna_lateral_menu.controls.append(
        ft.ElevatedButton("📄 Gerar PDF Oficial", bgcolor="#FACC15", color="#080D16", width=250, height=38, on_click=lambda e: gerar_pdf_completo_usuario("Relatorio Oficial"))
    )

    # Barra editorial do painel: hierarquia visual e atualização dos dados.
    area_conteudo_direita.controls.clear()
    area_conteudo_direita.controls.append(ft.Container(
        padding=ft.padding.symmetric(horizontal=20, vertical=15), border_radius=20,
        gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right,
            colors=["#173949", "#0F2635", "#0C1927"]),
        border=ft.border.all(1, "#235E59"),
        content=ft.ResponsiveRow(spacing=6, controls=[
            ft.Container(col={"xs":12,"lg":7}, content=ft.Column(spacing=4, controls=[
                ft.Text("CR  /  AGROSTAT", color="#5CEAC4", size=13, weight=ft.FontWeight.BOLD),
                ft.Text("Inteligência que cultiva decisões", color="#FFFFFF", size=23, weight=ft.FontWeight.BOLD),
                ft.Text(f"{uf_selecionada} • {subregiao_selecionada}", color="#B9D5DD", size=11),
            ])),
            ft.Container(col={"xs":12,"lg":5}, content=ft.Column(spacing=4, controls=[
                ft.Text("ÚLTIMA REFERÊNCIA", color="#8CB8C3", size=10, weight=ft.FontWeight.BOLD),
                ft.Text(dados.get("atualizacao", "Sem atualização"), color="#F7FBFD", size=14, weight=ft.FontWeight.BOLD),
                ft.Text("Preços regionais simulados • ver fontes no Comparador", color="#FACC15", size=11),
            ])),
        ])))

    if aba_atual == "painel":
      total_clientes = len(u_atual.get("clientes", []))
      qtd_agendamentos = len(u_atual.get("agenda_vendas", []))
      area_total = sum(float(c.get("hectares_soja",0) or 0) + float(c.get("hectares_arroz",0) or 0)
                       for c in u_atual.get("clientes", []))
      kpis = ft.ResponsiveRow(spacing=10)
      for titulo, valor, nota, cor in [
          ("CLIENTES NA CARTEIRA", str(total_clientes), "CRM comercial", "#38BDF8"),
          ("ÁREA ASSISTIDA", f"{area_total:,.0f} ha".replace(",","."), "Soja + arroz", "#34D399"),
          ("NEGOCIAÇÕES", str(qtd_agendamentos), "Agenda e vendas", "#FACC15"),
          ("DÓLAR DE REFERÊNCIA", dinheiro_br(dados.get("dolar",0)), "Yahoo quando disponível", "#D8B4FE"),
      ]:
        kpis.controls.append(ft.Container(col={"xs":6,"lg":3}, bgcolor="#112435", padding=16,
            border_radius=16, border=ft.border.all(1,"#214255"), content=ft.Column(spacing=6, controls=[
                ft.Text(titulo, color="#9FC4CD", size=10, weight=ft.FontWeight.BOLD),
                ft.Text(valor, color=cor, size=24, weight=ft.FontWeight.BOLD),
                ft.Text(nota, color="#9CAFC3", size=11),
            ])))
      area_conteudo_direita.controls.append(kpis)
      if avisos_crm_proximos:
        area_conteudo_direita.controls.append(ft.Container(bgcolor="#251E16", padding=15, border_radius=16,
            border=ft.border.all(1, "#FACC15"), content=ft.Column(spacing=7, controls=[
                ft.Row(wrap=True, controls=[
                    ft.Icon(ft.icons.NOTIFICATIONS_ACTIVE_OUTLINED, color="#FACC15", size=23),
                    ft.Text(f"ALERTAS DE CLIENTES · {len(avisos_crm_proximos)} pendente(s)", color="#FACC15", size=15, weight=ft.FontWeight.BOLD),
                    ft.ElevatedButton("Abrir carteira de clientes", bgcolor="#FACC15", color="#0A1826", on_click=lambda e: mudar_aba("perfil")),
                ]),
                *[ft.Text(f"{cl.get('nome','')}: {al.get('texto','')} | {sit[0]}", color=sit[1], size=12)
                  for cl, al, sit in avisos_crm_proximos[:5]],
            ])))
      area_conteudo_direita.controls.append(construir_bloco_terminal_chicago())

      grade = ft.ResponsiveRow(spacing=14, run_spacing=14)
      for idx, item in enumerate(dados["itens"]):
        preco_din = calcular_preco_dinamico_atual(item, uf_selecionada, subregiao_selecionada, fonte_analise_ativa)
        m_uf = calcular_medias_estados(item["regioes_sul"])
        alta = item["var_dia"] >= 0
        sinal = "+" if alta else ""

        def selecionar_card(e, i=idx):
          nonlocal item_grafico_idx
          item_grafico_idx = i
          renderizar()

        grade.controls.append(
            ft.Container(
                col={"xs": 12, "md": 6, "xl": 3},
                bgcolor="#0E2030",
                padding=16,
                border_radius=18,
                border=ft.border.all(2 if idx == item_grafico_idx else 1, item["cor"] if idx == item_grafico_idx else "#21394C"),
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text(item["nome_curto"], color="#FFFFFF", size=16, weight=ft.FontWeight.BOLD), ft.Text(item["codigo_cbot"], color="#38BDF8", size=11, weight=ft.FontWeight.BOLD)]),
                        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text(f"R$ {preco_din:.2f}", color="#FFFFFF", size=24, weight=ft.FontWeight.BOLD), ft.Text(f"{sinal}{item['var_dia']:.2f}%", color="#22C55E" if alta else "#F87171", size=12, weight=ft.FontWeight.BOLD)]),
                        ft.Text(f"Média {uf_selecionada}: R$ {m_uf.get(uf_selecionada, preco_din):.2f} | Sul: R$ {m_uf['SUL']:.2f}", color="#10B981", size=11, weight=ft.FontWeight.BOLD),
                        ft.ElevatedButton("✓ No Topo" if idx == item_grafico_idx else "🔍 Analisar", bgcolor=item["cor"] if idx == item_grafico_idx else "#21394C", color="#080D16" if idx == item_grafico_idx else "#FFFFFF", height=30, width=float("inf"), on_click=selecionar_card),
                    ],
                ),
            )
        )
      area_conteudo_direita.controls.append(grade)

    elif aba_atual == "comparador":
      area_conteudo_direita.controls.append(construir_comparador_mercado())

    elif aba_atual == "mapa":
      area_conteudo_direita.controls.append(construir_aba_mapa_clicavel())

    elif aba_atual == "perfil":
      area_conteudo_direita.controls.append(construir_aba_perfil_facebook())

    elif aba_atual == "clima":
      area_conteudo_direita.controls.append(construir_aba_clima_com_mapa())

    elif aba_atual == "stories":
      area_conteudo_direita.controls.append(construir_aba_stories_marketing())

    elif aba_atual == "ia_voz":
      area_conteudo_direita.controls.append(construir_aba_ia_voz())

    elif aba_atual == "regional":
      item_reg = dados["itens"][item_regional_idx]
      linhas_reg = ft.Column(spacing=8)
      for s_nome, fat_s in SUBREGIOES_ESTADOS.get(uf_selecionada, {}).items():
        val_p = calcular_preco_dinamico_atual(item_reg, uf_selecionada, s_nome, fonte_analise_ativa)
        dif = val_p - item_reg["contrato_empresa"]
        linhas_reg.controls.append(
            ft.Container(
                bgcolor="#0A1826",
                padding=12,
                border_radius=12,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(f"📍 {uf_selecionada} • {s_nome}", color="#FFFFFF", size=13, weight=ft.FontWeight.BOLD),
                        ft.Text(f"R$ {val_p:.2f} ({dif:+.2f} R$ vs Contrato)", color="#10B981" if dif >= 0 else "#FACC15", size=13, weight=ft.FontWeight.BOLD),
                    ],
                ),
            )
        )
      area_conteudo_direita.controls.append(
          ft.Container(bgcolor="#0E2030", padding=20, border_radius=24, content=ft.Column(spacing=12, controls=[ft.Text("🗺️ Contratos & Sub-Regiões dos Estados", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD), construir_seletor_triplo_regioes(), linhas_reg]))
      )

    elif aba_atual == "frete":
      c_km = ft.TextField(label="Distância (KM)", value="220", bgcolor="#0A1826", color="#FFFFFF", width=150)
      c_rkm = ft.TextField(label="R$/km", value="6.80", bgcolor="#0A1826", color="#FFFFFF", width=150)
      c_ton = ft.TextField(label="Toneladas", value="32", bgcolor="#0A1826", color="#FFFFFF", width=150)
      res_f = ft.Text("Custo Viagem: R$ 1.496,00 | Saca 60kg: R$ 2,80", color="#10B981", size=16, weight=ft.FontWeight.BOLD)

      def calc_f(e):
        try:
          tot = float(c_km.value) * float(c_rkm.value)
          pton = tot / float(c_ton.value)
          res_f.value = f"🚚 Viagem: R$ {tot:,.2f} | Por Ton: R$ {pton:.2f} | Saca 60kg: R$ {pton*0.06:.2f}"
          page.update()
        except Exception:
          pass

      area_conteudo_direita.controls.append(
          ft.Container(bgcolor="#0E2030", padding=22, border_radius=24, content=ft.Column(spacing=14, controls=[ft.Text("🚛 Estudo Logístico de Fretes (KM)", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD), ft.Row(wrap=True, spacing=10, controls=[c_km, c_rkm, c_ton, ft.ElevatedButton("Calcular", bgcolor="#FACC15", color="#080D16", on_click=calc_f)]), res_f]))
      )

    else:
      s_pr = ft.TextField(label="Preço Grão (R$)", value="134.24", bgcolor="#0A1826", color="#FFFFFF", width=160)
      s_sem = ft.TextField(label="Preço Semente (R$)", value="291.00", bgcolor="#0A1826", color="#FFFFFF", width=160)
      res_b = ft.Text("Relação Barter: 2,17 sacas de grão por 1 semente certificada.", color="#10B981", size=16, weight=ft.FontWeight.BOLD)

      def calc_b(e):
        try:
          tr = float(s_sem.value) / float(s_pr.value)
          res_b.value = f"⚖️ Relação Barter: {tr:.2f} sacas de grão pagam 1 unidade de semente."
          page.update()
        except Exception:
          pass

      area_conteudo_direita.controls.append(
          ft.Container(bgcolor="#0E2030", padding=22, border_radius=24, content=ft.Column(spacing=14, controls=[ft.Text("⚖️ Simulador Barter", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD), ft.Row(wrap=True, spacing=10, controls=[s_pr, s_sem, ft.ElevatedButton("Simular", bgcolor="#10B981", color="#080D16", on_click=calc_b)]), res_b]))
      )

    page.update()

  def mudar_aba(nova_aba):
    nonlocal aba_atual, horario_ultima_selecao
    aba_atual = nova_aba
    horario_ultima_selecao = agora_str()
    renderizar()

  def acao_atualizar(e):
    nonlocal dados, horario_ultima_selecao
    dados = coletar_mercado(dados)
    horario_ultima_selecao = dados["atualizacao"]
    mostrar_aviso(f"Cotações dinâmicas ({fonte_analise_ativa}, StoneX e CBOT) atualizadas em {dados['atualizacao']}!")
    renderizar()

  def montar_sistema():
    if not usuario_logado_key:
      raiz_pagina.content = construir_tela_autenticacao()
      page.update()
      return

    definicao_mobile = [
        ("painel", "Painel / Chicago"), ("mapa", "Mapa do Brasil"),
        ("perfil", "Perfil e Clientes"), ("clima", "Clima"),
        ("stories", "Stories"), ("ia_voz", "IA / Voz"),
        ("regional", "Contratos"), ("frete", "Fretes"),
        ("barter", "Barter"), ("comparador", "Comparador"),
    ]
    if (page.width or 1200) < 825:
      nav_mobile = ft.Dropdown(label="☰ Ir para...", width=250, value=aba_atual,
          options=[ft.dropdown.Option(k, nome) for k, nome in definicao_mobile],
          on_change=lambda e: mudar_aba(e.control.value))
      raiz_pagina.content = ft.Column(expand=True, spacing=9, controls=[
          ft.Container(bgcolor="#0D2633", padding=10, border_radius=14,
            content=ft.Row(wrap=True, spacing=8, controls=[
                ft.Text("🌾 CR AgroStat", size=19, color="#52E1BB", weight=ft.FontWeight.BOLD),
                nav_mobile,
                ft.IconButton(icon=ft.icons.REFRESH_ROUNDED, icon_color="#38BDF8", on_click=acao_atualizar),
                ft.IconButton(icon=ft.icons.PICTURE_AS_PDF_ROUNDED, icon_color="#FACC15",
                              on_click=lambda e: gerar_pdf_completo_usuario("Relatório Oficial")),
            ])),
          area_conteudo_direita,
      ])
    else:
      raiz_pagina.content = ft.Row(
          expand=True, spacing=14, vertical_alignment=ft.CrossAxisAlignment.START,
          controls=[
              ft.Container(width=272, bgcolor="#0E1D2B", padding=14, border_radius=24,
                           border=ft.border.all(1.5, "#234050"), content=coluna_lateral_menu),
              ft.Container(expand=True, content=area_conteudo_direita),
          ])
    renderizar()

  def verificar_responsividade(e):
    nonlocal menu_mobile_ativo
    novo_mobile = (page.width or 1200) < 825
    if novo_mobile != menu_mobile_ativo:
      menu_mobile_ativo = novo_mobile
      montar_sistema()

  menu_mobile_ativo = (page.width or 1200) < 825
  page.on_resize = verificar_responsividade
  page.add(raiz_pagina)
  montar_sistema()


if __name__ == "__main__":
  gerar_arquivos_servidor_e_icones()
  porta_servidor = int(os.environ.get("PORT", 8550))
  ft.app(
      target=main,
      view=None,
      host="0.0.0.0",
      port=porta_servidor,
      assets_dir=PASTA_ASSETS,
      upload_dir=PASTA_UPLOADS,
  )