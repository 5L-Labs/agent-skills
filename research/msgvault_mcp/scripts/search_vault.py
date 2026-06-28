import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import ssl

def call_mcp_tool(url, password, tool_name, arguments):
    # Disable SSL verification since some local servers use self-signed certificates
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    headers = {
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-06-18",
        "User-Agent": "MsgVault-MCP-Client-Python"
    }
    if password:
        # Basic auth format or bearer token
        import base64
        if password.startswith("Bearer "):
            headers["Authorization"] = password
        else:
            auth_str = f"njl:{password}"
            headers["Authorization"] = "Basic " + base64.b64encode(auth_str.encode()).decode()
            
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    # Initialize session
    init_payload = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "msgvault-cli", "version": "1.0"}
        }
    }
    
    try:
        # Initialize
        req = urllib.request.Request(url, data=json.dumps(init_payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            sid = r.headers.get("Mcp-Session-Id")
            
        # Call tool
        if sid:
            headers["Mcp-Session-Id"] = sid
            
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            body = r.read().decode()
            
            if "data:" in body:
                data_lines = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]
                body = "\n".join(data_lines)
                
            res = json.loads(body)
            if "error" in res:
                print(f"[-] MCP Error: {res['error']}", file=sys.stderr)
                sys.exit(1)
            return res.get("result", {})
            
    except urllib.error.HTTPError as e:
        print(f"[-] HTTP Error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[-] Connection Error: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Search emails in MsgVault via MCP.")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--limit", type=int, default=5, help="Max results")
    
    args = parser.parse_args()
    
    # Load .env locally if present
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    env_path = os.path.join(project_root, ".env")
    if os.path.exists(env_path):
        from dotenv import load_dotenv
        load_dotenv(env_path)
        
    url = os.getenv("MSGVAULT_URL") or "https://lunarbeacon.newyork.nicklange.family:9443/mcp"
    password = os.getenv("MSGVAULT_PASSWORD")
    
    if not password:
        print("[-] Error: MSGVAULT_PASSWORD must be defined in environment or .env file.", file=sys.stderr)
        sys.exit(1)
        
    print(f"[+] Searching MsgVault for query '{args.query}'...")
    result = call_mcp_tool(url, password, "search_messages", {"query": args.query, "limit": args.limit})
    
    content = result.get("content", [])
    if content:
        text_data = content[0].get("text", "[]")
        try:
            messages = json.loads(text_data)
            if messages is None:
                messages = []
            print(f"[+] Found {len(messages)} messages:")
            for m in messages:
                print(f"\n- From: {m.get('from_email', m.get('from', ''))}")
                print(f"  Subject: {m.get('subject', '')}")
                print(f"  Snippet: {m.get('snippet', '')}")
        except Exception as e:
            print(f"[-] Failed to parse message JSON: {e}")
            print(text_data)
    else:
        print("[-] No content returned from MsgVault.")

if __name__ == "__main__":
    main()
