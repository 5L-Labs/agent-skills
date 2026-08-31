#!/usr/bin/env python3
"""
Production-Grade Generic Auto Lease & Finance Negotiation Engine
Supports:
- Closed-form True $0 Drive-Off (Sign & Drive) lease calculation with NY State/Jurisdiction tax capitalization
- Multiple Security Deposit (MSD) optimization with money factor discount and guaranteed ROI
- Full 100% OTD Amortization Financing with custom APRs and terms
- Multi-tier target bid generation (Floor / Sweet Spot / Ceiling)
- JSON and Markdown export
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
        # Apply MSD discount
        effective_mf = max(0.00001, base_mf - (msds * self.msd_mf_discount))
        residual_value = msrp * residual_pct
        
        # Base capitalized costs before tax
        base_cap = selling_price + self.doc_fee + self.acq_fee + (self.gov_fee if zero_drive_off else 0.0)
        
        if zero_drive_off:
            # Closed-form solution for NY lease tax capitalized into payment
            # BaseMonthly = Depreciation + Rent Charge
            # TotalTax = (BaseMonthly * Term + doc_fee + acq_fee) * tax_rate
            # NetCap = base_cap + TotalTax
            num = ((base_cap + (self.doc_fee + self.acq_fee) * self.tax_rate - residual_value) / term_months) + \
                  ((base_cap + (self.doc_fee + self.acq_fee) * self.tax_rate + residual_value) * effective_mf)
            den = 1.0 - self.tax_rate - (term_months * self.tax_rate * effective_mf)
            
            base_monthly = num / den
            total_tax = (base_monthly * term_months + self.doc_fee + self.acq_fee) * self.tax_rate
            monthly_tax = total_tax / term_months
            total_monthly = base_monthly + monthly_tax
            drive_off = 0.0
        else:
            # Traditional lease (Taxes and first month paid upfront at signing)
            net_cap = base_cap
            monthly_dep = (net_cap - residual_value) / term_months
            monthly_rent = (net_cap + residual_value) * effective_mf
            base_monthly = monthly_dep + monthly_rent
            total_tax = (base_monthly * term_months + self.doc_fee + self.acq_fee) * self.tax_rate
            monthly_tax = 0.0
            total_monthly = base_monthly
            drive_off = total_monthly + total_tax + self.gov_fee

        # 1 MSD unit is monthly payment rounded up to nearest $50 increment
        msd_unit = math.ceil(total_monthly / 50.0) * 50.0
        total_msd_deposit = msd_unit * msds

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
            "drive_off": round(drive_off, 2),
            "total_lease_cost": round(total_monthly * term_months + drive_off, 2)
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
            finance_terms = [(48, 4.99), (60, 5.49), (72, 6.49)]
            
        report = {
            "msrp": msrp,
            "tax_rate_pct": round(self.tax_rate * 100, 3),
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
                term_key = f"{term}m_{int(res*100)}res"
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
    md = f"# 📱 {vehicle_name} — Generic Negotiation & Financial Matrix\n"
    md += f"**Benchmark MSRP**: **${msrp:,.2f}** | **Tax Jurisdiction**: **{data['tax_rate_pct']}% Tax** | **Doc Fee**: **$175.00**\n\n"
    
    md += "### 🎯 1. Lease Matrix (True $0 Drive-Off / Sign & Drive)\n"
    md += "| Negotiation Tier | Selling Price | 36 Mo / 15k Mi (0 MSD) | 36 Mo (6 MSDs) | 48 Mo (0 MSD) | 48 Mo (6 MSDs) |\n"
    md += "| :--- | :---: | :---: | :---: | :---: | :---: |\n"
    
    for t in data["tiers"]:
        # Find any 36m and 48m term dynamically
        l36_data = {}
        l48_data = {}
        for k, v in t["leases"].items():
            if k.startswith("36m"):
                l36_data = v
            elif k.startswith("48m"):
                l48_data = v
                
        l36_0 = l36_data.get("0_msd", {})
        l36_6 = l36_data.get("6_msd", {})
        l48_0 = l48_data.get("0_msd", {})
        l48_6 = l48_data.get("6_msd", {})
        
        p36_0 = f"${l36_0.get('total_monthly', 0):,.2f}" if l36_0 else "N/A"
        p36_6 = f"${l36_6.get('total_monthly', 0):,.2f}" if l36_6 else "N/A"
        p48_0 = f"${l48_0.get('total_monthly', 0):,.2f}" if l48_0 else "N/A"
        p48_6 = f"${l48_6.get('total_monthly', 0):,.2f}" if l48_6 else "N/A"
        
        md += f"| **{t['tier_name']}** | **${t['selling_price']:,.2f}** | **{p36_0}** | **{p36_6}** | **{p48_0}** | **{p48_6}** |\n"

    md += "\n### 🏦 2. Finance Matrix (True $0 Down / 100% Financed OTD)\n"
    md += "| Negotiation Tier | Selling Price | Total OTD Financed | 48 Mo (4.99%) | 60 Mo (5.49%) | 72 Mo (6.49%) |\n"
    md += "| :--- | :---: | :---: | :---: | :---: | :---: |\n"
    for t in data["tiers"]:
        f48 = t["finances"].get("48m_4.99apr", {}).get("monthly_payment", 0)
        f60 = t["finances"].get("60m_5.49apr", {}).get("monthly_payment", 0)
        f72 = t["finances"].get("72m_6.49apr", {}).get("monthly_payment", 0)
        md += f"| **{t['tier_name']}** | **${t['selling_price']:,.2f}** | **${t['purchase_otd']:,.2f}** | **${f48:,.2f}** | **${f60:,.2f}** | **${f72:,.2f}** |\n"

    return md

def main():
    parser = argparse.ArgumentParser(description="Generic Auto Lease & Finance Negotiation Calculator")
    parser.add_argument("--msrp", type=float, required=True, help="Vehicle MSRP sticker price")
    parser.add_argument("--name", type=str, default="Target Vehicle", help="Vehicle Label / Description")
    parser.add_argument("--tax-rate", type=float, default=0.08875, help="Sales tax rate (default 0.08875)")
    parser.add_argument("--acq-fee", type=float, default=650.0, help="Lease acquisition fee ($650 TFS / $795 LFS)")
    parser.add_argument("--mf", type=float, default=0.00220, help="Base Tier 1 Money Factor (default 0.00220)")
    parser.add_argument("--res36", type=float, default=0.58, help="36-month residual percentage (default 0.58)")
    parser.add_argument("--res48", type=float, default=0.50, help="48-month residual percentage (default 0.50)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of markdown")
    args = parser.parse_args()

    engine = AutoFinanceEngine(tax_rate=args.tax_rate, acq_fee=args.acq_fee)
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
