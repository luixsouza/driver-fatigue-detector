# Política de Privacidade — Driver Fatigue Detector

**Versão:** 1.0 — 2026-04-28
**Aplicável a:** todas as instalações deste software, em qualquer veículo
ou ambiente.

> Este documento descreve, de forma explícita, **o que é coletado, onde
> fica, quem acessa e o que nunca acontece** com os dados gerados pelo
> Driver Fatigue Detector. Foi pensado para responder ao critério
> "Privacidade" do checklist da disciplina Software para Sistemas
> Ubíquos e para servir de base de consentimento informado caso o
> sistema seja instalado em um veículo real.

---

## 1. Princípios

1. **Processamento 100% local (edge).** Toda a inferência (MediaPipe,
   evaluator de domínio, classificador ONNX de eyes-open/closed) roda
   na máquina onde o sistema está instalado. Nenhum frame de vídeo
   trafega pela internet em runtime.
2. **Minimização.** Só coletamos o que é necessário para detectar
   fadiga: indicadores numéricos derivados (EAR, MAR, head-yaw,
   head-pitch, qualidade do frame). O frame original é **descartado em
   memória** após ser processado.
3. **Sem identificação.** O sistema não tenta identificar o motorista.
   O baseline (`PersonalBaseline`) é **calibrado por sessão** e **não
   persiste** entre execuções — toda nova execução começa em
   calibração zerada.
4. **Transparência.** Este documento, o `docs/ARCHITECTURE.md` e o
   código-fonte completo (open-source) descrevem com precisão tudo
   que acontece.
5. **Controle do operador.** Todos os destinos opcionais (webhook
   HTTP, MQTT, dashboard remoto, JSONL persistente) são **desligados
   por padrão** ou exigem configuração explícita em
   `config/default.yaml`.

---

## 2. O que é coletado

### 2.1 Em memória (volátil, descartado a cada frame)

- Frame da webcam (matriz numpy de pixels).
- Landmarks faciais retornados pelo MediaPipe (468 pontos 3D).
- Crops dos olhos (apenas quando o validador `eye_state` está ativo).

Esses dados existem **apenas durante o processamento de cada frame**
e são sobrescritos pelo frame seguinte. Não são gravados em disco em
nenhuma circunstância.

### 2.2 Em disco (persistente, configurável)

| Dado | Onde | Quando | Como desligar |
|---|---|---|---|
| Métricas numéricas dos eventos (EAR, MAR, severidade, motivo) | `events.jsonl` (configurável) | Apenas se `JsonlEventSink` estiver no `sinks` | Remover `jsonl` da lista `sinks` em `config/*.yaml` |
| Vídeo gravado (`mp4`) | Caminho em `recording.path` | Apenas se `recording.path` estiver definido | Manter `recording.path: null` (default) |
| Logs textuais | `stderr` / arquivo de log do sistema | Sempre (apenas mensagens, sem imagem) | Reduzir nível de log via `--quiet` |

### 2.3 Em rede (configurável, sempre opcional)

| Destino | Tipo de dado | Como desligar |
|---|---|---|
| Dashboard local (`MjpegStreamPresenter`) | Frames JPEG anotados via HTTP MJPEG no localhost | Não usar `driver-fatigue web`, ou rodar com `dashboard_stream.enabled: false` |
| Webhook HTTP (`HttpWebhookSink`) | JSON com métricas numéricas (sem imagem) | Não definir `http_webhook` em `config/*.yaml` |
| MQTT (`MqttSink`) | JSON com métricas numéricas (sem imagem) | Não definir `mqtt` em `config/*.yaml` |

**Em nenhuma configuração suportada** o sistema envia imagem do
motorista para fora do dispositivo. O dashboard local serve MJPEG
**na própria máquina** (localhost) por padrão.

### 2.4 O que NUNCA é coletado

- Identidade biométrica do motorista (nenhum embedding facial
  persistido, nenhuma comparação com base de identificação).
- Áudio do ambiente.
- Localização GPS (o sistema não tem componente de geolocalização).
- Conteúdo de telas, mensagens ou qualquer outro app do dispositivo.
- Dados de navegação/internet.

---

## 3. Quem tem acesso

