# Auto-avaliação — Checklist de Sistema Ubíquo

**Projeto:** Driver Fatigue Detector
**Disciplina:** Software para Sistemas Ubíquos — IFG Câmpus Inhumas
**Data da avaliação:** 2026-04-28
**Branch avaliada:** `feat/fase2-5-falsos-positivos` (após fechamento do pacote de aderência ubíqua)
**Avaliador:** equipe do projeto (auto-avaliação para entrega)

> Este documento responde, item por item, ao checklist da disciplina. Cada
> resposta cita o código, a configuração ou o documento que sustenta a marcação.

---

## 1. Finalidade da proposta

O sistema observa o motorista por meio de uma webcam embarcada no veículo,
extrai indicadores de contexto (EAR — Eye Aspect Ratio, MAR — Mouth Aspect
Ratio, inclinação da cabeça, qualidade do frame), interpreta esses sinais
para detectar fadiga real e dispara, de forma automática e pouco intrusiva,
respostas no ambiente: alarme sonoro com rampa de volume, eventos para um
dashboard local e webhook HTTP/MQTT opcionais para integração com sistemas
de telemetria de frota.

A computação acontece **na borda** (notebook embarcado, SBC ou Raspberry
Pi), sem dependência de internet em runtime e sem upload de imagem. Veja
`docs/ARCHITECTURE.md` para o diagrama de camadas e
`docs/PRIVACY.md` para o tratamento de dados pessoais.

---

## 2. Critérios eliminatórios

| Marcar | Critério eliminatório | Aplica? |
|---|---|---|
| [ ] | É apenas um sistema web, aplicativo mobile ou dashboard sem interação com o ambiente físico. | Não — o detector observa o motorista (rosto/cabeça) via webcam e atua na cabine. |
| [ ] | Não utiliza sensores, atuadores, dispositivos embarcados, dispositivos móveis ou objetos inteligentes. | Não — webcam (sensor visual), alto-falante (atuador sonoro) e webhook/MQTT (atuadores em rede). |
| [ ] | Não coleta nem interpreta contexto. | Não — coleta EAR, MAR, head-yaw, head-pitch, qualidade de frame, baseline pessoal. |
| [ ] | Não possui adaptação automática ou comportamento dependente da situação. | Não — calibração de baseline por sessão e thresholds adaptativos (`CalibrationSettings`). |
| [ ] | Depende exclusivamente de entrada manual do usuário para todas as decisões. | Não — operação 100% autônoma; usuário não interage para detectar nem para alarmar. |
| [ ] | Não há distribuição entre dispositivos, serviços, nuvem, borda ou infraestrutura de comunicação. | Não — detector (processo) → dashboard web (processo) → sinks externos (HTTP/MQTT). |
| [ ] | Não apresenta preocupação com mobilidade, conectividade variável, segurança e privacidade. | Não — projeto pensado para veículo em movimento, com fallback offline e processamento local (`docs/DEPLOYMENT.md`). |

**Resultado da triagem:** zero critérios eliminatórios marcados → proposta segue para análise.

---

## 3. Checklist essencial de caracterização ubíqua

| Critério | Sim | Parcial | Não | Evidência |
|---|:-:|:-:|:-:|---|
| Integração com o ambiente físico | ✅ | | | Cabine do veículo + face do motorista; observação contínua via câmera. |
| Dispositivos distribuídos | ✅ | | | Detector + dashboard web + alto-falante + webhook/MQTT externo. Veja `docs/ARCHITECTURE.md`. |
| Comunicação em rede | ✅ | | | HTTP local (SSE + MJPEG + POST `/api/events`), webhook HTTP externo, MQTT. `infrastructure/alert_sinks/{http_webhook,mqtt}.py`. |
| Sensibilidade ao contexto | ✅ | | | EAR, MAR, head-yaw/pitch, qualidade do frame, baseline pessoal. `domain/value_objects.py`. |
| Interpretação de contexto | ✅ | | | `FatigueEvaluator` + `ContextValidator` (PERCLOS + classificador CNN local de eyes-open/closed). `domain/evaluator.py`, `infrastructure/context_validators/`. |
| Adaptação automática | ✅ | | | Baseline calibrado por sessão (`CalibrationSettings.warmup_frames`); thresholds relativos a `ear_rest`/`mar_rest`; histerese; cooldown. |
| Pró-atividade | ✅ | | | Alarme sonoro, evento para dashboard e webhook disparados sem comando do usuário. |
| Baixa intrusão | ✅ | | | Rampa de volume (`SoundSink.ramp_seconds`), HUD discreto, alarme só em `severity=alert` confirmado pelo validador contextual. |
| Mobilidade | ✅ | | | Roda 100% local em hardware embarcado no veículo; sem dependência de internet em runtime. `docs/DEPLOYMENT.md`. |
| Transparência operacional | ✅ | | | Usuário interage só com dashboard simples; toda a pipeline (MediaPipe → evaluator → ONNX → sinks) é interna. |

