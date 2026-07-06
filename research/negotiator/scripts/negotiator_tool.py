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

def decode_vin_from_profiles(vin, profiles):
    vin = vin.upper()
    for profile_key, p in profiles.items():
        sample = p.get("sample_vin", "").upper()
        if not sample:
            continue
        make = p.get("make", "")
        # For Toyota/Lexus, match first 5 chars
        if make.lower() in ["toyota", "lexus"]:
            if vin.startswith(sample[:5]):
                return p.get("make"), p.get("model"), p.get("trim"), p
        # For Chrysler, match first 6 chars
        elif make.lower() == "chrysler":
            if vin.startswith(sample[:6]):
                return p.get("make"), p.get("model"), p.get("trim"), p
        # General WMI fallback
        else:
            if vin.startswith(sample[:5]):
                return p.get("make"), p.get("model"), p.get("trim"), p
    return None, None, None, None

def find_profile_by_specs(make, model, trim, profiles):
    if not make or not model:
        return None
    make_lower = make.lower()
    model_lower = model.lower()
    trim_lower = (trim or "").lower()
    
    # Try exact match or inclusion
    for key, p in profiles.items():
        p_make = p.get("make", "").lower()
        p_model = p.get("model", "").lower()
        p_trim = p.get("trim", "").lower()
        
        if p_make == make_lower and p_model == model_lower:
            if not trim_lower or trim_lower in p_trim or p_trim in trim_lower:
                return p
                
    # Fallback to first make/model match
    for key, p in profiles.items():
        p_make = p.get("make", "").lower()
        p_model = p.get("model", "").lower()
        if p_make == make_lower and p_model == model_lower:
            return p
    return None

def calculate_shipping(dist):
    if dist <= 150:
        return 0.0
    return 1200.0

def calculate_travel(dist):
    if dist <= 150:
        return 50.0
    return 500.0

