---
name: nhtsa_lookup
description: Decodes any vehicle VIN using the public NHTSA API to extract year, make, model, trim, and drivetrain specifications.
version: 1.0.0
author: Antigravity Agent
license: MIT
---

# NHTSA VIN Lookup Skill

This skill allows you to decode any standard 17-character vehicle Identification Number (VIN) using the public National Highway Traffic Safety Administration (NHTSA) VPIC API. Use this tool as a fallback to verify vehicle specifications when a VIN is not listed in active sales feeds.

## How to Run

Execute the decoder script passing the VIN as the first argument:

```bash
python .agents/skills/nhtsa_lookup/scripts/decode_vin.py <17-CHAR-VIN>
```

### Example
```bash
python .agents/skills/nhtsa_lookup/scripts/decode_vin.py 5TDESKFC1TS29K272
```
