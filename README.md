# Claude Features Demo

Interactive React application showcasing Anthropic Claude capabilities via Azure AI Foundry.



## Quick Start

### 1. Start the Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

The Flask API starts at **http://localhost:5000**.

### 2. Start the Frontend

```bash
cd frontend
npm install
npm start
```

The React app starts at **http://localhost:3000**.

### 3. Use the App

1. Select a feature from the sidebar
2. Enter your prompt (if required)
3. Click **▶ Run** and watch the real-time streaming output
4. Download generated files (docx, pptx, pdf) directly from the browser

## Architecture

```
claude-demo/
├── backend/
│   ├── app.py               # Flask API (converted from claude.ipynb)
│   ├── requirements.txt
│   └── outputs/              # Generated files stored here
└── frontend/
    ├── public/index.html
    └── src/
        ├── index.js
        ├── index.css
        └── App.js            # Main React component
```

- **Backend** → Flask server with SSE streaming endpoints
- **Frontend** → React app consuming SSE for real-time token display
- Communication via **Server-Sent Events (SSE)** for live output streaming

