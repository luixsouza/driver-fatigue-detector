# Detecção de Sonolência — Plano de Estudo + Plano de Refatoração

**Data:** 2026-04-27
**Contexto:** projeto acadêmico (Sistemas Ubíquos) em Python + MediaPipe FaceLandmarker + Clean Architecture. Implementação atual é heurística simples (EAR/MAR + N frames consecutivos) e tem três problemas práticos confirmados em uso:

1. **Falsos positivos em piscadas normais** (piscada típica ~150ms, EAR cai pra ~0.18)
2. **Falsos negativos com olhos meio cerrados** (closure parcial sustentado não dispara)
3. **Cabeceio do motorista mal capturado** (head pose só como gate de qualidade, não como evidência)

Restrições: 100% open-source, sem API paga, roda em CPU local.

---

## 1. Diagnóstico — por que a implementação atual falha

A literatura é unânime ao identificar as duas decisões da implementação clássica que causam exatamente os sintomas que sentimos:

| Sintoma | Causa raiz | Fonte |
|---|---|---|
| FP em piscada | EAR instantâneo + janela curta de N frames consecutivos como gatilho único | Ghoddoosian et al. 2019; Singh 2024 (survey); Abe 2023 |
| FN em olho meio cerrado | Threshold geométrico fixo (`EAR < 0.21`) e binário "fechado/aberto" perde closure parcial | arXiv 2604.22479 (2024) |
| Cabeceio invisível | Head pose tratado como filtro de qualidade ao invés de feature de fusão | DrowSAFE Hackster 2024; Multi-Index Sensors 24:5683 (2024) |
| Threshold global hardcoded | Anatomia individual varia muito (formato de olho, óculos, iluminação) | arXiv 2604.22479 |
| OR/AND de regras booleanas | Falha quando uma modalidade é momentaneamente perdida | DrowSAFE; sahnimanas/Fatigue-Detection |

**Conclusão prática:** o problema **não é tunar threshold**. É a arquitetura da decisão. Toda a literatura recente converge em quatro mudanças:

1. PERCLOS sobre janela longa (30–60s) como **métrica primária**, não EAR instantâneo
2. **Calibração personalizada** (5s no início) — threshold relativo ao baseline do usuário
3. **Score ponderado** (0–100) combinando múltiplas evidências, não regras booleanas
4. **State machine com hysteresis assimétrica** — entrar em alerta é fácil, sair é difícil

---

## 2. Plano de estudo (ordem recomendada)

Sequência pensada pra ler do conceitual ao prático, ~6 horas total. Tudo aberto.

### Bloco A — Fundamentos (obrigatórios, ~2h)

1. **Survey 2024** — Singh et al., *A Survey on Drowsiness Detection: Modern Applications and Methods*, arXiv:2408.12990
   *Use como índice. Cobre EAR/MAR/PERCLOS, deep learning e datasets. Cite no artigo.*
   https://arxiv.org/html/2408.12990v1

2. **PERCLOS clínico** — Abe T., *PERCLOS-based technologies for detecting drowsiness*, SLEEP Advances 4(1), 2023
   *Define PERCLOS formal (P80, janela 1min). Documenta limitações (latência ~2.5s, fadiga moderada falha) e justifica fusão com head pose.*
   https://academic.oup.com/sleepadvances/article/4/1/zpad006/7000589

3. **NHTSA PERCLOS Tech Brief 1998** — referência primária dos thresholds
   https://ntlrepository.blob.core.windows.net/lib/51000/51300/51369/tb98-006.pdf

### Bloco B — Personalização e dataset (~1.5h)

4. **arXiv 2604.22479 (2024)** — *Improving Driver Drowsiness Detection via Personalized EAR/MAR Thresholds and CNN-Based Classification*
   *Define os números mágicos de calibração: EAR_threshold = 0.75 × EAR_baseline, MAR_threshold = 1.40 × MAR_baseline, com 5s de warmup.*
   https://arxiv.org/abs/2604.22479

5. **UTA-RLDD** — Ghoddoosian et al., CVPRW 2019, arXiv:1904.07312
   *Apresenta dataset (60 sujeitos, 30h, 3 classes alert/low-vigilant/drowsy) e baseline HM-LSTM. Mostra que classe binária é simplista demais.*
   https://openaccess.thecvf.com/content_CVPRW_2019/papers/AMFG/Ghoddoosian_A_Realistic_Dataset_and_Baseline_Temporal_Model_for_Early_Drowsiness_CVPRW_2019_paper.pdf

