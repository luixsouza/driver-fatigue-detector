# Spec: Artigo SOLID e Sistemas Ubíquos

**Data:** 2026-05-19
**Disciplina:** Arquitetura de Software — IFG, Bacharelado em Engenharia de Software
**Atividade:** Aplicação dos Princípios SOLID — Arquitetura e Sistemas Ubíquos
**Sistema-alvo:** Driver Fatigue Detector (este repositório)

---

## 1. Objetivo

Produzir um artigo técnico-científico em PDF de **no máximo 6 páginas** (formato SBC, duas colunas, fonte serifada 10 pt) aplicando os cinco princípios SOLID à arquitetura do nosso detector de fadiga, atendendo às quatro partes exigidas pela atividade:

1. Diagnóstico arquitetural (mapa de componentes + tabela de pontos sensíveis).
2. Aplicação dos cinco princípios SOLID ancorada em aspectos concretos do sistema.
3. Arquitetura consolidada + 3 ADRs.
4. Reflexão crítica sobre SOLID em sistemas ubíquos.

A entrega inclui também slides para apresentação oral (15 min + 5 min de arguição) — escopo deste spec é o **artigo**; os slides serão derivados posteriormente.

## 2. Contexto e narrativa adotada

**Narrativa híbrida:** o artigo menciona brevemente (≈1 parágrafo na Introdução) que o sistema evoluiu de uma versão monolítica anterior (referência ao artigo anterior do grupo, em estilo OpenCV+dlib+Pygame num único script), mas o foco do diagnóstico (Parte I) e da aplicação (Parte II) é a arquitetura atual já refatorada em camadas Clean (`domain`/`application`/`infrastructure`/`interfaces`).

Isso preserva contraste antes/depois sem precisar reescrever a história inteira do projeto. As "soluções ingênuas" descritas em cada princípio na Parte II referenciam padrões concretos do código monolítico anterior (ex.: `dlib.get_frontal_face_detector()` chamado direto no loop principal).

**Autores:** mesmos três do artigo anterior do grupo (Julliely S. Silva, Luis Eduardo S. Teles, Luis Felipe H. Penariol). Confirmar no momento da redação.

## 3. Estrutura do artigo (≤ 6 páginas)

Seguindo a distribuição sugerida pela atividade:

| Seção | Páginas | Conteúdo |
|-------|---------|----------|
| Título + autores + abstract/resumo + palavras-chave | 0,5 | Português + inglês, 100–150 palavras cada |
| 1. Introdução | 0,5 | Contexto do detector de fadiga, motivação para aplicar SOLID na refatoração, objetivos |
| 2. Fundamentação teórica | 0,5 | Sistemas ubíquos (Weiser, Satyanarayanan, Araujo) + síntese SOLID (Martin) |
| 3. Proposta arquitetural (Parte I) | 1,0 | Visão geral do detector, diagrama de componentes inicial (Fig. 1), tabela dos 5 pontos sensíveis (Tabela 1) |
| 4. Aplicação dos princípios SOLID (Parte II) | 2,0 | Cinco subseções (SRP, OCP, LSP, ISP, DIP), cada uma com aspecto, solução ingênua, diagrama de classes UML reduzido (Figs. 2–6), justificativa ubíqua |
| 5. Arquitetura consolidada (Parte III) | 0,75 | Diagrama consolidado (Fig. 7) + 3 ADRs em formato compacto (Tabela 2) |
| 6. Discussão (Parte IV) | 0,5 | Respostas articuladas às questões 4.1, 4.2, 4.3 |
| 7. Considerações finais | 0,15 | Síntese + trabalhos futuros |
| Referências | 0,1 | ≥ 5 (Martin SOLID; Martin Clean Arch; Weiser ubíquos; Satyanarayanan; Bass/Clements/Kazman; Nygard ADR; artigo anterior do grupo) |

Total estimado: **6,0 páginas** exatas. Se estourar, comprimir Fundamentação Teórica e Considerações Finais.

