# ⚡ Mantis Crypto Radar

A high-performance, asynchronous on-chain token scanner engineered for **Solana** and **Base** ecosystems. Mantis identifies newly surfaced token pairs, filters them through real-time liquidity/volume thresholds, executes an automated risk assessment pipeline, and dispatches actionable trade signals to Telegram with direct execution terminals.

---

## 🚀 Key Features

* **Dual-Chain Parallel Ingestion:** Concurrent scanning across Solana and Base using `httpx` connection pooling and `asyncio.gather`.
* **Multi-Layer Security Pipeline:** Automated contract security checks via RugCheck and GoPlus APIs (flags mint authority, freeze authority, honeypots, and top-holder concentration).
* **Persistent Deduplication:** SQLite state machine running in WAL mode to eliminate redundant alerts across restarts.
* **Smart Rate Limiting:** Concurrency control with `asyncio.Semaphore`, proactive 429 backoff handling, and jittered retries.
* **Instant Execution UX:** Telegram notifications formatted with instant trading action buttons (Trojan Bot, BullX Terminal, DexScreener, and CA copy).
* **System Telemetry:** Automated hourly diagnostic reporting tracking scanned pools, filtered volume, blocked rugs, and engine uptime.

---

## 🛠️ Architecture

```text
DexScreener Feeds ───► Concurrency Control (Semaphore)
                             │
                             ▼
                    Liquidity & Vol Filter
                             │
                             ▼
                  Security Engine (RugCheck / GoPlus)
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
       [Risk Score > 30]             [Risk Score <= 30]
         Dropped (Rug)                      │
                                            ▼
                                  SQLite Deduplication
                                            │
                                            ▼
                                   Telegram Dispatcher
