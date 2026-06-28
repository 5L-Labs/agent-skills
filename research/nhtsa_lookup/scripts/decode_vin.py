import sys
import json
import requests

def decode_vin(vin):
    vin = vin.strip().upper()
    if len(vin) != 17:
        print(f"[-] Error: VIN must be exactly 17 characters long. Got '{vin}' ({len(vin)} chars).", file=sys.stderr)
        sys.exit(1)
        
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevinvalues/{vin}?format=json"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            res = r.json().get("Results", [])[0]
            err_code = res.get("ErrorCode", "0")
            err_text = res.get("ErrorText", "")
            
            # If there is a warning or error, print it to stderr but do not crash
            if err_code != "0":
                print(f"[!] NHTSA Warning ({err_code}): {err_text}", file=sys.stderr)
                
            return res
        else:
            print(f"[-] Request failed with status code {r.status_code}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"[-] Connection error: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python decode_vin.py <17-character VIN>", file=sys.stderr)
        sys.exit(1)
        
    vin = sys.argv[1]
    data = decode_vin(vin)
    
    fields = {
        "Model Year": "ModelYear",
        "Make": "Make",
        "Model": "Model",
        "Trim / Grade": "Trim",
        "Body Class": "BodyClass",
        "Drive Type (Drivetrain)": "DriveType",
        "Engine HP": "EngineHP",
        "Primary Fuel Type": "FuelTypePrimary",
        "Plant City": "PlantCity",
        "Plant State": "PlantState",
        "Plant Country": "PlantCountry"
    }
    
    print(f"\n### 🛡️ NHTSA VIN Decode Results: {vin}")
    print("| Parameter | Value |")
    print("| --- | --- |")
    for label, key in fields.items():
        val = data.get(key)
        val_str = val if val and val.strip() else "N/A"
        print(f"| **{label}** | {val_str} |")

if __name__ == "__main__":
    main()
