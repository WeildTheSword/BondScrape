"""
NOS Extraction Schema

JSON schema for structured extraction of Notice of Sale documents.
Covers the full 55-feature taxonomy across 10 categories:
  Sale Logistics, Bond Identification, Maturity Structure,
  Coupon Provisions, Bid Evaluation, Redemption, Registration/Delivery,
  Credit/Enhancement, Legal/Advisory, Bidder Obligations.

Used by llm_extract.py as the target schema for LLM extraction,
and by validate.py for deterministic validation checks.
"""

NOS_EXTRACTION_SCHEMA = {
    "type": "object",
    "required": [
        "issuer", "bond_identification", "sale_logistics",
        "maturity_structure", "coupon_provisions", "bid_evaluation",
        "redemption", "registration_delivery", "credit_enhancement",
        "legal_advisory", "bidder_obligations"
    ],
    "properties": {

        # ── Issuer Identification ──────────────────────────────────
        "issuer": {
            "type": "object",
            "required": ["name", "type", "state"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Full legal name of the issuing entity"
                },
                "type": {
                    "type": "string",
                    "enum": [
                        "state", "county", "city", "town", "school_district",
                        "special_district", "authority", "municipal_utility_district",
                        "independent_school_district", "regional_school_unit", "other"
                    ],
                    "description": "Classification of the issuing entity"
                },
                "state": {
                    "type": "string",
                    "description": "Two-letter state abbreviation (e.g. TX, ME, CA)"
                },
                "county": {
                    "type": ["string", "null"],
                    "description": "County name if stated"
                }
            }
        },

        # ── Bond Identification & Structure ────────────────────────
        "bond_identification": {
            "type": "object",
            "required": ["series", "bond_type", "par_amount", "tax_status"],
            "properties": {
                "series": {
                    "type": "string",
                    "description": "Series designation (e.g. 'Series 2026', 'Series 2026A&B')"
                },
                "bond_type": {
                    "type": "string",
                    "enum": [
                        "go_unlimited_tax", "go_limited_tax", "revenue",
                        "assessment", "certificate_of_obligation",
                        "tax_increment", "bond_anticipation_note", "other"
                    ],
                    "description": "Fundamental obligation type backing repayment"
                },
                "bond_type_description": {
                    "type": "string",
                    "description": "Full bond type as stated in the document (e.g. 'Unlimited Tax Bonds')"
                },
                "par_amount": {
                    "type": "number",
                    "description": "Total principal amount of the offering in dollars"
                },
                "tax_status": {
                    "type": "string",
                    "enum": ["tax_exempt", "taxable", "amt_subject"],
                    "description": "Federal income tax treatment of interest"
                },
                "bank_qualified": {
                    "type": ["boolean", "null"],
                    "description": "Whether the issue qualifies as a qualified tax-exempt obligation (Section 265, <= $10M). null if not stated."
                },
                "purpose": {
                    "type": ["string", "null"],
                    "description": "What the bond proceeds will finance (e.g. 'new construction', 'refunding')"
                }
            }
        },

        # ── Sale Logistics ─────────────────────────────────────────
        "sale_logistics": {
            "type": "object",
            "required": ["sale_date"],
            "properties": {
                "sale_date": {
                    "type": "string",
                    "description": "Date and time bids are due (ISO 8601 or natural language as stated)"
                },
                "sale_time": {
                    "type": ["string", "null"],
                    "description": "Time bids are due if stated separately from date"
                },
                "bidding_platform": {
                    "type": ["string", "null"],
                    "enum": ["parity", "grant_street", "other", null],
                    "description": "Electronic platform used to submit bids"
                },
                "bidding_platform_name": {
                    "type": ["string", "null"],
                    "description": "Full platform name as stated (e.g. 'PARITY Electronic Bid Submission System')"
                },
                "bid_format": {
                    "type": ["string", "null"],
                    "enum": ["electronic_only", "written_fax_allowed", null],
                    "description": "How bids must be submitted"
                },
                "right_to_reject": {
                    "type": ["boolean", "null"],
                    "description": "Whether issuer reserves right to reject all bids"
                },
                "pre_sale_adjustment": {
                    "type": ["boolean", "null"],
                    "description": "Whether issuer can modify par amounts or maturities before bid opening"
                },
                "financial_advisor": {
                    "type": ["string", "null"],
                    "description": "Financial advisory firm name"
                }
            }
        },

        # ── Maturity & Amortization Structure ──────────────────────
        "maturity_structure": {
            "type": "object",
            "required": ["maturity_type", "dated_date", "maturity_schedule"],
            "properties": {
                "maturity_type": {
                    "type": "string",
                    "enum": ["serial_only", "term_only", "serial_and_term", "single_maturity"],
                    "description": "How principal repayment is scheduled"
                },
                "dated_date": {
                    "type": "string",
                    "description": "The date from which interest begins to accrue"
                },
                "interest_payment_dates": {
                    "type": ["string", "null"],
                    "description": "Specific months/dates interest is paid (e.g. 'May 1 and November 1')"
                },
                "first_interest_payment": {
                    "type": ["string", "null"],
                    "description": "Date of first interest payment if stated"
                },
                "maturity_schedule": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["date", "amount"],
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "Maturity date (e.g. 'April 1, 2029' or '2029')"
                            },
                            "amount": {
                                "type": "number",
                                "description": "Principal amount maturing on this date in dollars"
                            },
                            "type": {
                                "type": "string",
                                "enum": ["serial", "term"],
                                "description": "Whether this is a serial or term maturity"
                            }
                        }
                    },
                    "description": "Full maturity schedule: date + principal amount for each maturity"
                },
                "final_maturity_date": {
                    "type": ["string", "null"],
                    "description": "The last date any principal is due"
                },
                "bidder_term_bond_option": {
                    "type": ["boolean", "null"],
                    "description": "Whether bidders may designate term bonds from serial maturities"
                },
                "mandatory_sinking_fund": {
                    "type": ["boolean", "null"],
                    "description": "Whether term bonds have required periodic redemptions"
                },
                "number_of_maturities": {
                    "type": ["integer", "null"],
                    "description": "Total number of maturity dates"
                },
                "total_bond_years": {
                    "type": ["number", "null"],
                    "description": "Sum of (amount * years to maturity) for all maturities, if stated in document"
                },
                "average_maturity": {
                    "type": ["number", "null"],
                    "description": "Weighted average maturity in years, if stated in document"
                }
            }
        },

        # ── Coupon & Interest Provisions ───────────────────────────
        "coupon_provisions": {
            "type": "object",
            "properties": {
                "interest_payment_frequency": {
                    "type": ["string", "null"],
                    "enum": ["semiannual", "annual", "other", null],
                    "description": "How often bondholders receive interest"
                },
                "interest_calculation_basis": {
                    "type": ["string", "null"],
                    "enum": ["30_360", "actual_actual", "actual_360", null],
                    "description": "Day-count convention for computing interest"
                },
                "coupon_rate_constraints": {
                    "type": "object",
                    "properties": {
                        "ascending_only": {
                            "type": ["boolean", "null"],
                            "description": "Whether coupon rates must be non-descending across maturities"
                        },
                        "no_zero_coupon": {
                            "type": ["boolean", "null"],
                            "description": "Whether zero coupon bonds are prohibited"
                        },
                        "max_rate_cap": {
                            "type": ["number", "null"],
                            "description": "Maximum allowable coupon rate as percentage (e.g. 5.0)"
                        },
                        "max_number_of_rates": {
                            "type": ["integer", "null"],
                            "description": "Maximum number of different coupon rates permitted"
                        },
                        "no_restrictions": {
                            "type": ["boolean", "null"],
                            "description": "True if no coupon restrictions are stated"
                        }
                    }
                },
                "rate_increment": {
                    "type": ["string", "null"],
                    "description": "Minimum increment for coupon rates (e.g. '1/8 of 1%', '1/20 of 1%')"
                },
                "uniform_rate_per_maturity": {
                    "type": ["boolean", "null"],
                    "description": "Whether all bonds of the same maturity must bear one rate (split coupon allowed if false)"
                }
            }
        },

        # ── Bid Evaluation & Award Criteria ────────────────────────
        "bid_evaluation": {
            "type": "object",
            "required": ["basis_of_award"],
            "properties": {
                "basis_of_award": {
                    "type": "string",
                    "enum": ["nic", "tic", "net_effective_rate", "other"],
                    "description": "Metric used to determine winning bid. Texas 'net effective interest rate' is functionally NIC."
                },
                "good_faith_deposit": {
                    "type": "object",
                    "properties": {
                        "amount": {
                            "type": ["number", "null"],
                            "description": "Dollar amount of good faith deposit"
                        },
                        "percentage_of_par": {
                            "type": ["number", "null"],
                            "description": "Deposit as percentage of par (e.g. 2.0 for 2%)"
                        },
                        "form": {
                            "type": ["string", "null"],
                            "enum": ["wire_transfer", "certified_check", "cashiers_check", "surety_bond", "other", null],
                            "description": "How the deposit must be submitted"
                        }
                    }
                },
                "premium_discount_permitted": {
                    "type": ["string", "null"],
                    "enum": ["premium_allowed", "discount_allowed", "par_only", "both_allowed", null],
                    "description": "Whether bidders may offer above or below par"
                },
                "minimum_bid_price": {
                    "type": ["number", "null"],
                    "description": "Floor on the total dollar bid as percentage of par (e.g. 99.0 for 99%)"
                },
                "maximum_bid_price": {
                    "type": ["number", "null"],
                    "description": "Ceiling on the total dollar bid as percentage of par, if stated"
                },
                "max_interest_rate": {
                    "type": ["number", "null"],
                    "description": "Maximum net effective interest rate as percentage, if stated"
                },
                "issue_price_requirements": {
                    "type": ["string", "null"],
                    "enum": ["hold_the_offering_price", "10_percent_test", "competitive_sale_exception", null],
                    "description": "IRS issue price regulation that applies"
                }
            }
        },

        # ── Redemption Provisions ──────────────────────────────────
        "redemption": {
            "type": "object",
            "properties": {
                "optional_redemption": {
                    "type": ["string", "null"],
                    "enum": ["callable", "non_callable", "make_whole_call", null],
                    "description": "Whether the issuer may call bonds before maturity"
                },
                "first_call_date": {
                    "type": ["string", "null"],
                    "description": "Earliest date bonds may be called (e.g. 'April 1, 2031')"
                },
                "call_price": {
                    "type": ["number", "null"],
                    "description": "Price at which called bonds are redeemed (e.g. 100 for par)"
                },
                "call_protection_years": {
                    "type": ["number", "null"],
                    "description": "Number of years of call protection"
                },
                "extraordinary_redemption": {
                    "type": ["boolean", "null"],
                    "description": "Whether events trigger mandatory early redemption"
                }
            }
        },

        # ── Registration, Delivery & Form ──────────────────────────
        "registration_delivery": {
            "type": "object",
            "properties": {
                "book_entry": {
                    "type": ["string", "null"],
                    "enum": ["book_entry_only", "certificated", "both_available", null],
                    "description": "Form in which bonds are issued"
                },
                "denomination": {
                    "type": ["number", "null"],
                    "description": "Minimum face value of individual bonds in dollars (e.g. 5000)"
                },
                "paying_agent": {
                    "type": ["string", "null"],
                    "description": "Entity that maintains bondholder records and processes payments"
                },
                "delivery_date": {
                    "type": ["string", "null"],
                    "description": "Expected settlement date"
                },
                "latest_delivery_date": {
                    "type": ["string", "null"],
                    "description": "Latest acceptable delivery date if stated"
                },
                "delivery_method": {
                    "type": ["string", "null"],
                    "enum": ["dtc_fast", "physical_delivery", null],
                    "description": "How bonds will be delivered"
                },
                "cusip": {
                    "type": ["string", "null"],
                    "enum": ["assigned", "pending", "not_stated", null],
                    "description": "Whether CUSIP numbers have been assigned"
                }
            }
        },

        # ── Credit & Enhancement ───────────────────────────────────
        "credit_enhancement": {
            "type": "object",
            "properties": {
                "credit_rating": {
                    "type": ["string", "null"],
                    "description": "Bond rating(s) or 'unrated' or 'no application made'. Include agency name if stated."
                },
                "bond_insurance": {
                    "type": ["string", "null"],
                    "enum": ["insured", "bidder_option_to_insure", "uninsured", null],
                    "description": "Whether credit enhancement through insurance is contemplated"
                },
                "insurance_provider_restrictions": {
                    "type": ["string", "null"],
                    "description": "Rules around who may provide insurance"
                }
            }
        },

        # ── Legal & Advisory Team ──────────────────────────────────
        "legal_advisory": {
            "type": "object",
            "properties": {
                "bond_counsel": {
                    "type": ["string", "null"],
                    "description": "Bond counsel law firm name"
                },
                "disclosure_counsel": {
                    "type": ["string", "null"],
                    "description": "Disclosure counsel firm name"
                },
                "tax_counsel": {
                    "type": ["string", "null"],
                    "description": "Tax counsel firm name if separate from bond counsel"
                },
                "legal_opinion_type": {
                    "type": ["string", "null"],
                    "enum": ["unqualified", "qualified", null],
                    "description": "Form of the bond counsel opinion"
                },
                "continuing_disclosure": {
                    "type": ["string", "null"],
                    "enum": ["full_compliance", "exempt", "not_stated", null],
                    "description": "Whether issuer commits to ongoing disclosure per SEC Rule 15c2-12"
                }
            }
        },

        # ── Bidder Obligations & Risk Allocation ───────────────────
        "bidder_obligations": {
            "type": "object",
            "properties": {
                "commitment_type": {
                    "type": ["string", "null"],
                    "enum": ["firm_commitment", "best_efforts", null],
                    "description": "Nature of the underwriting commitment"
                },
                "reoffering_price_certification": {
                    "type": ["boolean", "null"],
                    "description": "Whether winning bidder must certify initial offering prices"
                },
                "official_statement_responsibility": {
                    "type": ["string", "null"],
                    "enum": ["issuer_prepares", "winning_bidder_completes", null],
                    "description": "Who bears responsibility for finalizing the OS"
                },
                "technology_risk_allocation": {
                    "type": ["string", "null"],
                    "enum": ["bidder_assumes_all_risk", "shared", "not_stated", null],
                    "description": "Who bears risk of electronic bid transmission failures"
                },
                "withdrawal_restrictions": {
                    "type": ["string", "null"],
                    "description": "Conditions under which a bidder may not withdraw after award"
                }
            }
        }
    }
}


