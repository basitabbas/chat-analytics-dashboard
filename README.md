# Chat Analytics Dashboard

Production-ready Flask API + dashboard for deployment on Render (API) and Netlify (frontend).

## Architecture
Frontend (Netlify) -> Flask API (Render) -> SQL Server

## Run locally
1. Create .env from .env.example
2. Install deps: pip install -r requirements.txt
3. Start API: python app_v2.py

## Deploy
- Push repo to GitHub
- Create Render Blueprint from ender.yaml
- Add required env vars in Render
- Deploy frontend to Netlify and point API URL to Render