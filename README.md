# Bot ChatGPT API - Next Gen

A powerful Next.js application providing access to state-of-the-art AI models including **ChatGPT 5**, along with utilities for Translation and YouTube Captions.

## Features

-   **ChatGPT 5**: The default model for intelligent conversations.
    -   Select "ChatGPT 5" in the playground or set `model: 'gpt-5'` in the API.
-   **Translator API**: Translate text between languages.
-   **YouTube Captions API**: Extract transcripts from YouTube videos.
-   **Mind Map Visualization**: Visualize your ideas directly in the Playground using Mermaid.js.

## Getting Started

1.  Install dependencies:
    ```bash
    npm install
    ```
2.  Run the development server:
    ```bash
    npm run dev
    ```
3.  Open [http://localhost:3000](http://localhost:3000).

## API Endpoints

### Chat Completion
**POST** `/api/chat`
```json
{
  "model": "gpt-5",
  "messages": [{"role": "user", "content": "Hello!"}],
  "stream": true
}
```

### Translator
**POST** `/api/translate`
```json
{
  "text": "Hello world",
  "target": "es"
}
```

### YouTube Transcript
**POST** `/api/youtube`
```json
{
  "url": "https://www.youtube.com/watch?v=..."
}
```

## Mind Maps
In the Playground, toggle the Network icon to view the Mind Map pane. Ask the AI to "draw a mind map" and it will generate a visualization for you.