## 4. Parte I — Diagnóstico arquitetural

### 4.1 Diagrama de componentes inicial (Fig. 1)

Diagrama UML de componentes em PlantUML, representando as 5 camadas exigidas pela atividade, com nomes ancorados no nosso código real:

- **Aquisição** — `VideoSource` (subclasses `WebcamSource`, `FileSource`, `RtspSource`)
- **Comunicação** — endpoint REST `/video/push` + autenticação por API key
- **Processamento e regras de negócio** — `domain` (entities, evaluator, fatigue_index) + `application` (use cases)
- **Armazenamento** — `JsonlSink` (eventos), config YAML, logs estruturados
- **Apresentação e atuação** — `interfaces/web` (React Cockpit), `AlertSink`s (sound, mqtt, http, log)

### 4.2 Tabela dos 5 pontos sensíveis (Tabela 1)

Casamento 1:1 entre ponto sensível e princípio SOLID (cada princípio aparece exatamente uma vez, garantindo coesão entre Parte I e Parte II).

| # | Ponto sensível (versão "antes") | Princípio em risco | Sintoma esperado | Característica ubíqua |
|---|---------------------------------|--------------------|--------------------|------------------------|
| 1 | Loop principal monolítico — script único que captura frame, detecta landmarks, calcula EAR/MAR, dispara alarme, renderiza UI | SRP | Qualquer alteração (novo sensor, novo alerta, persistência adicional) força edição do mesmo arquivo; testes unitários inviáveis | Escalabilidade e manutenibilidade |
| 2 | Detector facial hard-coded — `dlib.get_frontal_face_detector` chamado diretamente no loop | OCP | Trocar para MediaPipe, OpenVINO ou modelo customizado exige reescrever o pipeline de detecção | Heterogeneidade de algoritmos e dispositivos |
| 3 | Validadores de contexto heterogêneos — qualidade de imagem, head pose e oclusão tratados ad hoc no loop | LSP | Cada validador tem assinatura própria; adicionar um novo quebra suposições do orquestrador | Sensibilidade ao contexto |
| 4 | Interface "alerta" inflada — função `alarm()` acumula reprodução de som + log + (futuramente) MQTT/HTTP/JSONL | ISP | Adicionar canal silencioso força sinks "mudos" a implementar métodos de áudio que não usam | Heterogeneidade de atuadores |
| 5 | Motor de inferência acoplado — limiar de EAR + contagem de frames embutido no loop, sem abstração | DIP | Substituir limiar fixo por motor fuzzy ou modelo ML exige cirurgia no núcleo; impossível trocar política em runtime | Mobilidade computacional (cloud ↔ edge) |

## 5. Parte II — Aplicação dos cinco princípios SOLID

Para cada princípio, a seção apresenta: **(a)** aspecto ancorado em arquivo/módulo concreto do código atual; **(b)** descrição da solução ingênua (sem o princípio); **(c)** diagrama UML reduzido em PlantUML; **(d)** justificativa relacionando a uma característica ubíqua.

### 5.1 SRP — Single Responsibility Principle

- **Aspecto:** orquestração do ciclo de processamento de fadiga.
- **Antes (ingênuo):** loop único faz captura, conversão de cor, detecção de landmarks, cálculo de EAR/MAR, decisão de alerta, persistência e renderização.
- **Depois (no código atual):** separação em `application/use_cases/` (orquestração), `domain/evaluator.py` (regra de decisão), `infrastructure/video_sources/` (captura), `infrastructure/detectors/` (extração), `infrastructure/alert_sinks/` (publicação). Cada módulo tem uma razão única para mudar.
- **Diagrama UML (Fig. 2):** classes `ProcessFrameUseCase`, `FrameCaptured`, `Evaluator`, `AlertSink` com relações de uso unidirecionais.
- **Justificativa ubíqua:** **escalabilidade** — em um sistema ubíquo que pode evoluir para múltiplos motoristas, múltiplos veículos ou múltiplas câmeras simultâneas, separar responsabilidades permite escalar cada componente independentemente.