# Flattened field list for quick reference — maps each field to its
# JSON path and which agent consumes it
FIELD_AGENT_MAP = {
    # Sector Fit agent reads these
    "issuer.type": "sector_fit",
    "issuer.state": "sector_fit",
    "bond_identification.bond_type": "sector_fit",
    "bond_identification.tax_status": "sector_fit",
    "bond_identification.purpose": "sector_fit",
    "legal_advisory.bond_counsel": "sector_fit",

    # Size & Capital agent reads these
    "bond_identification.par_amount": "size_capital",
    "bidder_obligations.commitment_type": "size_capital",
    "bid_evaluation.good_faith_deposit": "size_capital",
    "registration_delivery.delivery_date": "size_capital",

    # Structure agent reads these
    "coupon_provisions.coupon_rate_constraints": "structure",
    "bid_evaluation.basis_of_award": "structure",
    "coupon_provisions.rate_increment": "structure",
    "bid_evaluation.premium_discount_permitted": "structure",
    "bid_evaluation.minimum_bid_price": "structure",
    "maturity_structure.maturity_schedule": "structure",
    "bid_evaluation.issue_price_requirements": "structure",
    "redemption": "structure",

    # Distribution agent reads these
    "bond_identification.par_amount": "distribution",
    "maturity_structure.maturity_type": "distribution",
    "maturity_structure.final_maturity_date": "distribution",
    "bond_identification.tax_status": "distribution",
    "bond_identification.bank_qualified": "distribution",
    "registration_delivery.denomination": "distribution",
    "redemption.optional_redemption": "distribution",
    "credit_enhancement.credit_rating": "distribution",

    # Calendar agent reads these
    "sale_logistics.sale_date": "calendar",
    "registration_delivery.delivery_date": "calendar",
    "sale_logistics.bidding_platform": "calendar",
}


def get_schema_for_prompt() -> str:
    """Return the schema as a formatted JSON string for inclusion in LLM prompts."""
    import json
    return json.dumps(NOS_EXTRACTION_SCHEMA, indent=2)
