from typing import Dict, Any, Optional

class AtmosInsights:
    def __init__(self, tone: str = "professional", profile: str = "standard"):
        self.tone = tone.lower()
        self.profile = profile.lower() 

    def set_tone(self, tone: str) -> None:
        """Dynamically updates the reporting tone."""
        if tone:
            self.tone = tone.lower()

    def set_profile(self, profile: str) -> None:
        """Dynamically updates the user health profile."""
        if profile:
            self.profile = profile.lower()

    def _calculate_velocity(self, current_aqi: int, past_aqi: Optional[int]) -> str:
        """Calculates the rate of change to predict near-future states."""
        if past_aqi is None: return "holding steady"
        
        delta = current_aqi - past_aqi
        if delta > 30:
            return "degrading rapidly"
        elif delta > 10:
            return "slowly worsening"
        elif delta < -20:
            return "improving rapidly"
        return "holding steady"

    def _get_aqi_category(self, aqi: int) -> str:
        """Maps an AQI value to its standard category."""
        if aqi <= 50: return "Good"
        elif aqi <= 100: return "Moderate"
        elif aqi <= 150: return "Unhealthy for Sensitive Groups"
        elif aqi <= 200: return "Unhealthy"
        elif aqi <= 300: return "Very Unhealthy"
        return "Hazardous"

    def _generate_scientific_summary(self, data: Dict[str, Any], past_aqi: Optional[int]) -> str:
        """Generates a highly technical, objective summary."""
        delta = data['aqi'] - (past_aqi if past_aqi is not None else data['aqi'])
        
        compound_warning = (
            "The intersection of elevated thermal metrics and atmospheric moisture creates a high-enthalpy "
            "environment. This synergistic amplification significantly increases physiological strain and "
            "particulate deposition rates in the respiratory tract. " 
            if data['compound_risk'] else 
            "Meteorological variables remain within nominal limits, presenting no synergistic "
            "amplification of current particulate toxicity. "
        )

        time_phrase = "over the preceding hour" if data.get('has_past') else "since system initialization"

        return (
            f"Atmospheric telemetry indicates a current Air Quality Index (AQI) of {data['aqi']} "
            f"({data['category']}). Temporal analysis {time_phrase} yields a ΔAQI of {delta}, "
            f"denoting a {data['velocity']} environmental baseline. Ambient meteorological parameters "
            f"are recorded at {data['temp']}°C and {data['humidity']}% relative humidity.\n\n"
            f"{compound_warning}"
            f"Evaluating under the '{self.profile.capitalize()}' physiological risk stratification. "
            f"Refer to the targeted mitigation protocols below to minimize exposure vectors."
        )

    def _generate_professional_summary(self, data: Dict[str, Any]) -> str:
        """Generates a clear, operational summary."""
        compound_warning = (
            "Furthermore, the combination of high heat and humidity is creating a severe physical "
            "stress environment, which multiplies the negative effects of the current air quality. " 
            if data['compound_risk'] else 
            "Temperature and humidity remain within parameters that do not significantly exacerbate air quality impacts. "
        )
        
        time_phrase = "Over the past hour" if data.get('has_past') else "Since system initialization"

        return (
            f"Current environmental telemetry indicates an Air Quality Index (AQI) of {data['aqi']} "
            f"({data['category']}). {time_phrase}, atmospheric conditions have been {data['velocity']}, "
            f"indicating a shifting environmental baseline. Current temperature is {data['temp']}°C with "
            f"a relative humidity of {data['humidity']}%. \n\n"
            f"{compound_warning}"
            f"Based on the active '{self.profile.capitalize()}' health profile, the current conditions "
            f"require careful monitoring. Please review the targeted recommendations below to ensure "
            f"safety and operational continuity."
        )

    def _generate_friendly_summary(self, data: Dict[str, Any]) -> str:
        """Generates a casual, easy-to-read summary."""
        compound_warning = (
            "Right now, it's really hot and humid out there! Combined with the air quality, "
            "it's much harder for your body to cool down and breathe easily. " 
            if data['compound_risk'] else 
            "The weather outside is fairly standard and shouldn't make the air feel any worse than it is. "
        )

        time_phrase = "Compared to an hour ago" if data.get('has_past') else "Since booting up"

        return (
            f"Here is your current environment breakdown! The air quality is currently classified as {data['category']} "
            f"with an AQI score of {data['aqi']}. {time_phrase}, the air is {data['velocity']}. "
            f"It is currently {data['temp']}°C outside with {data['humidity']}% humidity.\n\n"
            f"{compound_warning}"
            f"Since you are using the {self.profile.capitalize()} profile, we've tailored our advice "
            f"specifically for you. Check out the suggestions below to stay safe and comfortable today!"
        )

    def _build_action_plan(self, data: Dict[str, Any]) -> Dict[str, list]:
        """Generates categorized, actionable recommendations based on heuristics."""
        plan = {
            "health_and_activity": [],
            "indoor_environment": [],
            "monitoring_and_prep": []
        }

        # 1. Health & Activity Rules
        if data["compound_risk"]:
            plan["health_and_activity"].append("🚨 Cease all strenuous outdoor physical activity immediately due to severe heat/air compound risk.")
            plan["health_and_activity"].append("Increase hydration significantly; thermal stress multiplies respiratory strain.")
        elif data["aqi"] > 150 or (self.profile == "sensitive" and data["aqi"] > 100):
            plan["health_and_activity"].append("Wear a well-fitted N95 or FFP2 respirator if you must go outside.")
            plan["health_and_activity"].append("Limit outdoor exposure to essential transit only.")
        else:
            plan["health_and_activity"].append("Standard outdoor activities are safe to resume.")

        # 2. Indoor Environment Rules
        if data["aqi"] > 100:
            plan["indoor_environment"].append("Ensure all windows and external doors are tightly sealed.")
            plan["indoor_environment"].append("Activate indoor air purifiers (HEPA) on high settings.")
            
            if data["temp"] > 28:
                plan["indoor_environment"].append("Run air conditioning on 'recirculate' mode to avoid pulling in external air.")
        elif data["aqi"] <= 50 and data["temp"] < 25:
             plan["indoor_environment"].append("Favorable conditions: Open windows to ventilate indoor spaces and reduce CO2 buildup.")
        else:
             plan["indoor_environment"].append("Maintain standard indoor climate control.")

        # 3. Monitoring & Prep Rules
        if data["velocity"] == "degrading rapidly":
            plan["monitoring_and_prep"].append("⚠️ Warning: Conditions are deteriorating fast. Check telemetry again in 30 minutes.")
            plan["monitoring_and_prep"].append("Prepare to initiate lockdown protocols if AQI breaches hazardous thresholds.")
        elif data["velocity"] == "improving rapidly":
            plan["monitoring_and_prep"].append("Conditions are clearing. Standby to lift environmental restrictions within the hour.")
        else:
            plan["monitoring_and_prep"].append("Conditions are stable. Continue standard operational monitoring.")

        # Clean up empty categories 
        return {k: v for k, v in plan.items() if v}

    def generate(self, sensor_data: Dict[str, Any], trend_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main execution method to generate the complete insight payload."""
        
        # 1. Safely extract data from Flask dictionaries with fallbacks
        try:
            current_aqi = int(sensor_data.get("aqi", {}).get("value", 0))
        except (ValueError, TypeError):
            current_aqi = 0
            
        try:
            temp = float(sensor_data.get("temperature", 22.0))
        except (ValueError, TypeError):
            temp = 22.0
            
        try:
            humidity = float(sensor_data.get("humidity", 45.0))
        except (ValueError, TypeError):
            humidity = 45.0
            
        # Extract past AQI if available in trend_data, otherwise default to None
        past_aqi = trend_data.get("past_aqi", None)
        if past_aqi is not None:
            try:
                past_aqi = int(past_aqi)
            except (ValueError, TypeError):
                past_aqi = None
        
        # 2. Compile Data State
        data = {
            "aqi": current_aqi,
            "category": self._get_aqi_category(current_aqi),
            "velocity": self._calculate_velocity(current_aqi, past_aqi),
            "temp": temp,
            "humidity": humidity,
            "compound_risk": temp > 30.0 and humidity > 65.0 and current_aqi > 100,
            "has_past": past_aqi is not None  # Determines which time string to use
        }

        # 3. Generate Narrative Summary
        if self.tone == "scientific":
            summary = self._generate_scientific_summary(data, past_aqi)
        elif self.tone == "friendly":
            summary = self._generate_friendly_summary(data)
        else:
            summary = self._generate_professional_summary(data)

        # 4. Generate Categorized Action Plan
        action_plan = self._build_action_plan(data)

        # --- BACKWARD COMPATIBILITY PATCH ---
        # Flatten the categorized action plan into a single string for older frontends
        flat_recommendations = []
        for category_list in action_plan.values():
            flat_recommendations.extend(category_list)
        legacy_recommendation = " ".join(flat_recommendations)
        # ------------------------------------

        # 5. Return the structured payload for your API/Frontend
        return {
            "meta": {
                "tone_used": self.tone,
                "profile_used": self.profile
            },
            "summary": summary,
            "action_plan": action_plan,               # New format for future updates
            "recommendation": legacy_recommendation,  # Legacy format to fix your UI bug
            "state": data["category"]                 # Legacy state variable
        }
