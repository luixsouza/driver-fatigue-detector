# Artigo SOLID — Driver Fatigue Detector

Artigo técnico-científico para a disciplina de Arquitetura de Software (IFG), aplicando SOLID à arquitetura do detector de fadiga.

## Estrutura

- `artigo.tex` — documento LaTeX principal
- `sbc-template.sty` — estilo SBC (não modificar)
- `diagrams/*.puml` — fontes dos diagramas
- `diagrams/png/*.png` — diagramas renderizados (referenciados pelo .tex)
- `tools/plantuml.jar` — render de PlantUML
- `tools/render-diagrams.sh` — script para regerar todos os PNGs

## Como compilar

### Opção 1 — Overleaf (recomendado)

1. Subir `artigo.tex`, `sbc-template.sty` e a pasta `diagrams/png/` para um projeto Overleaf.
2. Definir compilador como **pdfLaTeX**.
3. Compilar. O PDF resultante deve ter no máximo 6 páginas.

### Opção 2 — Local (TeXLive ou MikTeX)

```bash
cd docs/article-solid
pdflatex artigo.tex && pdflatex artigo.tex   # duas passadas para referências
```

## Como regerar os diagramas

```bash
./tools/render-diagrams.sh
```

Requer `java` no PATH.

## Convenção de figuras

Cada `.puml` em `diagrams/` é renderizado para `diagrams/png/` com o mesmo nome base. O `.tex` referencia apenas os PNGs.
