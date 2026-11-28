"""Service layer shared by FastAPI, the MCP server, and collectors.

Services take a `Session`, validate business rules, and `flush()`; the caller owns
the transaction and decides when to commit.
"""
