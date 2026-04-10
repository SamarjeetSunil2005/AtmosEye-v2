# 🌩️ AtmosEye v2
**Deterministic Environmental Intelligence & IAQ Dashboard**

AtmosEye is an advanced, edge-computed environmental monitoring system. Instead of relying on "black box" machine learning or cloud processing, it uses transparent, deterministic statistical mathematics to actively monitor, analyze, and report on indoor air quality and comfort.

## ✨ Core Features
* **AtmosTrend Engine:** Uses Savitzky-Golay filtering to clean noisy PM2.5/VOC data and calculates Z-Scores/Rates of Change to detect anomalies.
* **Alert Debouncing:** A Finite State Machine (FSM) with hysteresis prevents alert fatigue and state-flapping.
* **Compound Risk Engine:** Intersects environmental variables (e.g., heat + poor air) to generate dynamic, synergistic health warnings.
* **Tone-Aware Insights:** Generates actionable, human-readable text summaries in Scientific, Professional, or Friendly formats.
* **Edge-Native:** Runs entirely offline on a Raspberry Pi, with Cloudflare Tunneling and a Telegram Bot for secure remote access.

## 🛠️ Hardware Requirements
* Raspberry Pi (3B, 4, or Zero 2W)
* PMS5003 Particulate Matter Sensor (Serial)
* BME680 / BME688 Environmental Sensor (I2C)

## 🚀 Quick Start
1. Clone the repository: `git clone https://github.com/YOUR-USERNAME/AtmosEye-v2.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the engine: `python3 engine.py`
4. Access the dashboard at `http://localhost:8080`

## 📄 Documentation
For a full breakdown of the mathematical models and categorization logic (including CPCB and US EPA standards), please refer to the `AtmosEye_Documentation.pdf` included in this repository.

## 📝 License
This project is licensed under the MIT License.
