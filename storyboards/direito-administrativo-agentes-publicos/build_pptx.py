#!/usr/bin/env python3
"""Monta o PPTX do storyboard "Agentes Públicos" a partir de prompts.json.

Cada cena vira um slide 16:9 com a imagem em sangria total e duas caixas de
texto reservadas (título + corpo), posicionadas na área livre indicada no JSON.

Uso:
    python3 -m pip install python-pptx
    python3 build_pptx.py
"""

from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

BASE = Path(__file__).parent
PREVIEW = BASE / "preview"
DATA = json.loads((BASE / "prompts.json").read_text(encoding="utf-8"))
PROMPTS = DATA["prompts"]
SAIDA = BASE / "apresentacao-agentes-publicos.pptx"

# ---------------------------------------------------------------- identidade
PRETO = RGBColor(0x00, 0x00, 0x00)
CARVAO = RGBColor(0x0B, 0x0B, 0x0C)
MARFIM = RGBColor(0xED, 0xE6, 0xDA)
LATAO = RGBColor(0xC6, 0xA6, 0x64)
CINZA = RGBColor(0x9C, 0x99, 0x93)
GRAFITE = RGBColor(0x6E, 0x6C, 0x68)

SERIFA = "Georgia"
SANS = "Arial"

W, H = Inches(13.333), Inches(7.5)
MARGEM = Inches(0.95)


# ------------------------------------------------------------------- helpers
def slide_preto(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])  # branco, em branco
    fundo = s.background.fill
    fundo.solid()
    fundo.fore_color.rgb = PRETO
    return s


def hex_rgb(hexstr: str) -> RGBColor:
    hexstr = hexstr.lstrip("#")
    return RGBColor(int(hexstr[0:2], 16), int(hexstr[2:4], 16), int(hexstr[4:6], 16))


def letreamento(run, centesimos: int) -> None:
    """Espaçamento entre letras (spc em centésimos de ponto)."""
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


def escrever(tf, texto, *, fonte, tamanho, cor, negrito=False, italico=False,
             espaco=0, alinhamento=PP_ALIGN.LEFT, entrelinha=None, primeiro=True):
    p = tf.paragraphs[0] if primeiro else tf.add_paragraph()
    p.alignment = alinhamento
    if entrelinha:
        p.line_spacing = entrelinha
    run = p.add_run()
    run.text = texto
    run.font.name = fonte
    run.font.size = Pt(tamanho)
    run.font.bold = negrito
    run.font.italic = italico
    run.font.color.rgb = cor
    if espaco:
        letreamento(run, espaco)
    return p


def regua(slide, x, y, largura=Inches(1.15), cor=LATAO, altura=Pt(1.25)):
    from pptx.enum.shapes import MSO_SHAPE

    barra = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, largura, altura)
    barra.fill.solid()
    barra.fill.fore_color.rgb = cor
    barra.line.fill.background()
    barra.shadow.inherit = False
    return barra


def imagem_fundo(slide, caminho: Path):
    pic = slide.shapes.add_picture(str(caminho), Emu(0), Emu(0), width=W, height=H)
    return pic


def scrim(slide, x, y, w, h, angulo: int = 0, opacidade: int = 94000):
    """Retângulo preto em degradê (preto -> transparente) para apoiar o texto.

    angulo: 0 = preto na esquerda, 180 = preto na direita, 90 = preto embaixo.
    """
    from lxml import etree
    from pptx.enum.shapes import MSO_SHAPE

    forma = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    forma.line.fill.background()
    forma.shadow.inherit = False

    ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    spPr = forma._element.spPr
    for tag in ("a:noFill", "a:solidFill", "a:gradFill", "a:pattFill"):
        for el in spPr.findall(f"{{{ns}}}{tag.split(':')[1]}"):
            spPr.remove(el)

    xml = (
        f'<a:gradFill xmlns:a="{ns}" rotWithShape="1"><a:gsLst>'
        f'<a:gs pos="0"><a:srgbClr val="000000"><a:alpha val="{opacidade}"/></a:srgbClr></a:gs>'
        f'<a:gs pos="45000"><a:srgbClr val="000000"><a:alpha val="70000"/></a:srgbClr></a:gs>'
        f'<a:gs pos="100000"><a:srgbClr val="000000"><a:alpha val="0"/></a:srgbClr></a:gs>'
        f'</a:gsLst><a:lin ang="{angulo * 60000}" scaled="0"/></a:gradFill>'
    )
    spPr.append(etree.fromstring(xml))
    # o gradFill precisa vir antes de a:ln
    ln = spPr.find(f"{{{ns}}}ln")
    if ln is not None:
        spPr.remove(ln)
        spPr.append(ln)
    return forma


