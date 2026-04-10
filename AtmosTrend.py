import numpy as np
from collections import deque
from scipy.signal import savgol_filter
from scipy.stats import zscore

class AtmosTrend:
    """
    Advanced Statistical Trend Engine
    Exposes full deterministic logic for UI review.
    """

    def __init__(self, buffer_size=120):
        self.pm25_buffer = deque(maxlen=buffer_size)
        self.temp_buffer = deque(maxlen=buffer_size)
        self.hum_buffer = deque(maxlen=buffer_size)
        self.gas_buffer = deque(maxlen=buffer_size)
        
        self.gas_ema = None
        self.gas_alpha = 0.15

        self.state = "NORMAL"
        self.hysteresis_counter = 0

        self.z_threshold = 2.0
        self.roc_threshold = 0.12
        self.volatility_threshold = 15.0
        self.hysteresis_limit = 3

    def update(self, temperature, humidity, pm25, pm10, gas_resistance):
        if temperature is not None: self.temp_buffer.append(float(temperature))
        if humidity is not None: self.hum_buffer.append(float(humidity))
        if gas_resistance is not None: self.gas_buffer.append(float(gas_resistance))
        if pm25 is not None: self.pm25_buffer.append(float(pm25))

        if gas_resistance is not None:
            if self.gas_ema is None: self.gas_ema = float(gas_resistance)
            else: self.gas_ema = (self.gas_alpha * float(gas_resistance) + (1 - self.gas_alpha) * self.gas_ema)

    def _gas_details(self):
        if len(self.gas_buffer) < 10:
            return {"level": "Calibrating", "current": 0, "baseline": 0, "deviation": 0, "stability": "Unknown", "sudden": False}
        
        curr = self.gas_buffer[-1]
        base = self.gas_ema if self.gas_ema else curr
        dev_pct = ((base - curr) / base) * 100 if base > 0 else 0
        
        if dev_pct > 25: level = "High"
        elif dev_pct > 10: level = "Elevated"
        elif dev_pct > 5: level = "Moderate"
        else: level = "Low"
        
        gas_arr = np.array(self.gas_buffer)
        gas_std = np.std(gas_arr)
        if gas_std > 5000: stability = "Highly Variable"
        elif gas_std > 2000: stability = "Fluctuating"
        else: stability = "Stable"
        
        sudden = False
        if len(gas_arr) >= 5:
            short_dev = abs(gas_arr[-1] - gas_arr[-5]) / gas_arr[-5]
            if short_dev > 0.15: sudden = True
            
        return {
            "level": str(level),
            "current": float(round(curr / 1000, 1)), # Convert to kOhm
            "baseline": float(round(base / 1000, 1)), 
            "deviation": float(round(dev_pct, 1)),
            "stability": str(stability),
            "sudden": bool(sudden)
        }

    def _comfort(self):
        if not self.temp_buffer:
            return {"level": "Nominal", "temp_zone": "Calibrating...", "hum_zone": "Calibrating...", "score": 0, "action": "Wait"}
        
        t = self.temp_buffer[-1]
        h = self.hum_buffer[-1]
        
        if t < 20: t_zone = f"Temp: {t:.1f}°C → Below Comfort (20–26°C)"
        elif t > 26: t_zone = f"Temp: {t:.1f}°C → Above Comfort (20–26°C)"
        else: t_zone = f"Temp: {t:.1f}°C → Optimal Zone"
        
        if h < 35: h_zone = f"Humidity: {h:.0f}% → Dry Zone (35–60%)"
        elif h > 60: h_zone = f"Humidity: {h:.0f}% → High Humidity Zone"
        else: h_zone = f"Humidity: {h:.0f}% → Optimal Zone"
        
        # Penalize score based on deviation from perfect 23C / 47.5%
        t_penalty = max(0, abs(t - 23) - 3) * 5
        h_penalty = max(0, abs(h - 47.5) - 12.5) * 1.5
        score = max(0, min(100, int(100 - t_penalty - h_penalty)))
        
        if score >= 90: level = "Comfortable"; action = "Maintain current condition"
        elif score >= 70: level = "Slightly Uncomfortable"; action = "Minor ventilation suggested"
        else:
            if t > 26 and h > 60: level = "Uncomfortable"; action = "Reduce humidity & cool"
            elif t > 26: level = "Hot"; action = "Increase ventilation/cooling"
            elif t < 20: level = "Cold"; action = "Heating recommended"
            else: level = "Uncomfortable"; action = "Adjust humidity"
            
        return {"level": str(level), "temp_zone": str(t_zone), "hum_zone": str(h_zone), "score": int(score), "action": str(action)}

    def _analyze_signal(self):
        data = np.array(self.pm25_buffer)
        try: smooth = savgol_filter(data, 11, 3)
        except: smooth = data 
        z_scores = zscore(smooth) if np.std(smooth) > 0 else np.zeros(len(smooth))
        
        roc = 0.0
        if len(smooth) > 5: roc = float((smooth[-1] - smooth[-5]))

        return {
            "latest_z": float(z_scores[-1]),
            "roc": float(roc),
            "volatility": float(np.std(smooth)),
            "smooth_array": [float(x) for x in smooth]
        }

    def analyze(self):
        comfort_data = self._comfort()
        gas_data = self._gas_details()

        if len(self.pm25_buffer) < 15:
            return {
                "trend_direction": "Stable", "fsm_state": "NORMAL", "roc": 0.0,
                "vol_level": "Low", "anomaly": "No anomaly", "comfort": comfort_data, "gases": gas_data,
                "raw_pm": [], "smooth_pm": []
            }

        stats = self._analyze_signal()
        
        # Anomaly logic
        anomaly = "No anomaly"
        if stats["latest_z"] > self.z_threshold: anomaly = "Sudden spike detected"
        elif stats["latest_z"] < -self.z_threshold: anomaly = "Sudden drop detected"

        # Volatility logic
        if stats["volatility"] > 10: vol_level = "High (unstable air)"
        elif stats["volatility"] > 4: vol_level = "Moderate"
        else: vol_level = "Low (steady environment)"

        # ROC / Direction
        direction = "Stable →"
        if stats["roc"] > 2.0: direction = "Worsening ↓"
        elif stats["roc"] < -2.0: direction = "Improving ↑"

        # FSM (Simplified for state tracking)
        trigger = (abs(stats["latest_z"]) > self.z_threshold) or (abs(stats["roc"]) > 5.0)
        if trigger: self.hysteresis_counter += 1
        else: self.hysteresis_counter = max(0, self.hysteresis_counter - 1)

        if self.hysteresis_counter >= self.hysteresis_limit:
            if self.state == "NORMAL": self.state = "WATCH"
            elif self.state == "WATCH": self.state = "WARNING"
            elif self.state == "WARNING": self.state = "CRITICAL"
            self.hysteresis_counter = 0
        elif self.hysteresis_counter == 0 and not trigger:
            if self.state == "CRITICAL": self.state = "WARNING"
            elif self.state == "WARNING": self.state = "WATCH"
            elif self.state == "WATCH": self.state = "NORMAL"

        return {
            "trend_direction": str(direction),
            "fsm_state": str(self.state),
            "roc": float(round(stats["roc"], 2)),
            "vol_level": str(vol_level),
            "anomaly": str(anomaly),
            "raw_pm": list(self.pm25_buffer)[-20:], # Last 20 points for UI sparkline
            "smooth_pm": stats["smooth_array"][-20:],
            "comfort": comfort_data,
            "gases": gas_data
        }
