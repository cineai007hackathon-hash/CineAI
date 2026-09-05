# Agentic Hackathon

A Google Agent Development Kit (ADK) project containing a weather and time assistant agent.

The agent can:

- Return a sample weather report for New York
- Return the current time in New York
- Explain when information is unavailable for another city

## Requirements

- Python 3.13 or newer
- [`uv`](https://docs.astral.sh/uv/)
- A Google Gemini API key, unless your environment is configured to use another supported model provider

## Project structure

```text
.
├── ad_multi_agent/
│   ├── agent.py       # Root agent and tool definitions
│   ├── __init__.py
│   └── .env           # Local environment variables; do not commit secrets
├── pyproject.toml
├── uv.lock
└── README.md
```

`ad_multi_agent` intentionally uses underscores. ADK uses the directory name as the app name, and app names must be valid Python identifiers. Renaming it to `ad-multi-agent` causes requests such as `/run_sse` to return `404`.

## Setup

From the project root:

```bash
uv sync
```

Configure credentials in your shell or in `ad_multi_agent/.env`:

```bash
export GOOGLE_API_KEY="your-api-key"
```

Keep API keys out of source control. The local `.env` file should not be committed.

## Run the ADK web interface

To serve all agents beneath the project root:

```bash
uv run adk web .
```

To serve only this agent:

```bash
uv run adk web ad_multi_agent
```

Open the URL printed by ADK, select `ad_multi_agent`, and enter a prompt such as:

```text
What is the weather in New York?
What time is it in New York?
```

If the browser shows an old blank page after changing the app directory, stop any previous ADK server, restart it, and hard-refresh the browser.

## Run the agent from Python

The root agent is available as `ad_multi_agent.agent.root_agent`:

```python
from ad_multi_agent.agent import root_agent
```

For local interactive use, the ADK web server is recommended because it provides session handling, streaming responses, and the development UI.

## Tools

`ad_multi_agent/agent.py` defines two tools:

- `get_weather(city)`: returns a sample report for New York and an unavailable response for other cities
- `get_current_time(city)`: returns the current time for New York using the `America/New_York` timezone

## Troubleshooting

### `/run_sse` returns `404`

Make sure the app directory is named `ad_multi_agent`, not `ad-multi-agent`. Restart the server after renaming it:

```bash
uv run adk web ad_multi_agent
```

### The agent does not respond

Check that:

1. The ADK process is still running.
2. The browser is connected to the same host and port shown in the terminal.
3. `GOOGLE_API_KEY` is set and valid.
4. The selected app is `ad_multi_agent`.

## License

The agent source includes the Apache License 2.0 header from the original Google ADK sample.

