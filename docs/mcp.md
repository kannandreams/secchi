# MCP and coding agents

Secchi includes a read-only Model Context Protocol server for coding agents and
MCP-compatible desktop clients. It exposes the same intelligence services used
by the CLI, dashboard, and reports.

## Start the server

After installing Secchi:

```bash
secchi mcp
# or
secchi-mcp
```

From a source checkout:

```bash
uv run secchi-mcp
```

## Client configuration

Add Secchi as a local stdio server in the MCP client configuration:

```json
{
  "mcpServers": {
    "secchi": {
      "command": "secchi-mcp"
    }
  }
}
```

From a source checkout, use the project path:

```json
{
  "mcpServers": {
    "secchi": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/secchi",
        "secchi-mcp"
      ]
    }
  }
}
```

## Available tools

| Tool | Purpose |
| --- | --- |
| `inspect_package` | Inspect health, adoption, releases, dependencies, and repository signals |
| `search_packages` | Search supported ecosystems and return ranked matches |
| `inspect_project` | Read a configured project and combine its package sources |
| `check_package` | Evaluate health and repository CI policies |
| `compare_packages` | Rank package choices with evidence and confidence |

The server is read-only. It does not install, upgrade, remove, or approve
dependencies. Optional signal failures are returned as warnings instead of
silently being represented as zero-valued data.

## Agent decision support

Agents can use `compare_packages` when selecting between dependencies. The
result is advisory and includes the recommendation basis, evidence, confidence,
and missing signals. Agents should still apply project-specific requirements,
license policy, compatibility constraints, and human review.
