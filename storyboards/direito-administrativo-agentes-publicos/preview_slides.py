#!/usr/bin/env python3
"""Renderiza PNGs aproximados de cada slide do PPTX, para conferência rápida.

Não substitui o PowerPoint: é um rasterizador simples que desenha imagens,
gradientes e caixas de texto nas posições reais dos shapes. As fontes usadas
aqui são DejaVu (Georgia/Arial podem não existir na máquina), então o
resultado serve para checar encaixe e hierarquia, não tipografia final.

Uso:
    python3 -m pip install python-pptx pillow
    python3 preview_slides.py
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation

BASE = Path(__file__).parent
SAIDA = BASE / "preview" / "slides"
NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
EMU_IN = 914400
DPI = 96

FONTES = {
    "serifa": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "sans_bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
}


def px(valor) -> int:
    return int(valor / EMU_IN * DPI)


def quebrar(draw, texto: str, fonte, largura: int) -> list[str]:
    linhas, atual = [], ""
    for palavra in texto.split():
        tentativa = f"{atual} {palavra}".strip()
        if draw.textlength(tentativa, font=fonte) <= largura or not atual:
            atual = tentativa
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def alfa_do_gradiente(grad, posicao: float) -> float:
    """Interpola a opacidade de um gradFill do DrawingML em uma posição 0-100."""
    pontos = [
        (int(gs.get("pos")) / 1000, int(gs.find(f".//{NS}alpha").get("val")) / 100000)
        for gs in grad.findall(f".//{NS}gs")
    ]
    if posicao <= pontos[0][0]:
        return pontos[0][1]
    if posicao >= pontos[-1][0]:
        return pontos[-1][1]
    for (p0, a0), (p1, a1) in zip(pontos, pontos[1:]):
        if p0 <= posicao <= p1:
            fator = (posicao - p0) / (p1 - p0) if p1 > p0 else 0
            return a0 + (a1 - a0) * fator
    return 0.0


def pintar_scrim(canvas, forma, caixa) -> None:
    grad = forma._element.find(f".//{NS}gradFill")
    x0, y0, x1, y1 = caixa
    largura, altura = max(1, x1 - x0), max(1, y1 - y0)
    angulo = int(grad.find(f"{NS}lin").get("ang")) // 60000

    mascara = Image.new("L", (largura, altura), 0)
    desenho = ImageDraw.Draw(mascara)
    comprimento = altura if angulo in (90, 270) else largura
    for i in range(comprimento):
        t = i / max(1, comprimento - 1) * 100
        if angulo in (180, 270):
            t = 100 - t
        alfa = int(alfa_do_gradiente(grad, t) * 255)
        if angulo in (90, 270):
            desenho.line([(0, altura - 1 - i), (largura, altura - 1 - i)], fill=alfa)
        else:
            desenho.line([(i, 0), (i, altura)], fill=alfa)
    canvas.paste(Image.new("RGB", (largura, altura), (0, 0, 0)), (x0, y0), mascara)


def pintar_texto(canvas, forma, caixa) -> None:
    x0, y0, x1, _ = caixa
    largura = max(1, x1 - x0)
    desenho = ImageDraw.Draw(canvas)
    y = y0
    for paragrafo in forma.text_frame.paragraphs:
        if not paragrafo.runs:
            continue
        run = paragrafo.runs[0]
        tamanho = run.font.size.pt if run.font.size else 12
        pixels = int(tamanho * DPI / 72)
        chave = "serifa" if "Georgia" in (run.font.name or "") else (
            "sans_bold" if run.font.bold else "sans"
        )
        fonte = ImageFont.truetype(FONTES[chave], pixels)
        cor = tuple(run.font.color.rgb) if run.font.color and run.font.color.rgb else (255, 255, 255)
        texto = "".join(r.text for r in paragrafo.runs)
        for linha in quebrar(desenho, texto, fonte, largura):
            desenho.text((x0, y), linha, font=fonte, fill=cor)
            y += int(pixels * (paragrafo.line_spacing or 1.2))


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    prs = Presentation(str(BASE / "apresentacao-agentes-publicos.pptx"))

    for indice, slide in enumerate(prs.slides, start=1):
        largura, altura = px(prs.slide_width), px(prs.slide_height)
        canvas = Image.new("RGB", (largura, altura), (0, 0, 0))

        for forma in slide.shapes:
            caixa = (
                px(forma.left),
                px(forma.top),
                px(forma.left + forma.width),
                px(forma.top + forma.height),
            )
            tamanho = (max(1, caixa[2] - caixa[0]), max(1, caixa[3] - caixa[1]))

            if forma.shape_type == 13:  # imagem
                img = Image.open(io.BytesIO(forma.image.blob)).convert("RGB")
                canvas.paste(img.resize(tamanho), (caixa[0], caixa[1]))
            elif forma._element.find(f".//{NS}gradFill") is not None:
                pintar_scrim(canvas, forma, caixa)
            elif forma.has_text_frame and forma.text_frame.text.strip():
                pintar_texto(canvas, forma, caixa)

        canvas.save(SAIDA / f"slide-{indice:02d}.png")

    print(f"{indice} prévias em {SAIDA.relative_to(BASE)}/")


if __name__ == "__main__":
    main()