def notas(slide, texto: str) -> None:
    slide.notes_slide.notes_text_frame.text = texto


# ----------------------------------------------------- áreas reservadas 16:9
# (x, topo do bloco, largura, base do bloco, alinhamento) — em polegadas.
# A caixa de título e a de corpo são derivadas desses limites; a base fica
# sempre acima do rodapé (6.88in) para não haver colisão.
BASE_BLOCO = 6.72
AREAS = {
    "metade esquerda inferior": (0.95, 3.52, 5.30, BASE_BLOCO, PP_ALIGN.LEFT),
    "terço inferior": (0.95, 3.92, 8.60, BASE_BLOCO, PP_ALIGN.LEFT),
    "lateral direita": (7.30, 2.20, 5.10, BASE_BLOCO, PP_ALIGN.LEFT),
    "canto superior esquerdo": (0.95, 0.85, 6.20, 4.60, PP_ALIGN.LEFT),
    "faixa superior": (0.95, 0.80, 9.20, 4.40, PP_ALIGN.LEFT),
    "metade esquerda": (0.95, 2.52, 5.45, BASE_BLOCO, PP_ALIGN.LEFT),
    "metade direita": (7.30, 2.52, 5.10, BASE_BLOCO, PP_ALIGN.LEFT),
    "toda a moldura": (2.10, 3.86, 9.15, 6.60, PP_ALIGN.CENTER),
}

ALTURA_TITULO = 1.24   # espaço reservado para até 2 linhas de título


def bloco_texto(slide, cena: dict):
    area = cena["especificacoes"]["area_livre_para_texto"]
    chave = next((k for k in AREAS if area.startswith(k)), "metade esquerda")
    x, topo, w, base, alinh = AREAS[chave]
    x, topo, w = Inches(x), Inches(topo), Inches(w)

    # 0. véu de leitura (degradê) atrás do bloco
    if chave in ("metade direita", "lateral direita"):
        scrim(slide, W - Inches(8.20), Emu(0), Inches(8.20), H, angulo=180)
    elif chave in ("terço inferior", "metade esquerda inferior", "toda a moldura"):
        scrim(slide, Emu(0), H - Inches(4.60), W, Inches(4.60), angulo=90)
    else:
        scrim(slide, Emu(0), Emu(0), Inches(8.20), H, angulo=0)

    # 1. etiqueta da cena
    kicker = caixa(slide, x, topo, w, Inches(0.28), alinhamento=alinh)
    extra = "  ·  EXTRA" if cena["id"].startswith("extra") else ""
    escrever(kicker.text_frame, f"CENA {cena['ordem']:02d}{extra}", fonte=SANS,
             tamanho=10, cor=LATAO, espaco=320, alinhamento=alinh)

    # 2. fio de latão
    largura_fio = Inches(1.15)
    fx = x if alinh == PP_ALIGN.LEFT else x + (w - largura_fio) / 2
    regua(slide, fx, topo + Inches(0.40), largura_fio)

    # 3. caixa de TÍTULO (reservada)
    ty = topo + Inches(0.62)
    tb = caixa(slide, x, ty, w, Inches(ALTURA_TITULO), alinhamento=alinh)
    titulo = cena["titulo"].split(" — ")[0].replace(" (cena extra)", "")
    escrever(tb.text_frame, titulo.upper(), fonte=SERIFA,
             tamanho=30, cor=MARFIM, espaco=120, entrelinha=0.95, alinhamento=alinh)

    # 4. caixa de CORPO (reservada) — usa toda a folga até a base do bloco
    by = ty + Inches(ALTURA_TITULO)
    bh = Inches(base) - by
    corpo = caixa(slide, x, by, w, bh, alinhamento=alinh)
    tf = corpo.text_frame
    escrever(tf, cena["conceito_juridico"], fonte=SANS, tamanho=13,
             cor=CINZA, entrelinha=1.40, alinhamento=alinh)
    escrever(tf, "Corpo de texto — substitua por anotações, artigos e exemplos.",
             fonte=SANS, tamanho=10, cor=GRAFITE, italico=True, alinhamento=alinh,
             primeiro=False)
    tf.paragraphs[1].space_before = Pt(10)

    # 5. rodapé
    rod = caixa(slide, Inches(0.95), H - Inches(0.60), Inches(6.0), Inches(0.26))
    escrever(rod.text_frame, "AGENTES PÚBLICOS  ·  DIREITO ADMINISTRATIVO",
             fonte=SANS, tamanho=8, cor=GRAFITE, espaco=260)
    num = caixa(slide, W - Inches(1.55), H - Inches(0.60), Inches(0.6), Inches(0.26),
                alinhamento=PP_ALIGN.RIGHT)
    escrever(num.text_frame, f"{cena['ordem']:02d}", fonte=SANS, tamanho=8,
             cor=GRAFITE, espaco=200, alinhamento=PP_ALIGN.RIGHT)


