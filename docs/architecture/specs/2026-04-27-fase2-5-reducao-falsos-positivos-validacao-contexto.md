# Fase 2.5 — Redução de Falsos Positivos + Validação de Contexto (100% Open Source)

**Data:** 2026-04-27
**Status:** Proposto (aguardando revisão)
**Branch sugerida:** `feat/fase2-5-falsos-positivos`
**Base:** Fase 2 concluída (`feat/fase2-fontes-saidas-gravacao`)
**Restrição dura:** zero dependência de API paga, zero serviço externo. Tudo roda localmente, com modelos e libs livres (Apache/MIT/BSD). Projeto acadêmico de Sistemas Ubíquos — autonomia e custo zero são requisitos.
**Specs anteriores:**
- `docs/superpowers/specs/2026-04-24-driver-fatigue-ubiquitous-design.md`
- `docs/superpowers/specs/2026-04-24-fase2-fontes-saidas-gravacao-design.md`

---

## 1. Problema

O detector atual dispara alarmes em situações que **não** correspondem a sonolência real, e o som é alto e contínuo. Sintomas observados:

- Bocejo "falso" quando o motorista está **falando** (MAR alto, mas é fala/canto, não bocejo).
- EAR baixo por **rosto inclinado / parcialmente fora do quadro** (não olho fechado).
- EAR baixo por **piscadas longas** ou ato de **coçar/esfregar o olho**.
- Disparo único pode bipar indefinidamente até o estado sair de `alert` — sem cooldown nem rampa de volume.
- Nenhuma calibração por usuário: o EAR de repouso varia bastante entre indivíduos (formato do olho, óculos, iluminação).

O resultado é um sistema "barulhento e desconfiável", inviabilizando uso real (e a demo do artigo).

## 2. Objetivo

Tornar o disparo do alarme **confiável**: só acordar o motorista quando há evidência forte de sonolência, e fazer isso de forma **arquitetonicamente coerente** com a Fase 1 (ports & adapters, domínio puro).

Dois eixos, em duas etapas — **ambas 100% locais, sem rede**:

- **Etapa A — Heurísticas no domínio:** matar 70-90% dos falsos positivos com guardas de qualidade, calibração por usuário, histerese e discriminadores temporais. Zero dependência nova.
- **Etapa B — Validador de contexto com modelo local:** confirmar suspeitas com um classificador CNN leve em ONNX/PyTorch antes de notificar os sinks. Modelo open-source pré-treinado, embutido (ou baixado uma vez), roda em CPU.

A Etapa A é pré-requisito da B (não adianta validar contexto se a suspeita base é lixo).

## 3. Não-objetivos

- Trocar MediaPipe por outro detector facial.
- Treinar modelo próprio de drowsiness do zero (usaremos pesos pré-treinados livres; eventual fine-tune é opcional).
- **Qualquer integração com API paga ou serviço remoto** (Claude, OpenAI, Gemini, AWS Rekognition, etc.). Inclusive grátis-com-cadastro: fora.
- Telemetria que dependa de internet em runtime.
- Multi-usuário simultâneo / identificação de motorista.
- Mudanças no formato dos sinks de saída (HTTP/MQTT/log/sound permanecem iguais — webhook HTTP é decisão do usuário do sistema, não do detector).

---

## 4. Etapa A — Heurísticas e Calibração

### 4.1 Calibração de baseline EAR/MAR por sessão

**Domínio:** novo value object `PersonalBaseline`.

```python
# domain/value_objects.py
@dataclass(frozen=True)
class PersonalBaseline:
    ear_rest: float          # EAR médio em repouso (olhos abertos, neutro)
    mar_rest: float          # MAR médio em repouso (boca fechada)
    ear_std: float           # desvio padrão observado
    mar_std: float
    sample_count: int        # nº de frames usados na calibração

    @property
    def is_calibrated(self) -> bool:
        return self.sample_count >= 30
```

**Política:** os primeiros N frames (default 60, ~2s @ 30fps) são usados para estimar `ear_rest`/`mar_rest`. Durante a calibração o alarme fica **inibido**. Os thresholds passam a ser **relativos**:

```
ear_threshold_effective = ear_rest * 0.75   # configurável: ear_close_ratio
mar_threshold_effective = mar_rest + 2.5 * mar_std   # configurável: mar_open_zscore
```

Isso elimina a sensibilidade ao formato do olho do usuário e à iluminação ambiente.

`AppSettings` ganha:

```yaml
calibration:
  enabled: true
  warmup_frames: 60
  ear_close_ratio: 0.75
  mar_open_zscore: 2.5
```

