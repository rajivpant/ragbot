# Ragbot Sizing Matrix — Open-Weights Models on Apple Silicon

This document maps each open-weights model in Ragbot's `engines.yaml` to the Mac hardware that runs it well, with concrete memory footprints, quantization recommendations, and expected tokens-per-second under the MLX backend.

The intended reader is somebody looking at the local-model dropdown in Ragbot and trying to answer one question: *will this model run usefully on my Mac, and if not, which quantization or which different model should I pick instead?* If you came here from the README link, start with [How to read the matrix](#how-to-read-the-matrix), pick your hardware in [Per-hardware sections](#per-hardware-sections), then cross-reference the [Per-model sections](#per-model-sections) for the deeper context.

All numbers are as of May 14, 2026. The MLX framework and Ollama 0.19+ MLX backend are the canonical local-inference paths assumed throughout; numbers for llama.cpp via the Metal backend are 20-40% slower in most cases and noted where relevant.

---

## How to read the matrix

### Quantization quality vs. memory

Open-weights models ship in several precisions. Ragbot's sizing matrix uses four reference points:

- **FP16 / BF16** — the precision the weights were trained in. No quality loss vs. the reference. Memory: ~2 bytes per parameter.
- **Q8_0** — 8-bit quantization. Quality loss is below the noise floor for most workloads; effectively equivalent to FP16 in side-by-side evals. Memory: ~1 byte per parameter.
- **Q5_K_M** — 5-bit quantization, k-quants medium. Quality loss is small and concentrated on outlier tokens (rare vocab, code edge cases). Memory: ~0.65 bytes per parameter.
- **Q4_K_M** — 4-bit quantization, k-quants medium. The most popular point on the curve: noticeable but acceptable quality loss for general chat, retrieval-augmented Q&A, summarization. Some quality loss on code generation, math, and long-context reasoning. Memory: ~0.5 bytes per parameter.

Two important caveats:

1. **MoE routing is more quantization-sensitive than dense layers.** The router that picks which expert handles a token operates on weight distributions. When those distributions lose precision, the router picks wrong experts more often, producing measurably worse output. This means the jump from Q4 to Q5 on Scout, Maverick, DeepSeek V3.2, Mistral Large 3, or Qwen3.6-35B-A3B may produce a more noticeable quality improvement than the same jump on a dense 17B or 27B model. ([source](https://www.sitepoint.com/llama-4-scout-on-mlx-the-complete-apple-silicon-guide-2026/))

2. **Unified memory is shared.** macOS plus your other open apps need their share. Plan for roughly **70-75% of your unified memory** being usable for model weights and KV cache. On a 64GB Mac that's ~45-48GB; on a 128GB Mac that's ~90-96GB. ([source](https://www.sitepoint.com/llama-4-scout-on-mlx-the-complete-apple-silicon-guide-2026/))

### Tier vocabulary

For each (hardware, model) pair the matrix records one of four verdicts:

- **comfortable** — fits at the listed precision with at least 25% headroom for KV cache, OS, and other applications. Suitable as a daily driver.
- **tight** — fits at the listed precision only if the Mac is dedicated to the model (no other heavy apps running). Suitable for batch jobs and bursty workloads.
- **Q4-only** — does not fit at FP16 or Q8 but fits at Q4 with at least 15% headroom. Quality loss is acceptable for general chat; consider a smaller model for code or math.
- **won't fit** — cannot fit at any practical quantization. Use a different model.

### KV cache memory

The KV cache grows linearly with context length and model dimensions. As a rough rule for the models in this matrix at FP16 KV (the MLX default):

- 8K context: 0.5-2 GB depending on model
- 32K context: 2-8 GB
- 128K context: 8-32 GB
- 1M context: 64-256 GB (Maverick and Scout territory; usually requires aggressive KV quantization)

When a model entry below says "comfortable for 8K, tight for 128K," this is why. The sizing-matrix tables in [Per-hardware sections](#per-hardware-sections) assume an 8K working context. The [Per-model sections](#per-model-sections) discuss the 128K-and-up cost.

### Memory bandwidth and tokens/sec

Memory bandwidth is the dominant factor in decode speed on Apple Silicon, more than core count:

| Chip | Unified memory bandwidth |
|---|---|
| M4 (base) | 120 GB/s |
| M4 Pro | 273 GB/s |
| M4 Max | 546 GB/s |
| M5 Max | 614 GB/s |
| M3 Ultra | 800 GB/s |
| M5 Ultra (expected mid-2026) | ~1,200 GB/s |

A rough decode-speed estimate: `tokens/sec ≈ bandwidth_GB_per_s / model_size_GB`. A 70 GB model on an M5 Max (614 GB/s) gets ~9 tok/s. A 22 GB Q4 model on the same hardware gets ~28 tok/s. MoE models read only the active expert weights per token, so a 17B-active 109B-total Scout decodes closer to 17B-dense speed than 109B-dense speed (with cache-locality penalties when the router picks different experts in sequence).

---

## Per-hardware sections

### Mac mini

The Mac mini line is the cheapest entry point for local LLMs in Ragbot. The M4 (base) variant ships with 16 GB minimum; the M4 Pro starts at 24 GB and can be configured up to 64 GB. Bandwidth jumps from 120 GB/s (base) to 273 GB/s (Pro) — the practical difference is the Pro can drive 27B-class models at conversational speed while the base is limited to 8B-class. ([source](https://www.popularai.org/p/mac-mini-llm-performance-in-2026))

#### Mac mini 16 GB (M4 base)

- **Total unified memory:** 16 GB
- **OS + base app overhead:** ~5-6 GB
- **LLM budget remaining:** ~10-11 GB

| Model | Params | FP16 mem | Q4 mem | Verdict |
|---|---|---|---|---|
| Gemma 4 E4B | 4B effective | 8 GB | 2.5 GB | comfortable (Q4) |
| Gemma 4 26B MoE | 26B (~3.8B active) | 52 GB | 15 GB | won't fit |
| Gemma 4 31B Dense | 31B | 62 GB | 18 GB | won't fit |
| Llama 4 Scout | 109B (17B active) | 218 GB | 58 GB | won't fit |
| Llama 4 Maverick | 400B (17B active) | 800 GB | 220 GB | won't fit |
| Qwen3.6 27B | 27B | 55 GB | 17 GB | won't fit |
| Qwen3.6 35B-A3B | 35B (3B active) | 70 GB | 22 GB | won't fit |
| DeepSeek V3.2 | 671B (37B active) | 1342 GB | 340 GB | won't fit |
| Mistral Large 3 | 675B (41B active) | 1350 GB | 340 GB | won't fit |
| Mistral Medium 3.5 | 128B | 256 GB | 70 GB | won't fit |
| Mistral Small 4 | 119B (6B active) | 238 GB | 64 GB | won't fit |

**Recommended models:** Gemma 4 E4B (Q4) for general chat and lightweight RAG. A 16 GB Mac mini is not the right machine for the v3.4 model additions — it's a starter local-inference box, fine for the existing Gemma 4 E4B but nothing else in this expanded model list.

#### Mac mini 32 GB (M4 Pro)

- **Total unified memory:** 32 GB
- **OS + base app overhead:** ~6-7 GB
- **LLM budget remaining:** ~24-26 GB

| Model | Params | FP16 mem | Q4 mem | Verdict |
|---|---|---|---|---|
| Gemma 4 E4B | 4B effective | 8 GB | 2.5 GB | comfortable |
| Gemma 4 26B MoE | 26B | 52 GB | 15 GB | Q4-only |
| Gemma 4 31B Dense | 31B | 62 GB | 18 GB | Q4-only |
| Llama 4 Scout | 109B | 218 GB | 58 GB | won't fit |
| Qwen3.6 27B | 27B | 55 GB | 17 GB | Q4-only |
| Qwen3.6 35B-A3B | 35B | 70 GB | 22 GB | Q4-only (tight) |
| Mistral Small 4 | 119B | 238 GB | 64 GB | won't fit |
| Mistral Medium 3.5 | 128B | 256 GB | 70 GB | won't fit |
| Llama 4 Maverick, DeepSeek V3.2, Mistral Large 3 | — | — | — | won't fit |

**Recommended models:** Gemma 4 26B MoE (Q4) for fast everyday use (MoE keeps decode snappy); Qwen3.6 27B (Q4) as a stronger alternative for coding and long-context retrieval. Qwen3.6 35B-A3B at Q4 is borderline — works but no headroom for parallel apps or long contexts.

#### Mac mini 64 GB (M4 Pro)

- **Total unified memory:** 64 GB
- **OS + base app overhead:** ~7-8 GB
- **LLM budget remaining:** ~56-58 GB

| Model | Params | FP16 mem | Q4 mem | Verdict |
|---|---|---|---|---|
| Gemma 4 E4B | 4B | 8 GB | 2.5 GB | comfortable |
| Gemma 4 26B MoE | 26B | 52 GB | 15 GB | comfortable (Q4), tight (Q8) |
| Gemma 4 31B Dense | 31B | 62 GB | 18 GB | comfortable (Q4), tight (Q8) |
| Llama 4 Scout | 109B | 218 GB | 58 GB | Q4-only (tight; ~58 GB Q4) |
| Qwen3.6 27B | 27B | 55 GB | 17 GB | comfortable (Q4), tight (Q8) |
| Qwen3.6 35B-A3B | 35B | 70 GB | 22 GB | comfortable (Q4), tight (FP16 ~70 GB) |
| Mistral Small 4 | 119B | 238 GB | 64 GB | tight (Q4; ~64 GB) |
| Mistral Medium 3.5 | 128B | 256 GB | 70 GB | won't fit |
| Llama 4 Maverick, DeepSeek V3.2, Mistral Large 3 | — | — | — | won't fit |

**Recommended models:** Qwen3.6 35B-A3B (Q4) for the best capability-per-dollar in this tier (3B active params keep decode fast, 35B total provides quality). Gemma 4 31B (Q4) for general use. Llama 4 Scout is technically fittable at Q4 but leaves almost no room for context or other apps — use the Mac Studio for Scout instead. ([source](https://like2byte.com/mac-mini-m4-local-llm-server-agency/))

### MacBook Air

The MacBook Air M5 line (2026) ships at 24 GB minimum and tops out at 32 GB. The M5 chip has 120 GB/s bandwidth — same as the base Mac mini M4 — so the Air is best thought of as a portable extension of the 24-32 GB Mac mini envelope, with the trade-off that thermals throttle sustained-load decode after 3-5 minutes. ([source](https://support.apple.com/en-us/126320))

#### MacBook Air 24 GB (M5)

- **Total unified memory:** 24 GB
- **OS + base app overhead:** ~6-7 GB (browser, Slack, etc. on a portable workhorse machine)
- **LLM budget remaining:** ~16-18 GB

| Model | Params | FP16 mem | Q4 mem | Verdict |
|---|---|---|---|---|
| Gemma 4 E4B | 4B | 8 GB | 2.5 GB | comfortable |
| Gemma 4 26B MoE | 26B | 52 GB | 15 GB | tight (Q4) |
| Gemma 4 31B Dense | 31B | 62 GB | 18 GB | tight (Q4) |
| Qwen3.6 27B | 27B | 55 GB | 17 GB | tight (Q4) |
| Qwen3.6 35B-A3B | 35B | 70 GB | 22 GB | won't fit (Q4 ~22 GB > 18 GB usable) |
| All 100B+ models | — | — | — | won't fit |

**Recommended models:** Gemma 4 E4B (Q4) for offline coding assistance and chat; Gemma 4 26B MoE (Q4) for stronger reasoning when plugged in (the MoE's 3.8B active params keep thermals manageable). Skip dense 27B-31B models on the 24 GB Air — they fit but thermals throttle hard.

#### MacBook Air 32 GB (M5)

- **Total unified memory:** 32 GB
- **OS + base app overhead:** ~6-7 GB
- **LLM budget remaining:** ~24-26 GB

| Model | Params | FP16 mem | Q4 mem | Verdict |
|---|---|---|---|---|
| Gemma 4 E4B | 4B | 8 GB | 2.5 GB | comfortable |
| Gemma 4 26B MoE | 26B | 52 GB | 15 GB | comfortable (Q4), tight (Q8) |
| Gemma 4 31B Dense | 31B | 62 GB | 18 GB | comfortable (Q4) |
| Qwen3.6 27B | 27B | 55 GB | 17 GB | comfortable (Q4) |
| Qwen3.6 35B-A3B | 35B | 70 GB | 22 GB | comfortable (Q4), tight (FP16) |
| All 100B+ models | — | — | — | won't fit |

**Recommended models:** Qwen3.6 27B (Q4) as the daily driver — strong quality, 17 GB footprint leaves plenty of room for Chrome and a few apps. Qwen3.6 35B-A3B (Q4) for coding sessions when you'll close other apps. Llama 4 Scout will not fit on any MacBook Air configuration.

### MacBook Pro

The MacBook Pro line (M5 Pro / M5 Max, 2026) is the practical local-inference sweet spot for most users: enough unified memory and bandwidth to run 30B-class dense models comfortably, plus the M5 Max 128 GB option for Scout. The MacBook Pro tops out at 128 GB; 192 GB and 256 GB are Mac Studio territory only. ([source](https://www.apple.com/newsroom/2026/03/apple-introduces-macbook-pro-with-all-new-m5-pro-and-m5-max/))

The M4 Pro 48 GB option is the "best price/perf" point in the MacBook Pro line for local LLMs; the M5 Max 128 GB is the "covers everything except Maverick / DeepSeek / Mistral Large 3" point.

#### MacBook Pro M4 Pro 48 GB

- **Total unified memory:** 48 GB
- **OS + base app overhead:** ~8-10 GB (dev workstation with IDE, browser, Slack, Docker)
- **LLM budget remaining:** ~38-40 GB

| Model | Params | FP16 mem | Q4 mem | Verdict |
|---|---|---|---|---|
| Gemma 4 E4B | 4B | 8 GB | 2.5 GB | comfortable |
| Gemma 4 26B MoE | 26B | 52 GB | 15 GB | comfortable (Q4), tight (Q8) |
| Gemma 4 31B Dense | 31B | 62 GB | 18 GB | comfortable (Q4) |
| Qwen3.6 27B | 27B | 55 GB | 17 GB | comfortable (Q4), tight (Q8) |
| Qwen3.6 35B-A3B | 35B | 70 GB | 22 GB | comfortable (Q4), tight (Q8) |
| Llama 4 Scout | 109B | 218 GB | 58 GB | won't fit |
| Mistral Small 4 | 119B | 238 GB | 64 GB | won't fit |
| Mistral Medium 3.5 | 128B | 256 GB | 70 GB | won't fit |

**Recommended models:** Qwen3.6 35B-A3B (Q4) as the daily driver. Gemma 4 31B (Q4) for slightly stronger English-language tasks. The M4 Pro 48 GB is the best machine for users who want strong open-weights local inference but don't need to run the very large MoE flagships.

#### MacBook Pro M5 Max 128 GB

- **Total unified memory:** 128 GB
- **OS + base app overhead:** ~10-12 GB
- **LLM budget remaining:** ~110-115 GB

| Model | Params | FP16 mem | Q4 mem | Verdict |
|---|---|---|---|---|
| Gemma 4 E4B | 4B | 8 GB | 2.5 GB | comfortable |
| Gemma 4 26B MoE | 26B | 52 GB | 15 GB | comfortable (any precision) |
| Gemma 4 31B Dense | 31B | 62 GB | 18 GB | comfortable (FP16 fits) |
| Qwen3.6 27B | 27B | 55 GB | 17 GB | comfortable (FP16 fits) |
| Qwen3.6 35B-A3B | 35B | 70 GB | 22 GB | comfortable (FP16 fits) |
| Llama 4 Scout | 109B | 218 GB | 58 GB | comfortable (Q4), tight (Q5) |
| Mistral Small 4 | 119B | 238 GB | 64 GB | comfortable (Q4), tight (Q5) |
| Mistral Medium 3.5 | 128B | 256 GB | 70 GB | comfortable (Q4) |
| Llama 4 Maverick | 400B | 800 GB | 220 GB | won't fit |
| DeepSeek V3.2 | 671B | 1342 GB | 340 GB | won't fit |
| Mistral Large 3 | 675B | 1350 GB | 340 GB | won't fit |

**Recommended models:** Llama 4 Scout (Q4) for long-context retrieval workloads — the 10M context window is the killer feature here. Qwen3.6 35B-A3B (Q8 or FP16) for coding (the quality bump from Q4 → FP16 is meaningful on routing-heavy MoE). Mistral Medium 3.5 (Q4) for the strongest dense local model that fits. ([source](https://hardwarepedia.com/blog/best-mac-for-local-ai-2026))

Decode-speed expectations on M5 Max 128 GB:

- Gemma 4 31B Q4: ~22 tok/s
- Qwen3.6 35B-A3B Q4: ~60 tok/s (3B active params)
- Llama 4 Scout Q4: ~30 tok/s (17B active params, MoE)
- Mistral Medium 3.5 Q4: ~9 tok/s (dense 128B; bandwidth-bound)

### Mac Studio

The Mac Studio is the only Mac that can run the very large MoE flagships (Llama 4 Maverick, DeepSeek V3.2, Mistral Large 3) at any practical quantization. The M3 Ultra is currently the top option, with 96 GB / 192 GB / 256 GB / 512 GB configurations and 800 GB/s memory bandwidth. ([source](https://news.ycombinator.com/item?id=46907001))

The M5 Ultra is expected mid-2026 with ~1,200 GB/s bandwidth; numbers below assume M3 Ultra.

#### Mac Studio M3 Ultra 192 GB

- **Total unified memory:** 192 GB
- **OS + base app overhead:** ~12-15 GB (typically a dedicated inference box)
- **LLM budget remaining:** ~175-180 GB

| Model | Params | FP16 mem | Q4 mem | Verdict |
|---|---|---|---|---|
| Gemma 4 31B Dense | 31B | 62 GB | 18 GB | comfortable (FP16) |
| Qwen3.6 35B-A3B | 35B | 70 GB | 22 GB | comfortable (FP16) |
| Llama 4 Scout | 109B | 218 GB | 58 GB | comfortable (Q4 / Q5 / Q8) |
| Mistral Medium 3.5 | 128B | 256 GB | 70 GB | comfortable (Q4 / Q5), tight (Q8) |
| Llama 4 Maverick | 400B | 800 GB | 220 GB | tight (Q4 ~220 GB > 180 GB usable) |
| DeepSeek V3.2 | 671B | 1342 GB | 340 GB | Q3-only (~250 GB at Q3_K_M) |
| Mistral Large 3 | 675B | 1350 GB | 340 GB | Q3-only (~270 GB Q3_K_M) |
| Mistral Small 4 | 119B | 238 GB | 64 GB | comfortable (Q4 / Q5 / Q8) |

**Recommended models:** Llama 4 Scout (Q8) for highest-quality long-context work. Mistral Medium 3.5 (Q5) for the strongest dense local model. DeepSeek V3.2 (Q3_K_M) for benchmark-class reasoning — Q3 is the practical floor for MoE routing quality on a 192 GB machine. ([source](https://venturebeat.com/ai/deepseek-v3-now-runs-at-20-tokens-per-second-on-mac-studio-and-thats-a-nightmare-for-openai))

#### Mac Studio M3 Ultra 256 GB

- **Total unified memory:** 256 GB
- **OS + base app overhead:** ~15 GB
- **LLM budget remaining:** ~240 GB

| Model | Params | FP16 mem | Q4 mem | Verdict |
|---|---|---|---|---|
| Llama 4 Scout | 109B | 218 GB | 58 GB | comfortable (FP16 fits with light headroom) |
| Llama 4 Maverick | 400B | 800 GB | 220 GB | comfortable (Q4), tight (Q5) |
| DeepSeek V3.2 | 671B | 1342 GB | 340 GB | comfortable (Q3_K_M ~250 GB) |
| Mistral Large 3 | 675B | 1350 GB | 340 GB | comfortable (Q3_K_M ~270 GB), tight (Q4) |
| Mistral Medium 3.5 | 128B | 256 GB | 70 GB | comfortable (Q8) |
| All smaller models | — | — | — | comfortable (any precision) |

**Recommended models:** Llama 4 Maverick (Q4) for the strongest open-weights model that fits well. DeepSeek V3.2 (Q3_K_M, expected ~40 tok/s at int4 quantization on M4 Ultra-class hardware). Mistral Large 3 (Q3_K_M) for the strongest open-weights dense-equivalent model. The 256 GB Mac Studio is the practical "runs everything in this matrix at quality" machine for 2026. ([source](https://huggingface.co/mlx-community/DeepSeek-V3.2-mlx-5bit))

Decode-speed expectations on M3 Ultra 256 GB:

- Llama 4 Maverick Q4: ~18 tok/s
- DeepSeek V3.2 Q3_K_M: ~22 tok/s (37B active; MoE)
- Mistral Large 3 Q3_K_M: ~15-22 tok/s (41B active; MoE)
- Mistral Medium 3.5 Q8: ~5-6 tok/s (dense 128B; bandwidth-bound)

---

## Per-model sections

### Gemma 4 E4B

- **Parameters:** 4B effective (Matformer architecture; the larger E12B variant can be elastically truncated to 4B)
- **License:** [Gemma terms of use](https://ai.google.dev/gemma/terms)
- **Profiles that run it well:** All of them. This is the universal small-tier model. ([source](https://gemma4-ai.com/blog/gemma4-mac-performance))
- **Expected MLX tokens/sec:**
  - M4 base (Mac mini 16 GB): ~80 tok/s Q4
  - M4 Pro (Mac mini 32-64 GB): ~95 tok/s Q4
  - M5 Max (MacBook Pro 128 GB): ~140 tok/s Q4
  - M3 Ultra (Mac Studio 192 GB+): ~160 tok/s Q4
- **KV cache cost at 8K context:** ~0.4 GB
- **KV cache cost at 128K context:** ~6 GB
- **Notes:** The default fallback for thermals-constrained portable devices. Ragbot's default `gemma4:e4b` Ollama tag picks Q4_K_M.

### Gemma 4 26B MoE

- **Parameters:** 26B total / ~3.8B active per token (MoE)
- **License:** Gemma
- **Profiles that run it well:** Mac mini 32 GB+ (Q4), MacBook Air 32 GB (Q4), all MacBook Pro and Mac Studio configurations. ([source](https://sudoall.com/gemma-4-31b-apple-silicon-local-guide/))
- **Expected MLX tokens/sec:**
  - M4 Pro Mac mini 64 GB: ~50 tok/s Q4
  - M5 Max MacBook Pro 128 GB: ~75 tok/s Q4 (MLX 20-30% faster than llama.cpp on MoE routing)
  - M3 Ultra Mac Studio: ~95 tok/s Q4
- **KV cache cost at 8K context:** ~1.2 GB
- **KV cache cost at 128K context:** ~19 GB

### Gemma 4 31B Dense

- **Parameters:** 31B dense
- **License:** Gemma
- **Profiles that run it well:** Mac mini 64 GB (Q4), MacBook Pro M4 Pro 48 GB+ (Q4), all higher-tier machines. ([source](https://sudoall.com/gemma-4-31b-apple-silicon-local-guide/))
- **Expected MLX tokens/sec:**
  - M4 Pro Mac mini 64 GB: ~14 tok/s Q4
  - M5 Max MacBook Pro 128 GB: ~22 tok/s Q4 (Ollama 0.19+ MLX backend; ~15 tok/s on Metal backend)
  - M3 Ultra Mac Studio: ~32 tok/s Q4
- **KV cache cost at 8K context:** ~1.6 GB
- **KV cache cost at 128K context:** ~26 GB
- **Notes:** The strongest dense Gemma 4 variant; preferred over the 26B MoE when output quality matters more than decode speed.

### Llama 4 Scout (17B-16E)

- **Parameters:** 17B active / 109B total (MoE, 16 experts)
- **License:** [Llama 4 Community License](https://www.llama.com/llama4/license/) (open weights with commercial-use restrictions; not OSI-approved)
- **Context window:** 10M tokens (Instruct variant) — the headline feature
- **Profiles that run it well:** MacBook Pro M5 Max 128 GB (Q4), all Mac Studio configurations. Won't fit on Mac mini or MacBook Air at any quantization. ([source](https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E))
- **Expected MLX tokens/sec:**
  - M5 Max 128 GB: ~30 tok/s Q4 (MoE active params drive decode speed)
  - M3 Ultra 192 GB: ~45 tok/s Q4
  - M3 Ultra 256 GB: ~50 tok/s Q4
- **KV cache cost at 8K context:** ~3 GB
- **KV cache cost at 128K context:** ~50 GB
- **KV cache cost at 1M context:** ~390 GB — requires aggressive KV-cache quantization to be tractable; the 10M context window is theoretical-ceiling, not "load a million tokens and chat" on any Mac
- **Notes:** All 109B parameters must fit in unified memory even though only 17B are active per token, because the router can pick any expert. MoE routing is quantization-sensitive; the jump from Q4 → Q5 produces more quality lift than the same jump on a dense model. ([source](https://www.sitepoint.com/llama-4-scout-on-mlx-the-complete-apple-silicon-guide-2026/))

### Llama 4 Maverick (17B-128E)

- **Parameters:** 17B active / 400B total (MoE, 128 experts)
- **License:** Llama 4 Community License
- **Context window:** 1M tokens
- **Profiles that run it well:** Mac Studio M3 Ultra 256 GB+ only. Q4 quant is ~220 GB which is too tight for the 192 GB Mac Studio. ([source](https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct))
- **Expected MLX tokens/sec:**
  - M3 Ultra 256 GB: ~18 tok/s Q4
  - M5 Ultra 512 GB (expected mid-2026): ~25-30 tok/s Q4
- **KV cache cost at 8K context:** ~3 GB
- **KV cache cost at 1M context:** ~390 GB
- **Notes:** The largest open-weights model in Ragbot's v3.4 lineup. Suitable for batch inference and overnight research workloads on the high-end Mac Studio; not a daily-driver model on any current Mac.

### Qwen3.6 27B Dense

- **Parameters:** 27B dense
- **License:** Apache 2.0 (true open-source)
- **Context window:** 256K tokens
- **Profiles that run it well:** Mac mini 32 GB+ (Q4), all MacBook Air 32 GB and above, all MacBook Pro and Mac Studio configurations. ([source](https://ollama.com/library/qwen3.6))
- **Expected MLX tokens/sec:**
  - M4 Pro Mac mini 64 GB: ~16 tok/s Q4
  - M5 Max MacBook Pro 128 GB: ~25 tok/s Q4 (qwen3.6:27b-mlx-bf16 native MLX tag)
  - M3 Ultra Mac Studio: ~38 tok/s Q4
- **KV cache cost at 8K context:** ~1.4 GB
- **KV cache cost at 128K context:** ~22 GB
- **Notes:** The strongest Apache-2.0 dense model that fits on consumer hardware. Ollama ships `qwen3.6:27b-mlx-bf16` (55 GB) for users with the memory; `qwen3.6:27b-mxfp8` (31 GB) and `qwen3.6:27b-q4_K_M` (17 GB) are the practical points.

### Qwen3.6 35B-A3B (MoE)

- **Parameters:** 35B total / 3B active per token (MoE)
- **License:** Apache 2.0
- **Context window:** 256K tokens
- **Thinking modes:** Hybrid (instruct + thinking) supported via the `thinking` field in the API. ([source](https://github.com/QwenLM/Qwen3.6))
- **Profiles that run it well:** Mac mini 64 GB (Q4), all MacBook Pro and Mac Studio. Borderline on 32 GB MacBook Air. ([source](https://botmonster.com/posts/qwen-3-6-35b-a3b-open-weight-coding-moe/))
- **Expected MLX tokens/sec:**
  - M4 Pro Mac mini 64 GB: ~45 tok/s Q4 (3B active params keep decode fast)
  - M5 Max MacBook Pro 128 GB: ~60 tok/s Q4
  - M3 Ultra Mac Studio: ~85 tok/s Q4
- **KV cache cost at 8K context:** ~1.8 GB
- **KV cache cost at 128K context:** ~28 GB
- **Notes:** Optimized for coding workloads in Alibaba's release. Excellent capability-per-dollar in the local-inference tier; the 3B active params combined with 35B total weights produce a quality-to-speed ratio better than most dense alternatives.

### DeepSeek V3.2

- **Parameters:** 671B total / 37B active per token (MoE)
- **License:** [DeepSeek Model License](https://github.com/deepseek-ai/DeepSeek-V3/blob/main/LICENSE-MODEL) (open weights, commercial use allowed with some conditions)
- **Context window:** 128K tokens, with sparse attention extending effective coverage further
- **Profiles that run it well:** Mac Studio M3 Ultra 192 GB+ at Q3_K_M; 256 GB or 512 GB for Q4. ([source](https://huggingface.co/mlx-community/DeepSeek-V3.2-mlx-5bit))
- **Expected MLX tokens/sec:**
  - M3 Ultra 192 GB Q3_K_M: ~18 tok/s
  - M3 Ultra 256 GB Q4: ~22 tok/s
  - M3 Ultra 512 GB Q4: ~25 tok/s (per [public report](https://apple.slashdot.org/story/25/03/25/2054214/deepseek-v3-now-runs-at-20-tokens-per-second-on-mac-studio))
  - M4 Ultra 256 GB int4: ~40 tok/s
- **KV cache cost at 8K context:** ~6 GB (sparse attention reduces this vs. dense 671B)
- **KV cache cost at 128K context:** ~95 GB
- **Notes:** Frontier-quality reasoning at the high end of the open-weights spectrum. Sparse Attention introduced in V3.2 makes long-context inference tractable on Apple Silicon in ways the original V3 was not. The MLX 5-bit quant ships at `mlx-community/DeepSeek-V3.2-mlx-5bit` and is the recommended starting point for Mac Studio 256 GB+ users.

### Mistral Large 3

- **Parameters:** 675B total / 41B active per token (sparse MoE)
- **License:** Apache 2.0 ([source](https://huggingface.co/mistralai/Mistral-Large-3-675B-Instruct-2512))
- **Context window:** 256K tokens
- **Profiles that run it well:** Mac Studio M3 Ultra 192 GB+ at Q3_K_M; 256 GB or higher for comfortable Q4. ([source](https://intuitionlabs.ai/articles/mistral-large-3-moe-llm-explained))
- **Expected MLX tokens/sec:**
  - M3 Ultra 192 GB Q3_K_M: ~12 tok/s
  - M3 Ultra 256 GB Q3_K_M: ~17 tok/s
  - M3 Ultra 512 GB Q4: ~22 tok/s
- **KV cache cost at 8K context:** ~6 GB
- **KV cache cost at 256K context:** ~190 GB (aggressive KV quant recommended for full context)
- **Notes:** The largest fully-Apache-2.0 open-weights model in this matrix. Direct competitor to DeepSeek V3.2 in the open-weights flagship category; choose Mistral Large 3 for permissive licensing and DeepSeek V3.2 for stronger reasoning benchmarks.

### Mistral Medium 3.5

- **Parameters:** 128B dense
- **License:** [Mistral Research License](https://mistral.ai/static/research/mistral-research-license.pdf) (non-commercial research use; commercial use requires a Mistral commercial license)
- **Context window:** 256K tokens
- **Profiles that run it well:** MacBook Pro M5 Max 128 GB (Q4), all Mac Studio. ([source](https://huggingface.co/mistralai/Mistral-Medium-3.5-128B))
- **Expected MLX tokens/sec:**
  - M5 Max 128 GB Q4: ~9 tok/s (dense 128B; bandwidth-bound)
  - M3 Ultra 192 GB Q5: ~12 tok/s
  - M3 Ultra 256 GB Q8: ~6 tok/s (Q8 is bandwidth-bound at this size)
- **KV cache cost at 8K context:** ~3 GB
- **KV cache cost at 256K context:** ~92 GB
- **Notes:** The strongest dense open-weights model that fits on a MacBook Pro. Quality is consistent across context lengths — no MoE routing artifacts. Lower tokens/sec than the MoE alternatives at the same memory footprint, which is the trade-off for dense quality.

### Mistral Small 4

- **Parameters:** 119B total / 6B active per token (MoE)
- **License:** Apache 2.0 ([source](https://mistral.ai/news/mistral-small-4))
- **Context window:** 256K tokens
- **Profiles that run it well:** MacBook Pro M5 Max 128 GB (Q4), all Mac Studio. The "Small" name refers to active params (6B), not weights footprint (~64 GB at Q4). ([source](https://www.popularai.org/p/mac-mini-llm-performance-in-2026))
- **Expected MLX tokens/sec:**
  - M5 Max 128 GB Q4: ~80 tok/s (6B active params; very fast decode)
  - M3 Ultra 256 GB Q8: ~70 tok/s
- **KV cache cost at 8K context:** ~3 GB
- **KV cache cost at 256K context:** ~92 GB
- **Notes:** The name is misleading — "Small" refers to the per-token compute (6B active) rather than the on-disk footprint (119B total weights). Apache 2.0 license. Best chosen when you want very fast decode on a Mac Studio and Apache 2.0 licensing matters; otherwise Qwen3.6 35B-A3B has similar properties at a smaller total footprint.

---

## Citations

The numbers in this matrix come from a combination of published vendor specs, third-party benchmarks, and community measurements. Inline citations link to the canonical source. Key references:

- [meta-llama/Llama-4-Scout-17B-16E - Hugging Face](https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E)
- [meta-llama/Llama-4-Maverick-17B-128E-Instruct - Hugging Face](https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct)
- [Llama 4 Scout on MLX: The Complete Apple Silicon Guide (2026) - SitePoint](https://www.sitepoint.com/llama-4-scout-on-mlx-the-complete-apple-silicon-guide-2026/)
- [Qwen3.6 release on Ollama](https://ollama.com/library/qwen3.6)
- [Qwen3 GitHub](https://github.com/QwenLM/Qwen3)
- [DeepSeek-V3.2-mlx-5bit - Hugging Face](https://huggingface.co/mlx-community/DeepSeek-V3.2-mlx-5bit)
- [DeepSeek-V3 - DeepSeek](https://huggingface.co/deepseek-ai/DeepSeek-V3)
- [Mistral Large 3 - Mistral AI](https://huggingface.co/mistralai/Mistral-Large-3-675B-Instruct-2512)
- [Mistral Medium 3.5 - Hugging Face](https://huggingface.co/mistralai/Mistral-Medium-3.5-128B)
- [Mistral Small 4 - Mistral AI](https://mistral.ai/news/mistral-small-4)
- [Apple MacBook Pro M5 Pro / M5 Max](https://www.apple.com/newsroom/2026/03/apple-introduces-macbook-pro-with-all-new-m5-pro-and-m5-max/)
- [Mac mini LLM performance in 2026 - PopularAI](https://www.popularai.org/p/mac-mini-llm-performance-in-2026)
- [Ollama MLX backend preview](https://ollama.com/blog/mlx)
- [MLX vs Ollama on Apple Silicon (2026) - Will It Run AI](https://willitrunai.com/blog/mlx-vs-ollama-apple-silicon-benchmarks)
- [Gemma 4 Mac M1 M2 M3 M4 performance](https://gemma4-ai.com/blog/gemma4-mac-performance)
- [Best Mac for Running AI Locally in 2026 - Hardwarepedia](https://hardwarepedia.com/blog/best-mac-for-local-ai-2026)
- [DeepSeek-V3 now runs at 20 tokens per second on Mac Studio - VentureBeat](https://venturebeat.com/ai/deepseek-v3-now-runs-at-20-tokens-per-second-on-mac-studio-and-thats-a-nightmare-for-openai)
- [What to Buy for Local LLMs (April 2026) - Julien Simon](https://julsimon.medium.com/what-to-buy-for-local-llms-april-2026-a4946a381a6a)

Numbers should be treated as approximations. Actual decode speed varies with concurrent system load, thermal state, KV cache size, and the specific Ollama / MLX version. The "comfortable / tight / Q4-only / won't fit" verdicts are the load-bearing part of this document — they are conservative on the side of leaving headroom, because a hot loaded model OOM-killing the user's other applications is a worse experience than a slightly slower decode.

## Workflow-specific recommendations

The matrix above answers "will this model fit?" This section answers "which model should I pick for this kind of work?"

### Conversational chat and Q&A

The dominant Ragbot workload. Decode speed matters more than tip-of-the-bell-curve quality. Recommended models by hardware tier:

- **Mac mini 16 GB:** Gemma 4 E4B (Q4). The only practical choice.
- **Mac mini 32 GB / MacBook Air 32 GB:** Qwen3.6 27B (Q4). Strong English, code, and reasoning. ~17 GB footprint leaves room for browser and IDE.
- **Mac mini 64 GB / MacBook Pro M4 Pro 48 GB:** Qwen3.6 35B-A3B (Q4). The capability-per-tok/s sweet spot at this tier.
- **MacBook Pro M5 Max 128 GB:** Llama 4 Scout (Q4) for long contexts and retrieval, or Qwen3.6 35B-A3B (Q8) for highest-quality short-context chat.
- **Mac Studio 192 GB+:** Llama 4 Scout (Q8 or FP16). Mistral Small 4 (Q5) as a fast alternative.

### RAG with long retrieved context

Workloads where Ragbot loads 32K-256K tokens of retrieved snippets and the model summarizes / reasons over them. KV cache cost becomes the dominant constraint, not model weights. Pick models with smaller per-token KV footprint:

- **Mac mini 32-64 GB:** Qwen3.6 27B (Q4) at 32K context. Higher contexts push KV cache past available memory.
- **MacBook Pro 48 GB:** Gemma 4 31B (Q4) at 64K context. Dense layers have predictable quality across long retrieved chunks.
- **MacBook Pro M5 Max 128 GB:** Llama 4 Scout (Q4) at 256K context with Q8 KV cache enabled. The 10M context ceiling is not practical but 256K-1M is.
- **Mac Studio 192 GB+:** Llama 4 Scout (Q5) at 1M context with Q8 KV. The configuration where the long-context story actually shines.

### Code generation and tool calling

Workloads where Ragbot's agent loop iterates with tools and the model needs to produce correct, executable code. Quality matters more than tokens/sec; quantization matters more than for chat:

- **Mac mini 64 GB / MacBook Pro 48 GB:** Qwen3.6 35B-A3B (Q5 or Q8 if it fits). Tuned for coding in Alibaba's release.
- **MacBook Pro M5 Max 128 GB:** Qwen3.6 35B-A3B (Q8 or FP16). The Q4 → Q8 jump produces visible quality lift on routing-heavy MoE for code.
- **Mac Studio 192 GB+:** Mistral Medium 3.5 (Q5 or Q8). Dense 128B avoids MoE routing artifacts on code edge cases. Slower but more consistent.

### Math and reasoning benchmarks

The hardest workload for local models. Cloud-frontier still has the edge on benchmark-class reasoning; the v3.4 lineup catches up on Mac Studio:

- **MacBook Pro M5 Max 128 GB:** Qwen3.6 35B-A3B with thinking mode enabled. Mistral Medium 3.5 (Q4) for non-MoE-routing comparison.
- **Mac Studio 256 GB+:** DeepSeek V3.2 (Q4 if 256 GB, Q5 if 512 GB). The strongest open-weights reasoning model in the matrix.
- **Mac Studio 256 GB+:** Mistral Large 3 (Q3_K_M or Q4). Apache 2.0 alternative to DeepSeek V3.2 with comparable reasoning quality on most benchmarks.

### Multimodal (image input)

Llama 4 Scout and Maverick are natively multimodal. The other models in the v3.4 lineup are text-only:

- **MacBook Pro M5 Max 128 GB:** Llama 4 Scout (Q4) for image-input chat.
- **Mac Studio 256 GB+:** Llama 4 Maverick (Q4) for the strongest multimodal open-weights model.

### Agent loops with high turn frequency

Ragbot's agent loop iterates with tool calls; the per-turn latency matters more than the throughput of any single response. Pick models with the fastest time-to-first-token on the loaded weights:

- **Mac mini 32-64 GB:** Qwen3.6 35B-A3B (Q4). 3B active params → low TTFT.
- **MacBook Pro M5 Max 128 GB:** Mistral Small 4 (Q4). 6B active params → very low TTFT on a high-bandwidth Mac.
- **Mac Studio 192 GB+:** Qwen3.6 35B-A3B (FP16) or Mistral Small 4 (Q8). Either provides high-quality output with low per-turn latency.

## Quick-reference summary table

This table compresses the matrix to a single-page reference. For each (model, hardware) pair the entry is the recommended quantization. `—` means the model doesn't fit at any quantization. `na` means the model is too small to make sense on that hardware (use a stronger model instead):

| Model | mini 16 | mini 32 | mini 64 | Air 24 | Air 32 | MBP 48 | MBP 128 | Studio 192 | Studio 256 |
|---|---|---|---|---|---|---|---|---|---|
| Gemma 4 E4B | Q4 | Q4 | Q8 | Q4 | Q8 | Q8 | FP16 | FP16 | FP16 |
| Gemma 4 26B MoE | — | Q4 | Q4 | Q4 | Q4 | Q8 | FP16 | FP16 | FP16 |
| Gemma 4 31B Dense | — | Q4 | Q4 | Q4 | Q4 | Q4 | FP16 | FP16 | FP16 |
| Qwen3.6 27B | — | Q4 | Q4 | Q4 | Q4 | Q5 | FP16 | FP16 | FP16 |
| Qwen3.6 35B-A3B | — | Q4 | Q4 | — | Q4 | Q5 | Q8 | FP16 | FP16 |
| Llama 4 Scout | — | — | Q4 | — | — | — | Q4 | Q5 | Q8 |
| Llama 4 Maverick | — | — | — | — | — | — | — | — | Q4 |
| DeepSeek V3.2 | — | — | — | — | — | — | — | Q3_K_M | Q3_K_M |
| Mistral Large 3 | — | — | — | — | — | — | — | Q3_K_M | Q3_K_M |
| Mistral Medium 3.5 | — | — | — | — | — | — | Q4 | Q5 | Q8 |
| Mistral Small 4 | — | — | — | — | — | — | Q4 | Q5 | Q8 |

Read this table top-to-bottom (each row = one model, scan left-to-right for the lowest hardware that runs it at the recommended quant) or left-to-right (each column = one Mac, scan top-to-bottom for the strongest model that fits).

## Cross-cutting topics

### MLX vs. llama.cpp Metal vs. Ollama backends

Ragbot's local-inference path runs through Ollama by default (`ollama_chat/` LiteLLM prefix). Ollama itself has three relevant backend generations:

1. **llama.cpp Metal** (Ollama 0.18 and earlier on Apple Silicon). The original local-inference path. Reliable, broad model support, GGUF-based. Throughput is 20-40% slower than MLX on most models, with the gap widening on MoE architectures because the GGUF expert routing has more overhead than the MLX equivalent.

2. **MLX preview backend** (Ollama 0.19+, March 2026). Auto-activates on Apple Silicon Macs with 32 GB+ unified memory. Bypasses GGUF entirely; loads MLX-format weights and talks directly to the Metal runtime. Roughly doubles decode speed on MoE models compared to the Metal backend on the same Mac. ([source](https://ollama.com/blog/mlx))

3. **Native MLX (no Ollama)**. Some Hugging Face users ship MLX-native model tags (`mlx-community/...`) that bypass Ollama and load directly via `mlx_lm`. The performance ceiling is highest here, but the ergonomics are worse — no model registry, no server, no LiteLLM integration without writing the glue.

Ragbot's default recommendation is **Ollama 0.19+ with MLX backend on 32 GB+ Macs, llama.cpp Metal on smaller Macs**. The numbers in the per-hardware sections above assume this configuration. If you've manually configured `mlx_lm` for direct inference, expect the numbers to be ~10-20% better.

### When to prefer MoE vs. dense

The v3.4 model lineup includes both architectures. The choice has trade-offs:

**MoE strengths:**
- Faster decode at equivalent total parameter count (only active params hit memory bandwidth per token)
- Better capability-per-watt — fewer FLOPs per token for the same output quality
- Scales gracefully to flagship sizes (Maverick at 400B, Mistral Large 3 at 675B)

**MoE weaknesses:**
- All expert weights must fit in unified memory even though only a fraction are active. This is the dominant constraint on Apple Silicon, which has unified memory but not the dozens of GB/s of SSD bandwidth that would make expert paging viable.
- More quantization-sensitive. Router quality degrades faster than dense layer quality as precision drops. Q4 on dense 32B is usually fine; Q4 on MoE 109B may show visible quality regressions on complex prompts.
- KV cache memory is the same as the dense equivalent — it doesn't shrink because the active parameters are smaller.

**Dense strengths:**
- More predictable quality across prompt types
- Less sensitive to quantization
- Simpler runtime (no routing overhead)

**Dense weaknesses:**
- Throughput is bandwidth-bound; a dense 128B at Q4 is ~9 tok/s on M5 Max even though the same Mac runs an MoE 109B at ~30 tok/s
- Doesn't scale efficiently beyond ~100B on consumer hardware

**Ragbot's default recommendation:** Pick MoE for daily-driver workloads (chat, RAG, summarization, lightweight code) where decode speed matters more than the marginal quality difference. Pick dense (Mistral Medium 3.5, Gemma 4 31B) for code generation, math, and long-context analysis where quality consistency matters more than tokens/sec.

### KV cache quantization

The KV cache costs documented in the per-model sections assume FP16 KV (MLX default). For long-context work (>32K tokens), KV cache memory often dominates the total footprint. Two mitigations:

1. **Q8 KV cache.** Halves KV memory with negligible quality loss for most workloads. Ragbot does not enable this by default but it's a single flag in Ollama (`OLLAMA_FLASH_ATTENTION=1` + `OLLAMA_KV_CACHE_TYPE=q8_0`). Worth enabling on any Mac with <128 GB unified memory if you regularly load contexts above 64K.

2. **Q4 KV cache.** Quarters KV memory. Quality loss is noticeable on long contexts where the model is reasoning back-and-forth over distant tokens. Suitable for retrieval-heavy workloads where the long context is mostly "stuffed documents the model reads once" rather than "rolling conversation history."

The 10M context on Llama 4 Scout and 1M context on Maverick are theoretical ceilings — even Q4 KV cache on a 1M context is ~100 GB. Realistic workloads on these models use 64K-256K of the available context window.

### Thinking modes on local models

Qwen3.6 35B-A3B is the only model in the v3.4 local-inference lineup that exposes a thinking mode (hybrid: `thinking` and `instruct`). The mode is controlled via the LiteLLM `thinking` parameter, which Ragbot wires through `reasoning_effort` for the cloud-flagship thinking models and through a Qwen-specific path for this model. Other local models (Gemma 4, Llama 4, DeepSeek V3.2, Mistral) do not expose a separate thinking mode in their open-weights releases as of May 14, 2026, even when the cloud-hosted versions might. This may change with future releases.

### Multi-model loading on the same Mac

Several profiles in the matrix list multiple "comfortable" models. The matrix verdicts assume only one model is loaded at a time. If your workflow requires keeping multiple models warm:

- **Two-model warm:** Subtract both models' footprints from the LLM budget. On an M5 Max 128 GB with ~110 GB LLM budget, this means you can keep Qwen3.6 35B-A3B (Q4, ~22 GB) and Gemma 4 31B (Q4, ~18 GB) simultaneously warm, leaving ~70 GB for KV cache and other apps.
- **Three-model warm:** Practical only on Mac Studio 192 GB+. Useful for benchmarking and A/B comparison workflows.
- **Hot-swap via Ollama.** Ollama unloads cold models after 5 minutes of inactivity by default. Setting `OLLAMA_KEEP_ALIVE=-1` keeps them resident; setting it to `30s` aggressively unloads. The right value depends on whether you're optimizing for switch latency or total memory pressure.

### Recommended starting configurations

For new users picking a Mac specifically for local Ragbot inference, the order of preference (best capability-per-dollar to best absolute capability) is:

1. **Mac mini M4 Pro 64 GB** — ~$2,200. Runs Qwen3.6 35B-A3B (Q4) and Gemma 4 31B (Q4) comfortably. The "good enough" floor.
2. **MacBook Pro M4 Pro 48 GB** — ~$2,800. Same model envelope as Mac mini 64 GB plus portability and thermals. The "portable workhorse" pick.
3. **MacBook Pro M5 Max 128 GB** — ~$5,500. Adds Llama 4 Scout (Q4), Mistral Medium 3.5 (Q4), and Mistral Small 4 (Q4). The "covers everything except flagships" pick.
4. **Mac Studio M3 Ultra 256 GB** — ~$8,000. Adds Llama 4 Maverick (Q4), DeepSeek V3.2 (Q3_K_M), Mistral Large 3 (Q3_K_M). The "runs everything" pick for serious local-inference workloads.
5. **Mac Studio M3 Ultra 512 GB** — ~$10,000+. Adds Q4 quality on all the flagships and headroom for KV cache at full context. The benchmark configuration.

Each step up the ladder adds capability in the form of model classes that become accessible, not pure tokens/sec gains. If your workload is well-served by Qwen3.6 35B-A3B (which covers chat, RAG, and most coding), step 1 is sufficient. If your workload requires DeepSeek V3.2 quality, step 4 is the floor.

### Cost-of-tokens vs. cloud APIs

Local inference has a high fixed cost (hardware) and near-zero marginal cost (electricity). Cloud APIs have zero fixed cost and a per-token marginal cost. The break-even depends on usage volume. As a rough heuristic for May 2026 pricing:

- A Mac Studio M3 Ultra 256 GB ($8,000) running DeepSeek V3.2 (Q3_K_M) at ~22 tok/s amortizes against ~$8,000 of cloud-frontier API spend.
- A MacBook Pro M5 Max 128 GB ($5,500) running Llama 4 Scout (Q4) at ~30 tok/s amortizes against ~$3,000-5,000 of cloud-flagship API spend (Scout-class capability is in the second-tier cloud price bracket, not the very top).
- The Mac mini M4 Pro 64 GB ($2,200) running Qwen3.6 35B-A3B (Q4) at ~45 tok/s amortizes against ~$1,500-2,500 of cloud-mid-tier API spend.

These break-evens shrink fast for users who run inference 24/7 (overnight batch jobs, agent loops, autonomous research). They grow for users who run inference for a few hours per week, where the cloud APIs win on raw cost-of-tokens. Ragbot supports both; the matrix is here so you can match the hardware to your workload.

## Keeping this matrix current

`engines.yaml` is the single source of truth for which models Ragbot exposes. When entries are added, removed, or have their `local_inference` block updated, this matrix is updated in the same PR. The verification artifact at [`docs/v3.4-model-additions-2026-05.md`](v3.4-model-additions-2026-05.md) documents which sources were consulted for each v3.4-era model addition.
