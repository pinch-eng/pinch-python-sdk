const path = require("path");
const express = require("express");
require("dotenv").config({ path: path.resolve(__dirname, "../../.env") });

const app = express();
const PORT = process.env.PORT || 3000;
const PINCH_API_KEY = process.env.PINCH_API_KEY;

if (!PINCH_API_KEY) {
  console.error("ERROR: PINCH_API_KEY is not set.");
  console.error("Create a .env file in the project root with: PINCH_API_KEY=your_key_here");
  process.exit(1);
}

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

app.post("/api/session", async (req, res) => {
  try {
    const response = await fetch("https://api.startpinch.com/api/beta1/session", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${PINCH_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        sourceLanguage: "en-US",
        targetLanguage: "es-ES",
        voiceType: "clone",
      }),
    });

    if (!response.ok) {
      const text = await response.text();
      console.error(`Pinch API error: ${response.status} ${text}`);
      return res.status(response.status).json({ error: text });
    }

    const data = await response.json();

    // Log token TTL so we can see when it expires
    if (data.token) {
      try {
        const payload = JSON.parse(Buffer.from(data.token.split(".")[1], "base64url").toString());
        const now = Math.floor(Date.now() / 1000);
        console.log(`Session created - token expires in ${payload.exp - now}s (TTL: ${payload.exp - payload.iat}s)`);
      } catch {}
    }

    res.json(data);
  } catch (err) {
    console.error("Session creation failed:", err.message);
    res.status(500).json({ error: "Failed to create session" });
  }
});

app.listen(PORT, () => {
  console.log(`Pinch Real-Time Demo running at http://localhost:${PORT}`);
});