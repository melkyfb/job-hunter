# NeuGlass Design System — Spec

> **Escopo:** Design system incremental — tokens + utility inline styles. PoC na ProfilePage. Expansão posterior para outras páginas.

**Goal:** Interface híbrida Neumorphism + Glassmorphism com física de luz coerente, sem dependências novas, aplicada progressivamente ao app.

**Stack:** React 19 + Vite, CSS custom properties em `index.css`, inline styles nos componentes (padrão atual mantido).

**Modo:** Light mode apenas. Dark mode existente (`data-theme="dark"`) não recebe o tratamento NeuGlass nesta iteração.

---

## 1. Física Visual — Arquitetura de Camadas

### O Problema de Compatibilidade

Neumorfismo e Glassmorfismo têm premissas físicas opostas que se conflitam se sobrepostos incorretamente:

- **Neumorfismo**: elemento compartilha exatamente a cor do fundo; sombras duplas (clara + escura) criam ilusão de extrusão/afundamento. O elemento É a superfície.
- **Glassmorfismo**: elemento flutua ACIMA de conteúdo, desfoca o que está atrás com `backdrop-filter`. Precisa de variação visual atrás para o blur mostrar algo.

**Conflito:** Glass sobre superfície neumórfica (monocromática) desfoca cinza uniforme — efeito morto.

### Solução: Background Ativo como Mediador

O gradiente de fundo serve simultaneamente como:
1. Canvas sobre o qual os painéis neumórficos são extrudados
2. Conteúdo que os elementos glass desfocam

```
z-0    Background (--blue-gradient)
       linear-gradient(135deg, #dde4f0 → #c8d8ee → #d5dff0)
       O que o glass desfoca. Precisa ter variação.

z-10   Painéis Neumórficos (--neumo-bg = #dde4f0)
       Mesma cor base do gradiente → parecem extrudados dele.
       Todos OPACOS. Cards, sections, headers.

z-20   Conteúdo interno dos painéis
       Texto, chips, botões internos, ícones.

z-50   Elementos Glass
       Flutuam sobre áreas NUAs do background (não sobre painéis neumo).
       ActionBar sticky = flutua sobre gradiente ao scrollar.

z-100  Modais / Drawers glass (iteração futura)
```

**Regra de ouro:** Elemento glass nunca deve ter painel neumórfico opaco como único background. Posicionar glass onde o gradiente seja visível atrás.

---

## 2. Design Tokens

Adicionar ao bloco `:root` em `frontend/src/index.css`:

```css
/* ── NeuGlass: Base neumórfica ───────────────────────────────── */
--neumo-bg:           #dde4f0;
--neumo-shadow-dark:  rgba(163, 177, 198, 0.65);
--neumo-shadow-light: rgba(255, 255, 255, 0.85);

--neumo-raised:
  8px 8px 20px var(--neumo-shadow-dark),
  -8px -8px 20px var(--neumo-shadow-light);

--neumo-raised-sm:
  4px 4px 12px var(--neumo-shadow-dark),
  -4px -4px 12px var(--neumo-shadow-light);

--neumo-inset:
  inset 5px 5px 12px var(--neumo-shadow-dark),
  inset -5px -5px 12px var(--neumo-shadow-light);

--neumo-pressed:
  inset 3px 3px 8px var(--neumo-shadow-dark),
  inset -3px -3px 8px var(--neumo-shadow-light);

/* ── NeuGlass: Glassmorphism ─────────────────────────────────── */
--glass-bg:      rgba(255, 255, 255, 0.18);
--glass-border:  rgba(255, 255, 255, 0.35);
--glass-blur:    blur(14px) saturate(180%);
--glass-shadow:  0 8px 32px rgba(30, 77, 158, 0.12);

/* ── NeuGlass: Paleta azul ───────────────────────────────────── */
--blue-primary:   #1E4D9E;
--blue-medium:    #3d6cbf;
--blue-light:     #EBF1FB;
--blue-border:    #C3D4EF;
--blue-gradient:  linear-gradient(135deg, #dde4f0 0%, #c8d8ee 55%, #d5dff0 100%);

/* ── NeuGlass: Texto sobre fundo neumo ──────────────────────── */
--neumo-text:    #2d3a52;
--neumo-text-s:  #5a6a82;
```

### Justificativas dos Valores

