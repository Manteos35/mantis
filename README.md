# ⚡ Mantis Crypto Radar

A high-performance, asynchronous on-chain token scanner engineered for **Solana** and **Base** ecosystems. Mantis identifies newly surfaced token pairs, filters them through real-time liquidity/volume thresholds, executes an automated risk assessment pipeline (detecting honeypots, minting permissions, and liquidity locks), and dispatches actionable trade signals to Telegram with direct execution terminals.

---

## 🚀 Key Features

* **Dual-Chain Parallel Ingestion:** Concurrent scanning across Solana and Base using `httpx` connection pooling and `asyncio.gather`.
* **Multi-Layer Security Pipeline:** Automated contract security checks via RugCheck and GoPlus APIs (flags mint authority, freeze authority, honeypots, and top-holder concentration).
* **Persistent Deduplication:** SQLite state machine running in WAL mode to eliminate redundant alerts across restarts.
* **Smart Rate Limiting:** Concurrency control with `asyncio.Semaphore`, proactive 429 backoff handling, and jittered retries.
* **Instant Execution UX:** Telegram notifications formatted with instant trading action buttons (Trojan Bot, BullX Terminal, DexScreener, and One-Tap CA Sharing).
* **System Telemetry:** Automated hourly diagnostic reporting tracking scanned pools, filtered volume, blocked rugs, and engine uptime.

---

## 🛠️ Architecture
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
---

## 📦 Getting Started

### Prerequisites
* Python 3.10+
* Node.js & PM2 (for 24/7 background deployment)
* Linux / VPS environment

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/Manteos35/mantis.git](https://github.com/Manteos35/mantis.git)
   cd mantis
Set up the virtual environment:Bashpython3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Configure Environment Variables:Bashcp .env.example .env
micro .env
Fill in your Telegram credentials:Kod snippet'iTELEGRAM_BOT_TOKEN="your_bot_token_here"
TELEGRAM_CHAT_ID="your_channel_or_chat_id_here"
Run the Engine:Development / Testing:Bashpython3 hunter.py
Production (PM2):Bashpm2 start hunter.py --name "mantis-radar" --interpreter ./venv/bin/python3
pm2 save
pm2 startup
🛡️ Security Verification MatrixCheckSolana MechanismEVM / Base MechanismThresholdMint AuthorityToken Program MetadataContract owner() / Mint FunctionMust be RevokedFreeze AuthorityToken Program Freeze KeyContract Freeze FunctionsMust be RevokedLiquidity LockLP Burn / Raydium Vault StateDEX Pair LP Token BalanceMinimum 80% LockedConcentrationTop 10 Holder BalancesTop 10 Holder Balances< 40% Cumulative SupplyTradeabilityOn-Chain SimulationGoPlus Honeypot DetectionZero Honeypot Risk⚠️ DisclaimerThis software is intended for informational and analytical purposes only. Cryptocurrency trading, especially micro-cap tokens, involves substantial financial risk. Perform your own due diligence before executing any trades.
