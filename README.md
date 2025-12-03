# ⚡ GridBot Pro - Binance Automated Trading

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Moderno-green.svg)
![SQLite](https://img.shields.io/badge/SQLite-Persistent-blue.svg)
![Binance](https://img.shields.io/badge/Binance-Spot-yellow.svg)

Un bot de trading automático de alta frecuencia basado en la estrategia **Grid Trading Estático**. Diseñado para **Binance** (Spot), con panel de control web profesional, gestión manual de emergencia y persistencia de datos.

---

## 🚀 Características Principales

### 🧠 Núcleo y Estrategia
* **Grid Estático Multi-Par:** Opera simultáneamente con múltiples monedas (BTC, ETH, SOL...) con configuraciones independientes.
* **Persistencia SQLite:** Todas las operaciones se guardan en base de datos local. Nada se pierde si se reinicia el bot.
* **Hot Reload 🔄:** Cambia la configuración (`config.json5`) sin detener el bot. El sistema detecta los cambios y recalcula las rejillas al vuelo.
* **Smart Recovery 🛡️:** Si el bot se reinicia, recupera el estado anterior y protege el inventario comprado.

### 🌐 Panel de Control Web (Dashboard)
* **Estadísticas Avanzadas:** Visualización separada de rendimiento de la **Sesión Actual** vs **Histórico Global**.
* **Gestión Manual de Órdenes:** Tabla global de órdenes con cálculo de PnL en tiempo real y botón de **pánico (Vender a USDC)** para cerrar posiciones manualmente.
* **Gráficos Interactivos:** Donuts de distribución de cartera y volumen de operaciones, más gráficos de velas (Candlestick) para cada moneda.
* **Frontend Optimizado:** Código separado (HTML/CSS/JS) para una carga rápida y formato numérico europeo (comas para decimales).
* **Configurador Visual:** Modifica parámetros (inversión, spread, rangos) directamente desde el navegador.

---

## 🛠️ Instalación Rápida

### 1. Requisitos
* Python 3.10 o superior.
* Cuenta en Binance (Testnet recomendado para pruebas).

### 2. Clonar y Preparar
Abre tu terminal y ejecuta:

```bash
# Clonar el repositorio
git clone [https://github.com/tu_usuario/gridbot_binance.git](https://github.com/tu_usuario/gridbot_binance.git)
cd gridbot_binance

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # En Linux/Mac
# venv\Scripts\activate   # En Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configuración
Crea el archivo de credenciales `.env` dentro de la carpeta `config/` basado en el ejemplo (o crea uno nuevo):

```dotenv
BINANCE_API_KEY=tu_api_key_aqui
BINANCE_SECRET_KEY=tu_secret_key_aqui
USE_TESTNET=True  # True para dinero ficticio, False para dinero real
```

Edita `config/config.json5` para definir tu estrategia inicial (pares, inversión, spread).

---

## ▶️ Uso

### Iniciar el Sistema
Ejecuta el comando principal. Esto iniciará el motor de trading y el servidor web.

```bash
python main.py
```

### Acceso al Dashboard
Abre tu navegador y ve a:
👉 **[http://localhost:8000](http://localhost:8000)**

### Herramientas Extra
Si necesitas reiniciar de cero o limpiar órdenes "zombis" de pruebas anteriores:

* **Limpieza de Órdenes:** Cancela todas las órdenes abiertas de golpe y muestra un balance de la cartera.
  ```bash
  python limpieza.py
  ```

---

## 📂 Estructura del Código

```text
gridbot_binance/
├── config/             # Configuración (.env, config.json5)
├── core/               # Lógica del Bot, Base de Datos y Conector Exchange
├── web/                # Servidor Web
│   ├── static/         # Frontend optimizado
│   │   ├── css/        # Estilos
│   │   └── js/         # Lógica visual (Gráficos, API calls)
│   ├── templates/      # HTML (Interfaz)
│   └── server.py       # API Backend (FastAPI)
├── main.py             # Ejecutable principal
├── limpieza.py           # Script de utilidad
└── requirements.txt    # Librerías necesarias
```

---

## ⚠️ Disclaimer (Aviso Legal)

Este software es una herramienta de automatización experimental desarrollada con **fines educativos**. El trading de criptomonedas conlleva un riesgo significativo de pérdida de capital.

* El autor no se hace responsable de posibles pérdidas financieras derivadas del uso, configuración o fallos del software.
* **Recomendación:** Prueba siempre la estrategia en la **Testnet** durante varios días antes de operar con capital real.

---
Desarrollado con ❤️ y Python.