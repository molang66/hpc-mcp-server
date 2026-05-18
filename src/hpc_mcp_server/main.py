from contextlib import asynccontextmanager
import os
import subprocess
from threading import Lock

from fastapi import FastAPI, HTTPException
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from hpc_mcp_server.api.health import router as health_router
from hpc_mcp_server.llama_backend import LLMBackend, build_backend

SERVICE_NAME = "hpc-mcp-server"
GPU_MODEL_SCRIPT = os.environ.get(
    "GPU_MODEL_SCRIPT",
    "/work2/09250/molang66/stampede3/GPUModeling25/3D_parallelism_prediction/3D_prediction.py",
)

mcp = FastMCP("ExecutionAwareLLM")
_backend: LLMBackend | None = None
_backend_lock = Lock()


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_new_tokens: int = Field(300, ge=1, le=2048)


class ChatResponse(BaseModel):
    response: str


class ServiceInfo(BaseModel):
    service: str
    endpoints: dict[str, str]
    model_id: str
    llm_backend: str


def get_backend() -> LLMBackend:
    global _backend
    if _backend is None:
        with _backend_lock:
            if _backend is None:
                _backend = build_backend()
    return _backend


def run_gpu_model() -> str:
    result = subprocess.run(
        ["python", GPU_MODEL_SCRIPT],
        capture_output=True,
        text=True,
        timeout=int(os.environ.get("GPU_MODEL_TIMEOUT_SECONDS", "300")),
        check=False,
    )

    if result.returncode != 0:
        return f"GPU modeling failed with exit code {result.returncode}\n{result.stderr}"

    return result.stdout


def should_run_gpu_model(prompt: str) -> bool:
    lower_prompt = prompt.lower()

    trigger_keywords = [
        "training time",
        "gpu time",
        "predict gpu",
        "performance estimation",
        "parallelism modeling",
        "3d parallelism",
        "gpu modeling",
    ]

    return any(keyword in lower_prompt for keyword in trigger_keywords)


def generate_chat_response(prompt: str, max_new_tokens: int = 300) -> str:
    if should_run_gpu_model(prompt):
        tool_output = run_gpu_model()
        return f"=== GPU Modeling Result ===\n\n{tool_output}"

    return get_backend().generate(prompt, max_new_tokens=max_new_tokens)


@mcp.tool()
def chat(prompt: str) -> str:
    """Main entry tool. Deterministic rule decides whether to call GPU modeling."""
    return generate_chat_response(prompt)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)
app.include_router(health_router)


@app.get("/", response_model=ServiceInfo)
def service_info() -> ServiceInfo:
    return ServiceInfo(
        service=SERVICE_NAME,
        endpoints={
            "health": "GET /health",
            "chat": "POST /chat",
            "mcp": "/mcp",
        },
        model_id=os.environ.get("MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct"),
        llm_backend=os.environ.get("LLM_BACKEND", "deepspeed"),
    )


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    try:
        return ChatResponse(
            response=generate_chat_response(
                request.prompt,
                max_new_tokens=request.max_new_tokens,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


app.mount("/mcp", mcp.streamable_http_app())


def run() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    run()
