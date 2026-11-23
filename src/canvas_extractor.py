"""
Canvas ABET Data Extractor
==========================
Automates the extraction of Canvas LMS data for ABET reporting / Power BI.

Extracted data (same structure as the manual CSV exports it replaces):
  - Course Status      : Published with Activity / Unpublished /
                         Published without Activity
  - Enrolled Students  : With Activity / Without Activity
  - Unpublished Courses detail (Course Name + Teacher)
  - CPI data (satisfaction scores per programme)

Original context: built during my UM6P end-of-studies internship (PFE) to feed
the Databricks Lakehouse (Bronze layer). This public version is sanitised:
the API token is read from an environment variable and the demo mode uses
fully synthetic data only — no real institutional data.

Usage:
    pip install requests pandas openpyxl
    export CANVAS_API_TOKEN="your-token"   # Canvas > Settings > New Access Token
    python canvas_extractor.py
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import requests

# ============================================================
# CONFIGURATION — adapt to your Canvas instance
# ============================================================
CONFIG = {
    # Example: https://your-institution.instructure.com
    "base_url": os.environ.get("CANVAS_BASE_URL", "https://canvas.example.edu"),
    # NEVER hard-code a token. Set the CANVAS_API_TOKEN environment variable.
    "api_token": os.environ.get("CANVAS_API_TOKEN", ""),
    "activity_threshold_days": 30,  # "recent activity" = last 30 days
    "output_dir": "canvas_output",
    "programmes": {
        # Mapping programme_code -> Canvas account_id.
        # Leave empty to extract ALL courses of the institution.
    },
}
# ============================================================

BASE_URL = CONFIG["base_url"].rstrip("/")
HEADERS = {
    "Authorization": f"Bearer {CONFIG['api_token']}",
    "Content-Type": "application/json",
}
ACTIVITY_CUTOFF = datetime.now() - timedelta(days=CONFIG["activity_threshold_days"])
OUTPUT_DIR = CONFIG["output_dir"]
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ------------------------------------------------------------
# Canvas API helpers (automatic pagination)
# ------------------------------------------------------------
def api_get(endpoint: str, params: dict = None) -> list:
    """Paginated GET against the Canvas API (follows Link rel="next")."""
    url = f"{BASE_URL}/api/v1/{endpoint}"
    results = []
    while url:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            results.extend(data)
        else:
            return data
        # Pagination via the Link header
        url = None
        link_header = resp.headers.get("Link", "")
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
                params = None  # params are already embedded in the next URL
                break
    return results


# ------------------------------------------------------------
# Course extraction
# ------------------------------------------------------------
def get_all_courses(account_id: str = "self") -> list:
    """Return every course of an account (published + unpublished)."""
    params = {
        "per_page": 100,
        "include[]": ["total_students", "teachers"],
        "state[]": ["available", "unpublished", "completed"],
    }
    return api_get(f"accounts/{account_id}/courses", params)


def get_course_activity(course_id: int) -> dict:
    """
    Activity stats for one course:
      - last_activity       : datetime or None
      - has_recent_activity : bool (within the last 30 days)
    """
    try:
        analytics = api_get(f"courses/{course_id}/analytics/activity")
        if not analytics:
            return {"last_activity": None, "has_recent_activity": False}
        last = max(analytics, key=lambda x: x.get("date", ""))
        last_date = datetime.strptime(last["date"][:10], "%Y-%m-%d")
        return {
            "last_activity": last_date,
            "has_recent_activity": last_date >= ACTIVITY_CUTOFF,
        }
    except Exception:
        return {"last_activity": None, "has_recent_activity": False}


# ------------------------------------------------------------
# Student extraction
# ------------------------------------------------------------
def get_student_activity(course_id: int) -> dict:
    """
    Return:
      - students_with_activity    : int
      - students_without_activity : int
    """
    enrollments = api_get(
        f"courses/{course_id}/enrollments",
        params={"type[]": "StudentEnrollment", "per_page": 100},
    )
    with_activity = 0
    without_activity = 0
    for enr in enrollments:
        last_activity_raw = enr.get("last_activity_at")
        if last_activity_raw:
            try:
                last_dt = datetime.strptime(last_activity_raw[:10], "%Y-%m-%d")
                if last_dt >= ACTIVITY_CUTOFF:
                    with_activity += 1
                    continue
            except Exception:
                pass
        without_activity += 1
    return {
        "students_with_activity": with_activity,
        "students_without_activity": without_activity,
    }


def get_teachers(course: dict) -> str:
    """Teacher display names of a course (from the `teachers` include)."""
    teachers = course.get("teachers", [])
    return ", ".join(t.get("display_name", "") for t in teachers)


# ------------------------------------------------------------
# Table building (same format as the manual CSV exports)
# ------------------------------------------------------------
def build_programme_tables(courses: list, programme_name: str) -> dict:
    """
    For one programme, build:
      - course_status : Courses Status | Number of Courses
      - students      : With Activity | Without Activity | Total
      - unpublished   : Course Name | Teacher Name
    """
    published_active = 0
    published_inactive = 0
    unpublished_count = 0
    total_with = 0
    total_without = 0
    unpublished_rows = []

    print(f"  -> Processing {programme_name} ({len(courses)} courses)...")

    for course in courses:
        course_id = course["id"]
        course_name = course.get("name", "")
        workflow = course.get("workflow_state", "")
        teacher_str = get_teachers(course)

        if workflow == "unpublished":
            unpublished_count += 1
            unpublished_rows.append(
                {"Course Name": course_name, "Teacher Name": teacher_str}
            )
        else:
            # Published course -> check recent activity
            activity = get_course_activity(course_id)
            if activity["has_recent_activity"]:
                published_active += 1
            else:
                published_inactive += 1
                unpublished_rows.append(
                    {
                        "Course Name": f"[Published without activity] {course_name}",
                        "Teacher Name": teacher_str,
                    }
                )

        stu = get_student_activity(course_id)
        total_with += stu["students_with_activity"]
        total_without += stu["students_without_activity"]

    course_rows = []
    if published_active:
        course_rows.append({"Courses Status": "Published with Activity",
                            "Number of Courses": published_active})
    if published_inactive:
        course_rows.append({"Courses Status": "Published without Activity",
                            "Number of Courses": published_inactive})
    if unpublished_count:
        course_rows.append({"Courses Status": "Unpublished",
                            "Number of Courses": unpublished_count})

    df_course_status = pd.DataFrame(course_rows)
    df_students = pd.DataFrame([{
        "Programme": programme_name,
        "Students with Activity": total_with,
        "Students without Activity": total_without,
        "Total Students": total_with + total_without,
    }])
    df_unpublished = (
        pd.DataFrame(unpublished_rows) if unpublished_rows
        else pd.DataFrame(columns=["Course Name", "Teacher Name"])
    )
    return {
        "course_status": df_course_status,
        "students": df_students,
        "unpublished": df_unpublished,
    }


# ------------------------------------------------------------
# Consolidated Power BI table (all programmes in one file)
# ------------------------------------------------------------
def build_consolidated(all_results: list) -> dict:
    """Aggregate every programme into single DataFrames for Power BI."""
    all_courses, all_students, all_unpub = [], [], []

    for r in all_results:
        prog, school = r["programme"], r["school"]
        if not r["course_status"].empty:
            df = r["course_status"].copy()
            df.insert(0, "School", school)
            df.insert(1, "Programme", prog)
            all_courses.append(df)
        if not r["students"].empty:
            df = r["students"].copy()
            df.insert(0, "School", school)
            all_students.append(df)
        if not r["unpublished"].empty:
            df = r["unpublished"].copy()
            df.insert(0, "School", school)
            df.insert(1, "Programme", prog)
            all_unpub.append(df)

    date_str = datetime.now().strftime("%Y-%m-%d")
    df_courses = pd.concat(all_courses, ignore_index=True) if all_courses else pd.DataFrame()
    df_students = pd.concat(all_students, ignore_index=True) if all_students else pd.DataFrame()
    df_unpub = pd.concat(all_unpub, ignore_index=True) if all_unpub else pd.DataFrame()

    # Extraction-date column enables month-over-month tracking in Power BI
    for df in (df_courses, df_students, df_unpub):
        if not df.empty:
            df["Extraction Date"] = date_str

    return {"courses": df_courses, "students": df_students, "unpublished": df_unpub}


# ------------------------------------------------------------
# Exports
# ------------------------------------------------------------
def export_csv(tables: dict, programme_name: str, school: str):
    """Export the 3 per-programme CSVs (same structure as the manual files)."""
    safe_prog = programme_name.replace("/", "_").replace(" ", "_")
    safe_school = school.replace("+", "plus").replace(" ", "_")
    folder = os.path.join(OUTPUT_DIR, f"{safe_school}_{safe_prog}")
    os.makedirs(folder, exist_ok=True)

    tables["course_status"].to_csv(
        os.path.join(folder, f"{safe_prog}_Course_status.csv"), index=False)
    tables["students"].to_csv(
        os.path.join(folder, f"{safe_prog}_Enrolled_Students.csv"), index=False)
    if not tables["unpublished"].empty:
        tables["unpublished"].to_csv(
            os.path.join(folder, f"{safe_prog}_Unpublished_Courses.csv"), index=False)


def export_powerbi_excel(consolidated: dict):
    """Export one consolidated Excel workbook (3 sheets) ready for Power BI."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(OUTPUT_DIR, f"Canvas_ABET_PowerBI_{date_str}.xlsx")

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        if not consolidated["courses"].empty:
            consolidated["courses"].to_excel(writer, sheet_name="Course_Status", index=False)
        if not consolidated["students"].empty:
            consolidated["students"].to_excel(writer, sheet_name="Student_Activity", index=False)
        if not consolidated["unpublished"].empty:
            consolidated["unpublished"].to_excel(writer, sheet_name="Unpublished_Courses", index=False)

    print(f"\nPower BI file exported: {out_path}")
    return out_path