### 4.2 Gate de qualidade do frame

**Domínio:** `FrameQuality` (novo value object), avaliado a cada frame.

Critérios para o frame ser considerado **confiável**:

1. MediaPipe retornou landmarks com confidence ≥ `min_face_confidence` (default 0.5).
2. Bounding box do rosto cobre ≥ `min_face_area_ratio` do frame (default 0.05).
3. Yaw/pitch estimados estão dentro de `max_head_yaw_deg` / `max_head_pitch_deg` (defaults 35° / 25°). Estimativa via 3 landmarks (nariz + 2 olhos) — não precisamos de SolvePnP cheio.
4. Olhos e boca não estão recortados pela borda do frame.

Se o frame falha o gate, o `DetectFatigueUseCase` retorna o estado **inalterado** (não conta como evidência de fadiga). Um contador `untrusted_frames_streak` vai pro HUD.

### 4.3 Histerese e cooldown no `FatigueEvaluator`

Hoje só temos `consecutive_frames` para **entrar** em alerta. Falta:

- `recovery_frames`: nº de frames consecutivos com EAR/MAR normais para **sair** de alerta (default 10).
- `alarm_cooldown_seconds`: tempo mínimo entre dois disparos do `notify()` (default 5s) — evita "tac-tac-tac" se o sinal oscilar.
- `min_alert_duration_frames`: tempo mínimo de alerta antes que `on_recovery` seja chamado (default 5).

Tudo configurável em `thresholds`. O cooldown vive no domínio (`FatigueState` ganha `last_alert_frame`).

### 4.4 Discriminador "fala vs bocejo"

Bocejos têm assinatura temporal **diferente** de fala:

- Bocejo: MAR sobe, **mantém-se alto por ≥ 1.5s**, desce.
- Fala/canto: MAR oscila rapidamente em torno de um valor médio elevado.

**Heurística:** janela deslizante dos últimos K frames de MAR (K=45, ~1.5s). Considera bocejo apenas se:

- `min(MAR[K]) ≥ mar_threshold_effective` (mantido alto, não só picos), **E**
- `std(MAR[K]) < yawn_stability_max` (default 0.04 — se varia muito, é fala).

Implementado no `FatigueEvaluator` com um deque interno (estado puro, sem I/O).

### 4.5 Rampa e volume controlado do alarme

`SoundSink` hoje toca `audio/alarm.wav` em loop a volume cheio. Mudanças:

- Iniciar em volume baixo (ex. 0.4) e subir até 1.0 ao longo de 3 segundos. Acorda sem assustar.
- Parar imediatamente quando `on_recovery` é chamado.
- Respeitar o cooldown global (`alarm_cooldown_seconds`).

Sem mudança de port — só comportamento interno do adapter.

### 4.6 Métricas operacionais (HUD + log)

O HUD ganha uma linha de "saúde":

```
QUALITY: OK | EAR base: 0.31 | MAR base: 0.42 | calibrated ✓
```

E quando o frame é descartado:

```
QUALITY: skip (head yaw 42°)
```

Útil pra debug e pra justificar no artigo "por que não disparou aqui".

### 4.7 Saída esperada da Etapa A

Sob uso normal (motorista atento, falando ao telefone, virando a cabeça pra checar retrovisor), **zero alarme**. Sob sonolência real (olhos fechados >0.6s estável + cabeça pendendo), alarme dispara em ≤ 1s.

---

## 5. Etapa B — `ContextValidator`: modelo CNN local confirma a suspeita

### 5.1 Novo port

```python
# application/ports.py
@runtime_checkable
class ContextValidatorPort(Protocol):
    def confirm_drowsy(
        self,
        frame: Frame,
        state: FatigueState,
    ) -> ContextVerdict:
        """Confirma (ou nega) que o frame mostra sonolência real."""
        ...
```

```python
# domain/value_objects.py
@dataclass(frozen=True)
class ContextVerdict:
    drowsy: bool
    confidence: float           # 0.0 - 1.0
    reason: str                 # explicação curta ("eyes closed long", "yawn sustained")
    latency_ms: float
```

### 5.2 Integração no `MonitorDriverUseCase`

O validador é chamado **somente** quando a etapa A já decidiu que entraria em alerta (ponto único de injeção, custo de inferência controlado):

```
heurística diz "entrar em alert"
        │
        ▼
ContextValidator.confirm_drowsy(frame, state)
        │
        ├── drowsy=True, confidence ≥ threshold → notifica sinks
        └── drowsy=False                        → suprime alarme + log "ctx_suppressed"
```

