# ⚡ GridBot Pro - Binance Automated Trading

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-green.svg)
![SQLite](https://img.shields.io/badge/SQLite-Integrated-blue.svg)
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
* **Formulari de Configuració:** Modifica paràmetres (inversió, spread, rangs) directament des del navegador sense tocar fitxers de codi.
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

## 🛠️ Instal·lació Ràpida

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
# Edita l'arxiu amb el teu editor preferit (nano, vim, code...)
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

## ▶️ Ús i Control

### Iniciar el Sistema
Aquesta comanda arrenca el motor de trading, el col·lector de dades i el servidor web.

```bash
python main.py
```

### Accés al Dashboard
Obre el navegador i ves a:
👉 **[http://localhost:8000](http://localhost:8000)**

### Eines d'Utilitat
Si necessites reiniciar de zero o netejar ordres "zombis" de la Testnet:

* **Neteja d'Ordres:** Cancel·la totes les ordres obertes i mostra un balanç del saldo total.
  ```bash
  python neteja.py
  ```
* **Liquidació Total:** Ven totes les criptomonedes a mercat per passar a USDC (Pànic/Reset).
  ```bash
  python vendre_tot.py
  ```

---

## 📊 Guia d'Estratègia (Spread)

El paràmetre `grid_spread` defineix la distància entre línies. Configura-ho segons la volatilitat de la moneda:

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
├── config/             # Configuració (.env, config.json5)
├── core/               # Nucli del sistema
│   ├── bot.py          # Lògica Grid Estàtic i Smart Reload
│   ├── exchange.py     # Connector CCXT
│   └── database.py     # Gestió SQLite i Persistència
├── web/                # Interfície d'Usuari
│   ├── server.py       # API Backend (FastAPI)
│   └── templates/      # Frontend (Bootstrap + ECharts + JS)
├── main.py             # Punt d'entrada (Multiprocess)
└── neteja.py           # Script d'utilitat
```

---

## ⚠️ Avís Legal (Disclaimer)

Aquest programari és una eina d'automatització. El trading de criptomonedes comporta un risc significatiu de pèrdua de capital.
* L'autor no es fa responsable de pèrdues financeres derivades de l'ús, configuració o errors del programari.
* **Recomanació:** Prova sempre l'estratègia a la **Testnet** durant dies abans d'operar amb capital real.

---
Desenvolupat amb ❤️ i Python.
