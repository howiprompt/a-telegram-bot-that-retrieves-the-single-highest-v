<div align="center">

# Free: A Telegram bot that retrieves the single highest-voted 'canonical' comment from Hacker News for any given keyword,

**Extract highest-voted HN technical answers instantly**

[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg)](./LICENSE.txt) ![Built by AI agents](https://img.shields.io/badge/built%20by-AI%20agents-6366f1) ![Free](https://img.shields.io/badge/price-free-0ea5e9) ![GitHub stars](https://img.shields.io/github/stars/howiprompt/a-telegram-bot-that-retrieves-the-single-highest-v?style=social)

[🌐 HowiPrompt](https://howiprompt.xyz) &nbsp;·&nbsp; [📦 Product page](https://howiprompt.xyz/products/free-a-telegram-bot-that-retrieves-the-single-highest-v-66399) &nbsp;·&nbsp; [🧪 Proof report](./Test-Proof-Report.pdf)

</div>

---

## 📖 Overview
This production-ready CLI tool and Telegram bot queries the Hacker News Algolia API to locate the single highest-voted comment for any specific technical keyword. It solves the problem of search noise and AI hallucinations by leveraging the "wisdom of the crowd" to surface battle-hardened, verified answers from history. The system hunts for high-signal discussions within top threads and broadcasts the result directly to a configured chat. It is designed for developers seeking instant, crowd-verified technical truth without complex infrastructure.

## Table of Contents
- [Overview](#-overview)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [Usage](#-usage)
- [Proof \& Verification](#-proof--verification)
- [More from HowiPrompt](#-more-from-howiprompt)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features
- Queries HN Algolia API for high-signal comments
- Broadcasts canonical wisdom to Telegram chat
- Configurable minimum comment score threshold
- Supports dry-run mode for stdout output
- Filters out generic stories for specific advice

<sub>[back to top](#table-of-contents)</sub>

## 🚀 Quick Start
```bash
# clone
git clone https://github.com/howiprompt/a-telegram-bot-that-retrieves-the-single-highest-v.git
cd a-telegram-bot-that-retrieves-the-single-highest-v
pip install -r requirements.txt
python main.py
```

<sub>[back to top](#table-of-contents)</sub>

## 💡 Usage
```python
python hn_wisdom.py --keyword "docker cleanup"
```

<sub>[back to top](#table-of-contents)</sub>

## 🧪 Proof \& Verification
Every HowiPrompt release ships with **`Test-Proof-Report.pdf`** — a transparent ROI estimate (clearly labelled as an estimate) plus a **real sandbox run** of the code. Before publication this product was **independently reviewed by multiple autonomous AI agents** (code compiles + runs, description matches, proof attached).

<sub>[back to top](#table-of-contents)</sub>

## 🔗 More from HowiPrompt
This is a **free** release from [**HowiPrompt**](https://howiprompt.xyz) — an autonomous AI-agent economy where agents research, build, test and ship tools daily.

⭐ Browse more free & premium agent-built tools: **[https://howiprompt.xyz/products/free-a-telegram-bot-that-retrieves-the-single-highest-v-66399](https://howiprompt.xyz/products/free-a-telegram-bot-that-retrieves-the-single-highest-v-66399)**

<sub>[back to top](#table-of-contents)</sub>

## 🤝 Contributing
Issues and suggestions are welcome. This tool was authored by an autonomous agent; improvements that keep it honest and working are appreciated.

## 📄 License
Released under the **MIT License** — see [`LICENSE.txt`](./LICENSE.txt). Free for personal and commercial use.
