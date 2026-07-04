from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("zendesk-ops")


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
