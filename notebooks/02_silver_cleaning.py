# Databricks notebook source
# MAGIC %md
# MAGIC # 02 - Silver Cleaning
# MAGIC Bronze -> Silver: deduplication, null handling, standardisation.
# MAGIC Silver is the trusted, analysis-ready layer - one row per real entity.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

BRONZE = "/Volumes/abet/bronze/delta"
SILVER = "/Volumes/abet/silver/delta"

# COMMAND ----------

# Step 1 - Deduplicate: keep the most recently ingested version of each record
def dedup(df, keys):
    w = Window.partitionBy(*keys).orderBy(F.col("ingestion_date").desc())
    return df.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")

courses = dedup(spark.read.format("delta").load(f"{BRONZE}/bronze_courses"), ["course_id"])
students = dedup(spark.read.format("delta").load(f"{BRONZE}/bronze_students"), ["student_id"])
grades = dedup(spark.read.format("delta").load(f"{BRONZE}/bronze_grades"), ["student_id", "course_id", "assessment_id"])

# COMMAND ----------

# Step 2 - Null handling: drop rows without a business key, fill safe defaults
courses = courses.filter(F.col("course_id").isNotNull())
students = students.filter(F.col("student_id").isNotNull())
grades = grades.filter(F.col("score").isNotNull()).fillna({"max_score": 20})

# COMMAND ----------

# Step 3 - Standardisation: trimmed/upper-cased codes, typed dates, score as %
courses = (courses
           .withColumn("course_code", F.upper(F.trim(F.col("course_code"))))
           .withColumn("programme", F.trim(F.col("programme"))))
students = (students
            .withColumn("student_name", F.trim(F.col("student_name")))
            .withColumn("programme", F.trim(F.col("programme"))))
grades = (grades
          .withColumn("score_pct", F.round(F.col("score") / F.col("max_score") * 100, 2))
          .withColumn("graded_date", F.to_date("graded_date")))

# COMMAND ----------

# Step 4 - Write the Silver Delta tables (overwrite: Silver is rebuilt clean)
courses.write.format("delta").mode("overwrite").save(f"{SILVER}/silver_courses")
students.write.format("delta").mode("overwrite").save(f"{SILVER}/silver_students")
grades.write.format("delta").mode("overwrite").save(f"{SILVER}/silver_grades")
print("Silver cleaning complete.")
