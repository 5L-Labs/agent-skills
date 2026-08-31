#!/usr/bin/env python3
"""
Production-Grade Generic Auto Lease & Finance Negotiation Engine
Supports:
- Closed-form True $0 Drive-Off (Sign & Drive) lease calculation with NY State/Jurisdiction tax capitalization
- Multiple Security Deposit (MSD) optimization with money factor discount and guaranteed annualized ROI
- Full 100% OTD Amortization Financing with custom APRs and terms
- Multi-tier target bid generation (Floor / Sweet Spot / Ceiling)
- Dynamic JSON and Markdown export adhering strictly to input parameters
"""

import argparse
import json
import math
import sys
from typing import Dict, List, Optional, Tuple, Any

class AutoFinanceEngine:
    def __init__(
        self,
        tax_rate: float = 0.08875,       # Default Yonkers, NY (8.875%)
        doc_fee: float = 175.0,           # NY legal doc fee cap
        acq_fee: float = 650.0,           # Standard captive lease acq fee ($650 TFS / $795 LFS)
        gov_fee: float = 285.0,           # Registration / Plates / Title / Tire fee
        msd_mf_discount: float = 0.00008  # LFS / TFS standard discount per MSD
    ):
        self.tax_rate = tax_rate
        self.doc_fee = doc_fee
        self.acq_fee = acq_fee
        self.gov_fee = gov_fee
        self.msd_mf_discount = msd_mf_discount

    def calculate_purchase_otd(self, selling_price: float) -> Tuple[float, float]:
        """Calculates total out-the-door price for vehicle purchase."""
        taxable_base = selling_price + self.doc_fee
        tax = taxable_base * self.tax_rate
        otd = selling_price + self.doc_fee + self.gov_fee + tax
        return otd, tax

    def calculate_finance_payment(self, amount_financed: float, apr: float, term_months: int) -> float:
        """Calculates monthly payment for standard amortized loan."""
        monthly_rate = (apr / 100.0) / 12.0
        if monthly_rate == 0:
            return amount_financed / term_months
        payment = amount_financed * (monthly_rate * (1 + monthly_rate)**term_months) / ((1 + monthly_rate)**term_months - 1)
        return payment

    def calculate_lease(
        self,
        msrp: float,
        selling_price: float,
        term_months: int,
        residual_pct: float,
        base_mf: float,
        msds: int = 0,
        zero_drive_off: bool = True
    ) -> Dict[str, Any]:
        """
        Calculates exact lease numbers with True $0 Drive-Off in NY State
        (Sales tax levied strictly on the sum of payments and capitalized).
        """
        # Apply MSD discount (preserve exact 0.0 MF if zero/subsidized, reject negative)
        effective_mf = max(0.0, base_mf - (msds * self.msd_mf_discount))
        residual_value = msrp * residual_pct
        
        # Base capitalized costs before tax
        base_cap = selling_price + self.doc_fee + self.acq_fee + (self.gov_fee if zero_drive_off else 0.0)
        
        if zero_drive_off:
            # Closed-form solution for NY lease tax capitalized into payment
            num = ((base_cap + (self.doc_fee + self.acq_fee) * self.tax_rate - residual_value) / term_months) + \
                  ((base_cap + (self.doc_fee + self.acq_fee) * self.tax_rate + residual_value) * effective_mf)
            den = 1.0 - self.tax_rate - (term_months * self.tax_rate * effective_mf)
            
            base_monthly = num / den
            total_tax = (base_monthly * term_months + self.doc_fee + self.acq_fee) * self.tax_rate
            monthly_tax = total_tax / term_months
            total_monthly = base_monthly + monthly_tax
            drive_off_fees = 0.0
            total_lease_cost = total_monthly * term_months
        else:
            # Traditional lease (Taxes and first month paid upfront at signing)
            net_cap = base_cap
            monthly_dep = (net_cap - residual_value) / term_months
            monthly_rent = (net_cap + residual_value) * effective_mf
            base_monthly = monthly_dep + monthly_rent
            total_tax = (base_monthly * term_months + self.doc_fee + self.acq_fee) * self.tax_rate
            monthly_tax = 0.0
            total_monthly = base_monthly
            drive_off_fees = total_monthly + total_tax + self.gov_fee
            # Net lease cost is total payments plus upfront taxes and fees (avoiding double counting first payment)
            total_lease_cost = (total_monthly * (term_months - 1)) + drive_off_fees

        # 1 MSD unit is monthly payment rounded up to nearest $50 increment
        msd_unit = math.ceil(total_monthly / 50.0) * 50.0
        total_msd_deposit = msd_unit * msds
        total_due_at_signing = drive_off_fees + total_msd_deposit

        return {
            "term_months": term_months,
            "residual_pct": residual_pct,
            "residual_value": residual_value,
            "effective_mf": round(effective_mf, 5),
            "equiv_apr": round(effective_mf * 2400, 2),
            "msds_count": msds,
            "msd_deposit": total_msd_deposit,
            "base_monthly": round(base_monthly, 2),
            "monthly_tax": round(monthly_tax, 2),
            "total_monthly": round(total_monthly, 2),
            "total_tax": round(total_tax, 2),
            "drive_off_fees": round(drive_off_fees, 2),
            "total_due_at_signing": round(total_due_at_signing, 2),
            "total_lease_cost": round(total_lease_cost, 2)
        }

    def generate_full_matrix(
        self,
        msrp: float,
        discounts: Optional[List[Tuple[str, float]]] = None,
        lease_terms: Optional[List[Tuple[int, float]]] = None,
        base_mf: float = 0.00220,
        msd_options: Optional[List[int]] = None,
        finance_terms: Optional[List[Tuple[int, float]]] = None
    ) -> Dict[str, Any]:
        """Generates a complete multi-tier lease and finance matrix."""
        
        if discounts is None:
            discounts = [("Tier 1: Floor (-10%)", 0.10), ("Tier 2: Target (-7.5%)", 0.075), ("Tier 3: Ceiling (-5%)", 0.05)]
        if lease_terms is None:
            lease_terms = [(36, 0.58), (48, 0.50)]
        if msd_options is None:
            msd_options = [0, 6]
        if finance_terms is None:
            # 48m/60m promotional captive APRs (4.99%/5.49%) and 72m standard tier (6.49%)
            finance_terms = [(48, 4.99), (60, 5.49), (72, 6.49)]
            
        report = {
            "msrp": msrp,
            "tax_rate_pct": round(self.tax_rate * 100, 3),
            "doc_fee": self.doc_fee,
            "acq_fee": self.acq_fee,
            "gov_fee": self.gov_fee,
            "tiers": []
        }

        for tier_name, discount_pct in discounts:
            sp = msrp * (1.0 - discount_pct)
            otd, tax = self.calculate_purchase_otd(sp)
            
            tier_data = {
                "tier_name": tier_name,
                "discount_pct": round(discount_pct * 100, 1),
                "selling_price": round(sp, 2),
                "purchase_tax": round(tax, 2),
                "purchase_otd": round(otd, 2),
                "leases": {},
                "finances": {}
            }

            # Calculate Lease Options
            for term, res in lease_terms:
                res_pct_label = f"{round(res * 100, 2):g}"
                term_key = f"{term}m_{res_pct_label}res"
                tier_data["leases"][term_key] = {}
                
                # Base zero-MSD baseline cost for ROI calculation
                base_lease = self.calculate_lease(msrp, sp, term, res, base_mf, msds=0, zero_drive_off=True)
                
                for msd in msd_options:
                    lease_res = self.calculate_lease(msrp, sp, term, res, base_mf, msds=msd, zero_drive_off=True)
                    
                    # Calculate MSD ROI (Return on Investment) annualized
                    if msd > 0 and lease_res["msd_deposit"] > 0:
                        total_savings = base_lease["total_lease_cost"] - lease_res["total_lease_cost"]
                        annual_savings = total_savings / (term / 12.0)
                        lease_res["msd_roi_pct"] = round((annual_savings / lease_res["msd_deposit"]) * 100, 2)
                        lease_res["total_savings_vs_0msd"] = round(total_savings, 2)
                    elif msd == 0:
                        lease_res["msd_roi_pct"] = 0.0
                        lease_res["total_savings_vs_0msd"] = 0.0

                    tier_data["leases"][term_key][f"{msd}_msd"] = lease_res

            # Calculate Finance Options
            for term, apr in finance_terms:
                pmt = self.calculate_finance_payment(otd, apr, term)
                tier_data["finances"][f"{term}m_{apr}apr"] = {
                    "term_months": term,
                    "apr": apr,
                    "monthly_payment": round(pmt, 2),
                    "total_finance_cost": round(pmt * term, 2),
                    "total_interest": round(pmt * term - otd, 2)
                }

            report["tiers"].append(tier_data)

        return report

