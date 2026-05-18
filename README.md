# HPC MCP Server

Execution-aware LLM MCP server packaged as an ICICLE/Tapis Python service.

Endpoints:

- `GET /health`
- `GET /`
- `POST /chat`
- `/mcp`

See `DEPLOY_TAPIS.md` for deployment and local validation steps.

Direct chat test:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is HPC in one sentence?","max_new_tokens":80}'
```
