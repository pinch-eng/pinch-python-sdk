# Pinch Real-Time Translation Demo

A minimal web app that demonstrates Pinch real-time speech translation. Speak into your microphone and see original and translated transcripts appear side by side.

## Setup

1. **Set your API key** in the project root `.env` file:

   ```
   PINCH_API_KEY=your_api_key_here
   ```

2. **Install dependencies and start the server:**

   ```bash
   cd examples/real-time-demo-app
   npm install
   npm start
   ```

3. **Open the demo** at [http://localhost:3000](http://localhost:3000).

## Usage

- Click **Connect** to create a session and start streaming your microphone audio.
- Original transcripts appear on the left; translated transcripts on the right.
- The timer at the top shows how long the session has been active.
- Click **Disconnect** to end the session.

## How it works

1. The browser sends a request to the local Express server (`/api/session`).
2. The server proxies the request to `https://startpinch.com/api/beta/session` with your API key and returns a `url` and `token`.
3. The browser connects to the room, publishes your microphone audio, and listens for transcript data messages.
4. Transcripts are displayed in real time, split into original and translated columns.