def format_markdown_report(data: Dict[str, Any], vehicle_name: str = "Vehicle") -> str:
    msrp = data["msrp"]
    tax_rate = data.get("tax_rate_pct", 8.875)
    doc_fee = data.get("doc_fee", 175.0)
    
    md = f"# 📱 {vehicle_name} — Generic Negotiation & Financial Matrix\n"
    md += f"**Benchmark MSRP**: **${msrp:,.2f}** | **Tax Jurisdiction**: **{tax_rate}% Tax** | **Doc Fee**: **${doc_fee:,.2f}**\n\n"
    
    if not data.get("tiers"):
        return md

    # Dynamically derive lease columns from the first tier
    first_tier = data["tiers"][0]
    lease_term_keys = list(first_tier.get("leases", {}).keys())
    
    md += "### 🎯 1. Lease Matrix (True $0 Drive-Off / Sign & Drive)\n"
    
    # Build dynamic lease headers
    lease_headers = ["Negotiation Tier", "Selling Price"]
    lease_sub_keys = []
    for lk in lease_term_keys:
        msd_keys = list(first_tier["leases"][lk].keys())
        for mk in msd_keys:
            msd_count = mk.split("_")[0]
            msd_label = f"({msd_count} MSDs)" if msd_count != "0" else "(0 MSD)"
            term_label = lk.replace("res", "% Res").replace("m_", " Mo / ")
            lease_headers.append(f"{term_label} {msd_label}")
            lease_sub_keys.append((lk, mk))

    md += "| " + " | ".join(lease_headers) + " |\n"
    md += "| " + " | ".join([":---"] + [":---:"] * (len(lease_headers) - 1)) + " |\n"

    for t in data["tiers"]:
        row = [f"**{t['tier_name']}**", f"**${t['selling_price']:,.2f}**"]
        for lk, mk in lease_sub_keys:
            cell_data = t["leases"].get(lk, {}).get(mk, {})
            val = f"${cell_data.get('total_monthly', 0):,.2f}" if cell_data else "N/A"
            row.append(f"**{val}**")
        md += "| " + " | ".join(row) + " |\n"

    # Dynamically derive finance columns from the first tier
    finance_term_keys = list(first_tier.get("finances", {}).keys())
    md += "\n### 🏦 2. Finance Matrix (True $0 Down / 100% Financed OTD)\n"
    
    finance_headers = ["Negotiation Tier", "Selling Price", "Total OTD Financed"]
    for fk in finance_term_keys:
        f_data = first_tier["finances"][fk]
        finance_headers.append(f"{f_data['term_months']} Mo ({f_data['apr']}%)")
    
    md += "| " + " | ".join(finance_headers) + " |\n"
    md += "| " + " | ".join([":---"] + [":---:"] * (len(finance_headers) - 1)) + " |\n"

    for t in data["tiers"]:
        row = [f"**{t['tier_name']}**", f"**${t['selling_price']:,.2f}**", f"**${t['purchase_otd']:,.2f}**"]
        for fk in finance_term_keys:
            f_cell = t["finances"].get(fk, {})
            val = f"${f_cell.get('monthly_payment', 0):,.2f}" if f_cell else "N/A"
            row.append(f"**{val}**")
        md += "| " + " | ".join(row) + " |\n"

    return md

