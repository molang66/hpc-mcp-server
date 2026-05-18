from hpc_mcp_server.llama_backend import build_backend


def main() -> None:
    backend = build_backend()
    print(backend.generate("Say hello in one short sentence.", max_new_tokens=32))


if __name__ == "__main__":
    main()
