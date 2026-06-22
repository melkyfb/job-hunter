# Fase de Refinamento — Backlog de Melhorias

Anotações coletadas durante o desenvolvimento das Fases 1–5.
Endereçar após a entrega funcional completa do projeto.

---

## UX / Frontend

### [UX-01] Upload: Estado de análise sem feedback adequado

**Componente:** `frontend/src/components/ResumeUpload.tsx`

**Problema observado:**
O estado `uploading` exibe apenas "Analysing your resume…" — uma frase estática que não dá ao usuário nenhuma informação sobre progresso, tempo estimado ou o que está acontecendo internamente. Se a chamada ao LLM demorar (especialmente com modelos locais via Ollama), o usuário não tem como saber se o processo travou ou está em andamento.

**O que melhorar:**

1. **Etapas visíveis do pipeline** — mostrar em qual passo o sistema está:
   - `Extracting text from your file…`
   - `Sending to AI for analysis…`
   - `Validating structured output…`
   - `Checking for missing metrics…`

   Isso exige um endpoint de SSE (Server-Sent Events) ou polling de status no backend, já que hoje a rota `/profile/ingest` é síncrona (bloqueia até o LLM responder).

2. **Tempo estimado** — ao iniciar, exibir uma estimativa baseada no provider configurado:
   - Local (Ollama): ~30–90s dependendo do modelo e hardware
   - OpenAI: ~5–15s

   O endpoint `GET /config/llm` já expõe o provider — o frontend pode usar isso para calibrar a mensagem.

3. **Indicador de atividade** — substituir o texto estático por um spinner ou progress bar animado que deixe claro que o processo está rodando, mesmo sem saber o % exato.

4. **Timeout com mensagem de erro explicativa** — se o fetch não retornar em X segundos (ex: 120s), exibir:
   > "This is taking longer than expected. If you're using a local model, it may still be processing. Check the backend logs or try again."

   Evita o usuário fechar a aba achando que travou, quando na verdade o LLM local só está lento.

**Mudanças necessárias:**

- **Backend:** Converter `/profile/ingest` para resposta assíncrona com job ID + endpoint de polling `GET /profile/ingest/{job_id}/status`, ou implementar SSE com `StreamingResponse` do FastAPI.
- **Frontend:** `ResumeUpload.tsx` precisa de um hook de polling ou EventSource, substituindo o único `await ingestResume(file)` atual.

**Referência de implementação:**
```
POST /profile/ingest           → retorna { job_id, status: "processing" } imediatamente
GET  /profile/ingest/{job_id}  → retorna { status, step, message, result? }
```

---

### [UX-02] Pós-HITL: Tela final sem visibilidade do resultado nem ação clara

**Contexto:**
Após o usuário preencher as métricas XYZ no `HITLForm` e clicar em "Save and continue", o fluxo chega ao estado `has_profile` no `App.tsx` — que hoje exibe apenas o nome, contagem de experiências e skills, e um link de "Re-import resume". O usuário não vê o que foi gerado e não tem nenhuma ação de valor imediato.

**Problema:**
O perfil estruturado é o produto principal do sistema — é ele que será a base de todos os currículos enviados às vagas. Não dar visibilidade a ele após a criação é uma oportunidade perdida de construir confiança no resultado da análise. O usuário também não sabe que precisa "aprovar" esse perfil antes de usá-lo para candidaturas.

**O que melhorar:**

1. **Visualização do Master Profile** — uma página `ProfilePage` que exibe o perfil estruturado de forma legível (não JSON bruto):
   - Seção de dados de contato
   - Cada `WorkExperience` com os bullets XYZ formatados (`as_bullet`)
   - Skills com nível visual (ex: barra ou badge)
   - Botão "Edit" inline para corrigir qualquer campo sem precisar re-fazer o upload

2. **Ação de criação do Master Currículo** — um botão em destaque: **"Generate Master Resume PDF"**
   - Gera o PDF completo a partir do `ProfileMaster` sem adaptação para vaga específica
   - Serve como documento de referência e validação visual do que o agente extraiu
   - Implementado no Phase 5 (`POST /application/generate` sem `job_id`, só com o perfil base)
   - Abre preview do PDF no browser ou faz download direto

3. **Fluxo de onboarding claro** — deixar explícito para o usuário o que vem a seguir:
   > "Your Master Profile is ready. Next: search for jobs and we'll tailor your resume for each one."
   - Breadcrumb ou stepper: `Import → Review → Search → Apply`

**Mudanças necessárias:**