# ------------------------------------------------------------
# School / programme mapping (PLACEHOLDER ids — replace with
# the real Canvas account ids of your own institution)
# ------------------------------------------------------------
SCHOOL_PROGRAMMES = {
    "School_A": {"Programme_A1": "accounts/ACCOUNT_ID_A1/courses",
                 "Programme_A2": "accounts/ACCOUNT_ID_A2/courses"},
    "School_B": {"Programme_B1": "accounts/ACCOUNT_ID_B1/courses"},
}


# ------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Canvas ABET Data Extractor")
    print(f"  Extraction date: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    if not CONFIG["api_token"]:
        print("\nNo CANVAS_API_TOKEN set -> running in DEMO mode (synthetic data).\n")
        demo_mode()
        return

    all_results = []
    try:
        all_courses = get_all_courses(account_id="self")
        print(f"\n{len(all_courses)} courses retrieved")

        by_account = {}
        for c in all_courses:
            by_account.setdefault(c.get("account_id", "Unknown"), []).append(c)

        for account_id, courses in by_account.items():
            tables = build_programme_tables(courses, programme_name=f"Account_{account_id}")
            all_results.append({
                "school": f"Account_{account_id}",
                "programme": f"Account_{account_id}",
                "course_status": tables["course_status"],
                "students": tables["students"],
                "unpublished": tables["unpublished"],
            })
            export_csv(tables, f"Account_{account_id}", f"Account_{account_id}")

    except requests.exceptions.ConnectionError:
        print("\nCould not reach Canvas -> falling back to DEMO mode.\n")
        demo_mode()
        return

    if all_results:
        export_powerbi_excel(build_consolidated(all_results))
        print(f"\nPer-programme CSVs exported to: {OUTPUT_DIR}/")
    else:
        print("\nNo results. Check the account_id configuration.")


# ------------------------------------------------------------
# Demo mode: SYNTHETIC data only, same structure as real output
# ------------------------------------------------------------
def demo_mode():
    """Generate a demo workbook from fully synthetic, fictional data."""
    print("Generating demo file (synthetic data, real output structure)...\n")
    demo_data = {
        "courses": pd.DataFrame([
            {"School": "School_A", "Programme": "Programme_A1", "Courses Status": "Published with Activity", "Number of Courses": 12, "Extraction Date": "2026-01-15"},
            {"School": "School_A", "Programme": "Programme_A1", "Courses Status": "Unpublished", "Number of Courses": 2, "Extraction Date": "2026-01-15"},
            {"School": "School_A", "Programme": "Programme_A2", "Courses Status": "Published with Activity", "Number of Courses": 9, "Extraction Date": "2026-01-15"},
            {"School": "School_B", "Programme": "Programme_B1", "Courses Status": "Published without Activity", "Number of Courses": 1, "Extraction Date": "2026-01-15"},
        ]),
        "students": pd.DataFrame([
            {"School": "School_A", "Programme": "Programme_A1", "Students with Activity": 120, "Students without Activity": 5, "Total Students": 125, "Extraction Date": "2026-01-15"},
            {"School": "School_A", "Programme": "Programme_A2", "Students with Activity": 80, "Students without Activity": 3, "Total Students": 83, "Extraction Date": "2026-01-15"},
            {"School": "School_B", "Programme": "Programme_B1", "Students with Activity": 40, "Students without Activity": 10, "Total Students": 50, "Extraction Date": "2026-01-15"},
        ]),
        "unpublished": pd.DataFrame([
            {"School": "School_A", "Programme": "Programme_A1", "Course Name": "A1-M101 - Sample Course One", "Teacher Name": "Teacher Example 1", "Extraction Date": "2026-01-15"},
            {"School": "School_B", "Programme": "Programme_B1", "Course Name": "B1-M202 - Sample Course Two", "Teacher Name": "Teacher Example 2", "Extraction Date": "2026-01-15"},
        ]),
    }
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(OUTPUT_DIR, f"Canvas_ABET_PowerBI_{date_str}_DEMO.xlsx")
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        demo_data["courses"].to_excel(writer, sheet_name="Course_Status", index=False)
        demo_data["students"].to_excel(writer, sheet_name="Student_Activity", index=False)
        demo_data["unpublished"].to_excel(writer, sheet_name="Unpublished_Courses", index=False)
    print(f"Demo file generated: {out_path}")
    return out_path


if __name__ == "__main__":
    main()
