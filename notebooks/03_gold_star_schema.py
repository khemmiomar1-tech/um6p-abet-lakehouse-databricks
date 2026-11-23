# Databricks notebook source
# MAGIC %md
# MAGIC # 03 - Gold Star Schema + ABET Attainment
# MAGIC Silver -> Gold: dimensional model (fact + dimensions) built for Power BI,
# MAGIC plus the CLO / SO attainment calculation used for ABET accreditation.

# COMMAND ----------

from pyspark.sql import functions as F

SILVER = "/Volumes/abet/silver/delta"
GOLD = "/Volumes/abet/gold/delta"

courses = spark.read.format("delta").load(f"{SILVER}/silver_courses")
students = spark.read.format("delta").load(f"{SILVER}/silver_students")
grades = spark.read.format("delta").load(f"{SILVER}/silver_grades")

# COMMAND ----------

# Step 1 - Dimensions
dim_course = courses.select("course_id", "course_code", "course_name", "programme", "clo_code", "so_code").dropDuplicates()
dim_student = students.select("student_id", "student_name", "programme", "cohort").dropDuplicates()

# Step 2 - Fact: one row per graded assessment
fact_grades = grades.select("student_id", "course_id", "assessment_id", "score", "max_score", "score_pct", "graded_date")

dim_course.write.format("delta").mode("overwrite").save(f"{GOLD}/dim_course")
dim_student.write.format("delta").mode("overwrite").save(f"{GOLD}/dim_student")
fact_grades.write.format("delta").mode("overwrite").save(f"{GOLD}/fact_grades")

# COMMAND ----------

# Step 3 - CLO attainment: % of students at or above the 70% target score
# (ABET convention used in the project: a CLO is "attained" when at least 70%
#  of students score at least 70% on the assessments mapped to that CLO.)
TARGET_SCORE = 70.0
TARGET_SHARE = 0.70

attainment = (
    fact_grades.join(dim_course, "course_id")
    .groupBy("programme", "clo_code", "so_code")
    .agg(
        F.count("*").alias("n_assessments"),
        F.avg("score_pct").alias("avg_score_pct"),
        (F.sum(F.when(F.col("score_pct") >= TARGET_SCORE, 1).otherwise(0)) / F.count("*")).alias("share_at_target"),
    )
    .withColumn("clo_attained", F.col("share_at_target") >= TARGET_SHARE)
)
attainment.write.format("delta").mode("overwrite").save(f"{GOLD}/gold_clo_so_attainment")
attainment.show()
