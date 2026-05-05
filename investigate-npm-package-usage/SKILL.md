---
name: investigate-npm-package-usage
description: Investigate whether and how npm packages are used in a Python project that integrates Node.js tools via CLI/subprocess
version: 1.0.0
author: Hermes Agent
---

# Investigate NPM Package Usage in Python/Node.js Hybrid Projects

## When to Use This Skill
You're working on a Python project that integrates Node.js tools (like agent-browser, playwright, etc.) via CLI/subprocess communication, and you need to determine:
- Whether specific npm packages are directly imported/used in Python code
- Whether they are merely internal dependencies of the Node.js tools
- Whether they need to be added to Python requirements or are already satisfied via the Node.js toolchain

## Step-by-Step Approach

### 1. Initial Search for Direct References
Search the Python source code for any direct imports or references to the target npm packages:

```bash
# Search for common import patterns in Python/JavaScript/TypeScript files
grep -r "ua-parser\|camoufox\|is-standalone-pwa\|detect-europe" --include="*.py" --include="*.js" --include="*.ts" --exclude-dir=node_modules --exclude-dir=.git .

# Check for various import/require patterns
grep -r "from.*ua-parser\|import.*ua-parser\|require.*ua-parser" --include="*.py" --exclude-dir=node_modules --exclude-dir=.git .
```

### 2. Examine Package.json Files
Check if any package.json files in the project list the target packages as dependencies:

```bash
# Find all package.json files
find . -name "package.json" -not -path "*/node_modules/*" -not -path "*/\.*" | while read pkg; do
    echo "Checking $pkg:"
    grep -E "\"ua-parser-js\"|\"camoufox-js\"|\"is-standalone-pwa\"|\"detect-europe-js\"" "$pkg" || true
done
```

### 3. Analyze the Integration Pattern
Determine how the project integrates with Node.js tools:
- Are Node.js tools used via CLI/subprocess? (e.g., `subprocess.run(["tool", ...])`)
- Are they used via Node.js bridges? (e.g., `pyppeteer`, `playwright`)
- Is there a Python wrapper around Node.js functionality?

### 4. Check the Node.js Tool's Dependencies
If the project uses a specific Node.js tool (like `agent-browser` in this case):

```bash
# Check the tool's package.json
ls -la node_modules/<tool-name>/package.json
cat node_modules/<tool-name>/package.json | grep -A20 "dependencies"

# Check if your target packages are listed there
```

### 5. Trace Transitive Dependencies
Check if the target packages are dependencies of the Node.js tool's dependencies:

```bash
# For each dependency of the NodeJS tool, check its package.json
for dep in $(cat node_modules/<tool-name>/package.json | jq -r '.dependencies | keys[]' 2>/dev/null || echo ""); do
    if [ -f "node_modules/$dep/package.json" ]; then
        echo "Checking $dep:"
        cat node_modules/$dep/package.json | grep -E "\"ua-parser-js\"|\"camoufox-js\"|\"is-standalone-pwa\"|\"detect-europe-js\"" || true
    fi
done
```

### 6. Look for Functional Equivalents in Python
Check if the project uses Python libraries that provide similar functionality:

```bash
# Check requirements.txt, pyproject.toml, etc. for Python UA parsing libraries
grep -i "user.*agent\|ua.*parser\|platform" requirements.txt pyproject.toml setup.py 2>/dev/null || true

# Search for usage of libraries like 'user-agents', 'ua-parser', etc.
grep -r "user.agents\|ua_parser\|platform" --include="*.py" --exclude-dir=node_modules .
```

### 7. Examine How the Node.js Tool is Invoked
Understand the communication pattern to confirm where the functionality resides:

```bash
# Look for subprocess calls to the Node.js tool
grep -r "subprocess\.run\|Popen\|call.*node\|call.*npx" --include="*.py" --exclude-dir=node_modules .

# Check for CLI argument parsing or JSON communication patterns
```

### 8. Determine the Conclusion
Based on your investigation:
- If direct references found in Python code → Package needs to be available in Python environment
- If only found in Node.js tool's dependencies → Satisfied via Node.js toolchain
- If not found anywhere → May be obsolete reference or needed for future functionality

## Key Indicators That Packages Are Node.js-Only Dependencies
- Project uses Node.js tools via CLI/subprocess (not direct Node.js bindings)
- Target packages appear in the Node.js tool's package.json or lockfile
- No direct imports/requires in Python source code
- No usage of Python equivalents of the functionality
- The Node.js tool handles all browser/UA detection internally

## Example Output Format
When documenting your findings:

```
Investigation Results for [package-name]:
----------------------------------------
Direct References in Python Code: [Yes/No]
  - Locations: [if any]
  
Found in package.json: [Yes/No]
  - Files: [if any]
  
Found in Node.js Tool Dependencies: [Yes/No]
  - Tool: [tool-name]
  - Dependency path: [tool] -> [intermediate-dep] -> [target-package] (if transitive)
  
Functional Equivalents in Python: [Yes/No]
  - Libraries: [if any]
  
Conclusion: [Package is only needed as internal dependency of [Node.js-tool] and does not need to be directly available in Python environment]
```

## Validation
To confirm your conclusion:
1. Try removing the package from node_modules and see if the Node.js tool still works
2. Check if the Python integration continues to function correctly
3. Verify that any browser/UA detection features work as expected