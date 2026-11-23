-- Gold layer - star schema for ABET reporting (Delta / Databricks SQL)
-- One fact table (grades) surrounded by conformed dimensions.

CREATE TABLE IF NOT EXISTS gold.dim_course (
    course_id   BIGINT,
    course_code STRING,
    course_name STRING,
    programme   STRING,
    clo_code    STRING,   -- Course Learning Outcome mapped to this course
    so_code     STRING    -- Student Outcome (ABET) mapped via the CLO
) USING DELTA;

CREATE TABLE IF NOT EXISTS gold.dim_student (
    student_id   BIGINT,
    student_name STRING,
    programme    STRING,
    cohort       STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS gold.fact_grades (
    student_id    BIGINT,
    course_id     BIGINT,
    assessment_id BIGINT,
    score         DOUBLE,
    max_score     DOUBLE,
    score_pct     DOUBLE,  -- score / max_score * 100, computed in Silver
    graded_date   DATE
) USING DELTA;

CREATE TABLE IF NOT EXISTS gold.gold_clo_so_attainment (
    programme       STRING,
    clo_code        STRING,
    so_code         STRING,
    n_assessments   BIGINT,
    avg_score_pct   DOUBLE,
    share_at_target DOUBLE,  -- share of assessments scoring >= 70%
    clo_attained    BOOLEAN  -- TRUE when share_at_target >= 70%
) USING DELTA;
