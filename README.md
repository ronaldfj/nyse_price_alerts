# 📈 Market Sentinel Bot

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg)

Sistema automatizado de vigilancia de mercados financieros que utiliza **Análisis Técnico Institucional** para identificar señales de alta probabilidad. El bot opera 100% en la nube mediante GitHub Actions y envía alertas en tiempo real vía Telegram.

## 🧠 Estrategia de Trading
El bot no busca movimientos al azar; filtra activos basándose en una confluencia de indicadores:

* **Tendencia Institucional:** Precio superior a la EMA 200 (Filtro de sesgo alcista).
* **Fuerza de Tendencia:** ADX > 20 para confirmar que existe momentum real.
* **Momento de Entrada:** RSI optimizado (45-65) con pendiente ascendente.
* **Gestión de Riesgo:** Solo se emiten alertas con un Ratio Riesgo:Beneficio (R:R) mínimo de 2.0.

## 🚀 Características Técnicas
* **Ejecución Serverless:** Programado con GitHub Actions (Cron).
* **Anti-Blocking:** Implementa User-Agents y retardos inteligentes para asegurar la disponibilidad de datos.
* **Persistence:** Gestión de estado vía JSON para evitar spam de alertas duplicadas.

## 🛠️ Configuración e Instalación

### 1. Requisitos Previos
* Python 3.9 o superior.
* Un Bot de Telegram (creado vía @BotFather).

### 2. Variables de Entorno (GitHub Secrets)
Para proteger la seguridad del sistema, no se utilizan archivos de configuración locales para credenciales. Debes configurar los siguientes **Secrets** en tu repositorio de GitHub:

| Secreto | Descripción |
| :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | El Token API de tu bot de Telegram. |
| `TELEGRAM_CHAT_ID` | El ID numérico del chat o grupo de destino. |

### 3. Instalación Local (para pruebas)
```bash
git clone [https://github.com/TU_USUARIO/TU_REPOSITORIO.git](https://github.com/TU_USUARIO/TU_REPOSITORIO.git)
cd TU_REPOSITORIO
pip install -r requirements.txt
python alert.py
