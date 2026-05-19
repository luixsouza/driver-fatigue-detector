# Deployment — Driver Fatigue Detector

**Versão:** 1.0 — 2026-04-28
**Aplicável a:** instalação do detector em ambiente real (cabine de
veículo, sala de simulação, bancada acadêmica).

> Este documento responde aos critérios "Mobilidade", "Tolerância a
> falhas", "Escalabilidade" e "Processamento local ou em nuvem" do
> checklist da disciplina, de forma operacional. Para o desenho da
> arquitetura veja `docs/ARCHITECTURE.md`; para tratamento de dados
> pessoais veja `docs/PRIVACY.md`.

---

## 1. Cenários de implantação

### 1.1 Bancada acadêmica (default da POC)

Notebook do estudante, webcam embutida, demo via `driver-fatigue web`
acessível em `http://localhost:8000`. Sem rede externa, sem auth.

```bash
pip install -e .
driver-fatigue web --port 8000
# → abre browser em http://localhost:8000
```

### 1.2 Veículo com notebook embarcado (cenário ubíquo)

Notebook fixado na cabine, webcam USB voltada para o motorista,
alto-falante interno do notebook como atuador. Conectividade
intermitente (4G/5G via roteador veicular ou hotspot do celular).

```bash
driver-fatigue run \
    --config config/vehicle.yaml \
    --headless \
    --context-validator eye_state
```

`config/vehicle.yaml` típico:

```yaml
source:
  kind: webcam
  index: 0

headless: true
sinks: [sound, log, jsonl]   # sem dashboard remoto

jsonl:
  path: /var/log/driver_fatigue/events.jsonl

context_validator:
  kind: eye_state
  fail_safe_on_error: alarm
```

### 1.3 SBC (Raspberry Pi 4 / similar)

Mesma configuração do 1.2, mas com escolhas extras de performance:

- Manter `theme.glow_enabled: false` e `headless: true` (sem janela
  OpenCV).
- Usar `EyeStateContextValidator` (modelo ~50 KB; <5 ms em CPU ARM).
- Não habilitar `drowsiness_cnn` (mais pesado).
- Monitorar termal: alarme contínuo do MediaPipe pode aquecer a SBC
  em ambiente fechado — usar dissipador.

### 1.4 Frota com central de telemetria

Cada veículo roda independente como em 1.2, publicando em MQTT:

```yaml
sinks: [sound, log, jsonl, mqtt]

mqtt:
  broker: telemetria.frota.example
  port: 8883       # TLS
  topic: fleet/${VEHICLE_ID}/fatigue
  username: ${MQTT_USER}
  password: ${MQTT_PASS}
```

Backend central (fora do escopo deste repo) consome o tópico,
deduplica eventos por `frame_index`/`timestamp` e alimenta o
dashboard de frota.

---

## 2. Mobilidade e conectividade variável

O sistema foi projetado para **operar com ou sem conectividade**:

| Situação | Comportamento |
|---|---|
| Sem internet (túnel, área rural) | Detector segue normal: alarme local (sound/log/jsonl) funciona. Webhook/MQTT acumulam falhas no log e seguem tentando o próximo evento (não fazem retry com fila — entrega "best effort"). |
| Wi-Fi caiu | Igual ao acima. Sinks de rede falham silenciosamente (`HttpWebhookSink._post` captura `httpx.HTTPError`). |
| Webcam USB desconectou | Detector morre; supervisor (`_DetectorSupervisor`) respawn em 2 s. Quando webcam volta, processo sobe. |
| Bateria baixa do notebook | Fora do escopo do software. Recomenda-se UPS pequeno ou alimentação 12V do veículo. |
| Mudança de motorista no meio da rota | Recalibrar reiniciando o detector (Ctrl+C ou supervisor). Baseline é por sessão, então o novo motorista é calibrado em ~2 s. |

**Importante:** o detector **nunca depende de internet em runtime**.
A única rede usada por padrão é o `localhost` (dashboard ↔ detector).
Tudo que sai do dispositivo é configuração explícita do operador.

---

## 3. Tolerância a falhas — checklist operacional

| Falha | Sintoma visível | Ação automática | Ação manual recomendada |
|---|---|---|---|
| Detector trava | Dashboard mostra `video_age_seconds` crescente | Supervisor mata e respawn em 2 s | Verificar log; se persistir, atualizar driver da câmera |
| Webcam ocupada por outro processo | `WebcamVideoSource` falha ao abrir | Supervisor faz backoff exponencial até 30 s | Liberar a câmera (Zoom/Teams/etc) |
| MediaPipe sem GPU/sem libs | Inicialização falha | Não há fallback automático | Reinstalar `mediapipe`; verificar `pip install -e .` |
| Modelo ONNX faltando | Log: `EyeStateContextValidator indisponivel` | Fallback para `NoopContextValidator` (alarme dispara só por heurística) | Rodar `python scripts/download_models.py` ou commitar o `.onnx` |
| Disco cheio (JSONL crescendo) | `JsonlEventSink` lança erro de I/O | `CompositeSink` isola; outros sinks seguem | Configurar `logrotate` no `events.jsonl` |
| Webhook externo fora do ar | Log: `webhook falhou: ConnectError` | Próximo evento tenta de novo; nada é enfileirado | Considerar `MqttSink` se entrega garantida importar |
| MQTT broker rejeita auth | Log de erro do paho | Sink falha por evento; seguir | Conferir credenciais |

