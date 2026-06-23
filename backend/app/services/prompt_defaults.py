from __future__ import annotations

DEFAULT_CV_PROMPT: str = """\
baseado nesse arquivo em anexo, crie um curriculum pra mim para esta vaga com o design abaixo:
VAGA:
{JOB_DESCRIPTION}
DESIGN:

## Contexto
Crie um currículum em HTML single-file, otimizado para impressão em A4, com design moderno em duas colunas. O arquivo deve ser autossuficiente (sem dependências externas exceto a fonte via CSS), pronto para abrir no navegador e imprimir/salvar como PDF via Ctrl+P.

---

## Layout Geral

- **Formato:** Página única A4 (`@page { size: A4; margin: 0; }`)
- **Estrutura:** div `.cv-wrap` com:
  1. Header superior (`div.cv-header`) — largura total
  2. Body (`div.cv-body`) com duas colunas lado a lado:
     - **Sidebar esquerda** (`div.sidebar`) — 32% da largura
     - **Coluna principal** (`div.main-col`) — 68% da largura
- **Fonte base:** Arial, sans-serif; `font-size: 9pt`
- **Sem margens** no body (`margin: 0; padding: 0`)
- **Background do body:** `#F0F4FC` (azul muito claro) — transparente no print

```css
@page { size: A4; margin: 0; }
body { font-family: Arial, sans-serif; font-size: 9pt; background: #F0F4FC; color: #1A2332; margin: 0; padding: 0; }
.cv-wrap { width: 210mm; min-height: 297mm; margin: 0 auto; background: #fff; }
.cv-body { display: flex; }
.sidebar { width: 32%; background: #F0F4FC; padding: 16px 14px; border-right: 2px solid #C3D4EF; }
.main-col { width: 68%; padding: 16px 18px; }
```

---

## Header (.cv-header)

- **Background:** `#1E4D9E`
- **Cor do texto:** `#fff`
- **Padding:** `18px 20px 14px`
- **Posição relativa** para conter o SVG decorativo
- Contém: `.cv-name` (18pt, 800), `.cv-role` (10pt, opacity 0.9), `.cv-contacts` (flex, gap 14px, 8pt)

```html
<div class="cv-header" style="position:relative;background:#1E4D9E;color:#fff;padding:18px 20px 14px;">
  <svg xmlns="http://www.w3.org/2000/svg" class="no-print"
    style="position:absolute;top:0;right:0;width:380px;height:110px;pointer-events:none;overflow:visible;"
    viewBox="0 0 380 110">
    <defs>
      <pattern id="dp" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
        <circle cx="2" cy="2" r="1.1" fill="rgba(255,255,255,0.22)"/>
      </pattern>
    </defs>
    <rect x="60" y="-5" width="320" height="120" fill="url(#dp)"/>
    <circle cx="330" cy="18" r="65" fill="rgba(147,197,253,0.07)"/>
    <circle cx="365" cy="85" r="48" fill="rgba(147,197,253,0.06)"/>
    <line x1="380" y1="0" x2="255" y2="110" stroke="rgba(255,255,255,0.07)" stroke-width="1.5"/>
  </svg>
  <div class="cv-name" style="font-size:18pt;font-weight:800;">{{NOME}}</div>
  <div class="cv-role" style="font-size:10pt;opacity:0.9;margin-top:3px;">{{CARGO}}</div>
  <div class="cv-contacts" style="display:flex;flex-wrap:wrap;gap:14px;font-size:8pt;margin-top:10px;">
    <span>{{CIDADE}}, {{PAÍS}}</span>
    <span>{{TELEFONE}}</span>
    <span><a href="mailto:{{EMAIL}}" style="color:rgba(255,255,255,0.85);text-decoration:none;">{{EMAIL}}</a></span>
    <span><a href="{{LINKEDIN}}" style="color:rgba(255,255,255,0.85);text-decoration:none;">{{LINKEDIN_DISPLAY}}</a></span>
  </div>
</div>
```

```css
@media print { .no-print { display: none !important; } }
```

---

## Sidebar

```css
.sec { font-size:8.5pt;font-weight:800;text-transform:uppercase;letter-spacing:0.8px;color:#1E4D9E;border-bottom:2px solid #1E4D9E;padding-bottom:3px;margin:14px 0 8px; }
.sec:first-child { margin-top:0; }
.chip-lbl { font-size:7pt;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#4A5568;margin:6px 0 3px; }
.chips { display:flex;flex-wrap:wrap;gap:3px;margin-bottom:4px; }
.chip { padding:2px 7px;border-radius:10px;font-size:7pt;font-weight:700;border:1px solid;display:inline-block; }
.c-b { background:#DBEAFE;color:#1E40AF;border-color:#93C5FD; }
.c-g { background:#D1FAE5;color:#065F46;border-color:#6EE7B7; }
.c-a { background:#FEF3C7;color:#92400E;border-color:#FCD34D; }
.c-p { background:#EDE9F8;color:#6B21A8;border-color:#C4B5FD; }
.c-s { background:#F1F5F9;color:#475569;border-color:#CBD5E1; }
.cert { margin-bottom:7px; }
.cert strong { font-size:8pt;display:block;color:#1A2332;line-height:1.3; }
.cert .m { font-size:7pt;color:#718096;display:block; }
.cert .ip { font-size:7pt;color:#7A5500;font-weight:700; }
.edu { margin-bottom:8px; }
.edu strong { font-size:8pt;display:block;color:#1A2332; }
.edu .m { font-size:7pt;color:#718096;display:block; }
.lang { margin-bottom:8px; }
.lang-n { font-size:8pt;font-weight:700; }
.lang-l { font-size:7pt;color:#718096;margin-bottom:3px; }
.bar { height:5px;background:#E2E8F0;border-radius:3px;overflow:hidden; }
.bf { height:100%;border-radius:3px;background:linear-gradient(to right,#1E4D9E,#60A5FA); }
```

Larguras de barra de idioma: Nativo=100%, C1=90%, B2=72%, B1=52%, A2=22%, A1=10%

---

## Coluna Principal

```css
.sum-p { font-size:8.5pt;line-height:1.65;color:#1A2332;margin-bottom:4px;border-left:3px solid #1E4D9E;padding-left:10px; }
.job { margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid #C3D4EF; }
.job:last-child { border-bottom:none;margin-bottom:0; }
.jt { display:flex;justify-content:space-between;align-items:flex-start;gap:6px; }
.jtl { font-size:9.5pt;font-weight:700;color:#1A2332; }
.jpr { font-size:7.5pt;font-weight:700;white-space:nowrap;background:#EBF1FB;color:#1E4D9E;padding:1px 8px;border-radius:10px;border:1px solid #C3D4EF; }
.jco { font-size:8.5pt;font-weight:600;color:#1E4D9E;margin:2px 0; }
.jtg { font-size:7pt;color:#718096;font-style:italic;margin-bottom:6px;line-height:1.4; }
.b { padding-left:14px; }
.b li { margin-bottom:4px;font-size:8.5pt;line-height:1.5; }
.b li strong { color:#163d80; }
```

Bullets usam fórmula XYZ do Google: "[Verbo] [Métrica de impacto] ao [tecnologia] — [contexto/resultado]"

---

## Paleta

| Token | Valor | Uso |
|-------|-------|-----|
| primary | #1E4D9E | headers, links, bordas |
| primary-dark | #163d80 | hover, texto forte |
| bg-light | #EBF1FB | badges, sidebar bg |
| border | #C3D4EF | bordas gerais |
| text | #1A2332 | texto principal |
| gray | #718096 | metadados |

RESTRIÇÕES:
1. HTML APENAS, SEM TEXTO EXTRA, SEM EXPLICAÇÕES.
2. FORMATADO PARA IMPRESSÃO, APENAS UMA PÁGINA, SEM RECORTE.
3. TODO O TEXTO EM INGLÊS, SEM PORTUGUÊS OU OUTRA LÍNGUA.
4. CAMPO PROFESSIONAL SUMMARY DEVE SER RELACIONADO E DIRECIONADO À VAGA EM QUESTÃO, COMO UMA MINI CARTA DE APRESENTAÇÃO DO PORQUE O CANDIDATO É BOM.
5. CAMPO SKILLS DEVEM FAZER SENTIDO COM A VAGA, APONTANDO AS SKILLS QUE O CANDIDATO TEM QUE SÃO EXIGIDAS PARA A VAGA.\
"""