Se o validador estiver `noop` (default), fluxo cai pro caminho atual sem mudança — nenhum overhead.

### 5.3 Estratégia: dois adapters locais, ambos open source

Nenhum chamado de rede em runtime. Modelos são baixados **uma vez** (build/setup) e versionados via hash.

#### 5.3.1 `EyeStateClassifier` (recomendado, padrão da Etapa B)

Classificador binário **eyes-open vs eyes-closed** rodando no crop dos olhos extraído via landmarks do MediaPipe (já temos). Combina sinal temporal (PERCLOS — % do tempo com olhos fechados em janela de 60s) com score do CNN.

- Input: dois crops 24x24 (olho esquerdo + direito), grayscale.
- Arquitetura: CNN minúscula tipo "MRL Eye Dataset" baseline (~50KB de pesos, **<5ms** em CPU).
- Pesos: pré-treinados livres do **MRL Eye Dataset** (CC0/Open Data Commons) ou **CEW dataset** — re-empacotados em ONNX e versionados no repo (`models/eye_state.onnx`, ~50-200KB).
- Decisão: `drowsy=True` se PERCLOS_60s > 0.4 **e** score atual ≥ `min_confidence`.

Vantagem: minúsculo, determinístico, explicável no artigo, e ataca exatamente o falso positivo principal (EAR baixo ≠ olho fechado).

#### 5.3.2 `DrowsinessCnnClassifier` (opcional, mais robusto)

Classificador holístico do rosto inteiro — pega bocejos prolongados + olhos + postura num único forward pass.

- Input: crop do rosto 224x224 (já temos bbox).
- Backbone: **MobileNetV3-Small** ou **EfficientNet-B0** pré-treinados em ImageNet, fine-tunados em **NTHU-DDD** ou **UTA-RLDD** (datasets acadêmicos abertos, padrão na literatura — ótimo pra citar no artigo).
- Runtime: `onnxruntime` em CPU, ~20-50ms/frame.
- Pesos: ou treinamos uma vez (script `scripts/train_drowsiness.py`, fora da pipeline runtime) e commitamos o `.onnx` (~5MB) ou usamos pesos pré-fine-tunados publicados em repos GitHub com licença permissiva (a verificar antes de adotar).

Localização única: `infrastructure/context_validators/`:

```
context_validators/
├── noop.py                   # NoopValidator — sempre confirma
├── eye_state_onnx.py         # EyeStateClassifier (5.3.1)
├── drowsiness_cnn_onnx.py    # DrowsinessCnnClassifier (5.3.2, opcional)
└── perclos.py                # buffer temporal compartilhado
```

Dep nova (mandatória pra Etapa B): `onnxruntime>=1.17` (Apache-2.0). É a única adição.

### 5.4 Configuração

```yaml
context_validator:
  kind: noop | eye_state | drowsiness_cnn   # default: eye_state
  min_confidence: 0.6
  fail_safe_on_error: alarm                  # alarm | suppress (default: alarm)
  perclos_window_seconds: 60
  perclos_threshold: 0.4

  eye_state:
    model_path: models/eye_state.onnx

  drowsiness_cnn:
    model_path: models/drowsiness_mobilenet.onnx
    input_size: 224
```

### 5.5 Procedência dos modelos (importa pro artigo)

Qualquer modelo embutido no repo precisa de:

- Licença permissiva (Apache, MIT, BSD, CC-BY, CC0).
- Dataset de origem citável (NTHU-DDD, UTA-RLDD, MRL Eye, CEW).
- Hash SHA-256 fixado em `models/MODELS.md` para reprodutibilidade.
- Script de treinamento (quando aplicável) em `scripts/`, com seed fixa.

Sem nada disso: não entra. Sem exceção.

### 5.6 Observabilidade

Cada chamada do validator é logada via `LogSink` com `latency_ms`, `verdict`, `reason`. Útil pra calibrar `min_confidence`/`perclos_threshold` por dataset e gerar tabelas pro artigo.

---

## 6. Mudanças por camada (resumo)

