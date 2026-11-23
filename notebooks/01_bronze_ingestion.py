# Databricks notebook source
# MAGIC %md
# MAGIC # 01 - Bronze Ingestion
# MAGIC Raw Canvas extracts land in Bronze exactly as extracted - no transformation,
# MAGIC so the raw history is always reproducible. Format: Delta Lake.

# COMMAND ----------

from pyspark.sql import functions as F

RAW_PATH = "/Volumes/abet/bronze/canvas_extracts"   # CSV files from src/canvas_extractor.py
BRONZE_PATH = "/Volumes/abet/bronze/delta"

# COMMAND ----------

# Step 1 - Read the raw CSV extracts (courses, students, grades)
courses_raw = spark.read.option("header", True).option("inferSchema", True).csv(f"{RAW_PATH}/courses.csv")
students_raw = spark.read.option("header", True).option("inferSchema", True).csv(f"{RAW_PATH}/students.csv")
grades_raw = spark.read.option("header", True).option("inferSchema", True).csv(f"{RAW_PATH}/grades.csv")

# COMMAND ----------

# Step 2 - Stamp each row with ingestion metadata, then write Delta as-is
def to_bronze(df, table):
    (df.withColumn("ingestion_date", F.current_date())
       .withColumn("source_file", F.lit("canvas_extractor"))
       .write.format("delta").mode("append").save(f"{BRONZE_PATH}/{table}"))

to_bronze(courses_raw, "bronze_courses")
to_bronze(students_raw, "bronze_students")
to_bronze(grades_raw, "bronze_grades")
print("Bronze ingestion complete.")
