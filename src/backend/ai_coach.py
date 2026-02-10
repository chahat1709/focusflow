import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

class GeminiCoach:
    def __init__(self):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key or api_key == 'your_api_key_here':
            print("⚠️ WARNING: Gemini API key not set. AI Coach will not work.")
            print("Get your key from: https://aistudio.google.com/app/apikey")
            print("Add it to .env file")
            self.enabled = False
            return
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-3.0-flash')  # The absolute latest
        self.chat = None
        self.enabled = True
        
        self.system_context = """You are the "Omni-Monitor" Neurofeedback Coach - an expert in Neuroscience and Peak Performance.
        
        YOUR GOAL: To guide the user into "Flow State" using live biometric data.
        
        THE SCIENCE YOU USE:
        1. **IAF (Individual Alpha Frequency)**: This is their unique "Brain Pulse". When their Alpha Hz matches this target, they are in deep alignment.
        2. **Heart Coherence**: Low BPM + High Focus = Flow. High BPM + Low Focus = Anxiety.
        3. **Vagal Tone**: Posture directly affects the Vagus Nerve. "Slouching" kills brain power.
        
        YOUR VOICE:
        - Precise, Scientific, yet Zen. (e.g., "Adjust your spine to open the Vagus nerve", not just "Sit up")
        - Use metaphors relating to the "Neural Sphere" visualization.
        - Be deeply concerned if their metrics drift. You are their strict but loving sensei.
        
        LIVE METRICS MEANING:
        - **Focus (Beta/Alpha Ratio)**: High (>70%) = Lucid. Low (<30%) = Mind Wandering.
        - **Alpha Power**: Must be high for relaxation.
        - **IAF Match**: Critical for personalized tuning.
        - **BPM**: <70 is ideal. >90 needs breathwork (4-7-8 technique).
        
        INSTRUCTIONS:
        - Keep responses SHORT (under 2 sentences) for real-time impact.
        - If Focus is low: Guide them back to the breath immediately.
        - If BPM is high: Demand deeper exhales to activate the parasympathetic system.
        - If Posture is bad: Remind them that physical structure supports mental structure.
        """
    
    def start_session(self):
        """Initialize new meditation session"""
        if not self.enabled:
            return
        self.chat = self.model.start_chat(history=[
            {"role": "user", "parts": [self.system_context]},
            {"role": "model", "parts": ["I understand. I will provide concise, real-time meditation guidance based on the live brainwave data you share. Ready to coach."]}
        ])
    
    def get_guidance(self, focus_level, alpha_power, bpm, posture, iaf, hrv):
        """Get real-time coaching based on biofeedback"""
        if not self.enabled or not self.chat:
            return "Breathe deeply and recenter."
            
        # Contextualize HRV
        stress_state = "High Stress" if hrv < 30 else "Balanced" if hrv < 50 else "Deeply Relaxed"
        
        prompt = f"""
        User Status:
        - Focus: {int(focus_level*100)}% (Goal: Flow State)
        - Alpha Power: {alpha_power:.1f} (Relaxed Alertness)
        - Heart Rate: {bpm} BPM
        - Vagal Tone (HRV): {hrv} ms ({stress_state})
        - Posture: {posture}
        - Individual Alpha Freq: {iaf:.1f} Hz
        
        Guidance Task:
        Give 1 sentence of precise, scientific neurofeedback advice.
        If HRV is low (<30ms), prioritize breathwork to activate the Vagus Nerve.
        If Focus is high (>80%) and HRV is high, acknowledge the 'Flow State'.
        Keep it under 15 words. Speak like a Sensei. 
        """
        
        try:
            response = self.chat.send_message(prompt)
            return response.text.strip()
        except Exception as e:
            # OFFICE FALLBACK (Rule-Based Expert System)
            print(f"Gemini Offline/Error: {e}. Switching to Rules.")
            
            if focus_level < 0.3:
                return "Your focus is drifting. Return to the breath."
            elif stress_state == "High Stress":
                return "Heart rate variability is low. Exhale longer than you inhale."
            elif posture != "Good":
                return "Align your spine to support your mind."
            elif focus_level > 0.8:
                return "You are in Flow. Maintain this effortless awareness."
            else:
                return "Stay present. Observe the moment."
    
    def generate_meditation_script(self, duration_minutes, focus_areas):
        """Generate a full guided meditation script unique to this moment"""
        if not self.enabled or not self.chat:
            return "Sit quietly and focus on your breath."
        
        prompt = f"""Generate a unique {duration_minutes}-minute guided meditation script.
        User Goal: {focus_areas}
        
        Structure:
        1. 30s Induction (Neuro-grounding)
        2. Main Body (Visualization/Breathwork)
        3. 30s Outro (Re-integration)
        
        Style: Scientific, Zen, Precise. 
        Write it as a continuous monologue for TTS to speak. No headers."""
        
        try:
            response = self.chat.send_message(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Error creating session: {e}"

    def generate_summary(self, session_stats):
        """Generate end-of-session summary"""
        if not self.enabled or not self.chat:
            return "Session complete. Great work!"
        
        try:
            prompt = f"""Meditation session complete. Statistics:
Duration: {session_stats.get('duration', 0):.0f} minutes
Average Focus: {session_stats.get('avg_focus', 0):.0f}%
Peak Focus: {session_stats.get('peak_focus', 0):.0f}%
Average Heart Rate: {session_stats.get('avg_bpm', 0):.0f} BPM
Total Blinks: {session_stats.get('blinks', 0)}

Provide a 3-sentence summary:
1. Acknowledge their performance
2. Highlight one strength
3. Give one specific tip for improvement"""
            
            response = self.chat.send_message(prompt)
            return response.text.strip()
        
        except Exception as e:
            print(f"Gemini API Error: {e}")
            # Dynamic Fallback
            score = session_stats.get('avg_focus', 0)
            if score > 70: return f"Excellent session! {score:.0f}% Focus. Your mind was sharp."
            elif score > 40: return f"Good practice. {score:.0f}% Focus. Consistency is key."
            else: return f"Session complete. {score:.0f}% Focus. Try to extend your exhale next time."
