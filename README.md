# Nashville Housing Data: Cleaning Project

Cleaning a raw real-estate sales dataset with **Python (pandas)** so it is ready for analysis.

## Dataset
- **Name:** Nashville Housing Data for Data Cleaning (Nashville, TN property sales, 2013–2019)
- **Source:** [AlexTheAnalyst/PortfolioProjects](https://github.com/AlexTheAnalyst/PortfolioProjects) (public GitHub repo)
- **Raw size:** 56,477 rows × 19 columns, saved here as `data/nashville_housing_raw.xlsx`
- **Cleaned size:** 56,373 rows × 22 columns, in `output/nashville_housing_cleaned.csv`

## Repository contents
| File | Purpose |
|---|---|
| `data/nashville_housing_raw.xlsx` | Original, untouched data |
| `clean_nashville_housing.py` | Reproducible cleaning script |
| `output/nashville_housing_cleaned.csv` | **Cleaned dataset** |
| `output/cleaning_log.csv` | Every step with the number of rows/cells affected |
| `requirements.txt` | Python dependencies |

**Run it:** `pip install -r requirements.txt && python clean_nashville_housing.py`

## Problems found and what I did

### 1. Missing values
| Column(s) | Missing (raw) | Action |
|---|---|---|
| `PropertyAddress` | 29 | **Filled** from other sales of the same `ParcelID` (all 29 recovered, since a parcel always has the same address) |
| `OwnerName` | 31,216 | Left null (no reliable source) |
| `OwnerAddress`, `Acreage`, `TaxDistrict`, `LandValue`, `BuildingValue`, `TotalValue` | ~30,462 each | Left null. These 6 columns are missing on exactly the same 30,404 rows, so the gap looks like a failed join to an assessor table, not random gaps. The source doesn't say why, and imputing would invent data. |
| `YearBuilt`, `Bedrooms`, `FullBath`, `HalfBath` | ~32,200–32,300 | Left null (no reliable source). Missing on every row that lacks assessor data, plus ~1,850 others; affects condos (44%), single family (40%) and vacant land (14%) |

> Nulls were only filled where the true value could be recovered from the data itself. Everything else stays null so downstream analysis can handle it deliberately.

### 2. Duplicate records
- **104 duplicate sales removed.** These had identical `ParcelID`, address, `SaleDate`, `SalePrice` and `LegalReference` but different `UniqueID`s. I checked that every duplicate group was identical in all other columns before dropping, and kept the first occurrence.
- A plain "drop exact duplicates" finds **zero**, because `UniqueID` differs. Duplicates only show up when the ID is excluded.

### 3. Incorrect data types
| Column | Before | After | Why |
|---|---|---|---|
| `LegalReference` | mixed `str` / `int` (6 values were ints) | string | It is an identifier, not a number |
| `YearBuilt`, `Bedrooms`, `FullBath`, `HalfBath` | float (e.g. `3.0`) | nullable integer | These are counts and years |
| `ParcelID` | object | string | Identifier |
| `SaleDate` | datetime | datetime (saved as `YYYY-MM-DD`) | Validated, no unparseable dates |

### 4. Inconsistent values
- **`SoldAsVacant`:** `Y`/`N` mixed with `Yes`/`No` (451 rows). Standardised to **Yes / No**.
- **`LandUse`:** 39 labels reduced to 37 by merging typos and abbreviations:
  - `VACANT RES LAND`, `VACANT RESIENTIAL LAND` → `VACANT RESIDENTIAL LAND`
  - `RESTURANT/CAFETERIA` → `RESTAURANT/CAFETERIA`
  - `GREENBELT/RES\r\nGRRENBELT/RES` (corrupted by a line break) → `GREENBELT/RES`
  - `CONDO` and `RESIDENTIAL CONDO` were deliberately **not** merged, since they may be distinct assessor categories.
- **Whitespace:** double spaces in 55k+ addresses (`1808  FOX CHASE DR`), trailing spaces, and Excel `_x000D_` artefacts were normalised.
- **Column names:** `UniqueID ` had a trailing space; all columns renamed to `snake_case`.

### 5. Structural improvement
- `PropertyAddress` split into `property_street` + `property_city`.
- `OwnerAddress` split into `owner_street` + `owner_city` + `owner_state`.

## Reviewed but intentionally not changed
These look suspicious but there is no safe correction, so they are documented, not altered:
| Check | Rows |
|---|---|
| `sale_price` under $1,000 (likely non-arm's-length transfers) | 7 |
| `acreage` over 50 | 4 |
| `bedrooms = 0` on single-family / condo / duplex | 4 |
| `total_value ≠ land_value + building_value` (±$1) | 7,154 |

Analysts may want to filter these depending on the question being asked.

## Before → After summary
| Metric | Raw | Cleaned |
|---|---|---|
| Rows | 56,477 | 56,373 |
| Columns | 19 | 22 |
| Missing `property_address` | 29 | 0 |
| Duplicate sales | 104 | 0 |
| `SoldAsVacant` distinct values | 4 | 2 |
| `LandUse` distinct labels | 39 | 37 |
| Property addresses with double spaces | 55,863 | 0 |
