# PaperTranslate UI

Frontend interface for the PaperTranslate project.

PaperTranslate is a local scientific document translation system designed for English–Vietnamese PDF translation with layout preservation.

This frontend is built with React and Vite.

## Features

Current frontend features include:

* PDF upload and drag-and-drop.
* Translation configuration.
* TranslateGemma 4B model interface.
* Translation policy configuration.
* Layout and document preservation options.
* OCR configuration.
* Export format selection.
* Processing progress interface.
* Original PDF preview.
* Translation result interface.
* History, Settings, and About pages.

> Note: Some statistics, history data, and processing progress are currently mock data for UI demonstration.

## Requirements

Before running the frontend, install:

* Node.js
* npm

Check your installation:

```bash
node --version
npm --version
```

## Clone the Repository

Clone the project:

```bash
git clone git@github.com:Jackouhai/Paper-Translate-Personal-Project.git
```

Move into the project directory:

```bash
cd Paper-Translate-Personal-Project
```

Switch to the frontend development branch:

```bash
git checkout thai-ubuntu
```

## Install Frontend Dependencies

Move into the frontend directory:

```bash
cd papertranslate-ui
```

Install the required dependencies:

```bash
npm install
```

You do not need to create a new React or Vite project.

The required dependencies are defined in `package.json` and `package-lock.json`.

## Run the Frontend

Start the Vite development server:

```bash
npm run dev
```

Vite will display a local development URL, for example:

```text
http://localhost:5173/
```

If port `5173` is already in use, Vite may automatically use another port such as `5174`.

Open the URL displayed in the terminal.

## Quick Start

After cloning the repository, the basic frontend setup is:

```bash
git checkout thai-ubuntu

cd papertranslate-ui

npm install

npm run dev
```

## Backend Connection

The frontend communicates with a FastAPI backend through:

```text
POST /translate
```

The current development backend is expected to run at:

```text
http://127.0.0.1:8002
```

The frontend expects a response similar to:

```json
{
  "status": "success",
  "filename": "paper.pdf",
  "pdf_url": "http://127.0.0.1:8002/uploads/paper.pdf",
  "html_url": "http://127.0.0.1:8002/outputs/paper.pdf.html"
}
```

The `pdf_url` field is used by the Original PDF Preview.

The `html_url` field is intended for translated document results.

If the backend uses another port or API address, the frontend API URL must be updated accordingly.

## Test the UI Without the AI Pipeline

The frontend interface can be started without PaddleOCR-VL or TranslateGemma:

```bash
cd papertranslate-ui
npm install
npm run dev
```

This allows developers to inspect and develop the UI.

However, features that require `/translate`, Original PDF Preview, or translated output require the backend service.

## Project Structure

```text
papertranslate-ui/
├── public/
│   ├── favicon.svg
│   └── icons.svg
├── src/
│   ├── assets/
│   ├── App.jsx
│   ├── App.css
│   ├── index.css
│   └── main.jsx
├── eslint.config.js
├── index.html
├── package.json
├── package-lock.json
├── vite.config.js
└── README.md
```

## Main Project Pipeline

The frontend is designed for the following workflow:

```text
User
  ↓
React Frontend
  ↓
FastAPI Backend
  ↓
pp_doclayout
  ↓
PaddleOCR-VL
  ↓
Layout Detection and OCR
  ↓
TranslateGemma
  ↓
Document Reconstruction
  ↓
HTML / PDF Export
```

## Development Status

Completed:

* React and Vite frontend.
* PDF upload interface.
* Translation configuration interface.
* Original PDF Preview integration.
* Frontend-to-backend API communication.

In development:

* Full FastAPI and `pp_doclayout` pipeline integration.
* Real-time processing progress.
* Translated HTML preview.
* PDF and Markdown export.
* Translation history.
* Local desktop packaging.

## Project Topic

**Applying Multimodal LLMs for English–Vietnamese Scientific Document Translation with Layout Preservation on Local Infrastructure**
