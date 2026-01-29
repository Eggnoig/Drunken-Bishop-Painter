# Drunken-Bishop-Painter
Desktop app that generates "drunken bishop" ASCII art from text input, with multiple hashing/encoding options. There are currently releases for Windows, Linux, and macOS. These releases are not signed as of right now, but they running the script on its own will function just as well, you just don't need to set up a virtual enviroment if you use the release. 

**Current Release**: v0.2.0

## Features
- Text -> bytes -> bishop walk rendering with start/end markers
- Hash or raw-bytes mode with optional salt and iterations
- Multiple color schemes plus a plain ASCII view
- Adjustable board size
- Optional animated walk preview with custom step timing

## Quick Start
1) Create a virtual environment and install requirements
2) Run `painter.py`

Example (Linux/macOS):
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python painter.py
```

Example (Windows PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python painter.py
```

## Usage
- Enter text, choose encoding and mode, then click Generate.

| Option | Description |
| --- | --- |
| Input text | Source text that is converted to bytes for the walk. |
| Encoding (UTF) | How the text is encoded (utf-8, ascii, latin-1, utf-16, utf-32). |
| Mode | Use a hash digest or raw bytes directly. |
| Hash | Hash algorithm used when Mode is Hash. |
| Scheme | Color palette for the colored view. |
| Salt | Optional extra bytes mixed into hashing. |
| Iterations | Number of hash rounds (1 = no strengthening). |
| Board W | Width of the walk grid. |
| Board H | Height of the walk grid. |
| Auto-update | Regenerates output when inputs change. |
| Show walk | Animates the bishop path step-by-step. |
| Walk time | Delay between steps in milliseconds. |
| Generate | Builds the output immediately. |

## Future Features
- Option to download ASCII Image
- Option to download GIF of the "Bishop" Walking
- Custom Color Schemes
- User drawn art -> generated hash