### 5.2 OCP — Open/Closed Principle

- **Aspecto:** extensão para novos detectores faciais sem alterar o pipeline.
- **Antes (ingênuo):** `cv2.VideoCapture` + `dlib.get_frontal_face_detector()` instanciados diretamente no script; trocar de algoritmo exige editar o loop.
- **Depois:** `FaceLandmarkDetector` como `Protocol`/ABC; `MediaPipeDetector` é só uma implementação. Acrescentar `DlibDetector`, `OpenVINODetector` ou `ONNXDetector` significa criar uma nova classe — o pipeline em `application/` permanece intacto.
- **Diagrama UML (Fig. 3):** Protocol `FaceLandmarkDetector` ← `MediaPipeDetector`, `DlibDetector` (proposto), `OpenVINODetector` (proposto). Cliente: `ProcessFrameUseCase` depende apenas do Protocol.
- **Justificativa ubíqua:** **heterogeneidade de dispositivos e algoritmos** — sistemas ubíquos abrangem hardware variado (laptop, smartphone, edge device, servidor com GPU). Permitir substituição de detector via configuração é essencial para portar o detector para diferentes plataformas sem reescrever o núcleo.

### 5.3 LSP — Liskov Substitution Principle

- **Aspecto:** contrato uniforme de validação de contexto (qualidade de imagem, oclusão, head pose).
- **Antes (ingênuo):** funções soltas (`check_quality(frame)`, `check_head_pose(landmarks, threshold)`, etc.) com assinaturas e comportamentos divergentes (algumas lançam exceção, outras retornam `None`, outras retornam `bool`).
- **Depois:** `ContextValidator` com contrato claro `validate(context) -> ValidationResult`, garantindo que todas as subclasses honrem o contrato sem efeitos colaterais inesperados. `ImageQualityValidator`, `HeadPoseValidator`, `OcclusionValidator` são intercambiáveis em qualquer ponto do pipeline.
- **Diagrama UML (Fig. 4):** classe abstrata `ContextValidator` com método `validate()`; subclasses concretas; cliente `ValidatePreconditionsUseCase` recebe lista de validadores.
- **Justificativa ubíqua:** **sensibilidade ao contexto** — sistemas ubíquos avaliam contexto continuamente (luz, posição do rosto, oclusão); validadores que falham seu contrato (ex.: lançam exceção em vez de retornar resultado) propagam erro até a UI e quebram a transparência prometida ao motorista.

### 5.4 ISP — Interface Segregation Principle

- **Aspecto:** publicação de eventos de fadiga em múltiplos canais.
- **Antes (ingênuo):** interface única `Notifier` com métodos `play_sound()`, `log()`, `write_file()`, `publish_mqtt()`, `post_webhook()` — sinks que não usam todos os métodos precisam stub-ar ou lançar `NotImplementedError`.
- **Depois:** interface minimal `AlertSink.publish(event: FatigueEvent) -> None`. Cada implementação (`LogSink`, `JsonlSink`, `MqttSink`, `HttpWebhookSink`, `SoundSink`) depende apenas do que efetivamente faz. `CompositeAlertSink` agrega sinks heterogêneos e isola falhas parciais.
- **Diagrama UML (Fig. 5):** interface `AlertSink` ← 5 implementações concretas; `CompositeAlertSink` (também `AlertSink`) agrega lista de sinks.
- **Justificativa ubíqua:** **heterogeneidade de atuadores e transparência** — sistemas ubíquos atuam por múltiplos canais (alerta visual no painel, áudio, push para nuvem, log local). Interfaces segregadas permitem que cada atuador físico ou lógico seja exatamente o que precisa ser, sem ferimentos por métodos não-implementados.

### 5.5 DIP — Dependency Inversion Principle

