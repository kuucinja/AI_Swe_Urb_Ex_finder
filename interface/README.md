# Urbex AI Agent Frontend

## Run

```bash
cd frontend
npm install
npm run dev
```

## Build

```bash
npm run build
```

## API

The chat service calls `POST /api/chat` and falls back to a local mock agent when the API is unavailable.

Set `VITE_AGENT_MODE=api` if you want to force the network call and use a real backend.

## Folder Layout

- `src/interface` holds the React UI.
- `../retrieval/data_locations` holds data, state, and shared types.
- `src/agentic-tools` holds the agent service layer and mock response logic.
