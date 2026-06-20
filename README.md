# Local AI Anime Storyboard Generator

Phase 1 MVP repository scaffold for a Windows-first local storyboard image generator.

Runtime setup and launch instructions will be added in their corresponding M0 tasks.

## Build This Project

### 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

### 2. Install dependencies

```bash
pip install -r requirements/base.txt -r requirements/dev.txt
```

### 3. Run tests

```bash
pytest
```

All tests should pass before launching the application.

### 4. Start the application

Development mode:

```bash
uvicorn app.main:app --reload
```

Production-style local run:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 5. Open the application

Open your browser and navigate to:

```text
http://127.0.0.1:8000
```

Health check endpoint:

```text
http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

## Future Packaging

The MVP is intended to run directly from source during development.

Future milestones may provide:

- PyInstaller packaging (`.exe`)
- Windows installer packaging
- One-click launcher scripts