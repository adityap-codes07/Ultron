import contextvars
import datetime as dt
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from pathlib import Path

import pyjokes
import pyttsx3
import speech_recognition as sr
import wikipedia


REMINDERS_FILE = Path(__file__).with_name("reminders.json")
NEWS_FEED_URL = "https://feeds.bbci.co.uk/news/rss.xml"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
response_messages = []
command_lock = threading.Lock()
audio_enabled = contextvars.ContextVar("audio_enabled", default=True)


def load_environment_file():
    environment_file = Path(__file__).with_name(".env")
    if not environment_file.exists():
        return
    for line in environment_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if separator and key and not os.environ.get(key):
            os.environ[key] = value


load_environment_file()


def speak(text):
    """Print and speak a response, continuing if audio output is unavailable."""
    response_messages.append(str(text))
    print(f"Assistant: {text}")
    if not audio_enabled.get():
        return
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except (RuntimeError, OSError):
        print("Speech output not supported.")


def wish_user():
    hour = dt.datetime.now().hour
    greeting = "Good Morning!" if hour < 12 else "Good Afternoon!" if hour < 18 else "Good Evening!"
    speak(greeting)
    speak("I am your voice assistant. How can I help you today?")


def listen_for_voice():
    """Capture one voice command from the computer running the server."""
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
        query = recognizer.recognize_google(audio)
        print(f"You: {query}")
        return query.lower().strip(), ""
    except sr.WaitTimeoutError:
        return "", "I did not hear anything before the timeout."
    except sr.UnknownValueError:
        return "", "I could not understand the audio."
    except sr.RequestError:
        return "", "Speech recognition needs an internet connection."
    except OSError:
        return "", "No working microphone was found."


def take_command(use_voice=True):
    """Listen for a command and fall back to typed input when needed."""
    if not use_voice:
        return input("You (type your command): ").strip().lower()

    query, error = listen_for_voice()
    if query:
        return query
    speak(error)
    return input("You (type your command): ").strip().lower()


def load_reminders():
    if not REMINDERS_FILE.exists():
        return []
    try:
        return json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save_reminders(reminders):
    REMINDERS_FILE.write_text(json.dumps(reminders, indent=2), encoding="utf-8")


def reminder_checker(stop_event):
    """Announce due reminders while the command loop remains available."""
    while not stop_event.wait(15):
        reminders = load_reminders()
        now = dt.datetime.now(dt.timezone.utc)
        changed = False
        for reminder in reminders:
            if not reminder["done"] and dt.datetime.fromisoformat(reminder["when"]) <= now:
                speak(f"Reminder: {reminder['message']}")
                reminder["done"] = True
                changed = True
        if changed:
            save_reminders(reminders)


def create_reminder(query):
    match = re.search(r"remind me to (.+?) in (\d+) (minute|minutes|hour|hours)", query)
    if not match:
        speak("Please say, remind me to do something in 10 minutes.")
        return

    message, amount, unit = match.groups()
    seconds = int(amount) * (3600 if unit.startswith("hour") else 60)
    when = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds)
    reminders = load_reminders()
    reminders.append({"message": message.strip(), "when": when.isoformat(), "done": False})
    save_reminders(reminders)
    speak(f"I will remind you to {message.strip()} in {amount} {unit}.")


def list_reminders():
    reminders = [reminder for reminder in load_reminders() if not reminder["done"]]
    if not reminders:
        speak("You have no pending reminders.")
        return
    for reminder in reminders:
        when = dt.datetime.fromisoformat(reminder["when"]).astimezone().strftime("%H:%M")
        speak(f"{reminder['message']} at {when}.")


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Ultron Assistant/1.0"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def weather_report(query):
    location = re.sub(r"\b(weather|forecast|in|at|for|what|is|the|like|today)\b", " ", query)
    location = " ".join(location.split()).strip()
    if not location:
        speak("Please include a location, such as weather in London.")
        return
    try:
        search_url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode({"name": location, "count": 1})
        place = get_json(search_url)["results"][0]
        forecast_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": place["latitude"], "longitude": place["longitude"], "current": "temperature_2m,wind_speed_10m",
        })
        current = get_json(forecast_url)["current"]
        speak(f"In {place['name']}, it is {current['temperature_2m']} degrees Celsius with wind at {current['wind_speed_10m']} kilometers per hour.")
    except (KeyError, IndexError, OSError, ValueError, urllib.error.URLError):
        speak("I could not retrieve the weather right now.")