DEFAULT_CL_PROMPT: str = """\
baseado nesse arquivo em anexo, crie uma carta de apresentação para esta vaga com o design abaixo:
VAGA:
{JOB_DESCRIPTION}
DESIGN:

## Contexto
Crie uma carta de apresentação em HTML single-file, otimizada para impressão em A4. O arquivo deve ser autossuficiente, pronto para abrir no navegador e imprimir/salvar como PDF via Ctrl+P.

---

## Layout

- **Formato:** Página única A4 (`@page { size: A4; margin: 0; }`)
- **Estrutura:** div `.cv-wrap` com:
  1. Header superior (`div.cv-header`) — IDÊNTICO ao do currículo (mesmo CSS, mesmo SVG decorativo)
  2. Body (`div.cl-body`) — largura total, sem colunas

```css
@page { size: A4; margin: 0; }
body { font-family: Arial, sans-serif; font-size: 9pt; background: #F0F4FC; color: #1A2332; margin: 0; padding: 0; }
.cv-wrap { width: 210mm; min-height: 297mm; margin: 0 auto; background: #fff; }
.cv-header { position: relative; background: #1E4D9E; color: #fff; padding: 18px 20px 14px; }
.cv-name { font-size: 18pt; font-weight: 800; }
.cv-role { font-size: 10pt; opacity: 0.9; margin-top: 3px; }
.cv-contacts { display: flex; flex-wrap: wrap; gap: 14px; font-size: 8pt; margin-top: 10px; }
.cv-contacts a { color: rgba(255,255,255,0.85); text-decoration: none; }
.cl-body { padding: 28px 32px; }
.cl-p { font-size: 9.5pt; line-height: 1.7; color: #1A2332; margin-bottom: 12px; }
.cl-salutation { font-size: 9.5pt; font-weight: 700; color: #1A2332; margin-bottom: 16px; }
.cl-closing { margin-top: 24px; font-size: 9.5pt; color: #1A2332; }
@media print { .no-print { display: none !important; } }
```

## Header (mesmo SVG decorativo do currículo)

```html
<div class="cv-header">
  <svg xmlns="http://www.w3.org/2000/svg" class="no-print"
    style="position:absolute;top:0;right:0;width:380px;height:110px;pointer-events:none;overflow:visible;"
    viewBox="0 0 380 110">
    <defs>
      <pattern id="dp" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
        <circle cx="2" cy="2" r="1.1" fill="rgba(255,255,255,0.22)"/>
      </pattern>
    </defs>
    <rect x="60" y="-5" width="320" height="120" fill="url(#dp)"/>
    <circle cx="330" cy="18" r="65" fill="rgba(147,197,253,0.07)"/>
    <circle cx="365" cy="85" r="48" fill="rgba(147,197,253,0.06)"/>
    <line x1="380" y1="0" x2="255" y2="110" stroke="rgba(255,255,255,0.07)" stroke-width="1.5"/>
  </svg>
  <div class="cv-name">{{NOME}}</div>
  <div class="cv-role">{{CARGO}}</div>
  <div class="cv-contacts">
    <span>{{CIDADE}}, {{PAÍS}}</span>
    <span><a href="mailto:{{EMAIL}}">{{EMAIL}}</a></span>
    <span><a href="{{LINKEDIN}}">{{LINKEDIN_DISPLAY}}</a></span>
  </div>
</div>
```

## Body (abaixo do header — sem colunas)

```html
<div class="cl-body">
  <div class="cl-salutation">Dear Hiring Manager,</div>
  <p class="cl-p">{{PARÁGRAFO 1 — introdução e fit com a vaga}}</p>
  <p class="cl-p">{{PARÁGRAFO 2 — conquista relevante com métrica}}</p>
  <p class="cl-p">{{PARÁGRAFO 3 — por que esta empresa/vaga}}</p>
  <div class="cl-closing">
    Best regards,<br/>
    <strong>{{NOME}}</strong>
  </div>
</div>
```

RESTRIÇÕES:
1. HTML APENAS, SEM TEXTO EXTRA, SEM EXPLICAÇÕES.
2. FORMATADO PARA IMPRESSÃO, APENAS UMA PÁGINA, SEM RECORTE.
3. TODO O TEXTO EM INGLÊS, SEM PORTUGUÊS OU OUTRA LÍNGUA.
4. CARTA DEVE SER RELACIONADA E DIRECIONADA À VAGA, DESTACANDO PORQUE O CANDIDATO É BOM PARA ELA.
5. USE AS CONQUISTAS DO CANDIDATO COM MÉTRICAS CONCRETAS NO CORPO DA CARTA.\
"""
