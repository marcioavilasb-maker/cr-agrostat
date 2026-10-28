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
import flet as ft
import requests
import yfinance as yf

ARQUIVO_DB = os.path.join("dados", "cr_agrostat_brasil_v9.json")
ARQUIVO_USUARIOS = os.path.join("dados", "cr_usuarios_crm_v9.json")
PASTA_RELATORIOS = "relatorios"
PASTA_ASSETS = "assets"
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
  texto = f"{SALT_SEGURANCA}:{senha_limpa.strip()}"
  return hashlib.sha256(texto.encode("utf-8")).hexdigest()


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
        f"Segundo a análise {fonte_ativa}, a paridade de importação e a demanda dos moinhos do Sul mantêm suporte entre R$ {trigo['prev_15d']:.2f} (15 dias) e R$ {trigo['prev_30d']:.2f} (30 dias)."
    )
  elif "soja" in p_low:
    val_s = round(soja["preco_atual"] * fator_f, 2)
    return (
        f"🌱 Análise de Soja ({regiao_interna_sel}): A saca de 60kg está cotada hoje a R$ {val_s:.2f} ({soja['var_dia']:+.2f}%), "
        f"com Chicago (ZS=F) em {soja['ult_usx']:.2f} USX e Dólar Comercial a R$ {dolar:.2f}. "
        f"O relatório da StoneX e CEPEA aponta atenção aos prêmios de exportação nos portos e ritmo de vendas do produtor. "
        f"A estimativa para 30 dias é de R$ {soja['prev_30d']:.2f}/sc."
    )
  elif "arroz" in p_low:
    val_a = round(arroz["preco_atual"] * fator_f, 2)
    return (
        f"🌾 Análise de Arroz em Casca ({regiao_interna_sel}): Cotação atual em R$ {val_a:.2f} por saca de 50kg ({arroz['var_dia']:+.2f}%). "
        f"Na Fronteira Oeste (São Borja/Itaqui) e Zona Sul, o indicador IRGA/CEPEA e a StoneX destacam firmeza pela reposição das indústrias beneficiadoras. "
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
        f"🌧️ Boletim Agrometeorológico ({polo_clima_sel}): Os modelos de satélite ECMWF e NOAA GFS monitoram a umidade do solo e as frentes frias. "
        f"Para pulverização e semeadura, aproveite as janelas sem precipitação acima de 5mm e ventos abaixo de 10 km/h. "
        f"Consulte a aba Clima para ver o comparativo completo das estações de 2023 a 2027."
    )
  elif any(k in p_low for k in ["stonex", "chicago", "bolsa", "dolar", "câmbio", "mercado"]):
    return (
        f"💎 Resumo StoneX & Chicago SRW ({agora_str()}): O Dólar Comercial opera a R$ {dolar:.2f} ({dolar_var:+.2f}%). "
        f"{info_fonte['resumo_analise']} Hoje os destaques na sua praça ({regiao_interna_sel}) são: "
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
def gerar_svg_stories_marketing_b64(dados, uf_sel, regiao_sel, nome_consultor, tel_consultor, chuva_10d_mm, temp_hoje, fonte_ativa):
  """Cria um Card Vertical 9:16 (Stories) rico em ilustrações temáticas de lavoura, clima e cotações."""
  itens = dados.get("itens", [])
  Linhas_cot = ""
  y_c = 340
  for it in itens[:6]:
    fator_sub = SUBREGIOES_ESTADOS.get(uf_sel, {}).get(regiao_sel, 1.0)
    val_r = round(it["preco_atual"] * fator_sub, 2)
    sinal = "+" if it["var_dia"] >= 0 else ""
    cor_v = "#4ADE80" if it["var_dia"] >= 0 else "#F87171"
    Linhas_cot += f"""
    <rect x="32" y="{y_c}" width="476" height="68" rx="14" fill="#111927" stroke="#1E293B" stroke-width="1.5"/>
    <circle cx="68" cy="{y_c+34}" r="18" fill="{it['cor']}" fill-opacity="0.22" stroke="{it['cor']}" stroke-width="2"/>
    <text x="68" y="{y_c+39}" fill="{it['cor']}" font-family="Arial" font-size="11" font-weight="bold" text-anchor="middle">{it['sigla'][:4]}</text>
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
  <rect width="540" height="960" rx="28" fill="url(#bgStory)" stroke="#10B981" stroke-width="3"/>

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
  <text x="110" y="96" fill="#38BDF8" font-family="Arial" font-size="11">📅 {dados.get('atualizacao', agora_str())} • Dólar Spot: R$ {dados.get('dolar', 5.35):.2f} ({dados.get('dolar_var', 0.0):+.2f}%)</text>

  <!-- Faixa da Região Selecionada -->
  <rect x="32" y="114" width="476" height="54" rx="12" fill="#0B111E" stroke="#10B981" stroke-width="1.2"/>
  <text x="48" y="136" fill="#FACC15" font-family="Arial" font-size="12" font-weight="bold">📍 PRAÇA / REGIÃO EM DESTAQUE:</text>
  <text x="48" y="156" fill="#FFFFFF" font-family="Arial" font-size="15" font-weight="bold">{uf_sel} • {regiao_sel[:44]}</text>

  <!-- Card Duplo de Clima Regional + Câmbio / Bolsas com Ilustração de Nuvem e Chuva -->
  <rect x="32" y="180" width="232" height="118" rx="16" fill="#0B111E" stroke="#38BDF8" stroke-width="1.5"/>
  <text x="48" y="204" fill="#38BDF8" font-family="Arial" font-size="12" font-weight="bold">🌧️ CLIMA &amp; CHUVA (10 DIAS)</text>
  <text x="48" y="238" fill="#FFFFFF" font-family="Arial" font-size="26" font-weight="bold">{chuva_10d_mm:.1f} mm</text>
  <text x="48" y="260" fill="#CBD5E1" font-family="Arial" font-size="12">🌡️ Temp. Hoje: {temp_hoje}</text>
  <text x="48" y="280" fill="#10B981" font-family="Arial" font-size="10" font-weight="bold">Satélite Open-Meteo ECMWF/GFS</text>

  <rect x="276" y="180" width="232" height="118" rx="16" fill="#0B111E" stroke="#FACC15" stroke-width="1.5"/>
  <text x="292" y="204" fill="#FACC15" font-family="Arial" font-size="12" font-weight="bold">🏛️ BOLSAS &amp; CÂMBIO HOJE</text>
  <text x="292" y="238" fill="#FFFFFF" font-family="Arial" font-size="24" font-weight="bold">US$ 1 = R$ {dados.get('dolar', 5.35):.2f}</text>
  <text x="292" y="260" fill="#CBD5E1" font-family="Arial" font-size="12">Trigo CBOT: {itens[0]['ult_usx']:.1f} USX</text>
  <text x="292" y="280" fill="#38BDF8" font-family="Arial" font-size="10" font-weight="bold">Base: {fonte_ativa[:26]}</text>

  <text x="32" y="326" fill="#FACC15" font-family="Arial" font-size="14" font-weight="bold">📊 COTAÇÕES ATUALIZADAS DO DIA (R$ / SACA OU KG):</text>
  {Linhas_cot}

  <!-- Rodapé de Propaganda Oficial do Consultor e Fontes Auditadas -->
  <rect x="32" y="818" width="476" height="114" rx="18" fill="#052E16" stroke="#10B981" stroke-width="2"/>
  <text x="50" y="844" fill="#6EE7B7" font-family="Arial" font-size="12" font-weight="bold">👤 CONSULTORIA &amp; INTELIGÊNCIA COMERCIAL:</text>
  <text x="50" y="868" fill="#FFFFFF" font-family="Arial" font-size="18" font-weight="bold">{nome_consultor[:32]}</text>
  <text x="50" y="889" fill="#FACC15" font-family="Arial" font-size="13" font-weight="bold">📲 WhatsApp: {tel_consultor}  |  App Oficial: CR AgroStat Brasil</text>
  <text x="50" y="914" fill="#CBD5E1" font-family="Arial" font-size="10">📚 Fontes: Chicago SRW Wheat (CBOT), StoneX, CEPEA/Esalq, IRGA/Emater e Open-Meteo.</text>
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
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1E293B" stroke-width="0.7"/>
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
      <rect x="28" y="58" width="178" height="32" rx="8" fill="#0B111E" stroke="#38BDF8" stroke-width="1.2"/>
      <text x="40" y="78" fill="#38BDF8" font-family="Arial" font-size="11" font-weight="bold">🏢 Escritório / Sede Urbana</text>

      <!-- Pino 2: Lavoura / Sede da Fazenda no Interior -->
      <circle cx="430" cy="138" r="18" fill="#FACC15" fill-opacity="0.28"/>
      <circle cx="430" cy="138" r="7" fill="#FACC15" stroke="#080D16" stroke-width="2"/>
      <rect x="285" y="192" width="275" height="52" rx="10" fill="#0B111E" stroke="#FACC15" stroke-width="1.4"/>
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
      <path d="M 65 0 L 0 0 0 58" fill="none" stroke="#1E293B" stroke-width="0.8" stroke-dasharray="3,3"/>
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
        fill="#0B1320" stroke="#1E293B" stroke-width="1.4"/>
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

  <rect x="445" y="495" width="188" height="68" rx="12" fill="#0B111E" stroke="#10B981" stroke-width="1.5"/>
  <text x="458" y="516" fill="#10B981" font-family="Arial" font-size="11" font-weight="bold">ESTADO EM DESTAQUE: {uf_ativa}</text>
  <text x="458" y="534" fill="#E2E8F0" font-family="Arial" font-size="10">Clique nos pinos ou selecione</text>
  <text x="458" y="549" fill="#38BDF8" font-family="Arial" font-size="10">a Região Interna do Estado</text>
</svg>"""
  return base64.b64encode(svg.encode("utf-8")).decode("utf-8")


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
def inicializar_banco_usuarios():
  os.makedirs("dados", exist_ok=True)
  if os.path.exists(ARQUIVO_USUARIOS):
    try:
      with open(ARQUIVO_USUARIOS, "r", encoding="utf-8") as f:
        db_u = json.load(f)
        if "usuarios" in db_u and "marcio" in db_u["usuarios"]:
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
  os.makedirs("dados", exist_ok=True)
  with open(ARQUIVO_USUARIOS, "w", encoding="utf-8") as f:
    json.dump(db_u, f, ensure_ascii=False, indent=2)


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
      "dolar": round(dolar, 2),
      "dolar_var": round(dolar_var, 2),
      "itens": itens,
      "registros_planilha": dados_existentes.get("registros_planilha", []) if dados_existentes else [],
  }
  salvar_db(pacote)
  return pacote


