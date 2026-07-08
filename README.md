# SelfChat: Temporal Self Dialogue

SelfChat is a small, offline-first interactive installation prototype. A visitor writes about their present moment and receives two local, template-based reflections: one from their past self and one from their future self.

This version uses **no AI API**, sends no visitor text to the internet, and has only one dependency: Flask.

On Windows it uses local mock writing. On the Raspberry Pi it can use the
supplied offline Qwen GGUF model through `llama-cpp-python`. No cloud API is
required in either mode.

## Project structure

```text
selfchat/
├── app.py
├── local_ai.py
├── requirements.txt
├── README.md
├── templates/
│   └── index.html
└── static/
    ├── style.css
    ├── background.js
    └── interaction.js
```

## Install and run on Windows

Open PowerShell in the project folder, then create a virtual environment:

```powershell
python -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, run this once in the same window and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Install Flask and start the app:

```powershell
pip install -r requirements.txt
python app.py
```

Open the three pages needed by the installation:

- Control/input page: [http://localhost:5000/control](http://localhost:5000/control)
- Left display — Future Self: [http://localhost:5000/future](http://localhost:5000/future)
- Right display — Past Self: [http://localhost:5000/past](http://localhost:5000/past)

Put the Future window on the left monitor and the Past window on the right monitor. Press `F11` in each display window for browser full-screen mode. The control page can be used on the same computer, a small third touchscreen, or another device on the local network.

## Push the project to GitHub

Create an empty repository on GitHub first. In PowerShell, from this project folder, run:

```powershell
git add .
git commit -m "Create SelfChat exhibition prototype"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/selfchat.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username. If this folder already has an `origin` remote, check it with `git remote -v` instead of adding it again.

## Clone and run on Raspberry Pi

The Pi needs Raspberry Pi OS with Python 3 and an internet connection for the initial Git clone and Flask installation. After that, the installation itself can run offline.

Open a terminal on the Pi and install the required system packages:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
```

Clone the repository, enter it, and create a virtual environment:

```bash
git clone https://github.com/YOUR-USERNAME/selfchat.git
cd selfchat
python3 -m venv venv
source venv/bin/activate
```

Install Flask and run the app:

```bash
pip install -r requirements.txt
python app.py
```

## Connect the supplied local AI on Raspberry Pi

Keep the large model and the supplied hardware toolkit in their existing
`yourPrototype` folder. Do not commit the `models/` folder to GitHub.

First enter the supplied toolkit folder and initialise its Python environment:

```bash
cd ~/Desktop/ai-dreaming-together-code/yourPrototype
source initdemo.sh
```

In that same terminal, enter the SelfChat repository and install Flask into
the active toolkit environment:

```bash
cd ~/selfchat
python3 -m pip install -r requirements.txt
```

Tell SelfChat where the toolkit is and require the real local model:

```bash
export SELFCHAT_AI_MODE=local
export SELFCHAT_TOOLKIT_PATH="$HOME/Desktop/ai-dreaming-together-code/yourPrototype"
```

Test the model before starting the web installation:

```bash
python3 local_ai.py "I am nervous about beginning something new"
```

The first run takes longer because the GGUF model must load into memory. A
successful test prints separate `PAST` and `FUTURE` responses.

Then start SelfChat from the same terminal:

```bash
python3 app.py
```

Before the exhibition opens, load the model once by running this in a second
terminal:

```bash
curl -X POST http://localhost:5000/health/load
```

Check [http://localhost:5000/health](http://localhost:5000/health). The JSON
should contain `"toolkit_found": true` and `"model_loaded": true`.

If the local model ever fails during the exhibition, SelfChat returns a mock
response instead of leaving both screens stuck. The control page reports that
the safe backup was used.

Open two Chromium windows on the Pi:

- `http://localhost:5000/future` on the left monitor
- `http://localhost:5000/past` on the right monitor

Open `http://localhost:5000/control` wherever the visitor will type. This can be another browser tab, a small touchscreen, or a phone/tablet on the same local network. Use full-screen mode for both artwork windows.

To update an existing Raspberry Pi copy later:

```bash
cd selfchat
git pull
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Open from another device on the same network

The server listens on all local network interfaces. Find the Pi's IP address with:

```bash
hostname -I
```

Then open `http://PI-IP-ADDRESS:5000/control` on another device connected to the same network. For example: `http://192.168.1.50:5000/control`.

## How the two-screen version works

The Flask server keeps one small temporary state in memory. The Past and Future display pages check that state several times per second. When the visitor submits text on the control page, both display pages notice the change and reveal their own response. Pressing **Reset both screens** returns both displays to their opening greeting.

The state is intentionally temporary: restarting `app.py` clears the previous visitor's words.

## Stop the app

Return to the terminal where SelfChat is running and press `Ctrl+C`.

## How the mock works

`app.py` checks the visitor's text for a few broad emotional keywords, then combines local writing fragments into a Past Self and Future Self response. A repeatable text hash adds variation. Nothing is sent outside the computer.
