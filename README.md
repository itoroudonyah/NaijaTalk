# NaijaTalk

NaijaTalk is a real-time speech translation app for Nigerian languages. It combines a Flutter client with a FastAPI backend that transcribes speech, translates the recognized text, and returns synthesized speech over a WebSocket connection.

## Features

- Speech-to-text for English, Yoruba, Hausa, and Igbo
- Text translation between supported languages
- Text-to-speech playback for translated output
- Flutter frontend for web, mobile, and desktop targets
- FastAPI backend with REST health endpoints and WebSocket translation flow
- Provider-selectable TTS support for YarnGPT, Google Cloud TTS, and Abena TTS

## Project Structure

```text
NaijaTalk/
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── main.py           # API routes and WebSocket endpoint
│   │   ├── models/           # ASR, translation, and TTS adapters
│   │   ├── services/         # Audio processing pipeline
│   │   └── websocket_manager.py
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   └── naijatalk_app/        # Flutter application
├── third_party/
│   └── yarngpt/              # YarnGPT submodule
├── docker-compose.yml
└── README.md
```

## Supported Languages

| Code | Language |
| --- | --- |
| `en` | English |
| `yo` | Yoruba |
| `ha` | Hausa |
| `ig` | Igbo |

## How It Works

1. The Flutter app records microphone audio.
2. Audio is encoded as base64 and sent to the backend WebSocket endpoint.
3. The backend converts audio to WAV using `pydub`.
4. ASR transcribes the audio with NCAIR language models.
5. Translation runs through `deep-translator` with fallback behavior.
6. TTS generates translated speech using the selected provider.
7. The backend sends translated text first, then generated audio.

## Prerequisites

- Python 3.11 recommended
- Flutter SDK 3.x
- Git
- FFmpeg, required by `pydub`
- A GitHub clone with submodules enabled

Install FFmpeg on macOS:

```bash
brew install ffmpeg
```

## Clone

Because YarnGPT is tracked as a submodule, clone with:

```bash
git clone --recurse-submodules git@github.com:itoroudonyah/NaijaTalk.git
cd NaijaTalk
```

If you already cloned without submodules:

```bash
git submodule update --init --recursive
```

## Backend Setup

From the project root:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

The backend starts on:

```text
http://localhost:8000
```

Useful endpoints:

```text
GET  /health
GET  /languages
WS   /ws/translate/{client_id}
```

## Frontend Setup

Open a second terminal:

```bash
cd frontend/naijatalk_app
flutter pub get
flutter run -d chrome
```

The Flutter app connects to:

```text
ws://localhost:8000/ws/translate/naijatalk_client
```

Make sure the backend is running before using the app.

## Environment Variables

Create `backend/.env` for local-only configuration. Do not commit this file.

```bash
PORT=8000
TTS_PROVIDER=yarngpt
YARNGPT_REPO_DIR=../third_party/yarngpt
YARNGPT_CACHE_DIR=~/.cache/naijatalk/yarngpt
```

### TTS Provider Options

| Provider | Value |
| --- | --- |
| YarnGPT | `yarngpt` |
| Google Cloud TTS | `google` |
| Abena TTS | `abena` |

For Google Cloud TTS, configure Google Application Default Credentials or set:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
```

Keep service account JSON files out of git.

For Abena TTS:

```bash
ABENA_API_KEY=your_api_key
```

## Model Notes

The backend loads most ML models lazily on the first request. First-time requests can be slow because models and tokenizer assets may need to download.

ASR model IDs:

- `NCAIR1/NigerianAccentedEnglish`
- `NCAIR1/Yoruba-ASR`
- `NCAIR1/Hausa-ASR`
- `NCAIR1/Igbo-ASR`

YarnGPT TTS uses:

- `saheedniyi/YarnGPT2`
- `novateur/WavTokenizer-medium-speech-75token`

## Git Hygiene

The repo intentionally ignores:

- Python virtual environments
- Python cache files
- Flutter build output
- local IDE files
- `.env` files
- Google service account JSON files
- local presentations and office temp files

Do not commit secrets such as API keys, service account files, or local credentials.

## Common Issues

### `ffmpeg` or audio conversion errors

Install FFmpeg:

```bash
brew install ffmpeg
```

### Flutter app says disconnected

Start the backend first:

```bash
cd backend
source venv/bin/activate
python run.py
```

Then restart the Flutter app.

### YarnGPT source repo not found

Initialize submodules:

```bash
git submodule update --init --recursive
```

Or set:

```bash
YARNGPT_REPO_DIR=/absolute/path/to/yarngpt
```

### GitHub push fails

Use SSH authentication:

```bash
ssh -T git@github.com
git push origin main
```

## Development Commands

Backend:

```bash
cd backend
source venv/bin/activate
python run.py
```

Frontend:

```bash
cd frontend/naijatalk_app
flutter pub get
flutter analyze
flutter test
flutter run -d chrome
```

## License

Add a license before publishing or sharing this project publicly.
