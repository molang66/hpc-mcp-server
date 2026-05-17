# Deploy to Tapis Pods

This service exposes:

- `GET /health` for ICICLE/Tapis rollout checks.
- `GET /` for service metadata.
- `POST /chat` for direct HTTP question answering.
- `/mcp` for Streamable HTTP MCP clients.

## Local validation first

Run local checks in layers. The health check does not load Llama, so it is the
fastest way to verify the service package and HTTP entrypoint.

```bash
cd All_in_all_LLM
uv sync
uv run uvicorn all_in_all_llm.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl http://127.0.0.1:8000/health
```

Only test real Llama generation locally if the machine has a CUDA GPU and enough
memory. Set `MODEL_ID` to either the Hugging Face model id or a local model path:

```bash
export MODEL_ID=/models/Llama-3.1-8B-Instruct
export HF_TOKEN=your_huggingface_token
export LLM_BACKEND=deepspeed
export HF_LOCAL_FILES_ONLY=false
export TENSOR_PARALLEL_SIZE=1
uv run uvicorn all_in_all_llm.main:app --host 127.0.0.1 --port 8000
```

The first MCP `chat` call will load the model.

For direct chat:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is HPC in one sentence?","max_new_tokens":80}'
```

## 1. Fill deployment identity

Edit `icicle-service.yaml`:

```yaml
project-name: all-in-all-llm
pod-name: allinallllm
```

`pod-name` must be lowercase alphanumeric for Tapis Pods.
If your ICICLE project/team name is different, update `project-name` before
committing.

## 2. Create the lockfile

ICICLE Python builds require `uv.lock`.

```bash
cd All_in_all_LLM
uv lock
```

Commit `uv.lock`.

## 3. Configure secrets and environment

Add this GitHub repository secret:

```text
TAPIS_TOKEN
```

The running Pod also needs access to the Llama model. Configure these as pod
environment variables or Tapis secrets:

```text
HF_TOKEN=your_huggingface_token
LLM_BACKEND=deepspeed
MODEL_ID=meta-llama/Llama-3.1-8B-Instruct
HF_LOCAL_FILES_ONLY=false
TENSOR_PARALLEL_SIZE=1
```

Alternatively, pre-download the model to a persistent path that is mounted inside
the Pod, then point `MODEL_ID` at that local directory:

```text
MODEL_ID=/models/Llama-3.1-8B-Instruct
LLM_BACKEND=deepspeed
HF_LOCAL_FILES_ONLY=true
```

The local directory must contain the Hugging Face model files, for example
`config.json`, tokenizer files, and model weight shards.

If the GPU modeling script is mounted at a different path inside the Pod, set:

```text
GPU_MODEL_SCRIPT=/path/inside/pod/3D_prediction.py
```

## 4. Push and deploy

```bash
git add .github/ icicle-service.yaml pyproject.toml uv.lock entrypoint.sh .dockerignore src/ DEPLOY_TAPIS.md
git commit -m "Deploy all-in-all LLM as ICICLE service"
git push
```

Watch the GitHub Actions deploy job. When it finishes, wait for the Tapis Pod
to roll out.

## 5. Verify

```bash
curl https://<pod-name>.pods.tacc.tapis.io/health
```

Expected:

```json
{
  "status": "ok",
  "service": "all-in-all-llm",
  "version": "0.1.0"
}
```

Then connect an MCP Streamable HTTP client to:

```text
https://<pod-name>.pods.tacc.tapis.io/mcp
```

For direct HTTP chat testing:

```bash
curl -X POST https://<pod-name>.pods.tacc.tapis.io/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is HPC in one sentence?","max_new_tokens":80}'
```

## Notes for Llama

This service loads Llama lazily on the first `chat` tool call, not during
`/health`. That makes rollout checks fast, but the first real chat request can
take a while because the model may download and initialize.

The Pod must have a GPU/CUDA-compatible runtime and enough memory for the model.
If startup or first chat fails, check the Tapis Pod logs first.

## Pre-download the Llama model

Prefer storing model weights on a persistent Tapis volume, shared work path, or
other mounted storage. Avoid baking the full model into the application image
unless the platform team explicitly recommends it; images become very large and
slow to build/pull.

For a first Tapis deployment, create or attach a persistent volume mounted at
`/models`, then set:

```text
MODEL_ID=/models/Llama-3.1-8B-Instruct
HF_HOME=/models/.cache/huggingface
```

On a machine or job that has access to the target storage and your Hugging Face
token:

```bash
huggingface-cli login
huggingface-cli download meta-llama/Llama-3.1-8B-Instruct \
  --local-dir /models/Llama-3.1-8B-Instruct \
  --local-dir-use-symlinks False
```

Then configure the Pod:

```text
MODEL_ID=/models/Llama-3.1-8B-Instruct
LLM_BACKEND=deepspeed
HF_HOME=/models/.cache/huggingface
HF_LOCAL_FILES_ONLY=true
```

`HF_TOKEN` may still be useful for gated model validation, but the service will
load from `MODEL_ID` locally when that path exists inside the Pod.

If the Tapis image is CUDA-friendly but not DeepSpeed-friendly, try:

```text
LLM_BACKEND=transformers
DEVICE_MAP=auto
```
