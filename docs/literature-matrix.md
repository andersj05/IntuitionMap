# IntuitionMap literature matrix

**Review status:** Phase 0 seed review
**Last searched:** 2026-07-28
**Scope:** mechanisms and evaluation evidence needed to choose the first
IntuitionMap experiments; this is not a claim of systematic-review
completeness.

## Review protocol

Works were included when they contributed at least one testable mechanism,
dataset, evaluation design, or important counterexample for the research
questions in the [canonical plan](research-and-implementation-plan.md).
Publisher pages, proceedings, author manuscripts, and official repositories
were preferred over summaries. Citation chaining started from the six seed
works in the plan.

Evidence classes used below:

- **Peer reviewed:** archival journal or conference paper.
- **Benchmark:** peer-reviewed paper whose main contribution is an evaluation
  resource.
- **Preprint:** not treated as settled evidence even when code is available.
- **Method:** peer-reviewed statistical or machine-learning control relevant to
  the evaluation contract.

Exact search queries used on 2026-07-28:

```text
Conditions for Intuitive Expertise Kahneman Klein 2009 DOI primary paper
Collins Loftus 1975 spreading activation theory semantic processing DOI primary paper
McClelland McNaughton O'Reilly 1995 complementary learning systems primary paper
Gentner 1983 structure-mapping theoretical framework analogy primary paper
site:aclanthology.org A-MEM Agentic Memory for LLM Agents 2025
site:aclanthology.org Associa Bridging Intuitive Associations and Deliberate Recall 2025
site:openreview.net HippoRAG Neurobiologically Inspired Long-Term Memory Large Language Models
Generative Agents Interactive Simulacra of Human Behavior UIST 2023 official paper
LongMemEval benchmark official paper long term interactive memory ICLR 2025
LaMP benchmark personalized language modeling ACL Anthology official paper
PersonalLLM dataset preference official paper arxiv
Lost in the Middle long contexts TACL official paper
Elkan Noto 2008 Learning classifiers from only positive unlabeled data official ACM
Guo Pleiss Sun Weinberger calibration modern neural networks ICML 2017 official proceedings
selective classification risk coverage Geifman El-Yaniv 2017 official paper
unbiased recommender learning missing not at random exposure bias official paper
```

The review also opened the official paper or repository pages linked by these
results and followed citations from the seed works. Product marketing claims
were excluded. A reported result below is the authors' result unless an
independent replication is explicitly named.

## Evidence extraction matrix