def get_cheapest_national(make, model, trim, api_key, target_vin=None, profile=None):
    # Query Visor API live for matching trim
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
            
    # Determine criteria from profile if available
    if profile:
        req_keywords = profile.get("required_trim_keywords")
        requires_awd = profile.get("requires_awd")
        requires_hybrid = profile.get("requires_hybrid")
        target_powertrain = None
        vin_prefix = profile.get("vin_prefix") or profile.get("sample_vin")
        if vin_prefix and len(vin_prefix) > 9:
            if make.lower() in ["toyota", "lexus"]:
                target_powertrain = vin_prefix[3:5]
            elif make.lower() == "chrysler":
                target_powertrain = vin_prefix[5]
    else:
        # Fallback to the original hardcoded matching logic
        req_keywords = None
        trim_lower = trim.lower()
        if "platinum" in trim_lower or "plat" in trim_lower:
            req_keywords = ["plat"]
        elif "limited" in trim_lower or "ltd" in trim_lower:
            req_keywords = ["limit"]
        elif "pinnacle" in trim_lower or "pinn" in trim_lower:
            req_keywords = ["pinn"]
        elif "350" in trim_lower:
            req_keywords = ["350"]
        else:
            trim_words = trim_lower.split()
            req_keywords = [w for w in trim_words if w not in ["awd", "4wd", "hybrid", "max"]]
            
        requires_awd = "awd" in trim_lower or "4wd" in trim_lower or "4x4" in trim_lower
        requires_hybrid = "hybrid" in trim_lower
        
        target_powertrain = None
        if target_vin:
            target_vin = target_vin.upper()
            if len(target_vin) > 9:
                if make.lower() in ["toyota", "lexus"]:
                    target_powertrain = target_vin[3:5]
                elif make.lower() == "chrysler":
                    target_powertrain = target_vin[5]
            
    matching = []
    for car in listings:
        car_trim = (car.get("trim") or "").lower()
        car_vin = (car.get("vin") or "").upper()
        price = car.get("price")
        car_type = (car.get("inventory_type", car.get("inventoryType", "used")) or "used").lower()
        
        if price is None or not car_vin:
            continue
            
        # Powertrain matching
        if target_powertrain and len(car_vin) > 9:
            if make.lower() in ["toyota", "lexus"]:
                if car_vin[3:5] != target_powertrain:
                    continue
            elif make.lower() == "chrysler":
                if car_vin[5] != target_powertrain:
                    continue
                    
        # Condition matching (strictly new)
        if car_type != "new":
            continue
            
        # Match trim keywords
        listing_text = f"{model} {car_trim}".upper()
        if req_keywords:
            if not any(k.upper() in listing_text for k in req_keywords):
                continue
                
        # Match AWD
        if requires_awd:
            is_awd_flag = car.get("is_awd") or (car.get("drivetrain") or "").upper() in ("AWD", "4WD", "4X4", "ALL-WHEEL DRIVE")
            if not is_awd_flag:
                vdp_url = car.get("vdp_url") or car.get("vdpUrl") or ""
                listing_text = f"{model} {car_trim} {vdp_url}".upper()
                is_awd_flag = any(token in listing_text for token in ("AWD", "4WD", "4X4"))
            if not is_awd_flag and car_vin.startswith("5TDAA") and len(car_vin) > 5:
                is_awd_flag = (car_vin[5] == "B")
            if not is_awd_flag:
                continue
                
        # Match Hybrid
        if requires_hybrid:
            if "HYBRID" not in listing_text and not car_vin.startswith(("5TDAC", "5TDAD")):
                continue
                
        lat = car.get("latitude")
        lon = car.get("longitude")
        dist = get_distance(lat, lon)
        car["computed_distance"] = dist
        matching.append(car)
            
    # Also load from saved file if API has fewer matches
    project_root = os.getcwd()
    current = os.path.dirname(os.path.abspath(__file__))
    while current and current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, ".git")) or os.path.exists(os.path.join(current, ".agents")):
            project_root = current
            break
        current = os.path.dirname(current)
        
    saved_path = os.path.join(project_root, "data", "comprehensive_search_results.json")
    if not os.path.exists(saved_path):
        saved_path = os.path.join(os.getcwd(), "data", "comprehensive_search_results.json")
        
    if os.path.exists(saved_path):
        try:
            with open(saved_path, "r") as f:
                saved_data = json.load(f)
                
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
                        if make.lower() in ["toyota", "lexus"]:
                            if car_vin[3:5] != target_powertrain:
                                continue
                        elif make.lower() == "chrysler":
                            if car_vin[5] != target_powertrain:
                                continue
                                
                    # Condition matching
                    if car_type != "new":
                        continue
                        
                    # Match trim keywords
                    listing_text = f"{model} {car_trim}".upper()
                    if req_keywords:
                        if not any(k.upper() in listing_text for k in req_keywords):
                            continue
                            
                    # Match AWD
                    if requires_awd:
                        is_awd_flag = car.get("is_awd") or (car.get("drivetrain") or "").upper() in ("AWD", "4WD", "4X4", "ALL-WHEEL DRIVE")
                        if not is_awd_flag:
                            vdp_url = car.get("vdp_url") or car.get("vdpUrl") or ""
                            listing_text = f"{model} {car_trim} {vdp_url}".upper()
                            is_awd_flag = any(token in listing_text for token in ("AWD", "4WD", "4X4"))
                        if not is_awd_flag and car_vin.startswith("5TDAA") and len(car_vin) > 5:
                            is_awd_flag = (car_vin[5] == "B")
                        if not is_awd_flag:
                            continue
                            
                    # Match Hybrid
                    if requires_hybrid:
                        if "HYBRID" not in listing_text and not car_vin.startswith(("5TDAC", "5TDAD")):
                            continue
                            
                    lat = car.get("latitude")
                    lon = car.get("longitude")
                    dist = get_distance(lat, lon)
                    car["computed_distance"] = dist
                    
                    if not any(x.get("vin") == car.get("vin") for x in matching):
                        matching.append(car)
        except Exception:
            pass

    matching.sort(key=lambda x: x.get("price", float('inf')))
    cheapest_nationwide = matching[0] if matching else None
    regional_matches = [c for c in matching if c.get("computed_distance", float('inf')) <= 250.0]
    cheapest_regional = regional_matches[0] if regional_matches else None
    
    return cheapest_regional, cheapest_nationwide, matching[:10]

