# Neural AI Agent

> **Created by: Ashish Thipkurle**  
> *A cutting-edge, local-first autonomous AI agent designed for advanced interaction, vision, and command execution.*

---

## 🚀 Overview
The **Neural AI Agent** is a modular, extensible AI system that runs locally on your machine. It combines powerful LLMs (Linear Logic Models) with real-time voice synthesis, computer vision, and OS-level capability to act as a true digital assistant.

## ✨ Features
- **🧠 LLM Brain**: Powered by **gpt-oss:120b-cloud** and **llava**.
- **🗣️ Voice Interface**: Real-time speech-to-text (Whisper) and high-quality text-to-speech (Piper).
- **👁️ Computer Vision**: Uses **llava** and Vision LLMs to "see" and analyze the screen or camera feed.
- **🌐 3D Interactive Globe**: A futuristic UI visualization of the agent's "thought network".
- **💻 Desktop Control**: Can launch apps, search the web (Wikipedia/DuckDuckGo), and run terminal commands.
- **🛡️ Hybrid Architecture: Core logic runs locally, but high-intelligence tasks are processed via a secure cloud connection.
---

## 🛠️ Tech Stack
- **Core**: Python 3.10+
- **Frontend**: React, TypeScript, Vite, Electron (for Desktop App)
- **AI Backend**: Ollama
- **Vision**: Ultralytics YOLOv8, OpenCV
- **Voice**: Piper TTS, Faster-Whisper

---

## 🔧 Setup Guide

### Prerequisites
1. **Ollama**: Download and install from [ollama.com](https://ollama.com).
   - Pull a model: `ollama pull llama3` (or `phi3:mini`)
2. **Python 3.10+**: Ensure Python is installed and added to PATH.
3. **Node.js**: Required for the React frontend.

### Installation
1. **Clone the Repository**
   ```bash
   git clone https://github.com/ashishthipkurle/Neural_AI_Agent.git
   cd Neural_AI_Agent
   ```

2. **Install Python Dependencies**
   (Recommended to use a virtual environment)
   ```bash
   pip install -r requirements.txt
   ```
   *Note: If you encounter issues with `piper-tts`, ensure you have the correct wheel for your OS.*

3. **Install Frontend Dependencies**
   ```bash
   cd desktop
   npm install
   cd ..
   ```

### 🚀 Usage

**Easy Start (Recommended)**
Double-click `start-all.bat` to launch everything automatically:
- Starts Ollama (if not running)
- Starts Python API Server (Port 8000)
- Starts React Frontend (Port 5173 / Electron)

**Manual Start**
1. **Start API**: `python agent/main.py`
2. **Start UI**: `cd desktop && npm run dev`

---

## 📂 Project Structure

```
/Neural_AI_Agent
 ├── agent/
 │   ├── core/           # Intent parsing, LLM interface, Event loop
 │   ├── tools/          # Capabilities (Web Search, OS Control, Vision)
 │   ├── memory/         # Database and Vector Store handling
 │   ├── vision/         # Camera and Screen analysis logic
 │   └── main.py         # Backend Entry Point
 │
 ├── desktop/            # React + Electron Frontend
 │   ├── src/renderer/   # UI Components (Chat, Globe, Code Editor)
 │   └── src/main/       # Electron Main Process
 │
 ├── web/                # (Optional) Web-only client
 │
 ├── voice_models/       # Piper TTS Models
 ├── piper/              # Piper executable for local TTS
 ├── logs/               # Application logs
 └── start-all.bat       # One-click startup script
```

---

## 🤝 Contribution
Created and maintained by **Ashish Thipkurle**.
Feel free to open issues or submit pull requests to improve the agent!