- **Aspecto:** motor de inferência de fadiga.
- **Antes (ingênuo):** limiar `EAR < 0.25` por 20 frames consecutivos codificado no loop. Trocar pelo motor fuzzy ou ML exige editar o loop.
- **Depois:** `IndexEvaluator` (Protocol) em `domain/fatigue_index.py`. Implementações concretas `FuzzyIndexEvaluator` (12 regras IF–THEN) e `NoOpIndexEvaluator` (fallback). Caso de uso depende somente do Protocol; bootstrap injeta a implementação por configuração.
- **Diagrama UML (Fig. 6):** caso de uso `EvaluateFatigueUseCase` → Protocol `IndexEvaluator` ← `FuzzyIndexEvaluator`, `NoOpIndexEvaluator`, `MLIndexEvaluator` (proposto).
- **Justificativa ubíqua:** **mobilidade computacional** — em um sistema ubíquo, a mesma decisão de fadiga pode ser tomada no edge (laptop do motorista, com fuzzy leve) ou na nuvem (modelo ML pesado quando há conectividade). DIP permite mover a lógica de inferência entre tiers sem reescrever o núcleo.

## 6. Parte III — Arquitetura consolidada e ADRs

### 6.1 Diagrama consolidado (Fig. 7)

Diagrama UML único (preferencialmente de componentes, com algumas relações de classe marcadas) mostrando todas as interfaces criadas e os pontos de extensão:

- **Camada Application** com use cases e Ports (`AlertSink`, `IndexEvaluator`, `FaceLandmarkDetector`, `VideoSource`, `ContextValidator`).
- **Camada Domain** com entidades e value objects, isolada de qualquer detalhe técnico.
- **Camada Infrastructure** com adapters concretos, agrupados visualmente por porta.
- **Camada Interfaces** com `web/` (React Cockpit) e `cli/` (entrypoints).
- Marcações no diagrama: **«DIP»** nas portas, **«OCP»** nos pontos de extensão (lista de adapters expansível), **«ISP»** nas interfaces minimais.

### 6.2 Três ADRs (Tabela 2 — formato compacto)

**ADR-01 — Detector facial como porta plugável (Aceito)**
- **Contexto:** o detector facial inicial era dlib hard-coded; trocar de algoritmo exigia editar o loop principal.
- **Decisão:** introduzir `FaceLandmarkDetector` como Protocol em `application/ports.py`; `MediaPipeDetector` é apenas uma implementação; bootstrap injeta via factory.
- **Princípios aplicados:** OCP + DIP.
- **Consequências:** ✓ permite trocar detector por configuração; ✓ habilita teste com fake detector. ✗ adiciona um nível de indireção; ✗ exige factory de bootstrap.

**ADR-02 — Inferência de fadiga via Strategy com fallback NoOp (Aceito)**
- **Contexto:** lógica de decisão originalmente atrelada a limiar fixo; impossível experimentar fuzzy ou ML sem reescrever o núcleo.
- **Decisão:** `IndexEvaluator` (Protocol) em `domain/`; implementações `FuzzyIndexEvaluator` (12 regras) e `NoOpIndexEvaluator` (fallback quando feature flag desligada).
- **Princípios aplicados:** DIP + OCP, com LSP implícito no contrato uniforme.
- **Consequências:** ✓ ligar/desligar fuzzy por config; ✓ caminho aberto para `MLIndexEvaluator`. ✗ aumenta superfície de configuração e cenários de teste; ✗ exige cuidado para que NoOp seja realmente compatível em todos os pontos de chamada.

**ADR-03 — Saídas de alerta segregadas via Composite (Aceito)**
- **Contexto:** notificação inicial misturava som, log e (no projeto evoluído) MQTT/HTTP/JSONL em uma única função.
- **Decisão:** interface minimal `AlertSink.publish(event)`; sinks especializados (`LogSink`, `JsonlSink`, `MqttSink`, `HttpWebhookSink`, `SoundSink`) compostos por `CompositeAlertSink`.
- **Princípios aplicados:** ISP + SRP.
- **Consequências:** ✓ adicionar/remover canal sem mexer no núcleo; ✓ falha em um sink não derruba os demais. ✗ aumenta quantidade de arquivos pequenos; ✗ orquestração de erros precisa decidir política (continuar, abortar, retry).