# --------------------------------------------------------------------- slides
def capa(prs, cena: dict):
    s = slide_preto(prs)
    imagem_fundo(s, PREVIEW / "cena-01-abertura.png")

    x = Inches(0.95)
    kicker = caixa(s, x, Inches(1.55), Inches(6.0), Inches(0.3))
    escrever(kicker.text_frame, "DIREITO ADMINISTRATIVO", fonte=SANS, tamanho=11,
             cor=LATAO, espaco=420)

    tb = caixa(s, x, Inches(2.00), Inches(5.85), Inches(1.90))
    tf = tb.text_frame
    escrever(tf, "Agentes", fonte=SERIFA, tamanho=54, cor=MARFIM, entrelinha=0.92)
    escrever(tf, "Públicos", fonte=SERIFA, tamanho=54, cor=MARFIM, entrelinha=0.92,
             primeiro=False)

    regua(s, x, Inches(4.05), Inches(1.6))

    sub = caixa(s, x, Inches(4.40), Inches(5.60), Inches(1.10))
    escrever(
        sub.text_frame,
        "Fundamentos, regime jurídico, princípios e responsabilidade "
        "daquele que age em nome do Estado.",
        fonte=SANS,
        tamanho=14,
        cor=CINZA,
        entrelinha=1.45,
    )

    ano = caixa(s, x, H - Inches(0.95), Inches(6.0), Inches(0.3))
    escrever(ano.text_frame, "AULA  ·  APRESENTAÇÃO  ·  2026", fonte=SANS,
             tamanho=9, cor=GRAFITE, espaco=300)

    notas(
        s,
        "Capa. Abra com a pergunta: quando o Estado age, quem exatamente está agindo?\n\n"
        "Imagem: cena-01 (monólito). Prompt completo em prompts.json.",
    )


def roteiro(prs):
    s = slide_preto(prs)
    x = Inches(0.95)

    kicker = caixa(s, x, Inches(0.85), Inches(6.0), Inches(0.3))
    escrever(kicker.text_frame, "ROTEIRO", fonte=SANS, tamanho=10, cor=LATAO, espaco=380)

    tb = caixa(s, x, Inches(1.22), Inches(8.0), Inches(0.8))
    escrever(tb.text_frame, "O que será percorrido", fonte=SERIFA, tamanho=32, cor=MARFIM)

    regua(s, x, Inches(2.10), Inches(1.3))

    itens = [(p["ordem"], p["titulo"].split(" — ")[0].replace(" (cena extra)", ""))
             for p in PROMPTS]
    col_w = Inches(3.75)
    for i, (num, titulo) in enumerate(itens):
        col = i // 6
        linha = i % 6
        cx = x + col * (col_w + Inches(0.55))
        cy = Inches(2.55) + linha * Inches(0.72)

        n = caixa(s, cx, cy, Inches(0.55), Inches(0.3))
        escrever(n.text_frame, f"{num:02d}", fonte=SANS, tamanho=10, cor=LATAO, espaco=180)

        t = caixa(s, cx + Inches(0.62), cy - Inches(0.04), col_w - Inches(0.62), Inches(0.5))
        escrever(t.text_frame, titulo, fonte=SANS, tamanho=12, cor=MARFIM)

    notas(
        s,
        "Slide de roteiro — pode ser ocultado se a apresentação for curta.\n"
        "As cenas 11 e 12 são extras e não aparecem aqui.",
    )