def read_news():
    try:
        request = urllib.request.Request(NEWS_FEED_URL, headers={"User-Agent": "Ultron Assistant/1.0"})
        with urllib.request.urlopen(request, timeout=10) as response:
            root = ET.fromstring(response.read())
        headlines = [item.findtext("title") for item in root.findall(".//item")[:5]]
        if not headlines:
            raise ValueError("No headlines returned")
        speak("Here are the latest headlines.")
        for index, headline in enumerate(headlines, start=1):
            speak(f"{index}. {headline}")
    except (ET.ParseError, OSError, ValueError, urllib.error.URLError):
        speak("I could not retrieve the news right now.")


def ask_general_question(query):
    """Use Gemini's free tier for questions outside the local command set."""
    load_environment_file()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        speak("General answers are disabled because GEMINI_API_KEY is not loaded. Add it to .env, then restart server.py.")
        return

    payload = json.dumps({
        "contents": [{"parts": [{"text": query}]}],
        "systemInstruction": {
            "parts": [{"text": "You are Ultron, a concise personal assistant. Answer clearly in three short sentences or fewer."}]
        },
    }).encode("utf-8")
    url = f"{GEMINI_API_URL}?key={urllib.parse.quote(api_key)}"
    request = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "User-Agent": "Ultron Assistant/1.0",
    }, method="POST")
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
            answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            speak(answer)
            return
        except urllib.error.HTTPError as error:
            if error.code == 503 and attempt == 0:
                time.sleep(1)
                continue
            if error.code in (400, 401, 403):
                speak("Gemini rejected the API key. Replace it with a valid key in .env and restart the server.")
            elif error.code == 404:
                speak("The configured Gemini model is unavailable for this API. Update the model in assistant.py.")
            elif error.code == 429:
                speak("The Gemini free-tier limit has been reached. Please try again later.")
            elif error.code == 503:
                speak("Gemini is temporarily overloaded. Please try the question again in a moment.")
            else:
                speak("The general knowledge service is temporarily unavailable.")
            return
        except (KeyError, IndexError, json.JSONDecodeError, OSError, ValueError, urllib.error.URLError):
            speak("I could not get an answer from the general knowledge service right now.")
            return


def process_command(query, speak_response=True):
    """Process a command and return the messages generated for the frontend."""
    with command_lock:
        token = audio_enabled.set(speak_response)
        try:
            response_messages.clear()
            handle_command(query)
            return " ".join(response_messages)
        finally:
            audio_enabled.reset(token)


def handle_command(query):
    """Process one command and return False when the assistant should stop."""
    if not query:
        return True
    if "exit" in query or "bye" in query:
        speak("Goodbye! Have a nice day!")
        return False
    if "help" in query:
        speak("You can ask for the time, weather, news, jokes, Wikipedia, reminders, Google, or YouTube.")
    elif "remind me" in query:
        create_reminder(query)
    elif "show reminders" in query or "list reminders" in query:
        list_reminders()
    elif "weather" in query or "forecast" in query:
        weather_report(query)
    elif "news" in query or "headlines" in query:
        read_news()
    elif "wikipedia" in query:
        try:
            result = wikipedia.summary(query.replace("wikipedia", "").strip(), sentences=2)
            speak(f"According to Wikipedia: {result}")
        except (wikipedia.exceptions.DisambiguationError, wikipedia.exceptions.PageError, ValueError):
            speak("Sorry, I could not find anything.")
    elif "open youtube" in query:
        speak("Opening YouTube...")
        webbrowser.open("https://www.youtube.com")
    elif "open google" in query:
        speak("Opening Google...")
        webbrowser.open("https://www.google.com")
    elif "time" in query:
        speak(f"The current time is {dt.datetime.now().strftime('%H:%M:%S')}")
    elif "joke" in query:
        speak(pyjokes.get_joke())
    else:
        ask_general_question(query)
    return True


def run_assistant(use_voice=True):
    wish_user()
    stop_event = threading.Event()
    threading.Thread(target=reminder_checker, args=(stop_event,), daemon=True).start()
    try:
        while handle_command(take_command(use_voice)):
            time.sleep(0.1)
    finally:
        stop_event.set()


if __name__ == "__main__":
    run_assistant()
    