| Token | Valor | Razão |
|-------|-------|-------|
| `--neumo-bg` | `#dde4f0` | Mid-tone azul-acinzentado. Diferença de luminosidade entre as sombras ~15% — suficiente para ilusão, mantém contraste de texto |
| `--neumo-shadow-dark` | `rgba(163,177,198,0.65)` | Derivado do `--neumo-bg` saturado + escurecido; coerente com iluminação de cima-esquerda |
| `--neumo-shadow-light` | `rgba(255,255,255,0.85)` | Branco com leve transparência para não "estourar" em telas com gamut amplo |
| `blur(14px)` | — | Ponto ótimo perf/visual. Acima de 20px degrada em mobile; abaixo de 8px o efeito some |
| `saturate(180%)` | — | Amplifica as cores do gradiente atrás do vidro sem necessitar de tint colorido |
| `rgba(30,77,158,0.12)` | `--glass-shadow` | `--blue-primary` com baixa opacidade — sombra coerente com a paleta |

### Performance: `backdrop-filter`

`backdrop-filter` força criação de stacking context e composite layer. Para evitar jank:

1. Adicionar `will-change: transform` no elemento glass (via inline style) — sinaliza ao browser para criar GPU layer antecipadamente
2. Nunca animar `backdrop-filter` diretamente — animar `opacity` do elemento em vez disso
3. Limite: máximo 3-4 elementos com `backdrop-filter` ativos simultaneamente na viewport

---

## 3. Mapa de Componentes — ProfilePage

```
ProfilePage (background: var(--blue-gradient), minHeight: 100svh)
│
├── ActionBar [GLASS z-50] — sticky top-0
│   backdrop-filter: var(--glass-blur)
│   background: var(--glass-bg)
│   border-bottom: 1px solid var(--glass-border)
│   box-shadow: var(--glass-shadow)
│   will-change: transform
│   Contém: Search Jobs (+ badge), Download PDF, Re-import, Auto Search
│
├── ProfileHeader [NEUMO z-10]
│   background: var(--neumo-bg)
│   box-shadow: var(--neumo-raised)
│   borderRadius: 20px, padding: 24px 28px, marginBottom: 20px
│   Contém: nome, cargo, contatos
│
├── Section: Summary [NEUMO z-10]
│   box-shadow: var(--neumo-raised)
│
├── Section: Experience [NEUMO z-10]
│   └── ExperienceCard [NEUMO z-10, elevação menor]
│       box-shadow: var(--neumo-raised-sm)
│
├── Section: Skills [NEUMO z-10]
│
├── Section: Education [NEUMO z-10]
│
├── Section: Languages [NEUMO z-10]
│
└── Section: Generation Prompts [NEUMO z-10]
    └── textarea [NEUMO inset]
        box-shadow: var(--neumo-inset)
        background: var(--neumo-bg)
    └── buttons Save/Reset
        box-shadow: var(--neumo-raised-sm)
        :active → box-shadow: var(--neumo-pressed)
```

### Padrão inline style para painéis neumórficos

```tsx
// Painel raised — usado em Section wrapper
const neumoPanel = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised)',
  borderRadius: 16,
  padding: '20px 24px',
  marginBottom: 20,
} satisfies React.CSSProperties

// Painel raised pequeno — usado em cards filhos
const neumoPanelSm = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised-sm)',
  borderRadius: 12,
  padding: '16px 18px',
  marginBottom: 12,
} satisfies React.CSSProperties

// Input/textarea inset
const neumoInset = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-inset)',
  borderRadius: 10,
  border: 'none',
  outline: 'none',
  padding: '12px 16px',
  color: 'var(--neumo-text)',
} satisfies React.CSSProperties

// Glass panel
const glassPanel = {
  background: 'var(--glass-bg)',
  backdropFilter: 'var(--glass-blur)',
  WebkitBackdropFilter: 'var(--glass-blur)',
  border: '1px solid var(--glass-border)',
  boxShadow: 'var(--glass-shadow)',
  willChange: 'transform',
} satisfies React.CSSProperties
```

---

## 4. Prova de Conceito — ProfilePage (esqueleto)

