# Cognitive Aid

Cognitive Aid is a Python-based cognitive training and assessment application designed for attention and working-memory tasks. The project focuses on children and individuals with attention-related difficulties such as ADHD by combining adaptive memory challenges, behavioral analytics, lapse tracking, and visual feedback into an interactive game-based environment. :contentReference[oaicite:0]{index=0}

The application includes multiple game modes involving sequence recall, mental reversal, grid rotation, associative memory, and mixed cognitive tasks. It also provides player-wise persistent progress tracking and a professional analytics dashboard for longitudinal performance analysis.

---

# Demo Links

## GitHub Repository

🔗 https://github.com/abdulrm624/CognitiveAid

---

## Primary Video Demonstration

🔗 https://iiithydstudents-my.sharepoint.com/:v:/g/personal/sudershan_sarraf_students_iiit_ac_in/IQA5VUva31DwS66vEBaQt655AT1UEktw8P2c4sj9i78-Nbo

---

## Alternative Video Demonstration

🔗 https://drive.google.com/file/d/1ILlg35kHZtP4CaZOwcwYLzSh4hcMC2Nk/view?usp=sharing

---

## Future UI Demo

🔗 https://cognitive-aid-game.vercel.app/

---

# Features

- Player profile support using name and age

- Two gameplay categories:
  - Grid-based memory tasks
  - Object-based memory tasks with floating abstract shapes

- Multiple cognitive gameplay modes:
  - Normal
  - Mental Reversal
  - Grid Rotation 90°
  - Grid Rotation 180°
  - Reversal + Rotation 90°
  - Reversal + Rotation 180°
  - Letter Association
  - Letter Reversal
  - Mixed Mode

- Adaptive difficulty progression

- Consecutive-correct level advancement

- Recovery mode after mistakes

- Dynamic grid expansion:
  - 3×3
  - 4×4
  - 5×5

- Four-minute timed sessions

- Attention lapse detection based on inactivity

- Persistent player-wise local data storage

- Password-protected results dashboard

- Behavioral analytics and visualizations

---

# Cognitive Motivation

The project was designed around the relationship between:

- sustained attention,
- working memory,
- executive control,
- cognitive flexibility,
- and behavioral engagement.

The system attempts to transform traditional memory and attention tasks into a more engaging game-like interaction while still preserving meaningful behavioral metrics such as:

- accuracy,
- response latency,
- lapse duration,
- level progression,
- and progress index.

The different gameplay modes intentionally vary the level of cognitive demand placed on the player. Tasks involving reversal, spatial rotation, and mixed-rule switching increase executive and working-memory load beyond simple sequential recall.

---

# Game Modes

## Normal

Repeat the sequence in the same order.

---

## Mental Reversal

Repeat the sequence in reverse order.

---

## Grid Rotation 90°

Mentally rotate the grid by 90° before responding.

---

## Grid Rotation 180°

Mentally rotate the grid by 180° before responding.

---

## Reversal + Rotation 90°

Rotate the grid and respond in reverse order.

---

## Reversal + Rotation 180°

Rotate the grid and respond in reverse order.

---

## Letter Association

Each cell is associated with a letter. The player selects the correct cell and types the associated letter.

---

## Letter Reversal

Similar to Letter Association but performed in reverse order.

---

## Mixed Mode

The active gameplay rule changes dynamically between levels.

---

# Categories

## Grid Category

The player memorizes highlighted grid cells.

The system progressively increases difficulty by expanding the grid:

- 3×3
- 4×4
- 5×5

---

## Objects Category

The player memorizes abstract object shapes instead of numbered cells.

The objects may float dynamically across the screen to increase visual-tracking and attention demands.

Only:

- Normal
- Mental Reversal

are available in Objects mode.

---

# Behavioral Metrics Collected

The application records detailed performance metrics including:

- Score
- Accuracy
- Error rate
- Response latency
- Highest level reached
- Level progression history
- Attention lapse count
- Total lapse duration
- Longest lapse
- Average response time
- Lifetime statistics
- Progress index

These metrics help analyze:

- sustained attention,
- cognitive load,
- working-memory performance,
- fatigue,
- and longitudinal behavioral trends.

---

# Progress Index

The Progress Index is one of the key analytical metrics used in the project.

It measures:

- active engagement time,
- response efficiency,
- and correctness simultaneously.

A lower progress index generally indicates:

- faster successful responses,
- fewer lapses,
- and more efficient cognitive performance.

---

# Results Dashboard

The application includes a password-protected analytics dashboard.

The dashboard includes visualizations for:

- Response-time trends
- Level progression
- Accuracy by mode
- Peak level reached per session
- Attention lapse duration
- Average response time by level
- Lifetime statistics

---

# Installation

## Clone the Repository

```bash
git clone https://github.com/abdulrm624/CognitiveAid.git

cd CognitiveAid

## Create a Virtual Environment

```bash
python3 -m venv cognitive-aid
```

---

# Activate the Virtual Environment

## Linux / macOS

```bash
source cognitive-aid/bin/activate
```

## Windows

```bash
cognitive-aid\Scripts\activate
```

---

# Install Required Libraries

```bash
pip install pillow matplotlib
```

---

## If tkinter is missing on Linux

```bash
sudo apt install python3-tk
```

---

# Running the Application

```bash
python3 btp1.py
```

---

# How to Play

1. Enter player name and age.

2. Select a category:
   - Grid
   - Objects

3. Select a game mode.

4. Click **Start Game**.

5. Watch the highlighted cells or objects carefully.

6. Repeat the sequence according to the selected gameplay rule.

7. Complete as many correct trials as possible before the session timer ends.

All session data is automatically saved locally.

---

# Scoring and Progression

- Correct responses increase score.

- Each correct sequence awards points based on level difficulty.

- The player has 3 lives per session.

- 5 consecutive correct trials advance the player to the next level.

- Mistakes may trigger recovery mode.

- Recovery mode requires 4 correct trials to restore the previous level.

---

# Data Storage

Player data is stored locally in JSON format.

Stored data includes:

- session history,
- scores,
- response times,
- lapse information,
- level progression,
- and lifetime statistics.

Generated object shapes are stored automatically inside a local `shapes/` directory.

---

# Repository Structure

```text
CognitiveAid/
│
├── btp1.py
├── shapes/
│   ├── shape_1.png
│   ├── shape_2.png
│   └── ...
│
├── README.md
├── full.jpeg
├── normal.jpeg
├── objects.jpeg
└── results.jpeg
```

---

# Technologies Used

- Python 3
- tkinter
- Pillow (PIL)
- matplotlib
- JSON persistence

---

# Future Improvements

- Improved UI and UX design
- Web and mobile deployment
- Sound cues and auditory feedback
- Real-world ADHD testing and cognitive evaluation
- Therapist/admin dashboard
- CSV and PDF report export
- Adaptive AI-based difficulty adjustment
- Additional cognitive gameplay modes
- Accessibility improvements
- Executable packaging

---

# Authors

## Abdul Rahman Mujtaba

2023102024

---

## Sudershan Sarraf

20231020215

---

# Notes

- The application stores all data locally.

- Internet connection is not required.

- The dashboard password is currently hardcoded.

- For production deployment, secure authentication and encrypted storage should be implemented.

---

# License

This project is intended for educational, research, and experimental purposes.
