# 🌩️ AtmosEye v2.0

**Deterministic Edge-Computed Environmental Intelligence Dashboard**

License: MIT  
Python  
Platform

AtmosEye is an advanced, privacy-first indoor air quality (IAQ) and environmental monitoring system. Unlike commercial "black-box" monitors that rely on proprietary cloud machine learning, AtmosEye utilizes **transparent, deterministic statistical mathematics** processed entirely on the edge.

By applying Savitzky-Golay filtering, Z-Score anomaly detection, and a Finite State Machine (FSM), AtmosEye eliminates noisy sensor data and "alert fatigue," providing actionable, tone-aware health insights based on physiological risk profiles.

---

## ✨ Core Engineering Features

- 🧮 **AtmosTrend Analytical Engine:** Applies Savitzky-Golay filtering to high-frequency sensor noise (PM2.5, VOCs) without distorting natural pollution peaks. Calculates 120-frame Z-Scores and Rates of Change (ROC) for mathematical anomaly detection.
- 🛡️ **Alert Debouncing (FSM):** Utilizes a Finite State Machine equipped with a hysteresis counter to prevent state-flapping. Hazardous conditions must remain true for consecutive cycles to trigger escalations.
- 🌡️ **Compound Risk Heuristics:** Intersects independent environmental variables (e.g., extreme heat + high humidity + poor air quality) to identify synergistic physiological threats, shifting safety recommendations dynamically.
- 🧠 **Tone-Aware Insights:** An onboard generative text engine translates mathematical states into human-readable action plans in three configurable vocabularies: Scientific, Professional, or Friendly.
- 🌍 **Zero-Trust Remote Access:** Integrated Cloudflare tunneling and an asynchronous Telegram Bot provide secure, encrypted remote access and alert delivery without opening vulnerable router ports.

---

## 🏗️ System Architecture

1. **Ingestion Layer:** Raw I2C and Serial telemetry buffered into 120-frame rolling arrays.
2. **Statistical Layer:** Real-time calculation of Exponential Moving Averages (EMA) for dynamic VOC baseline drift compensation.
3. **Logic Layer:** Cross-references standardized Indian CPCB and US EPA Air Quality Indices.
4. **Presentation Layer:** A responsive dashboard built with Alpine.js, Tailwind CSS, and D3.js, featuring progressive disclosure of telemetry (3-tier simplified UI vs. deep 6-tier telemetry arrays).

---

## 🛠️ Hardware Requirements

- **Compute:** Raspberry Pi (3B, 4, or Zero 2W) running a Debian-based OS.
- **Particulate Sensor:** Plantower PMS5003 (via UART / `/dev/serial0`).
- **Environmental Sensor:** Bosch BME680 or BME688 (via I2C / `0x76`).

---

## 🚀 Installation & Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/SamarjeetSunil2005/AtmosEye-v2.git
cd AtmosEye-v2
```

### 2. Install Dependencies

Ensure you have Python 3 installed, then install the required pip packages:

```bash
pip install -r requirements.txt
```

*(Dependencies include: Flask, Flask-SocketIO, numpy, scipy, psutil, adafruit-circuitpython-bme680, pyserial, python-telegram-bot)*

### 3. Hardware Configuration

Ensure I2C and Serial are enabled on your Raspberry Pi:

```bash
sudo raspi-config
# Interface Options -> Enable I2C
# Interface Options -> Serial Port -> Login Shell (No) / Hardware Port (Yes)
```

### 4. Run the Engine

Launch the core analytical engine. The system will automatically generate the required configuration files and log directories on first boot.

```bash
python3 engine.py
```

### 5. Access the Dashboard

- **Local Network:** Navigate to `http://<YOUR_PI_IP_ADDRESS>:8080` in any web browser.
- **Remote Access:** Use the dashboard or Telegram bot to activate the secure Cloudflare tunnel.

---

## 📊 Documentation & Mathematical Logic

For a comprehensive breakdown of the formulas, categorization logic, and physiological mapping standards used in this project, please consult the official technical specification:  
📄 [AtmosEye_Documentation.pdf](./AtmosEye_Documentation.pdf)

---

## 👨‍💻 Author

**Samarjeet Sunil**  
*Designed for edge-computing efficiency, user privacy, and strict deterministic reliability.*

## 📝 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
