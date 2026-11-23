# UM6P ABET Lakehouse - Databricks / PySpark

A Lakehouse pipeline built during my end-of-studies internship (PFE) at
**UM6P, Benguerir (Feb-Jul 2026)** to automate **ABET accreditation tracking**:
instead of manual spreadsheets, academic data flows from the Canvas LMS into a
Databricks Lakehouse (Bronze / Silver / Gold, Delta Lake) and is exposed to
Power BI dashboards that track **CLO / SO attainment**.

> **Honesty note:** this repository is a *portfolio reproduction* of that
> architecture. It contains **synthetic sample data only** - no real UM6P
> data (confidential). The Canvas extractor is my real internship code,
> sanitised: the API token is read from an environment variable.

## Architecture

```
Canvas LMS --(Python extractor)--> Bronze (raw Delta)
           --(PySpark cleaning)--> Silver (dedup, nulls, standardised)
           --(star schema)-------> Gold (fact_grades, dim_course, dim_student)
           --(Power BI + DAX)----> CLO / SO attainment dashboards
           + RAG assistant (LangChain + ChromaDB) over academic documents
```

## Contents

| Path | What it does |
|---|---|
| `src/canvas_extractor.py` | Canvas API extractor: paginated course / student / activity extraction, per-programme CSVs + consolidated Power BI workbook, synthetic demo mode |
| `notebooks/01_bronze_ingestion.py` | Raw extracts -> Bronze Delta tables, stamped with ingestion metadata |
| `notebooks/02_silver_cleaning.py` | Deduplication, null handling, standardisation, `score_pct` |
| `notebooks/03_gold_star_schema.py` | Fact/dimension tables + CLO/SO attainment (70% of students at 70%+) |
| `sql/gold_schema.sql` | Gold star schema DDL |
| `powerbi/dax_measures.md` | DAX measures: average score, share at target, CLO/SO attainment |
| `rag/rag_demo.py` | Mini RAG demo (LangChain + ChromaDB) over sample ABET documents |
| `data/sample/` | Small synthetic CSVs (courses, students, grades) |

## Run the extractor demo (no Canvas access needed)

```bash
pip install requests pandas openpyxl
python src/canvas_extractor.py   # no token set -> synthetic demo workbook
```

## Stack

Databricks - PySpark - Delta Lake - Python - SQL - Power BI / DAX -
LangChain - ChromaDB

## Resume (Francais)

Pipeline Lakehouse realise pendant mon stage de fin d'etudes a l'UM6P
(fev.-juil. 2026) pour automatiser le suivi d'accreditation ABET : extraction
des donnees Canvas avec Python, nettoyage PySpark sur Databricks en
architecture Bronze / Silver / Gold (Delta Lake), modelisation en schema en
etoile, tableaux de bord Power BI avec mesures DAX pour le suivi des CLO/SO,
et assistant RAG (LangChain, ChromaDB). Donnees d'exemple 100% synthetiques -
aucune donnee reelle de l'UM6P.

---
Omar Khemmi - Data Engineer - Casablanca, Morocco
