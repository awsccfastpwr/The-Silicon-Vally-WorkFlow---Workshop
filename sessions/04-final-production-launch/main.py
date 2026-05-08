import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from groq import Groq
from mangum import Mangum
from pydantic import BaseModel
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

load_dotenv()

app = FastAPI()
classifier = SentimentIntensityAnalyzer()
groq_api_key = os.getenv("GROQ_API_KEY") or os.getenv("groq_api")
groq_client = Groq(api_key=groq_api_key) if groq_api_key else None

class Review(BaseModel):
    text: str


def generate_roast(text: str, label: str, score: float) -> str:
    if not groq_client:
        return "Add GROQ_API_KEY (or groq_api) in your environment to enable roast mode."

    try:
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a witty comedian. Give one short, playful roast in 1-2 lines. "
                        "Keep it light, funny, and non-hateful. Avoid profanity, slurs, or bullying."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Text: {text}\n"
                        f"Sentiment label: {label}\n"
                        f"Confidence: {score:.4f}\n"
                        "Now roast the user in a funny but friendly way."
                    ),
                },
            ],
            temperature=1,
            max_completion_tokens=220,
            top_p=1,
            reasoning_effort="medium",
            stream=False,
            stop=None,
        )
        roast = completion.choices[0].message.content or ""
        return roast.strip() or "Your vibe is mysterious enough to confuse both AI and humans."
    except Exception:
        return "Roast engine took a coffee break. Try again in a moment."

@app.post("/predict")
def predict(review: Review):
    sentiment = classifier.polarity_scores(review.text)
    compound = sentiment["compound"]
    label = "POSITIVE" if compound >= 0 else "NEGATIVE"
    score = round(abs(compound), 4)
    roast = generate_roast(review.text, label, score)
    return {"label": label, "score": score, "roast": roast}


