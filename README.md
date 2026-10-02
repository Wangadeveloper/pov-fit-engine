# pov-fit-engine

**POV — Fit Intelligence & Live Virtual Try-On Platform**

An intelligent fashion e-commerce and sizing engine powered by Flask, Cloud Firestore/SQLite, and Perfect Corp (YouCam) AI Virtual Try-On.

## Features

- 👗 **Interactive Shop & Catalog**: Explore curated apparel items with real-time size recommendations.
- 📸 **User Fit Profile & Photo Upload**: Upload full-body photos via drag-and-drop or camera capture for accurate AR preview.
- 🪄 **Live AI Virtual Try-On**: Integration with YouCam S2S API (`v2.0/task/cloth-v3`) for instant AI garment rendering on user photos.
- ⚡ **Sandbox Mode**: Embedded fallback renderer allowing live preview without requiring an active API key during local dev.
- 📦 **Smart Wardrobe / Closet**: Save tried-on items directly to your personal wardrobe.

## Getting Started

### Prerequisites

- Python 3.10+
- Virtual environment (`venv`)

### Installation

1. Clone the repository:
   ```bash
   git clone git@github.com:Wangadeveloper/pov-fit-engine.git
   cd pov-fit-engine
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```

5. Run the development server:
   ```bash
   python3 run.py
   ```

6. Open [http://localhost:5000](http://localhost:5000) in your browser.
