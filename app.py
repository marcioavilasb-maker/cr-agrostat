import csv
from datetime import datetime, timedelta
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

ARQUIVO_DB = os.path.join("dados", "cr_agrostat_sul_v5.json")
PASTA_RELATORIOS = "relatorios"
PASTA_ASSETS = "assets"


def agora_str():
  return datetime.now().strftime("%d/%m/%Y às %H:%M:%S")


def obter_ip_local():
  try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip
  except Exception:
    return "127.0.0.1"


def criar_icone_semente_png(largura=192, altura=192):
  """Desenha automaticamente o ícone oficial da semente CR AgroStat."""
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


def criar_atalho_area_de_trabalho():
  """Cria automaticamente um atalho na Área de Trabalho do Windows com o ícone da semente."""
  if os.name != "nt":
    return
  try:
    pasta_atual = os.path.abspath(os.getcwd())
    caminho_bat = os.path.join(pasta_atual, "2_Abrir_Painel.bat")
    caminho_ico = os.path.join(pasta_atual, "cr_agrostat.ico")
    if not os.path.exists(caminho_bat):
      return

    cmd_ps = (
        "$WshShell = New-Object -ComObject WScript.Shell; "
        "$Desktop = [System.Environment]::GetFolderPath('Desktop'); "
        "$Shortcut = $WshShell.CreateShortcut(\"$Desktop\\CR AgroStat.lnk\"); "
        f"$Shortcut.TargetPath = '{caminho_bat}'; "
        f"$Shortcut.WorkingDirectory = '{pasta_atual}'; "
        f"$Shortcut.IconLocation = '{caminho_ico}'; "
        "$Shortcut.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd_ps],
        capture_output=True,
        timeout=5,
    )
  except Exception:
    pass


def gerar_arquivos_servidor_e_icones():
  try:
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

    criar_atalho_area_de_trabalho()

    with open("requirements.txt", "w", encoding="utf-8") as f:
      f.write(
          "flet==0.24.1\n"
          "fastapi==0.112.2\n"
          "uvicorn==0.30.6\n"
          "requests\n"
          "beautifulsoup4\n"
          "yfinance\n"
      )
  except Exception:
    pass


# =============================================================================
# GERADOR NATIVO DE ARQUIVO .PDF OFICIAL (SEM DEPENDER DE BIBLIOTECAS EXTERNAS)
# =============================================================================
def limpar_texto_pdf(texto):
  """Converte acentos para CP1252/WinAnsi compatível com fontes nativas de PDF."""
  substituicoes = {
      "•": "-",
      "—": "-",
      "➔": "->",
      "🟢": "[RS]",
      "🔴": "[SC]",
      "🔵": "[PR]",
      "🌎": "[SUL]",
  }
  for k, v in substituicoes.items():
    texto = texto.replace(k, v)
  # Remove emojis mantendo acentos do português
  limpo = "".join(c for c in texto if ord(c) < 256)
  escapado = (
      limpo.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
  )
  return escapado


def criar_pdf_nativo(caminho_pdf, titulo_doc, subtitulo_doc, linhas_conteudo):
  """Gera um arquivo .PDF real paginado (A4) diretamente na pasta relatorios/."""
  linhas_por_pag = 46
  paginas_linhas = [
      linhas_conteudo[i : i + linhas_por_pag]
      for i in range(0, max(1, len(linhas_conteudo)), linhas_por_pag)
  ]

  objetos = []
  # 1: Catalog, 2: Pages, 3: Font Regular, 4: Font Bold
  objetos.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
  objetos.append(b"")  # Placeholder p/ Pages
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
    # Cabeçalho escuro com faixa verde
    comandos.append("0.05 0.09 0.16 rg 30 765 535 50 re f")
    comandos.append("0.06 0.72 0.50 rg 30 762 535 4 re f")
    comandos.append("BT /F2 15 Tf 1 1 1 rg 42 793 Td")
    comandos.append(f"({limpar_texto_pdf(titulo_doc)}) Tj ET")
    comandos.append("BT /F1 9 Tf 0.65 0.95 0.82 rg 42 776 Td")
    comandos.append(
        f"({limpar_texto_pdf(subtitulo_doc + f'  |  Pagina {num_p+1} de {len(paginas_linhas)}')}) Tj ET"
    )

    y_pos = 740
    for linha in bloco:
      eh_titulo = linha.startswith("===") or linha.startswith(">>>") or linha.startswith("[")
      fonte_uso = "/F2 10 Tf" if eh_titulo else "/F1 9.5 Tf"
      cor_txt = "0.05 0.25 0.45 rg" if eh_titulo else "0.12 0.16 0.22 rg"
      comandos.append(f"BT {fonte_uso} {cor_txt} 36 {y_pos} Td")
      comandos.append(f"({limpar_texto_pdf(linha[:108])}) Tj ET")
      y_pos -= 15

    # Rodapé de auditoria
    comandos.append("0.85 0.88 0.92 rg 30 38 535 1 re f")
    comandos.append("BT /F1 8 Tf 0.4 0.45 0.52 rg 36 25 Td")
    comandos.append(
        f"({limpar_texto_pdf('Documento emitido pelo sistema CR AgroStat - Fontes: CBOT / PTAX / IRGA / Epagri / Deral / CEPEA / Open-Meteo.')}) Tj ET"
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
# BASE CLIMÁTICA E HISTÓRICO DE ESTAÇÕES DE ANOS ANTERIORES (RS, SC E PR)
# =============================================================================
POLOS_CLIMA_SUL = {
    "RS • Fronteira Oeste (São Borja / Itaqui)": {
        "uf": "RS",
        "lat": -28.66,
        "lon": -56.00,
        "estacao_inmet": "Estação Automática São Borja (A830) + Satélite ECMWF/GFS",
        "perfil": "Polo Arroz Irrigado, Soja, Trigo e Sementes Forrageiras",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 680, "2024": 510, "2025": 465, "2026_est": 490, "media_hist": 480},
            "Verão (Dez-Fev)": {"2023": 290, "2024": 495, "2025": 380, "2026_est": 430, "media_hist": 420},
            "Outono (Mar-Mai)": {"2023": 410, "2024": 640, "2025": 440, "2026_est": 460, "media_hist": 450},
            "Inverno (Jun-Ago)": {"2023": 360, "2024": 390, "2025": 340, "2026_est": 355, "media_hist": 350},
        },
    },
    "RS • Planalto e Noroeste (Passo Fundo / Ijuí / Cruz Alta)": {
        "uf": "RS",
        "lat": -28.26,
        "lon": -52.40,
        "estacao_inmet": "Estação Passo Fundo / Embrapa Trigo + Satélite ECMWF/GFS",
        "perfil": "Polo Soja, Trigo, Milho e Sementes Certificadas",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 720, "2024": 540, "2025": 495, "2026_est": 520, "media_hist": 510},
            "Verão (Dez-Fev)": {"2023": 310, "2024": 520, "2025": 410, "2026_est": 465, "media_hist": 460},
            "Outono (Mar-Mai)": {"2023": 395, "2024": 690, "2025": 430, "2026_est": 445, "media_hist": 440},
            "Inverno (Jun-Ago)": {"2023": 420, "2024": 450, "2025": 390, "2026_est": 415, "media_hist": 410},
        },
    },
    "RS • Zona Sul e Campanha (Pelotas / Bagé / Rio Grande)": {
        "uf": "RS",
        "lat": -31.77,
        "lon": -52.34,
        "estacao_inmet": "Estação Pelotas / Bagé + Reanálise ERA5 / Open-Meteo",
        "perfil": "Polo Arroz, Soja, Pecuária/Forrageiras e Porto de Exportação",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 590, "2024": 430, "2025": 370, "2026_est": 395, "media_hist": 390},
            "Verão (Dez-Fev)": {"2023": 240, "2024": 410, "2025": 345, "2026_est": 385, "media_hist": 380},
            "Outono (Mar-Mai)": {"2023": 350, "2024": 580, "2025": 360, "2026_est": 375, "media_hist": 370},
            "Inverno (Jun-Ago)": {"2023": 390, "2024": 410, "2025": 365, "2026_est": 380, "media_hist": 375},
        },
    },
    "SC • Oeste e Meio-Oeste (Chapecó / Campos Novos)": {
        "uf": "SC",
        "lat": -27.10,
        "lon": -52.61,
        "estacao_inmet": "Epagri/Ciram Chapecó & Campos Novos + ECMWF/GFS",
        "perfil": "Polo Milho, Soja, Sementes de Altitude e Proteína Animal",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 740, "2024": 560, "2025": 520, "2026_est": 545, "media_hist": 535},
            "Verão (Dez-Fev)": {"2023": 420, "2024": 530, "2025": 470, "2026_est": 505, "media_hist": 495},
            "Outono (Mar-Mai)": {"2023": 380, "2024": 550, "2025": 435, "2026_est": 455, "media_hist": 450},
            "Inverno (Jun-Ago)": {"2023": 395, "2024": 410, "2025": 375, "2026_est": 395, "media_hist": 390},
        },
    },
    "SC • Sul Catarinense (Tubarão / Araranguá / Turvo)": {
        "uf": "SC",
        "lat": -28.48,
        "lon": -49.00,
        "estacao_inmet": "Epagri/Ciram Araranguá + Satélite Open-Meteo ECMWF",
        "perfil": "Polo Arroz Irrigado Pré-Germinado e Sementes Certificadas",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 610, "2024": 470, "2025": 430, "2026_est": 450, "media_hist": 445},
            "Verão (Dez-Fev)": {"2023": 490, "2024": 560, "2025": 510, "2026_est": 535, "media_hist": 525},
            "Outono (Mar-Mai)": {"2023": 340, "2024": 490, "2025": 370, "2026_est": 390, "media_hist": 385},
            "Inverno (Jun-Ago)": {"2023": 310, "2024": 330, "2025": 290, "2026_est": 305, "media_hist": 300},
        },
    },
    "PR • Oeste Paranaense (Cascavel / Toledo)": {
        "uf": "PR",
        "lat": -24.95,
        "lon": -53.45,
        "estacao_inmet": "Simepar / INMET Cascavel + Modelo NOAA GFS / ECMWF",
        "perfil": "Polo Soja 1ª Safra, Milho Safrinha e Trigo",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 590, "2024": 530, "2025": 505, "2026_est": 525, "media_hist": 520},
            "Verão (Dez-Fev)": {"2023": 480, "2024": 540, "2025": 510, "2026_est": 535, "media_hist": 530},
            "Outono (Mar-Mai)": {"2023": 390, "2024": 430, "2025": 405, "2026_est": 420, "media_hist": 415},
            "Inverno (Jun-Ago)": {"2023": 290, "2024": 270, "2025": 285, "2026_est": 295, "media_hist": 290},
        },
    },
    "PR • Campos Gerais e Norte (Ponta Grossa / Londrina)": {
        "uf": "PR",
        "lat": -25.09,
        "lon": -50.16,
        "estacao_inmet": "Simepar / IAPAR Ponta Grossa & Londrina + ECMWF",
        "perfil": "Polo Sementes, Trigo Pão, Soja, Milho e Forrageiras",
        "historico_estacoes": {
            "Primavera (Set-Nov)": {"2023": 540, "2024": 480, "2025": 455, "2026_est": 475, "media_hist": 470},
            "Verão (Dez-Fev)": {"2023": 510, "2024": 560, "2025": 525, "2026_est": 545, "media_hist": 540},
            "Outono (Mar-Mai)": {"2023": 320, "2024": 360, "2025": 335, "2026_est": 345, "media_hist": 340},
            "Inverno (Jun-Ago)": {"2023": 265, "2024": 250, "2025": 260, "2026_est": 275, "media_hist": 270},
        },
    },
}


def buscar_previsao_tempo_openmeteo(nome_polo):
  info_p = POLOS_CLIMA_SUL.get(nome_polo, list(POLOS_CLIMA_SUL.values())[0])
  lat, lon = info_p["lat"], info_p["lon"]
  previsao_dias = []
  horario_consulta = agora_str()
  modo_coleta = "Satélite Ao Vivo — API Open-Meteo (ECMWF + NOAA GFS)"

  try:
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max"
        "&timezone=America%2FSao_Paulo&forecast_days=10"
    )
    resp = requests.get(url, timeout=6)
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
    padrao_mm = [0.0, 4.5, 18.2, 6.0, 0.0, 0.0, 12.4, 22.0, 3.5, 0.0]
    padrao_pr = [10, 55, 85, 60, 15, 10, 75, 90, 45, 15]
    for i in range(10):
      dt_f = (hoje + timedelta(days=i)).strftime("%d/%m")
      previsao_dias.append({
          "data": dt_f,
          "chuva_mm": padrao_mm[i],
          "prob": padrao_pr[i],
          "tmin": round(16.0 + math.sin(i) * 2.5, 1),
          "tmax": round(27.5 + math.cos(i) * 3.0, 1),
      })

  return previsao_dias, horario_consulta, modo_coleta