## 7. Parte IV — Discussão crítica

### 7.1 Questão 4.1 — Características ubíquas que tornam SOLID relevante

Argumentar com base em **(i) heterogeneidade** e **(ii) sensibilidade ao contexto**:

- Heterogeneidade exemplificada pelo ADR-01: o mesmo sistema precisa rodar com detector MediaPipe (CPU laptop), dlib (dispositivos legados), OpenVINO (edge Intel) ou ONNX (servidor com GPU). Sem OCP+DIP, cada novo destino exige fork do código.
- Sensibilidade ao contexto exemplificada pelos validadores e pela inferência fuzzy: o sistema precisa adaptar-se a luz ambiente, oclusão por óculos, ângulo de cabeça. LSP garante que cada validador pode ser plugado/removido sem efeitos colaterais; DIP no `IndexEvaluator` permite que a estratégia de decisão mude com o contexto (modo noturno usa modelo diferente do diurno).

### 7.2 Questão 4.2 — Onde SOLID seria contraproducente

**Ponto identificado:** o hot path de captura+pré-processamento de frame (`VideoSource.read()` → conversão de cor → `Detector.detect_landmarks()`).

Esse trecho roda a 30 FPS e cada microssegundo conta. Aplicar Strategy/Visitor/Chain-of-Responsibility com múltiplos níveis de indireção neste ponto introduziria overhead de invocação virtual e perda de localidade de cache que poderiam baixar o FPS efetivo. Justifica-se manter este trecho linear e acoplado dentro do adapter concreto (`MediaPipeDetector.detect`), com SOLID concentrado apenas na **fronteira** entre detector e use case — não dentro dele.

### 7.3 Questão 4.3 — SOLID em dispositivos com restrição

**Postura do grupo: aplicação parcial / por camada.**

No nosso caso atual, o detector roda em laptop ou desktop, então não há restrição severa. Mas se o sistema fosse portado para uma ESP32-CAM ou um Raspberry Pi Zero (cenário ubíquo realista para um veículo embarcado), a postura seria:

- **Camadas superiores (domain, application, ports):** SOLID se aplica plenamente. São poucos objetos, mudam pouco em runtime, e o ganho em testabilidade compensa o custo.
- **Camada edge (infrastructure de captura e detecção):** SOLID se aplica apenas na fronteira (porta única para o use case). Internamente, o adapter pode ser procedural, com buffers pré-alocados e zero indireção, otimizado para o hardware específico.

Essa postura evita o dogmatismo de "SOLID em tudo" e respeita a realidade de que sistemas ubíquos têm camadas com perfis de recursos radicalmente diferentes.

## 8. Diagramas — entregáveis técnicos

Todos em PlantUML, versionados em `docs/article-solid/diagrams/`, renderizados em PNG para inclusão no LaTeX.

| Arquivo `.puml` | Figura no artigo | Conteúdo |
|-----------------|------------------|----------|
| `01-componentes-inicial.puml` | Fig. 1 | Diagrama de componentes inicial, 5 camadas |
| `02-srp-use-cases.puml` | Fig. 2 | Separação de responsabilidades em use cases |
| `03-ocp-detector.puml` | Fig. 3 | Protocol `FaceLandmarkDetector` + implementações |
| `04-lsp-validators.puml` | Fig. 4 | Hierarquia `ContextValidator` |
| `05-isp-alert-sinks.puml` | Fig. 5 | `AlertSink` + Composite |
| `06-dip-index-evaluator.puml` | Fig. 6 | `IndexEvaluator` Strategy |
| `07-arquitetura-consolidada.puml` | Fig. 7 | Visão integrada com marcações DIP/OCP/ISP |

