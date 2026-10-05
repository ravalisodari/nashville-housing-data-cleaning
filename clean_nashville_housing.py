"""
Clean the Nashville Housing raw dataset.

Usage:
    python clean_nashville_housing.py                # downloads raw file if missing
    python clean_nashville_housing.py path/to/raw.xlsx

Outputs (in ./output):
    nashville_housing_cleaned.csv   cleaned dataset
    cleaning_log.csv                one row per cleaning step, with counts of affected rows
"""
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

RAW_URL = (
    "https://raw.githubusercontent.com/AlexTheAnalyst/PortfolioProjects/main/"
    "Nashville%20Housing%20Data%20for%20Data%20Cleaning.xlsx"
)
RAW_PATH = Path("data/nashville_housing_raw.xlsx")
OUT_DIR = Path("output")

log = []


def record(step, issue, action, rows):
    log.append({"step": step, "issue": issue, "action": action, "rows_affected": int(rows)})
    print(f"[{step:>2}] {issue:<45} -> {rows:>6} rows | {action}")


def collapse_ws(s: pd.Series) -> pd.Series:
    """Remove Excel line-break artefacts, collapse repeated spaces, strip ends."""
    return (
        s.str.replace(r"_x000D_|\r|\n", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def main(raw_path: Path):
    # ------------------------------------------------------------------ load
    if not raw_path.exists():
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading raw data to {raw_path} ...")
        urllib.request.urlretrieve(RAW_URL, raw_path)

    df = pd.read_excel(raw_path)
    n_raw = len(df)
    print(f"Loaded {n_raw:,} rows x {df.shape[1]} columns\n")

    # ------------------------------------------------- 1. column names
    old_cols = list(df.columns)
    rename = {
        "UniqueID": "unique_id", "ParcelID": "parcel_id", "LandUse": "land_use",
        "PropertyAddress": "property_address", "SaleDate": "sale_date",
        "SalePrice": "sale_price", "LegalReference": "legal_reference",
        "SoldAsVacant": "sold_as_vacant", "OwnerName": "owner_name",
        "OwnerAddress": "owner_address", "Acreage": "acreage",
        "TaxDistrict": "tax_district", "LandValue": "land_value",
        "BuildingValue": "building_value", "TotalValue": "total_value",
        "YearBuilt": "year_built", "Bedrooms": "bedrooms",
        "FullBath": "full_bath", "HalfBath": "half_bath",
    }
    df.columns = [c.strip() for c in df.columns]  # 'UniqueID ' has a trailing space
    df = df.rename(columns=rename)
    record(1, "Column names had trailing space ('UniqueID ') / CamelCase",
           "Stripped and converted to snake_case", len(old_cols))

    # ---------------------------------------------- 2. data types
    changed = 0
    # LegalReference is stored as a mix of str and int -> make it a clean string
    mixed = df["legal_reference"].map(lambda v: not isinstance(v, str)).sum()
    df["legal_reference"] = df["legal_reference"].astype(str).str.strip()
    changed += mixed
    df["parcel_id"] = df["parcel_id"].astype("string").str.strip()
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    for c in ["year_built", "bedrooms", "full_bath", "half_bath"]:
        df[c] = df[c].astype("Int64")  # whole numbers (were float64 because of NaN)
    record(2, "Wrong dtypes (mixed str/int ref, float counts)",
           "legal_reference->string, year_built/bedrooms/full_bath/half_bath->Int64, sale_date->datetime",
           len(df))

    # ------------------------------------- 3. whitespace / artefacts
    text_cols = ["parcel_id", "land_use", "property_address", "owner_name",
                 "owner_address", "tax_district"]
    n_ws = 0
    for c in text_cols:
        before = df[c].copy()
        df[c] = collapse_ws(df[c].astype("string"))
        n_ws += (before.fillna("") != df[c].fillna("")).sum()
    record(3, "Extra/double spaces, stray '_x000D_' line breaks",
           "Collapsed whitespace, removed Excel carriage-return artefacts (count = cells changed)", n_ws)

    # -------------------------------------- 4. inconsistent categories
    # sold_as_vacant: Y/N vs Yes/No
    n_sav = df["sold_as_vacant"].isin(["Y", "N"]).sum()
    df["sold_as_vacant"] = df["sold_as_vacant"].str.strip().str.upper().map(
        {"Y": "Yes", "YES": "Yes", "N": "No", "NO": "No"})
    record(4, "sold_as_vacant mixed 'Y'/'N' with 'Yes'/'No'", "Standardised to Yes/No", n_sav)

    # land_use: abbreviations, typos, duplicated labels
    land_use_map = {
        "VACANT RES LAND": "VACANT RESIDENTIAL LAND",
        "VACANT RESIENTIAL LAND": "VACANT RESIDENTIAL LAND",
        "RESTURANT/CAFETERIA": "RESTAURANT/CAFETERIA",
        "GREENBELT/RES GRRENBELT/RES": "GREENBELT/RES",
        "CONDOMINIUM OFC OR OTHER COM CONDO": "CONDOMINIUM OFC OR OTHER COM CONDO",
    }
    n_lu = df["land_use"].isin(land_use_map.keys()).sum() - (
        df["land_use"] == "CONDOMINIUM OFC OR OTHER COM CONDO").sum()
    n_lu_before = df["land_use"].nunique()
    df["land_use"] = df["land_use"].replace(land_use_map)
    record(5, f"land_use typos/abbreviations ({n_lu_before} labels)",
           f"Merged to {df['land_use'].nunique()} canonical labels", n_lu)

    # ------------------------------------------ 6. missing addresses
    miss_before = df["property_address"].isna().sum()
    addr_lookup = (df.dropna(subset=["property_address"])
                   .drop_duplicates("parcel_id")
                   .set_index("parcel_id")["property_address"])
    fill = df["property_address"].isna()
    df.loc[fill, "property_address"] = df.loc[fill, "parcel_id"].map(addr_lookup)
    record(6, "Missing property_address",
           f"Filled from other sales of the same parcel_id ({miss_before - df['property_address'].isna().sum()} of {miss_before} recovered)",
           miss_before - df["property_address"].isna().sum())

    # ---------------------------------- 7. split combined address fields
    pa = df["property_address"].str.rsplit(",", n=1, expand=True)
    df["property_street"] = pa[0].str.strip()
    df["property_city"] = pa[1].str.strip()
    oa = df["owner_address"].str.rsplit(",", n=2, expand=True)
    df["owner_street"] = oa[0].str.strip()
    df["owner_city"] = oa[1].str.strip()
    df["owner_state"] = oa[2].str.strip()
    df = df.drop(columns=["property_address", "owner_address"])
    record(7, "Combined address fields (street, city, state in one cell)",
           "Split into property_street/city and owner_street/city/state", len(df))

    # --------------------------------------------- 8. duplicates
    key = ["parcel_id", "property_street", "sale_date", "sale_price", "legal_reference"]
    n_dup = df.duplicated(subset=key, keep="first").sum()
    df = df.drop_duplicates(subset=key, keep="first")
    record(8, "Duplicate sales (same parcel/address/date/price/deed, different unique_id)",
           "Dropped repeats, kept first occurrence", n_dup)

    # ---------------------------------------- 9. remaining checks
    # Values reviewed but deliberately NOT changed (no safe correction exists).
    review = {
        "sale_price < $1,000 (possible non-arm's-length / typo)": (df["sale_price"] < 1000).sum(),
        "acreage > 50 (extreme outlier)": (df["acreage"] > 50).sum(),
        "bedrooms == 0 on a residential land-use": ((df["bedrooms"] == 0) &
            df["land_use"].isin(["SINGLE FAMILY", "RESIDENTIAL CONDO", "DUPLEX"])).sum(),
        "total_value != land_value + building_value (+/- $1)": (
            (df["land_value"] + df["building_value"] - df["total_value"]).abs() > 1).sum(),
    }
    for k, v in review.items():
        record(9, f"Reviewed, kept as-is: {k}", "Documented only (no reliable fix)", v)

    # -------------------------------------------------- reorder + save
    cols = ["unique_id", "parcel_id", "land_use", "property_street", "property_city",
            "sale_date", "sale_price", "legal_reference", "sold_as_vacant",
            "owner_name", "owner_street", "owner_city", "owner_state", "acreage",
            "tax_district", "land_value", "building_value", "total_value",
            "year_built", "bedrooms", "full_bath", "half_bath"]
    df = df[cols].sort_values("unique_id").reset_index(drop=True)

    OUT_DIR.mkdir(exist_ok=True)
    df.to_csv(OUT_DIR / "nashville_housing_cleaned.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame(log).to_csv(OUT_DIR / "cleaning_log.csv", index=False)

    print(f"\nRows: {n_raw:,} -> {len(df):,}")
    print("Remaining nulls (kept as NaN, not imputed):")
    print(df.isna().sum()[df.isna().sum() > 0].to_string())


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RAW_PATH)
