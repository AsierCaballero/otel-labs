# Contributing

Thank you for your interest in contributing to the OpenTelemetry DevOps Labs!

## How to contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Make your changes
4. Run the tests: `cd app && pip install -r requirements-dev.txt && pytest tests/ -v`
5. Commit using conventional commit messages
6. Push and open a Pull Request

## Development setup

```bash
cp .env.example .env
docker compose up -d
chmod +x demo.sh && ./demo.sh
```

## Code style

- Python: follow PEP 8
- YAML: 2-space indentation
- Dockerfiles: multi-stage, non-root user

## Reporting issues

Open an issue with the label `bug` or `enhancement` and describe the problem clearly.
