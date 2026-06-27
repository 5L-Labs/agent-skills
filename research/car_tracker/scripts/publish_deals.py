import os
import sys
import json
import argparse
import requests
from dotenv import load_dotenv

# Base coordinate for distance calculation (Yonkers, NY)
YONKERS_LAT = 40.9312
YONKERS_LON = -73.8987

def get_distance(lat2, lon2):
    import math
    if lat2 is None or lon2 is None:
        return float('inf')
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - YONKERS_LAT)
    dlon = math.radians(lon2 - YONKERS_LON)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(YONKERS_LAT)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 1.18

def get_listings_for_trim(make, model, trim, vin_prefix, api_key, project_root):
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    listings = []
    limit = 100
    offset = 0
    
    # Query up to 15 pages to find matches across entire inventory
    if api_key:
        for page in range(15):
            url = f"https://api.visor.vin/v1/listings?make={make}&model={model}&limit={limit}&offset={offset}"
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200:
                    data = r.json().get("data", [])
                    if not data:
                        break
                    listings.extend(data)
                    offset += limit
                else:
                    print(f"[-] Warning: Visor API request failed with status code {r.status_code}", file=sys.stderr)
                    break
            except Exception as e:
                print(f"[-] Warning: Visor API request failed with error: {e}", file=sys.stderr)
                break
                
    # Filter by trim keywords & powertrain
    matching = []
    trim_lower = trim.lower()
    
    if "platinum" in trim_lower or "plat" in trim_lower:
        filter_words = ["plat"]
    elif "limited" in trim_lower or "ltd" in trim_lower:
        filter_words = ["limit"]
    elif "pinnacle" in trim_lower or "pinn" in trim_lower:
        filter_words = ["pinn"]
    elif "350" in trim_lower:
        filter_words = ["350"]
    else:
        trim_words = trim_lower.split()
        filter_words = [w for w in trim_words if w not in ["awd", "4wd", "hybrid", "max"]]
        
    for car in listings:
        car_trim = (car.get("trim") or "").lower()
        car_vin = (car.get("vin") or "").upper()
        price = car.get("price")
        car_type = (car.get("inventory_type", car.get("inventoryType", "used")) or "used").lower()
        
        if price is None or not car_vin:
            continue
            
        # Powertrain matching
        if vin_prefix and len(car_vin) > 9:
            if make.lower() == "toyota" or make.lower() == "lexus":
                if len(vin_prefix) > 4 and car_vin[3:5] != vin_prefix[3:5]:
                    continue
            elif make.lower() == "chrysler":
                if len(vin_prefix) > 5 and car_vin[5] != vin_prefix[5]:
                    continue
                    
        # Condition matching (strictly brand-new)
        if car_type != "new":
            continue
            
        # Match trim keywords
        if any(w in car_trim for w in filter_words):
            lat = car.get("latitude")
            lon = car.get("longitude")
            dist = get_distance(lat, lon)
            car["computed_distance"] = dist
            matching.append(car)
            
    # Also load from saved file if API has fewer matches
    saved_path = os.path.join(project_root, "data", "comprehensive_search_results.json")
    if os.path.exists(saved_path):
        try:
            with open(saved_path, "r") as f:
                saved_data = json.load(f)
                
            # Flatten lists
            for key in saved_data:
                for car in saved_data[key]:
                    car_make = car.get("make", "")
                    car_model = car.get("model", "")
                    car_trim = (car.get("trim") or "").lower()
                    car_vin = (car.get("vin") or "").upper()
                    car_type = (car.get("inventory_type", car.get("inventoryType", "used")) or "used").lower()
                    price = car.get("price")
                    
                    if price is None or car_make.lower() != make.lower() or model.lower() not in car_model.lower():
                        continue
                        
                    # Powertrain matching
                    if vin_prefix and len(car_vin) > 9:
                        if make.lower() == "toyota" or make.lower() == "lexus":
                            if len(vin_prefix) > 4 and car_vin[3:5] != vin_prefix[3:5]:
                                continue
                        elif make.lower() == "chrysler":
                            if len(vin_prefix) > 5 and car_vin[5] != vin_prefix[5]:
                                continue
                                
                    # Condition matching
                    if car_type != "new":
                        continue
                        
                    if any(w in car_trim for w in filter_words):
                        lat = car.get("latitude")
                        lon = car.get("longitude")
                        dist = get_distance(lat, lon)
                        car["computed_distance"] = dist
                        # Prevent duplicate VINs
                        if not any(x.get("vin") == car.get("vin") for x in matching):
                            matching.append(car)
        except Exception as e:
            print(f"[-] Warning: Failed to load comprehensive_search_results.json: {e}", file=sys.stderr)

    # Sort matching by price ascending
    matching.sort(key=lambda x: x.get("price", float('inf')))
    return matching

def load_seen_listings(state_path):
    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_listings(seen_set, state_path):
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    try:
        with open(state_path, "w") as f:
            json.dump(list(seen_set), f, indent=2)
    except Exception as e:
        print(f"[-] Error saving state file: {e}", file=sys.stderr)

