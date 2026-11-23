# Power BI - DAX Measures (ABET CLO / SO Tracking)

Gold tables (`fact_grades`, `dim_course`, `dim_student`, `gold_clo_so_attainment`)
are connected to Power BI in a star schema: filters flow from the dimensions
to the fact table.

## Average score (%)

```dax
Avg Score % = AVERAGE ( fact_grades[score_pct] )
```

## Share of students at target (>= 70%)

```dax
Share At Target =
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_grades ), fact_grades[score_pct] >= 70 ),
    COUNTROWS ( fact_grades )
)
```

## CLO attainment flag (target: 70% of students at 70%+)

```dax
CLO Attained =
IF ( [Share At Target] >= 0.70, "Attained", "Not attained" )
```

## SO attainment (average of its CLO shares)

```dax
SO Attainment =
AVERAGEX (
    VALUES ( dim_course[clo_code] ),
    [Share At Target]
)
```

## Number of graded assessments

```dax
Nb Assessments = COUNTROWS ( fact_grades )
```