| Camada | O que muda |
|---|---|
| `domain/value_objects.py` | + `PersonalBaseline`, `FrameQuality`, `ContextVerdict` |
| `domain/evaluator.py` | + histerese, cooldown, discriminador fala/bocejo, baseline relativo |
| `domain/entities.py` | `FatigueState` ganha `last_alert_frame`, `baseline`, `quality` |
| `application/ports.py` | + `ContextValidatorPort` |
| `application/use_cases/monitor_driver.py` | + ramo de validação contextual antes de `notify()` |
| `application/use_cases/detect_fatigue.py` | + checagem de `FrameQuality`, calibração warmup |
| `infrastructure/context_validators/` | **novo** pacote (`noop.py`, `eye_state_onnx.py`, `drowsiness_cnn_onnx.py`, `perclos.py`) |
| `models/` | + `eye_state.onnx` (mandatório p/ Etapa B), opcionalmente `drowsiness_mobilenet.onnx`, + `MODELS.md` (proveniência + hashes) |
| `scripts/` | + `download_models.py` (busca pesos open-source uma vez) e, se aplicável, `train_drowsiness.py` |
| `infrastructure/sinks/sound.py` | rampa de volume + cooldown |
| `infrastructure/rendering/hud.py` | linha de qualidade/baseline |
| `infrastructure/face_detector/mediapipe.py` | expor confidence + bbox |
| `interfaces/cli/main.py` | + flag `--context-validator={noop,eye_state,drowsiness_cnn}` |
| `bootstrap.py` | montar `ContextValidator` conforme settings |
| `config/default.yaml` | seções `calibration`, `context_validator`, `recovery_frames`, `alarm_cooldown_seconds` |

Sem breaking change: Etapa A é ligada por padrão (calibração + histerese — puramente benéfica). Etapa B vem com `kind=eye_state` por padrão **se** `models/eye_state.onnx` existir; caso contrário, cai automaticamente pra `noop` com warning no log (não quebra `pip install -e .` em máquina limpa).

---

## 7. Estratégia de testes

**Unit (domain):**
- `evaluator` calibra baseline corretamente em N frames.
- `evaluator` aplica histerese — entrada/saída têm contagens distintas.
- `evaluator` discrimina fala (alta variância MAR) de bocejo (baixa variância, alto sustentado).
- `FrameQuality` rejeita yaw/pitch fora de faixa, área pequena, confidence baixa.

**Integration:**
- `EyeStateClassifier` carrega ONNX e classifica crops sintéticos (olho fechado/aberto gerados por fixture).
- `DrowsinessCnnClassifier` (quando incluído) carrega ONNX e processa frame inteiro.
- `PerclosBuffer` calcula PERCLOS corretamente em janela deslizante.
- `SoundSink` faz rampa e respeita cooldown (mockando `pygame.mixer`).
- Bootstrap faz fallback automático pra `NoopValidator` se modelo ONNX ausente.

**E2E:**
- Pipeline completa com vídeo `assets/test_sonolency.mp4` + validator `noop` → comportamento não regride.
- Pipeline com validator mockado que sempre retorna `drowsy=False` → alarme nunca dispara, mas log mostra `ctx_suppressed`.
- Pipeline com `eye_state` real + vídeo de sonolência → alarme dispara dentro de 1s.

**Validação manual (artigo):**
- Vídeo do motorista falando → 0 alarmes.
- Vídeo do motorista virando cabeça → 0 alarmes.
- Vídeo de sonolência real → alarme em ≤ 1s, com rampa.

Cobertura `domain/application` mantém o gate de 95%.

---

## 8. Faseamento sugerido

| Fase | Conteúdo | Estimativa |
|---|---|---|
| 2.5a | Etapa A completa (calibração, gate, histerese, cooldown, fala/bocejo, rampa de som) | médio |
| 2.5b | `ContextValidatorPort` + `NoopValidator` + ramo no use case + cobertura | pequeno |
| 2.5c | `EyeStateClassifier` (ONNX) + `PerclosBuffer` + modelo embutido + testes | médio |
| 2.5d (opcional) | `DrowsinessCnnClassifier` + script de treino/download + testes | médio |

Cada subfase em PR separado, com sua própria pasta `.planning/phase-*` quando rodarmos via `/gsd`.

---

## 9. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Etapa A "calibrar errado" se o motorista começa já cansado | Recalibração contínua: baseline é EMA dos últimos M minutos quando frame está em qualidade alta e estado normal. |
| Modelo ONNX pesado pra hardware fraco (Raspberry Pi etc.) | `EyeStateClassifier` é ~50KB e <5ms — viável até em SBC. `drowsiness_cnn` é opcional. Adapter faz lazy-load + fallback pra `noop` se `onnxruntime` faltar. |
| Falso negativo do modelo "deixa motorista dormir" | `min_confidence` baixa por default (0.6) + PERCLOS independente — em dúvida, alarme dispara. `fail_safe_on_error=alarm` em qualquer erro de inferência. |
| Modelo embutido aumenta tamanho do repo | `EyeStateClassifier` ~50-200KB (ok). Modelo grande (`drowsiness_mobilenet`, ~5MB) fica fora do git e é baixado via `scripts/download_models.py` na hora do setup. |
| Licenciamento dos pesos pode ser ambíguo | `models/MODELS.md` documenta licença, dataset de origem e SHA-256 de cada arquivo. Pesos sem licença clara não entram. |

