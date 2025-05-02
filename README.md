# 🖼️ AI Thumbnail Generator

Generate professional YouTube thumbnails from sketches and text prompts using OpenAI's DALL·E, with user authentication, Stripe subscriptions, and Supabase-powered backend.

## 🔥 Features

- 🎨 Draw rough sketches on a canvas
- ✍️ Add prompts to guide thumbnail generation
- 🤖 AI-powered image generation (DALL·E 3 via OpenAI)
- 🔐 User authentication via Supabase Auth
- 💳 Subscription plans using Stripe Checkout
- 📈 Usage-based access control (Starter, Growth, Scale plans)
- 🌐 Fully responsive web UI built with Bootstrap
- 📁 Auto-tracking of generated thumbnails per user
- ⚙️ Subscription management & cancellation via Stripe Portal

## 🚀 Tech Stack

- **Frontend**: HTML, JavaScript, Bootstrap
- **Backend**: Python, Flask, Gunicorn
- **AI**: OpenAI DALL·E 3
- **Database/Auth**: Supabase (PostgreSQL)
- **Payments**: Stripe (Subscriptions & Webhooks)
- **Deployment**: Heroku + Custom Domain via Namecheap

## 🧠 How It Works

1. User logs in or signs up using Supabase.
2. Sketch something or upload a reference image.
3. Add a creative prompt to guide the AI.
4. AI generates 5 thumbnail variations.
5. Users on free tier get 3 thumbnails/month. Upgrade to generate more.
6. Stripe handles billing. Webhooks update subscription status in Supabase.

