# Ultron Voice Assistant

A small voice-activated personal assistant with typed-input fallback.

## Setup

Use the project virtual environment:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

A working microphone is required for voice commands. The assistant uses Google speech recognition, so voice recognition needs an internet connection. Weather data comes from Open-Meteo and headlines come from the BBC RSS feed; no API keys are required.

## General questions

Local commands are handled first. Questions that do not match those commands can use Google's Gemini 2.0 Flash free tier. Create a Gemini API key, then set it in the same PowerShell session used to start the server:

```powershell
$env:GEMINI_API_KEY = "your-key-here"
python server.py
```

Or use a local `.env` file. Copy the template; do not put the key in `.env.example`:

```powershell
Copy-Item .env.example .env
notepad .env
python server.py
```

The `.env` file must contain exactly one setting, for example `GEMINI_API_KEY=your-key-here`. Restart `server.py` after changing the key.

The key is read only by Python and is never sent to the browser. Do not commit it to the repository. Without the key, the assistant explains how to enable the fallback instead of making an external request.

## Run the web interface

Start the local web server:

```powershell
python server.py
```

Then open `http://127.0.0.1:8000` in a browser. Click the orb to use the computer microphone through Python speech recognition, or type a question below it. Answers are sent to `assistant.py` and spoken by the browser.

If voice input does not start, check that Windows allows microphone access for the Python application and that a microphone is selected in the system settings. The typed input remains available when a microphone is unavailable.

## Run the terminal assistant

```powershell
python assistant.py
```

If microphone input is unavailable, the assistant falls back to typed commands.

## Supported commands

- `help`
- `what time is it`
- `what is the weather in London`
- `read the news`
- `tell me a joke`
- `search Wikipedia for Ada Lovelace`
- `remind me to take a break in 10 minutes`
- `show reminders`
- `open Google`
- `open YouTube`
- `exit`

Reminders are saved in `reminders.json` next to the script and are checked while the assistant is running.