- **Frontend:** Criar `frontend/src/pages/ProfilePage.tsx` com visualização completa do `ProfileMaster`. Substituir o placeholder atual no `App.tsx` (estado `has_profile`).
- **Frontend:** Componente `XYZBullet.tsx` para renderizar cada `XYZExperience` no formato bullet Google.
- **Backend:** Adicionar endpoint `POST /application/master-resume` que gera PDF do `ProfileMaster` sem precisar de vaga — reutiliza o gerador de PDF da Fase 5 com template genérico.

**Referência de implementação:**
```
GET  /profile/                  → já existe, retorna ProfileMaster
POST /application/master-resume → novo, retorna { pdf_base64 }
```

---

### [UX-03] Busca de vagas: campo de pesquisa livre sem sugestões inteligentes do perfil

**Contexto:**
A `JobSearchPage` hoje exibe um `<input>` em branco onde o usuário precisa digitar manualmente um título de vaga ou palavras-chave. O sistema já possui o `ProfileMaster` completo com roles, skills e tecnologias — mas não usa esse contexto para orientar a busca, desperdiçando uma oportunidade de tornar o fluxo muito mais rápido.

**Problema:**
Um usuário que acabou de importar o currículo não quer começar a busca do zero. Ele quer validar quais títulos fazem sentido para o seu perfil e escolher rapidamente. Forçar digitação livre também aumenta a chance de queries pobres que retornam vagas irrelevantes.

**O que melhorar:**

1. **Geração de sugestões durante a ingestão** — no final do pipeline de ingestão (após o perfil ser validado e salvo), o agente executa uma chamada LLM extra para gerar até **20 sugestões de busca** baseadas no perfil estruturado. Cada sugestão contém:
   - `title`: título do cargo (ex: "Senior Backend Engineer")
   - `keywords`: lista de 3–5 palavras-chave ATS-relevantes para aquele título (ex: `["Python", "FastAPI", "REST API", "PostgreSQL"]`)

   Essas sugestões são salvas junto ao `ProfileMaster` (novo campo `job_suggestions: list[JobSuggestion]`).

2. **UI de seleção na `JobSearchPage`** — substituir o input livre por uma experiência em três camadas:
   - **Sugestões em chips clicáveis** — cada `JobSuggestion` aparece como um chip. Clicar em um preenche o campo de query e exibe as keywords daquele título como chips secundários selecionáveis.
   - **Seleção múltipla de keywords** — o usuário pode adicionar ou remover keywords individuais da query antes de buscar.
   - **Campo livre sempre disponível** — um input abaixo das sugestões permite digitar uma query completamente customizada, para o caso em que nenhuma sugestão serve.

3. **Persistência da seleção** — as sugestões escolhidas ficam marcadas visualmente em buscas subsequentes, facilitando iteração.

**Mudanças necessárias:**

- **Backend — modelo:** Adicionar a `ProfileMaster`:
  ```python
  class JobSuggestion(BaseModel):
      title: str
      keywords: list[str]

  # em ProfileMaster:
  job_suggestions: list[JobSuggestion] = Field(default_factory=list)
  ```

- **Backend — ingestion:** Após salvar o perfil em `IngestionService.run()`, disparar `SuggestionsAgent` que chama o LLM com o perfil e retorna `list[JobSuggestion]` validado por Pydantic. Usar o mesmo self-correction loop da ingestão.

- **Backend — endpoint:** `GET /profile/suggestions` ou incluir as sugestões diretamente no retorno de `GET /profile/` (campo `job_suggestions`).

- **Frontend:** Refatorar `JobSearchPage.tsx` — substituir o `<input>` por um componente `JobQueryBuilder` com chips de sugestão, chips de keywords e fallback para input livre.

**Referência de implementação:**
```
# Prompt para SuggestionsAgent
"Based on this profile, generate 20 job search suggestions.
Each suggestion must have a title and 3-5 ATS keywords for that title.
Return JSON: { suggestions: [{ title: string, keywords: string[] }] }"
```

---

### [FEAT-01] Busca automática de vagas sem interação do usuário

**Contexto:**
Hoje a `JobSearchPage` é inteiramente manual — o usuário precisa escolher um título ou digitar uma query antes de qualquer busca acontecer. Para usuários que estão ativamente procurando emprego, isso cria fricção desnecessária a cada sessão.

**O que melhorar:**

Adicionar um botão **"Auto Search"** (ou modo automático ativável nas configurações) que dispara uma busca sem nenhuma entrada do usuário:

1. **Seleção automática das 5 melhores queries** — o sistema usa as `job_suggestions` geradas na ingestão (ver `[UX-03]`) e seleciona as 5 com maior relevância para o perfil. A lógica de seleção pode ser simples (top 5 por score de compatibilidade estimado pelo LLM durante a geração das sugestões) ou um segundo LLM call curto: `"Given this profile, rank these 20 suggestions by likelihood of success. Return the top 5 titles only."`.

