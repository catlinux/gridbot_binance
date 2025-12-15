# 🚀 GridBot Binance: Automatización Profesional de Trading

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Moderno-green.svg)
![SQLite](https://img.shields.io/badge/SQLite-Persistent-blue.svg)
![Binance](https://img.shields.io/badge/Binance-Spot-yellow.svg)

Bienvenido a tu centro de mando. Este software no es un simple bot; es una **suite completa de gestión de activos** diseñada para aprovechar la volatilidad del mercado cripto las 24 horas del día. A diferencia de operar manualmente o usar herramientas básicas, este bot aplica lógica matemática y análisis técnico para optimizar tus entradas y salidas.

---

## 📸 Capturas de Pantalla

| Dashboard General | Configuración Visual |
|:---:|:---:|
| ![Dashboard](docs/screenshots/dashboard_preview.png) | ![Configuración](docs/screenshots/config_preview.png) |
| *Vista global de PnL y Gráficos* | *Edición de estrategias sin tocar código* |

---

## 📑 Índice de Contenidos

1.  [¿Por qué necesitas un Bot? (Comparativas)](#-por-qué-necesitas-un-bot-comparativas)
2.  [Características Principales](#-características-principales)
3.  [Estructura del Proyecto](#-estructura-del-proyecto)
4.  [Instalación y Puesta en Marcha](#-instalación-y-puesta-en-marcha)
5.  [Configuración de Telegram](#-configuración-de-telegram)
6.  [Guía de Uso](#-guía-de-uso)
7.  [Ayuda al Proyecto y Soporte](#-ayuda-al-proyecto-y-soporte)
8.  [Aviso Legal](#-aviso-legal-disclaimer)

---

## 🌟 ¿Por qué necesitas un Bot? (Comparativas)

El mercado cripto nunca duerme. Aquí verás por qué esta herramienta es superior tanto al trading manual como a los bots genéricos de los exchanges.

### 1. Bot vs. Trading Manual
Operar "a mano" es agotador e ineficiente para estrategias de rango (Grid).

| Característica | 👤 Operativa Manual | 🤖 GridBot Automatizado |
| :--- | :--- | :--- |
| **Horario** | Necesitas dormir, comer y trabajar. | **24/7 Non-Stop**. Aprovecha cada movimiento de madrugada. |
| **Psicología** | El miedo y la avaricia provocan errores. | **Sin Emociones**. Ejecuta el plan matemático fríamente. |
| **Velocidad** | Tardas segundos en calcular y poner órdenes. | **Milisegundos**. Reacciona al instante a las mechas del mercado. |
| **Gestión** | Mover 20 líneas de compra/venta es un caos. | Ajusta **cientos de órdenes** automáticamente. |
| **Oportunidad** | Pierdes las pequeñas oscilaciones (ruido). | Hace **Scalping** constante, sumando pequeñas ganancias que crean grandes beneficios. |

### 2. Este Bot vs. Bot Nativo de Binance
Binance ofrece un bot gratuito, pero es muy limitado para usuarios avanzados que buscan control total.

| Característica | 🤖 Bot Nativo de Binance | ⚡ GridBot Personalizado (Este Proyecto) |
| :--- | :--- | :--- |
| **Entrada al Mercado** | Entra "a mercado" inmediatamente. Si el precio cae al iniciar, quedas atrapado (*bagholder*). | **Entrada Inteligente (RSI)**. Espera pacientemente a que el indicador marque sobreventa para iniciar en el mejor punto. |
| **Control de Sesión** | Mezcla el PnL histórico con el actual. | **PnL de Sesión Real**. Puedes reiniciar el contador para medir el rendimiento de una sesión específica sin borrar el histórico. |
| **Emergencias** | Cancelar es lento y manual. | **Botón de Pánico**. Detén el motor, cancela todo o vende todo a mercado con un solo clic. |
| **Notificaciones** | Avisos genéricos de la App. | **Telegram en Tiempo Real**. Recibe cada compra, venta y beneficio detallado en tu reloj o móvil. |
| **Visualización** | Gráfico estándar. | **Dashboard Profesional**. Gráficos interactivos con tus órdenes pintadas, temas visuales y control de cartera. |

---

## 🛠️ Características Principales

* **Estrategia Grid con Trailing Up:** Compra progresivamente en las bajadas y vende en las subidas. Si el precio se dispara (*pump*), el bot persigue la subida para maximizar el beneficio.
* **Motor de Análisis RSI:** Configura perfiles de riesgo (**Conservador, Moderado, Agresivo**) para que el bot solo active nuevas operaciones cuando el mercado esté en condiciones óptimas (ej: RSI < 30).
* **Dashboard Web Completo:**
    * **Temas:** Soporte para **Modo Claro**, **Modo Oscuro** y **Layout con Barra Lateral**.
    * **Gráficos:** Tecnología *Lightweight Charts* y *ECharts* para visualizar velas, líneas de tendencia y distribución de cartera.
    * **Control Total:** Arranca, pausa o detén el motor desde la web.
* **Seguridad:** Gestión de claves API mediante variables de entorno (`.env`) y sistema de logs detallados.

![Ejemplo de Gráfico con Órdenes](web/static/img/chart_example.png)
*(Añade aquí una imagen del gráfico con las líneas de compra/venta)*

---

## 📂 Estructura del Proyecto

El sistema es modular para facilitar su mantenimiento y escalabilidad:

```text
gridbot_binance/
├── config/
│   ├── config.json5                        # Configuración editable (Estrategias y Pares)
│   ├── env.example                         # Archivo de muestra del .env
│   └── .env                                # Claves API y Secretos (NO subir a Git)
├── core/
│   ├── __init__.py
│   ├── bot.py                              # Lógica del Grid, Smart Reload y Cierre Manual
│   ├── database.py                         # Gestión SQLite (Histórico, Sesión y Persistencia)
│   └── exchange.py                         # Conector Binance (CCXT) y gestión de órdenes
├── data/
│   ├── bot_data.db                         # Base de datos principal (SQLite)
│   ├── bot_data.db-shm                     # Índice de memoria compartida (temporal)
│   └── bot_data.db-wal                     # Registro de escritura anticipada (temporal)
├── utils/
│   ├── __init__.py
│   ├── logger.py                           # Sistema de logs y colores
│   └── telegram.py                         # Sistema de alertas a Telegram
├── web/
│   ├── static/                             # Archivos estáticos (Frontend optimizado)
│   │   ├── css/
│   │   │   ├── themes/                     
│   │   │   │   ├── dark.css                # Tema Oscuro (Próximamente)              
│   │   │   │   ├── light.css               # Tema claro
│   │   │   │   └── sidebar-dark.css        # Tema oscuro con barra lateral (Próximamente)
│   │   │   └── style.css                   # Estilos genéricos de todos los temas
│   │   └── js/
│   │       ├── charts.js                   # Toda la lógica de gráficos
│   │       ├── config.js                   # Lógica del formulario de configuración y estrategias RSI
│   │       ├── dashboard.js                # (Principal): Lógica central, API, estado global e inicialización
│   │       └── utils.js                    # Formateadores de texto, números y colores
│   ├── templates/
│   │   └── index.html                      # Estructura HTML base
│   └── server.py                           # API Backend (FastAPI)
├── .gitignore                              # Archivo de seguridad para mantener datos sensibles fuera de GitHub
├── main.py                                 # Punto de entrada (Run)
├── limpieza.py                             # Script de utilidad para cancelar todo
├── estructura.txt                          # Estructura con árbol de archivos
├── README.md                               # Archivo explicativo de las funciones del bot para GitHub
└── requirements.txt                        # Librerías necesarias
```

---

## 💻 Instalación y Puesta en Marcha

### Requisitos
* Python 3.8 o superior.
* Cuenta de Binance.

### Paso 1: Descargar y Entorno Virtual
Abre tu terminal:

```bash
# Entra en la carpeta del proyecto
cd gridbot_binance

# Crear entorno virtual (Recomendado para no mezclar librerías)
python -m venv venv

# Activar entorno
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
```

### Paso 2: Instalar Dependencias
```bash
pip install -r requirements.txt
```

### Paso 3: Configuración (.env)
El proyecto incluye una plantilla en la carpeta `config/`.

1.  Ve a la carpeta `config/`.
2.  Copia el archivo `env.example` y renómbralo a `.env`.
3.  Edita el archivo `.env` y añade tus claves. El archivo debe quedar así:

```env
# Archivo: config/.env

BINANCE_API_KEY=tu_api_key_de_binance
BINANCE_SECRET_KEY=tu_secret_key_de_binance
USE_TESTNET=False  # Pon True si quieres practicar con dinero ficticio

# Configuración de Telegram (Ver sección siguiente)
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
```

### Paso 4: Ejecutar
Vuelve a la raíz del proyecto y ejecuta:
```bash
python main.py
```
Abre tu navegador en: **http://localhost:8000**

---

## 🤖 Configuración de Telegram

Para que el bot te avise al móvil, necesitas crear tu propio bot de avisos. Es gratis y muy rápido:

![Ejemplo de Alertas en Telegram](web/static/img/telegram_alert.png)
*(Añade aquí una captura del bot de Telegram enviando una alerta)*

1.  **Crear el Bot:**
    * Abre Telegram y busca al usuario **@BotFather**.
    * Envía el comando `/newbot`.
    * Ponle un nombre y un usuario. BotFather te dará un **Token**.
    * Copia ese Token en tu archivo `config/.env` donde dice `TELEGRAM_TOKEN`.

2.  **Obtener tu ID:**
    * Busca en Telegram al usuario **@userinfobot**.
    * Dale a "Iniciar". Te responderá con un número (tu ID).
    * Copia ese número en tu archivo `config/.env` donde dice `TELEGRAM_CHAT_ID`.

3.  **Activar:**
    * Busca tu nuevo bot en Telegram y dale a "Iniciar" para abrir el chat.

---

## 🎮 Guía de Uso

![Pantalla de Configuración](web/static/img/config_screen.png)
*(Añade aquí una captura de la pestaña de configuración)*

1.  **Configuración (Pestaña ⚙️):**
    * Selecciona las monedas que quieres operar (ej: `SOL/USDC`).
    * Define la **Inversión por línea** y el **Spread** (separación entre compras).
    * Elige el perfil RSI (Recomendado: Moderado).
    * Activa el interruptor "ON" y guarda.

2.  **Monitorización (Dashboard 🏠):**
    * Verás el estado del bot. Si el mercado cumple las condiciones RSI, el bot empezará a lanzar órdenes.
    * Puedes usar el selector de temas (arriba a la derecha) para cambiar entre modo Claro, Oscuro o Barra Lateral.

3.  **Seguridad:**
    * Aunque el bot gestiona el riesgo dividiendo el capital, **utiliza siempre Stop Loss** manual en Binance si el mercado es muy volátil, o vigila la operación.

---

## ❤️ Ayuda al Proyecto y Soporte

Este proyecto es Open Source y requiere muchas horas de desarrollo y mantenimiento. Si la herramienta te ha sido útil, te ha ayudado a aprender o te ha generado beneficios, considera hacer una pequeña donación. ¡Ayuda a mantener el código actualizado y a añadir nuevas funcionalidades!

Puedes enviar tu apoyo a las siguientes direcciones (Redes baratas y rápidas):

* **Polygon (MATIC):** `0x5dD9a7b2D831A319a68214C11015f64Dbc6bb79c`
* **Solana (SOL):** `GbAFM55PyBb2otqUb1oTTtqzE39fwE6XS7HVsCCwX5Tw`

**NOTA:** No se requiere TAG ni MEMO para estas direcciones. Si tu exchange te obliga a poner uno para realizar el envío, simplemente escribe 0.
(Asegúrate de seleccionar la red correcta).

¡Muchas gracias por tu colaboración!

---

## ⚠️ Aviso Legal (Disclaimer)

Este software es una herramienta de automatización experimental desarrollada con fines exclusivamente educativos. El trading de criptomonedas conlleva un riesgo significativo de pérdida de capital.

El autor no se hace responsable de posibles pérdidas financieras, errores de ejecución, lucro cesante o problemas derivados del uso o configuración de este software.

**Recomendación:** Prueba siempre la estrategia en la **Testnet de Binance** durante varios días antes de operar con capital real. Úsalo bajo tu propia responsabilidad.
