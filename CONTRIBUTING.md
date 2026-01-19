# Contributing to Pinch SDK

Thanks for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/pinch-eng/pinch-python-sdk.git
cd pinch-python-sdk
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit with clear messages
6. Push to your fork
7. Open a Pull Request against `main`

## Code Style

- Use type hints
- Follow existing code patterns
- Keep changes focused and minimal

## Releases

Releases are managed by maintainers only. The publish workflow runs automatically when a GitHub Release is created.