def main():
    project_root = os.getcwd()
    current = os.path.dirname(os.path.abspath(__file__))
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
    
    parser = argparse.ArgumentParser(description="Negotiator Tool - Calculates OTD spreads and bids.")
    parser.add_argument("--vin", type=str, help="VIN of the target vehicle")
    parser.add_argument("--make", type=str, help="Make of the vehicle (if VIN not supplied/known)")
    parser.add_argument("--model", type=str, help="Model of the vehicle")
    parser.add_argument("--trim", type=str, help="Trim level of the vehicle")
    parser.add_argument("--price", type=float, required=True, help="Dealership quoted price")
    parser.add_argument("--config", type=str, help="Path to target profiles JSON configuration file")
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = args.config
    if not config_path:
        for loc in [
            os.path.join(project_root, "config", "target_profiles.json"),
            os.path.join(project_root, "data", "target_profiles.json"),
            os.path.join(project_root, "target_profiles.json"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "target_profiles.json"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "target_profiles.json"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "target_profiles.json")
        ]:
            if os.path.exists(loc):
                config_path = loc
                break
                
    profiles = {}
    if not config_path or not os.path.exists(config_path):
        print("[-] Error: Configuration file not found. Please create 'config/target_profiles.json' or supply --config.", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(config_path, "r") as f:
            profiles = json.load(f)
    except Exception as e:
        print(f"[-] Error loading config from {config_path}: {e}", file=sys.stderr)
        sys.exit(1)
            
    make, model, trim = args.make, args.model, args.trim
    vin = args.vin
    profile = None
    
    if vin:
        v_make, v_model, v_trim, matched_prof = decode_vin_from_profiles(vin, profiles)
        if v_make:
            make, model, trim, profile = v_make, v_model, v_trim, matched_prof
            
    if not profile and (make and model):
        profile = find_profile_by_specs(make, model, trim, profiles)
        
    if not make or not model:
        print("[-] Error: Make and Model could not be resolved. Please supply --make and --model or a valid VIN.")
        sys.exit(1)
        
    trim = trim or ""
    
    quoted_price = args.price
    quoted_otd = calculate_otd(quoted_price)
    
    cheapest_regional, cheapest_nationwide, top_listings = get_cheapest_national(make, model, trim, api_key, target_vin=vin, profile=profile)
    
    if cheapest_regional:
        reg_price = cheapest_regional["price"]
        reg_otd = calculate_otd(reg_price)
        reg_lbl = f"Cheapest Regional ({cheapest_regional.get('state', 'PA')} — {cheapest_regional['computed_distance']:.0f} mi)"
    else:
        reg_price = quoted_price * 0.95
        reg_otd = calculate_otd(reg_price)
        reg_lbl = "Cheapest Regional (Est. 5% Disc)"
        
    if cheapest_nationwide:
        nat_price = cheapest_nationwide["price"]
        nat_otd = calculate_otd(nat_price)
        nat_lbl = f"Cheapest Nation ({cheapest_nationwide.get('state', 'UT')} — {cheapest_nationwide['computed_distance']:.0f} mi)"
    else:
        nat_price = quoted_price * 0.95
        nat_otd = calculate_otd(nat_price)
        nat_lbl = "Cheapest Nation (Est. 5% Disc)"
        
    # Load baseline targets dynamically
    baselines = []
    for key, p in profiles.items():
        name = f"{p.get('make')} {p.get('model')} {p.get('trim')}"
        otd = p.get("target_otd_price")
        if otd:
            price = (otd - DOC_FEES) / (1 + TAX_RATE)
            baselines.append({"name": name, "price": price})
        else:
            price = p.get("target_price") or p.get("price")
            if price:
                baselines.append({"name": name, "price": price})
                
    if not baselines:
        print("[-] Warning: No baseline vehicles with target prices found in configuration.", file=sys.stderr)
        
    # --- TABLE 1: CURRENT VS BENCHMARKS ---
    print("\n### Table 1: Quote vs. Benchmarks (New Only)")
    print("```")
    print(f"{'Target Vehicle':<42} | {'Price':<8} | {'OTD Price':<9} | {'Room':<7}")
    print("-" * 75)
    print(f"{'Quoted ' + make + ' ' + model:<42} | ${quoted_price:,.0f} | ${quoted_otd:,.0f} | --")
    print(f"{reg_lbl:<42} | ${reg_price:,.0f} | ${reg_otd:,.0f} | ${quoted_otd - reg_otd:,.0f}")
    print(f"{nat_lbl:<42} | ${nat_price:,.0f} | ${nat_otd:,.0f} | ${quoted_otd - nat_otd:,.0f}")
    
    for b in baselines:
        b_otd = calculate_otd(b["price"])
        room = quoted_otd - b_otd
        print(f"{b['name']:<42} | ${b['price']:,.0f} | ${b_otd:,.0f} | ${room:,.0f}")
    print("```")
    
    # --- TABLE 2: NEGOTIATION BID TIER TARGETS ---
    reg_midpoint = reg_price + 0.5 * (quoted_price - reg_price)
    reg_mid_otd = calculate_otd(reg_midpoint)
    reg_agg = reg_price * 0.90
    reg_agg_otd = calculate_otd(reg_agg)
    
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
