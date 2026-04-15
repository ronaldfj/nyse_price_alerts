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


🤝 Contribuciones
¡Las contribuciones son bienvenidas! Si tienes una idea para mejorar los indicadores o la eficiencia del bot:

Haz un Fork del proyecto.

Crea una rama para tu mejora (git checkout -b feature/MejoraTecnica).

Realiza tus cambios y haz un Commit descriptivo.

Envía un Pull Request.

Nota: Por favor, asegúrate de que tus cambios no expongan datos sensibles y mantengan la compatibilidad con el sistema de retardos (delays) para evitar bloqueos de IP.

⚖️ Licencia
Distribuido bajo la Licencia MIT. Ver LICENSE para más información.


---

### Recomendaciones adicionales para tu repo:

1.  **Archivo `requirements.txt`:** Crea este archivo en la raíz y pega esto:
    ```text
    pandas
    yfinance
    requests
    ```
2.  **Archivo `.gitignore`:** Es vital para tu seguridad y orden. Pega esto:
    ```text
    __pycache__/
    *.json
    .env
    .DS_Store
    ```
    *Esto evitará que se suba el archivo `stock_state.json` o `crypto_state.json`, manteniendo tus logs de alertas privados.*

3.  **Diferenciación:** En el README de **Cripto**, puedes mencionar que el cron corre cada 4 horas, mientras que en el de **Bolsa** puedes destacar que solo opera en días hábiles de mercado.

¿Te gustaría que añadamos alguna sección específica sobre el análisis de **ADX 100** que vimos en tus capturas?
