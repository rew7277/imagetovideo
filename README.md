# ◈ Canvara — Collaborative Drawing App

A real-time collaborative drawing app built with **FastAPI**, **SQLite/PostgreSQL**, **WebSockets**, and vanilla HTML/CSS/JS.

![Canvara Screenshot](docs/screenshot.png)

## Features

- 🔐 **JWT Authentication** — signup, login, logout
- 🎨 **Drawing Board** — pen, eraser, line, rectangle, circle tools
- 🎨 **Color Picker** — full color picker + preset palette
- 💾 **Save & Load** — all drawings persisted to database
- 🖼️ **Dashboard** — gallery view of all your canvases with thumbnails
- 🔴 **Real-time Collaboration** — WebSocket-powered live drawing with others
- 🪄 **Background Removal** — client-side pixel manipulation
- 📤 **PNG Export** — download your drawing
- ↩️ **Undo / Redo** — full history support
- 📱 **Touch Support** — works on tablets and mobile

---

## Tech Stack

| Layer     | Tech                                |
|-----------|-------------------------------------|
| Backend   | FastAPI, Python 3.11                |
| ORM       | SQLAlchemy 2.0                      |
| Database  | SQLite (local) / PostgreSQL (prod)  |
| Auth      | JWT (python-jose) + bcrypt          |
| Realtime  | WebSockets (FastAPI native)         |
| Frontend  | Vanilla HTML/CSS/JS                 |
| Fonts     | Syne + Space Mono (Google Fonts)    |
| Deploy    | Railway.app                         |

---

## Project Structure

```
canvara/
├── backend/
│   ├── main.py              # FastAPI app entrypoint
│   ├── core/
│   │   ├── database.py      # SQLAlchemy engine + session
│   │   └── security.py      # JWT, bcrypt helpers
│   ├── models/
│   │   ├── user.py          # User ORM model
│   │   └── canvas.py        # Canvas ORM model
│   ├── schemas/
│   │   ├── auth.py          # Pydantic request/response schemas
│   │   └── canvas.py
│   └── routers/
│       ├── auth.py          # POST /api/auth/register, /login, GET /me
│       ├── canvas.py        # CRUD /api/canvas/
│       └── websocket.py     # WS /ws/draw/{canvas_id}
├── frontend/
│   ├── templates/
│   │   └── index.html       # Single-page app shell
│   └── static/
│       ├── css/main.css
│       └── js/
│           ├── api.js        # REST + WebSocket client
│           ├── canvas.js     # DrawingEngine class
│           └── app.js        # SPA controller
├── requirements.txt
├── Procfile                  # Railway deployment
├── runtime.txt
├── .env.example
├── alembic.ini
└── README.md
```

---

## Local Setup

### 1. Clone & navigate

```bash
git clone https://github.com/yourname/canvara.git
cd canvara
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum change SECRET_KEY
```

### 5. Run the server

```bash
uvicorn backend.main:app --reload --port 8000
```

Open your browser at: **http://localhost:8000**

The SQLite database (`canvasapp.db`) will be created automatically on first run.

---

## API Endpoints

### Auth
| Method | Endpoint              | Description           |
|--------|-----------------------|-----------------------|
| POST   | `/api/auth/register`  | Register new user     |
| POST   | `/api/auth/login`     | Login, returns JWT    |
| GET    | `/api/auth/me`        | Get current user      |

### Canvas
| Method | Endpoint              | Description               |
|--------|-----------------------|---------------------------|
| GET    | `/api/canvas/`        | List all user canvases    |
| POST   | `/api/canvas/`        | Create new canvas         |
| GET    | `/api/canvas/{id}`    | Load canvas with data     |
| PUT    | `/api/canvas/{id}`    | Update/save canvas        |
| DELETE | `/api/canvas/{id}`    | Delete canvas             |

### WebSocket
| URL                        | Description                          |
|----------------------------|--------------------------------------|
| `ws://host/ws/draw/{id}`   | Real-time drawing room for canvas ID |

---

## Deploy to Railway

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourname/canvara.git
git push -u origin main
```

### 2. Create Railway project

1. Go to [railway.app](https://railway.app) and sign in
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your repo

### 3. Add PostgreSQL

1. In Railway dashboard: click **+ Add Service** → **Database** → **PostgreSQL**
2. Railway auto-sets `DATABASE_URL` — no manual config needed!

### 4. Set environment variables

In Railway → your service → **Variables** tab, add:

```
SECRET_KEY=your-super-secret-random-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

`DATABASE_URL` is injected automatically by Railway.

### 5. Deploy

Railway will detect the `Procfile` and `runtime.txt` and deploy automatically.
Your app will be live at `https://your-app.up.railway.app`.

---

## Keyboard Shortcuts

| Key        | Action       |
|------------|--------------|
| `P`        | Pen tool     |
| `E`        | Eraser       |
| `L`        | Line         |
| `R`        | Rectangle    |
| `C`        | Circle       |
| `Ctrl+Z`   | Undo         |
| `Ctrl+Y`   | Redo         |
| `Ctrl+S`   | Save         |

---

## Development Notes

- **Auto-save**: Canvas auto-saves every 30 seconds while in the studio
- **WebSocket rooms**: Each canvas has its own room — only users editing the same canvas see each other's strokes in real-time
- **Background removal**: Client-side only — removes near-white pixels. For production use, consider integrating remove.bg API
- **Thumbnails**: Generated as 320×240 base64 PNG, stored in the database

---

## License

MIT — do whatever you want with it.
