"""
================================================================================
  Chat Analytics Dashboard — Python Flask API  (FULLY DYNAMIC VERSION)
  File: app.py

  NEW ENDPOINTS ADDED:
  ────────────────────
  GET /api/config?websiteId=5578          ← metric config (labels, categories)
  GET /api/topnconfig?websiteId=5578      ← top-n list config (labels, format)
  GET /api/stats?websiteId=5578&yearMonth=2026-03
  GET /api/websites
  GET /api/months?websiteId=5578
  GET /api/health
================================================================================
"""

import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import pyodbc
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

# ════════════════════════════════════════════════════════════════
#  ⚠  EDIT THESE WITH YOUR SQL SERVER DETAILS
# ════════════════════════════════════════════════════════════════
SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")
SQL_TRUSTED = os.getenv("SQL_TRUSTED", "false").lower() == "true"
SQL_USERNAME = os.getenv("SQL_USERNAME")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
SQL_ENCRYPT = os.getenv("SQL_ENCRYPT", "yes")
SQL_TRUST_CERT = os.getenv("SQL_TRUST_SERVER_CERTIFICATE", "yes")
# ════════════════════════════════════════════════════════════════


def get_connection():
    if not SQL_SERVER or not SQL_DATABASE:
        raise RuntimeError("SQL_SERVER and SQL_DATABASE are required environment variables.")
    if not SQL_TRUSTED and (not SQL_USERNAME or not SQL_PASSWORD):
        raise RuntimeError("SQL_USERNAME and SQL_PASSWORD are required when SQL_TRUSTED=false.")

    if SQL_TRUSTED:
        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};Trusted_Connection=yes;"
            f"Encrypt={SQL_ENCRYPT};TrustServerCertificate={SQL_TRUST_CERT};"
        )
    else:
        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
            f"UID={SQL_USERNAME};PWD={SQL_PASSWORD};"
            f"Encrypt={SQL_ENCRYPT};TrustServerCertificate={SQL_TRUST_CERT};"
        )
    return pyodbc.connect(conn_str, timeout=30)


def rows_to_list(cursor):
    """Convert all rows to list of dicts."""
    columns = [col[0] for col in cursor.description]
    results = []
    for row in cursor.fetchall():
        d = {}
        for col, val in zip(columns, row):
            d[col] = float(val) if hasattr(val, '__float__') else val
        results.append(d)
    return results


def row_to_dict(cursor, row):
    """Convert single row to dict."""
    columns = [col[0] for col in cursor.description]
    return {
        col: (float(val) if hasattr(val, '__float__') else val)
        for col, val in zip(columns, row)
    }