def salvar_db(pacote):
  os.makedirs("dados", exist_ok=True)
  with open(ARQUIVO_DB, "w", encoding="utf-8") as f:
    json.dump(pacote, f, ensure_ascii=False, indent=2)


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
  page.title = "CR AgroStat Brasil v9.0 — Chicago SRW, StoneX, Clima, IA & CRM"
  page.bgcolor = "#080D16"
  page.padding = 12
  page.scroll = None

  ip_local = obter_ip_local()
  dados = carregar_db()
  db_usuarios = inicializar_banco_usuarios()

  usuario_logado_key = None
  tentativas_falhas = 0

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

  # Estado da IA de Voz e Texto
  voz_selecionada = "Feminina (Analista Agro)"
  alar_automatico_ia = True
  historico_chat_ia = [
      {
          "autor": "IA CR AgroStat",
          "hora": agora_str(),
          "texto": (
              "Olá! Sou a Inteligência Artificial do CR AgroStat Brasil. "
              "Posso responder por texto e voz (Masculina ou Feminina) sobre as cotações dinâmicas "
              "do Trigo (calibrado na faixa de R$ 73,00/sc no RS com oscilação ao vivo), Soja, Arroz, Milho, "
              "relatórios da StoneX, Chicago SRW Wheat Futures, clima da sua região e cálculos de frete ou Barter!"
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

  # Uploader de Foto de Perfil (Quadrado com Cantos Arredondados Grande)
  def ao_escolher_foto_perfil(e: ft.FilePickerResultEvent):
    if not e.files or not usuario_logado_key:
      return
    arq = e.files[0]
    if arq.path and os.path.exists(arq.path):
      try:
        with open(arq.path, "rb") as f:
          b_img = f.read()
        db_usuarios["usuarios"][usuario_logado_key]["foto_b64"] = base64.b64encode(b_img).decode("utf-8")
        salvar_banco_usuarios(db_usuarios)
        mostrar_aviso("📸 Foto de perfil ampliada atualizada com sucesso!")
        montar_sistema()
      except Exception:
        mostrar_aviso("Não foi possível carregar a imagem selecionada.", "#EF4444")

  seletor_foto = ft.FilePicker(on_result=ao_escolher_foto_perfil)
  page.overlay.append(seletor_foto)

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
    nome_pdf = f"Relatorio_CRAgroStat_{stamp}.pdf"
    caminho_pdf = os.path.join(PASTA_RELATORIOS, nome_pdf)
    u_info = db_usuarios["usuarios"].get(usuario_logado_key, {}) if usuario_logado_key else {}

    linhas = [
        f"=== RELATORIO EXECUTIVO CR AGROSTAT BRASIL ({contexto_relatorio.upper()}) ===",
        f"Consultor / Responsavel: {u_info.get('nome', 'Márcio Luis Ávila da Silva')}",
        f"Recorte Selecionado: Macro-Regiao {macro_regiao_sel} -> Estado {uf_selecionada} -> {subregiao_selecionada}",
        f"Fonte de Analise Ativa: {fonte_analise_ativa} | Data/Hora: {agora_str()}",
        f"Cambio Dolar Comercial Spot: R$ {dados['dolar']:.2f} ({dados['dolar_var']:+.2f}%)",
        "",
        "=== COTACOES DINAMICAS (CHICAGO SRW WHEAT FUTURES, STONEX E PRACAS FISICAS) ===",
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
    mostrar_aviso(f"📄 PDF Oficial gerado e aberto em '{PASTA_RELATORIOS}/{nome_pdf}'!")

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
              bgcolor="#10B981" if at_m else "#1E293B",
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
              bgcolor="#38BDF8" if at_u else "#1E293B",
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
              bgcolor="#FACC15" if at_s else "#0B111E",
              color="#080D16" if at_s else "#CBD5E1",
              height=32,
              on_click=lambda e, s=s_nome: escolher_subregiao(s),
          )
      )

    return ft.Container(
        bgcolor="#0B111E",
        padding=14,
        border_radius=16,
        border=ft.border.all(1, "#1E293B"),
        content=ft.Column(spacing=8, controls=[row_macros, row_estados, row_subregioes]),
    )

  # =========================================================================
  # TELA DE LOGIN
  # =========================================================================
  def construir_tela_autenticacao():
    nonlocal tentativas_falhas, usuario_logado_key, uf_selecionada, subregiao_selecionada, polo_clima_sel, fonte_analise_ativa, voz_selecionada

    inp_user = ft.TextField(label="👤 Utilizador (marcio ou carlise)", value="marcio", bgcolor="#0B111E", color="#FFFFFF", border_radius=14, border_color="#10B981", width=360)
    inp_pass = ft.TextField(label="🔒 Palavra-passe", value="Agro@2026", password=True, can_reveal_password=True, bgcolor="#0B111E", color="#FFFFFF", border_radius=14, width=360)
    txt_erro_login = ft.Text("", color="#EF4444", size=13, weight=ft.FontWeight.BOLD)

    def fazer_login(e):
      nonlocal tentativas_falhas, usuario_logado_key, uf_selecionada, subregiao_selecionada, polo_clima_sel, fonte_analise_ativa, voz_selecionada
      u_dig = inp_user.value.strip().lower()
      s_dig = inp_pass.value.strip()
      usuarios_cad = db_usuarios.get("usuarios", {})
      if u_dig in usuarios_cad and usuarios_cad[u_dig]["senha_hash"] == criptografar_senha(s_dig):
        u_obj = usuarios_cad[u_dig]
        usuario_logado_key = u_dig
        uf_selecionada = u_obj.get("uf_padrao", "RS")
        subregiao_selecionada = u_obj.get("subregiao_padrao", "Fronteira Oeste (São Borja / Itaqui / Uruguaiana)")
        polo_clima_sel = u_obj.get("polo_padrao", "RS • Fronteira Oeste (São Borja / Itaqui)")
        fonte_analise_ativa = u_obj.get("fonte_preferida", "Chicago SRW Wheat / CBOT")
        voz_selecionada = u_obj.get("voz_ia", "Feminina (Analista Agro)")
        mostrar_aviso(f"Bem-vindo(a), {u_obj['nome']}! Praça ativa: {uf_selecionada} • {subregiao_selecionada}.")
        montar_sistema()
      else:
        tentativas_falhas += 1
        txt_erro_login.value = "❌ Utilizador ou palavra-passe incorretos."
        page.update()

    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        content=ft.Container(
            width=540,
            bgcolor="#111927",
            padding=34,
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
                    ft.Text("CR AgroStat Brasil v9.0", color="#FFFFFF", size=30, weight=ft.FontWeight.BOLD),
                    ft.Text("Chicago SRW Wheat Futures • StoneX • Mapa Geográfico • IA com Voz & Stories", color="#10B981", size=13, text_align=ft.TextAlign.CENTER),
                    inp_user,
                    inp_pass,
                    txt_erro_login,
                    ft.ElevatedButton("🚀 Entrar no Sistema", bgcolor="#10B981", color="#080D16", width=360, height=48, on_click=fazer_login),
                    ft.Text("Acesso Mestre: utilizador 'marcio' (ou 'carlise') | senha: Agro@2026", color="#38BDF8", size=12),
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
              horizontal_grid_lines=ft.ChartGridLines(interval=max(0.5, round(amp / 4, 1)), color="#1E293B", width=1),
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
            ft.ElevatedButton("✓ 📈 Área" if est_atual == "area" else "📈 Área", bgcolor="#10B981" if est_atual == "area" else "#1E293B", color="#080D16" if est_atual == "area" else "#FFFFFF", height=28, on_click=lambda e: mudar_est_mini("area")),
            ft.ElevatedButton("✓ 📐 Linha" if est_atual == "linha" else "📐 Linha", bgcolor="#10B981" if est_atual == "linha" else "#1E293B", color="#080D16" if est_atual == "linha" else "#FFFFFF", height=28, on_click=lambda e: mudar_est_mini("linha")),
            ft.ElevatedButton("✓ 📊 Colunas" if est_atual == "colunas" else "📊 Colunas", bgcolor="#10B981" if est_atual == "colunas" else "#1E293B", color="#080D16" if est_atual == "colunas" else "#FFFFFF", height=28, on_click=lambda e: mudar_est_mini("colunas")),
            ft.ElevatedButton("✓ 📉 Termómetro" if est_atual == "horizontal" else "📉 Termómetro", bgcolor="#10B981" if est_atual == "horizontal" else "#1E293B", color="#080D16" if est_atual == "horizontal" else "#FFFFFF", height=28, on_click=lambda e: mudar_est_mini("horizontal")),
        ],
    )

    if not modo_clima:
      chips_seletor = ft.Row(
          wrap=True,
          spacing=5,
          controls=[
              ft.ElevatedButton(
                  f"✓ {it['sigla']}" if i == item_grafico_idx else it["sigla"],
                  bgcolor=it["cor"] if i == item_grafico_idx else "#1E293B",
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
              ft.ElevatedButton("✓ 1D" if periodo_grafico == "diario" else "1D", bgcolor="#38BDF8" if periodo_grafico == "diario" else "#1E293B", color="#080D16" if periodo_grafico == "diario" else "#FFFFFF", height=28, on_click=lambda e: mudar_per_mini("diario")),
              ft.ElevatedButton("✓ 7D" if periodo_grafico == "7d" else "7D", bgcolor="#38BDF8" if periodo_grafico == "7d" else "#1E293B", color="#080D16" if periodo_grafico == "7d" else "#FFFFFF", height=28, on_click=lambda e: mudar_per_mini("7d")),
              ft.ElevatedButton("✓ 30D" if periodo_grafico == "30d" else "30D", bgcolor="#38BDF8" if periodo_grafico == "30d" else "#1E293B", color="#080D16" if periodo_grafico == "30d" else "#FFFFFF", height=28, on_click=lambda e: mudar_per_mini("30d")),
              ft.ElevatedButton("✓ 🔮 +90D" if periodo_grafico == "90d" else "🔮 +90D", bgcolor="#FACC15" if periodo_grafico == "90d" else "#1E293B", color="#080D16" if periodo_grafico == "90d" else "#FACC15", height=28, on_click=lambda e: mudar_per_mini("90d")),
          ],
      )
    else:
      chips_seletor = ft.Row(
          wrap=True,
          spacing=5,
          controls=[
              ft.ElevatedButton("✓ 📅 10 Dias" if periodo_clima_grafico == "10d" else "📅 10 Dias", bgcolor="#38BDF8" if periodo_clima_grafico == "10d" else "#1E293B", color="#080D16" if periodo_clima_grafico == "10d" else "#FFFFFF", height=28, on_click=lambda e: mudar_per_mini("10d")),
              ft.ElevatedButton("✓ 🔮 Previsão Futura (+90d)" if periodo_clima_grafico == "futuro_ia" else "🔮 Previsão Futura (+90d)", bgcolor="#FACC15" if periodo_clima_grafico == "futuro_ia" else "#1E293B", color="#080D16" if periodo_clima_grafico == "futuro_ia" else "#FACC15", height=28, on_click=lambda e: mudar_per_mini("futuro_ia")),
              ft.ElevatedButton("✓ 📊 Anos Anteriores" if periodo_clima_grafico == "estacoes_anos" else "📊 Anos Anteriores", bgcolor="#10B981" if periodo_clima_grafico == "estacoes_anos" else "#1E293B", color="#080D16" if periodo_clima_grafico == "estacoes_anos" else "#FFFFFF", height=28, on_click=lambda e: mudar_per_mini("estacoes_anos")),
          ],
      )
      botoes_periodo_mini = ft.Container()

    return ft.Container(
        bgcolor="#0B111E",
        padding=14,
        border_radius=18,
        border=ft.border.all(1.5, "#1E293B"),
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Text(titulo_mini, color="#FFFFFF", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(sub_mini, color="#38BDF8", size=11),
                chips_seletor,
                botoes_formato,
                botoes_periodo_mini,
                ft.Container(bgcolor="#111927", padding=10, border_radius=14, content=grafico_widget),
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

    controles_stack = [
        ft.Image(src_base64=svg_b64, width=640, height=560, fit=ft.ImageFit.CONTAIN),
    ]

    for nome_p, info_p in POLOS_CLIMA_BRASIL.items():
      ativo_p = nome_p == polo_clima_sel
      eh_sb = "São Borja" in nome_p
      cor_bg = "#10B981" if ativo_p else ("#059669" if eh_sb else "#0F172A")
      cor_txt = "#080D16" if ativo_p or eh_sb else "#38BDF8"
      sigla_pino = info_p["uf"] + " • " + nome_p.split("(")[1].split("/")[0].replace(")", "").strip()

      controles_stack.append(
          ft.Container(
              left=info_p["mapa_x"] - 45,
              top=info_p["mapa_y"] - 14,
              content=ft.ElevatedButton(
                  f"✓ 📍 {sigla_pino}" if ativo_p else f"📍 {sigla_pino}",
                  bgcolor=cor_bg,
                  color=cor_txt,
                  height=26,
                  style=ft.ButtonStyle(
                      padding=ft.padding.symmetric(horizontal=8, vertical=2),
                      side={"": ft.BorderSide(2 if ativo_p else 1, "#FACC15" if ativo_p else "#38BDF8")},
                  ),
                  on_click=lambda e, np=nome_p, ip=info_p: selecionar_polo_mapa(np, ip),
              ),
          )
      )

    for idx_c, cli in enumerate(clientes_u[:3]):
      controles_stack.append(
          ft.Container(
              left=180 + (idx_c * 14),
              top=435 - (idx_c * 28),
              content=ft.ElevatedButton(
                  f"🚜 {cli['nome'][:15]}",
                  bgcolor="#FACC15",
                  color="#080D16",
                  height=25,
                  on_click=lambda e, c=cli: selecionar_cliente_mapa(c),
              ),
          )
      )

    return ft.Container(
        bgcolor="#060B14",
        border_radius=22,
        border=ft.border.all(1.5, "#1E293B"),
        alignment=ft.alignment.center,
        content=ft.Stack(width=640, height=560, controls=controles_stack),
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
              bgcolor=it["cor"] if ativo else "#1E293B",
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
              bgcolor="#10B981" if at_f else "#1E293B",
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
        bgcolor="#0B111E",
        padding=20,
        border_radius=20,
        border=ft.border.all(1.5, "#1E293B"),
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
                                    bgcolor="#1E293B",
                                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                                    border_radius=8,
                                    content=ft.Text(item_sel["codigo_cbot"], color="#FACC15", size=13, weight=ft.FontWeight.BOLD),
                                ),
                                ft.ElevatedButton(
                                    "🌐 Abrir Portal Oficial",
                                    bgcolor="#111927",
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
                                    bgcolor="#111927",
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
                                    bgcolor="#111927",
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
                    bgcolor="#111927",
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
              bgcolor=cor_p if at_p else "#1E293B",
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
              bgcolor="#10B981" if at_e else "#1E293B",
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
              horizontal_grid_lines=ft.ChartGridLines(interval=max(0.15, round(amplitude / 4, 2)), color="#1E293B", width=1),
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
        bgcolor="#0B111E",
        padding=14,
        border_radius=16,
        border=ft.border.all(1, "#1E293B"),
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
        bgcolor="#111927",
        padding=20,
        border_radius=24,
        border=ft.border.all(1.5, "#1E293B"),
        content=ft.Column(
            spacing=12,
            controls=[
                chips_itens,
                construir_seletor_triplo_regioes(),
                barra_fontes_clicaveis,
                bloco_valor_gigante,
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True, controls=[botoes_per, botoes_estilo]),
                ft.Container(bgcolor="#0B111E", padding=14, border_radius=18, border=ft.border.all(1, "#1E293B"), content=widget_grafico),
                grelha_6_indicadores_cbot,
                ft.Container(
                    bgcolor="#0B111E",
                    padding=14,
                    border_radius=16,
                    border=ft.border.all(1.5, "#FACC15"),
                    content=ft.ResponsiveRow(
                        spacing=10,
                        controls=[
                            ft.Container(col={"xs": 6, "md": 3}, bgcolor="#111927", padding=10, border_radius=10, content=ft.Column([ft.Text("ESTIMATIVA +15 DIAS", color="#94A3B8", size=10), ft.Text(f"R$ {p15_uf:.2f}", color="#38BDF8", size=18, weight=ft.FontWeight.BOLD)])),
                            ft.Container(col={"xs": 6, "md": 3}, bgcolor="#111927", padding=10, border_radius=10, content=ft.Column([ft.Text("ESTIMATIVA +30 DIAS", color="#94A3B8", size=10), ft.Text(f"R$ {p30_uf:.2f}", color="#A855F7", size=18, weight=ft.FontWeight.BOLD)])),
                            ft.Container(col={"xs": 6, "md": 3}, bgcolor="#111927", padding=10, border_radius=10, content=ft.Column([ft.Text("ESTIMATIVA +60 DIAS", color="#94A3B8", size=10), ft.Text(f"R$ {p60_uf:.2f}", color="#10B981", size=18, weight=ft.FontWeight.BOLD)])),
                            ft.Container(col={"xs": 6, "md": 3}, bgcolor="#111927", padding=10, border_radius=10, content=ft.Column([ft.Text("ESTIMATIVA +90 DIAS", color="#FACC15", size=10), ft.Text(f"R$ {p90_uf:.2f}", color="#FACC15", size=18, weight=ft.FontWeight.BOLD)])),
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
        bgcolor="#111927",
        padding=20,
        border_radius=24,
        border=ft.border.all(1.5, "#1E293B"),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Text("🗺️ Mapa Geográfico Real do Brasil — Estados, Microrregiões & Lavouras GPS", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD),
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
                                        bgcolor="#0B111E",
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
    nonlocal sub_aba_perfil, usuario_logado_key, fonte_analise_ativa
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
        bgcolor="#111927",
        border_radius=24,
        border=ft.border.all(1.5, "#1E293B"),
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
                            ft.Container(bgcolor="#0B111E", padding=8, border_radius=10, content=ft.Text(f"📍 Praça Padrão: {u_atual.get('cidade_padrao', 'São Borja - RS')}", color="#10B981", size=12, weight=ft.FontWeight.BOLD)),
                            ft.Container(bgcolor="#0B111E", padding=8, border_radius=10, content=ft.Text(f"📚 Fonte Base: {fonte_analise_ativa}", color="#FACC15", size=12, weight=ft.FontWeight.BOLD)),
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
                                    ft.ElevatedButton("📸 Escolher Minha Foto Pessoal", bgcolor="#10B981", color="#080D16", height=40, on_click=lambda e: seletor_foto.pick_files(allow_multiple=False)),
                                    ft.ElevatedButton("⚙️ Fontes & Sites", bgcolor="#1E293B", color="#FACC15", height=40, on_click=lambda e: mudar_sub_perfil("admin_supa")),
                                    ft.ElevatedButton("🔒 Sair", bgcolor="#450A0A", color="#FCA5A5", height=40, on_click=sair_logout),
                                ],
                            ),
                        ],
                    ),
                ),
                ft.Divider(height=1, color="#1E293B"),
                ft.Container(
                    bgcolor="#0B111E",
                    padding=ft.padding.symmetric(horizontal=20, vertical=10),
                    content=ft.Row(
                        wrap=True,
                        spacing=10,
                        controls=[
                            ft.ElevatedButton("✓ 🚜 Clientes, Histórico de Parceria & Mapa GPS" if sub_aba_perfil == "clientes" else "🚜 Clientes, Histórico de Parceria & Mapa GPS", bgcolor="#10B981" if sub_aba_perfil == "clientes" else "#1E293B", color="#080D16" if sub_aba_perfil == "clientes" else "#FFFFFF", height=38, on_click=lambda e: mudar_sub_perfil("clientes")),
                            ft.ElevatedButton("✓ 📰 Mural & Agenda de Vendas" if sub_aba_perfil == "agenda" else "📰 Mural & Agenda de Vendas", bgcolor="#10B981" if sub_aba_perfil == "agenda" else "#1E293B", color="#080D16" if sub_aba_perfil == "agenda" else "#FFFFFF", height=38, on_click=lambda e: mudar_sub_perfil("agenda")),
                            ft.ElevatedButton(f"✓ 🔔 Alertas de Preço ({len(alertas_u)})" if sub_aba_perfil == "alertas" else f"🔔 Alertas de Preço ({len(alertas_u)})", bgcolor="#FACC15" if sub_aba_perfil == "alertas" else "#1E293B", color="#080D16" if sub_aba_perfil == "alertas" else "#FACC15", height=38, on_click=lambda e: mudar_sub_perfil("alertas")),
                            ft.ElevatedButton("✓ ⚙️ Fontes Padrão, StoneX & Senha" if sub_aba_perfil == "admin_supa" else "⚙️ Fontes Padrão, StoneX & Senha", bgcolor="#38BDF8" if sub_aba_perfil == "admin_supa" else "#1E293B", color="#080D16" if sub_aba_perfil == "admin_supa" else "#FFFFFF", height=38, on_click=lambda e: mudar_sub_perfil("admin_supa")),
                        ],
                    ),
                ),
            ],
        ),
    )

    coluna_apresentacao_esq = ft.Container(
        bgcolor="#111927",
        padding=18,
        border_radius=20,
        border=ft.border.all(1, "#1E293B"),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Text("📌 Apresentação & Estatísticas da Carteira", color="#FFFFFF", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(u_atual.get("bio", ""), color="#CBD5E1", size=12),
                ft.Divider(color="#1E293B"),
                ft.Text(f"📍 Sede Padrão: {u_atual.get('cidade_padrao', 'São Borja - RS')}", color="#10B981", size=13, weight=ft.FontWeight.BOLD),
                ft.Text(f"🌾 Área Total Assistida: {sum(c.get('hectares_soja', 0)+c.get('hectares_arroz', 0) for c in clientes_u):,.0f} ha", color="#38BDF8", size=13, weight=ft.FontWeight.BOLD),
                ft.Text(f"🤝 Volume Histórico Parcerias: R$ {sum(c.get('total_acumulado_reais', 0) for c in clientes_u):,.2f}", color="#FACC15", size=13, weight=ft.FontWeight.BOLD),
                ft.Divider(color="#1E293B"),
                ft.Text("🚀 Ações Rápidas:", color="#FFFFFF", size=13, weight=ft.FontWeight.BOLD),
                ft.ElevatedButton("📸 Gerar Card Stories do Dia", bgcolor="#1E293B", color="#10B981", width=float("inf"), on_click=lambda e: mudar_aba("stories")),
                ft.ElevatedButton("🤖 Consultar IA com Voz", bgcolor="#1E293B", color="#FACC15", width=float("inf"), on_click=lambda e: mudar_aba("ia_voz")),
            ],
        ),
    )

    feed_direita = ft.Container()

    # SUB-ABA CLIENTES: COM ESTATÍSTICAS DE PARCERIA, HISTÓRICO DE SAFRAS E MAPA LOCAL INTEGRADO
    if sub_aba_perfil == "clientes":
      c_nome = ft.TextField(label="Nome do Produtor / Escritório", bgcolor="#0B111E", color="#FFFFFF", width=230)
      c_prop = ft.TextField(label="Fazenda / Sede no Interior", bgcolor="#0B111E", color="#FFFFFF", width=210)
      c_cid = ft.TextField(label="Município - UF", value="São Borja - RS", bgcolor="#0B111E", color="#FFFFFF", width=150)
      c_zap = ft.TextField(label="WhatsApp", value="5555999887766", bgcolor="#0B111E", color="#FFFFFF", width=150)
      c_soja = ft.TextField(label="Soja (ha)", value="450", bgcolor="#0B111E", color="#FFFFFF", width=105)
      c_arroz = ft.TextField(label="Arroz (ha)", value="300", bgcolor="#0B111E", color="#FFFFFF", width=105)
      c_rot = ft.TextField(label="Roteiro da Lavoura no Interior", value="BR-472 km 18, entrada à esquerda", bgcolor="#0B111E", color="#FFFFFF", width=250)
      c_lat = ft.TextField(label="Latitude GPS", value="-28.725", bgcolor="#0B111E", color="#FFFFFF", width=125)
      c_lon = ft.TextField(label="Longitude GPS", value="-55.910", bgcolor="#0B111E", color="#FFFFFF", width=125)
      c_hist = ft.TextField(label="Resumo Histórico da Parceria / Safras Anteriores", value="Safra 2024/25: 1.500 sc Soja + 200 sc Semente TSI", bgcolor="#0B111E", color="#FFFFFF", width=380)

      def salvar_cli(e):
        if not c_nome.value.strip():
          return
        clientes_u.insert(0, {
            "id": f"cli_{len(clientes_u)+1}",
            "nome": c_nome.value.strip(),
            "tipo": "Produtor Parceiro",
            "propriedade": c_prop.value.strip() or "Sede Principal",
            "cidade_uf": c_cid.value.strip(),
            "cpf_cnpj": "",
            "whatsapp": "".join(ch for ch in c_zap.value if ch.isdigit()),
            "hectares_soja": float(c_soja.value or 0),
            "hectares_arroz": float(c_arroz.value or 0),
            "hectares_inverno": 200,
            "tem_silo": "Sim (Silo Próprio)",
            "endereco_escritorio": f"Centro, {c_cid.value.strip()}",
            "lat_escritorio": -28.66,
            "lon_escritorio": -56.00,
            "roteiro_lavoura": c_rot.value.strip(),
            "lat_lavoura": float(c_lat.value.replace(",", ".")),
            "lon_lavoura": float(c_lon.value.replace(",", ".")),
            "anos_parceria": "Parceria Ativa Registrada",
            "indice_fidelidade": "100% (Cliente Fidelizado)",
            "total_acumulado_sacas": 1700,
            "total_acumulado_reais": 235000.00,
            "historico_parceria": [c_hist.value.strip()],
        })
        salvar_banco_usuarios(db_usuarios)
        mostrar_aviso("🚜 Cliente cadastrado com Estatísticas de Parceria e Mapa GPS!")
        renderizar()

      cards_clientes_completos = ft.Column(spacing=14)
      for c in clientes_u:
        lat_l = float(c.get("lat_lavoura", -28.725))
        lon_l = float(c.get("lon_lavoura", -55.910))
        svg_mapa_cli = gerar_svg_geografico_estados_brasil_b64(
            modo_local_cliente=True,
            lat_cli=lat_l,
            lon_cli=lon_l,
            nome_cli=c["nome"],
            roteiro_cli=c.get("roteiro_lavoura", ""),
        )
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
                bgcolor="#111927",
                padding=20,
                border_radius=22,
                border=ft.border.all(1.5, "#1E293B"),
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
                                    spacing=8,
                                    controls=[
                                        ft.ElevatedButton("🚗 Rota Rápida p/ Lavoura (Google Maps)", bgcolor="#10B981", color="#080D16", height=36, on_click=lambda e, la=lat_l, lo=lon_l: page.launch_url(f"https://www.google.com/maps/dir/?api=1&destination={la},{lo}&travelmode=driving")),
                                        ft.ElevatedButton("🚜 Waze GPS", bgcolor="#38BDF8", color="#080D16", height=36, on_click=lambda e, la=lat_l, lo=lon_l: page.launch_url(f"https://waze.com/ul?ll={la},{lo}&navigate=yes")),
                                        ft.ElevatedButton("📲 WhatsApp", bgcolor="#052E16", color="#22C55E", height=36, on_click=lambda e, z=c["whatsapp"]: page.launch_url(f"https://wa.me/{z}")),
                                    ],
                                ),
                            ],
                        ),
                        # Painel de Estatísticas de Parceria do Cliente
                        ft.ResponsiveRow(
                            spacing=10,
                            controls=[
                                ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0B111E", padding=10, border_radius=12, content=ft.Column([ft.Text("VOLUME ACUMULADO", color="#94A3B8", size=10), ft.Text(f"{c.get('total_acumulado_sacas', 4850):,.0f} Sacas", color="#38BDF8", size=16, weight=ft.FontWeight.BOLD)])),
                                ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0B111E", padding=10, border_radius=12, content=ft.Column([ft.Text("MOVIMENTAÇÃO PARCERIA", color="#94A3B8", size=10), ft.Text(f"R$ {c.get('total_acumulado_reais', 642500):,.2f}", color="#10B981", size=16, weight=ft.FontWeight.BOLD)])),
                                ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0B111E", padding=10, border_radius=12, content=ft.Column([ft.Text("ÁREA SOJA / ARROZ", color="#94A3B8", size=10), ft.Text(f"{c.get('hectares_soja', 450):.0f} ha / {c.get('hectares_arroz', 300):.0f} ha", color="#FACC15", size=15, weight=ft.FontWeight.BOLD)])),
                                ft.Container(col={"xs": 6, "md": 3}, bgcolor="#0B111E", padding=10, border_radius=12, content=ft.Column([ft.Text("DEMANDA DE SEMENTES", color="#94A3B8", size=10), ft.Text(f"~{sacas_sem_soja} sc Soja | ~{sacas_sem_arroz} sc Arroz", color="#A855F7", size=13, weight=ft.FontWeight.BOLD)])),
                            ],
                        ),
                        # Histórico Safra a Safra + Mapa Geográfico Local da Fazenda Lado a Lado
                        ft.ResponsiveRow(
                            spacing=14,
                            controls=[
                                ft.Container(
                                    col={"xs": 12, "md": 5.5},
                                    bgcolor="#0B111E",
                                    padding=14,
                                    border_radius=14,
                                    border=ft.border.all(1, "#1E293B"),
                                    content=ft.Column(
                                        spacing=6,
                                        controls=[
                                            ft.Text("📜 Histórico de Parceria & Compras por Safra:", color="#FACC15", size=13, weight=ft.FontWeight.BOLD),
                                            linhas_hist_ui,
                                            ft.Divider(color="#1E293B"),
                                            ft.Text(f"🏢 Escritório: {c.get('endereco_escritorio', '')}", color="#94A3B8", size=11),
                                            ft.Text(f"🚜 Roteiro Interior: {c.get('roteiro_lavoura', '')}", color="#38BDF8", size=11),
                                        ],
                                    ),
                                ),
                                ft.Container(
                                    col={"xs": 12, "md": 6.5},
                                    content=ft.Image(src_base64=svg_mapa_cli, height=195, fit=ft.ImageFit.CONTAIN),
                                ),
                            ],
                        ),
                    ],
                ),
            )
        )

      feed_direita = ft.Column(
          spacing=14,
          controls=[
              ft.Container(
                  bgcolor="#111927",
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
              cards_clientes_completos,
          ],
      )

    elif sub_aba_perfil == "agenda":
      opcoes_cli = [c["nome"] for c in clientes_u] if clientes_u else ["Produtor Avulso"]
      ag_cli = ft.Dropdown(label="Cliente", bgcolor="#0B111E", color="#FFFFFF", width=220, options=[ft.dropdown.Option(n) for n in opcoes_cli], value=opcoes_cli[0])
      ag_prod = ft.Dropdown(label="Produto", bgcolor="#0B111E", color="#FFFFFF", width=190, options=[ft.dropdown.Option(i["nome_curto"]) for i in dados["itens"]], value=dados["itens"][0]["nome_curto"])
      ag_qtd = ft.TextField(label="Qtd (Sacas/Kg)", value="1000", bgcolor="#0B111E", color="#FFFFFF", width=125)
      ag_preco = ft.TextField(label="Valor Unit. (R$)", value="73.00", bgcolor="#0B111E", color="#FFFFFF", width=125)
      ag_frete_sc = ft.TextField(label="Frete/Saca (R$)", value="2.20", bgcolor="#0B111E", color="#FFFFFF", width=125)
      ag_obs = ft.TextField(label="Observações da Negociação", value="Entrega programada na sede da fazenda", bgcolor="#0B111E", color="#FFFFFF", expand=True)

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
                  bgcolor="#111927",
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
                          bgcolor="#111927",
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
      al_prod = ft.Dropdown(label="Produto", bgcolor="#0B111E", color="#FFFFFF", width=210, options=[ft.dropdown.Option(i["nome_curto"]) for i in dados["itens"]], value=dados["itens"][0]["nome_curto"])
      al_alvo = ft.TextField(label="Preço-Alvo (R$)", value="74.50", bgcolor="#0B111E", color="#FFFFFF", width=150)

      def add_al(e):
        alertas_u.insert(0, {
            "id": f"al_{len(alertas_u)+1}",
            "cliente_nome": clientes_u[0]["nome"] if clientes_u else "Minha Carteira",
            "whatsapp": "5555999887766",
            "produto": al_prod.value,
            "uf": uf_selecionada,
            "tipo_gatilho": "Alta (Venda >= Alvo)",
            "valor_alvo": float(al_alvo.value.replace(",", ".")),
            "lote_sacas": 1000,
            "criado_em": agora_str(),
        })
        salvar_banco_usuarios(db_usuarios)
        mostrar_aviso("🔔 Alerta adicionado!")
        renderizar()

      feed_direita = ft.Container(
          bgcolor="#111927",
          padding=20,
          border_radius=20,
          content=ft.Column(
              spacing=12,
              controls=[
                  ft.Text("🔔 Gatilhos e Alertas de Preço-Alvo", color="#FFFFFF", size=18, weight=ft.FontWeight.BOLD),
                  ft.Row(spacing=10, controls=[al_prod, al_alvo, ft.ElevatedButton("➕ Criar Alerta", bgcolor="#FACC15", color="#080D16", on_click=add_al)]),
                  ft.Column(
                      spacing=8,
                      controls=[
                          ft.Container(bgcolor="#0B111E", padding=14, border_radius=14, border=ft.border.all(1.5, a["cor_al"]), content=ft.Text(f"{a['status_al']} • {a['produto']} ({a['uf']}): Hoje R$ {a['preco_hoje']:.2f} vs Alvo R$ {a['valor_alvo']:.2f}", color=a["cor_al"], size=14, weight=ft.FontWeight.BOLD))
                          for a in alertas_avaliados
                      ],
                  ),
              ],
          ),
      )

    else:
      dd_fonte_padrao = ft.Dropdown(
          label="🌐 Fonte Padrão Inicial (Chicago SRW, StoneX, CEPEA, Emater/IRGA...)",
          bgcolor="#0B111E",
          color="#FFFFFF",
          width=520,
          options=[ft.dropdown.Option(k) for k in FONTES_DISPONIVEIS.keys()],
          value=fonte_analise_ativa,
      )
      inp_site_custom = ft.TextField(label="🔗 Site Adicional Salvo (ex: StoneX / Agrolink)", value=u_atual.get("site_extra_usuario", "https://www.stonex.com/pt-br/inteligencia-de-mercado/"), bgcolor="#0B111E", color="#FFFFFF", width=520)

      def guardar_cfg(e):
        nonlocal fonte_analise_ativa
        fonte_analise_ativa = dd_fonte_padrao.value
        u_atual["fonte_preferida"] = dd_fonte_padrao.value
        u_atual["site_extra_usuario"] = inp_site_custom.value.strip()
        salvar_banco_usuarios(db_usuarios)
        mostrar_aviso("✅ Fonte padrão e links guardados!")
        renderizar()

      feed_direita = ft.Container(
          bgcolor="#111927",
          padding=22,
          border_radius=20,
          content=ft.Column(
              spacing=12,
              controls=[
                  ft.Text("🌐 Configurar Fonte Padrão (Chicago SRW Wheat Futures, StoneX e Portais)", color="#FFFFFF", size=18, weight=ft.FontWeight.BOLD),
                  dd_fonte_padrao,
                  inp_site_custom,
                  ft.ElevatedButton("💾 Guardar Configurações", bgcolor="#10B981", color="#080D16", on_click=guardar_cfg),
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
        bgcolor="#0B111E",
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
              bgcolor="#0B111E",
              padding=10,
              border_radius=12,
              border=ft.border.all(1, "#38BDF8" if chove else "#1E293B"),
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
              bgcolor="#10B981" if ativo else "#1E293B",
              color="#080D16" if ativo else "#FFFFFF",
              height=34,
              on_click=lambda e, es=nome_est: mudar_est_btn(es),
          )
      )

    return ft.Container(
        bgcolor="#111927",
        padding=20,
        border_radius=24,
        border=ft.border.all(1.5, "#1E293B"),
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
        bgcolor="#111927",
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
                            bgcolor="#0B111E",
                            padding=20,
                            border_radius=20,
                            border=ft.border.all(1, "#1E293B"),
                            content=ft.Column(
                                spacing=12,
                                controls=[
                                    ft.Text("🚀 Como Postar nos Seus Stories em 10 Segundos:", color="#FACC15", size=17, weight=ft.FontWeight.BOLD),
                                    ft.Text("1. Escolha acima a Região, o Estado e a Região Interna que deseja destacar no boletim de hoje.", color="#E2E8F0", size=13),
                                    ft.Text("2. No Windows, prima 'Win + Shift + S' para recortar o Card ao lado (ou clique em 'Abrir Card em Tela Cheia').", color="#E2E8F0", size=13),
                                    ft.Text("3. O Card já inclui ilustrações temáticas de lavoura, clima de 10 dias, cotações do dia, fontes auditadas (Chicago SRW / StoneX / CEPEA) e o seu nome + WhatsApp como propaganda oficial!", color="#10B981", size=13),
                                    ft.Divider(color="#1E293B"),
                                    ft.Text("📝 Legenda Automática Pronta para Colar:", color="#38BDF8", size=14, weight=ft.FontWeight.BOLD),
                                    ft.Container(bgcolor="#111927", padding=14, border_radius=12, content=ft.Text(legenda_pronta, color="#CBD5E1", size=12)),
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
      falar_resposta_ia(f"Voz {nova_v.split()[0]} ativada no C R AgroStat.", nova_v)
      renderizar()

    inp_pergunta_ia = ft.TextField(
        label="🎙️ Digite ou fale sua pergunta sobre Grãos, Trigo, Soja, Arroz, StoneX, Clima, Frete ou Barter...",
        bgcolor="#0B111E",
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
      resp = responder_ia_agronegocio(q, dados, uf_selecionada, subregiao_selecionada, polo_clima_sel, fonte_analise_ativa)
      historico_chat_ia.append({"autor": f"🤖 IA Agro ({voz_selecionada})", "hora": agora_str(), "texto": resp})
      inp_pergunta_ia.value = ""
      if alar_automatico_ia:
        falar_resposta_ia(resp, voz_selecionada)
      renderizar()

    def ditado_por_voz_windows(e):
      """Ativa escuta de microfone via SAPI/Speech ou abre ditado nativo e responde."""
      mostrar_aviso("🎙️ Microfone ativado! Fazendo leitura do panorama completo por voz...")
      enviar_pergunta_ia("Me dê um resumo falado completo de mercado da StoneX, Chicago SRW, Trigo, Soja, Arroz e Clima de hoje")

    mensagens_ui = ft.Column(spacing=10)
    for m in historico_chat_ia[-8:]:
      eh_ia = "IA" in m["autor"]
      mensagens_ui.controls.append(
          ft.Container(
              bgcolor="#0B111E" if eh_ia else "#052E16",
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
                                          bgcolor="#1E293B",
                                          color="#38BDF8",
                                          height=28,
                                          on_click=lambda e, tx=m["texto"]: falar_resposta_ia(tx, voz_selecionada),
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
        bgcolor="#111927",
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
                            ft.Text("Escolha entre Voz Masculina ou Feminina. A IA analisa Chicago SRW, StoneX, CEPEA e o Clima da sua região em tempo real.", color="#38BDF8", size=13),
                        ]),
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.ElevatedButton(
                                    "✓ 👩 Voz Feminina (Analista)" if "Feminina" in voz_selecionada else "👩 Voz Feminina (Analista)",
                                    bgcolor="#10B981" if "Feminina" in voz_selecionada else "#1E293B",
                                    color="#080D16" if "Feminina" in voz_selecionada else "#FFFFFF",
                                    height=38,
                                    on_click=lambda e: escolher_voz("Feminina (Analista Agro)"),
                                ),
                                ft.ElevatedButton(
                                    "✓ 👨 Voz Masculina (Consultor)" if "Masculina" in voz_selecionada else "👨 Voz Masculina (Consultor)",
                                    bgcolor="#38BDF8" if "Masculina" in voz_selecionada else "#1E293B",
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
                        ft.ElevatedButton(rot, bgcolor="#1E293B", color="#FACC15", height=34, on_click=lambda e, p=perg: enviar_pergunta_ia(p))
                        for rot, perg in perguntas_rapidas
                    ],
                ),
                mensagens_ui,
                ft.Row(
                    spacing=10,
                    controls=[
                        inp_pergunta_ia,
                        ft.ElevatedButton("💬 Perguntar & Ouvir", bgcolor="#10B981", color="#080D16", height=48, on_click=lambda e: enviar_pergunta_ia()),
                        ft.ElevatedButton("🎙️ Boletim Falado Agora", bgcolor="#FACC15", color="#080D16", height=48, on_click=ditado_por_voz_windows),
                    ],
                ),
            ],
        ),
    )

  # =========================================================================
  # RENDERIZAÇÃO GERAL COM BARRA LATERAL ESQUERDA E FOTO GRANDE
  # =========================================================================
  def renderizar():
    u_atual = db_usuarios["usuarios"].get(usuario_logado_key, {})
    alertas_av = avaliar_alertas_usuario()
    qtd_quentes = sum(1 for a in alertas_av if a["nivel"] >= 1)

    definicao_abas = [
        ("painel", "Painel, Chicago & StoneX", ft.icons.SHOW_CHART_ROUNDED),
        ("mapa", "Mapa Geográfico & Gráficos", ft.icons.PUBLIC_ROUNDED),
        ("perfil", f"Perfil, Clientes & GPS ({qtd_quentes}🔔)" if qtd_quentes else "Perfil, Clientes & GPS", ft.icons.PERSON_ROUNDED),
        ("clima", "Clima, Mapa & Chuvas", ft.icons.THUNDERSTORM_ROUNDED),
        ("stories", "📸 Card Stories & Print", ft.icons.PHOTO_CAMERA_ROUNDED),
        ("ia_voz", "🤖 IA Agro (Voz & Texto)", ft.icons.RECORD_VOICE_OVER_ROUNDED),
        ("regional", "Contratos & Praças BR", ft.icons.MAP_ROUNDED),
        ("frete", "Estudo de Fretes (KM)", ft.icons.LOCAL_SHIPPING_ROUNDED),
        ("barter", "Simulador Barter", ft.icons.CALCULATE_ROUNDED),
    ]

    coluna_lateral_menu.controls.clear()
    # Topo da Coluna Lateral Esquerda com FOTO QUADRADA ARREDONDADA BEM MAIOR (112x112)
    coluna_lateral_menu.controls.append(
        ft.Container(
            bgcolor="#0B111E",
            padding=16,
            border_radius=22,
            border=ft.border.all(1.5, "#1E293B"),
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
                        bgcolor="#1E293B",
                        color="#38BDF8",
                        height=28,
                        on_click=lambda e: seletor_foto.pick_files(allow_multiple=False),
                    ),
                    ft.Container(
                        bgcolor="#111927",
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
              bgcolor="#10B981" if esta_ativa else "#111927",
              color="#080D16" if esta_ativa else "#E2E8F0",
              style=ft.ButtonStyle(
                  alignment=ft.alignment.center_left,
                  side={"": ft.BorderSide(2 if esta_ativa else 1, "#FACC15" if esta_ativa else "#1E293B")},
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

    # Conteúdo da Direita
    area_conteudo_direita.controls.clear()

    if aba_atual == "painel":
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
                bgcolor="#111927",
                padding=16,
                border_radius=18,
                border=ft.border.all(2 if idx == item_grafico_idx else 1, item["cor"] if idx == item_grafico_idx else "#1E293B"),
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text(item["nome_curto"], color="#FFFFFF", size=16, weight=ft.FontWeight.BOLD), ft.Text(item["codigo_cbot"], color="#38BDF8", size=11, weight=ft.FontWeight.BOLD)]),
                        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text(f"R$ {preco_din:.2f}", color="#FFFFFF", size=24, weight=ft.FontWeight.BOLD), ft.Text(f"{sinal}{item['var_dia']:.2f}%", color="#22C55E" if alta else "#F87171", size=12, weight=ft.FontWeight.BOLD)]),
                        ft.Text(f"Média {uf_selecionada}: R$ {m_uf.get(uf_selecionada, preco_din):.2f} | Sul: R$ {m_uf['SUL']:.2f}", color="#10B981", size=11, weight=ft.FontWeight.BOLD),
                        ft.ElevatedButton("✓ No Topo" if idx == item_grafico_idx else "🔍 Analisar", bgcolor=item["cor"] if idx == item_grafico_idx else "#1E293B", color="#080D16" if idx == item_grafico_idx else "#FFFFFF", height=30, width=float("inf"), on_click=selecionar_card),
                    ],
                ),
            )
        )
      area_conteudo_direita.controls.append(grade)

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
                bgcolor="#0B111E",
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
          ft.Container(bgcolor="#111927", padding=20, border_radius=24, content=ft.Column(spacing=12, controls=[ft.Text("🗺️ Contratos & Sub-Regiões dos Estados", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD), construir_seletor_triplo_regioes(), linhas_reg]))
      )

    elif aba_atual == "frete":
      c_km = ft.TextField(label="Distância (KM)", value="220", bgcolor="#0B111E", color="#FFFFFF", width=150)
      c_rkm = ft.TextField(label="R$/km", value="6.80", bgcolor="#0B111E", color="#FFFFFF", width=150)
      c_ton = ft.TextField(label="Toneladas", value="32", bgcolor="#0B111E", color="#FFFFFF", width=150)
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
          ft.Container(bgcolor="#111927", padding=22, border_radius=24, content=ft.Column(spacing=14, controls=[ft.Text("🚛 Estudo Logístico de Fretes (KM)", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD), ft.Row(spacing=10, controls=[c_km, c_rkm, c_ton, ft.ElevatedButton("Calcular", bgcolor="#FACC15", color="#080D16", on_click=calc_f)]), res_f]))
      )

    else:
      s_pr = ft.TextField(label="Preço Grão (R$)", value="134.24", bgcolor="#0B111E", color="#FFFFFF", width=160)
      s_sem = ft.TextField(label="Preço Semente (R$)", value="291.00", bgcolor="#0B111E", color="#FFFFFF", width=160)
      res_b = ft.Text("Relação Barter: 2,17 sacas de grão por 1 semente certificada.", color="#10B981", size=16, weight=ft.FontWeight.BOLD)

      def calc_b(e):
        try:
          tr = float(s_sem.value) / float(s_pr.value)
          res_b.value = f"⚖️ Relação Barter: {tr:.2f} sacas de grão pagam 1 unidade de semente."
          page.update()
        except Exception:
          pass

      area_conteudo_direita.controls.append(
          ft.Container(bgcolor="#111927", padding=22, border_radius=24, content=ft.Column(spacing=14, controls=[ft.Text("⚖️ Simulador Barter", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD), ft.Row(spacing=10, controls=[s_pr, s_sem, ft.ElevatedButton("Simular", bgcolor="#10B981", color="#080D16", on_click=calc_b)]), res_b]))
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

    raiz_pagina.content = ft.Row(
        expand=True,
        spacing=14,
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Container(
                width=272,
                bgcolor="#111927",
                padding=14,
                border_radius=24,
                border=ft.border.all(1.5, "#1E293B"),
                content=coluna_lateral_menu,
            ),
            ft.Container(
                expand=True,
                content=area_conteudo_direita,
            ),
        ],
    )
    renderizar()

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
  )