## 9. Arquivos a produzir

```
docs/article-solid/
├── artigo.tex                         # fonte LaTeX (formato SBC, ≤6 págs)
├── sbc-template.sty                   # estilo SBC (reutilizar do artigo anterior)
├── refs.bib                           # referências em BibTeX (opcional, ou inline)
├── diagrams/
│   ├── 01-componentes-inicial.puml
│   ├── 02-srp-use-cases.puml
│   ├── 03-ocp-detector.puml
│   ├── 04-lsp-validators.puml
│   ├── 05-isp-alert-sinks.puml
│   ├── 06-dip-index-evaluator.puml
│   ├── 07-arquitetura-consolidada.puml
│   └── png/                           # PNGs gerados
└── README.md                          # como compilar (plantuml + pdflatex)
```

## 10. Referências mínimas

Mínimo de 5 (atividade exige ≥5, com pelo menos 1 sobre SOLID, 1 sobre ubíquos, 1 sobre arquitetura):

1. **MARTIN, R. C.** Arquitetura Limpa: o guia do artesão para estrutura e design de software. Alta Books, 2019.
2. **MARTIN, R. C.** Agile Software Development: Principles, Patterns, and Practices. Prentice Hall, 2002.
3. **WEISER, M.** The Computer for the 21st Century. Scientific American, v. 265, n. 3, p. 94–104, 1991.
4. **SATYANARAYANAN, M.** Pervasive computing: vision and challenges. IEEE Personal Communications, v. 8, n. 4, p. 10–17, 2001.
5. **BASS, L.; CLEMENTS, P.; KAZMAN, R.** Software Architecture in Practice. 4. ed. Addison-Wesley, 2021.
6. **NYGARD, M.** Documenting Architecture Decisions. 2011.
7. **ARAUJO, R. B.** Computação ubíqua: princípios, tecnologias e desafios. SBRC, 2003.
8. **SILVA, J. S.; TELES, L. E. S.; PENARIOL, L. F. H.** Detector de Fadiga: Uma Solução para Monitoramento em Tempo Real. (Artigo anterior do grupo — autocitação.)

## 11. Trade-offs e riscos

- **Limite de páginas:** o conteúdo é volumoso para 6 páginas. Mitigação: ADRs em formato compacto numa tabela; diagramas pequenos lado a lado (2 colunas); fundamentação teórica enxuta.
- **Diagramas de classes UML reduzidos por princípio (5 figuras):** pode ficar excessivo. Mitigação: combinar Figs. 3–6 em pares (uma figura com dois princípios) se necessário, totalizando 4–5 figuras em vez de 7.
- **Coerência interna (critério de avaliação):** as decisões da Seção 4 devem refletir-se na Seção 5. Mitigação: cada princípio da Parte II referencia explicitamente um ou mais ADRs da Parte III.
- **Postura crítica sem dogmatismo:** a postura "parcial por camada" foi escolhida para evitar parecer apologética a SOLID. Mitigação: na Q. 4.2, ser explícito sobre o hot path como zona de pragmatismo.

## 12. Critérios de pronto

- [ ] Artigo compilando para PDF com ≤6 páginas A4 (margens 2 cm).
- [ ] 7 figuras PlantUML renderizadas em PNG e referenciadas no texto.
- [ ] Tabela 1 (pontos sensíveis) e Tabela 2 (ADRs) presentes.
- [ ] Cinco subseções da Parte II completas, com ancoragem em código, antes/depois, diagrama e justificativa ubíqua.
- [ ] Discussão crítica articulada respondendo 4.1, 4.2, 4.3.
- [ ] ≥ 5 referências, padrão consistente (SBC ou ABNT NBR 6023).
- [ ] Revisão ortográfica/gramatical em português brasileiro técnico-acadêmico.
- [ ] Verificado que todas as figuras e tabelas são referenciadas no texto antes de sua aparição.