**Critério mínimo (≥ 7 Sim, incluindo ambiente físico, contexto, rede e adaptação):** atendido com 10/10.

---

## 4. Checklist técnico-arquitetural

| Critério | Sim | Parcial | Não | Evidência |
|---|:-:|:-:|:-:|---|
| Arquitetura distribuída | ✅ | | | Camadas: sensor (webcam) → núcleo de domínio (Clean Architecture) → adapters (sinks/presenters) → consumidores externos. `docs/ARCHITECTURE.md`. |
| Sensores ou fontes de contexto | ✅ | | | Webcam (`WebcamVideoSource`), arquivo de vídeo (`FileVideoSource`), RTSP (`RtspVideoSource`). |
| Atuadores ou respostas do sistema | ✅ | | | `SoundSink` (alarme com rampa), `HttpWebhookSink`, `MqttSink`, `LogSink`, `JsonlEventSink` (persistência local). |
| Middleware ou integração | ✅ | | | `CompositeSink` faz fan-out com isolamento de falhas; `MonitorDriverUseCase` orquestra ports; servidor web atua como broker SSE local. |
| Persistência de dados | ✅ | | | `JsonlEventSink` (append-only) grava eventos com timestamp, EAR/MAR, baseline e motivo do disparo em `events.jsonl`. |
| Processamento local ou em nuvem | ✅ | | | 100% borda. Decisão consciente (privacidade + custo + autonomia). Documentado em `docs/PRIVACY.md` e `docs/ARCHITECTURE.md`. |
| Escalabilidade | ✅ | | | Modelo ONNX é minúsculo (~50 KB); pipeline cabe em SBC. Para frota: cada veículo é uma instância independente que publica em MQTT/HTTP centralizado. Discutido em `docs/ARCHITECTURE.md` (seção "Escalabilidade"). |
| Tolerância a falhas | ✅ | | | `_DetectorSupervisor` respawn automático; `CompositeSink` isola falhas por sink; `fail_safe_on_error: alarm` no validador; fallback para `NoopContextValidator` se ONNX faltar; loop em arquivo. |
| Segurança | ✅ | | | API key obrigatória em endpoints sensíveis (`/api/events`, `/api/video/push`); webhook HTTP suporta `bearer_token`. `config/default.yaml` (`web.api_key`, `http_webhook.bearer_token`). |
| Privacidade | ✅ | | | Vídeo nunca sai do dispositivo. Baseline anônimo por sessão (não persiste entre execuções). JSONL local guarda só métricas numéricas, sem imagem. `docs/PRIVACY.md`. |

---

## 5. Checklist de experiência do usuário

| Critério | Sim | Parcial | Não | Evidência |
|---|:-:|:-:|:-:|---|
| Interface natural | ✅ | | | Sem interação ativa: motorista dirige, sistema observa. Resposta é sonora (rampa) e visual (dashboard). |
| Usabilidade em contexto real | ✅ | | | Pensado para o ambiente da cabine: HUD discreto, dashboard opcional, alarme físico. `docs/DEPLOYMENT.md`. |
| Relevância situacional | ✅ | | | Alarme só dispara após confirmação contextual (PERCLOS + CNN); calibração filtra falsos positivos por iluminação/anatomia. |
| Controle pelo usuário | ✅ | | | Tudo configurável via `config/*.yaml`: thresholds, validador (noop/eye_state), sinks ativos, cooldown, rampa de som. |
| Baixa sobrecarga cognitiva | ✅ | | | Motorista não precisa configurar nada em uso normal; o sistema age sozinho e silencia quando o estado normaliza (`on_recovery`). |

---

## 6. Checklist de justificativa acadêmica