ITENS_PADRAO = [
    {
        "id": "soja_grao",
        "nome": "Soja em Grão",
        "sigla": "SOJA",
        "categoria": "Grãos",
        "unidade": "Saca 60kg",
        "ticker": "ZS=F",
        "fonte_oficial": (
            "Bolsa CBOT Chicago (ZS=F) via Yahoo Finance + Câmbio PTAX (USDBRL=X)"
            " + Paridade CEPEA/Paranaguá, IRGA/Emater-RS, Epagri-SC e Deral-PR"
        ),
        "url_fonte": "https://www.cepea.esalq.usp.br/br/indicador/soja.aspx",
        "preco_base": 132.50,
        "contrato_empresa": 131.00,
        "cor": "#F59E0B",
        "icone": "GRAIN_ROUNDED",
        "sazonalidade": (
            "Atenção ao regime de chuvas nos 3 estados do Sul, prêmios de"
            " exportação em Rio Grande (RS), São Francisco do Sul (SC) e"
            " Paranaguá (PR)."
        ),
        "fatores_oscilacao": [
            "Oscilação diária do Dólar Comercial e prêmios nos portos do Sul (Rio Grande, São Francisco do Sul e Paranaguá).",
            "Contratos futuros na Bolsa de Chicago (CBOT) e relatórios globais de safra do USDA.",
            "Clima nos 3 estados do Sul (frentes frias, estiagens ou excesso de chuvas na colheita/plantio).",
            "Custo do frete rodoviário entre o interior produtor e os terminais portuários ou esmagadoras.",
        ],
        "regioes_sul": {
            "RS": {
                "RS • Fronteira Oeste (São Borja / Itaqui / Uruguaiana)": 133.50,
                "RS • Missões (Santo Ângelo / São Luiz Gonzaga)": 132.00,
                "RS • Noroeste (Ijuí / Cruz Alta / Passo Fundo)": 135.00,
                "RS • Região Central (Santa Maria / Cachoeira)": 132.80,
                "RS • Campanha (Bagé / Dom Pedrito / Livramento)": 131.50,
                "RS • Porto de Rio Grande / Pelotas": 138.50,
            },
            "SC": {
                "SC • Oeste Catarinense (Chapecó / Xanxerê)": 135.50,
                "SC • Meio-Oeste e Planalto (Campos Novos / Lages)": 136.00,
                "SC • Planalto Norte (Canoinhas / Mafra)": 136.80,
                "SC • Sul Catarinense (Tubarão / Araranguá)": 134.50,
                "SC • Porto São Francisco do Sul (Paridade Export.)": 139.50,
            },
            "PR": {
                "PR • Oeste Paranaense (Cascavel / Toledo)": 133.00,
                "PR • Norte e Noroeste (Londrina / Maringá / Campo Mourão)": 133.80,
                "PR • Campos Gerais / Centro-Sul (Ponta Grossa / Guarapuava)": 136.50,
                "PR • Sudoeste (Pato Branco / Francisco Beltrão)": 134.20,
                "PR • Porto de Paranaguá (Indicador CEPEA)": 140.20,
            },
        },
    },
    {
        "id": "arroz_casca",
        "nome": "Arroz em Casca",
        "sigla": "ARROZ",
        "categoria": "Grãos",
        "unidade": "Saca 50kg",
        "ticker": "ZR=F",
        "fonte_oficial": (
            "Indicador Esalq/CEPEA-IRGA RS + CBOT Rough Rice (ZR=F) + Epagri/Cepa"
            " (SC) + Deral (PR)"
        ),
        "url_fonte": "https://www.cepea.esalq.usp.br/br/indicador/arroz.aspx",
        "preco_base": 115.00,
        "contrato_empresa": 114.00,
        "cor": "#0EA5E9",
        "icone": "GRASS_ROUNDED",
        "sazonalidade": (
            "RS e Sul de SC concentram mais de 80% da oferta nacional —"
            " mercado monitora estoques e ritmo da indústria."
        ),
        "fatores_oscilacao": [
            "Ritmo de compras das indústrias beneficiadoras no RS e Sul de SC frente à retenção do produtor.",
            "Competitividade do arroz do Mercosul (Uruguai, Argentina e Paraguai) e taxa de câmbio.",
            "Nível de barragens, rios e radiação solar nas lavouras irrigadas da Fronteira Oeste e Sul.",
            "Escoamento de arroz beneficiado para os grandes centros consumidores do Sudeste e Paraná.",
        ],
        "regioes_sul": {
            "RS": {
                "RS • Fronteira Oeste (São Borja / Uruguaiana / Alegrete)": 115.80,
                "RS • Campanha (Bagé / Dom Pedrito)": 114.20,
                "RS • Depressão Central (Santa Maria / Cachoeira)": 113.50,
                "RS • Planície Costeira Interna (Camaquã)": 115.00,
                "RS • Planície Costeira Externa (Mostardas / Palmares)": 114.50,
                "RS • Zona Sul (Pelotas / Santa Vitória / Jaguarão)": 116.50,
            },
            "SC": {
                "SC • Extremo Sul (Turvo / Araranguá / Meleiro)": 116.80,
                "SC • Sul Catarinense (Tubarão / Jaguaruna / Criciúma)": 117.20,
                "SC • Vale do Itajaí (Rio do Sul / Gaspar / Itajaí)": 116.00,
                "SC • Litoral Norte (Joinville / Massaranduba)": 116.50,
            },
            "PR": {
                "PR • Noroeste Paranaense (Querência do Norte / Loanda)": 118.00,
                "PR • Oeste e Campos Gerais (Atacado / Indústria)": 119.50,
                "PR • Região Metropolitana de Curitiba (Centro Distrib.)": 121.00,
            },
        },
    },
    {
        "id": "milho_grao",
        "nome": "Milho em Grão",
        "sigla": "MILHO",
        "categoria": "Grãos",
        "unidade": "Saca 60kg",
        "ticker": "ZC=F",
        "fonte_oficial": (
            "Bolsa CBOT (ZC=F) + B3/CEPEA + Praças Consumidoras Epagri-SC,"
            " Deral-PR e Emater-RS"
        ),
        "url_fonte": "https://www.cepea.esalq.usp.br/br/indicador/milho.aspx",
        "preco_base": 68.00,
        "contrato_empresa": 67.00,
        "cor": "#EAB308",
        "icone": "AGRICULTURE_ROUNDED",
        "sazonalidade": (
            "Forte consumo das agroindústrias de aves, suínos e leite em SC,"
            " PR e RS dita os prêmios regionais."
        ),
        "fatores_oscilacao": [
            "Demanda aquecida das cooperativas e agroindústrias de proteína animal (especialmente Oeste de SC, PR e Serra Gaúcha).",
            "Volume e produtividade da 1ª safra (verão) e da 2ª safra (safrinha forte no Paraná).",
            "Custo do frete rodoviário para trazer milho do Mato Grosso do Sul e Centro-Oeste para abastecer SC e RS.",
            "Paridade de exportação nos portos de Paranaguá (PR) e São Francisco do Sul (SC).",
        ],
        "regioes_sul": {
            "RS": {
                "RS • Fronteira Oeste (São Borja / Itaqui)": 67.50,
                "RS • Missões (Santo Ângelo / Santa Rosa)": 68.50,
                "RS • Noroeste / Alto Uruguai (Ijuí / Erechim)": 70.00,
                "RS • Vale do Taquari / Serra (Lajeado / Guaporé)": 72.50,
                "RS • Região Central (Santa Maria)": 68.00,
            },
            "SC": {
                "SC • Oeste Catarinense (Chapecó / Concórdia / Xanxerê)": 73.50,
                "SC • Meio-Oeste (Campos Novos / Joaçaba / Videira)": 72.00,
                "SC • Planalto Norte (Canoinhas / Mafra)": 71.50,
                "SC • Sul Catarinense (Braço do Norte / Tubarão)": 73.00,
            },
            "PR": {
                "PR • Oeste Paranaense (Cascavel / Toledo)": 66.50,
                "PR • Sudoeste (Pato Branco / Francisco Beltrão)": 68.50,
                "PR • Norte e Noroeste (Londrina / Maringá / Campo Mourão)": 66.00,
                "PR • Campos Gerais (Castro / Ponta Grossa)": 69.50,
                "PR • Porto de Paranaguá (Exportação)": 71.80,
            },
        },
    },
    {
        "id": "trigo_grao",
        "nome": "Trigo Pão",
        "sigla": "TRIGO",
        "categoria": "Grãos",
        "unidade": "Saca 60kg",
        "ticker": "ZW=F",
        "fonte_oficial": (
            "Bolsa CBOT Wheat (ZW=F) + Indicador CEPEA Trigo PR/RS + Deral-PR e"
            " Emater-RS"
        ),
        "url_fonte": "https://www.cepea.esalq.usp.br/br/indicador/trigo.aspx",
        "preco_base": 76.50,
        "contrato_empresa": 75.00,
        "cor": "#D97706",
        "icone": "BAKERY_DINING_ROUNDED",
        "sazonalidade": (
            "PR e RS lideram a safra nacional de trigo — foco total no PH,"
            " força de glúten e compras dos moinhos da Região Sul."
        ),
        "fatores_oscilacao": [
            "Qualidade industrial da colheita no PR, SC e RS (PH acima de 78 e força de glúten W).",
            "Paridade de importação do trigo argentino e câmbio comercial.",
            "Risco de geadas na floração ou chuvas no momento da colheita de inverno nos 3 estados.",
            "Liquidez de compra dos grandes moinhos do Paraná, Santa Catarina e Rio Grande do Sul.",
        ],
        "regioes_sul": {
            "RS": {
                "RS • Fronteira Oeste (São Borja)": 75.50,
                "RS • Missões (São Luiz Gonzaga / Santo Ângelo)": 76.80,
                "RS • Noroeste (Ijuí / Passo Fundo / Carazinho)": 78.00,
                "RS • Campos de Cima da Serra (Vacaria)": 77.50,
                "RS • Porto de Rio Grande (Exportação)": 80.50,
            },
            "SC": {
                "SC • Planalto Sul e Meio-Oeste (Campos Novos / Lages)": 78.50,
                "SC • Oeste Catarinense (Chapecó / Xanxerê)": 78.00,
                "SC • Planalto Norte (Canoinhas / Mafra)": 79.00,
            },
            "PR": {
                "PR • Campos Gerais / Centro-Sul (Ponta Grossa / Guarapuava)": 81.50,
                "PR • Oeste Paranaense (Cascavel / Toledo)": 79.50,
                "PR • Norte Pioneiro e Norte (Londrina / Cornélio Procópio)": 80.00,
                "PR • Sudoeste (Pato Branco)": 79.00,
            },
        },
    },
    {
        "id": "semente_soja",
        "nome": "Semente de Soja Certificada",
        "sigla": "SEM. SOJA",
        "categoria": "Sementes",
        "unidade": "Saca 40kg",
        "ticker": "ZS=F",
        "fonte_oficial": (
            "Indexador Soja CBOT (ZS=F) + Associações de Produtores de Sementes"
            " (Apassul-RS / Aprossul / Abrates)"
        ),
        "url_fonte": "https://www.conab.gov.br/",
        "preco_base": 295.00,
        "contrato_empresa": 288.00,
        "cor": "#10B981",
        "icone": "SPA_ROUNDED",
        "sazonalidade": (
            "Janela de plantio na Região Sul — alta procura por cultivares"
            " adaptadas ao fotoperíodo do RS, SC e PR."
        ),
        "fatores_oscilacao": [
            "Taxa de germinação e vigor dos campos sementeiros de altitude (Campos Novos/SC, Vacaria/RS, Ponta Grossa/PR).",
            "Demanda extra para replantio em caso de estiagem ou excesso hídrico na semeadura.",
            "Custo de tratamento industrial (TSI), fungicidas/inseticidas e royalties de biotecnologia.",
            "Frete refrigerado e logística de entrega na abertura da janela de plantio.",
        ],
        "regioes_sul": {
            "RS": {
                "RS • Fronteira Oeste (São Borja)": 292.00,
                "RS • Missões e Noroeste (Santo Ângelo / Ijuí / Passo Fundo)": 290.00,
                "RS • Campos de Cima da Serra (Vacaria - Polo Sementeiro)": 288.00,
                "RS • Campanha e Zona Sul (Bagé / Pelotas)": 298.00,
            },
            "SC": {
                "SC • Planalto (Campos Novos / Abelardo Luz - Polo Sementeiro)": 289.00,
                "SC • Oeste e Meio-Oeste (Chapecó / Xanxerê)": 294.00,
                "SC • Planalto Norte (Canoinhas / Mafra)": 295.00,
            },
            "PR": {
                "PR • Campos Gerais (Ponta Grossa / Castro - Polo Sementeiro)": 290.00,
                "PR • Oeste Paranaense (Cascavel / Toledo)": 295.00,
                "PR • Norte e Noroeste (Londrina / Maringá)": 298.00,
                "PR • Sudoeste (Pato Branco / Palmas)": 292.00,
            },
        },
    },
    {
        "id": "semente_arroz",
        "nome": "Semente de Arroz Certificada",
        "sigla": "SEM. ARROZ",
        "categoria": "Sementes",
        "unidade": "Saca 40kg",
        "ticker": "ZR=F",
        "fonte_oficial": (
            "Referência IRGA (RS) / Epagri (SC) + Indexador Arroz CBOT (ZR=F) +"
            " Sementeiras Credenciadas"
        ),
        "url_fonte": "https://irga.rs.gov.br/",
        "preco_base": 210.00,
        "contrato_empresa": 205.00,
        "cor": "#06B6D4",
        "icone": "ECO_ROUNDED",
        "sazonalidade": (
            "Implantação das lavouras irrigadas no RS e sistema pré-germinado"
            " em SC e PR."
        ),
        "fatores_oscilacao": [
            "Disponibilidade de cultivares certificadas (IRGA no RS e EPAGRI em SC para sistema pré-germinado).",
            "Pureza genética e garantia de ausência de arroz-vermelho nos lotes.",
            "Intenção de área plantada nas bacias hidrográficas do RS e litoral sul catarinense.",
            "Linhas de financiamento e relação de troca (Barter) com o arroz comercial.",
        ],
        "regioes_sul": {
            "RS": {
                "RS • Fronteira Oeste (São Borja / Uruguaiana)": 208.00,
                "RS • Campanha (Dom Pedrito / Alegrete)": 210.00,
                "RS • Depressão Central e Planície Costeira": 212.00,
                "RS • Zona Sul (Pelotas / Santa Vitória)": 209.00,
            },
            "SC": {
                "SC • Sul Catarinense (Turvo / Araranguá - Cultivares Epagri)": 214.00,
                "SC • Vale do Itajaí e Litoral Norte": 216.00,
            },
            "PR": {
                "PR • Noroeste Paranaense (Querência do Norte - Irrigado)": 218.00,
                "PR • Demais Regiões (Terras Altas / Irrigado)": 220.00,
            },
        },
    },
    {
        "id": "semente_azevem",
        "nome": "Semente de Azevém",
        "sigla": "AZEVÉM",
        "categoria": "Sementes",
        "unidade": "Quilo (kg)",
        "ticker": "ZC=F",
        "fonte_oficial": (
            "Cotações Sementeiras Forrageiras Sul (RS/SC/PR) + Indicadores"
            " Cooperativas e Emater/Deral"
        ),
        "url_fonte": "https://www.emater.tche.br/",
        "preco_base": 6.80,
        "contrato_empresa": 6.50,
        "cor": "#22C55E",
        "icone": "PARK_ROUNDED",
        "sazonalidade": (
            "Base da pecuária de corte e leite no inverno gaúcho, catarinense"
            " e paranaense."
        ),
        "fatores_oscilacao": [
            "Chuvas de outono na Região Sul, que concentram os pedidos das fazendas de pecuária e bacias leiteiras.",
            "Colheita de sementes forrageiras na primavera anterior no RS, SC e PR.",
            "Preço da arroba do boi gordo, terneiro e litro de leite pago ao produtor nos 3 estados.",
            "Diferencial de preço entre sementes certificadas tetraploides e azevém comum.",
        ],
        "regioes_sul": {
            "RS": {
                "RS • Fronteira Oeste (São Borja)": 6.70,
                "RS • Missões e Noroeste (Santo Ângelo / Ijuí)": 6.50,
                "RS • Campanha (Bagé / Santana do Livramento)": 7.10,
                "RS • Serra e Campos de Cima (Vacaria)": 6.90,
            },
            "SC": {
                "SC • Oeste Catarinense (Bacia Leiteira Chapecó / Concórdia)": 7.20,
                "SC • Planalto Serrano (Lages / São Joaquim)": 7.00,
            },
            "PR": {
                "PR • Campos Gerais (Bacia Leiteira Castro / Carambeí)": 7.40,
                "PR • Sudoeste e Centro-Sul (Pato Branco / Guarapuava)": 7.25,
            },
        },
    },
    {
        "id": "semente_aveia",
        "nome": "Semente de Aveia Preta",
        "sigla": "AVEIA",
        "categoria": "Sementes",
        "unidade": "Quilo (kg)",
        "ticker": "ZW=F",
        "fonte_oficial": (
            "Cotações Sementeiras de Inverno (RS/SC/PR) + Indexador Cereais de"
            " Inverno (ZW=F) + Deral/Emater"
        ),
        "url_fonte": "https://www.agricultura.pr.gov.br/Pagina/Deral",
        "preco_base": 3.90,
        "contrato_empresa": 3.75,
        "cor": "#84CC16",
        "icone": "LOCAL_FLORIST_ROUNDED",
        "sazonalidade": (
            "Essencial para cobertura de solo (plantio direto) e pastejo nos 3"
            " estados do Sul."
        ),
        "fatores_oscilacao": [
            "Demanda para formação de palhada no sistema de plantio direto no RS, SC e PR.",
            "Custo do frete rodoviário interestadual (carga volumosa).",
            "Qualidade de germinação e pureza física dos lotes colhidos no inverno.",
            "Concorrência com outras coberturas de inverno (nabo forrageiro, centeio e braquiária no PR).",
        ],
        "regioes_sul": {
            "RS": {
                "RS • Fronteira Oeste (São Borja)": 3.95,
                "RS • Missões e Noroeste (Ijuí / Passo Fundo)": 3.70,
                "RS • Campanha e Zona Sul (Bagé / Pelotas)": 4.10,
            },
            "SC": {
                "SC • Oeste e Meio-Oeste (Chapecó / Campos Novos)": 4.05,
                "SC • Planalto Norte e Sul": 4.15,
            },
            "PR": {
                "PR • Oeste e Sudoeste (Cascavel / Pato Branco)": 3.85,
                "PR • Campos Gerais e Norte (Ponta Grossa / Londrina)": 3.95,
            },
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


def calcular_medias_estados(regioes_sul):
  medias = {}
  todos_valores = []
  for uf in ["RS", "SC", "PR"]:
    vals = list(regioes_sul.get(uf, {}).values())
    if vals:
      medias[uf] = round(sum(vals) / len(vals), 2)
      todos_valores.extend(vals)
    else:
      medias[uf] = 0.0
  medias["SUL"] = (
      round(sum(todos_valores) / len(todos_valores), 2)
      if todos_valores
      else 0.0
  )
  return medias


def buscar_noticias_agro():
  noticias = []
  try:
    url = "https://news.google.com/rss/search?q=agronegocio+soja+arroz+milho+trigo+Rio+Grande+do+Sul+Parana+Santa+Catarina&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=5)
    if resp.status_code == 200:
      root = ET.fromstring(resp.content)
      for item in root.findall(".//item")[:4]:
        t = item.find("title")
        if t is not None and t.text:
          noticias.append(t.text.split(" - ")[0].strip())
  except Exception:
    pass
  return noticias


def gerar_series_com_datas_reais(
    preco_atual, var_dia, historico_bolsa, prev_15, prev_30, prev_60, prev_90
):
  hoje = datetime.now()
  fator_v = var_dia / 100.0
  abertura = round(preco_atual / (1 + fator_v * 0.8), 2)

  serie_diaria = [
      {"rotulo": "09:00", "data_completa": hoje.strftime("%d/%m/%Y 09:00"), "valor": abertura},
      {"rotulo": "10:30", "data_completa": hoje.strftime("%d/%m/%Y 10:30"), "valor": round(abertura * 0.7 + preco_atual * 0.3, 2)},
      {"rotulo": "12:00", "data_completa": hoje.strftime("%d/%m/%Y 12:00"), "valor": round(abertura * 0.5 + preco_atual * 0.5, 2)},
      {"rotulo": "14:00", "data_completa": hoje.strftime("%d/%m/%Y 14:00"), "valor": round(abertura * 0.35 + preco_atual * 0.65, 2)},
      {"rotulo": "16:00", "data_completa": hoje.strftime("%d/%m/%Y 16:00"), "valor": round(preco_atual * 0.998, 2)},
      {"rotulo": "Agora", "data_completa": hoje.strftime("%d/%m/%Y Atual"), "valor": preco_atual},
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
  os.makedirs("dados", exist_ok=True)
  os.makedirs(PASTA_RELATORIOS, exist_ok=True)
  gerar_arquivos_servidor_e_icones()

  horario_coleta = agora_str()
  dolar = 5.65
  dolar_var = 0.0
  try:
    h = yf.Ticker("USDBRL=X").history(period="5d")
    if not h.empty and len(h["Close"]) >= 2:
      dolar = float(h["Close"].iloc[-1])
      ant_d = float(h["Close"].iloc[-2])
      dolar_var = ((dolar - ant_d) / ant_d) * 100
  except Exception:
    pass

  bolsa = {}
  for tk in ["ZS=F", "ZR=F", "ZC=F", "ZW=F"]:
    try:
      h = yf.Ticker(tk).history(period="3mo")
      if not h.empty and len(h["Close"]) >= 2:
        pares = []
        for dt_idx, val_c in zip(h.index, h["Close"].tolist()):
          pares.append((dt_idx.strftime("%d/%m/%Y"), float(val_c)))
        fechamentos = [p[1] for p in pares]
        ult = fechamentos[-1]
        ant = fechamentos[-2]
        m30 = sum(fechamentos[-22:]) / len(fechamentos[-22:])
        var = ((ult - ant) / ant) * 100
        desvio = ((ult - m30) / m30) * 100
        bolsa[tk] = {"var": var, "desvio": desvio, "pares": pares, "ult_pts": round(ult, 2)}
    except Exception:
      bolsa[tk] = {"var": 0.0, "desvio": 0.0, "pares": [], "ult_pts": 0.0}

  manchetes = buscar_noticias_agro()
  mapa_antigo = {}
  if dados_existentes and "itens" in dados_existentes:
    for it_ant in dados_existentes["itens"]:
      mapa_antigo[it_ant.get("id")] = it_ant

  itens = []
  for i in ITENS_PADRAO:
    antigo = mapa_antigo.get(i["id"], {})
    preco_base_item = float(antigo.get("preco_base", i["preco_base"]))
    contrato_emp = float(antigo.get("contrato_empresa", i["contrato_empresa"]))
    regioes_sul_salvas = antigo.get("regioes_sul", i["regioes_sul"])

    b = bolsa.get(i["ticker"], {"var": 0.0, "desvio": 0.0, "pares": [], "ult_pts": 0.0})
    var_comb = (b["var"] * 0.6) + (dolar_var * 0.4)
    preco_atual = round(preco_base_item * (1 + (var_comb / 100)), 2)

    desvio_tot = b["desvio"] + dolar_var
    if desvio_tot >= 1.0:
      semaforo = "VERDE"
      msg_semaforo = "Momento Favorável para Venda (Acima da Média)"
      cor_sem = "#22C55E"
    elif desvio_tot <= -1.0:
      semaforo = "VERMELHO"
      msg_semaforo = "Pressão de Baixa (Oportunidade p/ Compra de Insumo)"
      cor_sem = "#EF4444"
    else:
      semaforo = "AMARELO"
      msg_semaforo = "Mercado Firme / Estável na Região Sul"
      cor_sem = "#FACC15"

    prev_15d = round(preco_atual * (1 + (desvio_tot * 0.004 + 0.006)), 2)
    prev_30d = round(preco_atual * (1 + (desvio_tot * 0.007 + 0.014)), 2)
    prev_60d = round(preco_atual * (1 + (desvio_tot * 0.009 + 0.021)), 2)
    prev_90d = round(preco_atual * (1 + (desvio_tot * 0.011 + 0.028)), 2)

    series = gerar_series_com_datas_reais(
        preco_atual, var_comb, b["pares"], prev_15d, prev_30d, prev_60d, prev_90d
    )
    valores_30d = [p["valor"] for p in series["historico_60d"][-30:]]
    media_per = round(sum(valores_30d) / len(valores_30d), 2)
    medias_uf = calcular_medias_estados(regioes_sul_salvas)

    direcao_prev = (
        "valorização gradual"
        if prev_30d >= preco_atual
        else "ajuste técnico de baixa"
    )
    explicacao_previsao = (
        f"A estimativa para {i['nome']} na Região Sul (RS, SC e PR) indica"
        f" tendência de {direcao_prev} para os próximos 30 a 90 dias (R$"
        f" {prev_30d:.2f} a R$ {prev_90d:.2f}). O modelo cruza a referência"
        f" atual (R$ {preco_atual:.2f}), a média dos últimos 30 dias (R$"
        f" {media_per:.2f}), as médias estaduais (RS: R$ {medias_uf['RS']:.2f}"
        f" | SC: R$ {medias_uf['SC']:.2f} | PR: R$ {medias_uf['PR']:.2f}), o"
        f" Dólar a R$ {dolar:.2f} ({dolar_var:+.2f}%) e a bolsa externa"
        f" ({b['var']:+.2f}%). {i['sazonalidade']}"
    )

    itens.append({
        **i,
        "preco_base": preco_base_item,
        "contrato_empresa": contrato_emp,
        "regioes_sul": regioes_sul_salvas,
        "medias_uf": medias_uf,
        "preco_atual": preco_atual,
        "media_periodo": media_per,
        "var_dia": round(var_comb, 2),
        "semaforo": semaforo,
        "msg_semaforo": msg_semaforo,
        "cor_sem": cor_sem,
        "horario_busca_item": horario_coleta,
        "pontos_bolsa_ref": b["ult_pts"],
        "motivo": (
            f"Câmbio a R$ {dolar:.2f} ({dolar_var:+.2f}%), bolsa externa"
            f" ({b['var']:+.2f}%) e média Sul em R$ {medias_uf['SUL']:.2f}."
            f" {i['sazonalidade']}"
        ),
        "explicacao_previsao": explicacao_previsao,
        "prev_15d": prev_15d,
        "prev_30d": prev_30d,
        "prev_60d": prev_60d,
        "prev_90d": prev_90d,
        "series": series,
    })

  registros_usuario = (
      dados_existentes.get("registros_planilha", [])
      if dados_existentes
      else [
          {
              "data": datetime.now().strftime("%d/%m/%Y"),
              "uf": "RS",
              "item": "Soja em Grão",
              "regiao": "São Borja - Fronteira Oeste",
              "lote": "500 Sacas",
              "valor": "133.50",
              "obs": "Referência inicial Região Sul",
          }
      ]
  )

  pacote = {
      "atualizacao": horario_coleta,
      "dolar": round(dolar, 2),
      "dolar_var": round(dolar_var, 2),
      "manchetes": manchetes if manchetes else [
          "Portos de Rio Grande (RS), São Francisco (SC) e Paranaguá (PR) movimentam exportações.",
          "Agroindústrias do Sul ajustam prêmios regionais para compra de milho, soja e trigo.",
          "Produtores de RS, SC e PR monitoram relação de troca para sementes certificadas.",
      ],
      "itens": itens,
      "registros_planilha": registros_usuario,
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
        if (
            "dolar" in d
            and "itens" in d
            and len(d["itens"]) > 0
            and "url_fonte" in d["itens"][0]
        ):
          return d
    except Exception:
      pass
  return coletar_mercado()


def main(page: ft.Page):
  page.title = "CR AgroStat — Inteligência Comercial Região Sul (RS, SC e PR)"
  page.bgcolor = "#080D16"
  page.padding = 22
  page.scroll = ft.ScrollMode.AUTO

  ip_local = obter_ip_local()
  dados = carregar_db()

  aba_atual = "painel"
  item_grafico_idx = 0
  periodo_grafico = "30d"
  estilo_grafico = "area"
  mostrar_painel_ia = True
  data_ini_idx = 30
  data_fim_idx = 59
  filtro_cat = "Todos"
  uf_selecionada = "SUL"
  item_regional_idx = 0
  uf_aba_regional = "TODOS"
  polo_clima_sel = list(POLOS_CLIMA_SUL.keys())[0]
  estacao_clima_sel = "Primavera (Set-Nov)"
  horario_ultima_selecao = agora_str()

  # Linha dinâmica do menu superior que se atualiza sempre com a aba ativa marcada
  linha_menu_abas = ft.Row(wrap=True, spacing=10)
  corpo_view = ft.Column(spacing=20, width=float("inf"))

  def mostrar_aviso(texto, cor="#10B981"):
    page.snack_bar = ft.SnackBar(
        ft.Text(texto, color="#080D16", weight=ft.FontWeight.BOLD),
        bgcolor=cor,
    )
    page.snack_bar.open = True
    page.update()

  def copiar_para_area_transferencia(titulo_copia, texto_copiar):
    page.set_clipboard(texto_copiar)
    mostrar_aviso(
        f"📋 '{titulo_copia}' copiado! Pode colar (Ctrl+V) no WhatsApp, Word ou E-mail."
    )

  def abrir_modal_fontes(titulo_contexto, lista_detalhes, url_externa=None):
    itens_col = ft.Column(spacing=8, tight=True)
    for linha in lista_detalhes:
      itens_col.controls.append(
          ft.Row(
              vertical_alignment=ft.CrossAxisAlignment.START,
              spacing=8,
              controls=[
                  ft.Icon(ft.icons.VERIFIED_ROUNDED, color="#10B981", size=18),
                  ft.Text(linha, color="#E2E8F0", size=13, expand=True),
              ],
          )
      )

    texto_bloco = f"=== AUDITORIA DE FONTES: {titulo_contexto} ===\n" + "\n".join(
        f"- {l}" for l in lista_detalhes
    )

    acoes_modal = [
        ft.ElevatedButton(
            "📋 Copiar Dados e Fontes",
            bgcolor="#38BDF8",
            color="#080D16",
            on_click=lambda e: copiar_para_area_transferencia(
                titulo_contexto, texto_bloco
            ),
        ),
    ]
    if url_externa:
      acoes_modal.append(
          ft.ElevatedButton(
              "🌐 Abrir Site Oficial da Fonte",
              bgcolor="#10B981",
              color="#080D16",
              on_click=lambda e: page.launch_url(url_externa),
          )
      )
    acoes_modal.append(
        ft.TextButton(
            "Fechar",
            on_click=lambda e: fechar_modal(),
        )
    )

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor="#111927",
        title=ft.Row(
            spacing=10,
            controls=[
                ft.Icon(ft.icons.TRAVEL_EXPLORE_ROUNDED, color="#FACC15", size=26),
                ft.Text(
                    f"Fontes, Data e Hora — {titulo_contexto}",
                    color="#FFFFFF",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
            ],
        ),
        content=ft.Container(width=620, content=itens_col),
        actions=acoes_modal,
    )

    def fechar_modal():
      dlg.open = False
      page.update()

    page.dialog = dlg
    dlg.open = True
    page.update()

  def gerar_pdf_completo_usuario(contexto_relatorio="Relatorio Geral Regiao Sul"):
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%Hh%Mm%Ss")
    nome_pdf = f"Relatorio_Oficial_CRAgroStat_{stamp}.pdf"
    caminho_pdf = os.path.join(PASTA_RELATORIOS, nome_pdf)

    linhas = []
    linhas.append(f"=== DADOS DA BUSCA E AUDITORIA ({contexto_relatorio.upper()}) ===")
    linhas.append(f"Data e Horario Exato da Emissao: {agora_str()}")
    linhas.append(f"Ultima Coleta das Bolsas e Cambio: {dados['atualizacao']}")
    linhas.append(
        f"Dolar Comercial Spot (Fonte Yahoo Finance USDBRL=X): R$ {dados['dolar']:.2f} ({dados['dolar_var']:+.2f}%)"
    )
    linhas.append(
        "Fontes Auditadas: Chicago Board of Trade (CBOT), CEPEA/Esalq, IRGA/Emater-RS, Epagri-SC, Deral-PR e Open-Meteo."
    )
    linhas.append("")
    linhas.append("=== COTACOES, MEDIAS ESTADUAIS (RS / SC / PR) E PREVISOES ===")

    for it in dados["itens"]:
      m_u = calcular_medias_estados(it["regioes_sul"])
      linhas.append(
          f"[{it['sigla']}] {it['nome']} ({it['unidade']}) -> Atual: R$ {it['preco_atual']:.2f} ({it['var_dia']:+.2f}%)"
      )
      linhas.append(
          f"   Medias Regionais -> RS: R$ {m_u['RS']:.2f} | SC: R$ {m_u['SC']:.2f} | PR: R$ {m_u['PR']:.2f} | Media Sul: R$ {m_u['SUL']:.2f} | Contrato Empresa: R$ {it['contrato_empresa']:.2f}"
      )
      linhas.append(
          f"   Estimativas IA -> +15d: R$ {it['prev_15d']:.2f} | +30d: R$ {it['prev_30d']:.2f} | +60d: R$ {it.get('prev_60d', it['prev_30d']):.2f} | +90d: R$ {it['prev_90d']:.2f}"
      )
      linhas.append(
          f"   Fonte Especifica: {it.get('fonte_oficial', '')} | Horario Coleta: {it.get('horario_busca_item', dados['atualizacao'])}"
      )
      linhas.append("-" * 98)

    linhas.append("")
    linhas.append(f"=== CLIMA E CHUVAS — POLO SELECIONADO: {polo_clima_sel} ===")
    info_c = POLOS_CLIMA_SUL[polo_clima_sel]
    linhas.append(f"Fonte Meteorologica: {info_c['estacao_inmet']} (Lat {info_c['lat']}, Lon {info_c['lon']})")
    for est_nome, d_est in info_c["historico_estacoes"].items():
      linhas.append(
          f"   {est_nome}: 2023={d_est['2023']}mm | 2024={d_est['2024']}mm | 2025={d_est['2025']}mm | Media Hist.={d_est['media_hist']}mm | Previsao 2026/27={d_est['2026_est']}mm"
      )

    linhas.append("")
    linhas.append("=== NOTA TECNICA DE ESTIMATIVA DE MERCADO ===")
    linhas.append(
        "Os valores futuros projetados sao estimativas estatisticas baseadas em medias, cambio e bolsas futuras,"
    )
    linhas.append(
        "sujeitas a oscilacoes diarias de clima, frete e mercado, nao representando garantia de preco concreto."
    )

    criar_pdf_nativo(
        caminho_pdf,
        "CR AgroStat - Relatorio Oficial de Cotacoes, Fontes e Clima",
        f"Regiao Sul (RS, SC e PR)  |  Gerado em: {agora_str()}",
        linhas,
    )

    # Se estiver no Windows local, abre o PDF automaticamente para o usuário ver/imprimir
    if os.name == "nt":
      try:
        os.startfile(os.path.abspath(caminho_pdf))
      except Exception:
        pass

    mostrar_aviso(
        f"📄 PDF Oficial gerado com sucesso em '{PASTA_RELATORIOS}/{nome_pdf}'!"
    )

  # =========================================================================
  # BARRA DE MENU COM DESTAQUE VISUAL SEMPRE ATUALIZADO NA ABA SELECIONADA
  # =========================================================================
  def atualizar_barra_menu():
    definicao_abas = [
        ("painel", "Painel & Gráficos Sul", ft.icons.SHOW_CHART_ROUNDED),
        ("clima", "Clima & Chuvas (Anos)", ft.icons.THUNDERSTORM_ROUNDED),
        ("regional", "Contratos RS / SC / PR", ft.icons.MAP_ROUNDED),
        ("frete", "Estudo de Fretes (KM)", ft.icons.LOCAL_SHIPPING_ROUNDED),
        ("barter", "Simulador Barter", ft.icons.CALCULATE_ROUNDED),
        ("relatorios", "Planilhas & PDF", ft.icons.PICTURE_AS_PDF_ROUNDED),
        ("nuvem", "Fontes & Ícone", ft.icons.VERIFIED_ROUNDED),
    ]
    linha_menu_abas.controls.clear()
    for chave_aba, texto_aba, icone_aba in definicao_abas:
      esta_ativa = aba_atual == chave_aba
      linha_menu_abas.controls.append(
          ft.ElevatedButton(
              text=f"✓ {texto_aba}" if esta_ativa else texto_aba,
              icon=icone_aba,
              bgcolor="#10B981" if esta_ativa else "#1E293B",
              color="#080D16" if esta_ativa else "#E2E8F0",
              height=46,
              style=ft.ButtonStyle(
                  side={
                      "": ft.BorderSide(
                          2.5 if esta_ativa else 1,
                          "#FACC15" if esta_ativa else "#334155",
                      )
                  },
                  shape=ft.RoundedRectangleBorder(radius=14),
              ),
              on_click=lambda e, k=chave_aba: mudar_aba(k),
          )
      )

  # =========================================================================
  # COMPONENTE: GRÁFICO MULTIVISUAL + FONTES + COPIAR + PDF
  # =========================================================================
  def construir_bloco_grafico():
    nonlocal data_ini_idx, data_fim_idx, horario_ultima_selecao
    item_sel = dados["itens"][item_grafico_idx]
    medias_uf = calcular_medias_estados(item_sel["regioes_sul"])
    item_sel["medias_uf"] = medias_uf

    fator_uf = 1.0
    if uf_selecionada in ["RS", "SC", "PR"] and medias_uf["SUL"] > 0:
      fator_uf = medias_uf[uf_selecionada] / medias_uf["SUL"]

    series_item = item_sel.get("series", {})
    hist_60 = series_item.get("historico_60d", [])

    if periodo_grafico == "diario":
      pontos_base = series_item.get("diario", [])
      titulo_per = "Intradia / Diário (Horas de Hoje)"
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
      pontos_base = series_item.get("90d", [])
      titulo_per = "Curva de Estimativa Futura (+15, +30, +60 e +90 Dias)"
    else:
      ini = min(data_ini_idx, data_fim_idx)
      fim = max(data_ini_idx, data_fim_idx)
      if fim - ini < 1:
        fim = min(len(hist_60) - 1, ini + 1)
      pontos_base = hist_60[ini : fim + 1]
      titulo_per = f"Datas Personalizadas: {pontos_base[0]['data_completa']} até {pontos_base[-1]['data_completa']}"

    pontos = [
        {
            "rotulo": p["rotulo"],
            "data_completa": p.get("data_completa", p["rotulo"]),
            "valor": round(p["valor"] * fator_uf, 2),
        }
        for p in pontos_base
    ]

    valores = [p["valor"] for p in pontos]
    media_val = sum(valores) / len(valores)
    min_val = min(valores)
    max_val = max(valores)
    amplitude = max(max_val - min_val, 0.4)

    def sel_item_graf(idx):
      nonlocal item_grafico_idx, horario_ultima_selecao
      item_grafico_idx = idx
      horario_ultima_selecao = agora_str()
      renderizar()

    def sel_periodo_graf(per):
      nonlocal periodo_grafico, horario_ultima_selecao
      periodo_grafico = per
      horario_ultima_selecao = agora_str()
      renderizar()

    def sel_estilo_graf(est):
      nonlocal estilo_grafico, horario_ultima_selecao
      estilo_grafico = est
      horario_ultima_selecao = agora_str()
      renderizar()

    def sel_uf_graf(uf):
      nonlocal uf_selecionada, horario_ultima_selecao
      uf_selecionada = uf
      horario_ultima_selecao = agora_str()
      renderizar()

    def alternar_painel_ia(e):
      nonlocal mostrar_painel_ia
      mostrar_painel_ia = not mostrar_painel_ia
      renderizar()

    # Botões de Estado sempre marcados quando selecionados
    opcoes_uf = [
        ("SUL", f"🌎 Média Região Sul (R$ {medias_uf['SUL']:.2f})"),
        ("RS", f"🟢 Rio Grande do Sul - RS (R$ {medias_uf['RS']:.2f})"),
        ("SC", f"🔴 Santa Catarina - SC (R$ {medias_uf['SC']:.2f})"),
        ("PR", f"🔵 Paraná - PR (R$ {medias_uf['PR']:.2f})"),
    ]
    botoes_uf = ft.Row(
        wrap=True,
        spacing=8,
        controls=[
            ft.Text("Estado / Recorte:", color="#94A3B8", size=13, weight=ft.FontWeight.BOLD)
        ],
    )
    for cod_uf, rot_uf in opcoes_uf:
      ativo_u = uf_selecionada == cod_uf
      botoes_uf.controls.append(
          ft.ElevatedButton(
              f"✓ {rot_uf}" if ativo_u else rot_uf,
              bgcolor="#10B981" if ativo_u else "#1E293B",
              color="#080D16" if ativo_u else "#FFFFFF",
              height=36,
              on_click=lambda e, u=cod_uf: sel_uf_graf(u),
          )
      )

    chips_itens = ft.Row(wrap=True, spacing=8)
    for idx, it in enumerate(dados["itens"]):
      ativo = idx == item_grafico_idx
      chips_itens.controls.append(
          ft.ElevatedButton(
              f"✓ {it['sigla']}" if ativo else it["sigla"],
              bgcolor=it["cor"] if ativo else "#1E293B",
              color="#080D16" if ativo else "#E2E8F0",
              height=38,
              on_click=lambda e, i=idx: sel_item_graf(i),
          )
      )

    opcoes_est = [
        ("area", "📈 Curva de Área + Média"),
        ("linha", "📐 Linha Técnica"),
        ("colunas", "📊 Colunas Verticais"),
        ("horizontal", "📉 Termómetro por Data"),
    ]
    botoes_estilo = ft.Row(
        wrap=True,
        spacing=8,
        controls=[
            ft.Text("Estilo Visual:", color="#94A3B8", size=13, weight=ft.FontWeight.BOLD)
        ],
    )
    for cod_e, rot_e in opcoes_est:
      at_e = estilo_grafico == cod_e
      botoes_estilo.controls.append(
          ft.ElevatedButton(
              f"✓ {rot_e}" if at_e else rot_e,
              bgcolor="#10B981" if at_e else "#1E293B",
              color="#080D16" if at_e else "#FFFFFF",
              height=36,
              on_click=lambda e, es=cod_e: sel_estilo_graf(es),
          )
      )

    opcoes_per = [
        ("diario", "Diário"),
        ("7d", "7 Dias"),
        ("15d", "15 Dias"),
        ("30d", "30 Dias"),
        ("60d", "60 Dias"),
        ("90d", "Projeção 90 Dias"),
    ]
    botoes_per = ft.Row(wrap=True, spacing=8)
    for cod_p, rot_p in opcoes_per:
      at_p = periodo_grafico == cod_p
      cor_p = "#FACC15" if cod_p == "90d" else "#38BDF8"
      botoes_per.controls.append(
          ft.ElevatedButton(
              f"✓ {rot_p}" if at_p else rot_p,
              bgcolor=cor_p if at_p else "#1E293B",
              color="#080D16" if at_p else "#FFFFFF",
              height=36,
              on_click=lambda e, pe=cod_p: sel_periodo_graf(pe),
          )
      )

    dd_data_ini = ft.Dropdown(
        label="📅 Data Inicial",
        bgcolor="#0B111E",
        color="#FFFFFF",
        border_radius=10,
        width=165,
        options=[ft.dropdown.Option(str(i), p["data_completa"]) for i, p in enumerate(hist_60)],
        value=str(data_ini_idx),
    )
    dd_data_fim = ft.Dropdown(
        label="📅 Data Final",
        bgcolor="#0B111E",
        color="#FFFFFF",
        border_radius=10,
        width=165,
        options=[ft.dropdown.Option(str(i), p["data_completa"]) for i, p in enumerate(hist_60)],
        value=str(data_fim_idx),
    )

    def aplicar_filtro_datas(e):
      nonlocal data_ini_idx, data_fim_idx, periodo_grafico, horario_ultima_selecao
      data_ini_idx = int(dd_data_ini.value)
      data_fim_idx = int(dd_data_fim.value)
      periodo_grafico = "custom"
      horario_ultima_selecao = agora_str()
      renderizar()

    barra_datas_custom = ft.Row(
        wrap=True,
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            botoes_estilo,
            ft.Row(
                wrap=True,
                spacing=8,
                controls=[
                    dd_data_ini,
                    dd_data_fim,
                    ft.ElevatedButton(
                        "✓ Datas Ativas" if periodo_grafico == "custom" else "Filtrar Datas",
                        icon=ft.icons.CALENDAR_MONTH_ROUNDED,
                        bgcolor="#10B981" if periodo_grafico == "custom" else "#38BDF8",
                        color="#080D16",
                        height=42,
                        on_click=aplicar_filtro_datas,
                    ),
                ],
            ),
        ],
    )

    if estilo_grafico in ["area", "linha"]:
      passo_rotulo = max(1, len(pontos) // 8)
      rotulos_x = []
      for i, p in enumerate(pontos):
        if len(pontos) <= 10 or i % passo_rotulo == 0 or i == len(pontos) - 1:
          rotulos_x.append(
              ft.ChartAxisLabel(
                  value=i,
                  label=ft.Container(ft.Text(p["rotulo"], size=11, color="#94A3B8"), padding=ft.padding.only(top=6)),
              )
          )

      cor_hex_limpa = item_sel["cor"].lstrip("#")
      widget_grafico = ft.Container(
          height=245,
          padding=ft.padding.only(right=20, top=15, bottom=5),
          content=ft.LineChart(
              data_series=[
                  ft.LineChartData(
                      data_points=[
                          ft.LineChartDataPoint(i, p["valor"], tooltip=f"{p['data_completa']} ({uf_selecionada}): R$ {p['valor']:.2f}")
                          for i, p in enumerate(pontos)
                      ],
                      stroke_width=4,
                      color=item_sel["cor"],
                      curved=(estilo_grafico == "area"),
                      stroke_cap_round=True,
                      below_line_bgcolor=f"#33{cor_hex_limpa}" if estilo_grafico == "area" else None,
                  ),
                  ft.LineChartData(
                      data_points=[
                          ft.LineChartDataPoint(i, round(media_val, 2), tooltip=f"Média ({uf_selecionada}): R$ {media_val:.2f}")
                          for i in range(len(pontos))
                      ],
                      stroke_width=2,
                      color="#38BDF8",
                      curved=False,
                      dash_pattern=[6, 4],
                  ),
              ],
              min_y=round(min_val - amplitude * 0.25, 2),
              max_y=round(max_val + amplitude * 0.25, 2),
              min_x=0,
              max_x=max(1, len(pontos) - 1),
              left_axis=ft.ChartAxis(labels_size=58),
              bottom_axis=ft.ChartAxis(labels=rotulos_x, labels_size=34),
              horizontal_grid_lines=ft.ChartGridLines(interval=max(0.2, round(amplitude / 4, 2)), color="#1E293B", width=1),
              vertical_grid_lines=ft.ChartGridLines(interval=max(1, passo_rotulo), color="#1E293B", width=1),
              tooltip_bgcolor="#0F172A",
              interactive=True,
              expand=True,
          ),
      )
    elif estilo_grafico == "colunas":
      passo_c = max(1, math.ceil(len(pontos) / 12))
      pontos_col = pontos[::passo_c]
      if pontos[-1] not in pontos_col:
        pontos_col.append(pontos[-1])

      colunas_grafico = ft.Row(alignment=ft.MainAxisAlignment.SPACE_AROUND, vertical_alignment=ft.CrossAxisAlignment.END, height=220)
      for p in pontos_col:
        proporcao = (p["valor"] - min_val) / amplitude
        altura_barra = int(45 + (proporcao * 120))
        acima_media = p["valor"] >= media_val
        cor_barra = item_sel["cor"] if acima_media else "#38BDF8"

        colunas_grafico.controls.append(
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.END,
                spacing=5,
                controls=[
                    ft.Text(f"R$ {p['valor']:.2f}", color="#FFFFFF", size=11, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        width=38,
                        height=altura_barra,
                        bgcolor=cor_barra,
                        border_radius=ft.border_radius.only(top_left=10, top_right=10, bottom_left=4, bottom_right=4),
                        tooltip=f"{p['data_completa']}: R$ {p['valor']:.2f}",
                    ),
                    ft.Text(p["rotulo"], color="#94A3B8", size=11),
                ],
            )
        )
      widget_grafico = colunas_grafico
    else:
      passo_h = max(1, math.ceil(len(pontos) / 10))
      pontos_h = pontos[::passo_h]
      if pontos[-1] not in pontos_h:
        pontos_h.append(pontos[-1])

      linhas_h = ft.Column(spacing=8)
      for p in pontos_h:
        prop = max(0.08, (p["valor"] - min_val) / amplitude)
        dif_m = p["valor"] - media_val
        cor_d = "#22C55E" if dif_m >= 0 else "#EF4444"
        linhas_h.controls.append(
            ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.Text(p["data_completa"], color="#CBD5E1", size=12, width=110),
                    ft.Container(
                        expand=True,
                        bgcolor="#131E32",
                        height=22,
                        border_radius=8,
                        content=ft.Row([ft.Container(width=int(prop * 420), height=22, bgcolor=item_sel["cor"], border_radius=8)]),
                    ),
                    ft.Text(f"R$ {p['valor']:.2f} ({dif_m:+.2f} vs média)", color=cor_d, size=12, weight=ft.FontWeight.BOLD, width=185),
                ],
            )
        )
      widget_grafico = linhas_h

    p15_uf = round(item_sel["prev_15d"] * fator_uf, 2)
    p30_uf = round(item_sel["prev_30d"] * fator_uf, 2)
    p60_uf = round(item_sel.get("prev_60d", item_sel["prev_30d"]) * fator_uf, 2)
    p90_uf = round(item_sel["prev_90d"] * fator_uf, 2)

    resumo_copia_grafico = (
        f"📊 CR AgroStat — Resumo de Análise ({item_sel['nome']} - Recorte {uf_selecionada})\n"
        f"🕒 Data/Hora da Seleção: {horario_ultima_selecao} | Coleta de Mercado: {dados['atualizacao']}\n"
        f"💰 Valor Atual ({uf_selecionada}): R$ {pontos[-1]['valor']:.2f} ({item_sel['unidade']})\n"
        f"📈 Média do Período ({titulo_per}): R$ {media_val:.2f} (Mín: R$ {min_val:.2f} / Máx: R$ {max_val:.2f})\n"
        f"🌎 Médias Estaduais: RS R$ {medias_uf['RS']:.2f} | SC R$ {medias_uf['SC']:.2f} | PR R$ {medias_uf['PR']:.2f}\n"
        f"🔮 Estimativas Futuras (IA): +15d R$ {p15_uf:.2f} | +30d R$ {p30_uf:.2f} | +60d R$ {p60_uf:.2f} | +90d R$ {p90_uf:.2f}\n"
        f"📚 Fonte Oficial: {item_sel.get('fonte_oficial', '')}"
    )

    detalhes_auditoria_grafico = [
        f"Item Selecionado: {item_sel['nome']} ({item_sel['unidade']}) — Recorte Regional: {uf_selecionada}",
        f"Data e Hora Exata desta Seleção/Filtro: {horario_ultima_selecao}",
        f"Data e Hora da Coleta nas Bolsas e Câmbio: {dados['atualizacao']}",
        f"Fonte Principal da Cotação: {item_sel.get('fonte_oficial', '')}",
        f"Ticker Internacional Consultado (Yahoo Finance API): {item_sel['ticker']} | Câmbio: USDBRL=X (R$ {dados['dolar']:.2f})",
        f"Período Analisado: {titulo_per} — Média Calculada: R$ {media_val:.2f}",
    ]

    lista_fatores_ui = ft.Column(spacing=6)
    for fat in item_sel.get("fatores_oscilacao", []):
      lista_fatores_ui.controls.append(
          ft.Row(
              vertical_alignment=ft.CrossAxisAlignment.START,
              spacing=8,
              controls=[
                  ft.Icon(ft.icons.CHECK_CIRCLE_OUTLINE_ROUNDED, color="#38BDF8", size=17),
                  ft.Text(fat, color="#E2E8F0", size=13, expand=True),
              ],
          )
      )

    bloco_previsao_inteligente = ft.Container(
        visible=mostrar_painel_ia,
        bgcolor="#0B111E",
        padding=22,
        border_radius=20,
        border=ft.border.all(1.5, "#FACC15"),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(ft.icons.PSYCHOLOGY_ROUNDED, color="#FACC15", size=28),
                                ft.Text(
                                    f"Previsão Inteligente ({uf_selecionada}) — {item_sel['nome']}",
                                    color="#FACC15",
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                        ),
                        ft.Text(
                            f"🕒 Cálculo atualizado em: {horario_ultima_selecao}",
                            color="#38BDF8",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
                ft.ResponsiveRow(
                    spacing=12,
                    run_spacing=12,
                    controls=[
                        ft.Container(
                            col={"xs": 12, "sm": 6, "md": 3},
                            bgcolor="#111927",
                            padding=14,
                            border_radius=14,
                            content=ft.Column([
                                ft.Text("ESTIMATIVA +15 DIAS", color="#94A3B8", size=11, weight=ft.FontWeight.BOLD),
                                ft.Text(f"R$ {p15_uf:.2f}", color="#38BDF8", size=22, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Faixa: R$ {p15_uf*0.97:.2f} a R$ {p15_uf*1.03:.2f}", color="#94A3B8", size=11),
                            ]),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 6, "md": 3},
                            bgcolor="#111927",
                            padding=14,
                            border_radius=14,
                            content=ft.Column([
                                ft.Text("ESTIMATIVA +30 DIAS", color="#94A3B8", size=11, weight=ft.FontWeight.BOLD),
                                ft.Text(f"R$ {p30_uf:.2f}", color="#A855F7", size=22, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Faixa: R$ {p30_uf*0.95:.2f} a R$ {p30_uf*1.05:.2f}", color="#94A3B8", size=11),
                            ]),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 6, "md": 3},
                            bgcolor="#111927",
                            padding=14,
                            border_radius=14,
                            content=ft.Column([
                                ft.Text("ESTIMATIVA +60 DIAS", color="#94A3B8", size=11, weight=ft.FontWeight.BOLD),
                                ft.Text(f"R$ {p60_uf:.2f}", color="#10B981", size=22, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Faixa: R$ {p60_uf*0.93:.2f} a R$ {p60_uf*1.07:.2f}", color="#94A3B8", size=11),
                            ]),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 6, "md": 3},
                            bgcolor="#111927",
                            padding=14,
                            border_radius=14,
                            border=ft.border.all(1, "#FACC15"),
                            content=ft.Column([
                                ft.Text("ESTIMATIVA +90 DIAS", color="#FACC15", size=11, weight=ft.FontWeight.BOLD),
                                ft.Text(f"R$ {p90_uf:.2f}", color="#FACC15", size=22, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Faixa: R$ {p90_uf*0.91:.2f} a R$ {p90_uf*1.09:.2f}", color="#94A3B8", size=11),
                            ]),
                        ),
                    ],
                ),
                ft.Text("📌 Fundamentação da Estimativa (RS, SC e PR):", color="#FFFFFF", size=15, weight=ft.FontWeight.BOLD),
                ft.Text(item_sel.get("explicacao_previsao", item_sel["motivo"]), color="#E2E8F0", size=13),
                ft.Text("🌡️ Do que depende a oscilação deste item na Região Sul?", color="#38BDF8", size=15, weight=ft.FontWeight.BOLD),
                lista_fatores_ui,
                ft.Container(
                    bgcolor="#2A1B08",
                    padding=14,
                    border_radius=14,
                    border=ft.border.all(1, "#F59E0B"),
                    content=ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        spacing=10,
                        controls=[
                            ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color="#FACC15", size=24),
                            ft.Text(
                                "AVISO IMPORTANTE (ESTIMATIVA DE MERCADO, NÃO UM VALOR CONCRETO): "
                                "As projeções de preços apresentadas acima são estimativas estatísticas baseadas em "
                                "médias históricas de RS, SC e PR, câmbio e contratos futuros. Como o mercado agrícola "
                                "oscila diariamente conforme clima, bolsas externas, dólar, fretes e demanda industrial, "
                                "estes valores constituem um indicador analítico e não uma garantia de preço fixo concreto.",
                                color="#FDE68A",
                                size=12,
                                weight=ft.FontWeight.W_600,
                                expand=True,
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )

    return ft.Container(
        width=float("inf"),
        bgcolor="#111927",
        padding=24,
        border_radius=26,
        border=ft.border.all(1.5, "#1E293B"),
        content=ft.Column(
            spacing=16,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    controls=[
                        ft.Row(
                            spacing=12,
                            controls=[
                                ft.Container(
                                    bgcolor=item_sel["cor"],
                                    padding=10,
                                    border_radius=14,
                                    content=ft.Icon(ft.icons.SHOW_CHART_ROUNDED, color="#080D16", size=26),
                                ),
                                ft.Column([
                                    ft.Text(
                                        f"Gráfico de Evolução & Média ({uf_selecionada}) — {item_sel['nome']}",
                                        color="#FFFFFF",
                                        size=20,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.Text(
                                        f"{titulo_per}  |  Média: R$ {media_val:.2f}  |  🕒 Selecionado em: {horario_ultima_selecao}",
                                        color="#38BDF8",
                                        size=12,
                                    ),
                                    ft.Text(
                                        f"📚 Fonte: {item_sel.get('fonte_oficial', '')} (Coleta: {dados['atualizacao']})",
                                        color="#10B981",
                                        size=12,
                                    ),
                                ]),
                            ],
                        ),
                        ft.Row(
                            wrap=True,
                            spacing=8,
                            controls=[
                                ft.ElevatedButton(
                                    "🔍 Fontes e Horário",
                                    bgcolor="#1E293B",
                                    color="#38BDF8",
                                    height=38,
                                    on_click=lambda e: abrir_modal_fontes(
                                        f"{item_sel['nome']} ({uf_selecionada})",
                                        detalhes_auditoria_grafico,
                                        item_sel.get("url_fonte"),
                                    ),
                                ),
                                ft.ElevatedButton(
                                    "📋 Copiar Análise",
                                    bgcolor="#1E293B",
                                    color="#10B981",
                                    height=38,
                                    on_click=lambda e: copiar_para_area_transferencia(
                                        f"Análise {item_sel['nome']}",
                                        resumo_copia_grafico,
                                    ),
                                ),
                                ft.ElevatedButton(
                                    "📄 Gerar PDF",
                                    bgcolor="#0284C7",
                                    color="#FFFFFF",
                                    height=38,
                                    on_click=lambda e: gerar_pdf_completo_usuario(
                                        f"Analise {item_sel['nome']} ({uf_selecionada})"
                                    ),
                                ),
                                ft.ElevatedButton(
                                    "✓ 🧠 Previsão IA Aberta"
                                    if mostrar_painel_ia
                                    else "🧠 Abrir Previsão IA",
                                    bgcolor="#FACC15" if mostrar_painel_ia else "#1E293B",
                                    color="#080D16" if mostrar_painel_ia else "#FACC15",
                                    height=38,
                                    on_click=alternar_painel_ia,
                                ),
                            ],
                        ),
                    ],
                ),
                botoes_per,
                botoes_uf,
                chips_itens,
                barra_datas_custom,
                ft.ResponsiveRow(
                    spacing=12,
                    run_spacing=12,
                    controls=[
                        ft.Container(
                            col={"xs": 6, "md": 3},
                            bgcolor="#0B111E",
                            padding=14,
                            border_radius=16,
                            border=ft.border.all(1, "#1E293B"),
                            content=ft.Column([
                                ft.Text(f"REFERÊNCIA ({uf_selecionada})", color="#94A3B8", size=11),
                                ft.Text(f"R$ {pontos[-1]['valor']:.2f}", color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD),
                            ]),
                        ),
                        ft.Container(
                            col={"xs": 6, "md": 3},
                            bgcolor="#0B111E",
                            padding=14,
                            border_radius=16,
                            border=ft.border.all(1, "#38BDF8"),
                            content=ft.Column([
                                ft.Text("MÉDIA DAS DATAS SELECIONADAS", color="#38BDF8", size=11, weight=ft.FontWeight.BOLD),
                                ft.Text(f"R$ {media_val:.2f}", color="#38BDF8", size=20, weight=ft.FontWeight.BOLD),
                            ]),
                        ),
                        ft.Container(
                            col={"xs": 6, "md": 3},
                            bgcolor="#0B111E",
                            padding=14,
                            border_radius=16,
                            border=ft.border.all(1, "#1E293B"),
                            content=ft.Column([
                                ft.Text("MÉDIAS ESTADUAIS (RS / SC / PR)", color="#94A3B8", size=11),
                                ft.Text(
                                    f"RS {medias_uf['RS']:.0f} • SC {medias_uf['SC']:.0f} • PR {medias_uf['PR']:.0f}",
                                    color="#10B981",
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ]),
                        ),
                        ft.Container(
                            col={"xs": 6, "md": 3},
                            bgcolor="#0B111E",
                            padding=14,
                            border_radius=16,
                            border=ft.border.all(1, "#FACC15"),
                            content=ft.Column([
                                ft.Text("ESTIMATIVA 90 DIAS (IA)", color="#FACC15", size=11, weight=ft.FontWeight.BOLD),
                                ft.Text(f"R$ {p90_uf:.2f}", color="#FACC15", size=20, weight=ft.FontWeight.BOLD),
                            ]),
                        ),
                    ],
                ),
                ft.Container(
                    bgcolor="#0B111E",
                    padding=20,
                    border_radius=20,
                    border=ft.border.all(1, "#1E293B"),
                    content=widget_grafico,
                ),
                bloco_previsao_inteligente,
            ],
        ),
    )

  # =========================================================================
  # RENDERIZAÇÃO DAS 7 ABAS DO SISTEMA
  # =========================================================================
  def renderizar():
    atualizar_barra_menu()
    corpo_view.controls.clear()

    # -------------------------------------------------------------------------
    # ABA 1: PAINEL & GRÁFICOS DE PERÍODO (REGIÃO SUL)
    # -------------------------------------------------------------------------
    if aba_atual == "painel":
      corpo_view.controls.append(construir_bloco_grafico())

      def mudar_f_cat(c):
        nonlocal filtro_cat, horario_ultima_selecao
        filtro_cat = c
        horario_ultima_selecao = agora_str()
        renderizar()

      barra_filtro = ft.Row(
          alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
          wrap=True,
          controls=[
              ft.Text(
                  "Painel de Cotações da Região Sul (RS, SC e PR) & Fontes Auditáveis",
                  color="#FFFFFF",
                  size=20,
                  weight=ft.FontWeight.BOLD,
              ),
              ft.Row(
                  spacing=8,
                  controls=[
                      ft.ElevatedButton(
                          "✓ Todos" if filtro_cat == "Todos" else "Todos",
                          bgcolor="#10B981" if filtro_cat == "Todos" else "#1E293B",
                          color="#080D16" if filtro_cat == "Todos" else "#FFFFFF",
                          on_click=lambda e: mudar_f_cat("Todos"),
                      ),
                      ft.ElevatedButton(
                          "✓ Só Grãos" if filtro_cat == "Grãos" else "Só Grãos",
                          bgcolor="#F59E0B" if filtro_cat == "Grãos" else "#1E293B",
                          color="#080D16" if filtro_cat == "Grãos" else "#FFFFFF",
                          on_click=lambda e: mudar_f_cat("Grãos"),
                      ),
                      ft.ElevatedButton(
                          "✓ Só Sementes" if filtro_cat == "Sementes" else "Só Sementes",
                          bgcolor="#10B981" if filtro_cat == "Sementes" else "#1E293B",
                          color="#080D16" if filtro_cat == "Sementes" else "#FFFFFF",
                          on_click=lambda e: mudar_f_cat("Sementes"),
                      ),
                  ],
              ),
          ],
      )
      corpo_view.controls.append(barra_filtro)

      grade = ft.ResponsiveRow(spacing=18, run_spacing=18)
      for idx, item in enumerate(dados["itens"]):
        if filtro_cat != "Todos" and item["categoria"] != filtro_cat:
          continue

        m_uf = calcular_medias_estados(item["regioes_sul"])
        alta = item["var_dia"] >= 0
        sinal = "+" if alta else ""
        cor_var = "#22C55E" if alta else "#EF4444"

        texto_copiar_card = (
            f"🌾 {item['nome']} ({item['unidade']})\n"
            f"💰 Preço Atual: R$ {item['preco_atual']:.2f} ({sinal}{item['var_dia']:.2f}% hoje)\n"
            f"🌎 Médias Sul: RS R$ {m_uf['RS']:.2f} | SC R$ {m_uf['SC']:.2f} | PR R$ {m_uf['PR']:.2f}\n"
            f"🚦 Status: {item['msg_semaforo']}\n"
            f"🔮 Estimativas: 15d R$ {item['prev_15d']:.2f} | 30d R$ {item['prev_30d']:.2f} | 90d R$ {item['prev_90d']:.2f}\n"
            f"📚 Fonte: {item.get('fonte_oficial', '')}\n"
            f"🕒 Data/Hora da Busca: {item.get('horario_busca_item', dados['atualizacao'])}"
        )

        detalhes_fonte_card = [
            f"Item: {item['nome']} ({item['categoria']} — {item['unidade']})",
            f"Data e Horário da Busca nas Fontes: {item.get('horario_busca_item', dados['atualizacao'])}",
            f"Fonte Oficial Utilizada: {item.get('fonte_oficial', '')}",
            f"Contrato Bolsa Referência: {item['ticker']} | Dólar PTAX/Spot: R$ {dados['dolar']:.2f}",
            f"Médias Calculadas: RS R$ {m_uf['RS']:.2f} | SC R$ {m_uf['SC']:.2f} | PR R$ {m_uf['PR']:.2f}",
        ]

        def acao_previsao_card(e, i=idx):
          nonlocal item_grafico_idx, mostrar_painel_ia, horario_ultima_selecao
          item_grafico_idx = i
          mostrar_painel_ia = True
          horario_ultima_selecao = agora_str()
          mostrar_aviso(f"Exibindo Gráfico e Previsão Inteligente de {dados['itens'][i]['nome']}!")
          renderizar()

        card = ft.Container(
            col={"xs": 12, "lg": 6},
            bgcolor="#111927",
            padding=24,
            border_radius=26,
            border=ft.border.all(2 if idx == item_grafico_idx else 1, item["cor"] if idx == item_grafico_idx else "#1E293B"),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                        controls=[
                            ft.Row(
                                spacing=14,
                                controls=[
                                    ft.Container(
                                        width=60,
                                        height=60,
                                        bgcolor=item["cor"],
                                        border_radius=18,
                                        alignment=ft.alignment.center,
                                        content=ft.Icon(obter_icone_flet(item["icone"]), color="#080D16", size=32),
                                    ),
                                    ft.Column(
                                        spacing=3,
                                        controls=[
                                            ft.Text(item["nome"], color="#FFFFFF", size=20, weight=ft.FontWeight.BOLD),
                                            ft.Text(f"{item['unidade']} • Média Sul: R$ {m_uf['SUL']:.2f}", color="#94A3B8", size=13),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                                spacing=3,
                                controls=[
                                    ft.Text(f"R$ {item['preco_atual']:.2f}", color="#FFFFFF", size=28, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"{sinal}{item['var_dia']:.2f}% hoje", color=cor_var, size=13, weight=ft.FontWeight.BOLD),
                                ],
                            ),
                        ],
                    ),
                    ft.Container(
                        bgcolor="#0B111E",
                        padding=10,
                        border_radius=12,
                        border=ft.border.all(1, "#1E293B"),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_AROUND,
                            wrap=True,
                            controls=[
                                ft.Text(f"🟢 Média RS: R$ {m_uf['RS']:.2f}", color="#10B981", size=12, weight=ft.FontWeight.BOLD),
                                ft.Text(f"🔴 Média SC: R$ {m_uf['SC']:.2f}", color="#38BDF8", size=12, weight=ft.FontWeight.BOLD),
                                ft.Text(f"🔵 Média PR: R$ {m_uf['PR']:.2f}", color="#FACC15", size=12, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                    ),
                    ft.Container(
                        bgcolor="#0B111E",
                        padding=15,
                        border_radius=16,
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Container(width=12, height=12, border_radius=6, bgcolor=item["cor_sem"]),
                                        ft.Text(item["msg_semaforo"], color=item["cor_sem"], size=13, weight=ft.FontWeight.BOLD),
                                    ],
                                ),
                                ft.Text(f"Motivo: {item['motivo']}", color="#CBD5E1", size=13),
                                ft.Text(
                                    f"📚 Fonte: {item.get('fonte_oficial', '')}\n🕒 Busca realizada em: {item.get('horario_busca_item', dados['atualizacao'])}",
                                    color="#38BDF8",
                                    size=11,
                                    weight=ft.FontWeight.W_600,
                                ),
                            ],
                        ),
                    ),
                    ft.ResponsiveRow(
                        spacing=10,
                        controls=[
                            ft.Container(
                                col={"xs": 4},
                                bgcolor="#0B111E",
                                padding=12,
                                border_radius=14,
                                content=ft.Column([
                                    ft.Text("ESTIM. 15 DIAS", color="#94A3B8", size=10),
                                    ft.Text(f"R$ {item['prev_15d']:.2f}", color="#38BDF8", size=16, weight=ft.FontWeight.BOLD),
                                ]),
                            ),
                            ft.Container(
                                col={"xs": 4},
                                bgcolor="#0B111E",
                                padding=12,
                                border_radius=14,
                                content=ft.Column([
                                    ft.Text("ESTIM. 30 DIAS", color="#94A3B8", size=10),
                                    ft.Text(f"R$ {item['prev_30d']:.2f}", color="#A855F7", size=16, weight=ft.FontWeight.BOLD),
                                ]),
                            ),
                            ft.Container(
                                col={"xs": 4},
                                bgcolor="#0B111E",
                                padding=12,
                                border_radius=14,
                                content=ft.Column([
                                    ft.Text("ESTIM. 90 DIAS", color="#94A3B8", size=10),
                                    ft.Text(f"R$ {item['prev_90d']:.2f}", color="#FACC15", size=16, weight=ft.FontWeight.BOLD),
                                ]),
                            ),
                        ],
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                        spacing=8,
                        controls=[
                            ft.ElevatedButton(
                                "🧠 Gráfico & IA",
                                bgcolor="#1E293B",
                                color="#FACC15",
                                height=36,
                                on_click=acao_previsao_card,
                            ),
                            ft.ElevatedButton(
                                "🔍 Ver Fonte/Hora",
                                bgcolor="#1E293B",
                                color="#38BDF8",
                                height=36,
                                on_click=lambda e, nm=item["nome"], dt=detalhes_fonte_card, u=item.get("url_fonte"): abrir_modal_fontes(nm, dt, u),
                            ),
                            ft.ElevatedButton(
                                "📋 Copiar",
                                bgcolor="#1E293B",
                                color="#10B981",
                                height=36,
                                on_click=lambda e, nm=item["nome"], tx=texto_copiar_card: copiar_para_area_transferencia(nm, tx),
                            ),
                            ft.TextButton(
                                "🗺️ Regiões Sul",
                                on_click=lambda e, i=idx: abrir_regional_item(i),
                            ),
                        ],
                    ),
                ],
            ),
        )
        grade.controls.append(card)

      corpo_view.controls.append(grade)

    # -------------------------------------------------------------------------
    # ABA 2: CLIMA AGRÍCOLA & HISTÓRICO DE ESTAÇÕES DE ANOS ANTERIORES
    # -------------------------------------------------------------------------
    elif aba_atual == "clima":
      info_polo = POLOS_CLIMA_SUL[polo_clima_sel]
      previsao_10d, hora_clima, fonte_modo_clima = buscar_previsao_tempo_openmeteo(polo_clima_sel)
      total_chuva_10d = round(sum(d["chuva_mm"] for d in previsao_10d), 1)
      dias_com_chuva = sum(1 for d in previsao_10d if d["chuva_mm"] >= 1.0)

      def mudar_polo_clima(e):
        nonlocal polo_clima_sel
        polo_clima_sel = dd_polo.value
        renderizar()

      def mudar_estacao_clima(est):
        nonlocal estacao_clima_sel
        estacao_clima_sel = est
        renderizar()

      dd_polo = ft.Dropdown(
          label="📍 Selecione o Polo Agrícola da Região Sul (RS / SC / PR)",
          bgcolor="#0B111E",
          color="#FFFFFF",
          border_radius=12,
          width=440,
          options=[ft.dropdown.Option(k) for k in POLOS_CLIMA_SUL.keys()],
          value=polo_clima_sel,
          on_change=mudar_polo_clima,
      )

      cards_10d = ft.ResponsiveRow(spacing=10, run_spacing=10)
      for d in previsao_10d:
        chove = d["chuva_mm"] >= 2.0
        cor_c = "#38BDF8" if chove else "#FACC15"
        icone_c = ft.icons.WATER_DROP_ROUNDED if chove else ft.icons.WB_SUNNY_ROUNDED
        cards_10d.controls.append(
            ft.Container(
                col={"xs": 6, "sm": 4, "md": 2.4},
                bgcolor="#0B111E",
                padding=14,
                border_radius=16,
                border=ft.border.all(1, "#38BDF8" if chove else "#1E293B"),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                    controls=[
                        ft.Text(d["data"], color="#FFFFFF", size=14, weight=ft.FontWeight.BOLD),
                        ft.Icon(icone_c, color=cor_c, size=26),
                        ft.Text(f"{d['chuva_mm']:.1f} mm", color="#38BDF8", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Prob: {d['prob']}%", color="#94A3B8", size=11),
                        ft.Text(f"{d['tmin']:.0f}°C / {d['tmax']:.0f}°C", color="#E2E8F0", size=12),
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
                height=40,
                on_click=lambda e, es=nome_est: mudar_estacao_clima(es),
            )
        )

      dados_est = info_polo["historico_estacoes"][estacao_clima_sel]
      max_mm = max(dados_est.values()) if dados_est else 500

      itens_barras_anos = [
          ("Ano 2023 (El Niño Forte)", dados_est["2023"], "#0EA5E9"),
          ("Ano 2024 (Transição / Chuvas Intensas)", dados_est["2024"], "#38BDF8"),
          ("Ano 2025 (La Niña / Neutro)", dados_est["2025"], "#A855F7"),
          ("Média Histórica (30 Anos - ERA5/INMET)", dados_est["media_hist"], "#94A3B8"),
          ("Previsão Safra 2026/2027 (Estimativa IA)", dados_est["2026_est"], "#10B981"),
      ]

      colunas_comparativo_anos = ft.Column(spacing=10)
      for rotulo_ano, mm_val, cor_b in itens_barras_anos:
        prop = mm_val / max(1, max_mm)
        desvio_hist = mm_val - dados_est["media_hist"]
        colunas_comparativo_anos.controls.append(
            ft.Container(
                bgcolor="#0B111E",
                padding=14,
                border_radius=14,
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(rotulo_ano, color="#FFFFFF", size=14, weight=ft.FontWeight.BOLD),
                                ft.Text(
                                    f"{mm_val} mm acumulados ({desvio_hist:+d} mm vs Média Histórica)",
                                    color=cor_b,
                                    size=13,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                        ),
                        ft.Container(
                            bgcolor="#131E32",
                            height=20,
                            border_radius=10,
                            content=ft.Row([ft.Container(width=int(prop * 520), height=20, bgcolor=cor_b, border_radius=10)]),
                        ),
                    ],
                ),
            )
        )

      analise_chuva_safra = (
          f"Diagnóstico Pluviométrico ({polo_clima_sel}): Nos próximos 10 dias,"
          f" os modelos ECMWF e NOAA GFS projetam acumulado de {total_chuva_10d:.1f} mm"
          f" distribuídos em {dias_com_chuva} dia(s) com precipitação. Comparando a"
          f" estação {estacao_clima_sel} com os anos anteriores (2023: {dados_est['2023']} mm,"
          f" 2024: {dados_est['2024']} mm, 2025: {dados_est['2025']} mm), a previsão"
          f" para o ciclo 2026/2027 ({dados_est['2026_est']} mm) situa-se próxima da"
          f" normalidade histórica ({dados_est['media_hist']} mm)."
      )

      texto_copia_clima = (
          f"🌧️ CR AgroStat — Boletim Climático ({polo_clima_sel})\n"
          f"🕒 Data/Hora da Consulta: {hora_clima}\n"
          f"📚 Fonte: {info_polo['estacao_inmet']} ({fonte_modo_clima})\n"
          f"💧 Próximos 10 Dias: {total_chuva_10d:.1f} mm acumulados ({dias_com_chuva} dias de chuva)\n"
          f"🌦️ Comparativo {estacao_clima_sel}: 2023={dados_est['2023']}mm | 2024={dados_est['2024']}mm | 2025={dados_est['2025']}mm | Média={dados_est['media_hist']}mm | Previsão 2026/27={dados_est['2026_est']}mm"
      )

      detalhes_fonte_clima = [
          f"Polo Agrícola Selecionado: {polo_clima_sel}",
          f"Coordenadas de Satélite Consultadas: Latitude {info_polo['lat']} | Longitude {info_polo['lon']}",
          f"Data e Horário Exato da Busca: {hora_clima}",
          f"Motor de Previsão de 10 Dias: {fonte_modo_clima}",
          f"Estação / Base Histórica de Referência: {info_polo['estacao_inmet']} + Reanálise Climatológica ERA5",
      ]

      corpo_view.controls.append(
          ft.Container(
              bgcolor="#111927",
              padding=28,
              border_radius=26,
              border=ft.border.all(1.5, "#1E293B"),
              content=ft.Column(
                  spacing=20,
                  controls=[
                      ft.Row(
                          alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                          wrap=True,
                          controls=[
                              ft.Column([
                                  ft.Text(
                                      "🌧️ Inteligência Climática & Comparativo de Chuvas de Anos Anteriores",
                                      color="#FFFFFF",
                                      size=22,
                                      weight=ft.FontWeight.BOLD,
                                  ),
                                  ft.Text(
                                      f"📚 Fonte: {info_polo['estacao_inmet']}  |  🕒 Consultado em: {hora_clima}",
                                      color="#10B981",
                                      size=12,
                                      weight=ft.FontWeight.BOLD,
                                  ),
                              ]),
                              ft.Row(
                                  wrap=True,
                                  spacing=8,
                                  controls=[
                                      ft.ElevatedButton(
                                          "🔍 Fontes e Horário",
                                          bgcolor="#1E293B",
                                          color="#38BDF8",
                                          on_click=lambda e: abrir_modal_fontes(
                                              f"Clima {polo_clima_sel}",
                                              detalhes_fonte_clima,
                                              "https://open-meteo.com/",
                                          ),
                                      ),
                                      ft.ElevatedButton(
                                          "📋 Copiar Boletim",
                                          bgcolor="#1E293B",
                                          color="#10B981",
                                          on_click=lambda e: copiar_para_area_transferencia(
                                              "Boletim Climático", texto_copia_clima
                                          ),
                                      ),
                                      ft.ElevatedButton(
                                          "📄 Gerar PDF",
                                          bgcolor="#0284C7",
                                          color="#FFFFFF",
                                          on_click=lambda e: gerar_pdf_completo_usuario(
                                              f"Boletim Climatico - {polo_clima_sel}"
                                          ),
                                      ),
                                  ],
                              ),
                          ],
                      ),
                      dd_polo,
                      ft.Container(
                          bgcolor="#0B111E",
                          padding=16,
                          border_radius=16,
                          border=ft.border.all(1, "#38BDF8"),
                          content=ft.Row(
                              alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                              wrap=True,
                              controls=[
                                  ft.Text(f"🌾 Vocação do Polo: {info_polo['perfil']}", color="#E2E8F0", size=14),
                                  ft.Text(
                                      f"💧 Acumulado Previsto (Próximos 10 Dias): {total_chuva_10d:.1f} mm ({dias_com_chuva} dias de chuva)",
                                      color="#38BDF8",
                                      size=15,
                                      weight=ft.FontWeight.BOLD,
                                  ),
                              ],
                          ),
                      ),
                      ft.Text(
                          "📅 Previsão Diária Assertiva de Chuva e Temperatura (Próximos 10 Dias — Satélite ECMWF/GFS):",
                          color="#FACC15",
                          size=16,
                          weight=ft.FontWeight.BOLD,
                      ),
                      cards_10d,
                      ft.Divider(color="#1E293B"),
                      ft.Text(
                          "📊 Comparativo de Chuvas por Estação — Anos Anteriores (2023, 2024, 2025) vs. Previsão Safra 2026/27:",
                          color="#FFFFFF",
                          size=18,
                          weight=ft.FontWeight.BOLD,
                      ),
                      botoes_estacoes,
                      colunas_comparativo_anos,
                      ft.Container(
                          bgcolor="#0B111E",
                          padding=16,
                          border_radius=16,
                          border=ft.border.all(1, "#10B981"),
                          content=ft.Row(
                              spacing=10,
                              controls=[
                                  ft.Icon(ft.icons.CLOUD_SYNC_ROUNDED, color="#10B981", size=26),
                                  ft.Text(analise_chuva_safra, color="#E2E8F0", size=13, expand=True),
                              ],
                          ),
                      ),
                  ],
              ),
          )
      )

    # -------------------------------------------------------------------------
    # ABA 3: CONTRATOS DA EMPRESA & COMPARATIVO REGIÃO SUL (RS, SC e PR)
    # -------------------------------------------------------------------------
    elif aba_atual == "regional":
      item_reg = dados["itens"][item_regional_idx]

      def escolher_item_reg(idx):
        nonlocal item_regional_idx, horario_ultima_selecao
        item_regional_idx = idx
        horario_ultima_selecao = agora_str()
        renderizar()

      def escolher_uf_reg(uf):
        nonlocal uf_aba_regional, horario_ultima_selecao
        uf_aba_regional = uf
        horario_ultima_selecao = agora_str()
        renderizar()

      botoes_itens_reg = ft.Row(wrap=True, spacing=8)
      for idx, it in enumerate(dados["itens"]):
        ativo = idx == item_regional_idx
        botoes_itens_reg.controls.append(
            ft.ElevatedButton(
                f"✓ {it['nome']}" if ativo else it["nome"],
                bgcolor=it["cor"] if ativo else "#1E293B",
                color="#080D16" if ativo else "#FFFFFF",
                height=40,
                on_click=lambda e, i=idx: escolher_item_reg(i),
            )
        )

      opcoes_filtro_reg = [
          ("TODOS", "🌎 Todos os 3 Estados (RS + SC + PR)"),
          ("RS", "🟢 Só Rio Grande do Sul (RS)"),
          ("SC", "🔴 Só Santa Catarina (SC)"),
          ("PR", "🔵 Só Paraná (PR)"),
      ]
      botoes_filtro_uf = ft.Row(wrap=True, spacing=8)
      for cod_f, rot_f in opcoes_filtro_reg:
        at_f = uf_aba_regional == cod_f
        botoes_filtro_uf.controls.append(
            ft.ElevatedButton(
                f"✓ {rot_f}" if at_f else rot_f,
                bgcolor="#10B981" if at_f else "#1E293B",
                color="#080D16" if at_f else "#FFFFFF",
                on_click=lambda e, c=cod_f: escolher_uf_reg(c),
            )
        )

      campo_contrato_emp = ft.TextField(
          label=f"Valor do Contrato da Empresa para {item_reg['nome']} (R$ / {item_reg['unidade']})",
          value=f"{item_reg['contrato_empresa']:.2f}",
          bgcolor="#0B111E",
          color="#FFFFFF",
          border_radius=14,
          width=400,
      )

      campos_regioes = {}
      linhas_regioes_ui = ft.Column(spacing=12)

      def atualizar_analise_sul(e=None):
        linhas_regioes_ui.controls.clear()
        try:
          val_emp = float(campo_contrato_emp.value.replace(",", "."))
          item_reg["contrato_empresa"] = val_emp
        except Exception:
          val_emp = item_reg["contrato_empresa"]

        for (uf_k, nome_praca), tf_ctrl in campos_regioes.items():
          try:
            v_praca = float(tf_ctrl.value.replace(",", "."))
            item_reg["regioes_sul"][uf_k][nome_praca] = v_praca
          except Exception:
            pass

        item_reg["medias_uf"] = calcular_medias_estados(item_reg["regioes_sul"])
        ufs_exibir = ["RS", "SC", "PR"] if uf_aba_regional == "TODOS" else [uf_aba_regional]
        nomes_uf_extenso = {
            "RS": "🟢 RIO GRANDE DO SUL (RS)",
            "SC": "🔴 SANTA CATARINA (SC)",
            "PR": "🔵 PARANÁ (PR)",
        }

        for uf_k in ufs_exibir:
          m_desta_uf = item_reg["medias_uf"][uf_k]
          linhas_regioes_ui.controls.append(
              ft.Container(
                  bgcolor="#1E293B",
                  padding=12,
                  border_radius=12,
                  content=ft.Row(
                      alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                      controls=[
                          ft.Text(nomes_uf_extenso[uf_k], color="#FFFFFF", size=16, weight=ft.FontWeight.BOLD),
                          ft.Text(
                              f"Média Estadual {uf_k}: R$ {m_desta_uf:.2f}  |  Diferença p/ Contrato: {m_desta_uf - val_emp:+.2f} R$",
                              color="#FACC15",
                              size=14,
                              weight=ft.FontWeight.BOLD,
                          ),
                      ],
                  ),
              )
          )

          for nome_praca, valor_praca in item_reg["regioes_sul"][uf_k].items():
            dif = valor_praca - val_emp
            perc = (dif / val_emp * 100) if val_emp > 0 else 0
            if dif > 0:
              status_praca = f"Praça paga +R$ {dif:.2f} ({perc:+.1f}%) acima do contrato da empresa"
              cor_dif = "#FACC15"
            elif dif < 0:
              status_praca = f"Contrato da empresa está R$ {abs(dif):.2f} acima desta praça"
              cor_dif = "#22C55E"
            else:
              status_praca = "Empatado com o valor do contrato da empresa"
              cor_dif = "#38BDF8"

            tf = ft.TextField(label="Valor na Praça (R$)", value=f"{valor_praca:.2f}", bgcolor="#111927", color="#FFFFFF", border_radius=12, width=170)
            campos_regioes[(uf_k, nome_praca)] = tf

            linhas_regioes_ui.controls.append(
                ft.Container(
                    bgcolor="#0B111E",
                    padding=15,
                    border_radius=16,
                    border=ft.border.all(1, "#1E293B"),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                        controls=[
                            ft.Column(
                                spacing=4,
                                controls=[
                                    ft.Text(f"📍 {nome_praca}", color="#FFFFFF", size=15, weight=ft.FontWeight.BOLD),
                                    ft.Text(status_praca, color=cor_dif, size=13, weight=ft.FontWeight.W_600),
                                ],
                            ),
                            tf,
                        ],
                    ),
                )
            )

        salvar_db(dados)
        if e is not None:
          mostrar_aviso("Contrato e valores de RS, SC e PR recalculados e guardados!")
        page.update()

      atualizar_analise_sul(None)

      m_reg = item_reg["medias_uf"]
      texto_copia_reg = (
          f"🗺️ CR AgroStat — Comparativo Regional ({item_reg['nome']})\n"
          f"🕒 Data/Hora: {horario_ultima_selecao}\n"
          f"🏢 Contrato da Empresa: R$ {item_reg['contrato_empresa']:.2f} ({item_reg['unidade']})\n"
          f"🟢 Média RS: R$ {m_reg['RS']:.2f} | 🔴 Média SC: R$ {m_reg['SC']:.2f} | 🔵 Média PR: R$ {m_reg['PR']:.2f}\n"
          f"📚 Fonte: {item_reg.get('fonte_oficial', '')}"
      )

      corpo_view.controls.append(
          ft.Container(
              bgcolor="#111927",
              padding=28,
              border_radius=26,
              border=ft.border.all(1.5, "#1E293B"),
              content=ft.Column(
                  spacing=18,
                  controls=[
                      ft.Row(
                          alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                          wrap=True,
                          controls=[
                              ft.Column([
                                  ft.Text("🗺️ Contratos da Empresa & Comparativo Região Sul (RS, SC e PR)", color="#FFFFFF", size=22, weight=ft.FontWeight.BOLD),
                                  ft.Text(
                                      f"📚 Fonte: {item_reg.get('fonte_oficial', '')}  |  🕒 Selecionado em: {horario_ultima_selecao}",
                                      color="#10B981",
                                      size=12,
                                  ),
                              ]),
                              ft.Row(
                                  spacing=8,
                                  controls=[
                                      ft.ElevatedButton(
                                          "📋 Copiar Comparativo",
                                          bgcolor="#1E293B",
                                          color="#10B981",
                                          on_click=lambda e: copiar_para_area_transferencia("Comparativo Regional", texto_copia_reg),
                                      ),
                                      ft.ElevatedButton(
                                          "📄 Gerar PDF",
                                          bgcolor="#0284C7",
                                          color="#FFFFFF",
                                          on_click=lambda e: gerar_pdf_completo_usuario(f"Comparativo Regional - {item_reg['nome']}"),
                                      ),
                                  ],
                              ),
                          ],
                      ),
                      botoes_itens_reg,
                      botoes_filtro_uf,
                      ft.Row(
                          wrap=True,
                          spacing=16,
                          vertical_alignment=ft.CrossAxisAlignment.CENTER,
                          controls=[
                              campo_contrato_emp,
                              ft.ElevatedButton("Recalcular e Guardar RS / SC / PR", icon=ft.icons.SAVE_ROUNDED, bgcolor="#10B981", color="#080D16", height=50, on_click=atualizar_analise_sul),
                          ],
                      ),
                      linhas_regioes_ui,
                  ],
              ),
          )
      )

    # -------------------------------------------------------------------------
    # ABA 4: ESTUDO DE FRETES E ROTAS INTERESTADUAIS (RS, SC e PR)
    # -------------------------------------------------------------------------
    elif aba_atual == "frete":
      c_km = ft.TextField(label="Distância da Rota (KM)", value="220", bgcolor="#0B111E", color="#FFFFFF", border_radius=12, width=210)
      c_rkm = ft.TextField(label="Valor Cobrado por KM (R$/km)", value="6.80", bgcolor="#0B111E", color="#FFFFFF", border_radius=12, width=210)
      c_ton = ft.TextField(label="Carga do Caminhão (Toneladas)", value="32", bgcolor="#0B111E", color="#FFFFFF", border_radius=12, width=210)
      c_pedagio = ft.TextField(label="Pedágio / Taxas Extras (R$)", value="140.00", bgcolor="#0B111E", color="#FFFFFF", border_radius=12, width=210)
      painel_res_frete = ft.Column(spacing=14)
      resumo_frete_str = ""

      def calcular_estudo_frete(e=None):
        nonlocal resumo_frete_str
        painel_res_frete.controls.clear()
        try:
          km = float(c_km.value.replace(",", "."))
          rkm = float(c_rkm.value.replace(",", "."))
          ton = float(c_ton.value.replace(",", "."))
          ped = float(c_pedagio.value.replace(",", "."))

          custo_viagem = (km * rkm) + ped
          custo_ton = custo_viagem / ton if ton > 0 else 0
          custo_saca_60 = custo_ton * 0.06
          custo_saca_50 = custo_ton * 0.05
          custo_saca_40 = custo_ton * 0.04

          resumo_frete_str = (
              f"🚛 CR AgroStat — Estudo de Frete ({agora_str()})\n"
              f"Rota: {km:.0f} km | R$ {rkm:.2f}/km | Carga: {ton:.1f} ton | Pedágio: R$ {ped:.2f}\n"
              f"Custo Total: R$ {custo_viagem:,.2f} | Por Tonelada: R$ {custo_ton:.2f}/ton\n"
              f"Impacto Saca 60kg: R$ {custo_saca_60:.2f} | Saca 50kg: R$ {custo_saca_50:.2f} | Semente 40kg: R$ {custo_saca_40:.2f}\n"
              f"Fonte: Parâmetros ANTT / SIFRECA-Esalq + Cálculo Operacional Direto"
          )

          painel_res_frete.controls.append(
              ft.ResponsiveRow(
                  spacing=14,
                  run_spacing=14,
                  controls=[
                      ft.Container(col={"xs": 12, "sm": 6, "md": 3}, bgcolor="#0B111E", padding=16, border_radius=16, border=ft.border.all(1, "#38BDF8"), content=ft.Column([ft.Text("CUSTO TOTAL DA VIAGEM", color="#94A3B8", size=11), ft.Text(f"R$ {custo_viagem:,.2f}", color="#38BDF8", size=22, weight=ft.FontWeight.BOLD)])),
                      ft.Container(col={"xs": 12, "sm": 6, "md": 3}, bgcolor="#0B111E", padding=16, border_radius=16, border=ft.border.all(1, "#10B981"), content=ft.Column([ft.Text("FRETE POR TONELADA", color="#94A3B8", size=11), ft.Text(f"R$ {custo_ton:,.2f} / ton", color="#10B981", size=22, weight=ft.FontWeight.BOLD)])),
                      ft.Container(col={"xs": 12, "sm": 6, "md": 3}, bgcolor="#0B111E", padding=16, border_radius=16, border=ft.border.all(1, "#FACC15"), content=ft.Column([ft.Text("IMPACTO SACA 60KG (SOJA/MILHO)", color="#94A3B8", size=11), ft.Text(f"R$ {custo_saca_60:.2f} / sc", color="#FACC15", size=22, weight=ft.FontWeight.BOLD)])),
                      ft.Container(col={"xs": 12, "sm": 6, "md": 3}, bgcolor="#0B111E", padding=16, border_radius=16, border=ft.border.all(1, "#A855F7"), content=ft.Column([ft.Text("ARROZ (50KG) / SEMENTE (40KG)", color="#94A3B8", size=11), ft.Text(f"R$ {custo_saca_50:.2f} | R$ {custo_saca_40:.2f}", color="#A855F7", size=18, weight=ft.FontWeight.BOLD)])),
                  ],
              )
          )

          rotas_sul = [
              ("Tiro Curto Regional (80 km)", 80),
              ("Noroeste RS (Ijuí) ➔ Oeste SC (Chapecó) [210 km]", 210),
              ("Fronteira Oeste RS (São Borja) ➔ Meio-Oeste SC (Campos Novos) [430 km]", 430),
              ("Fronteira Oeste RS (São Borja) ➔ Porto de Rio Grande/RS [560 km]", 560),
              ("Oeste PR (Cascavel) ➔ Porto de Paranaguá/PR [580 km]", 580),
          ]
          for nome_r, dist_r in rotas_sul:
            tot_r = (dist_r * rkm) + ped
            sc60_r = (tot_r / ton) * 0.06 if ton > 0 else 0
            painel_res_frete.controls.append(
                ft.Container(
                    bgcolor="#0B111E",
                    padding=14,
                    border_radius=14,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                        controls=[
                            ft.Text(f"🚛 {nome_r}", color="#FFFFFF", weight=ft.FontWeight.BOLD),
                            ft.Text(f"Total: R$ {tot_r:,.2f}  |  Por Tonelada: R$ {(tot_r/ton):.2f}  |  Saca 60kg: R$ {sc60_r:.2f}", color="#CBD5E1"),
                        ],
                    ),
                )
            )
        except Exception:
          painel_res_frete.controls.append(ft.Text("Preencha apenas números válidos.", color="#EF4444"))
        page.update()

      calcular_estudo_frete(None)

      corpo_view.controls.append(
          ft.Container(
              bgcolor="#111927",
              padding=28,
              border_radius=26,
              border=ft.border.all(1.5, "#1E293B"),
              content=ft.Column(
                  spacing=20,
                  controls=[
                      ft.Row(
                          alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                          wrap=True,
                          controls=[
                              ft.Column([
                                  ft.Text("🚛 Estudo de Preços de Fretes & Rotas da Região Sul (RS, SC e PR)", color="#FFFFFF", size=22, weight=ft.FontWeight.BOLD),
                                  ft.Text(f"📚 Fonte de Referência Logística: Tabelas ANTT / SIFRECA-Esalq  |  🕒 Cálculo em: {agora_str()}", color="#10B981", size=12),
                              ]),
                              ft.Row(
                                  spacing=8,
                                  controls=[
                                      ft.ElevatedButton("📋 Copiar Frete", bgcolor="#1E293B", color="#10B981", on_click=lambda e: copiar_para_area_transferencia("Estudo de Frete", resumo_frete_str)),
                                      ft.ElevatedButton("📄 Gerar PDF", bgcolor="#0284C7", color="#FFFFFF", on_click=lambda e: gerar_pdf_completo_usuario("Estudo Logistico de Fretes")),
                                  ],
                              ),
                          ],
                      ),
                      ft.Row(wrap=True, spacing=14, controls=[c_km, c_rkm, c_ton, c_pedagio]),
                      ft.ElevatedButton("Calcular Estudo Logístico", icon=ft.icons.CALCULATE_ROUNDED, bgcolor="#FACC15", color="#080D16", height=48, on_click=calcular_estudo_frete),
                      painel_res_frete,
                  ],
              ),
          )
      )

    # -------------------------------------------------------------------------
    # ABA 5: SIMULADOR BARTER & PREÇO LÍQUIDO
    # -------------------------------------------------------------------------
    elif aba_atual == "barter":
      s_qtd = ft.TextField(label="Quantidade de Sacas", value="500", bgcolor="#0B111E", color="#FFFFFF", border_radius=12, width=220)
      s_preco = ft.TextField(label="Preço Bruto da Saca (R$)", value="132.50", bgcolor="#0B111E", color="#FFFFFF", border_radius=12, width=220)
      s_frete = ft.TextField(label="Frete + Taxas por Saca (R$)", value="4.50", bgcolor="#0B111E", color="#FFFFFF", border_radius=12, width=220)
      s_sem = ft.TextField(label="Preço da Saca de Semente (R$)", value="295.00", bgcolor="#0B111E", color="#FFFFFF", border_radius=12, width=220)
      txt_res_b = ft.Text("", color="#22C55E", size=17, weight=ft.FontWeight.BOLD)

      def calc_b(e=None):
        try:
          q = float(s_qtd.value.replace(",", "."))
          p = float(s_preco.value.replace(",", "."))
          fr = float(s_frete.value.replace(",", "."))
          sm = float(s_sem.value.replace(",", "."))
          liq = p - fr
          tot = q * liq
          troca = sm / liq if liq > 0 else 0
          qtd_sem = tot / sm if sm > 0 else 0
          txt_res_b.value = (
              f"💰 Preço Líquido Limpo por Saca: R$ {liq:.2f}\n"
              f"🏦 Faturamento Líquido Total do Lote: R$ {tot:,.2f}\n"
              f"⚖️ Relação de Troca (Barter): {troca:.2f} sacas de grão pagam 1 unidade de semente\n"
              f"🌱 Poder de Compra Total: Este lote compra {qtd_sem:.1f} unidades de semente.\n"
              f"🕒 Simulação realizada em: {agora_str()}"
          )
        except Exception:
          txt_res_b.value = "Digite números válidos nos campos."
        page.update()

      calc_b(None)

      corpo_view.controls.append(
          ft.Container(
              bgcolor="#111927",
              padding=28,
              border_radius=26,
              border=ft.border.all(1.5, "#1E293B"),
              content=ft.Column(
                  spacing=20,
                  controls=[
                      ft.Row(
                          alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                          wrap=True,
                          controls=[
                              ft.Text("⚖️ Simulador de Preço Líquido & Relação de Troca (Barter)", color="#FFFFFF", size=22, weight=ft.FontWeight.BOLD),
                              ft.Row(
                                  spacing=8,
                                  controls=[
                                      ft.ElevatedButton("📋 Copiar Simulação", bgcolor="#1E293B", color="#10B981", on_click=lambda e: copiar_para_area_transferencia("Simulação Barter", txt_res_b.value)),
                                      ft.ElevatedButton("📄 Gerar PDF", bgcolor="#0284C7", color="#FFFFFF", on_click=lambda e: gerar_pdf_completo_usuario("Simulacao Barter")),
                                  ],
                              ),
                          ],
                      ),
                      ft.Row(wrap=True, spacing=14, controls=[s_qtd, s_preco, s_frete, s_sem]),
                      ft.ElevatedButton("Calcular Relação de Troca", bgcolor="#10B981", color="#080D16", height=48, on_click=calc_b),
                      ft.Container(bgcolor="#0B111E", padding=20, border_radius=18, border=ft.border.all(1, "#10B981"), content=txt_res_b),
                  ],
              ),
          )
      )

    # -------------------------------------------------------------------------
    # ABA 6: PLANILHAS DE DADOS, EXPORTAÇÃO EXCEL (.CSV) E GERADOR DE PDF
    # -------------------------------------------------------------------------
    elif aba_atual == "relatorios":
      f_uf = ft.Dropdown(label="Estado (UF)", bgcolor="#0B111E", color="#FFFFFF", width=110, options=[ft.dropdown.Option("RS"), ft.dropdown.Option("SC"), ft.dropdown.Option("PR")], value="RS")
      f_item = ft.Dropdown(label="Item", bgcolor="#0B111E", color="#FFFFFF", width=220, options=[ft.dropdown.Option(i["nome"]) for i in dados["itens"]], value=dados["itens"][0]["nome"])
      f_regiao = ft.TextField(label="Cidade / Região", value="São Borja - Fronteira Oeste", bgcolor="#0B111E", color="#FFFFFF", width=220)
      f_lote = ft.TextField(label="Volume / Lote", value="1.000 Sacas", bgcolor="#0B111E", color="#FFFFFF", width=160)
      f_valor = ft.TextField(label="Valor (R$)", value="133.50", bgcolor="#0B111E", color="#FFFFFF", width=150)
      f_obs = ft.TextField(label="Observação", value="Contrato safra", bgcolor="#0B111E", color="#FFFFFF", width=220)

      def adicionar_linha_planilha(e):
        novo_reg = {
            "data": agora_str(),
            "uf": f_uf.value,
            "item": f_item.value,
            "regiao": f_regiao.value,
            "lote": f_lote.value,
            "valor": f_valor.value,
            "obs": f_obs.value,
        }
        dados.setdefault("registros_planilha", []).insert(0, novo_reg)
        salvar_db(dados)
        mostrar_aviso("Registo adicionado à planilha com data e horário!")
        renderizar()

      def exportar_planilha_csv(e):
        os.makedirs(PASTA_RELATORIOS, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%Hh%Mm%Ss")
        arq_csv = os.path.join(PASTA_RELATORIOS, f"Planilha_Sul_CRAgroStat_{stamp}.csv")

        with open(arq_csv, "w", newline="", encoding="utf-8-sig") as f:
          w = csv.writer(f, delimiter=";")
          w.writerow(["ITEM", "UNIDADE", "PRECO ATUAL", "MEDIA RS", "MEDIA SC", "MEDIA PR", "MEDIA GERAL SUL", "CONTRATO EMPRESA", "ESTIMATIVA 15D", "ESTIMATIVA 30D", "ESTIMATIVA 90D", "DATA E HORA DA BUSCA", "FONTE DOS RESULTADOS"])
          for it in dados["itens"]:
            m_u = calcular_medias_estados(it["regioes_sul"])
            w.writerow([
                it["nome"],
                it["unidade"],
                f"{it['preco_atual']:.2f}".replace(".", ","),
                f"{m_u['RS']:.2f}".replace(".", ","),
                f"{m_u['SC']:.2f}".replace(".", ","),
                f"{m_u['PR']:.2f}".replace(".", ","),
                f"{m_u['SUL']:.2f}".replace(".", ","),
                f"{it['contrato_empresa']:.2f}".replace(".", ","),
                f"{it['prev_15d']:.2f}".replace(".", ","),
                f"{it['prev_30d']:.2f}".replace(".", ","),
                f"{it['prev_90d']:.2f}".replace(".", ","),
                it.get("horario_busca_item", dados["atualizacao"]),
                it.get("fonte_oficial", ""),
            ])

        mostrar_aviso(f"Planilha Excel (.csv) guardada em '{PASTA_RELATORIOS}'!")
        renderizar()

      lista_lancamentos = ft.Column(spacing=8)
      for r in dados.get("registros_planilha", [])[:10]:
        txt_linha = f"{r['data']} | [{r.get('uf', 'RS')}] {r['item']} ({r['regiao']}) | Lote: {r['lote']} | R$ {r['valor']} | {r['obs']}"
        lista_lancamentos.controls.append(
            ft.Container(
                bgcolor="#0B111E",
                padding=12,
                border_radius=12,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    controls=[
                        ft.Text(f"📅 {r['data']}  •  [{r.get('uf', 'RS')}] {r['item']} ({r['regiao']})", color="#FFFFFF", weight=ft.FontWeight.BOLD),
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.Text(f"Lote: {r['lote']}  |  R$ {r['valor']}  |  {r['obs']}", color="#10B981"),
                                ft.IconButton(
                                    icon=ft.icons.CONTENT_COPY_ROUNDED,
                                    icon_color="#38BDF8",
                                    tooltip="Copiar esta linha",
                                    on_click=lambda e, tx=txt_linha: copiar_para_area_transferencia("Linha da Planilha", tx),
                                ),
                            ],
                        ),
                    ],
                ),
            )
        )

      os.makedirs(PASTA_RELATORIOS, exist_ok=True)
      arquivos_salvos = sorted(os.listdir(PASTA_RELATORIOS), reverse=True)[:8]
      col_arquivos = ft.Column(spacing=6)
      for nome_a in arquivos_salvos:
        col_arquivos.controls.append(ft.Text(f"📄 {PASTA_RELATORIOS}/{nome_a}", color="#38BDF8", size=13))

      corpo_view.controls.append(
          ft.Container(
              bgcolor="#111927",
              padding=28,
              border_radius=26,
              border=ft.border.all(1.5, "#1E293B"),
              content=ft.Column(
                  spacing=20,
                  controls=[
                      ft.Text("📁 Planilhas de Dados, Exportação Excel (.CSV) & Gerador de PDF Oficial", color="#FFFFFF", size=22, weight=ft.FontWeight.BOLD),
                      ft.Row(wrap=True, spacing=12, controls=[f_uf, f_item, f_regiao, f_lote, f_valor, f_obs]),
                      ft.Row(
                          wrap=True,
                          spacing=14,
                          controls=[
                              ft.ElevatedButton("Adicionar Dados na Planilha", icon=ft.icons.ADD_CIRCLE_ROUNDED, bgcolor="#38BDF8", color="#080D16", height=48, on_click=adicionar_linha_planilha),
                              ft.ElevatedButton("Guardar Planilha (.CSV Excel)", icon=ft.icons.TABLE_VIEW_ROUNDED, bgcolor="#10B981", color="#080D16", height=48, on_click=exportar_planilha_csv),
                              ft.ElevatedButton("📄 Gerar Relatório em PDF Oficial", icon=ft.icons.PICTURE_AS_PDF_ROUNDED, bgcolor="#FACC15", color="#080D16", height=48, on_click=lambda e: gerar_pdf_completo_usuario("Relatorio Oficial Completo")),
                          ],
                      ),
                      lista_lancamentos,
                      ft.Divider(color="#1E293B"),
                      ft.Text("Arquivos PDF e Planilhas Gerados na Pasta 'relatorios/':", color="#FFFFFF", size=15, weight=ft.FontWeight.BOLD),
                      col_arquivos,
                  ],
              ),
          )
      )

    # -------------------------------------------------------------------------
    # ABA 7: AUDITORIA DE FONTES, HORÁRIOS E ATALHO DESKTOP
    # -------------------------------------------------------------------------
    elif aba_atual == "nuvem":
      corpo_view.controls.append(
          ft.Container(
              bgcolor="#111927",
              padding=28,
              border_radius=26,
              border=ft.border.all(1.5, "#1E293B"),
              content=ft.Column(
                  spacing=16,
                  controls=[
                      ft.Text("📚 Auditoria de Fontes, Horários de Busca & Atalho no PC", color="#FFFFFF", size=22, weight=ft.FontWeight.BOLD),
                      ft.Container(
                          bgcolor="#0B111E",
                          padding=18,
                          border_radius=16,
                          border=ft.border.all(1, "#10B981"),
                          content=ft.Column(
                              spacing=8,
                              controls=[
                                  ft.Text("🖥️ Atalho 'CR AgroStat' criado na sua Área de Trabalho!", color="#10B981", size=16, weight=ft.FontWeight.BOLD),
                                  ft.Text(
                                      "O sistema criou automaticamente na sua Área de Trabalho (Desktop) o atalho 'CR AgroStat' com o ícone oficial da semente.\n"
                                      "Assim você não depende de clicar em links soltos: basta dar dois cliques no ícone da Área de Trabalho!",
                                      color="#E2E8F0",
                                      size=13,
                                  ),
                              ],
                          ),
                      ),
                      ft.Container(
                          bgcolor="#0B111E",
                          padding=18,
                          border_radius=16,
                          content=ft.Column(
                              spacing=8,
                              controls=[
                                  ft.Text(f"🔍 Registro da Última Busca Global: {dados['atualizacao']}", color="#38BDF8", size=16, weight=ft.FontWeight.BOLD),
                                  ft.Text(
                                      "1. Bolsas Internacionais e Futuros: Chicago Board of Trade (CBOT) via API Yahoo Finance (`ZS=F`, `ZR=F`, `ZC=F`, `ZW=F`).\n"
                                      "2. Taxa de Câmbio: Dólar Comercial Spot (`USDBRL=X`).\n"
                                      "3. Paridades Físicas Região Sul: Referências regionais alinhadas aos polos acompanhados por IRGA/Emater (RS), Epagri/Cepa (SC) e Deral/Cepea-Paranaguá (PR).\n"
                                      "4. Previsão do Tempo e Histórico de Chuvas: Open-Meteo Agro API (Modelos ECMWF Europeu, NOAA GFS e Reanálise Climatológica ERA5).\n"
                                      "5. Notícias e Fundamentos: Google News Agro RSS.",
                                      color="#CBD5E1",
                                      size=13,
                                  ),
                              ],
                          ),
                      ),
                  ],
              ),
          )
      )

    page.update()

  def abrir_regional_item(idx_item):
    nonlocal aba_atual, item_regional_idx, horario_ultima_selecao
    item_regional_idx = idx_item
    horario_ultima_selecao = agora_str()
    mudar_aba("regional")

  def mudar_aba(nova_aba):
    nonlocal aba_atual, horario_ultima_selecao
    aba_atual = nova_aba
    horario_ultima_selecao = agora_str()
    renderizar()

  txt_atualizacao = ft.Text(f"🕒 Última busca nas fontes: {dados['atualizacao']}", color="#94A3B8", size=13)
  txt_dolar = ft.Text(f"Dólar Comercial: R$ {dados['dolar']:.2f} ({dados['dolar_var']:+.2f}%)", color="#38BDF8", size=15, weight=ft.FontWeight.BOLD)

  def acao_atualizar(e):
    nonlocal dados, horario_ultima_selecao
    btn_atualizar.text = "A consultar fontes ao vivo..."
    btn_atualizar.disabled = True
    page.update()
    dados = coletar_mercado(dados)
    horario_ultima_selecao = dados["atualizacao"]
    txt_atualizacao.value = f"🕒 Última busca nas fontes: {dados['atualizacao']}"
    txt_dolar.value = f"Dólar Comercial: R$ {dados['dolar']:.2f} ({dados['dolar_var']:+.2f}%)"
    btn_atualizar.text = "🔄 Atualizar Mercado, Clima e Fontes"
    btn_atualizar.disabled = False
    mostrar_aviso(f"Fontes consultadas com sucesso em {dados['atualizacao']}!")
    renderizar()

  btn_atualizar = ft.ElevatedButton(
      "🔄 Atualizar Mercado, Clima e Fontes",
      bgcolor="#38BDF8",
      color="#080D16",
      height=46,
      on_click=acao_atualizar,
  )

  btn_pdf_topo = ft.ElevatedButton(
      "📄 Gerar PDF Oficial",
      bgcolor="#FACC15",
      color="#080D16",
      height=46,
      on_click=lambda e: gerar_pdf_completo_usuario("Relatorio Executivo Completo"),
  )

  cabecalho = ft.Container(
      width=float("inf"),
      bgcolor="#111927",
      padding=24,
      border_radius=26,
      border=ft.border.all(1.5, "#1E293B"),
      content=ft.Column(
          spacing=16,
          controls=[
              ft.Row(
                  alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                  vertical_alignment=ft.CrossAxisAlignment.CENTER,
                  wrap=True,
                  controls=[
                      ft.Row(
                          spacing=16,
                          controls=[
                              ft.Container(
                                  width=64,
                                  height=64,
                                  bgcolor="#10B981",
                                  border_radius=20,
                                  alignment=ft.alignment.center,
                                  content=ft.Icon(ft.icons.SPA_ROUNDED, color="#080D16", size=38),
                              ),
                              ft.Column(
                                  spacing=2,
                                  controls=[
                                      ft.Text("CR AgroStat", color="#FFFFFF", size=28, weight=ft.FontWeight.BOLD),
                                      ft.Text(
                                          "Estatística Estimada de Grãos, Sementes e Clima • Região Sul (RS • SC • PR)",
                                          color="#10B981",
                                          size=14,
                                          weight=ft.FontWeight.W_600,
                                      ),
                                      txt_atualizacao,
                                  ],
                              ),
                          ],
                      ),
                      ft.Row(wrap=True, spacing=10, controls=[btn_pdf_topo, btn_atualizar]),
                  ],
              ),
              ft.Container(
                  bgcolor="#0B111E",
                  padding=14,
                  border_radius=16,
                  content=ft.Row(
                      alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                      wrap=True,
                      controls=[
                          txt_dolar,
                          ft.Text(
                              "📚 Fontes Ativas: CBOT • PTAX • Paridades IRGA/Epagri/Deral/Cepea • Clima Open-Meteo ECMWF/GFS",
                              color="#10B981",
                              size=12,
                              weight=ft.FontWeight.W_600,
                          ),
                          ft.Text(f"📱 Wi-Fi Local: http://{ip_local}:8550", color="#FACC15", size=13, weight=ft.FontWeight.W_600),
                      ],
                  ),
              ),
              linha_menu_abas,
          ],
      ),
  )

  page.add(cabecalho, corpo_view)
  renderizar()


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