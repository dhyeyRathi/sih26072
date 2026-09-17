# SIH26072 — Thunderstorm & Lightning Nowcasting Platform

**Smart India Hackathon 2026** · Ministry of Earth Sciences · India Meteorological Department
**Theme:** Disaster Management

---

## What Is This?

Every year, thunderstorms and lightning cause significant damage across India — destroying property, disrupting travel, and most importantly, putting lives at risk. The challenge is that these events develop and move fast. By the time a traditional weather forecast reaches the right people, the storm may have already arrived.

This project is a **storm prediction and warning platform** built specifically for that problem. It doesn't try to predict tomorrow's weather. Instead, it answers a much more urgent question:

> **What is going to happen in the next 10 to 60 minutes — and where?**

The system watches the sky using multiple sources of weather information, combines them using artificial intelligence, and tells forecasters and disaster teams exactly where storms are heading, how dangerous they are, and what's in their path.

---

## The Problem We're Solving

When a thunderstorm is forming or moving, the people who need to act — weather forecasters, district authorities, emergency responders — need answers to very specific questions:

- **Where is the storm right now?**
- **Where is it going?**
- **How fast is it moving?**
- **How strong will it be when it arrives?**
- **Is there a risk of lightning?**
- **Which towns, hospitals, schools, highways, or airports are in danger?**
- **How confident are we in this prediction?**
- **When exactly should we expect it?**

Today, answering all of these questions quickly and accurately requires checking multiple separate systems. Our platform brings everything together into one place and uses AI to fill in the gaps that current tools can't — particularly short-term prediction and storm tracking.

---

## Who Is This For?

### Weather Forecasters (Primary Users)

The people at IMD who monitor the atmosphere and issue official warnings. They need the full picture — every piece of weather data, the AI prediction, storm tracking, uncertainty levels, and the ability to review and approve warnings before they go out.

### State & District Disaster Management Authorities

Officials responsible for disaster response at the state and district level. They don't need raw weather data — they need to know which areas are at risk, how severe the threat is, when it will arrive, and what important places (hospitals, schools, roads) might be affected.

### Emergency Responders

Teams like NDRF/SDRF, fire services, and police control rooms. They need simple, location-specific information — is my area at risk, what direction is the storm coming from, how much time do I have, and is it safe to continue operations?

---

## How Does It Work?

The system works like a pipeline with five clear stages.

### Stage 1 — Gather Weather Information

We collect data from five different types of sources:

- **Radar** — Scans the atmosphere to see where rain and storms are happening right now. This is the most important input.
- **Satellite** — Views from space showing cloud formation, cloud movement, and temperature changes at the top of clouds.
- **Lightning sensors** — Records of where lightning strikes are occurring and how frequently.
- **Ground weather stations** — Measurements of temperature, humidity, pressure, wind, and rainfall from stations on the ground.
- **Weather models** — Computer simulations of the atmosphere that give broader context about conditions that support storm formation.

### Stage 2 — Clean and Combine

Each of these sources comes in a different format, covers different areas, updates at different times, and measures things at different scales. Before the AI can use them, we need to:

- Check the data for errors or gaps
- Align everything to the same map grid
- Synchronize everything to the same time reference
- Combine them into a single, unified picture of the atmosphere

### Stage 3 — AI Prediction

The AI model looks at the last hour of combined weather data and predicts what will happen next — at 10, 20, 30, 40, 50, and 60 minutes into the future.

It doesn't just say "storm" or "no storm." It produces:

- **Predicted storm images** showing where storms will be at each future time step
- **Storm probability** — how likely a thunderstorm is at each location
- **Lightning probability** — how likely lightning is at each location
- **Individual storm tracking** — detecting each storm as a separate object, tracking its movement, speed, direction, intensity, and whether it's growing or shrinking
- **Predicted storm path** — where each storm is expected to move over the next hour
- **Confidence level** — how certain the prediction is (honestly reported, not inflated)

### Stage 4 — Risk Assessment

The AI predictions are passed to a separate decision layer that converts them into practical information:

- **Risk level** for each area (low, moderate, high, severe)
- **Estimated time of arrival** at specific locations
- **Affected districts and areas**
- **Exposed infrastructure** — which hospitals, schools, airports, highways, railways, and emergency facilities are in the storm's path
- **Warning recommendations** ready for a forecaster to review

### Stage 5 — Dashboard & Human Review

Everything is displayed on an interactive map-based dashboard. The forecaster can:

- See current weather conditions and AI predictions overlaid on a map
- Click on individual storms to see their details, trajectory, and risk
- Slide through time to see predictions for each future interval
- Check which areas and infrastructure are at risk
- Review warning recommendations
- Approve, edit, or dismiss a warning before it goes out

**The AI assists. The human decides.** No warning is ever sent automatically — a trained forecaster always has the final say.

---

## What Makes This Different?

