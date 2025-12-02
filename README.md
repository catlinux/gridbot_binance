# ⚡ GridBot Pro - Binance Automated Trading

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-green.svg)
![Binance](https://img.shields.io/badge/Binance-Connect-yellow.svg)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)

Un bot de trading automàtic d'alta freqüència basat en l'estratègia **Grid Trading Estàtic**. Dissenyat per a **Binance** (Spot), amb panell de control web en temps real, gestió d'errors robusta i capacitat de reconfiguració en calent.

![Dashboard Preview](docs/screenshots/dashboard_preview.png)
*(Pots afegir captures a una carpeta docs/screenshots)*

---

## 🚀 Característiques Principals

### 🧠 Nucli Intel·ligent
* **Grid Estàtic:** Utilitza línies de preu fixes per evitar el desplaçament (drift) i garantir compres baixes i vendes altes.
* **Multi-Parell:** Opera simultàniament amb múltiples monedes (BTC, ETH, XRP, DOGE...) amb configuracions independents.
* **Hot Reload 🔄:** Canvia la configuració (`config.json5`) sense aturar el bot. El sistema detecta els canvis i recalcula les graelles al vol.
* **Protecció d'Inventari 🛡️:** Si reinicies l'estratègia, el bot "congela" les monedes comprades anteriorment per no vendre-les amb pèrdues.

### 🌐 Panell de Control Web
* **Dashboard Professional:** Visió global del saldo, beneficis de sessió i estat del sistema.
* **Gràfics en Temps Real:** Integració amb **Apache ECharts** per visualitzar espelmes i línies de grid.
* **Timeframes Configurables:** Canvia la vista del gràfic (1m, 5m, 1h, 4h...) a l'instant.
* **Dades Històriques:** Taules detallades d'ordres obertes i operacions completades.

### ⚙️ Seguretat i Robustesa
* **Tolerància a Fallades d'API:** Gestiona timeouts i errors de Binance sense penjar-se.
* **Anti-Duplicats:** Lògica de *Fuzzy Matching* per evitar posar ordres repetides al mateix preu.
* **Gestió de Comissions:** Ajusta automàticament les ordres de venda si el saldo és insuficient degut als *fees* de l'exchange.
* **Base de Dades SQLite:** Emmagatzematge local eficient per no saturar l'API de Binance amb les peticions de la web.

---

## 🛠️ Instal·lació

### 1. Requisits
* Python 3.10 o superior.
* Un compte a Binance (es recomana usar la **Testnet** per proves).

### 2. Clonar i Preparar
```bash
# Clonar el repositori
git clone https://github.com/catlinux/gridbot_binance.git
cd gridbot_binance

# Crear entorn virtual
python3 -m venv venv
source venv/bin/activate  # A Linux/Mac
# venv\Scripts\activate  # A Windows

# Instal·lar dependències
pip install -r requirements.txt
```

### 3. Configuració
Crea l'arxiu de credencials basat en l'exemple:

```bash
cp config/.env.example config/.env
```

Edita `config/.env` i afegeix les teves claus API:
```dotenv
BINANCE_API_KEY=la_teva_api_key
BINANCE_SECRET_KEY=el_teu_secret_key
USE_TESTNET=True  # Canvia a False per diners reals
```

### 4. Definir Estratègia
Edita `config/config.json5` per definir quines monedes operar i com:

```javascript
"pairs": [
  { 
    "symbol": "BTC/USDC", 
    "enabled": true,
    "strategy": {
      "grids_quantity": 20,   // Nombre de línies
      "amount_per_grid": 150, // Inversió per línia
      "grid_spread": 0.6      // % Distància entre línies
    }
  }
]
```

---

## ▶️ Ús

### Iniciar el Bot
Això arrencarà el motor de trading i el servidor web simultàniament.

```bash
python main.py
```

Obre el navegador a: **[http://localhost:8000](http://localhost:8000)**

### Eines d'Utilitat
Si necessites reiniciar de zero o netejar ordres "zombis" de la Testnet:

```bash
# Cancel·la totes les ordres i mostra un resum del saldo
python neteja.py

# VENDRE TOT A MERCAT (Pas a USDC d'emergència)
python vendre_tot.py
```

---

## 📊 Guia d'Estratègia (Spread)

El paràmetre `grid_spread` defineix l'agressivitat del bot:

| Spread (%) | Tipus | Recomanat per a... |
| :--- | :--- | :--- |
| **0.1% - 0.3%** | Scalping Agressiu | Stablecoins o mercats molt laterals. (Atenció als fees!) |
| **0.5% - 0.8%** | Estàndard | BTC, ETH. Equilibri entre risc i benefici. |
| **1.0% - 2.0%** | Swing / Volatilitat | Altcoins (SOL, BNB). Captura moviments més amplis. |
| **> 2.5%** | Seguretat | "Memecoins" o mercats extremadament volàtils (DOGE, PEPE). |

---

## 📂 Estructura del Projecte

```text
gridbot_binance/
├── config/             # Configuració i claus (.env, config.json5)
├── core/               # Lògica del nucli
│   ├── bot.py          # Cervell principal (Grid Logic)
│   ├── exchange.py     # Connector CCXT amb Binance
│   └── database.py     # Gestió SQLite
├── utils/              # Eines (Logger colors)
├── web/                # Servidor Web (FastAPI)
│   ├── server.py       # API Backend
│   └── templates/      # Frontend HTML/JS
├── main.py             # Punt d'entrada
└── neteja.py           # Script d'utilitat
```

---

## ⚠️ Disclaimer

Aquest programari és per a fins educatius i experimentals. El trading de criptomonedes implica un alt risc financer.
* **Utilitza sempre la Testnet** abans de posar diners reals.
* L'autor no es fa responsable de les pèrdues financeres derivades de l'ús d'aquest bot.
* Assegura't d'entendre com funciona el `Grid Trading` abans d'operar.

---
Desenvolupat amb ❤️ i Python.