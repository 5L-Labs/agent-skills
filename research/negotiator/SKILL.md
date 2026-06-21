---
name: negotiator
description: Calculates OTD pricing spreads, cheapest market benchmarks, and mobile-friendly negotiation bid tiers to assist in dealership negotiations.
version: 1.0.0
author: Antigravity Agent
license: MIT
metadata:
  hermes:
    tags: [negotiation, car-buying, auto-pricing, visor-api, extended-warranty]
---

# Negotiator Skill

This skill assists agents in running mobile-friendly pricing comparisons and negotiation target bid spreadsheets for target vehicles.

## Purpose

Use this skill when the user provides a VIN or a specific quote for a vehicle (e.g. at a dealership with options) and wants to:
1. Compare that price with other regional listings.
2. Establish a clear negotiation gap against similar units.
3. Compute midpoint (50% spread) and aggressive (10% below market) target bids for phone/email pitches.
4. Access post-sale extended warranty contacts for Toyota, Lexus, and Chrysler vehicles.

## Setup & Credentials

To run the negotiator tool, you need to configure the following environment variables or add them to your `.env` file:

*   `VISOR.VIN_API_KEY` (or `VISOR_API_KEY`): Required. The bearer API token used to query the live Visor API (`https://api.visor.vin/v1/listings`) for real-time inventory listings.

## Dependencies

This skill requires the following Python libraries:
*   `requests`
*   `python-dotenv`

## How to Run

Execute the tool via Python:

```bash
python scripts/negotiator_tool.py --price <QUOTED_PRICE> [ --vin <VIN> ] [ --make <MAKE> --model <MODEL> --trim <TRIM> ]
```

### Parameters
*   `--price`: (Required) The current quoted price of the vehicle.
*   `--vin`: (Optional) The 17-digit VIN. If supplied, the tool decodes it to determine the make/model/trim.
*   `--make`: (Optional) The vehicle make (e.g., Toyota, Lexus, Chrysler).
*   `--model`: (Optional) The vehicle model (e.g., Grand Highlander, Pacifica, TX).
*   `--trim`: (Optional) The trim level (e.g., Pinnacle AWD, Hybrid MAX Platinum AWD).

## Example Output

The script outputs three tables formatted to fit perfectly on mobile screens:

1.  **Quote vs. Benchmarks**: Compares the quoted OTD against the cheapest comparable unit found in the database, and against our baseline target vehicles (Pacifica, Grand Highlander, Lexus TX).
2.  **Negotiation Bid Targets**: Outlines specific regional and nationwide bid tiers:
    *   **Midpoint (50% Spread)**: The halfway point between the dealer's quote and the cheapest market price.
    *   **Cheapest Market (100%)**: The lowest price listed in the market for this exact trim.
    *   **Aggressive (-10% Market)**: 10% below the cheapest market price, useful for low-balling or initiating a tough push.
3.  **Top Cheapest Nationwide Deals**: Lists the top 10 cheapest comparable units nationwide, sorted by distance from Yonkers, NY, showing their OTD prices and delta price differences from the absolute cheapest model.

It also conditionally appends **Post-Sale Factory Warranty Nuggets** at the bottom if the vehicle is a Toyota, Lexus, or Chrysler.

## Post-Sale Warranty (VSC) & Protection Contacts

Reference these contacts post-purchase to secure official manufacturer extended warranties at wholesale or heavily discounted pricing.

### 1. Toyota Grand Highlander & Lexus Configurations
Toyota and Lexus share the same corporate backing (Toyota Motor Insurance Services). These high-volume finance managers can write official factory policies for both brands:
*   **The Contact**: Jerry Johnson at Midwest Superstore (Hutchinson, KS).
    *   *Why he's famous*: "Jerry from Midwest" is a household name across Toyota and Lexus forums. He sells official Toyota/Lexus Platinum VSCs at a fraction of standard retail.
    *   *How to reach him*: Email directly at jerryj@midwestsuperstore.com or call the dealership at 800-530-5789.
*   **The Alternative**: Troy Dietrich at Factory Discount Warranty (backed by a brick-and-mortar Toyota network in MA).
    *   *How to reach him*: Submit a quote request through fd-warranty.com.
*   *Note*: You can purchase these plans anytime up until the original 3-year / 36,000-mile bumper-to-bumper factory warranty expires.

### 2. Chrysler Pacifica
For a Pacifica, purchase an official Mopar MaxCare plan (the highest tier component coverage directly from Stellantis). Do not accept a third-party plan:
*   **The Contact**: Tom Winkels at LaFontaine CDJR (formerly Hayes Jeep).
    *   *Why he's famous*: Tom is the undisputed "low-margin king" for Mopar warranties across the internet. He sells authentic Mopar Vehicle Protection plans at wholesale volume margins.
    *   *How to reach him*: Email at tomwinkels@hayescars.com or contact the dealership's finance department.
*   **The Online Portal Option**: Zeigler Auto Group (chryslerfactoryplans.com).
    *   *Why they're famous*: Zeigler is a massive dealer group with an automated online checkout for official Mopar plans.
    *   *The trick*: Use online forum promo codes (often `PAYINFULL` or `DAMON`) to instantly cut an extra $300 to $500 off the quote.
