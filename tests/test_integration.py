import pytest
from zendesk_ops_mcp.zendesk_client import ZendeskClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connectivity():
    client = ZendeskClient()
    try:
        data = await client.get("/api/v2/users/me.json")
        assert "user" in data
    finally:
        await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_groups():
    client = ZendeskClient()
    try:
        data = await client.get("/api/v2/groups.json")
        assert "groups" in data
    finally:
        await client.close()