| Marcar | Elemento | Evidência |
|:-:|---|---|
| ✅ | Qual problema real será resolvido. | Fadiga ao volante — causa relevante de acidentes. Spec da Fase 1 e introdução do artigo (`docs/Artigo_Detector_de_Fadiga__*.pdf`). |
| ✅ | Qual ambiente físico será monitorado. | Cabine do veículo, com foco no rosto do motorista. |
| ✅ | Quais usuários serão beneficiados. | Motoristas profissionais (caminhão, ônibus, aplicativo) e gestores de frota. |
| ✅ | Quais dispositivos / fontes de dados. | Webcam embarcada (sensor), notebook/SBC (processamento), alto-falante (atuador), opcional integração com central via webhook/MQTT. |
| ✅ | Quais informações de contexto. | EAR, MAR, head-yaw, head-pitch, qualidade do frame, baseline pessoal, PERCLOS de 60 s. |
| ✅ | Como o contexto é interpretado. | `FatigueEvaluator` (heurísticas + histerese + cooldown + discriminador fala/bocejo) + `ContextValidator` (CNN local + PERCLOS). |
| ✅ | Como o sistema se adapta automaticamente. | Calibração por sessão (`PersonalBaseline`), thresholds relativos, gate de qualidade que descarta frames não confiáveis. |
| ✅ | Grau de autonomia. | Total: zero input do usuário em runtime; supervisor respawn; fallback para validador noop se modelo faltar. |
| ✅ | Como os componentes distribuídos se comunicam. | HTTP (SSE + MJPEG + POST), MQTT, log local, JSONL. Diagrama em `docs/ARCHITECTURE.md`. |
| ✅ | Riscos de segurança, privacidade e falhas. | API key local, processamento 100% borda, supervisor de detector, isolamento de falhas no `CompositeSink`. Detalhes em `docs/PRIVACY.md` e `docs/DEPLOYMENT.md`. |
| ✅ | Evidência para validar a POC. | `JsonlEventSink` produz log auditável de cada disparo; spec da Fase 2.5 define vídeos de validação manual. |
| ✅ | Diferença em relação a um sistema web/mobile convencional. | (a) percebe ambiente físico via câmera; (b) atua sem comando do usuário; (c) processa na borda; (d) integra heterogêneos via sinks; (e) calibra-se ao usuário. |

---

## 7. Pontuação sugerida

| Dimensão | Máx. | Auto-nota | Justificativa |
|---|:-:|:-:|---|
| Integração com ambiente físico | 10 | 10 | Cabine do veículo + face do motorista, em tempo real. |
| Uso de sensores, atuadores ou dispositivos inteligentes | 10 | 9 | Webcam + alto-falante + dashboard. Falta sensor adicional (ex.: acelerômetro do veículo) — registrado como evolução futura. |
| Sensibilidade e interpretação de contexto | 15 | 14 | EAR/MAR/head-pose + baseline + CNN local + PERCLOS. |
| Adaptação automática e pró-atividade | 15 | 14 | Calibração por sessão, thresholds relativos, alarme automático com rampa. EMA contínua planejada (item 9.1 do spec) ainda não implementada. |
| Arquitetura distribuída e comunicação em rede | 10 | 9 | Detector + dashboard + sinks externos via HTTP/MQTT. Diagrama documentado. |
| Mobilidade, transparência e baixa intrusão | 10 | 9 | Roda offline, HUD discreto, rampa de som. Não temos ainda app mobile companion (não é objetivo). |
| Segurança, privacidade e confiabilidade | 10 | 9 | API key + bearer token + supervisor + processamento local. Falta TLS por padrão (deployment-dependent — documentado). |
| Escalabilidade e heterogeneidade | 10 | 8 | Cada veículo é instância independente; sinks heterogêneos (HTTP/MQTT/log/sound). Backend central de frota está fora do escopo. |
| Clareza da proposta e viabilidade da POC | 10 | 10 | Spec, artigo, código testado e demo executável (`driver-fatigue web`). |
| **Total** | **100** | **92** | — |

| Pontuação | Classificação |
|---|---|
| 0 a 39 | Não caracteriza sistema ubíquo |
| 40 a 59 | Sistema parcialmente ubíquo, mas incompleto |
| 60 a 79 | Proposta ubíqua aceitável |
| **80 a 100** | **Proposta fortemente aderente à computação ubíqua** ← |

---

## 8. Pergunta final de validação

> *O sistema utiliza dispositivos distribuídos e informações de contexto do
> ambiente físico para adaptar seu comportamento de forma automática,
> natural, conectada e pouco intrusiva, oferecendo apoio ao usuário em sua
> rotina?*

**Sim.** O Driver Fatigue Detector observa o motorista por meio de uma
webcam embarcada, calibra-se ao seu padrão pessoal de EAR/MAR no início de
cada sessão, interpreta o contexto (incluindo um classificador CNN local
para confirmar suspeitas) e atua automaticamente — alarme sonoro com
rampa, eventos no dashboard e integrações via webhook/MQTT — sem exigir
nenhum comando do motorista, e sem que dado pessoal (vídeo) saia do
dispositivo.

---

## 9. Observações do avaliador

- **Pontos fortes:** processamento 100% local, calibração por sessão,
  validador contextual com fallback, arquitetura limpa (4 camadas),
  política de privacidade explícita.
- **Limitações conhecidas:** sem identificação de motorista, sem app
  mobile, sem integração com sensores adicionais do veículo (CAN bus,
  acelerômetro). Todas registradas no spec da Fase 2.5 como não-objetivos
  conscientes.
- **Próximos passos (fora do escopo da entrega atual):** EMA contínua do
  baseline; backend central de frota; cliente mobile para visualização
  remota.