# ──────────────────────────────────────────────────────────────
#  GET /api/health
# ──────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    try:
        conn = get_connection()
        conn.cursor().execute("SELECT 1")
        conn.close()
        return jsonify({"status": "ok", "db": "connected"})
    except Exception as e:
        return jsonify({"status": "error", "db": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  GET /api/websites
#  Returns all website IDs that have processed data
# ──────────────────────────────────────────────────────────────
@app.route("/api/websites")
def get_websites():
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT WebsiteId
            FROM dbo.WebsiteStatsSummary
            ORDER BY WebsiteId
        """)
        ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        return jsonify(ids)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  GET /api/months?websiteId=5578
#  Returns available months for a website
# ──────────────────────────────────────────────────────────────
@app.route("/api/months")
def get_months():
    website_id = request.args.get("websiteId", "5578")
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT YearMonth
            FROM dbo.WebsiteStatsSummary
            WHERE WebsiteId = ?
            ORDER BY YearMonth DESC
        """, int(website_id))
        months = [row[0] for row in cursor.fetchall()]
        conn.close()
        return jsonify(months)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  GET /api/config?websiteId=5578
#
#  Reads WebsiteMetricConfig for this website.
#  Returns every active metric with its label, category,
#  aggtype and outputcolumn — the dashboard uses this to
#  know what panels to draw and how to label each metric.
#
#  Example response:
#  [
#    { "ShortCol":"total_chats", "MetricLabel":"TotalChats",
#      "MetricCategory":"Volume", "AggType":"NUM",
#      "OutputColumn":"RAW_TRUE", "SortOrder":1 },
#    ...
#  ]
# ──────────────────────────────────────────────────────────────
@app.route("/api/config")
def get_config():
    website_id = request.args.get("websiteId", "5578")
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ShortCol,
                MetricLabel,
                MetricCategory,
                AggType,
                OutputColumn,
                SortOrder
            FROM dbo.WebsiteMetricConfig
            WHERE WebsiteId = ?
              AND IsActive   = 1
             AND isoutputvisible=1
            ORDER BY SortOrder, MetricLabel
        """, int(website_id))
        rows = rows_to_list(cursor)
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  GET /api/topnconfig?websiteId=5578
#
#  Reads WebsiteTopNConfig for this website.
#  Returns every active top-N list with its label and format.
#  Dashboard uses this to know which lists to show and how
#  to format each one (VALUE_ONLY / VALUE_COUNT / VALUE_DASH).
#
#  Example response:
#  [
#    { "ListType":"Sentiment", "ListLabel":"SentimentSummaryList",
#      "FormatMode":"VALUE_DASH", "SortOrder":1 },
#    ...
#  ]
# ──────────────────────────────────────────────────────────────
@app.route("/api/topnconfig")
def get_topn_config():
    website_id = request.args.get("websiteId", "5578")
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ListType,
                ListLabel,
                FormatMode,
                TopN,
                SortOrder
            FROM dbo.WebsiteTopNConfig
            WHERE WebsiteId = ?
              AND IsActive   = 1
            ORDER BY SortOrder
        """, int(website_id))
        rows = rows_to_list(cursor)
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  GET /api/stats?websiteId=5578&yearMonth=2026-03
#
#  Calls usp_GetWebsiteStatsWide and returns the wide row.
#  Also returns raw TopN rows from WebsiteStatsTopN so the
#  dashboard can render each list properly.
#
#  Response shape:
#  {
#    "metrics": { "TotalChats":169, "QualifiedOpportunity":132, ... },
#    "topn":    { "Sentiment":[{"ItemValue":"neutral","ItemCount":92}, ...],
#                 "City":     [...],
#                 "FAQ":      [...],
#                 ... }
#  }
# ──────────────────────────────────────────────────────────────
@app.route("/api/stats")
def get_stats():
    website_id = request.args.get("websiteId", "5578")
    year_month = request.args.get("yearMonth", "2026-03")

    if not website_id.isdigit():
        return jsonify({"error": "websiteId must be a number"}), 400
    if len(year_month) != 7 or year_month[4] != "-":
        return jsonify({"error": "yearMonth must be yyyy-MM"}), 400

    try:
        conn   = get_connection()
        cursor = conn.cursor()

        # ── 1. Call the wide procedure (gets flat metric row) ──
        cursor.execute(
            "EXEC dbo.sp_GetWebsiteStats @WebsiteId=?, @YearMonth=?",
            int(website_id), year_month
        )
        row = cursor.fetchone()
        if row is None:
            conn.close()
            return jsonify({
                "error": f"No data for WebsiteId={website_id} "
                         f"YearMonth={year_month}. "
                         f"Run usp_ProcessWebsiteStats first."
            }), 404

        metrics = row_to_dict(cursor, row)

        # ── 2. Get raw TopN rows (structured, not comma strings) ──
        # Some stored procs return extra result sets; skip them if present.
        while cursor.nextset():
            pass
        cursor.execute("""
            SELECT ListType, ItemValue, ItemCount, Rank
            FROM dbo.WebsiteStatsTopN
            WHERE WebsiteId = ?
              AND YearMonth  = ?
            ORDER BY ListType, Rank
        """, int(website_id), year_month)

        topn_raw  = rows_to_list(cursor)
        topn_dict = {}
        for item in topn_raw:
            lt = item["ListType"]
            if lt not in topn_dict:
                topn_dict[lt] = []
            topn_dict[lt].append({
                "ItemValue": item["ItemValue"],
                "ItemCount": int(item["ItemCount"]) if item["ItemCount"] else 0,
                "Rank":      int(item["Rank"])      if item["Rank"]      else 0
            })

        conn.close()
        return jsonify({"metrics": metrics, "topn": topn_dict})

    except pyodbc.Error as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


