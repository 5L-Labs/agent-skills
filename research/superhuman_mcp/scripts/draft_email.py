import os
import sys
import json
import argparse
import urllib.request
import urllib.error

def call_mcp_tool(url, auth, tool_name, arguments):
    headers = {
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-06-18",
        "User-Agent": "Superhuman-MCP-Client-Python"
    }
    if auth:
        headers["Authorization"] = auth if auth.startswith("Bearer ") else f"Bearer {auth}"
        
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    # We must first initialize the SSE/HTTP session
    init_payload = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "superhuman-cli", "version": "1.0"}
        }
    }
    
    try:
        # Initialize
        req = urllib.request.Request(url, data=json.dumps(init_payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            sid = r.headers.get("Mcp-Session-Id")
            
        # Call tool
        if sid:
            headers["Mcp-Session-Id"] = sid
            
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode()
            
            # SSE framing cleanup if present
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
    parser = argparse.ArgumentParser(description="Create or update an email draft via Superhuman Mail MCP.")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--subject", help="Subject line")
    parser.add_argument("--body", help="HTML body content (direct write)")
    parser.add_argument("--instructions", help="AI instructions for the email draft")
    
    args = parser.parse_args()
    
    # Load .env locally if present
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    env_path = os.path.join(project_root, ".env")
    if os.path.exists(env_path):
        from dotenv import load_dotenv
        load_dotenv(env_path)
        
    url = os.getenv("SUPERHUMAN_URL")
    auth = os.getenv("SUPERHUMAN_AUTH")
    
    if not url:
        print("[-] Error: SUPERHUMAN_URL must be defined in environment or .env file.", file=sys.stderr)
        sys.exit(1)
        
    tool_args = {
        "type": "new",
        "to": [args.to]
    }
    if args.subject:
        tool_args["subject"] = args.subject
    if args.body:
        tool_args["body"] = args.body
    if args.instructions:
        tool_args["instructions"] = args.instructions
        
    if not args.body and not args.instructions:
        print("[-] Error: Either --body or --instructions must be provided.", file=sys.stderr)
        sys.exit(1)
        
    print(f"[+] Creating email draft to '{args.to}' via Superhuman MCP...")
    result = call_mcp_tool(url, auth, "create_or_update_draft", tool_args)
    print("[+] Successfully created draft!")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