This isn't a generic weather app or a chatbot. Here's what sets it apart:

1. **Storm-level tracking** — Instead of showing a vague colored map, the system detects and follows each individual storm, giving it an identity and tracking its life cycle.

2. **Predicted path with arrival time** — Each storm gets a projected trajectory showing where it will be at +15, +30, +45, and +60 minutes, along with an estimated time of arrival at any selected location.

3. **Honest uncertainty** — The system reports how confident it actually is, rather than displaying made-up percentages. If the prediction is uncertain, it says so.

4. **Impact awareness** — The platform doesn't just predict weather; it connects predictions to real-world impact by showing which people, buildings, roads, and facilities are at risk.

5. **Historical comparison** — When a storm appears, the system can find past storms with similar characteristics and show how those events evolved, giving forecasters valuable context.

6. **Evidence-based explanations** — When the system flags a high-risk area, it can show the forecaster *why* — which signals (increasing lightning, growing radar echoes, favorable atmospheric conditions) contributed to that assessment.

7. **Smart assistant (optional)** — A built-in assistant that can answer forecaster questions like "Why is this area flagged as high risk?" or "What does the operational guideline say about this situation?" — pulling answers from official documents and current data, with proper source references.

8. **System health visibility** — The dashboard clearly shows whether each data source is working, when it was last updated, and whether any inputs are missing — so no one trusts a prediction built on incomplete information.

---

## How the Dashboard Looks

### For Forecasters

```
┌──────────────────────────────────────────────────────────┐
│ System Health: Radar ● Satellite ● Lightning ● Stations ●│
├──────────────────────────────────────────────────────────┤
│                                                          │
│                    Interactive Map                        │
│                                                          │
│     🔴 Storm C-1042 → NE at 38 km/h                     │
│        └── predicted path with uncertainty               │
│                                                          │
├──────────────────────┬───────────────────────────────────┤
│ Storm Details        │ Risk Level / Evidence / Confidence│
├──────────────────────┴───────────────────────────────────┤
│ Timeline: Now  +10  +20  +30  +40  +50  +60 min         │
└──────────────────────────────────────────────────────────┘
```

### For Disaster Authorities

A simplified view focused on:
- Risk map with affected districts highlighted
- Severity levels and estimated arrival times
- Exposed hospitals, schools, and critical facilities
- Current warning status

### For Responders

A minimal view showing:
- Is my location at risk?
- Which direction is the threat coming from?
- How much time do I have?
- Is it safe to continue operations?

---

## Building It Step by Step

We're building this in phases, starting small and expanding.

### Phase 1 — Core System

- Connect to weather data sources
- Build the AI prediction model (starting with radar, the most important input)
- Detect and track individual storms
- Predict storm paths 10–60 minutes ahead
- Build the interactive map dashboard
- Add storm probability and lightning risk layers
- Show prediction confidence
- Add the risk assessment layer
- Build the forecaster review and warning workflow
- Show data source health

### Phase 2 — Enhanced Intelligence

- Add satellite, lightning, station, and weather model data into the AI model
- Measure whether each additional data source actually improves predictions
- Add historical storm comparison
- Add infrastructure exposure mapping (hospitals, schools, airports, etc.)
- Add event replay — go back in time and watch how a past storm unfolded vs. what the AI predicted

### Phase 3 — Smart Assistant

- Add a question-answering assistant for forecasters
- Connect it to official guidelines, research, and historical records
- Let it pull live weather and prediction data when answering questions
- Ensure all answers cite their sources

---

## Starting Region

Rather than trying to cover all of India from day one, the first version focuses on a specific region — likely **Gujarat/Ahmedabad** — where we can access the necessary data and demonstrate the system end to end. Once proven, it can be expanded to other regions.

---

## Important Principles

- **AI assists, humans decide.** The system never issues warnings on its own.
- **Honesty over impressiveness.** We report actual model performance, not inflated numbers.
- **Science first, features second.** The prediction engine must work well before we add bells and whistles.
- **Show your work.** Every prediction should be backed by visible evidence.
- **Know your limits.** The dashboard clearly shows when data is missing or stale.

---

## Technology Overview

| Layer | What It Does |
|-------|-------------|
| Data collection | Gathers radar, satellite, lightning, station, and model data |
| Data processing | Cleans, aligns, and combines all data onto a common grid |
| AI engine | Predicts storm evolution 10–60 minutes ahead |
| Storm tracker | Identifies individual storms and follows their movement |
| Risk engine | Converts predictions into risk levels, arrival times, and exposure |
| Database | Stores geographic data, storm records, alerts, and searchable documents |
| Dashboard | Interactive map-based interface for forecasters and authorities |
| Smart assistant | Answers questions using official documents and live data |

---

*Built for Smart India Hackathon 2026 — Problem Statement SIH26072*
*Ministry of Earth Sciences · India Meteorological Department*