2. **Execução paralela das 5 buscas** — cada título dispara `run_pipeline()` independentemente (já existe no `job_pipeline.py`). As 5 execuções rodam em paralelo com `asyncio.gather()` ou `ThreadPoolExecutor`. O resultado é um único pool de vagas deduplicado por URL.

3. **Deduplicação e re-ranking** — vagas que aparecem em múltiplas buscas ganham um bônus de score (sinal de que são relevantes para vários ângulos do perfil). O resultado final é um ranking único com as melhores vagas encontradas nas 5 buscas.

4. **UX do modo automático:**
   - Botão "Auto Search" em destaque na tela de perfil (ao lado de "Search Jobs")
   - Enquanto roda: `"Finding the best jobs for your profile across 5 searches…"` com indicador de progresso por busca concluída (`2/5 searches done`)
   - Resultado exibe uma tag de qual busca encontrou cada vaga: ex. `"Found via: Senior Backend Engineer"`

**Dependência:** Requer `[UX-03]` implementado, pois depende do campo `job_suggestions` no `ProfileMaster`. Se as sugestões não existirem, o auto search pode fazer fallback para extrair as 5 top skills do perfil como queries diretas.

**Mudanças necessárias:**

- **Backend:** Novo endpoint `POST /jobs/auto-search` — sem body, carrega o perfil, seleciona as 5 melhores queries, executa o pipeline em paralelo, deduplica e retorna `list[RankedJob]` com campo extra `found_via: str`.
- **Frontend:** Botão "Auto Search" no `App.tsx` (estado `has_profile`) e indicador de progresso com contagem de buscas concluídas.

**Referência de implementação:**
```
POST /jobs/auto-search  (sem body)
→ carrega ProfileMaster
→ seleciona top 5 de job_suggestions (ou fallback: top skills)
→ asyncio.gather(run_pipeline × 5)
→ deduplica por posting.url, bônus +10 para duplicatas
→ retorna list[RankedJob] ordenado por score desc
```

---

### [UX-04] Tema claro/escuro com switch manual e fallback para preferência do sistema

**Contexto:**
O `index.css` já define CSS variables para os dois temas via `@media (prefers-color-scheme: dark)`, e os componentes foram corrigidos para usar essas variáveis (`var(--text)`, `var(--text-h)`, `var(--bg)`, `var(--border)`, `var(--accent)`). O que falta é permitir que o usuário **force** um tema independentemente da configuração do sistema, com persistência entre sessões.

**O que implementar:**

1. **Switch de tema** — componente `ThemeToggle` (ícone de sol/lua) fixo no canto superior direito da aplicação. Toggle entre `light`, `dark` e `system` (padrão).

2. **Lógica de aplicação do tema:**
   - Ao selecionar `light` ou `dark`, adicionar o atributo `data-theme="light"` ou `data-theme="dark"` no `<html>`.
   - Ao selecionar `system`, remover o atributo (volta a respeitar `prefers-color-scheme`).
   - Persistir a escolha em `localStorage` com a chave `"theme"`.
   - Na inicialização (`main.tsx`), ler o `localStorage` **antes** do primeiro render para evitar flash de tema errado (FOUC).

3. **CSS — adaptar as variáveis para responder ao `data-theme`:**
   ```css
   /* Substitui o @media por seletores de atributo */
   :root, [data-theme="light"] { --bg: #fff; --text: #6b6375; ... }
   [data-theme="dark"]          { --bg: #16171d; --text: #9ca3af; ... }

   /* Fallback para quem não tem preferência salva */
   @media (prefers-color-scheme: dark) {
     :root:not([data-theme="light"]) { /* dark vars */ }
   }
   ```

4. **Regra de ouro:** nenhum componente deve ter cores hexadecimais hardcoded para texto, fundo ou bordas. Todas as cores de UI devem vir das CSS variables. Cores semânticas fixas são aceitáveis apenas para status (verde de match, vermelho de missing, score badge).

**Arquivos a criar/modificar:**
- `frontend/src/components/ThemeToggle.tsx` — componente do switch
- `frontend/src/hooks/useTheme.ts` — hook que lê/escreve localStorage e aplica `data-theme` no `<html>`
- `frontend/src/index.css` — adaptar media query para seletores `data-theme`
- `frontend/src/main.tsx` — chamar `initTheme()` antes do ReactDOM.render para evitar FOUC

**Referência de implementação (hook):**
```ts
// hooks/useTheme.ts
type Theme = 'light' | 'dark' | 'system'

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem('theme') as Theme) ?? 'system'
  )
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])
  return { theme, setTheme }
}
```

---

### [UX-05] Feedback em tempo real durante a busca de vagas (Adzuna)