def main():
    parser = argparse.ArgumentParser(description="Generic Auto Lease & Finance Negotiation Calculator")
    parser.add_argument("--msrp", type=float, required=True, help="Vehicle MSRP sticker price")
    parser.add_argument("--name", type=str, default="Target Vehicle", help="Vehicle Label / Description")
    parser.add_argument("--tax-rate", type=float, default=0.08875, help="Sales tax rate (default 0.08875)")
    parser.add_argument("--doc-fee", type=float, default=175.0, help="Doc fee (default 175.0)")
    parser.add_argument("--acq-fee", type=float, default=650.0, help="Lease acquisition fee ($650 TFS / $795 LFS)")
    parser.add_argument("--gov-fee", type=float, default=285.0, help="Government registration/plates fee (default 285.0)")
    parser.add_argument("--mf", type=float, default=0.00220, help="Base Tier 1 Money Factor (default 0.00220)")
    parser.add_argument("--res36", type=float, default=0.58, help="36-month residual percentage (default 0.58)")
    parser.add_argument("--res48", type=float, default=0.50, help="48-month residual percentage (default 0.50)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of markdown")
    args = parser.parse_args()

    engine = AutoFinanceEngine(
        tax_rate=args.tax_rate,
        doc_fee=args.doc_fee,
        acq_fee=args.acq_fee,
        gov_fee=args.gov_fee
    )
    data = engine.generate_full_matrix(
        msrp=args.msrp,
        base_mf=args.mf,
        lease_terms=[(36, args.res36), (48, args.res48)]
    )

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_markdown_report(data, vehicle_name=args.name))

if __name__ == "__main__":
    main()
