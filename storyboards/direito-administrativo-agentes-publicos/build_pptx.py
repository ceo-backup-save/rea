#!/usr/bin/env python3
"""Monta os decks do storyboard "Agentes Públicos" a partir de prompts.json.

Dois perfis tipográficos:

    classico   Georgia (títulos) + Arial (corpo)          -> apresentacao-agentes-publicos.pptx
    editorial  Cambria (títulos) + Arial (corpo), com escala tipográfica,
               fontes ligadas ao TEMA do PowerPoint (troca global em 1 clique)
                                                            -> apresentacao-agentes-publicos-v2.pptx

Uso:
    python3 -m pip install python-pptx
    python3 build_pptx.py                      # perfil editorial (padrão)
    python3 build_pptx.py --perfil classico
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

BASE_DIR = Path(__file__).parent
PREVIEW = BASE_DIR / "preview"
DATA = json.loads((BASE_DIR / "prompts.json").read_text(encoding="utf-8"))
PROMPTS = DATA["prompts"]

IMAGENS = {
    "cena-01": "cena-01-abertura.png",
    "cena-02": "cena-02-teoria-do-orgao.png",
    "cena-03": "cena-03-investidura.png",
    "cena-04": "cena-04-legalidade.png",
    "cena-05": "cena-05-hierarquia.png",
    "cena-06": "cena-06-impessoalidade.png",
    "cena-07": "cena-07-moralidade.png",
    "cena-08": "cena-08-publicidade.png",
    "cena-09": "cena-09-responsabilidade.png",
    "cena-10": "cena-10-fechamento.png",
    "extra-11": "extra-11-eficiencia.png",
    "extra-12": "extra-12-continuidade.png",
}

W, H = Inches(13.333), Inches(7.5)
NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


# --------------------------------------------------------------- perfis
CLASSICO = {
    "nome": "classico",
    "arquivo": "apresentacao-agentes-publicos.pptx",
    "serifa": "Georgia",
    "sans": "Arial",
    "usar_tema": False,
    "preto": RGBColor(0x00, 0x00, 0x00),
    "marfim": RGBColor(0xED, 0xE6, 0xDA),
    "latao": RGBColor(0xC6, 0xA6, 0x64),
    "cinza": RGBColor(0x9C, 0x99, 0x93),
    "grafite": RGBColor(0x6E, 0x6C, 0x68),
    "margem": 0.95,
    "base_bloco": 6.72,
    "titulo_pt": 30,
    "titulo_track": 120,
    "titulo_alto": 1.24,
    "lead_pt": 13,
    "corpo_pt": 10,
    "kicker_pt": 10,
    "kicker_track": 320,
    "rodape_pt": 8,
    "capa_pt": 54,
    "scrim": 94000,
}

EDITORIAL = {
    "nome": "editorial",
    "arquivo": "apresentacao-agentes-publicos-v2.pptx",
    "serifa": "Cambria",
    "sans": "Arial",
    "usar_tema": True,
    "preto": RGBColor(0x00, 0x00, 0x00),
    "marfim": RGBColor(0xF2, 0xEC, 0xE1),
    "latao": RGBColor(0xC9, 0xA9, 0x6A),
    "cinza": RGBColor(0xBD, 0xB7, 0xAB),
    "grafite": RGBColor(0x7A, 0x76, 0x6F),
    "margem": 1.00,
    "base_bloco": 6.66,
    "titulo_pt": 34,
    "titulo_track": 60,
    "titulo_alto": 1.52,
    "lead_pt": 15,
    "corpo_pt": 11,
    "kicker_pt": 9,
    "kicker_track": 400,
    "rodape_pt": 8,
    "capa_pt": 60,
    "scrim": 93000,
}

PERFIS = {"classico": CLASSICO, "editorial": EDITORIAL}

# (x, topo, largura, base, alinhamento) — em polegadas
AREAS = {
    "metade esquerda inferior": (1.00, 2.90, 5.35, PP_ALIGN.LEFT),
    "terço inferior": (1.00, 3.24, 8.30, PP_ALIGN.LEFT),
    "lateral direita": (7.35, 2.10, 4.95, PP_ALIGN.LEFT),
    "canto superior esquerdo": (1.00, 0.85, 6.10, PP_ALIGN.LEFT),
    "faixa superior": (1.00, 0.80, 8.90, PP_ALIGN.LEFT),
    "metade esquerda": (1.00, 2.42, 5.35, PP_ALIGN.LEFT),
    "metade direita": (7.35, 2.42, 4.95, PP_ALIGN.LEFT),
    "toda a moldura": (2.20, 3.30, 8.90, PP_ALIGN.CENTER),
}

def altura_texto(texto: str, pt: float, largura_in: float, entrelinha: float) -> float:
    """Estimativa conservadora da altura de um parágrafo (em polegadas)."""
    largura_caractere = pt * 0.52 / 72          # média para sem serifa
    por_linha = max(8, int(largura_in / largura_caractere))
    linhas = 0
    for paragrafo in texto.split("\n"):
        linhas += max(1, -(-len(paragrafo) // por_linha))
    return linhas * pt * entrelinha / 72 + 0.06


# Alturas de referência do bloco (polegadas), medidas para o perfil editorial.
BLOCO_COMPLETO = 4.10   # título 2 linhas + lead 3 linhas + 2 linhas de corpo
BLOCO_ENXUTO = 3.30     # título 2 linhas + lead curto + 1 linha de corpo


# --------------------------------------------------------------- helpers
def slide_preto(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    fundo = s.background.fill
    fundo.solid()
    fundo.fore_color.rgb = RGBColor(0x00, 0x00, 0x00)
    return s


def definir_fontes_tema(prs, serifa: str, sans: str) -> None:
    """Grava as fontes no tema: títulos = serifa, corpo = sem serifa.

    Com isso, Design > Variantes > Fontes troca a tipografia do deck inteiro
    de uma vez, porque todo texto aponta para +mj-lt / +mn-lt.
    """
    for part in prs.part.package.iter_parts():
        if not str(part.partname).endswith("theme/theme1.xml"):
            continue
        xml = part.blob.decode("utf-8")
        xml = re.sub(
            r'(<a:majorFont>\s*<a:latin typeface=")[^"]*(")',
            rf"\g<1>{serifa}\g<2>",
            xml,
            count=1,
        )
        xml = re.sub(
            r'(<a:minorFont>\s*<a:latin typeface=")[^"]*(")',
            rf"\g<1>{sans}\g<2>",
            xml,
            count=1,
        )
        part._blob = xml.encode("utf-8")
        return


def fonte(t: dict, papel: str) -> str:
    """Nome da fonte a gravar no run (tema ou explícita)."""
    if t["usar_tema"]:
        return "+mj-lt" if papel == "titulo" else "+mn-lt"
    return t["serifa"] if papel == "titulo" else t["sans"]


def letreamento(run, centesimos: int) -> None:
    run.font._rPr.set("spc", str(centesimos))


def caixa(slide, x, y, w, h, *, alinhamento=PP_ALIGN.LEFT, ancoragem=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = ancoragem
    tf.paragraphs[0].alignment = alinhamento
    return tb


def escrever(tf, texto, *, nome, tamanho, cor, negrito=False, italico=False,
             espaco=0, alinhamento=PP_ALIGN.LEFT, entrelinha=None, antes=0,
             primeiro=True, versalete=False):
    p = tf.paragraphs[0] if primeiro else tf.add_paragraph()
    p.alignment = alinhamento
    if entrelinha:
        p.line_spacing = entrelinha
    if antes:
        p.space_before = Pt(antes)
    run = p.add_run()
    run.text = texto
    run.font.name = nome
    run.font.size = Pt(tamanho)
    run.font.bold = negrito
    run.font.italic = italico
    run.font.color.rgb = cor
    if espaco:
        letreamento(run, espaco)
    if versalete:
        run.font._rPr.set("cap", "small")
    return p


def regua(slide, x, y, t: dict, largura=Inches(1.05), cor=None, altura=Pt(1.0)):
    barra = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, largura, altura)
    barra.fill.solid()
    barra.fill.fore_color.rgb = cor or t["latao"]
    barra.line.fill.background()
    barra.shadow.inherit = False
    return barra


def scrim(slide, x, y, w, h, angulo: int = 0, opacidade: int = 93000):
    """Retângulo preto em degradê (preto -> transparente) para apoiar o texto.

    angulo: 0 = preto à esquerda, 180 = preto à direita, 90 = preto embaixo.
    """
    forma = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    forma.line.fill.background()
    forma.shadow.inherit = False

    spPr = forma._element.spPr
    for tag in ("noFill", "solidFill", "gradFill", "pattFill"):
        for el in spPr.findall(f"{NS}{tag}"):
            spPr.remove(el)

    ns = NS.strip("{}")
    xml = (
        f'<a:gradFill xmlns:a="{ns}" rotWithShape="1"><a:gsLst>'
        f'<a:gs pos="0"><a:srgbClr val="000000"><a:alpha val="{opacidade}"/></a:srgbClr></a:gs>'
        f'<a:gs pos="45000"><a:srgbClr val="000000"><a:alpha val="72000"/></a:srgbClr></a:gs>'
        f'<a:gs pos="100000"><a:srgbClr val="000000"><a:alpha val="0"/></a:srgbClr></a:gs>'
        f'</a:gsLst><a:lin ang="{angulo * 60000}" scaled="0"/></a:gradFill>'
    )
    grad = etree.fromstring(xml)
    ln = spPr.find(f"{NS}ln")
    if ln is not None:
        ln.addprevious(grad)
    else:
        spPr.append(grad)
    return forma


def imagem_fundo(slide, caminho: Path):
    return slide.shapes.add_picture(str(caminho), Emu(0), Emu(0), width=W, height=H)


def notas(slide, texto: str) -> None:
    slide.notes_slide.notes_text_frame.text = texto


def rodape(slide, t: dict, numero: int, tema: str = "AGENTES PÚBLICOS  ·  DIREITO ADMINISTRATIVO"):
    m = Inches(t["margem"])
    esq = caixa(slide, m, H - Inches(0.58), Inches(6.2), Inches(0.24))
    escrever(esq.text_frame, tema, nome=fonte(t, "corpo"), tamanho=t["rodape_pt"],
             cor=t["grafite"], espaco=260)
    dir_ = caixa(slide, W - m - Inches(0.6), H - Inches(0.58), Inches(0.6),
                 Inches(0.24), alinhamento=PP_ALIGN.RIGHT)
    escrever(dir_.text_frame, f"{numero:02d}", nome=fonte(t, "corpo"),
             tamanho=t["rodape_pt"], cor=t["grafite"], espaco=200,
             alinhamento=PP_ALIGN.RIGHT)


# --------------------------------------------------------------- slides
def bloco_texto(slide, cena: dict, t: dict, numero: int):
    area = cena["especificacoes"]["area_livre_para_texto"]
    chave = next((k for k in AREAS if area.startswith(k)), "metade esquerda")
    x_in, topo_in, w_in, alinh = AREAS[chave]
    x, topo, w = Inches(x_in), Inches(topo_in), Inches(w_in)
    base = Inches(t["base_bloco"])
    disponivel = t["base_bloco"] - topo_in

    # 0. véu de leitura
    if chave in ("metade direita", "lateral direita"):
        scrim(slide, W - Inches(8.30), Emu(0), Inches(8.30), H, angulo=180, opacidade=t["scrim"])
    elif chave in ("terço inferior", "metade esquerda inferior", "toda a moldura"):
        scrim(slide, Emu(0), H - Inches(4.70), W, Inches(4.70), angulo=90, opacidade=t["scrim"])
    else:
        scrim(slide, Emu(0), Emu(0), Inches(8.30), H, angulo=0, opacidade=t["scrim"])

    # 1. etiqueta
    extra = "  ·  EXTRA" if cena["id"].startswith("extra") else ""
    kicker = caixa(slide, x, topo, w, Inches(0.24), alinhamento=alinh)
    escrever(kicker.text_frame, f"CENA {cena['ordem']:02d}{extra}", nome=fonte(t, "corpo"),
             tamanho=t["kicker_pt"], cor=t["latao"], espaco=t["kicker_track"],
             alinhamento=alinh)

    # 2. fio
    largura_fio = Inches(1.05)
    fx = x if alinh == PP_ALIGN.LEFT else x + (w - largura_fio) / 2
    regua(slide, fx, topo + Inches(0.38), t, largura_fio)

    # 3. título (reservado)
    completo = disponivel >= BLOCO_COMPLETO
    alto_titulo = t["titulo_alto"] if completo else 1.26
    ty = topo + Inches(0.62 if completo else 0.58)
    titulo = cena["titulo"].split(" — ")[0].replace(" (cena extra)", "")
    tb = caixa(slide, x, ty, w, Inches(alto_titulo), alinhamento=alinh)
    escrever(tb.text_frame, titulo.upper(), nome=fonte(t, "titulo"),
             tamanho=t["titulo_pt"], cor=t["marfim"], espaco=t["titulo_track"],
             entrelinha=0.96, alinhamento=alinh)

    # 4. lead — o conceito jurídico (sempre presente)
    y_lead = ty + Inches(alto_titulo) + Inches(0.16)
    lead_pt = t["lead_pt"] if completo else t["lead_pt"] - 1.5
    alto_lead = altura_texto(cena["conceito_juridico"], lead_pt, w_in, 1.40)
    # aperta o lead se ele empurrar o bloco além da base reservada
    while (y_lead + Inches(alto_lead) > base - Inches(0.20)
           and lead_pt > 11):
        lead_pt -= 0.5
        alto_lead = altura_texto(cena["conceito_juridico"], lead_pt, w_in, 1.40)

    lead = caixa(slide, x, y_lead, w, Inches(alto_lead), alinhamento=alinh)
    escrever(lead.text_frame, cena["conceito_juridico"], nome=fonte(t, "corpo"),
             tamanho=lead_pt, cor=t["cinza"], entrelinha=1.40, alinhamento=alinh)

    # 5. corpo (reservado) — só entra se houver folga real
    y_corpo = y_lead + Inches(alto_lead) + Inches(0.16)
    altura_corpo = base - y_corpo
    if altura_corpo >= Inches(0.34):
        corpo = caixa(slide, x, y_corpo, w, altura_corpo, alinhamento=alinh)
        escrever(corpo.text_frame,
                 "Corpo de texto — substitua por anotações, artigos e exemplos.",
                 nome=fonte(t, "corpo"), tamanho=t["corpo_pt"], cor=t["grafite"],
                 italico=True, entrelinha=1.35, alinhamento=alinh)

    rodape(slide, t, numero)


def capa(prs, t: dict):
    s = slide_preto(prs)
    imagem_fundo(s, PREVIEW / IMAGENS["cena-01"])
    scrim(s, Emu(0), Emu(0), Inches(8.60), H, angulo=0, opacidade=95000)

    m = Inches(t["margem"])
    kicker = caixa(s, m, Inches(1.62), Inches(6.0), Inches(0.26))
    escrever(kicker.text_frame, "DIREITO ADMINISTRATIVO", nome=fonte(t, "corpo"),
             tamanho=9, cor=t["latao"], espaco=440)

    tb = caixa(s, m, Inches(2.02), Inches(5.95), Inches(1.95))
    tf = tb.text_frame
    escrever(tf, "Agentes", nome=fonte(t, "titulo"), tamanho=t["capa_pt"],
             cor=t["marfim"], entrelinha=0.94)
    escrever(tf, "Públicos", nome=fonte(t, "titulo"), tamanho=t["capa_pt"],
             cor=t["marfim"], entrelinha=0.94, primeiro=False)

    regua(s, m, Inches(4.22), t, Inches(1.45))

    sub = caixa(s, m, Inches(4.54), Inches(5.30), Inches(1.20))
    escrever(sub.text_frame,
             "Fundamentos, regime jurídico, princípios e responsabilidade "
             "daquele que age em nome do Estado.",
             nome=fonte(t, "corpo"), tamanho=14, cor=t["cinza"], entrelinha=1.45)

    meta = caixa(s, m, H - Inches(0.95), Inches(6.4), Inches(0.5))
    tfm = meta.text_frame
    escrever(tfm, "AULA  ·  APRESENTAÇÃO  ·  2026", nome=fonte(t, "corpo"),
             tamanho=8, cor=t["grafite"], espaco=340)
    escrever(tfm, "Títulos Cambria  ·  texto Arial" if t["usar_tema"]
             else "Títulos Georgia  ·  texto Arial",
             nome=fonte(t, "corpo"), tamanho=8, cor=t["grafite"], espaco=200,
             antes=6, primeiro=False)

    notas(s, "Capa.\n\nAbra com a pergunta: quando o Estado age, quem exatamente está agindo?\n"
             "Imagem: cena-01 (monólito). Prompt completo em prompts.json.")


def roteiro(prs, t: dict, numero: int):
    s = slide_preto(prs)
    m = Inches(t["margem"])

    kicker = caixa(s, m, Inches(0.88), Inches(6.0), Inches(0.24))
    escrever(kicker.text_frame, "ROTEIRO", nome=fonte(t, "corpo"), tamanho=9,
             cor=t["latao"], espaco=440)

    tb = caixa(s, m, Inches(1.20), Inches(9.0), Inches(0.75))
    escrever(tb.text_frame, "O que será percorrido", nome=fonte(t, "titulo"),
             tamanho=32, cor=t["marfim"])

    regua(s, m, Inches(2.06), t, Inches(1.20))

    col_w = Inches(3.68)
    for i, p in enumerate(PROMPTS):
        col, linha = i // 6, i % 6
        cx = m + col * (col_w + Inches(0.62))
        cy = Inches(2.50) + linha * Inches(0.68)
        titulo = p["titulo"].split(" — ")[0].replace(" (cena extra)", "")

        n = caixa(s, cx, cy, Inches(0.5), Inches(0.26))
        escrever(n.text_frame, f"{p['ordem']:02d}", nome=fonte(t, "titulo"),
                 tamanho=11, cor=t["latao"])

        item = caixa(s, cx + Inches(0.58), cy - Inches(0.02), col_w - Inches(0.58),
                     Inches(0.5))
        escrever(item.text_frame, titulo, nome=fonte(t, "corpo"), tamanho=12,
                 cor=t["marfim"], entrelinha=1.15)

    rodape(s, t, numero)
    notas(s, "Slide de roteiro — pode ser ocultado em versões curtas.\n"
             "As cenas 11 e 12 são extras e aparecem aqui apenas como referência.")


def cena(prs, p: dict, t: dict, numero: int):
    s = slide_preto(prs)
    imagem_fundo(s, PREVIEW / IMAGENS[p["id"]])
    bloco_texto(s, p, t, numero)
    notas(s, f"{p['titulo']}\n\n"
             f"CONCEITO: {p['conceito_juridico']}\n\n"
             f"DEIXA DE FALA: {p['gancho_de_fala']}\n\n"
             f"OBJETO VISUAL: {p['objeto_visual']}\n\n"
             f"PROMPT (EN): {p['prompt']}\n\n"
             f"NEGATIVE: {p['negative_prompt']}\n\n"
             f"NOTA: {p['notas_de_uso']}")


def encerramento(prs, t: dict, numero: int):
    s = slide_preto(prs)
    imagem_fundo(s, PREVIEW / IMAGENS["extra-12"])
    scrim(s, Emu(0), Emu(0), Inches(8.70), H, angulo=0, opacidade=96000)

    m = Inches(t["margem"])
    kicker = caixa(s, m, Inches(1.92), Inches(6.0), Inches(0.24))
    escrever(kicker.text_frame, "ENCERRAMENTO", nome=fonte(t, "corpo"), tamanho=9,
             cor=t["latao"], espaco=440)

    regua(s, m, Inches(2.36), t, Inches(1.20))

    tb = caixa(s, m, Inches(2.74), Inches(7.20), Inches(1.66))
    tf = tb.text_frame
    escrever(tf, "Os agentes passam,", nome=fonte(t, "titulo"), tamanho=32,
             cor=t["marfim"], entrelinha=1.18)
    escrever(tf, "a função pública permanece.", nome=fonte(t, "titulo"), tamanho=32,
             cor=t["marfim"], entrelinha=1.18, primeiro=False)

    sub = caixa(s, m, Inches(4.78), Inches(5.20), Inches(1.30))
    tf2 = sub.text_frame
    escrever(tf2, "Obrigado.", nome=fonte(t, "titulo"), tamanho=17, cor=t["marfim"],
             espaco=80)
    escrever(tf2, "Dúvidas, comentários e indicações de leitura.",
             nome=fonte(t, "corpo"), tamanho=12, cor=t["cinza"], antes=10,
             primeiro=False)

    rodape(s, t, numero)
    notas(s, "Slide final. Imagem: extra-12 (canal de luz entre blocos).\n"
             "A cena 10 (porta entreaberta) encerra a sequência de conteúdo.")


def plancha_tipografia(prs, t: dict, numero: int):
    """Prancha de especificação: mostra a escala e o par serifa/sem serifa."""
    s = slide_preto(prs)
    m = Inches(t["margem"])

    kicker = caixa(s, m, Inches(0.72), Inches(8.0), Inches(0.24))
    escrever(kicker.text_frame, "APÊNDICE  ·  SISTEMA TIPOGRÁFICO", nome=fonte(t, "corpo"),
             tamanho=9, cor=t["latao"], espaco=380)

    # amostra serifada
    a1 = caixa(s, m, Inches(1.30), Inches(2.4), Inches(1.85))
    escrever(a1.text_frame, "Aa", nome=fonte(t, "titulo"), tamanho=100,
             cor=t["marfim"], entrelinha=1.0)

    lab1 = caixa(s, m, Inches(3.22), Inches(4.60), Inches(0.95))
    tf1 = lab1.text_frame
    escrever(tf1, f"{t['serifa'].upper()}  ·  TÍTULOS", nome=fonte(t, "corpo"),
             tamanho=9, cor=t["latao"], espaco=300)
    escrever(tf1, "Serifada de alto contraste, em caixa alta, "
                  f"{t['titulo_pt']}pt, com leve tracking positivo.",
             nome=fonte(t, "corpo"), tamanho=10.5, cor=t["cinza"], entrelinha=1.38,
             antes=8, primeiro=False)

    # amostra sem serifa
    x2 = Inches(6.85)
    a2 = caixa(s, x2, Inches(1.30), Inches(2.4), Inches(1.85))
    escrever(a2.text_frame, "Aa", nome=fonte(t, "corpo"), tamanho=100,
             cor=t["marfim"], entrelinha=1.0)

    lab2 = caixa(s, x2, Inches(3.22), Inches(4.60), Inches(0.95))
    tf2 = lab2.text_frame
    escrever(tf2, f"{t['sans'].upper()}  ·  CORPO", nome=fonte(t, "corpo"),
             tamanho=9, cor=t["latao"], espaco=300)
    escrever(tf2, "Sem serifa, neutra e legível em projeção. "
                  f"Lead {t['lead_pt']}pt, corpo {t['corpo_pt']}pt, entrelinha 1,40.",
             nome=fonte(t, "corpo"), tamanho=10.5, cor=t["cinza"], entrelinha=1.38,
             antes=8, primeiro=False)

    regua(s, m, Inches(4.42), t, Inches(11.30), cor=t["grafite"], altura=Pt(0.75))

    escala = [
        ("TÍTULO DE CENA", f"{t['titulo_pt']} pt"),
        ("LEAD / CONCEITO", f"{t['lead_pt']} pt"),
        ("CORPO", f"{t['corpo_pt']} pt"),
        ("ETIQUETA E RODAPÉ", f"{t['kicker_pt']} pt"),
    ]
    for i, (rotulo, valor) in enumerate(escala):
        y = Inches(4.72) + i * Inches(0.40)
        r = caixa(s, m, y, Inches(4.0), Inches(0.28))
        escrever(r.text_frame, rotulo, nome=fonte(t, "corpo"), tamanho=9,
                 cor=t["cinza"], espaco=240)
        v = caixa(s, m + Inches(4.30), y, Inches(1.5), Inches(0.28))
        escrever(v.text_frame, valor, nome=fonte(t, "corpo"), tamanho=9,
                 cor=t["latao"], espaco=120)

    dica = caixa(s, Inches(6.85), Inches(4.70), Inches(5.45), Inches(1.30))
    tfd = dica.text_frame
    escrever(tfd, "TROCA GLOBAL", nome=fonte(t, "corpo"), tamanho=9, cor=t["latao"],
             espaco=300)
    escrever(tfd, "Fontes gravadas no tema: em Design > Variantes > Fontes o deck "
                  "inteiro muda de uma vez.",
             nome=fonte(t, "corpo"), tamanho=10.5, cor=t["cinza"], entrelinha=1.38,
             antes=8, primeiro=False)

    rodape(s, t, numero)
    notas(s, "Prancha de especificação tipográfica. Faz parte do apêndice: "
             "oculte ou exclua antes de apresentar.")


def apendice(prs, t: dict, numero: int):
    s = slide_preto(prs)
    m = Inches(t["margem"])
    kicker = caixa(s, m, Inches(0.78), Inches(8.0), Inches(0.24))
    escrever(kicker.text_frame, "APÊNDICE  ·  REMOVER ANTES DE APRESENTAR",
             nome=fonte(t, "corpo"), tamanho=9, cor=t["latao"], espaco=320)

    tb = caixa(s, m, Inches(1.12), Inches(9.0), Inches(0.6))
    escrever(tb.text_frame, "Notas de produção", nome=fonte(t, "titulo"), tamanho=28,
             cor=t["marfim"])

    regua(s, m, Inches(1.88), t, Inches(1.10))

    itens = [
        ("Formato", "16:9. Imagens em sangria total (1376×768). Exporte em PDF para projetar."),
        ("Tipografia", f"Títulos em {t['serifa']}, corpo em {t['sans']}. Fontes no tema, troca global."),
        ("Paleta", "#000000 · #0B0B0C · #1C1C1E · #F2ECE1 · #C9A96A"),
        ("Regra de ouro", "Nenhuma imagem tem texto: todo texto é o que está nestas caixas."),
        ("Consistência", "Todas as cenas foram geradas com a mesma cauda de estilo do JSON."),
        ("Onde editar", "As notas do apresentador de cada slide trazem conceito e prompt."),
    ]
    for i, (titulo, texto) in enumerate(itens):
        y = Inches(2.32) + i * Inches(0.74)
        rot = caixa(s, m, y, Inches(2.30), Inches(0.3))
        escrever(rot.text_frame, titulo.upper(), nome=fonte(t, "corpo"), tamanho=9,
                 cor=t["latao"], espaco=240)
        val = caixa(s, m + Inches(2.55), y - Inches(0.04), Inches(8.60), Inches(0.6))
        escrever(val.text_frame, texto, nome=fonte(t, "corpo"), tamanho=11,
                 cor=t["cinza"], entrelinha=1.32)

    rodape(s, t, numero)
    notas(s, "Slide de apoio. Oculte (botão direito > Ocultar slide) ou exclua.")


def montar(t: dict) -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    if t["usar_tema"]:
        definir_fontes_tema(prs, t["serifa"], t["sans"])

    prs.core_properties.title = "Agentes Públicos — Direito Administrativo"
    prs.core_properties.subject = "Storyboard visual para aula de agentes públicos"
    prs.core_properties.author = "Storyboard"
    prs.core_properties.keywords = "direito administrativo; agentes públicos; storyboard"

    capa(prs, t)
    roteiro(prs, t, 2)
    for i, p in enumerate(PROMPTS, start=3):
        cena(prs, p, t, i)
    encerramento(prs, t, 15)
    plancha_tipografia(prs, t, 16)
    apendice(prs, t, 17)

    destino = BASE_DIR / t["arquivo"]
    prs.save(destino)
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera o deck do storyboard.")
    parser.add_argument("--perfil", choices=sorted(PERFIS), default="editorial")
    args = parser.parse_args()

    t = PERFIS[args.perfil]
    destino = montar(t)
    print(f"{destino.name}  ·  perfil {t['nome']}  ·  {t['serifa']} + {t['sans']}")


if __name__ == "__main__":
    main()