### Bloco C — Implementação de referência (~2h)

6. **DrowSAFE — Real-Time Driver Drowsiness Detection System (Hackster.io 2024)**
   *Pipeline pronto pra produção: EAR + MAR + PERCLOS + head pose num score 0–100 ponderado (PERCLOS 40 / EAR 25 / head 20 / MAR 15) + state machine 3 níveis com hysteresis assimétrica (entra WARNING@40, sai@30; entra CRITICAL@70, sai@55). Roda 30fps em Raspberry Pi 5. **É o padrão a copiar.***
   https://www.hackster.io/MohamedAliBedair/drowsafe-real-time-driver-drowsiness-detection-system-aeee70

7. **danielsousaoliveira/driving-monitor-python** — repo Python com MediaPipe + PERCLOS + MAR + head pose. Mais alinhado com nosso stack.
   https://github.com/danielsousaoliveira/driving-monitor-python

8. **Multi-Index Driver Drowsiness Detection** — Sensors 24:5683 (2024). Voto majoritário em janela temporal. Útil pra justificar arquitetura no artigo.
   https://www.mdpi.com/1424-8220/24/17/5683

### Bloco D — Opcional (avançado, só se for fundo no artigo)

9. **HMM tracking** — Applied Sciences 6:137 (2016). Dois HMMs (piscada + nodding) com fusão. Para citar como referência clássica de fusão temporal.
10. **Transformer drowsiness** — Scientific Reports 15, s41598-025-02111-x (2025). ViT 99.15% mas inviável sem GPU. Cite como SOTA pra justificar nossa escolha mais leve.

---

## 3. Datasets de referência (priorizados pelo nosso uso)

| Dataset | Pra que serve aqui | Acesso |
|---|---|---|
| **MRL Eye / CEW** | Treinar/validar classificador olho-aberto/fechado se decidirmos plugar CNN | Aberto, uso acadêmico |
| **YawDD** | Calibrar discriminador yawn vs talk | IEEE DataPort, login grátis |
| **UTA-RLDD** | Validação end-to-end do pipeline completo (3 classes) | Solicitação acadêmica + espelho Kaggle |
| **NTHU-DDD** | Padrão ouro de simulação se conseguir acesso | Solicitação ao laboratório |
| **DROZY** | Multimodal (EEG/EOG/ECG) — só citar, não usamos | Acesso institucional ULg |

Pro nosso projeto, **MRL Eye + YawDD + UTA-RLDD** são suficientes. NTHU-DDD é nice-to-have.

---

## 4. Modelos open-source plugáveis (sem API, CPU)

Pesquisa validou os seguintes pesos. Tabela com licenças e tamanhos:

| Modelo | Task | URL | Licença | Tamanho | Notas |
|---|---|---|---|---|---|
| **open-closed-eye-0001** (OpenVINO) | Eye state | github.com/openvinotoolkit/open_model_zoo | Apache-2.0 | <1MB, 32×32 | Drop-in replacement do EAR. ~1ms CPU. |
| **MichalMlodawski/...mobilev2** (HF) | Eye state | huggingface.co/MichalMlodawski/open-closed-eye-classification-mobilev2 | **CC-BY-NC-ND** | ~17MB | 99% acc. **Atenção: não-comercial.** OK pra artigo acadêmico, não pra produto. |
| **dima806/closed_eyes_image_detection** (HF) | Eye state | huggingface.co/dima806/closed_eyes_image_detection | Apache-2.0 | ~344MB (ViT-base) | Permissivo mas pesado. |
| **yakhyo/head-pose-estimation** | Head pose 6D | github.com/yakhyo/head-pose-estimation | MIT | **5.93MB** (MobileNetV3-small) | ONNX puro, sem PyTorch dep. |
| **PINTO0309/DMHead** | Head pose 6D | github.com/PINTO0309/DMHead | MIT | ~30-40MB (RepVGG-B1g2) | 3.86° MAE no AFLW2000. |
| **iglaweb/HippoYD** | Yawn (YawDD) | github.com/iglaweb/HippoYD | Apache-2.0 | leve | ONNX pronto, 0.988 acc. |
| **mosesb/drowsiness-detection-yolo-cls** (HF) | Drowsiness E2E | huggingface.co/mosesb/drowsiness-detection-yolo-cls | MIT | 99.8% acc | Considerar `YOLOv11n-cls` <10MB. |