- **Operador local da máquina** — administra o `config/*.yaml` e tem
  acesso ao `events.jsonl` se ele estiver habilitado.
- **Consumidores de webhook/MQTT/dashboard remoto** — apenas se o
  operador local configurar essas integrações. Nesse caso, o dado
  enviado é **apenas numérico** (vide §2.3).

Nenhum desenvolvedor do projeto, nenhum servidor de telemetria
hospedado por nós, nenhuma API de terceiros recebe dado em runtime.
O projeto não opera nenhum serviço remoto.

---

## 4. Segurança das integrações opcionais

Quando o operador habilita endpoints em rede:

- **Dashboard local (`driver-fatigue web`):** os endpoints sensíveis
  (`POST /api/events`, `POST /api/video/push`) exigem o header
  `X-API-Key` se `web.api_key` estiver configurado. O detector
  embarcado é configurado com a mesma chave. Recomenda-se ligar `api_key`
  sempre que o servidor não estiver restrito a `host: 127.0.0.1`.
- **Webhook HTTP:** suporta `bearer_token`. Recomenda-se URL HTTPS
  para destinos fora da rede local.
- **MQTT:** suporta `username`/`password`. Recomenda-se broker com
  TLS quando aplicável.

A camada de transporte (TLS, VPN, rede interna) é responsabilidade
da infraestrutura na qual o sistema é instalado — o software em si
não impõe nem proíbe TLS.

---

## 5. Retenção

- Frames em memória: descartados frame a frame (segundos).
- `events.jsonl`: append-only, retenção definida pelo operador
  (rotacionar com `logrotate` ou similar). Default: sem rotação.
- Vídeo gravado: só existe se `recording.path` estiver definido;
  retenção definida pelo operador.
- Logs textuais: gerenciados pelo sistema operacional do operador.

---

## 6. Consentimento

O Driver Fatigue Detector é uma ferramenta de software. O **operador
que instala o sistema em um veículo é responsável** por:

1. Informar o motorista de que a câmera está observando-o.
2. Obter consentimento informado para a finalidade (segurança contra
   fadiga) e para os destinos configurados (dashboard local, webhook,
   MQTT).
3. Documentar a base legal aplicável (LGPD: legítimo interesse de
   segurança no trabalho, consentimento, ou outra base apropriada).

O consentimento padrão recomendado deve cobrir, no mínimo:

- Que a câmera capta imagem do motorista durante a condução.
- Que a imagem é processada localmente e descartada frame a frame.
- Que apenas métricas numéricas (EAR/MAR/severidade) podem ser
  enviadas a um sistema central, e quais são esses destinos.
- Que o motorista pode solicitar acesso, correção ou exclusão dos
  registros gerados a seu respeito (cabíveis sob LGPD/GDPR).

---

## 7. Decisões conscientes (trade-offs)

| Decisão | Por quê |
|---|---|
| Não identificar o motorista | Evita transformar o sistema em ferramenta de vigilância pessoal; minimiza dado sensível. |
| Baseline por sessão (não persistente) | Cada motorista pode usar o mesmo veículo sem que dados anteriores influenciem; também evita acúmulo de dado biométrico. |
| Sem criptografia em repouso do `events.jsonl` | O arquivo só contém métricas numéricas anônimas; criptografia é responsabilidade do disco/SO do operador. |
| Sem TLS forçado nos sinks | Pode rodar em rede local segura sem PKI; quando público, operador configura TLS no proxy/broker. |
| Sem upload de modelo | Modelos ONNX são versionados no repo (com hash) — operador sabe exatamente o que está rodando. |

---

## 8. Como auditar

1. O código-fonte está aberto: toda escrita de disco passa por
   `infrastructure/alert_sinks/` ou `infrastructure/presenters/`.
2. Toda chamada de rede passa por `HttpWebhookSink`, `MqttSink` ou
   `MjpegStreamPresenter`. Inspeção via `grep -R 'httpx\|paho\|requests'`.
3. O `JsonlEventSink` é a única fonte de persistência de eventos —
   inspecionar `events.jsonl` mostra exatamente o que foi gravado.
4. `--verbose` no CLI faz cada decisão (gate de qualidade,
   calibração, validação contextual) ser logada.
