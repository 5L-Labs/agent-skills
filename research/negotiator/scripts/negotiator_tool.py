import os
import sys
import json
import argparse
import requests
from dotenv import load_dotenv

# Yonkers NY tax & doc fee config
TAX_RATE = 0.0838
DOC_FEES = 325.00

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

def calculate_otd(price):
    return price * (1 + TAX_RATE) + DOC_FEES

def decode_vin_prefix(vin):
    vin = vin.upper()
    if vin.startswith("2C4RC"):
        return "Chrysler", "Pacifica", "Pinnacle AWD"
    elif vin.startswith("5TDAC"):
        return "Toyota", "Grand Highlander", "Hybrid Limited AWD"
    elif vin.startswith("5TDAD"):
        return "Toyota", "Grand Highlander", "Hybrid MAX Platinum AWD"
    elif vin.startswith("5TDAA"):
        return "Lexus", "TX", "350 AWD"
    return None, None, None

def calculate_shipping(dist):
    if dist <= 150:
        return 0.0
    return 1200.0

def calculate_travel(dist):
    if dist <= 150:
        return 50.0
    return 500.0

def get_cheapest_national(make, model, trim, api_key, target_vin=None):
    # Query Visor API live for matching trim
    headers = {"Authorization": f"Bearer {api_key}"}
    listings = []
    limit = 100
    offset = 0
    
    # Query up to 15 pages to find matches across entire inventory
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
                break
        except Exception:
            break
            
    # Determine target powertrain and inventory type from target VIN
    target_powertrain = None
    target_inventory_type = "new"  # default
    
    if target_vin:
        target_vin = target_vin.upper()
        if len(target_vin) > 9:
            # Powertrain coding
            if make.lower() == "toyota" or make.lower() == "lexus":
                target_powertrain = target_vin[3:5]  # AD, AC, AA
            elif make.lower() == "chrysler":
                target_powertrain = target_vin[5]  # 3, 1
            
            # Inventory type is strictly new as we are only comparing new cars
            target_inventory_type = "new"
            
    # Filter by trim keywords
    matching = []
    trim_lower = trim.lower()
    
    # Define primary trim identifier for robust matching
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
        
        if price is None:
            continue
            
        # Powertrain matching
        if target_powertrain and len(car_vin) > 9:
            if make.lower() == "toyota" or make.lower() == "lexus":
                if car_vin[3:5] != target_powertrain:
                    continue
            elif make.lower() == "chrysler":
                if car_vin[5] != target_powertrain:
                    continue
                    
        # Condition matching
        if car_type != target_inventory_type:
            continue
            
        # Match trim keywords
        if any(w in car_trim for w in filter_words):
            lat = car.get("latitude")
            lon = car.get("longitude")
            dist = get_distance(lat, lon)
            car["computed_distance"] = dist
            matching.append(car)
            
    # Also load from saved file if API has fewer matches
    saved_path = "/Users/njl/dev/src/mkai/car_buying/data/comprehensive_search_results.json"
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
                    if target_powertrain and len(car_vin) > 9:
                        if make.lower() == "toyota" or make.lower() == "lexus":
                            if car_vin[3:5] != target_powertrain:
                                continue
                        elif make.lower() == "chrysler":
                            if car_vin[5] != target_powertrain:
                                continue
                                
                    # Condition matching
                    if car_type != target_inventory_type:
                        continue
                        
                    if any(w in car_trim for w in filter_words):
                        lat = car.get("latitude")
                        lon = car.get("longitude")
                        dist = get_distance(lat, lon)
                        car["computed_distance"] = dist
                        # Prevent duplicate VINs
                        if not any(x.get("vin") == car.get("vin") for x in matching):
                            matching.append(car)
        except Exception:
            pass

    # Sort matching by price
    matching.sort(key=lambda x: x.get("price", float('inf')))
    
    cheapest_nationwide = matching[0] if matching else None
    
    # Filter for regional (<= 250 miles)
    regional_matches = [c for c in matching if c.get("computed_distance", float('inf')) <= 250.0]
    cheapest_regional = regional_matches[0] if regional_matches else None
    
    return cheapest_regional, cheapest_nationwide, matching[:10]

