#!/usr/bin/env python3
"""Gera o storyboard em Markdown a partir de prompts.json.

Uso:
    python3 build_storyboard.py

Fonte única de verdade: prompts.json. Edite lá e rode de novo.
"""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).parent
DATA = json.loads((BASE / "prompts.json").read_text(encoding="utf-8"))
PROMPTS = DATA["prompts"]
ESTILO = DATA["diretriz_visual"]

CABECALHO = f"""# Storyboard — Direito Administrativo: Agentes Públicos

**Formato:** {DATA["formato"]} · **Versão:** {DATA["versao"]}
**Direção de arte:** minimalista profissional, fundo preto dominante, zero texto na imagem.

Uma sequência pensada para ser projetada em slides 16:9 durante uma aula expositiva.
Cada cena é um objeto visual único, isolado no escuro, que **traduz um instituto jurídico
sem literalidade e sem palavras** — o texto do slide entra por cima, na edição.

---

## 1. Linguagem visual (regras que valem para todas as cenas)

| Elemento | Definição |
|---|---|
| Fundo | {ESTILO["fundo"]} |
| Paleta | `{"` · `".join(ESTILO["paleta"])}` |
| Luz | {ESTILO["luz"]} |
| Materiais | {ESTILO["materiais"]} |
| Acabamento | {ESTILO["acabamento"]} |
| Regra absoluta | {ESTILO["regra_absoluta"]} |
| Composição | {ESTILO["composicao"]} |

**Cauda de estilo** (cole no fim de qualquer prompt para manter a unidade da série):

> {ESTILO["cauda_de_estilo"]}

**Por que preto e sem texto:** o fundo preto elimina ruído e mantém o foco na ideia;
a ausência de texto evita conflito tipográfico com a fala do professor e permite
reaproveitar a mesma imagem em qualquer idioma ou versão do material.

---

## 2. Roteiro da sequência

| # | Cena | Conceito jurídico | Objeto visual | Tela | Transição |
|---|---|---|---|---|---|
"""


def tabela() -> str:
    linhas = []
    for p in PROMPTS:
        linhas.append(
            "| {o} | **{t}** | {c} | {v} | {d}s | {tr} |".format(
                o=p["ordem"],
                t=p["titulo"],
                c=p["conceito_juridico"],
                v=p["objeto_visual"],
                d=p["duracao_em_tela_s"],
                tr=p["transicao"],
            )
        )
    total = sum(p["duracao_em_tela_s"] for p in PROMPTS[:10])
    linhas.append("")
    linhas.append(
        f"Sequência principal (cenas 1 a 10): **{total} segundos** de imagem em tela. "
        "As cenas 11 e 12 são extras, para encaixar conforme o recorte da aula."
    )
    return "\n".join(linhas)


PREVIAS = """
### Prévias de direção de arte

Três cenas foram geradas como teste da linguagem visual (as demais seguem exatamente
a mesma receita de luz, paleta e lente).

| Cena 01 | Cena 02 | Cena 06 |
|---|---|---|
| ![Abertura](preview/cena-01-abertura.png) | ![Teoria do órgão](preview/cena-02-teoria-do-orgao.png) | ![Impessoalidade](preview/cena-06-impessoalidade.png) |
"""


def bloco(p: dict) -> str:
    spec = p["especificacoes"]
    return f"""### {p["ordem"]:02d}. {p["titulo"]}

- **Conceito:** {p["conceito_juridico"]}
- **Objeto visual:** {p["objeto_visual"]}
- **Deixa de fala:** {p["gancho_de_fala"]}
- **Especificação:** {spec["proporcao"]} · {spec["resolucao"]} · {spec["formato"]} · área livre para texto: {spec["area_livre_para_texto"]}
- **Tela / transição:** {p["duracao_em_tela_s"]}s · {p["transicao"]}
- **Nota de uso:** {p["notas_de_uso"]}

```json
{json.dumps(p, ensure_ascii=False, indent=2)}
```
"""


RODAPE = """
---

## 4. Como gerar (passo a passo)

1. **Escolha o modelo** e cole o campo `prompt` da cena (não o JSON inteiro).
2. **Mantenha a receita fixa** entre as cenas: mesmo modelo, mesma versão, mesmo
   `seed` quando a ferramenta permitir (Midjourney: `--seed 1234`; Flux/SD: seed fixa).
   Consistência de série vem mais do *seed + paleta + lente* do que do assunto.
3. **Gere em 16:9 nativo** (1920×1088 ou maior). Não gere quadrado e corte depois:
   o enquadramento com muito espaço negativo se perde no recorte.
4. **Aplique o `negative_prompt`** sempre. Texto fantasma e marca d'água são os
   defeitos mais comuns neste tipo de imagem.
5. **Descarte e regenere** qualquer quadro com: letras/números legíveis, rosto
   reconhecível, fundo cinza ou branco, mais de uma fonte de luz, saturação colorida.
6. **Pós-produção mínima:** puxe o preto para `#000` puro (curvas), reduza a saturação
   global exceto no latão, adicione grão fino se o modelo entregar imagem "plástica".

### Consistência entre cenas

- Todas as cenas usam a mesma altura de horizonte e o mesmo tipo de lente (35mm).
- O latão (`#C6A664`) aparece em **no máximo 5% do quadro** — é acento, não cor.
- Nenhuma cena tem mais de um objeto protagonista.
- Reserve a área indicada em `area_livre_para_texto` para o título do slide.

### Checklist antes de fechar o deck

- [ ] 10 cenas geradas em 16:9, todas com fundo preto dominante
- [ ] Zero texto, letra, número, logo ou marca d'água em qualquer quadro
- [ ] Paleta unificada (preto + marfim + um fio de latão)
- [ ] Ordem narrativa: abstração → vínculo → princípios → responsabilidade → permanência
- [ ] Exportação em PNG (ou WebP de alta qualidade) para preservar o preto chapado
- [ ] Teste em projetor: a aresta/feixe de luz de cada cena precisa sobreviver ao contraste ruim

### Arquivos deste pacote

| Arquivo | Conteúdo |
|---|---|
| `prompts.json` | 12 prompts em JSON estruturado, prontos para consumo por script |
| `storyboard.md` | Este documento (gerado a partir do JSON) |
| `build_storyboard.py` | Script que regenera o Markdown a partir do JSON |
| `preview/` | Prévias geradas das cenas 01, 02 e 06 para validar a direção de arte |
"""


def main() -> None:
    partes = [CABECALHO.rstrip("\n"), tabela(), PREVIAS, "\n---\n\n## 3. Prompts em JSON\n"]
    partes.append(
        "Cada objeto abaixo é autossuficiente: pode ser copiado isoladamente para um\n"
        "pipeline, uma API ou uma planilha de produção. O campo `prompt` é o texto que\n"
        "vai para o modelo; os demais campos são metadados de direção e de roteiro.\n"
    )
    for p in PROMPTS:
        partes.append(bloco(p))
    partes.append(RODAPE)
    (BASE / "storyboard.md").write_text("\n".join(partes), encoding="utf-8")
    print(f"storyboard.md gerado com {len(PROMPTS)} cenas.")


if __name__ == "__main__":
    main()