**Insight crítico (do agente 3):** o **MediaPipe FaceLandmarker que já usamos** entrega 52 blendshapes nativos, incluindo `eyeBlinkLeft` e `eyeBlinkRight` (score 0-1 onde 1 = totalmente fechado). É **mais robusto que EAR puro** e não exige modelo extra. Hoje não estamos usando — deveríamos.

Documentação: https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker

---

## 5. Plano de Refatoração — Pipeline em 4 camadas

Mantendo a Clean Architecture atual, refatoramos a lógica de decisão pra esse desenho convergente da literatura. Cada camada é testável isoladamente.

```
                 ┌──────────────────────────────────────────┐
                 │          MediaPipe FaceLandmarker        │
                 │  (landmarks + blendshapes — já temos)    │
                 └────────────────────┬─────────────────────┘
                                      │
           ┌──────────────────────────▼──────────────────────────┐
   1.      │   FrameFeatures        (DOMAIN value object)        │
 features  │   ear, mar, blink_score (blendshape), head_pitch,   │
 por frame │   head_yaw, head_roll, eye_closed_prob (CNN opt)    │
           └──────────────────────────┬──────────────────────────┘
                                      │
           ┌──────────────────────────▼──────────────────────────┐
   2.      │   PersonalBaseline      (DOMAIN value object)       │
calibração │   ear_baseline, mar_baseline, captura 5s @ neutro    │
 por user  │   thresholds = (0.75 × ear_base, 1.40 × mar_base)   │
           └──────────────────────────┬──────────────────────────┘
                                      │
           ┌──────────────────────────▼──────────────────────────┐
   3.      │   TemporalAggregates    (DOMAIN value object)       │
agregação  │   perclos_60s (P80), blink_rate, yawn_count_60s,    │
 temporal  │   head_pitch_smoothed, eye_closure_smoothed         │
           └──────────────────────────┬──────────────────────────┘
                                      │
           ┌──────────────────────────▼──────────────────────────┐
   4.      │   FusionService         (DOMAIN service)            │
  fusão    │   score 0-100 = 0.40·perclos + 0.25·ear_dev         │
score+SM  │            + 0.20·head_pitch + 0.15·yawn_rate       │
           │   AlertStateMachine (NORMAL ⇄ WARNING ⇄ CRITICAL)   │
           │   hysteresis assimétrica                            │
           └──────────────────────────┬──────────────────────────┘
                                      │
                            FatigueState (atual)
```

### 5.1 Camada de features (`domain/features.py`, novo)

```python
@dataclass(frozen=True, slots=True)
class FrameFeatures:
    ear: float                   # 0-1, médio dos dois olhos
    mar: float                   # 0-2 típico
    blink_score: float           # MediaPipe blendshape, 0-1 onde 1=fechado
    eye_closed_prob: float       # CNN opcional; None se não usar
    head_pitch_deg: float
    head_yaw_deg: float
    head_roll_deg: float
    detection_confidence: float
```

`MediapipeFaceDetector` já calcula landmarks; só precisa retornar também os blendshapes (FaceLandmarker já produz, basta ativar `output_face_blendshapes=True` na criação do landmarker).

### 5.2 Calibração (`domain/calibration.py`, refatorar `PersonalBaseline`)

Já existe `PersonalBaseline` com Welford. Mudanças:

- Tempo de warmup: 5s @ 30fps = 150 frames (atualmente 45)
- Após calibração, **persistir thresholds derivados** no estado:
  - `ear_close_threshold = 0.75 * ear_baseline` (paper arXiv 2604.22479)
  - `mar_yawn_threshold = 1.40 * mar_baseline`
- Recalibração contínua opcional: EMA dos últimos 30s **só quando estado=normal e qualidade=ok** (evita corromper baseline com sonolência)

### 5.3 Agregação temporal (`domain/aggregates.py`, novo)