def main():
    load_dotenv("/Users/njl/dev/src/mkai/car_buying/.env")
    api_key = os.getenv("VISOR.VIN_API_KEY") or os.getenv("VISOR_API_KEY")
    
    parser = argparse.ArgumentParser(description="Negotiator Tool - Calculates OTD spreads and bids.")
    parser.add_argument("--vin", type=str, help="VIN of the target vehicle")
    parser.add_argument("--make", type=str, help="Make of the vehicle (if VIN not supplied/known)")
    parser.add_argument("--model", type=str, help="Model of the vehicle")
    parser.add_argument("--trim", type=str, help="Trim level of the vehicle")
    parser.add_argument("--price", type=float, required=True, help="Dealership quoted price")
    
    args = parser.parse_args()
    
    make, model, trim = args.make, args.model, args.trim
    vin = args.vin
    
    if vin:
        v_make, v_model, v_trim = decode_vin_prefix(vin)
        if v_make:
            make, model, trim = v_make, v_model, v_trim
            
    if not make or not model:
        print("[-] Error: Make and Model could not be resolved. Please supply --make and --model.")
        sys.exit(1)
        
    trim = trim or ""
    
    # 1. Quoted VIN details
    quoted_price = args.price
    quoted_otd = calculate_otd(quoted_price)
    
    # 2. Get cheapest comparable model in the database/market
    cheapest_regional, cheapest_nationwide, top_listings = get_cheapest_national(make, model, trim, api_key, target_vin=vin)
    
    # Regional math
    if cheapest_regional:
        reg_price = cheapest_regional["price"]
        reg_otd = calculate_otd(reg_price)
        reg_lbl = f"Cheapest Regional ({cheapest_regional.get('state', 'PA')} — {cheapest_regional['computed_distance']:.0f} mi)"
    else:
        # Fallback if no regional found (Est. 5% discount)
        reg_price = quoted_price * 0.95
        reg_otd = calculate_otd(reg_price)
        reg_lbl = "Cheapest Regional (Est. 5% Disc)"
        
    # Nationwide math
    if cheapest_nationwide:
        nat_price = cheapest_nationwide["price"]
        nat_otd = calculate_otd(nat_price)
        nat_lbl = f"Cheapest Nation ({cheapest_nationwide.get('state', 'UT')} — {cheapest_nationwide['computed_distance']:.0f} mi)"
    else:
        # Fallback if no nationwide found
        nat_price = quoted_price * 0.95
        nat_otd = calculate_otd(nat_price)
        nat_lbl = "Cheapest Nation (Est. 5% Disc)"
        
    # 3. Load baseline target prices for Pacifica, Grand Highlander, Lexus
    # Baselines are our 3 selected target vehicles
    baselines = [
        {"name": "Pacifica (SC New 2026)", "price": 54499.00},
        {"name": "G. Highlander (PA New 2026)", "price": 53396.00},
        {"name": "Lexus TX 350 (New 2026)", "price": 58000.00}
    ]
    
    # --- TABLE 1: CURRENT VS BENCHMARKS ---
    print("\n### Table 1: Quote vs. Benchmarks (New Only)")
    print("```")
    print(f"{'Target Vehicle':<32} | {'Price':<8} | {'OTD Price':<9} | {'Room':<7}")
    print("-" * 65)
    print(f"{'Quoted ' + make + ' ' + model:<32} | ${quoted_price:,.0f} | ${quoted_otd:,.0f} | --")
    print(f"{reg_lbl:<32} | ${reg_price:,.0f} | ${reg_otd:,.0f} | ${quoted_otd - reg_otd:,.0f}")
    print(f"{nat_lbl:<32} | ${nat_price:,.0f} | ${nat_otd:,.0f} | ${quoted_otd - nat_otd:,.0f}")
    
    for b in baselines:
        b_otd = calculate_otd(b["price"])
        room = quoted_otd - b_otd
        print(f"{b['name']:<32} | ${b['price']:,.0f} | ${b_otd:,.0f} | ${room:,.0f}")
    print("```")
    
    # --- TABLE 2: NEGOTIATION BID TIER TARGETS ---
    # Regional bids
    reg_midpoint = reg_price + 0.5 * (quoted_price - reg_price)
    reg_mid_otd = calculate_otd(reg_midpoint)
    reg_agg = reg_price * 0.90
    reg_agg_otd = calculate_otd(reg_agg)
    
    # Nationwide bids
    nat_midpoint = nat_price + 0.5 * (quoted_price - nat_price)
    nat_mid_otd = calculate_otd(nat_midpoint)
    nat_agg = nat_price * 0.90
    nat_agg_otd = calculate_otd(nat_agg)
    
    print("\n### Table 2: Negotiation Bid Targets (New Only)")
    print("\n**Regional Negotiation Bids (Drivable Range)**")
    print("```")
    print(f"{'Bid Tier Target':<24} | {'Price':<8} | {'OTD Price':<9} | {'Savings':<8}")
    print("-" * 57)
    print(f"{'Quoted Price (Base)':<24} | ${quoted_price:,.0f} | ${quoted_otd:,.0f} | $0")
    print(f"{'Midpoint (50% Spread)':<24} | ${reg_midpoint:,.0f} | ${reg_mid_otd:,.0f} | ${quoted_otd - reg_mid_otd:,.0f}")
    print(f"{'Cheapest Regional (100%)':<24} | ${reg_price:,.0f} | ${reg_otd:,.0f} | ${quoted_otd - reg_otd:,.0f}")
    print(f"{'Aggressive (-10% Reg)':<24} | ${reg_agg:,.0f} | ${reg_agg_otd:,.0f} | ${quoted_otd - reg_agg_otd:,.0f}")
    print("```")
    
    print("\n**Nationwide Negotiation Bids (Fly / Ship)**")
    print("```")
    print(f"{'Bid Tier Target':<24} | {'Price':<8} | {'OTD Price':<9} | {'Savings':<8}")
    print("-" * 57)
    print(f"{'Quoted Price (Base)':<24} | ${quoted_price:,.0f} | ${quoted_otd:,.0f} | $0")
    print(f"{'Midpoint (50% Spread)':<24} | ${nat_midpoint:,.0f} | ${nat_mid_otd:,.0f} | ${quoted_otd - nat_mid_otd:,.0f}")
    print(f"{'Cheapest Nation (100%)':<24} | ${nat_price:,.0f} | ${nat_otd:,.0f} | ${quoted_otd - nat_otd:,.0f}")
    print(f"{'Aggressive (-10% Nat)':<24} | ${nat_agg:,.0f} | ${nat_agg_otd:,.0f} | ${quoted_otd - nat_agg_otd:,.0f}")
    print("```")

    # --- TABLE 3: TOP CHEAPEST NATIONWIDE DEALS ---
    print("\n### Table 3: Top Cheapest Nationwide Deals (New Only)")
    print("```")
    print(f"{'Dealership (State — Dist)':<35} | {'Price':<7} | {'OTD Price':<9} | {'Delta':<7}")
    print("-" * 67)
    
    # Sort top_listings (cheapest 10) by distance
    top_listings.sort(key=lambda x: x.get("computed_distance", float('inf')))
    cheapest_price = cheapest_nationwide["price"] if cheapest_nationwide else 0
    
    for car in top_listings:
        c_price = car.get("price")
        c_dist = car.get("computed_distance", float('inf'))
        c_state = car.get("state", "??")
        c_dealer = car.get("dealer_name") or "Dealer"
        c_dealer_lbl = f"{c_dealer[:22]} ({c_state} — {c_dist:.0f} mi)"
        
        c_otd = calculate_otd(c_price)
        delta = c_price - cheapest_price
        print(f"{c_dealer_lbl:<35} | ${c_price:,.0f} | ${c_otd:,.0f} | +${delta:,.0f}")
    print("```")
    
    # Conditional Post-Sale Warranty Printout
    m_lower = make.lower()
    if m_lower in ["toyota", "lexus"]:
        print("\n### 🎁 Post-Sale Factory Warranty Nuggets (Toyota/Lexus)")
        print("- Jerry Johnson at Midwest Superstore (Hutchinson, KS): jerryj@midwestsuperstore.com | 800-530-5789")
        print("  *Why he's famous*: Famous across forums for selling official Toyota/Lexus Platinum VSCs at wholesale volume margins.")
        print("- Troy Dietrich at Factory Discount Warranty: Submit a quote request through fd-warranty.com.")
        print("  *Note*: VSCs can be purchased anytime until the original 3-year/36,000-mile bumper-to-bumper warranty expires.")
    elif m_lower in ["chrysler"]:
        print("\n### 🎁 Post-Sale Factory Warranty Nuggets (Mopar MaxCare)")
        print("- Tom Winkels at LaFontaine CDJR: tomwinkels@hayescars.com")
        print("  *Why he's famous*: Undisputed Mopar warranty low-margin king, sells authentic plans at wholesale margins.")
        print("- Zeigler Auto Group: chryslerfactoryplans.com")
        print("  *The trick*: Use online forum promo codes like PAYINFULL or DAMON for an extra $300-$500 off their automated quote.")
        print("  *Note*: Always request official Mopar MaxCare plan; do not accept third-party plans.")

if __name__ == "__main__":
    main()
