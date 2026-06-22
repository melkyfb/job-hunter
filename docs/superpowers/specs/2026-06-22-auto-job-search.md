# Auto Busca de Vagas — Design Spec

**Date:** 2026-06-22
**Status:** Approved for implementation

---

## Overview

A busca automática de vagas executa pesquisas periódicas de emprego em background, com base nas sugestões do perfil e em entradas customizadas pelo usuário. Os resultados são persistidos localmente, deduplicados entre execuções e organizados num pipeline de status (nova → aplicada → entrevista → oferta / sem interesse). A tela de Auto Busca exibe configurações, lista paginada de vagas e abas por status. Um badge na ProfilePage indica novas vagas encontradas.

---

## 1. Armazenamento

Três arquivos em `~/.job_hunter/`:

### `auto_search_config.json`

Configurações do usuário. Pré-populado na primeira leitura com os `job_suggestions` do `ProfileMaster`.

```json
{
  "enabled": true,
  "interval_hours": 2,
  "location": "Munich, Germany",
  "page_size": 10,
  "entries": [
    {
      "id": "uuid-v4",
      "title": "Senior Backend Engineer",
      "keywords": ["python", "fastapi", "postgresql"],
      "active": true,
      "custom": false
    },
    {
      "id": "uuid-v4",
      "title": "My Custom Title",
      "keywords": ["go", "grpc"],
      "active": true,
      "custom": true
    }
  ]
}
```

- `enabled` — liga/desliga o scheduler sem perder as demais configurações
- `entries` com `custom: false` são sincronizadas dos `job_suggestions` do perfil; com `custom: true` foram criadas manualmente pelo usuário
- O usuário pode desativar entries individualmente (`active: false`) sem excluí-las

### `auto_search_results.json`

Vagas encontradas, indexadas por `url_hash` (SHA-256 truncado dos primeiros 16 chars da URL).

```json
{
  "last_run_at": "2026-06-22T14:00:00",
  "next_run_at": "2026-06-22T16:00:00",
  "new_count": 12,
  "jobs": {
    "<url_hash>": {
      "posting": { "...": "JobPosting fields" },
      "match": { "...": "MatchScore fields" },
      "found_at": "2026-06-22T10:00:00",
      "last_seen_at": "2026-06-22T14:00:00",
      "found_via": "Senior Backend Engineer",
      "run_id": "uuid-v4"
    }
  }
}
```

**Deduplicação entre execuções:**
- Mesma URL já existente → atualiza `last_seen_at`, recalcula score como `max(stored, new)`, preserva `found_at`
- Vaga com status ≠ NONE nunca tem seu conteúdo sobrescrito (só `last_seen_at`)
- `new_count` incrementa para cada URL nova (nunca vista antes); zerado quando o usuário visualiza a aba "Novas vagas"

### `job_status.json`

Status do pipeline, indexado por `url_hash`.

```json
{
  "<url_hash>": {
    "status": "APPLIED",
    "updated_at": "2026-06-22T11:30:00",
    "notes": "Enviado via LinkedIn"
  }
}
```

**Status disponíveis:** `NONE` · `NOT_INTERESTED` · `APPLIED` · `INTERVIEWING` · `OFFER_RECEIVED`

---

## 2. Modelos Pydantic

Novo arquivo `backend/app/models/auto_search.py`:

```python
class SearchEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    keywords: list[str]
    active: bool = True
    custom: bool = False

class AutoSearchConfig(BaseModel):
    enabled: bool = True
    interval_hours: int = Field(default=2, ge=1, le=168)
    location: str = "Munich, Germany"
    page_size: int = Field(default=10, ge=5, le=50)
    entries: list[SearchEntry] = Field(default_factory=list)

class JobStatus(str, Enum):
    NONE = "NONE"
    NOT_INTERESTED = "NOT_INTERESTED"
    APPLIED = "APPLIED"
    INTERVIEWING = "INTERVIEWING"
    OFFER_RECEIVED = "OFFER_RECEIVED"

class JobStatusEntry(BaseModel):
    status: JobStatus = JobStatus.NONE
    updated_at: datetime = Field(default_factory=datetime.now)
    notes: Optional[str] = None

class SavedJob(BaseModel):
    posting: JobPosting
    match: MatchScore
    found_at: datetime
    last_seen_at: datetime
    found_via: str
    run_id: str

class AutoSearchSummary(BaseModel):
    enabled: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    new_count: int
    total_count: int

class AutoSearchResultsPage(BaseModel):
    jobs: list[SavedJobWithStatus]     # SavedJob + url_hash + status
    total: int
    page: int
    page_size: int
    total_pages: int
```

---

## 3. Backend — Serviços

### `backend/app/services/auto_search_store.py`

Responsabilidades: ler/escrever os 3 arquivos JSON com lock de threading para segurança em acessos concorrentes.

