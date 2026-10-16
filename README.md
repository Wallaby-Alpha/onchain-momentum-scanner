# On-Chain Momentum Scanner & Performance Tracker

An automated scanner and ranker for finding high-momentum **on-chain market leaders** (typically $200k–$10M market cap, >2.5 days old, liquid pools) using the DexScreener, Raydium & GeckoTerminal APIs.

The system dispatches formatted Telegram alerts with multi-timeframe order flow metrics, logs alert snapshots into a local SQLite database, and includes a **Forward Performance Evaluator** so you can audit how alerted tokens actually performed over subsequent hours and days.

---

## 🎯 Target Universe & Philosophy

Most on-chain bots chase 5-minute microcap launches (<$50k market cap) that rug within 2 hours. This scanner is built specifically for **structural trend leaders**:
1. **Established Lindy Age**: Default > 2.5 days old (filters out 99% of instant rugs and pump.fun snipes).
2. **Growth & Mid-Cap Sweet Spot**: $200k to $10M market cap (sufficient market traction before major CEX saturation).
3. **Liquidity Depth**: > $20k pool reserve to prevent excessive slippage.
4. **Fractal Trend & Order Flow**: Sustained green alignment across 1h, 6h, and 24h intervals with >50% buyer transaction ratio.
5. **Anti-Wash Sanity**: Rejects pairs with extreme turnover ratios driven by bot wash loops.

---

## 🏗 System Architecture (3,000-Token Scaled Pipeline)

```
┌──────────────────────────────────────────┐
│  High-Scale Universe Discovery (3,000)   │
│  - Persistent SQLite Registry (Active)   │
│  - Raydium V3 Top-Volume Pools (Solana)  │
│  - GeckoTerminal Trending & Top Pools    │
│  - CoinGecko Base/BSC/ETH/Arbitrum Lists │
└────────────────────┬─────────────────────┘
                     │ 3,000 Candidate Tokens
                     ▼
┌──────────────────────────────────────────┐
│  Async DexScreener Enrichment (aiohttp)  │
│  - 100 parallel batches (30 tokens/call) │
│  - Resolves ~1,000 primary pairs in ~5s  │
│  - Auto-updates local SQLite registry    │
└────────────────────┬─────────────────────┘
                     │ Full Metrics Payload
                     ▼
┌──────────────────────────────────────────┐
│  Filtering & Quantitative Momentum Score │
│  - Age & Market Cap gates                │
│  - Multi-timeframe trend (40%)           │
│  - Buyer transaction dominance (30%)     │
│  - Volume acceleration velocity (20%)    │
│  - Liquidity depth (10%)                 │
└────────────────────┬─────────────────────┘
                     │ Ranked Leaders
                     ▼
┌──────────────────────────────────────────┐
│  Tracker & Alert Engine                  │
│  - Cooldown gate (prevents duplicate spam│
│  - SQLite database snapshot storage      │
│  - Rich HTML Telegram notification       │
└──────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│  Forward Performance Evaluator           │
│  python -m src.evaluator                 │
│  - Live price fetch vs alert price       │
│  - Win rate % and runner identification  │
└──────────────────────────────────────────┘
```

---

## 🚀 Quick Start (Local Run)

### 1. Clone & Install Dependencies
```bash
git clone <your-repo-url>
cd onchain-momentum-scanner

# Create Python virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment
Copy the example configuration:
```bash
cp .env.example .env
```
Edit `.env` to set your parameters:
* `TELEGRAM_BOT_TOKEN`: Your token from [@BotFather](https://t.me/BotFather)
* `TELEGRAM_CHAT_ID`: Your chat ID (get via [@userinfobot](https://t.me/userinfobot))
*(If left empty, alerts will print directly to the console).*

### 3. Dry Run Test (Immediate Console Table)
Run a single scan right away to view currently discovered momentum leaders:
```bash
python test_run.py
```

### 4. Run Single Scan Cycle & Record to Database
```bash
python -m src.main --once
```

### 5. Run Continuous Daemon
```bash
python -m src.main
```

---

## 📊 Forward Performance Evaluator

The core feature for auditing your strategy: compare every alerted coin against its live price to evaluate real-world performance:

```bash
python -m src.evaluator
```

**Sample Output:**
```
Evaluating performance for 2 past alert(s)...