---

## 4. Persistência local (auditoria)

`JsonlEventSink` grava cada `notify`/`on_recovery` em append-only.
Formato (uma linha JSON por evento):

```json
{"event":"fatigue_alert","timestamp":1714294583.12,"frame_index":10523,"ear":0.18,"mar":0.42,"severity":"alert","baseline_ear":0.31,"baseline_mar":0.18,"calibrated":true,"reason":"ctx_confirmed"}
{"event":"fatigue_recovery","timestamp":1714294591.07,"frame_index":10760}
```

Útil para:

- Evidência de validação da POC (relatório acadêmico).
- Auditoria pós-incidente ("o sistema disparou às 14:23 — por quê?").
- Alimentação de análises offline (notebook Jupyter, pandas).

Recomendação de retenção: rotacionar diariamente com `logrotate`,
manter 30 dias localmente, fazer upload manual do que interessa
(privacidade preservada — só métricas numéricas).

---

## 5. Configuração mínima de segurança

Para qualquer cenário com servidor web acessível além do localhost:

```yaml
web:
  host: 0.0.0.0
  port: 8000
  api_key: ${DRIVER_FATIGUE_API_KEY}   # obrigatório fora do localhost
```

Detector é injetado com a mesma chave (via env var ou flag `--api-key`).
Sem isso, qualquer um na rede local pode envenenar o stream do
dashboard. Veja `docs/PRIVACY.md` §4.

Para webhook externo:

```yaml
http_webhook:
  url: https://central.frota.example/fatigue
  bearer_token: ${WEBHOOK_BEARER_TOKEN}
  timeout_seconds: 3.0
```

Sempre HTTPS quando o destino estiver fora da rede local.

---

## 6. Validação manual (smoke test pós-deploy)

Após instalar em qualquer cenário, rodar este checklist:

1. ✅ `driver-fatigue run --help` mostra todas as flags.
2. ✅ Iniciar detector — log mostra "calibrando baseline"; após ~2 s,
   "baseline calibrado: ear_rest=0.XX, mar_rest=0.XX".
3. ✅ Fechar olhos por ≥ 1 s → alarme dispara com rampa.
4. ✅ Abrir olhos → alarme silencia em ≤ 0.3 s.
5. ✅ Falar / cantar (boca aberta com variação) → **nenhum** alarme.
6. ✅ Virar cabeça pra checar retrovisor → HUD mostra "skip" e
   nenhum alarme dispara.
7. ✅ Conferir `events.jsonl` (se habilitado) — uma linha por
   `notify`/`on_recovery`.
8. ✅ Se webhook habilitado, conferir endpoint recebendo payload.
9. ✅ Matar o processo do detector com `kill` — supervisor respawn
   em ≤ 2 s (cenário com `driver-fatigue web`).

---

## 7. Por que **não** rodamos em nuvem

O processamento do vídeo é deliberadamente local. Razões:

1. **Privacidade.** Imagem do motorista nunca sai do veículo.
2. **Latência.** Alarme precisa disparar em < 1 s; round-trip para
   nuvem em 4G/5G é instável.
3. **Custo.** Inferência GPU em nuvem para frota é cara; o modelo
   local custa zero por inferência.
4. **Autonomia.** Em túnel/área rural sem conectividade, o sistema
   continua funcionando.

A nuvem entra apenas (opcionalmente) como **destino agregador**
para métricas numéricas via MQTT/HTTP — nunca para inferência.

---

## 8. Hardware mínimo recomendado

| Componente | Mínimo | Recomendado |
|---|---|---|
| CPU | x86_64 dual-core 1.5 GHz ou ARM Cortex-A72 | Quad-core 2 GHz |
| RAM | 2 GB | 4 GB |
| Webcam | 480p @ 15 fps | 720p @ 30 fps (HD) |
| Armazenamento | 200 MB livres | 1 GB (com `events.jsonl` rotativo) |
| Áudio | Saída para alto-falante | Alto-falante dedicado da cabine |

Testado em: notebook Intel i5 8ª geração + webcam HD interna.
Compatível em teoria com Raspberry Pi 4 + USB cam (não testado
nesta entrega — registrado como evolução futura).