**Funções exportadas:**
- `load_config() -> AutoSearchConfig` — lê config; se não existir, cria a partir de `ProfileMaster.job_suggestions`
- `save_config(config: AutoSearchConfig) -> None`
- `upsert_jobs(jobs: list[RankedJob], run_id: str, found_via: str) -> int` — retorna contagem de vagas **novas** (não antes vistas)
- `get_results_page(page, page_size, status_filter, sort) -> AutoSearchResultsPage`
- `get_summary() -> AutoSearchSummary`
- `set_job_status(url_hash: str, status: JobStatus, notes: str | None) -> None`
- `mark_seen() -> None` — zera `new_count`
- `update_run_times(last_run_at: datetime, next_run_at: datetime) -> None`
- `cleanup(before_date: datetime | None, remove_not_interested: bool, remove_unavailable: bool) -> int` — retorna contagem de vagas removidas

**`remove_unavailable`:** remove vagas cujo `last_seen_at` é anterior a `last_run_at` (a última execução não as encontrou mais).

### `backend/app/services/auto_search_scheduler.py`

APScheduler `BackgroundScheduler` (thread-based, sem asyncio).

```python
_scheduler = BackgroundScheduler(timezone="UTC")
_JOB_ID = "auto_search"

def _run() -> None:
    """Executed by the scheduler in a background thread."""
    config = load_config()
    if not config.enabled:
        return
    profile = ProfileRepository().load()   # needed by run_pipeline for scoring
    run_id = str(uuid4())
    for entry in config.entries:
        if not entry.active:
            continue
        query = f"{entry.title} {' '.join(entry.keywords)}"
        # run_pipeline(profile, query, location, max_results) from job_pipeline.py
        results = run_pipeline(profile, query, config.location, max_results=20)
        upsert_jobs(results, run_id=run_id, found_via=entry.title)
    next_run = datetime.now(UTC) + timedelta(hours=config.interval_hours)
    update_run_times(last_run_at=datetime.now(UTC), next_run_at=next_run)

def start(interval_hours: int = 2) -> None:
    _scheduler.add_job(_run, "interval", hours=interval_hours, id=_JOB_ID, replace_existing=True)
    _scheduler.start()

def reschedule(new_interval_hours: int) -> None:
    _scheduler.reschedule_job(_JOB_ID, trigger="interval", hours=new_interval_hours)

def trigger_now() -> None:
    _scheduler.add_job(_run, "date", id=f"{_JOB_ID}_manual", replace_existing=True)

def shutdown() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
```

`start()` / `shutdown()` são chamados nos eventos de lifespan do FastAPI em `main.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    start(interval_hours=config.interval_hours)
    yield
    shutdown()

app = FastAPI(lifespan=lifespan)
```

---

## 4. Backend — Router

Novo arquivo `backend/app/routers/auto_search.py`, prefix `/auto-search`.

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/config` | Retorna `AutoSearchConfig` |
| `PUT` | `/config` | Salva config; se `interval_hours` mudou, chama `reschedule()`; se `enabled` mudou, liga/desliga |
| `GET` | `/summary` | Retorna `AutoSearchSummary` (lightweight, chamado a cada 60s pelo frontend) |
| `POST` | `/run` | Dispara `trigger_now()` + retorna `{status: "triggered"}` |
| `GET` | `/results` | Paginado: `?page=1&page_size=10&status_filter=NONE&sort=score`. `status_filter` aceita valor único (`NONE`) ou múltiplos separados por vírgula (`APPLIED,INTERVIEWING,OFFER_RECEIVED`) para a aba Pipeline. |
| `POST` | `/mark-seen` | Zera `new_count` (chamado ao abrir aba "Novas vagas") |
| `PATCH` | `/jobs/{url_hash}/status` | Body: `{status, notes?}` → `set_job_status()` |
| `DELETE` | `/cleanup` | Query params: `before_date?`, `remove_not_interested?`, `remove_unavailable?` → retorna `{removed: int}` |

Registrado em `main.py`: `app.include_router(auto_search.router)`.

---

## 5. Frontend

### `frontend/src/api/client.ts` — novos tipos e funções

**Novos tipos:**
```typescript
type JobStatus = 'NONE' | 'NOT_INTERESTED' | 'APPLIED' | 'INTERVIEWING' | 'OFFER_RECEIVED'

interface SearchEntry {
  id: string
  title: string
  keywords: string[]
  active: boolean
  custom: boolean
}

interface AutoSearchConfig {
  enabled: boolean
  interval_hours: number
  location: string
  page_size: number
  entries: SearchEntry[]
}

interface AutoSearchSummary {
  enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  new_count: number
  total_count: number
}

interface SavedJobWithStatus {
  url_hash: string
  posting: JobPosting
  match: MatchScore
  found_at: string
  last_seen_at: string
  found_via: string
  status: JobStatus
  notes: string | null
}