if __name__ == "__main__":
    print("\n" + "="*55)
    print("  Chat Analytics API  —  FULLY DYNAMIC")
    print(f"  Server:   {SQL_SERVER}")
    print(f"  Database: {SQL_DATABASE}")
    print(f"  Auth:     {'Windows' if SQL_TRUSTED else 'SQL'}")
    print("  URL:      http://localhost:5000")
    print("  Endpoints:")
    print("    /api/health")
    print("    /api/websites")
    print("    /api/months?websiteId=")
    print("    /api/config?websiteId=")
    print("    /api/topnconfig?websiteId=")
    print("    /api/stats?websiteId=&yearMonth=")
    print("="*55 + "\n")
    app.run(debug=True, port=5000)
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import pyodbc
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
CORS(app, resources={r"/api/*": {"origins": [origin.strip() for origin in CORS_ORIGINS.split(",")]}})

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")
SQL_TRUSTED = os.getenv("SQL_TRUSTED", "false").lower() == "true"
SQL_USERNAME = os.getenv("SQL_USERNAME")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
SQL_ENCRYPT = os.getenv("SQL_ENCRYPT", "yes")
SQL_TRUST_CERT = os.getenv("SQL_TRUST_SERVER_CERTIFICATE", "yes")


def validate_config():
    missing = [k for k, v in {
        "SQL_SERVER": SQL_SERVER,
        "SQL_DATABASE": SQL_DATABASE,
    }.items() if not v]
    if not SQL_TRUSTED:
        for k, v in {"SQL_USERNAME": SQL_USERNAME, "SQL_PASSWORD": SQL_PASSWORD}.items():
            if not v:
                missing.append(k)
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(sorted(set(missing)))}"
        )


def get_connection():
    validate_config()
    if SQL_TRUSTED:
        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
            f"Trusted_Connection=yes;"
            f"Encrypt={SQL_ENCRYPT};TrustServerCertificate={SQL_TRUST_CERT};"
        )
    else:
        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
            f"UID={SQL_USERNAME};PWD={SQL_PASSWORD};"
            f"Encrypt={SQL_ENCRYPT};TrustServerCertificate={SQL_TRUST_CERT};"
        )
    return pyodbc.connect(conn_str, timeout=30)


def rows_to_list(cursor):
    """Convert all rows to list of dicts."""
    columns = [col[0] for col in cursor.description]
    results = []
    for row in cursor.fetchall():
        d = {}
        for col, val in zip(columns, row):
            d[col] = float(val) if hasattr(val, '__float__') else val
        results.append(d)
    return results


def row_to_dict(cursor, row):
    """Convert single row to dict."""
    columns = [col[0] for col in cursor.description]
    return {
        col: (float(val) if hasattr(val, '__float__') else val)
        for col, val in zip(columns, row)
    }


