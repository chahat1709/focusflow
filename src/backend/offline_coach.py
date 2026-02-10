import random

class OfflineCoach:
    def __init__(self):
        self.enabled = True
        print("✅ Offline Neuro-Expert Initialized (Local Mode)")
    
    def start_session(self):
        # No API connection needed
        pass
    
    def get_guidance(self, focus_level, alpha_power, bpm, posture, iaf, hrv):
        """Rule-based expert system for biofeedback"""
        if not self.enabled: return None
        
        # 1. Safety / Signal Check
        if focus_level == 0 and bpm == 0:
            return "Adjust sensor for better signal."
            
        # 2. HRV / Stress Check (Highest Priority)
        if hrv < 30:
            return random.choice([
                "Signal shows stress. Exhale longer than you inhale.",
                "Deepen your breath. Activate the vagus nerve.",
                "Slow down. Let your heart rate drop."
            ])
            
        # 3. Focus Check
        if focus_level < 0.3:
            return random.choice([
                "Mind wandering detected. return to the breath.",
                "Gently bring your attention back.",
                "Focus is drifting. Reset your posture."
            ])
            
        # 4. Flow State Maintenance
        if focus_level > 0.8 and hrv > 50:
            return random.choice([
                "You are in Flow. Maintain this state.",
                "Excellent coherence. Stay here.",
                "Deep focus detected. Effortless awareness."
            ])
            
        # 5. General Guidance
        return random.choice([
            "Relax your jaw and shoulders.",
            "Breathe into your belly.",
            "Observe the silence between thoughts."
        ])

    def generate_summary(self, session_stats):
        """Generate offline report based on stats"""
        score = session_stats.get('avg_focus', 0)
        duration = session_stats.get('duration', 0)
        
        # Intro
        if score > 80:
            intro = "Outstanding session. Your mind was incredibly sharp today."
        elif score > 50:
            intro = "Good practice session. You maintained a steady baseline."
        else:
            intro = "Challenging session, but showing up is what matters."
            
        # Analysis
        analysis = f"You spent {duration:.1f} minutes in practice with an average focus of {score}%."
        
        # Tip
        if session_stats.get('avg_bpm', 0) > 80:
            tip = "Your heart rate was slightly elevated. Try 4-7-8 breathing next time."
        elif score < 50:
            tip = "To improve focus, count your breaths from 1 to 10."
        else:
            tip = "Great consistency. Try increasing your session length tomorrow."
            
        return f"{intro}\n\n{analysis}\n\n💡 Tip: {tip}"