**Problema observado:**
A busca via Adzuna pode demorar vários segundos — a API externa tem latência variável, e o pipeline ainda executa scoring paralelo com LLM após receber os resultados. Durante todo esse tempo o usuário vê apenas "Fetching jobs and scoring each one against your profile…" sem nenhuma indicação de progresso.

**O que melhorar:**

1. **Progresso por etapas** — comunicar ao usuário em qual fase está:
   - `Searching Adzuna for "{query}" in {location}…`
   - `Found {n} jobs. Scoring each against your profile…`
   - `Scored {x}/{n} jobs…` (atualizado conforme o scoring paralelo conclui)
   - `Done! Showing {k} jobs above compatibility threshold.`

2. **Mecanismo sugerido:** Server-Sent Events (SSE) via `GET /jobs/search/stream` — o backend emite eventos JSON incrementais conforme cada etapa conclui. O frontend consome com `EventSource`. Alternativa mais simples: polling via `GET /jobs/search/{search_id}/status` a cada 1s.

3. **Detalhes a exibir no frontend durante a busca:**
   - Quantidade de vagas encontradas na fonte externa
   - Progresso do scoring (`x de n vagas analisadas`)
   - Tempo decorrido (contador simples em segundos)
   - Indicador visual de qual fonte está sendo usada (Adzuna / Mock)

**Arquivos a modificar:**
- `backend/app/services/job_pipeline.py` — emitir callbacks/eventos por etapa
- `backend/app/routers/jobs.py` — endpoint SSE ou polling de status
- `frontend/src/pages/JobSearchPage.tsx` — substituir mensagem estática por progresso dinâmico

---

### [PERF-01] Cache de buscas para evitar chamadas repetidas ao Adzuna

**Contexto:**
O Adzuna tem limite de requisições por plano (free tier: 100 req/mês). Um usuário que faz a mesma busca em intervalos curtos (revisitando a tela, testando variações) consome quota desnecessariamente e recebe dados idênticos, já que vagas raramente mudam em menos de algumas horas.

**O que implementar:**

1. **Cache em disco com TTL** — persistir o resultado de cada busca em `~/.job_hunter/search_cache/`. Chave: hash de `(query, location, max_results)`. TTL padrão: 2h (configurável via `.env`).

2. **Comportamento esperado:**
   - Busca dentro do TTL → retorna resultado do cache instantaneamente, sem chamar Adzuna
   - Busca fora do TTL ou novo parâmetro → chama Adzuna, atualiza o cache
   - Cache miss forçado → parâmetro `?force_refresh=true` no endpoint ignora o cache

3. **Limitação do Adzuna a investigar:** A API do Adzuna não fornece um campo `Last-Modified` ou ETag por busca — verificar se existe algum mecanismo de cache condicional nos headers de resposta. Se não houver, o TTL fixo é a única estratégia viável.

4. **Transparência para o usuário:** mostrar no resultado quando o cache foi usado:
   - `"Results from cache · searched {X} minutes ago · Refresh"`

5. **Implementação sugerida:**
   ```python
   # backend/app/services/search_cache.py
   import hashlib, json
   from pathlib import Path
   from datetime import datetime, timedelta

   _CACHE_DIR = Path.home() / ".job_hunter" / "search_cache"
   _DEFAULT_TTL = timedelta(hours=2)

   def cache_key(query: str, location: str, max_results: int) -> str:
       raw = f"{query}|{location}|{max_results}"
       return hashlib.sha256(raw.encode()).hexdigest()[:16]

   def get_cached(key: str, ttl=_DEFAULT_TTL) -> list | None:
       path = _CACHE_DIR / f"{key}.json"
       if not path.exists(): return None
       data = json.loads(path.read_text())
       if datetime.fromisoformat(data["cached_at"]) + ttl < datetime.now():
           return None  # expired
       return data["results"]

   def set_cache(key: str, results: list) -> None:
       _CACHE_DIR.mkdir(parents=True, exist_ok=True)
       path = _CACHE_DIR / f"{key}.json"
       path.write_text(json.dumps({"cached_at": datetime.now().isoformat(), "results": results}))
   ```

**Arquivos a criar/modificar:**
- `backend/app/services/search_cache.py` — lógica de cache (novo)
- `backend/app/services/job_pipeline.py` — integrar cache antes de chamar o provider
- `backend/app/routers/jobs.py` — expor `cached_at` e `force_refresh` no request/response
- `backend/app/core/config.py` — `search_cache_ttl_hours: int = Field(default=2)`
- `frontend/src/pages/JobSearchPage.tsx` — exibir indicador de cache + botão de refresh forçado

---

<!-- Adicionar mais refinamentos aqui conforme identificados -->