interface AutoSearchResultsPage {
  jobs: SavedJobWithStatus[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
```

**Novas funções:**
```typescript
getAutoSearchConfig()                                  // GET /auto-search/config
saveAutoSearchConfig(config: AutoSearchConfig)         // PUT /auto-search/config
getAutoSearchSummary()                                 // GET /auto-search/summary
triggerAutoSearch()                                    // POST /auto-search/run
getAutoSearchResults(page, pageSize, statusFilter, sort) // GET /auto-search/results
markAutoSearchSeen()                                   // POST /auto-search/mark-seen
setJobStatus(urlHash, status, notes?)                  // PATCH /auto-search/jobs/{hash}/status
cleanupAutoSearch(params)                              // DELETE /auto-search/cleanup
```

### Componentes novos

**`frontend/src/components/AutoSearchConfig.tsx`**

Painel colapsável. Estados: `collapsed` / `expanded` / `saving`.

- Toggle `enabled` (liga/desliga scheduler)
- `<select>` para `interval_hours` (opções: 1h, 2h, 4h, 8h, 12h, 24h)
- Input de texto para `location`
- Lista de entries: cada uma tem checkbox (active), label do título editável inline, chips dos keywords editáveis (tag input), botão de remover (apenas para `custom: true`)
- Botão "+ Adicionar título" — abre linha nova com inputs em branco
- Botão "Salvar" — chama `saveAutoSearchConfig`, se intervalo mudou o scheduler é reconfigurado automaticamente no backend

**`frontend/src/components/JobStatusMenu.tsx`**

Dropdown `⋮` por card de vaga.

Opções do menu:
- **Sem interesse** → status `NOT_INTERESTED`
- **Currículo enviado** → status `APPLIED`
- **Em processo** (entrevista) → status `INTERVIEWING`
- **Oferta recebida** → status `OFFER_RECEIVED`
- **Desfazer** (se já tem status) → volta para `NONE`

Ao selecionar, chama `setJobStatus()` e o card é removido da aba atual via atualização de estado local (sem reload da página).

### `frontend/src/pages/AutoSearchPage.tsx` — redesenho completo

**Layout:**

```
Header
  Título + botão "Buscar agora" + botão "Voltar"
  Linha de status: "Última busca: há Xmin · Próxima: em Ymin · N vagas"

AutoSearchConfig (colapsável)

3 abas:
  [Novas vagas N]  [Pipeline N]  [Sem interesse N]

Controles da aba:
  Ordenar: [Score ▼ | Mais recente ▼]    [🧹 Limpar…]

Lista de cards (paginada)
  Cada card: ScoreBadge · título · empresa · local · data · found_via chip · ⋮ menu

Paginação: [< 1 2 3 ... N >]
```

**Aba "Novas vagas":** `status_filter=NONE`. Ao abrir, chama `markAutoSearchSeen()`.

**Aba "Pipeline":** mostra APPLIED + INTERVIEWING + OFFER_RECEIVED. Agrupa visualmente por etapa com cabeçalho de seção.

**Aba "Sem interesse":** `status_filter=NOT_INTERESTED`. Permite desfazer (voltar para NONE).

**Modal de cleanup (botão 🧹):**
- Checkbox "Remover vagas mais antigas que [data]"
- Checkbox "Remover vagas marcadas como sem interesse"
- Checkbox "Remover vagas que não aparecem mais nas buscas"
- Botão "Limpar" com contagem prévia

### Badge na ProfilePage

**`App.tsx`:**
- Estado `autoSearchNewCount: number`
- `useEffect` que chama `getAutoSearchSummary()` a cada 60s
- Passa `newCount` para `ProfilePage` como prop `autoSearchBadge`

**`ProfilePage.tsx`:**
- Botão "⚡ Auto Search" ganha badge visual quando `autoSearchBadge > 0`:
  `⚡ Auto Search ●12`

---

## 6. Fluxo de Dados

```
APScheduler (thread)
  → _run()
    → load_config()
    → para cada entry ativa: run_job_pipeline(query, location)
    → upsert_jobs(results, run_id, found_via)  ← incrementa new_count
    → update_run_times()

Frontend (App.tsx, 60s)
  → GET /auto-search/summary
  → mostra badge se new_count > 0

Usuário abre AutoSearchPage
  → GET /auto-search/results?page=1&status_filter=NONE
  → POST /auto-search/mark-seen   ← zera new_count

Usuário clica ⋮ → "Currículo enviado"
  → PATCH /auto-search/jobs/{hash}/status
  → card removido da aba localmente

Usuário salva configuração
  → PUT /auto-search/config
  → backend chama reschedule() se interval mudou

Usuário clica "Buscar agora"
  → POST /auto-search/run
  → scheduler dispara _run() imediatamente em background
```

---

## 7. Fora de Escopo

- Notificações nativas do sistema operacional (toast/push)
- Sincronização de status com plataformas externas (LinkedIn, etc.)
- Histórico de execuções (log de cada run)
- Busca em múltiplos países simultaneamente por execução