# ──────────────────────────────────────────────────────────────
#  GET /api/health
# ──────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    try:
        conn = get_connection()
        conn.cursor().execute("SELECT 1")
        conn.close()
        return jsonify({"status": "ok", "db": "connected"})
    except Exception as e:
        return jsonify({"status": "error", "db": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  GET /api/websites
#  Returns all website IDs that have processed data
# ──────────────────────────────────────────────────────────────
@app.route("/api/websites")
def get_websites():
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT WebsiteId
            FROM dbo.WebsiteStatsSummary
            ORDER BY WebsiteId
        """)
        ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        return jsonify(ids)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  GET /api/months?websiteId=5578
#  Returns available months for a website
# ──────────────────────────────────────────────────────────────
@app.route("/api/months")
def get_months():
    website_id = request.args.get("websiteId", "5578")
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT YearMonth
            FROM dbo.WebsiteStatsSummary
            WHERE WebsiteId = ?
            ORDER BY YearMonth DESC
        """, int(website_id))
        months = [row[0] for row in cursor.fetchall()]
        conn.close()
        return jsonify(months)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  GET /api/config?websiteId=5578
#
#  Reads WebsiteMetricConfig for this website.
#  Returns every active metric with its label, category,
#  aggtype and outputcolumn — the dashboard uses this to
#  know what panels to draw and how to label each metric.
#
#  Example response:
#  [
#    { "ShortCol":"total_chats", "MetricLabel":"TotalChats",
#      "MetricCategory":"Volume", "AggType":"NUM",
#      "OutputColumn":"RAW_TRUE", "SortOrder":1 },
#    ...
#  ]
# ──────────────────────────────────────────────────────────────
@app.route("/api/config")
def get_config():
    website_id = request.args.get("websiteId", "5578")
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ShortCol,
                MetricLabel,
                MetricCategory,
                AggType,
                OutputColumn,
                SortOrder
            FROM dbo.WebsiteMetricConfig
            WHERE WebsiteId = ?
              AND IsActive   = 1
             AND isoutputvisible=1
            ORDER BY SortOrder, MetricLabel
        """, int(website_id))
        rows = rows_to_list(cursor)
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  GET /api/topnconfig?websiteId=5578
#
#  Reads WebsiteTopNConfig for this website.
#  Returns every active top-N list with its label and format.
#  Dashboard uses this to know which lists to show and how
#  to format each one (VALUE_ONLY / VALUE_COUNT / VALUE_DASH).
#
#  Example response:
#  [
#    { "ListType":"Sentiment", "ListLabel":"SentimentSummaryList",
#      "FormatMode":"VALUE_DASH", "SortOrder":1 },
#    ...
#  ]
# ──────────────────────────────────────────────────────────────
@app.route("/api/topnconfig")
def get_topn_config():
    website_id = request.args.get("websiteId", "5578")
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ListType,
                ListLabel,
                FormatMode,
                TopN,
                SortOrder
            FROM dbo.WebsiteTopNConfig
            WHERE WebsiteId = ?
              AND IsActive   = 1
            ORDER BY SortOrder
        """, int(website_id))
        rows = rows_to_list(cursor)
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  GET /api/stats?websiteId=5578&yearMonth=2026-03
#
#  Calls usp_GetWebsiteStatsWide and returns the wide row.
#  Also returns raw TopN rows from WebsiteStatsTopN so the
#  dashboard can render each list properly.
#
#  Response shape:
#  {
#    "metrics": { "TotalChats":169, "QualifiedOpportunity":132, ... },
#    "topn":    { "Sentiment":[{"ItemValue":"neutral","ItemCount":92}, ...],
#                 "City":     [...],
#                 "FAQ":      [...],
#                 ... }
#  }
# ──────────────────────────────────────────────────────────────
@app.route("/api/stats")
def get_stats():
    website_id = request.args.get("websiteId", "5578")
    year_month = request.args.get("yearMonth", "2026-03")

    if not website_id.isdigit():
        return jsonify({"error": "websiteId must be a number"}), 400
    if len(year_month) != 7 or year_month[4] != "-":
        return jsonify({"error": "yearMonth must be yyyy-MM"}), 400

    try:
        conn   = get_connection()
        cursor = conn.cursor()

        # ── 1. Call the wide procedure (gets flat metric row) ──
        cursor.execute(
            "EXEC dbo.sp_GetWebsiteStats @WebsiteId=?, @YearMonth=?",
            int(website_id), year_month
        )
        row = cursor.fetchone()
        if row is None:
            conn.close()
            return jsonify({
                "error": f"No data for WebsiteId={website_id} "
                         f"YearMonth={year_month}. "
                         f"Run usp_ProcessWebsiteStats first."
            }), 404

        metrics = row_to_dict(cursor, row)

        # ── 2. Get raw TopN rows (structured, not comma strings) ──
        # Some stored procs return extra result sets; skip them if present.
        while cursor.nextset():
            pass
        cursor.execute("""
            SELECT ListType, ItemValue, ItemCount, Rank
            FROM dbo.WebsiteStatsTopN
            WHERE WebsiteId = ?
              AND YearMonth  = ?
            ORDER BY ListType, Rank
        """, int(website_id), year_month)

        topn_raw  = rows_to_list(cursor)
        topn_dict = {}
        for item in topn_raw:
            lt = item["ListType"]
            if lt not in topn_dict:
                topn_dict[lt] = []
            topn_dict[lt].append({
                "ItemValue": item["ItemValue"],
                "ItemCount": int(item["ItemCount"]) if item["ItemCount"] else 0,
                "Rank":      int(item["Rank"])      if item["Rank"]      else 0
            })

        conn.close()
        return jsonify({"metrics": metrics, "topn": topn_dict})

    except pyodbc.Error as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  Chat Analytics API  —  PRODUCTION READY")
    print(f"  Server:   {SQL_SERVER or '(not set)'}")
    print(f"  Database: {SQL_DATABASE or '(not set)'}")
    print(f"  Auth:     {'Windows' if SQL_TRUSTED else 'SQL'}")
    print("  URL:      http://localhost:5000")
    print("  Endpoints:")
    print("    /api/health")
    print("    /api/websites")
    print("    /api/months?websiteId=")
    print("    /api/config?websiteId=")
    print("    /api/topnconfig?websiteId=")
    print("    /api/stats?websiteId=&yearMonth=")
    print("=" * 55 + "\n")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