---

## 9.5 Aderência ao paradigma ubíquo

Esta seção mapeia cada decisão de design da Fase 2.5 ao critério
correspondente do **Checklist de Sistema Ubíquo** da disciplina.
Auto-avaliação completa, com pontuação e justificativas, em
`docs/UBIQUITY-CHECKLIST.md`. Diagrama de camadas em
`docs/ARCHITECTURE.md`. Privacidade em `docs/PRIVACY.md`.

| Decisão da Fase 2.5 | Critério do checklist | Como satisfaz |
|---|---|---|
| `PersonalBaseline` + warmup de calibração | **Adaptação automática**, **Sensibilidade ao contexto** | Thresholds passam a ser relativos ao motorista da sessão; sistema aprende o EAR/MAR de repouso sem intervenção manual. |
| `FrameQualityPolicy` (yaw/pitch/área) | **Sensibilidade ao contexto**, **Tolerância a falhas** | Frame não-confiável é descartado sem alterar estado, evitando falso positivo por cabeça virada. |
| Histerese + `alarm_cooldown_seconds` + `min_alert_duration_frames` | **Adaptação automática**, **Baixa intrusão** | Comportamento muda conforme histórico recente; alarme não oscila. |
| Discriminador fala vs bocejo (janela MAR) | **Interpretação de contexto** | Não basta coletar MAR — interpreta o padrão temporal para distinguir situações distintas. |
| Rampa de volume no `SoundSink` | **Baixa intrusão**, **Pró-atividade** | Sistema acorda o motorista de forma gradual e natural, sem assustar. |
| `ContextValidatorPort` + `EyeStateClassifier` (ONNX local) | **Interpretação de contexto**, **Processamento local** | Confirma a suspeita com modelo CNN rodando 100% na borda. |
| `NoopContextValidator` como fallback automático | **Tolerância a falhas**, **Heterogeneidade** | Falha do modelo ONNX não derruba o sistema; cai pra heurística pura. |
| `JsonlEventSink` (nova camada de persistência) | **Persistência de dados** | Evidência auditável da POC; só métricas numéricas, sem imagem. |
| `web.api_key` + `X-API-Key` no servidor | **Segurança** | Endpoints sensíveis (`/api/events`, `/api/video/push`) protegidos quando o dashboard não está em localhost. |
| Processamento 100% local + sem upload | **Privacidade**, **Mobilidade**, **Processamento local ou em nuvem** | Vídeo nunca sai do dispositivo; sistema funciona offline; baseline não persiste entre sessões. |
| `MqttSink`, `HttpWebhookSink`, `MjpegStreamPresenter` | **Distribuição entre dispositivos**, **Comunicação em rede**, **Heterogeneidade** | Métricas numéricas podem ser publicadas em broker MQTT/webhook HTTP de uma central de frota. |
| `_DetectorSupervisor` (respawn) + `CompositeSink` (isolamento) | **Tolerância a falhas** | Detector que morre é reiniciado; falha de um sink não afeta os outros. |
| `/api/health` (uptime, video_age, event_age, last_severity) | **Tolerância a falhas**, **Transparência operacional** | Permite monitoramento externo do estado do sistema sem expor detalhes da pipeline. |

**Pontuação esperada** após esta fase: ~92/100 (ver
`docs/UBIQUITY-CHECKLIST.md` §7) — classe "Proposta fortemente
aderente à computação ubíqua".

---

## 10. Aberto pra discussão

1. **Calibração:** começar simples (warmup fixo) ou já entrar com EMA contínua? Proposta: warmup fixo na 2.5a, EMA na 2.5c se necessário.
2. **Fail-safe:** default deve ser `alarm` (paranoico) ou `suppress` (silencioso)? Proposta atual: `alarm`.
3. **Modelo `eye_state` no git:** ~50-200KB cabe sem dor — proposta: commitar direto (reprodutibilidade > limpeza). `drowsiness_cnn` fica fora.
4. **Rampa de som:** 3s é suave demais pra acordar quem dorme? Talvez 1.5s. Decisão pode sair do teste manual.
5. **Sub-fase 2.5d (CNN holística) vale a pena?** Só se 2.5c não bastar. Por padrão fica como nice-to-have.