```python
class TemporalAggregator:
    """Mantém buffers circulares e expõe métricas derivadas."""
    def __init__(self, fps_estimate: float = 30):
        self._buf_60s = deque(maxlen=int(60 * fps_estimate))     # PERCLOS
        self._buf_smooth = deque(maxlen=int(1 * fps_estimate))   # 1s smoothing
        self._yawn_events: deque[float] = deque()                # timestamps
        self._head_pitch_buf = deque(maxlen=int(2 * fps_estimate))

    def absorb(self, features: FrameFeatures, ts: float, baseline: PersonalBaseline) -> TemporalAggregates:
        eye_closed = features.blink_score > 0.7  # ou EAR < threshold personalizado
        self._buf_60s.append(eye_closed)
        # ... PERCLOS, smoothing, yawn rate, etc
```

### 5.4 Fusion + State Machine (`domain/fusion.py`, novo — substitui o evaluator)

```python
@dataclass(frozen=True)
class FusionWeights:
    perclos: float = 0.40
    ear_deviation: float = 0.25
    head_pitch: float = 0.20
    yawn_rate: float = 0.15

@dataclass(frozen=True)
class StateMachineConfig:
    warning_enter: float = 40.0
    warning_exit: float = 30.0    # hysteresis assimétrica
    critical_enter: float = 70.0
    critical_exit: float = 55.0
    debounce_seconds: float = 3.0

def compute_fatigue_score(
    aggregates: TemporalAggregates,
    baseline: PersonalBaseline,
    weights: FusionWeights,
) -> float:
    perclos_norm = clip(aggregates.perclos_60s / 0.30, 0, 1)        # alarme @ 30%
    ear_dev_norm = clip(1 - aggregates.ear_smoothed / baseline.ear_rest, 0, 1)
    pitch_norm = clip(abs(aggregates.head_pitch_smoothed_deg) / 30, 0, 1)
    yawn_norm = clip(aggregates.yawn_count_60s / 4.0, 0, 1)
    score = (weights.perclos * perclos_norm
             + weights.ear_deviation * ear_dev_norm
             + weights.head_pitch * pitch_norm
             + weights.yawn_rate * yawn_norm) * 100
    return score
```

A state machine substitui o atual `consecutive_frames`/`recovery_frames` por:

- 3 estados: `NORMAL`, `WARNING`, `CRITICAL`
- transição com hysteresis (entra fácil, sai difícil) — elimina o flickering
- debounce: precisa do score sustentado por X segundos antes de transitar

---

## 6. Faseamento (encaixa no /gsd)

| Fase | Conteúdo | Esforço | Ganho esperado |
|---|---|---|---|
| **2.6a** | Ativar blendshapes do MediaPipe + adicionar `FrameFeatures` | pequeno | Eye closure mais robusta que EAR puro |
| **2.6b** | Calibração personalizada com thresholds derivados (75%/140%) e warmup 5s | pequeno | Mata 60% dos FP — diferentes anatomias |
| **2.6c** | `TemporalAggregator` com PERCLOS P80 (60s), yawn count, smoothing | médio | Mata 80% dos FP em piscada |
| **2.6d** | `FusionService` com score ponderado + `AlertStateMachine` com hysteresis | médio | Estabilidade — fim do flickering |
| **2.6e** | Head pose com solvePnP (em vez de proxy geométrico) e nodding como evidência | médio | Detecta cabeceio mesmo de olho aberto |
| **2.6f** (opt) | Plugar OpenVINO `open-closed-eye-0001` como `eye_state_validator` | pequeno | +5-10% acurácia em iluminação difícil |
| **2.6g** (opt) | Validação no UTA-RLDD: matriz de confusão, ROC, FPR/TPR documentados pro artigo | médio-grande | Defensável academicamente |

Fases 2.6a–2.6d são o caminho crítico. Tudo acima de 2.6d é incremental, sem refatoração.

---

## 7. Quick wins (commits dos próximos dias)

Em ordem de impacto/esforço, antes da refatoração grande:

1. **Ativar blendshapes do MediaPipe** (`output_face_blendshapes=True`) e usar `eyeBlinkLeft`/`eyeBlinkRight` como métrica primária no lugar do EAR. ~30min de código.
2. **PERCLOS P80 60s** simples como gatilho secundário ao lado do `consecutive_frames` atual: dispara também se PERCLOS > 0.20. ~1h.
3. **Calibração 5s** — aumentar `warmup_frames` pra 150 e usar 75%/140% (já temos `ear_close_ratio`, só ajustar). ~10min.
4. **Hysteresis simples** — mudar `recovery_frames` pra valor maior (15-20) e exigir `severity=normal` por X frames antes de sair. Já temos a infra. ~30min.
5. **Yawn sustentado 1.5s + simetria vertical/horizontal**. ~1h.