@app.get("/", response_class=HTMLResponse)
def home():
        return """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Sentiment Studio</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-1: #0a1f1c;
            --bg-2: #142d3a;
            --accent: #f5b942;
            --accent-2: #51e5a5;
            --text: #f3f7f6;
            --muted: #b4c1be;
            --card: rgba(10, 14, 19, 0.68);
            --border: rgba(255, 255, 255, 0.16);
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            min-height: 100dvh;
            font-family: "Space Grotesk", sans-serif;
            color: var(--text);
            background:
                radial-gradient(circle at 10% 20%, #235447 0%, transparent 35%),
                radial-gradient(circle at 90% 80%, #2f4058 0%, transparent 35%),
                linear-gradient(140deg, var(--bg-1), var(--bg-2));
            display: grid;
            place-items: center;
            padding: 2rem 1rem;
            overflow-x: hidden;
        }

        body::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background-image: radial-gradient(rgba(255,255,255,0.05) 1px, transparent 1px);
            background-size: 3px 3px;
            opacity: 0.08;
        }

        .shell {
            width: min(900px, 100%);
            background: var(--card);
            border: 1px solid var(--border);
            backdrop-filter: blur(14px);
            border-radius: 24px;
            padding: 1.3rem;
            box-shadow: 0 30px 80px rgba(0, 0, 0, 0.35);
            animation: rise 550ms ease-out both;
        }

        .head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 1rem;
        }

        .title {
            margin: 0;
            font-size: clamp(1.8rem, 5vw, 3.1rem);
            letter-spacing: -0.03em;
            line-height: 1;
        }

        .pill {
            font-family: "IBM Plex Mono", monospace;
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 0.3rem 0.7rem;
            color: var(--muted);
            font-size: 0.78rem;
            white-space: nowrap;
        }

        .subtitle {
            margin: 0.2rem 0 1.1rem;
            color: var(--muted);
            max-width: 68ch;
        }

        form {
            display: grid;
            gap: 0.85rem;
        }

        textarea {
            width: 100%;
            min-height: 160px;
            resize: vertical;
            border-radius: 16px;
            border: 1px solid var(--border);
            padding: 1rem;
            font: inherit;
            color: var(--text);
            background: rgba(255, 255, 255, 0.04);
            transition: border-color 160ms ease, transform 160ms ease;
        }

        textarea:focus {
            outline: none;
            border-color: var(--accent-2);
            transform: translateY(-1px);
        }

        .row {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            flex-wrap: wrap;
        }

        button {
            border: 0;
            color: #101010;
            background: linear-gradient(120deg, var(--accent), #fadc97);
            font-family: "Space Grotesk", sans-serif;
            font-size: 1rem;
            font-weight: 700;
            border-radius: 12px;
            padding: 0.74rem 1.1rem;
            cursor: pointer;
            transition: transform 180ms ease, filter 180ms ease;
            will-change: transform;
        }

        button:hover { transform: translateY(-2px); filter: brightness(1.05); }
        button:active { transform: translateY(0); }
        button[disabled] { opacity: 0.6; cursor: not-allowed; }

        .hint {
            font-family: "IBM Plex Mono", monospace;
            color: var(--muted);
            font-size: 0.78rem;
        }

        .result {
            margin-top: 1rem;
            border-radius: 16px;
            border: 1px solid var(--border);
            padding: 1rem;
            background: rgba(255, 255, 255, 0.03);
            opacity: 0;
            transform: translateY(8px);
            transition: opacity 220ms ease, transform 220ms ease;
        }

        .result.show {
            opacity: 1;
            transform: translateY(0);
        }

        .tag {
            display: inline-block;
            border-radius: 999px;
            padding: 0.2rem 0.55rem;
            font-size: 0.78rem;
            font-family: "IBM Plex Mono", monospace;
            border: 1px solid var(--border);
        }

        .score {
            font-size: 2rem;
            margin: 0.35rem 0 0;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .roast {
            margin: 0.7rem 0 0;
            color: #f6e2ba;
            line-height: 1.45;
            font-size: 1rem;
        }

        .error {
            color: #ffb4b4;
            font-family: "IBM Plex Mono", monospace;
            font-size: 0.85rem;
            min-height: 1.2em;
        }

        @keyframes rise {
            from { opacity: 0; transform: translateY(12px) scale(0.99); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }

        @media (max-width: 640px) {
            .shell { padding: 1rem; border-radius: 18px; }
            .head { align-items: flex-start; flex-direction: column; }
            textarea { min-height: 140px; }
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation: none !important;
                transition: none !important;
            }
        }
    </style>
</head>
<body>
    <main class="shell">
        <header class="head">
            <h1 class="title">Sentiment Studio</h1>
            <span class="pill">FastAPI + VADER + Groq</span>
        </header>

        <p class="subtitle">
            Drop any text snippet to classify its sentiment instantly. Ideal for support messages, reviews, and social posts.
        </p>

        <form id="predict-form">
            <textarea id="text" placeholder="Example: This workshop is surprisingly practical and super engaging."></textarea>
            <div class="row">
                <button id="submit" type="submit">Analyze Sentiment</button>
                <span class="hint">POST /predict</span>
            </div>
            <div class="error" id="error"></div>
        </form>

        <section id="result" class="result" aria-live="polite">
            <span id="label" class="tag">-</span>
            <p id="score" class="score">Confidence: -</p>
            <p id="roast" class="roast">Roast: -</p>
        </section>
    </main>

    <script>
        const form = document.getElementById("predict-form");
        const text = document.getElementById("text");
        const submit = document.getElementById("submit");
        const error = document.getElementById("error");
        const result = document.getElementById("result");
        const label = document.getElementById("label");
        const score = document.getElementById("score");
        const roast = document.getElementById("roast");

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            error.textContent = "";

            const value = text.value.trim();
            if (!value) {
                error.textContent = "Please enter some text first.";
                return;
            }

            submit.disabled = true;
            submit.textContent = "Analyzing...";

            try {
                const response = await fetch("/predict", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text: value })
                });

                if (!response.ok) {
                    throw new Error("Request failed with status " + response.status);
                }

                const data = await response.json();
                label.textContent = data.label;
                score.textContent = "Confidence: " + Number(data.score).toFixed(4);
                roast.textContent = "Roast: " + (data.roast || "No roast this round.");
                result.classList.add("show");
            } catch (err) {
                error.textContent = err.message || "Something went wrong while calling /predict.";
            } finally {
                submit.disabled = false;
                submit.textContent = "Analyze Sentiment";
            }
        });
    </script>
</body>
</html>
"""

@app.get("/health")
def health():
    return {"status": "ok"}


handler = Mangum(app)