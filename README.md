# Plan B Guardian Railway Refactor

Files:
- main.py -> bot entry point
- config.py -> constants/config
- state.py -> runtime state and Discord/OpenAI clients
- helpers.py -> utility helpers and embed builders
- ai_features.py -> AI chat/bouncer/analyze helpers
- moderation.py -> moderation, jail, spam, targeted harassment logic
- console.py -> console panel UI
- requirements.txt -> Python deps
- Dockerfile -> Railway deploy

Local run:
1. Create `.env` from `.env.example`
2. Install deps: `pip install -r requirements.txt`
3. Run: `python main.py`

Railway:
1. Push this whole folder to GitHub
2. Deploy repo on Railway
3. Add `TOKEN` and `OPENAI_API_KEY`
4. Redeploy
Test deploy check
