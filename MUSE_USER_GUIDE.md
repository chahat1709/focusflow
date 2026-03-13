# FocusFlow & Muse 2: Hardware & Calibration Guide

This manual covers the strict hardware requirements and operational procedures necessary to achieve clinical-grade focus scores using the FocusFlow application and the InteraXon Muse 2 headband.

Because FocusFlow records **raw neurological data** rather than pre-smoothed consumer metrics, the physical environment and the student’s behavior during calibration are critical. **Garbage In = Garbage Out.**

---

## 1. Preparing the Hardware

### The 4 Sensor Points
The Muse 2 headband has 4 primary EEG (brainwave) sensors:
1. **AF7 (Left Forehead)**
2. **AF8 (Right Forehead)**
3. **TP9 (Left Ear, behind the lobe)**
4. **TP10 (Right Ear, behind the lobe)**

### Putting it On Correctly
1. Ensure the student's forehead is clean (free of heavy makeup or thick sweat).
2. Ensure there is no hair trapped beneath the ear sensors (TP9/TP10) or forehead sensors.
3. The headband should sit relatively low on the forehead, just above the eyebrows.
4. **Tighten it.** It should be snug, but not painful. If the headband shifts when the student moves their head, it is too loose. 

### Reading the Dashboard Contact Map
On the FocusFlow Dashboard, watch the **Signal Quality (Contact Map)**. 
- **Green:** Perfect connection (Low impedance).
- **Red / Flashing:** The sensor is "railing" (reading pure noise because it is not touching the skin, or there is heavy muscle tension).
*Do not start a session until all 4 sensors are consistently Green.*

---

## 2. The Critical 15-Second Calibration (The "Zero Point")

**This is the most important step in the entire application.**

Every student has a different biological skull thickness and resting brainwave pattern. The application cannot score a student until it learns what their specific "Resting State" looks like. When you click **Start Session**, the system will force a 15-second calibration window. 

### The Law of Calibration
The system assumes that whatever happens in these 15 seconds is the student's **absolute biological minimum resting state** (their "Zero Point"). 

**If the student corrupts this 15-second window, their entire session score will be mathematically distorted.**

*   **SCENARIO A (Perfect):** The student sits completely still, stares blankly at the wall, and relaxes their body. The baseline is set correctly. When they begin their actual homework, the system easily detects the spike in Beta waves. They score a 90%.
*   **SCENARIO B (Garbage In):** During the 15-second calibration, the student is laughing, talking to the teacher, looking around the room, or actively trying to solve a math problem. The system records this high state of arousal and maps *that* as their new "Zero Point". For the rest of the 30-minute session, the student can never beat their own corrupted baseline. They will score a 0%.

### Administrator Instructions During Calibration:
1. Instruct the student: *"Sit comfortably, place your hands in your lap, and look at the blank wall or turn off your screen."*
2. Instruct the student: *"Relax your jaw. Do not speak. Take a deep breath."*
3. Click **Start Session**.
4. Demand absolute silence for 15 seconds until the calibration UI clears.
5. Only *after* calibration is complete should the student begin their task (reading, math, testing).

---

## 3. Avoiding Artifacts (Noise)

Brainwaves are measured in microvolts (µV) — they are incredibly tiny signals. Muscle movements generate electrical signals that are **100x to 1000x louder** than brainwaves. This is called EMG Noise.

While FocusFlow has built-in digital signal processing (DSP) to filter out standard noise, violent movements will overwhelm the mathematical filters.

### A. The "Jaw Clench" Problem
*   **What happens:** When a student is frustrated or stressed, they often clench their jaw or grind their teeth.
*   **The resulting error:** The jaw muscles trigger massive high-frequency electrical spikes that bleed directly into the temporal (ear) and frontal sensors. Jaw clenching operates at the exact same frequency as "Deep Focus" (Beta and Gamma waves). If a student clenches their jaw for 5 minutes, the system might mistakenly think they are 95% focused, when in reality they are just stressed.
*   **The Fix:** Remind students to keep their teeth slightly parted and their tongue relaxed. 

### B. Excessive Blinking and Eye Darting
*   **What happens:** Blinking creates a massive voltage cliff on the frontal sensors (AF7/AF8). 
*   **The resulting error:** FocusFlow has a built-in algorithm that detects blinks and deletes that 1-second chunk of corrupted data. However, if a student is vigorously darting their eyes side-to-side (saccades) without blinking, or fluttering their eyelids rapidly, the artifact rejection algorithm may not catch it, muddying the data.
*   **The Fix:** The student should maintain relatively steady visual focus on their screen or paper. 

### C. Physical Fidgeting
*   **What happens:** Bouncing legs, tapping pencils, or shifting in the chair.
*   **The resulting error:** The movement subtly shifts the skin under the sensors, changing the electrical resistance (impedance) and injecting low-frequency noise.
*   **The Fix:** Students should sit with both feet flat on the floor in a supportive chair.

---

## 4. Summary Checklist for Admins
- [ ] Dampen the forehead and behind the ears slightly if the skin is extremely dry.
- [ ] Ensure the headband is tight and all 4 sensors show Green.
- [ ] Force the student to sit absolutely still and silent, doing nothing, for the 15-second calibration.
- [ ] Ensure the student is not resting their chin on their hand (pushes the ear sensors).
- [ ] Monitor for jaw clenching if scores suddenly spike to 95% without dropping.