def cena(prs, p: dict):
    s = slide_preto(prs)
    arquivo = PREVIEW / {
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
    }[p["id"]]
    imagem_fundo(s, arquivo)
    bloco_texto(s, p)

    notas(
        s,
        f"{p['titulo']}\n\n"
        f"CONCEITO: {p['conceito_juridico']}\n\n"
        f"DEIXA DE FALA: {p['gancho_de_fala']}\n\n"
        f"OBJETO VISUAL: {p['objeto_visual']}\n\n"
        f"PROMPT (EN): {p['prompt']}\n\n"
        f"NEGATIVE: {p['negative_prompt']}\n\n"
        f"NOTA: {p['notas_de_uso']}",
    )


def encerramento(prs):
    s = slide_preto(prs)
    imagem_fundo(s, PREVIEW / "extra-12-continuidade.png")
    scrim(s, Emu(0), Emu(0), Inches(8.60), H, angulo=0, opacidade=97000)

    x = Inches(0.95)
    kicker = caixa(s, x, Inches(1.95), Inches(6.0), Inches(0.3))
    escrever(kicker.text_frame, "ENCERRAMENTO", fonte=SANS, tamanho=10, cor=LATAO,
             espaco=380)

    regua(s, x, Inches(2.42), Inches(1.3))

    tb = caixa(s, x, Inches(2.82), Inches(7.30), Inches(1.55))
    tf = tb.text_frame
    escrever(tf, "Os agentes passam,", fonte=SERIFA, tamanho=32, cor=MARFIM,
             entrelinha=1.18)
    escrever(tf, "a função pública permanece.", fonte=SERIFA, tamanho=32, cor=MARFIM,
             entrelinha=1.18, primeiro=False)

    sub = caixa(s, x, Inches(4.86), Inches(5.40), Inches(1.30))
    tf2 = sub.text_frame
    escrever(tf2, "Obrigado.", fonte=SANS, tamanho=15, cor=MARFIM, espaco=120)
    escrever(tf2, "Dúvidas, comentários e indicações de leitura.", fonte=SANS,
             tamanho=12, cor=CINZA, primeiro=False)
    tf2.paragraphs[1].space_before = Pt(10)

    notas(s, "Slide final. Imagem: extra-12 (canal de luz entre blocos).\n"
             "A cena 10 (porta entreaberta) encerra a sequência de conteúdo.")


def apendice(prs):
    s = slide_preto(prs)
    x = Inches(0.95)
    kicker = caixa(s, x, Inches(0.80), Inches(8.0), Inches(0.3))
    escrever(kicker.text_frame, "APÊNDICE  ·  REMOVER ANTES DE APRESENTAR", fonte=SANS,
             tamanho=9, cor=LATAO, espaco=300)

    tb = caixa(s, x, Inches(1.15), Inches(9.0), Inches(0.6))
    escrever(tb.text_frame, "Notas de produção", fonte=SERIFA, tamanho=26, cor=MARFIM)

    regua(s, x, Inches(1.95), Inches(1.2))

    itens = [
        ("Formato", "16:9, imagens em 1376×768 (sangria total). Exporte em PDF para projetar."),
        ("Tipografia", f"Títulos em {SERIFA}, corpo em {SANS}. Substitua no PowerPoint se quiser."),
        ("Paleta", "#000000 · #0B0B0C · #1C1C1E · #EDE6DA · #C6A664"),
        ("Regra de ouro", "Nenhuma imagem tem texto: todo texto é o que está nestas caixas."),
        ("Repetição", "Toda cena foi gerada com a mesma cauda de estilo de prompts.json."),
        ("Onde editar", "As notas do apresentador de cada slide trazem o prompt completo."),
    ]
    for i, (titulo, texto) in enumerate(itens):
        y = Inches(2.40) + i * Inches(0.78)
        t = caixa(s, x, y, Inches(2.30), Inches(0.4))
        escrever(t.text_frame, titulo.upper(), fonte=SANS, tamanho=9, cor=LATAO, espaco=200)
        c = caixa(s, x + Inches(2.55), y - Inches(0.05), Inches(8.60), Inches(0.6))
        escrever(c.text_frame, texto, fonte=SANS, tamanho=12, cor=CINZA, entrelinha=1.3)

    notas(s, "Slide de apoio. Oculte (botão direito > Ocultar slide) ou exclua.")


def main() -> None:
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H

    capa(prs, PROMPTS[0])
    roteiro(prs)
    for p in PROMPTS:
        cena(prs, p)
    encerramento(prs)
    apendice(prs)

    prs.save(SAIDA)
    print(f"{SAIDA.name}: {len(prs.slides._sldIdLst)} slides")


if __name__ == "__main__":
    main()