```tsx
// frontend/src/pages/ProfilePage.tsx (estrutura NeuGlass)

const PAGE_BG: React.CSSProperties = {
  background: 'var(--blue-gradient)',
  minHeight: '100svh',
  padding: '0 0 40px',
}

const ACTION_BAR: React.CSSProperties = {
  position: 'sticky',
  top: 0,
  zIndex: 50,
  background: 'var(--glass-bg)',
  backdropFilter: 'var(--glass-blur)',
  WebkitBackdropFilter: 'var(--glass-blur)',
  borderBottom: '1px solid var(--glass-border)',
  boxShadow: 'var(--glass-shadow)',
  willChange: 'transform',
  padding: '12px 24px',
  display: 'flex',
  gap: 10,
  alignItems: 'center',
}

const NEUMO_PANEL: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised)',
  borderRadius: 16,
  padding: '20px 24px',
  marginBottom: 20,
}

const NEUMO_CARD_SM: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised-sm)',
  borderRadius: 12,
  padding: '14px 16px',
  marginBottom: 12,
}

const NEUMO_INSET: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-inset)',
  borderRadius: 10,
  border: 'none',
  outline: 'none',
  padding: '12px 14px',
  width: '100%',
  resize: 'vertical',
  color: 'var(--neumo-text)',
  fontFamily: 'var(--mono)',
  fontSize: 12,
}

export function ProfilePage({ profile, onSearchJobs, ... }) {
  return (
    <div style={PAGE_BG}>

      {/* ── Glass: barra de ações flutuante ── */}
      <div style={ACTION_BAR}>
        <button onClick={onSearchJobs} style={{ /* CTA primário azul */ }}>
          Buscar Vagas
          {profile.job_suggestions.length > 0 && (
            <span style={{ /* badge */ }}>{profile.job_suggestions.length}</span>
          )}
        </button>
        <button style={{ /* secundário neumo */ }}>Download PDF</button>
        <button style={{ /* secundário neumo */ }}>Re-importar</button>
      </div>

      <div style={{ maxWidth: 720, margin: '32px auto', padding: '0 24px' }}>

        {/* ── Neumo: header de perfil ── */}
        <div style={NEUMO_PANEL}>
          <h1 style={{ color: 'var(--neumo-text)', margin: 0 }}>{profile.contact.full_name}</h1>
          <p style={{ color: 'var(--neumo-text-s)', marginTop: 4 }}>
            {[c.email, c.phone, c.location].filter(Boolean).join(' · ')}
          </p>
        </div>

        {/* ── Neumo: seção de experiência ── */}
        {profile.work_experiences.length > 0 && (
          <div style={NEUMO_PANEL}>
            <SectionTitle>Experiência</SectionTitle>
            {profile.work_experiences.map(exp => (
              <div key={exp.id} style={NEUMO_CARD_SM}>
                <ExperienceCard exp={exp} />
              </div>
            ))}
          </div>
        )}

        {/* ── Neumo: editor de prompts (textarea inset) ── */}
        <div style={NEUMO_PANEL}>
          <SectionTitle>Prompts de Geração</SectionTitle>
          <label style={{ color: 'var(--neumo-text-s)', fontSize: 12 }}>CV Prompt</label>
          <textarea style={NEUMO_INSET} rows={6} value={cvPrompt} onChange={...} />
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button
              style={NEUMO_CARD_SM}
              onMouseDown={e => e.currentTarget.style.boxShadow = 'var(--neumo-pressed)'}
              onMouseUp={e => e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)'}
            >
              Salvar
            </button>
            <button style={NEUMO_CARD_SM}>Resetar</button>
          </div>
        </div>

      </div>
    </div>
  )
}
```

---

## 5. Escopo de Implementação (PoC)

### Arquivos modificados
- `frontend/src/index.css` — adicionar bloco de tokens NeuGlass ao `:root`
- `frontend/src/pages/ProfilePage.tsx` — aplicar estilos NeuGlass

### Arquivos não tocados nesta iteração
- `JobSearchPage.tsx`, `AutoSearchPage.tsx`, `IngestPage.tsx` — expansão futura
- Backend — nenhuma mudança
- `App.tsx` — nenhuma mudança (background global fica no ProfilePage wrapper)

### Não incluído
- Dark mode NeuGlass (requer segundo conjunto de tokens)
- Animações de transição neumo (`:hover`, `:focus` além do `:active` básico)
- Outros componentes além de ProfilePage

---

## 6. Considerações de Acessibilidade

O Neumorfismo tem contraste naturalmente baixo entre superfície e fundo. Mitigações obrigatórias:

1. **Texto**: sempre usar `--neumo-text` (`#2d3a52`) sobre `--neumo-bg` — razão de contraste ~7:1 (passa AA+)
2. **Bordas de foco**: elementos interativos precisam de `outline: 2px solid var(--blue-primary)` no `:focus-visible` — sombras neumo sozinhas não comunicam foco
3. **Botões**: manter texto legível; não confiar na sombra como único indicador de "clicável" — adicionar cor de texto `--blue-primary` nos CTAs