| Citation / evidence class | Year | Definition used | Mechanism | Training signal | Dataset and split | Baselines | Primary metric | Reported result | Limitation or negative evidence | Code / data | License status | IntuitionMap experiment relevance |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|
| [Kahneman & Klein, “Conditions for Intuitive Expertise”](https://doi.org/10.1037/a0016755) — peer reviewed synthesis | 2009 | Skilled intuition is recognition of learned environmental regularities, not a feeling that guarantees correctness. | Regular environment plus repeated opportunity for valid feedback. | Experience and outcome feedback; no ML training. | Cross-tradition synthesis; no benchmark split. | Heuristics-and-biases versus naturalistic decision-making accounts. | Explanatory boundary conditions. | Both traditions agree that predictability and learning opportunity govern whether intuition is trustworthy. | Subjective confidence is not evidence of accuracy; the paper does not operationalize personal text-link prediction. | Paper only. | Publisher copyright; no reusable dataset/code. | Requires repeated held-out judgments and makes “the graph feels right” an invalid success criterion (RQ3, RQ8). |
| [Collins & Loftus, “A Spreading-Activation Theory of Semantic Processing”](https://doi.org/10.1037/0033-295X.82.6.407) — peer reviewed theory | 1975 | Recall is activation spreading through a weighted semantic network; activation strength decays with distance. | Weighted links, spreading activation, thresholded retrieval, and context-sensitive priming. | Hand-specified theory fit to prior behavioral experiments. | Multiple published production, categorization, verification, and priming experiments; no modern train/test split. | Earlier hierarchical semantic-network account. | Ability to explain reaction-time and priming patterns. | A non-hierarchical weighted network accounts for several relatedness and typicality effects. | Population semantic priming is not a user-specific graph; broad hubs and short paths can activate irrelevant concepts. | Paper only. | Publisher copyright; no reusable dataset/code. | Motivates bounded graph diffusion, decay, and explicit hub controls, tested against flat retrieval (RQ5, RQ6). |
| [McClelland, McNaughton & O’Reilly, “Why There Are Complementary Learning Systems”](https://doi.org/10.1037/0033-295X.102.3.419) — peer reviewed theory/model | 1995 | Memory requires rapid storage of episodes and slower extraction of shared structure. | Sparse hippocampal traces plus gradual interleaved neocortical learning/consolidation. | Simulated episodes and interleaved neural-network learning. | Computational demonstrations and neuropsychological evidence; no product-like split. | Single-system connectionist learning and then-current consolidation accounts. | Avoidance of catastrophic interference while learning structure. | Complementary fast and slow systems explain why rapid episodic learning and gradual generalization can coexist. | It is a functional theory, not evidence that two software modules reproduce biological intuition. | Author manuscript; simulation details in paper. | Paper/manuscript terms only; no dataset selected for reuse. | Supports immutable fast capture plus slower derived representations, but requires an ablation against a single-store system (RQ4, RQ5). |
| [Gentner, “Structure-Mapping: A Theoretical Framework for Analogy”](https://doi.org/10.1207/s15516709cog0702_3) — peer reviewed theory | 1983 | Analogy maps relational structure rather than surface attributes; coherent higher-order systems are preferred. | Directional base-to-target mapping and the systematicity principle. | Formal interpretation rules; no learned model. | Worked comparisons; no train/test split. | Literal similarity, abstraction, and appearance matching. | Qualitative explanatory discrimination. | The framework distinguishes analogy from surface similarity using mapped relations and higher-order structure. | Original paper is primarily theoretical and does not establish scalable automatic detection in noisy notes. | Paper only. | Free-to-read publisher page; no dataset/code license. | Requires a directed relation task with hard topical-similarity invalids, not cosine similarity alone (RQ2, RQ6). |
| [Park et al., “Generative Agents”](https://doi.org/10.1145/3586183.3606763) — peer reviewed | 2023 | An episodic memory stream supports believable behavior when relevant experiences are retrieved and reflected into higher-level memories. | Retrieval score combining recency, importance, and relevance; LLM reflection and planning. | Prompted LLM generations and hand-authored agent setup, not learned personal labels. | 25-agent sandbox; ablations and human believability evaluation rather than chronological user holdout. | Architecture variants without observation, reflection, or planning. | Human-rated believability and behavior consistency. | Each major component contributed to believability in the reported ablation. | Believability is not factual or personal-association accuracy; reflections can introduce unsupported derived claims. | [Official code repository](https://github.com/joonspk-research/generative_agents). | Code license must be pinned before reuse; ACM paper terms apply to paper. | Recency is a baseline feature; reflections must be versioned derived artifacts with provenance and tested for utility (RQ1, RQ5, RQ8). |
| [Liu et al., “Lost in the Middle”](https://aclanthology.org/2024.tacl-1.9/) — peer reviewed negative evidence | 2024 | Long-context access is positional and unreliable even when the needed text is present. | Controlled relocation of evidence within long inputs. | None; evaluation only. | Multi-document QA and key-value retrieval with controlled evidence positions. | Multiple open and closed long-context LMs. | QA and retrieval accuracy by evidence position. | Performance commonly forms a U-shape: best at the beginning/end and materially worse in the middle. | Tests supplied context, not persistent memory or personal judgments; model families have since changed. | [Code and data](https://github.com/nelson-liu/lost-in-the-middle). | Repository license must be pinned before reuse; ACL paper is CC BY 4.0. | Rejects “put every thought in one prompt” as a sufficient baseline; retrieval must be measured separately (RQ1, RQ7). |
| [Jiménez Gutiérrez et al., “HippoRAG”](https://arxiv.org/abs/2405.14831) — peer reviewed, NeurIPS 2024 | 2024 | Long-term memory is a passage-backed associative index that completes a partial cue through a graph. | LLM OpenIE graph, dense synonym edges, query entities, Personalized PageRank, passage aggregation. | Off-the-shelf LLM/extractor and retriever; no task-specific or personal training in the reported main system. | 1,000 dev questions each from MuSiQue, 2WikiMultiHopQA, and HotpotQA; 100 MuSiQue train examples tune two hyperparameters. | BM25, Contriever, GTR, ColBERTv2, Propositionizer, RAPTOR, IRCoT. | Retrieval recall@2/@5; QA exact match/F1; cost and latency. | Up to 20-point retrieval gains on the harder multi-hop sets; authors report lower online cost/latency than iterative IRCoT. | In a 100-error analysis: NER 48%, OpenIE 28%, PPR 24%; context is discarded by entity bias, longer-document extraction and scale remain unproven. | [Official code/data](https://github.com/OSU-NLP-Group/HippoRAG). | Pin repository and dependency licenses before reuse. | Strong B6 candidate only after flat/hybrid baselines; directly test graph construction errors and equal-budget PPR ablation (RQ5). |
| [Salemi et al., “LaMP”](https://aclanthology.org/2024.acl-long.399/) — benchmark | 2024 | Personalization conditions generation/classification on a user profile of prior inputs and user-produced or approved outputs. | Retrieve profile items, then use in-prompt augmentation or fusion-in-decoder. | Historical user profile items and task labels. | Seven tasks; both user-based and time-based separation settings. | Non-personalized models, random/profile retrieval variants, zero-shot and fine-tuned LMs. | Task-specific accuracy/F1/MAE/ROUGE. | Authors report average relative gains of 23.5% when fine-tuned and 12.2% zero-shot with personalized augmentation. | Source tasks proxy behavior and style, not directed thought associations; underlying dataset terms differ and Avocado is not public. | [Official code/data methods](https://github.com/LaMP-Benchmark/LaMP). | Code/methods CC BY-NC-SA 4.0; each source dataset keeps its own terms. | Candidate capability check for sparse profile retrieval; cannot support the personal-intuition claim (RQ3). |
| [Wu et al., “LongMemEval”](https://proceedings.iclr.cc/paper_files/paper/2025/file/d813d324dbf0598bbdc9c8e79740ed01-Paper-Conference.pdf) — benchmark, ICLR 2025 | 2025 | Long-term interactive memory is accurate indexing, retrieval, and reading over timestamped chat sessions, including update and abstention behavior. | Session decomposition, fact-augmented keys, time-aware query expansion, then reading. | Curated questions/evidence and generated/filler histories; evaluation only for most systems. | 500 questions across short/medium/oracle histories and five capabilities. | Full-context commercial/open models and multiple memory/indexing variants. | QA accuracy and session/turn recall. | Commercial and long-context systems showed about a 30% accuracy drop on sustained histories; proposed optimizations improved recall and QA. | Mostly synthetic/curated QA evidence; generated histories and LLM auto-evaluation do not measure a user’s latent links. | [Official repository](https://github.com/xiaowu0162/LongMemEval) and official cleaned HF release. | Repository code is MIT; exact data-license scope must be resolved before acquisition. | Best first temporal-memory capability benchmark, with native QA retained and an adapter limited to retrieval components (RQ1, RQ4). |
| [Xu et al., “A-MEM”](https://arxiv.org/abs/2502.12110) — peer reviewed, NeurIPS 2025 | 2025 | Memory is an evolving network of atomic notes enriched with generated context, tags, keywords, embeddings, and links. | Dense top-k candidate search, LLM link generation, in-place evolution of retrieved notes, dense retrieval. | LLM-generated note attributes/links; no human personal-link labels. | LoCoMo and DialSim; QA across six foundation models; reported category metrics rather than protected chronological personal split. | Raw LoCoMo, ReadAgent, MemoryBank, MemGPT. | QA F1/BLEU plus ROUGE/METEOR/SBERT and token length. | Reported gains across six backbones; e.g. GPT-4o-mini temporal F1 45.85 versus MemGPT 25.52, with much shorter retrieved context. | Results do not isolate link quality; model-generated context may create circular signal, and replacing historical notes violates immutable-source provenance. | [Evaluation code](https://github.com/WujiangXu/A-mem) and [system code](https://github.com/WujiangXu/A-mem-sys). | Repository licenses must be verified before reuse. | Test enriched derived notes and link proposals separately; never overwrite captured thought text (RQ2, RQ8). |
| [Zhang, Yuan & Jiang, “Associa”](https://aclanthology.org/2025.findings-acl.901/) — peer reviewed, Findings ACL 2025 | 2025 | Associative recall extracts a connected evidence subgraph; deliberate recall iteratively repairs missing evidence. | Event-centric graph, query/node/edge prizes, Prize-Collecting Steiner Tree, fine-tuned 3B query refinement, evidence ranking. | LLM graph extraction plus supervised fine-tuning for deliberate recall; no personal verdict labels. | LongMemEval-S/M and LoCoMo; dataset-provided evaluation, not user chronological holdout. | BM25, dense retrievers, LongMemEval retrieval, MemoryBank, MemoRAG, LightRAG. | Recall@5/@10, nDCG, QA accuracy, cost/latency. | LongMemEval-S R@5 0.87 versus strongest dense BGE 0.75; LongMemEval-M 0.66 versus BGE 0.56. | The paper explicitly does not model temporal information and evaluates English only; graph construction and recursive retrieval add model dependence. | Paper and prompts; no code link on the ACL record reviewed here. | ACL paper CC BY 4.0; implementation reuse status unresolved. | PCST is a later B6 comparator after candidate recall works; use identical evidence pools and price all graph construction (RQ5, RQ7). |
| [Zollo et al., “PersonalLLM”](https://arxiv.org/abs/2409.20296) — preprint/benchmark | 2024 | Personalization is adaptation to a simulated individual’s heterogeneous response preferences under sparse feedback. | Personalities induced from reward models; in-context and meta-learning baselines transfer across simulated users. | Reward-model scores/preferences over multiple candidate answers. | Train/evaluation resources on Hugging Face; simulated personalities rather than natural user thought histories. | Basic in-context learning and meta-learning. | Preference/reward prediction and personalized response quality as defined in the paper. | Baselines demonstrate that sparse preference adaptation is measurable but leave substantial room for improvement. | Preferences are simulated from pretrained reward models and may inherit their biases; no directed link or temporal-intuition labels. | [Official dataset](https://huggingface.co/datasets/namkoong-lab/PersonalLLM). | HF metadata currently says CC BY 4.0; this conflicts with an earlier CC BY-NC planning note and must be resolved at a pinned revision. | Candidate alternative to LaMP for a cold-start personalization component only (RQ3). |
| [Yu et al., “Agentic Memory (AgeMem)”](https://aclanthology.org/2026.acl-long.981/) — peer reviewed, ACL 2026 | 2026 | Memory is a learnable policy over persistent LTM and active-context STM operations. | ADD/UPDATE/DELETE/RETRIEVE/SUMMARY/FILTER tools; three-stage curriculum; step-wise GRPO. | Composite terminal task, context, and memory-quality rewards propagated to memory actions. | Training trajectories from HotpotQA; evaluation on ALFWorld, SciWorld, PDDL, BabyAI, HotpotQA. | No-memory, LangMem, A-MEM, Mem0, graph Mem0, no-RL variants. | Task score, LLM-judge score, memory quality, prompt tokens, tool calls. | Average score rose from strongest listed baseline 37.14 to 41.96 on Qwen2.5-7B, and 45.74 to 54.31 on Qwen3-4B. | Fixed tool set, controlled benchmarks, HotpotQA-only training, no persistent real-user evaluation; some headline components use LLM judges. | Paper links implementation resources; exact code/data revision not yet registered. | ACL paper CC BY 4.0; code license must be pinned. | B7 only after learning curves justify RL; first compare fixed, interpretable policies at equal task information and cost (RQ7). |
| [Elkan & Noto, “Learning Classifiers from Only Positive and Unlabeled Data”](https://doi.org/10.1145/1401890.1401920) — method | 2008 | Unlabeled examples are a mixture of positives and negatives, not negative labels. | Estimate the positive-labeling probability, rescale a classifier, or weight unlabeled examples. | Labeled positives plus unlabeled examples. | Multiple classification datasets under simulated positive-label omission. | Naive positive-versus-unlabeled classification and prior PU methods. | Classification accuracy/probability quality. | Under selected-completely-at-random positives, a nontraditional classifier’s probabilities differ from true positive probabilities by a constant factor that can be estimated. | The SCAR assumption can fail badly when the UI/model determines which links receive labels. | Paper/author resources. | Publisher terms; no dataset planned for acquisition. | Formal reason never to convert missing links into invalid; exposure source must be stored and proposal-stream bias tested (RQ3, RQ8). |
| [Saito et al., “Unbiased Recommender Learning from Missing-Not-At-Random Implicit Feedback”](https://doi.org/10.1145/3336191.3371783) — method, WSDM 2020 | 2020 | Missing feedback reflects both relevance and unequal exposure. | Inverse-propensity unbiased risk estimator plus clipping for bias-variance control. | Click/implicit feedback with estimated exposure propensities. | Semi-synthetic and real recommendation datasets. | Uniform PU weighting and EM/confidence baselines. | Ranking/recommendation accuracy, including rare items. | Reported gains over baselines, especially for rarely observed items. | Propensity estimation is itself difficult; clipping trades bias for variance and offline assumptions may not match a changing annotation UI. | Paper and author code where supplied. | Dataset-specific terms; no artifact selected. | Requires logging proposal source/probability and preserving a random discovery stream before learning from UI acceptance (RQ3, RQ6). |
| [Guo et al., “On Calibration of Modern Neural Networks”](https://proceedings.mlr.press/v70/guo17a.html) — method, ICML 2017 | 2017 | Confidence should match empirical correctness frequency. | Post-hoc temperature scaling on held-out validation logits. | Labeled validation data. | CIFAR-10/100 and ImageNet; train/validation/test protocol from the paper. | Histograms, Platt scaling, isotonic regression, matrix/vector scaling. | Expected calibration error and negative log likelihood. | Modern neural networks were often miscalibrated; a single temperature was a strong simple correction. | Classification calibration does not automatically calibrate ranking under temporal drift or sparse personal labels. | [Paper/code links](https://proceedings.mlr.press/v70/guo17a.html). | PMLR paper; dataset and code terms remain source-specific. | Establishes a cheap calibrator baseline and supports dated rolling recalibration (RQ3, RQ4). |
| [Geifman & El-Yaniv, “Selective Classification for Deep Neural Networks”](https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html) — method, NeurIPS 2017 | 2017 | A model may abstain on some inputs to control error on the covered subset. | Confidence-ranked selection with high-probability risk control. | Labeled calibration/validation examples. | ImageNet and other classification benchmarks in the paper. | Ordinary full-coverage classifiers and selection heuristics. | Risk-coverage curve. | Authors report approximately 2% top-5 ImageNet error at almost 60% coverage with a 99.9% guarantee under their setup. | Coverage guarantees depend on representative validation data and do not remove distribution shift. | Paper and supplementary material. | Proceedings paper; no dataset/code imported. | Makes abstention a measured output, not a hidden threshold; compare useful recall at matched risk/coverage (RQ2, RQ8). |

## Negative-evidence ledger

These findings constrain the design even when they do not favor a graph:

| ID | Evidence against an easy or preferred story | Required control |
|---|---|---|
| N1 | Felt certainty is not reliable evidence of intuitive accuracy. | Protected chronological user judgments and repeated-label reliability. |
| N2 | A large context window does not reliably use evidence in the middle. | Explicit retrieval baseline; never use “all thoughts in prompt” as the only comparator. |
| N3 | HippoRAG, A-MEM, Associa, and AgeMem report generic QA/task gains, not prediction of a person’s directed thought links. | Keep public capability scores separate from the private headline metric. |
| N4 | HippoRAG’s graph gains are bottlenecked by NER/OpenIE errors and unproven scale. | Store extraction provenance, audit unsupported nodes/edges, and match graph/flat budgets. |
| N5 | A-MEM evolves historical note representations in place. | Preserve immutable source captures; write all summaries, tags, and evolved context as versioned derived artifacts. |
| N6 | Associa omits temporal modeling and uses English-only benchmarks. | Enforce point-in-time graph reconstruction and record language scope. |
| N7 | Missing and unexposed pairs are not negatives. | Explicit `invalid` labels only; preserve discovery/proposal streams and exposure probability. |
| N8 | Neural confidence can be badly miscalibrated. | Report calibration and risk-coverage, with an explicit abstention action. |
| N9 | Learned memory policies require substantial training and were evaluated in controlled environments. | Do not begin RL/GNN work until cheaper personal and graph baselines pass their gates. |

No independent reproduction of the recent graph-memory headline results was
located in this bounded Phase 0 review. That absence is recorded as uncertainty,
not as evidence that the results are false.

## Mechanism comparison

| Mechanism family | What it can plausibly add | Main confound | Cheapest discriminating test |
|---|---|---|---|
| Lexical/recency retrieval | Transparent high-precision local links. | Favors literal repetition and recent notes. | BM25/TF-IDF and most-recent controls on the same temporal candidates. |
| Dense semantic retrieval | Paraphrase and topical recall. | Similarity can erase direction and confuse separate projects. | Dense versus lexical at fixed `k`, including near-topic explicit invalids. |
| Pairwise directed reranking | Relation and direction judgments after broad recall. | Prompt/model knowledge can impersonate user preference. | Frozen candidate set; generic reranker versus small personal head. |
| Graph diffusion or subgraph optimization | Multi-hop integration and remote associations. | Hubs, extractor errors, and extra information/compute. | Flat versus one-hop/PPR/PCST at the same source passages, top-k, and cost. |
| Generated summaries/reflections | Compact higher-order representations. | Unsupported inference and provenance inversion. | Original-only versus versioned-derived retrieval with attribution audit. |
| User-specific calibration/head | Sparse adaptation to personal verdicts. | Exposure bias and temporal drift. | Rolling cold-start curve against the strongest generic model. |
| Learned memory policy | Task-dependent write/read/forget behavior. | Reward leakage, high cost, and data hunger. | Fixed-policy baseline first; only advance after G4/G5 and a preregistered task reward. |

## First experiments that distinguish explanations

1. **Retrieval complementarity:** compare lexical, recency, dense, and a
   deterministic union on identical chronological candidates. This distinguishes
   semantic coverage from a trivial recency effect.
2. **Relationship versus similarity:** freeze the candidate set and compare
   cosine similarity with a directed pair scorer on topical-but-invalid pairs.
3. **Generic versus personal signal:** freeze representations and compare a
   generic calibrator with a small user-specific linear or pairwise head as the
   label count grows.
4. **Graph value:** compare flat retrieval, one-hop expansion, Personalized
   PageRank, and a constrained subgraph method at equal candidate, token,
   latency, and source-information budgets.
5. **Derived-memory value:** compare immutable source-only retrieval with
   retrieval over versioned summaries/tags; audit every gain for unsupported
   content and temporal leakage.
6. **Exposure bias:** compare independently supplied discovery links with
   model-proposal acceptances and a controlled random sample. Do not pool the
   streams without an exposure feature.
7. **Abstention:** calibrate on a chronological validation block and compare
   risk-coverage curves, not only a single threshold chosen after test results.

The review therefore supports the plan’s current ladder: strengthen cheap
retrieval and measurement first, obtain protected personal evidence only after
the data controls exist, and test graph mechanisms as matched ablations rather
than assuming that a graph is the source of any gain.