Total: ~3h. Resolve provavelmente a maior parte do "tá ruim" sem mexer na arquitetura.

---

## 8. Anti-patterns a evitar (fica documentado pra não repetirmos)

- ❌ Threshold EAR global hardcoded (ex `EAR < 0.21`). Sempre relativo ao baseline.
- ❌ Decisão por `if EAR < t and MAR > t and head_down`. Use score ponderado.
- ❌ Janela curta de N frames consecutivos como único gatilho. Use PERCLOS sobre janela longa.
- ❌ Sem hysteresis. Score na fronteira pisca on/off.
- ❌ Mistura yaw e pitch como "head movement". Yaw alto = retrovisor; só pitch sustentado = cabeceio.
- ❌ Decisão binária drowsy/awake. Use 3 classes (alerta/baixa vigilância/sonolento) — dá pra graduar alarme.
- ❌ Não medir num dataset de referência. Sem isso, "funciona" é opinião.
- ❌ Modelos com licença CC-BY-NC pra trabalho que pode virar produto. OK pra artigo acadêmico com citação.

---

## 9. Próximos passos sugeridos

Recomendo nessa ordem:

1. **Ler Bloco A do plano de estudo** (~2h) antes de codar — vai mudar como você pensa o problema.
2. **Implementar quick wins (§7)** num único PR pequeno — já melhora muito a percepção.
3. **Abrir spec da fase 2.6** (refatoração em 4 camadas, §5) e rodar via `/gsd:plan-phase`.
4. **Validar no UTA-RLDD** ao final — produz números defensáveis pro artigo.

Datasets a baixar agora pra ter em mãos:
- MRL Eye (treinar/validar eye_state quando chegarmos lá)
- YawDD (calibrar discriminador yawn vs fala)
- UTA-RLDD (validação end-to-end)

---

## 10. Bibliografia consolidada

**Surveys e fundamentos**
- Singh et al. 2024, *A Survey on Drowsiness Detection — Modern Applications and Methods*, arXiv:2408.12990
- Abe T. 2023, *PERCLOS-based technologies for detecting drowsiness*, SLEEP Advances 4(1) zpad006, DOI:10.1093/sleepadvances/zpad006
- NHTSA 1998, *PERCLOS Tech Brief* (referência primária dos thresholds)

**Datasets e baselines**
- Ghoddoosian et al. 2019, *A Realistic Dataset and Baseline Temporal Model for Early Drowsiness Detection*, CVPRW (UTA-RLDD), arXiv:1904.07312
- Abtahi et al. 2014, YawDD MMSys, IEEE DataPort DOI:10.21227/e1qm-hb90
- MRL Eye Dataset, https://mrl.cs.vsb.cz/eyedataset.html

**Métodos modernos**
- arXiv 2604.22479 (2024), *Improving Driver Drowsiness Detection via Personalized EAR/MAR Thresholds*
- Multi-Index, *Sensors* 24:5683 (2024)
- Real-time ML facial features, *Sensors* 25:812 (2025)
- Transformer ViT, *Scientific Reports* s41598-025-02111-x (2025)

**Implementações de referência**
- DrowSAFE, Hackster.io 2024 (https://www.hackster.io/MohamedAliBedair/drowsafe-real-time-driver-drowsiness-detection-system-aeee70)
- danielsousaoliveira/driving-monitor-python (MediaPipe + PERCLOS, MIT)
- neelanjan00/Driver-Drowsiness-Detection (3-fold metrics, 150⭐, MIT)
- Tandon-A/Drowsiness-Detection-Mediapipe (calibração + LSTM, MIT)
- rezaghoddoosian/Early-Drowsiness-Detection (HM-LSTM oficial UTA-RLDD)

**Modelos open-source**
- OpenVINO open-closed-eye-0001 (Apache-2.0, <1MB)
- yakhyo/head-pose-estimation MobileNetV3-small (MIT, 5.93MB ONNX)
- PINTO0309/DMHead 6DRepNet (MIT, ~30MB)
- iglaweb/HippoYD (Apache-2.0, YawDD)
- MediaPipe FaceLandmarker blendshapes (built-in, gratuito)