╒══════╤══════════════════╤═══════════╤══════════╤═════════╤═════════╤═══════════════╤═════════════════╤════════════╕
│   ID │ Alerted At       │ Elapsed   │ Symbol   │ Chain   │   Score │ Alert Price   │ Current Price   │ Return %   │
╞══════╪══════════════════╪═══════════╪══════════╪═════════╪═════════╪═══════════════╪═════════════════╪════════════╡
│    2 │ 2026-10-15 00:01 │ 2.4h ago  │ SI276    │ solana  │    46.3 │ $0.0014       │ $0.0018         │ 🚀 +28.5%  │
├──────┼──────────────────┼───────────┼──────────┼─────────┼─────────┼───────────────┼─────────────────┼────────────┤
│    1 │ 2026-10-15 00:01 │ 2.4h ago  │ DOPE     │ solana  │    49.4 │ $0.0042       │ $0.0039         │ 🟡 -7.1%   │
╘══════╧══════════════════╧═══════════╧══════════╧═════════╧═════════╧═══════════════╧═════════════════╧════════════╛

📊 Summary Statistics:
• Total Evaluated: 2
• Positive Return Win Rate: 50.0% (1/2)
• Runners (> +20% gain): 50.0% (1/2)
```

---

## 🌐 Deploying to DigitalOcean Droplet

### Option A: 1-Click Systemd Service (Recommended)

1. Create a basic **Ubuntu 24.04 LTS Droplet** on DigitalOcean ($4 - $6/mo droplet is more than sufficient).
2. SSH into your droplet:
   ```bash
   ssh root@<YOUR_DROPLET_IP>
   ```
3. Clone your GitHub repository to `/opt/onchain-momentum-scanner`:
   ```bash
   git clone https://github.com/<your-username>/onchain-momentum-scanner.git /opt/onchain-momentum-scanner
   cd /opt/onchain-momentum-scanner
   ```
4. Run the automated setup script:
   ```bash
   chmod +x deploy/setup_droplet.sh
   ./deploy/setup_droplet.sh
   ```
5. Configure your `.env` with your Telegram credentials:
   ```bash
   cp .env.example .env
   nano .env
   ```
6. Start & enable the background daemon:
   ```bash
   systemctl start onchain-momentum
   systemctl enable onchain-momentum
   ```
7. Check live streaming logs:
   ```bash
   journalctl -u onchain-momentum -f
   ```

---

### Option B: Docker Compose

If you prefer containerized deployment:

```bash
# Install Docker on Ubuntu
curl -fsSL https://get.docker.com | sh

# Configure .env
cp .env.example .env
nano .env

# Build and start in detached background mode
docker compose up -d --build

# View container logs
docker compose logs -f
```

---

## ⚙️ Configuration Reference (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SCAN_INTERVAL_MINUTES` | `15` | Minutes between automated scans |
| `TOP_PICKS_PER_SCAN` | `3` | Maximum alerts dispatched per cycle |
| `ALERT_COOLDOWN_HOURS` | `12` | Cooldown to prevent repeating the same token |
| `MIN_MCAP_USD` | `1000000` | Minimum Market Cap ($1M) |
| `MAX_MCAP_USD` | `60000000` | Maximum Market Cap ($60M) |
| `MIN_AGE_DAYS` | `2.5` | Minimum pair age in days |
| `MIN_LIQUIDITY_USD` | `100000` | Minimum liquidity reserve ($100k) |
| `MIN_VOLUME_24H_USD` | `300000` | Minimum 24h trading volume |
| `MIN_BUYER_RATIO_1H` | `0.48` | Minimum fraction of 1h txns that are buys |
| `MIN_PRICE_CHANGE_1H` | `-3.0` | Maximum 1h pullback allowed |
| `MIN_PRICE_CHANGE_6H` | `0.0` | Minimum 6h price change |
| `MIN_PRICE_CHANGE_24H` | `5.0` | Minimum 24h price change |
| `MIN_MOMENTUM_SCORE` | `45.0` | Minimum composite score (0-100) |
| `ENABLED_CHAINS` | `solana,base,ethereum,bsc` | Comma-separated target networks |