def main():
    # Resolve project root dynamically to ensure path portability
    current = os.path.dirname(os.path.abspath(__file__))
    project_root = os.getcwd()
    while current and current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, ".git")) or os.path.exists(os.path.join(current, ".agents")):
            project_root = current
            break
        current = os.path.dirname(current)

    dotenv_path = os.path.join(project_root, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
    else:
        load_dotenv()
        
    api_key = os.getenv("VISOR.VIN_API_KEY") or os.getenv("VISOR_API_KEY")
    if not api_key:
        print("[-] Warning: VISOR_API_KEY environment variable is not set. Visor API live search will be skipped.", file=sys.stderr)
        
    parser = argparse.ArgumentParser(description="Daily Car Tracker - Publishes new and cheapest car deals.")
    parser.add_argument("--trims", type=str, help="Path to JSON config of trims to monitor")
    args = parser.parse_args()
    
    # Load monitored trims
    trims_path = args.trims or os.path.join(project_root, "data", "tracked_trims.json")
    if os.path.exists(trims_path):
        try:
            with open(trims_path, "r") as f:
                monitored_trims = json.load(f)
        except Exception as e:
            print(f"[-] Error loading trims config: {e}. Using defaults.", file=sys.stderr)
            monitored_trims = [
                {"make": "Toyota", "model": "Grand Highlander", "trim": "Hybrid MAX Platinum AWD", "vin_prefix": "5TDAD"},
                {"make": "Chrysler", "model": "Pacifica", "trim": "Pinnacle AWD", "vin_prefix": "2C4RC3"},
                {"make": "Lexus", "model": "TX", "trim": "350 AWD", "vin_prefix": "5TDAA"}
            ]
    else:
        monitored_trims = [
            {"make": "Toyota", "model": "Grand Highlander", "trim": "Hybrid MAX Platinum AWD", "vin_prefix": "5TDAD"},
            {"make": "Chrysler", "model": "Pacifica", "trim": "Pinnacle AWD", "vin_prefix": "2C4RC3"},
            {"make": "Lexus", "model": "TX", "trim": "350 AWD", "vin_prefix": "5TDAA"}
        ]
        
    # State tracking
    state_path = os.path.join(project_root, "data", "seen_listings.json")
    seen_vins = load_seen_listings(state_path)
    new_seen_vins = set(seen_vins)
    
    print("# Daily Car Market Bulletin (New Listings & Cheapest Deals)")
    print(f"*Report generated for Yonkers, NY coordinates. Target distance comparisons sorted by proximity.*")
    
    for target in monitored_trims:
        make = target["make"]
        model = target["model"]
        trim = target["trim"]
        vin_prefix = target.get("vin_prefix")
        
        print(f"\n## 🚙 {make} {model} ({trim})")
        
        # Get listings
        listings = get_listings_for_trim(make, model, trim, vin_prefix, api_key, project_root)
        
        if not listings:
            print("*No active new inventory matching specifications found.*")
            continue
            
        cheapest_price = listings[0]["price"]
        
        # 1. Identify New Arrivals
        new_arrivals = []
        for car in listings:
            vin = car.get("vin")
            if vin not in seen_vins:
                new_arrivals.append(car)
                new_seen_vins.add(vin)
                
        # Print New Arrivals (sorted by distance)
        print("\n### 🆕 New Arrivals in the Last 24 Hours")
        if new_arrivals:
            new_arrivals.sort(key=lambda x: x.get("computed_distance", float('inf')))
            print(f"| {'Dealership (State — Dist)':<35} | {'Price':<7} | {'Delta':<7} | {'VIN':<18} | {'Link':<12} |")
            print(f"| {'-' * 35} | {'-' * 7} | {'-' * 7} | {'-' * 18} | {'-' * 12} |")
            for car in new_arrivals:
                c_price = car.get("price")
                c_dist = car.get("computed_distance", float('inf'))
                c_state = car.get("state", "??")
                c_dealer = car.get("dealer_name") or "Dealer"
                c_dealer_lbl = f"{c_dealer[:22]} ({c_state} — {c_dist:.0f} mi)"
                c_vin = car.get("vin", "")
                delta = c_price - cheapest_price
                c_vdp = car.get("vdp_url") or car.get("vdpUrl") or "#"
                link_str = f"[Dealer Site]({c_vdp})" if c_vdp != "#" else "N/A"
                print(f"| {c_dealer_lbl:<35} | ${c_price:,.0f} | +${delta:,.0f} | {c_vin} | {link_str} |")
        else:
            print("*No new listings appeared on the market since last check.*")
            
        # Print Cheapest Overall Deals (sorted by price)
        print("\n### 🏆 Top 5 Cheapest Active Deals")
        top_cheapest = listings[:5]
        print(f"| {'Dealership (State — Dist)':<35} | {'Price':<7} | {'Delta':<7} | {'VIN':<18} | {'Link':<12} |")
        print(f"| {'-' * 35} | {'-' * 7} | {'-' * 7} | {'-' * 18} | {'-' * 12} |")
        for car in top_cheapest:
            c_price = car.get("price")
            c_dist = car.get("computed_distance", float('inf'))
            c_state = car.get("state", "??")
            c_dealer = car.get("dealer_name") or "Dealer"
            c_dealer_lbl = f"{c_dealer[:22]} ({c_state} — {c_dist:.0f} mi)"
            c_vin = car.get("vin", "")
            delta = c_price - cheapest_price
            c_vdp = car.get("vdp_url") or car.get("vdpUrl") or "#"
            link_str = f"[Dealer Site]({c_vdp})" if c_vdp != "#" else "N/A"
            print(f"| {c_dealer_lbl:<35} | ${c_price:,.0f} | +${delta:,.0f} | {c_vin} | {link_str} |")
        
    # Update global state of seen VINs
    save_seen_listings(new_seen_vins, state_path)

if __name__ == "__main__":
    main()
