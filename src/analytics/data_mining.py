"""Reproducible, history-preserving exploratory data-mining models.

The module deliberately keeps model outputs separate from certified BI metrics.
Each successful invocation appends a model run and marks one run per model type
as current; dashboards read the ``analytics.current_*`` views.
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from itertools import combinations
from math import ceil
from uuid import uuid4

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import RobustScaler


sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

MIN_COMPLETED_SHIFTS = 10
K_CANDIDATES = range(2, 9)
KMEANS_SEEDS = (17, 29, 42, 61, 73)
OUTLIER_LOWER_QUANTILE = 0.01
OUTLIER_UPPER_QUANTILE = 0.99
MIN_CLUSTER_SHARE = 0.02
RULE_MIN_SUPPORT = 0.005
RULE_MIN_CONFIDENCE = 0.2
RULE_MIN_LIFT = 1.1
RULE_MIN_ANTECEDENT_COUNT = 50
RULE_MIN_STABILITY = 0.70
RULE_SAMPLE_PER_STRATUM = 500
MAX_PUBLISHED_RULES = 100


def read_sql_quietly(query, conn):
    """Read SQL without the pandas warning emitted for psycopg2 connections."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="pandas only supports SQLAlchemy connectable.*", category=UserWarning
        )
        return pd.read_sql(query, conn)


def format_item(item):
    prefix_map = {
        "pb:": "pickup_borough", "pz:": "pickup_zone", "db:": "dropoff_borough",
        "dz:": "dropoff_zone", "hb:": "hour_bucket", "dn:": "day_name",
        "dt:": "day_type", "vn:": "vendor",
    }
    for prefix, label in prefix_map.items():
        if item.startswith(prefix):
            return f"{label}={item[len(prefix):]}"
    return item


def format_rule_string(items):
    return ", ".join(format_item(item) for item in sorted(items))


def rule_dimension_fields(antecedent, consequent):
    """Expose filterable dimensions alongside readable rule text."""
    fields = {
        "antecedent_pickup_borough": None, "antecedent_pickup_zone": None,
        "antecedent_hour_bucket": None, "antecedent_day_type": None,
        "antecedent_vendor": None, "consequent_dropoff_borough": None,
        "consequent_dropoff_zone": None,
    }
    antecedent_prefixes = {
        "pb:": "antecedent_pickup_borough", "pz:": "antecedent_pickup_zone",
        "hb:": "antecedent_hour_bucket", "dt:": "antecedent_day_type",
        "vn:": "antecedent_vendor",
    }
    consequent_prefixes = {"db:": "consequent_dropoff_borough", "dz:": "consequent_dropoff_zone"}
    for item in antecedent:
        for prefix, field in antecedent_prefixes.items():
            if item.startswith(prefix):
                fields[field] = item[len(prefix):]
                break
    for prefix, field in consequent_prefixes.items():
        if consequent.startswith(prefix):
            fields[field] = consequent[len(prefix):]
            break
    return fields


def _support_map(transactions, min_support):
    """Frequent itemsets through size three; the configured Apriori scope."""
    n = len(transactions)
    counts_1 = {}
    for transaction in transactions:
        for item in set(transaction):
            counts_1[item] = counts_1.get(item, 0) + 1
    frequent_1 = {item for item, count in counts_1.items() if count / n >= min_support}
    support = {frozenset((item,)): count / n for item, count in counts_1.items() if item in frequent_1}
    for size in (2, 3):
        counts = {}
        for transaction in transactions:
            items = sorted(set(transaction).intersection(frequent_1))
            for candidate_tuple in combinations(items, size):
                candidate = frozenset(candidate_tuple)
                if size == 3 and any(frozenset(pair) not in support for pair in combinations(candidate, 2)):
                    continue
                counts[candidate] = counts.get(candidate, 0) + 1
        support.update({candidate: count / n for candidate, count in counts.items() if count / n >= min_support})
    return support


def _prune_redundant_rules(rules):
    """Remove a more-specific rule when its subset has comparable confidence."""
    retained = []
    for rule in sorted(rules, key=lambda item: (len(item["antecedent_items"]), -item["confidence"], -item["support"])):
        antecedent = rule["antecedent_items"]
        redundant = any(
            kept["consequent_item"] == rule["consequent_item"]
            and kept["antecedent_items"] < antecedent
            and kept["confidence"] >= rule["confidence"] - 0.02
            for kept in retained
        )
        if not redundant:
            retained.append(rule)
    return retained


def run_apriori(transactions, min_support=RULE_MIN_SUPPORT, min_confidence=RULE_MIN_CONFIDENCE,
                min_lift=RULE_MIN_LIFT, min_antecedent_count=1):
    """Generate pickup/time -> dropoff rules, retaining raw values for validation."""
    transactions = [set(transaction) for transaction in transactions if transaction]
    if not transactions:
        return []
    n = len(transactions)
    support_dict = _support_map(transactions, min_support)
    rules = []
    for itemset, support in support_dict.items():
        if len(itemset) < 2:
            continue
        for item in itemset:
            if not item.startswith(("db:", "dz:")):
                continue
            consequent = frozenset((item,))
            antecedent = itemset - consequent
            if any(value.startswith(("db:", "dz:")) for value in antecedent):
                continue
            antecedent_support = support_dict.get(antecedent)
            consequent_support = support_dict.get(consequent)
            if not antecedent_support or not consequent_support:
                continue
            antecedent_count = round(antecedent_support * n)
            confidence = support / antecedent_support
            lift = confidence / consequent_support
            if (confidence < min_confidence or lift < min_lift or antecedent_count < min_antecedent_count):
                continue
            rules.append({
                "antecedent": format_rule_string(antecedent), "consequent": format_item(item),
                "support": support, "confidence": confidence, "lift": lift,
                "antecedent_support": antecedent_support, "consequent_support": consequent_support,
                "antecedent_count": antecedent_count, "antecedent_items": frozenset(antecedent),
                "consequent_item": item, **rule_dimension_fields(antecedent, item),
            })
    return sorted(_prune_redundant_rules(rules), key=lambda item: (-item["lift"], -item["support"]))


def _rule_confidence(transactions, antecedent, consequent):
    matching = [basket for basket in transactions if antecedent.issubset(basket)]
    if not matching:
        return 0.0
    return sum((consequent in basket) for basket in matching) / len(matching)


def _score_rule_stability(rules, transactions, timestamps):
    """Score confidence repeatability across chronological halves of the sample."""
    midpoint = pd.Series(timestamps).median()
    first = [basket for basket, stamp in zip(transactions, timestamps) if stamp <= midpoint]
    second = [basket for basket, stamp in zip(transactions, timestamps) if stamp > midpoint]
    for rule in rules:
        first_conf = _rule_confidence(first, rule["antecedent_items"], rule["consequent_item"])
        second_conf = _rule_confidence(second, rule["antecedent_items"], rule["consequent_item"])
        rule["stability_score"] = 1.0 - abs(first_conf - second_conf)
    return rules


def _publish_model_run(cur, model_type, model_run_id, model_run_at, training_start, training_end,
                       input_row_count, eligible_row_count, sample_method, parameters, metrics):
    cur.execute("UPDATE analytics.model_runs SET is_current = FALSE WHERE model_type = %s AND is_current", (model_type,))
    cur.execute("""
        INSERT INTO analytics.model_runs (
            model_run_id, model_type, status, model_run_at, training_start, training_end,
            input_row_count, eligible_row_count, sample_method, parameters, evaluation_metrics, is_current
        ) VALUES (%s, %s, 'SUCCEEDED', %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, TRUE)
    """, (str(model_run_id), model_type, model_run_at, training_start, training_end,
          input_row_count, eligible_row_count, sample_method, json.dumps(parameters, sort_keys=True),
          json.dumps(metrics, sort_keys=True)))


def run_driver_segmentation(conn) -> int:
    """Fit a robust K-Means model after eligibility, clipping and model selection."""
    print("Running Driver Segmentation using K-Means model selection...")
    query = """
    WITH driver_trips AS (
        SELECT driver_key, AVG(trip_distance) AS average_trip_distance,
               SUM(tip_amount) / NULLIF(COUNT(trip_id), 0) AS tips_per_trip
        FROM analytics.trip_pickup GROUP BY driver_key
    ), driver_shifts AS (
        SELECT driver_key, driver_id, driver_name, COUNT(shift_id) AS completed_shifts,
               SUM(trip_count)::numeric / NULLIF(COUNT(shift_id), 0) AS trips_per_shift,
               SUM(total_revenue) * 60 / NULLIF(SUM(shift_duration_minutes), 0) AS revenue_per_hour,
               SUM(occupied_minutes) / NULLIF(SUM(shift_duration_minutes), 0) AS utilization_rate,
               SUM(idle_minutes)::numeric / NULLIF(COUNT(shift_id), 0) AS idle_minutes_per_shift
        FROM analytics.shift GROUP BY driver_key, driver_id, driver_name
    )
    SELECT s.driver_key, s.driver_id, s.driver_name, s.completed_shifts,
           COALESCE(s.trips_per_shift, 0)::float AS trips_per_shift,
           COALESCE(s.revenue_per_hour, 0)::float AS revenue_per_hour,
           COALESCE(s.utilization_rate, 0)::float AS utilization_rate,
           COALESCE(s.idle_minutes_per_shift, 0)::float AS idle_minutes_per_shift,
           COALESCE(t.average_trip_distance, 0)::float AS average_trip_distance,
           COALESCE(t.tips_per_trip, 0)::float AS tips_per_trip
    FROM driver_shifts s LEFT JOIN driver_trips t ON s.driver_key = t.driver_key
    """
    raw_df = read_sql_quietly(query, conn)
    df = raw_df.loc[raw_df["completed_shifts"] >= MIN_COMPLETED_SHIFTS].copy()
    features = ["revenue_per_hour", "utilization_rate", "trips_per_shift", "average_trip_distance",
                "tips_per_trip", "idle_minutes_per_shift", "completed_shifts"]
    if len(df) < 3:
        print(f"Only {len(df)} eligible drivers; at least 3 are required. Skipping driver clustering.")
        return 0
    values = df[features].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    lower = values.quantile(OUTLIER_LOWER_QUANTILE)
    upper = values.quantile(OUTLIER_UPPER_QUANTILE)
    clipped = values.clip(lower=lower, upper=upper, axis=1)
    scaled = RobustScaler().fit_transform(clipped)
    min_cluster_size = max(5, ceil(len(df) * MIN_CLUSTER_SHARE))
    candidates = []
    for k in K_CANDIDATES:
        if k >= len(df):
            continue
        labels = KMeans(n_clusters=k, random_state=42, n_init=20).fit_predict(scaled)
        if np.bincount(labels).min() < min_cluster_size:
            continue
        candidates.append({"k": k, "labels": labels, "silhouette": float(silhouette_score(scaled, labels)),
                           "davies_bouldin": float(davies_bouldin_score(scaled, labels)),
                           "calinski_harabasz": float(calinski_harabasz_score(scaled, labels))})
    if not candidates:
        print("No candidate K satisfies the minimum cluster-size guardrail. Skipping driver clustering.")
        return 0
    selected = sorted(candidates, key=lambda item: (-item["silhouette"], item["davies_bouldin"], item["k"]))[0]
    stability = [adjusted_rand_score(selected["labels"], KMeans(n_clusters=selected["k"], random_state=seed, n_init=20).fit_predict(scaled)) for seed in KMEANS_SEEDS]
    df["cluster_id"] = selected["labels"]
    ranks = df.groupby("cluster_id")["revenue_per_hour"].mean().rank(method="dense", ascending=False).astype(int)
    df["segment_label"] = df["cluster_id"].map(lambda cluster: f"Revenue profile rank {ranks.loc[cluster]} of {selected['k']}")
    with conn.cursor() as cur:
        cur.execute("SELECT MIN(shift_start)::date, MAX(shift_start)::date FROM analytics.shift")
        training_start, training_end = cur.fetchone()
        model_run_id, model_run_at = uuid4(), datetime.now(timezone.utc)
        _publish_model_run(cur, "DRIVER_SEGMENTATION", model_run_id, model_run_at, training_start, training_end,
                           len(raw_df), len(df), "all eligible drivers", {
                               "features": features, "missing_value_policy": "zero for no observed trip metric; infinities replaced with zero",
                               "scaler": "RobustScaler", "outlier_clip_quantiles": [OUTLIER_LOWER_QUANTILE, OUTLIER_UPPER_QUANTILE],
                               "k_candidates": list(K_CANDIDATES), "minimum_completed_shifts": MIN_COMPLETED_SHIFTS,
                               "minimum_cluster_size": min_cluster_size, "selection_metric": "maximum silhouette; tie: minimum Davies-Bouldin, then lower k",
                           }, {"silhouette": selected["silhouette"], "davies_bouldin": selected["davies_bouldin"],
                               "calinski_harabasz": selected["calinski_harabasz"], "stability_ari": float(np.mean(stability)),
                               "stability_seed_count": len(KMEANS_SEEDS), "selected_k": selected["k"]})
        insert = """INSERT INTO analytics.driver_segments (
            driver_key, driver_id, driver_name, completed_shifts, trips_per_shift, revenue_per_hour,
            utilization_rate, idle_minutes_per_shift, average_trip_distance, tips_per_trip, cluster_id,
            segment_label, model_run_id, model_run_at, training_start, training_end, feature_set, model_k, silhouette_score
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        for _, row in df.iterrows():
            cur.execute(insert, (row.driver_key, row.driver_id, row.driver_name, int(row.completed_shifts),
                row.trips_per_shift, row.revenue_per_hour, row.utilization_rate, row.idle_minutes_per_shift,
                row.average_trip_distance, row.tips_per_trip, int(row.cluster_id), row.segment_label,
                str(model_run_id), model_run_at, training_start, training_end, ",".join(features), selected["k"], selected["silhouette"]))
    print(f"Published {len(df)} driver segments for run {model_run_id}; k={selected['k']}, silhouette={selected['silhouette']:.4f}.")
    return len(df)


def run_route_association_rules(conn) -> int:
    """Mine quality-filtered association rules from a deterministic stratified sample."""
    print("Running Route Association Rules using stratified Apriori sampling...")
    query = f"""
    WITH ranked AS (
        SELECT trip_id, pickup_datetime, pickup_borough, pickup_zone, dropoff_borough, dropoff_zone,
               CASE WHEN pickup_hour BETWEEN 0 AND 5 THEN '00-05 Overnight'
                    WHEN pickup_hour BETWEEN 6 AND 11 THEN '06-11 Morning'
                    WHEN pickup_hour BETWEEN 12 AND 17 THEN '12-17 Afternoon' ELSE '18-23 Evening' END AS hour_bucket,
               pickup_day_name, CASE WHEN pickup_day_name IN ('Saturday', 'Sunday') THEN 'Weekend' ELSE 'Weekday' END AS day_type,
               vendor_name,
               ROW_NUMBER() OVER (PARTITION BY DATE_TRUNC('month', pickup_datetime), pickup_borough ORDER BY md5(trip_id)) AS stratum_rank
        FROM analytics.trip_pickup
    ) SELECT * FROM ranked WHERE stratum_rank <= {RULE_SAMPLE_PER_STRATUM} ORDER BY pickup_datetime, trip_id
    """
    df = read_sql_quietly(query, conn)
    if df.empty:
        print("No trip data found. Skipping association rules.")
        return 0
    def basket(row):
        values = (("pb:", row.pickup_borough), ("pz:", row.pickup_zone), ("db:", row.dropoff_borough),
                  ("dz:", row.dropoff_zone), ("hb:", row.hour_bucket), ("dn:", row.pickup_day_name),
                  ("dt:", row.day_type), ("vn:", row.vendor_name))
        return {prefix + str(value) for prefix, value in values if pd.notna(value) and str(value).strip()}
    transactions = [basket(row) for row in df.itertuples(index=False)]
    rules = run_apriori(
        transactions,
        min_support=RULE_MIN_SUPPORT,
        min_confidence=RULE_MIN_CONFIDENCE,
        min_lift=RULE_MIN_LIFT,
        min_antecedent_count=RULE_MIN_ANTECEDENT_COUNT,
    )
    rules = _score_rule_stability(rules, transactions, pd.to_datetime(df["pickup_datetime"]))
    rules = [rule for rule in rules if rule["stability_score"] >= RULE_MIN_STABILITY]
    published = rules[:MAX_PUBLISHED_RULES]
    coverage = (sum(any(rule["antecedent_items"].issubset(basket) and rule["consequent_item"] in basket for rule in published) for basket in transactions) / len(transactions)) if published else 0.0
    training_start, training_end = pd.to_datetime(df.pickup_datetime).min().date(), pd.to_datetime(df.pickup_datetime).max().date()
    with conn.cursor() as cur:
        model_run_id, model_run_at = uuid4(), datetime.now(timezone.utc)
        _publish_model_run(cur, "ROUTE_ASSOCIATION", model_run_id, model_run_at, training_start, training_end,
                           len(df), len(transactions), f"deterministic hash-stratified: up to {RULE_SAMPLE_PER_STRATUM} trips/month/pickup borough", {
                               "algorithm": "Apriori itemsets through size 3", "min_support": RULE_MIN_SUPPORT,
                               "min_confidence": RULE_MIN_CONFIDENCE, "min_lift": RULE_MIN_LIFT,
                               "min_antecedent_count": RULE_MIN_ANTECEDENT_COUNT, "min_stability": RULE_MIN_STABILITY,
                               "sample_per_stratum": RULE_SAMPLE_PER_STRATUM,
                           }, {"rules_generated_before_stability": len(rules), "rules_published": len(published), "rule_coverage": coverage})
        insert = """INSERT INTO analytics.route_association_rules (
            antecedent, consequent, support, confidence, lift, antecedent_support, consequent_support,
            model_run_id, model_run_at, training_start, training_end, basket_count, rules_generated,
            rules_published, min_support, min_confidence, min_lift, antecedent_count, stability_score,
            antecedent_pickup_borough, antecedent_pickup_zone, antecedent_hour_bucket, antecedent_day_type,
            antecedent_vendor, consequent_dropoff_borough, consequent_dropoff_zone
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        for rule in published:
            cur.execute(insert, (rule["antecedent"], rule["consequent"], rule["support"], rule["confidence"], rule["lift"],
                rule["antecedent_support"], rule["consequent_support"], str(model_run_id), model_run_at, training_start, training_end,
                len(transactions), len(rules), len(published), RULE_MIN_SUPPORT, RULE_MIN_CONFIDENCE, RULE_MIN_LIFT,
                rule["antecedent_count"], rule["stability_score"], rule["antecedent_pickup_borough"], rule["antecedent_pickup_zone"],
                rule["antecedent_hour_bucket"], rule["antecedent_day_type"], rule["antecedent_vendor"],
                rule["consequent_dropoff_borough"], rule["consequent_dropoff_zone"]))
    print(f"Published {len(published)} association rules for run {model_run_id}; coverage={coverage:.2%}.")
    return len(published)


def execute_data_mining(conn) -> dict[str, int]:
    """Execute both exploratory models in the caller's transaction."""
    drivers_loaded = run_driver_segmentation(conn)
    rules_loaded = run_route_association_rules(conn)
    return {"rows_read": drivers_loaded + rules_loaded, "loaded": drivers_loaded + rules_loaded, "rejected": 0}
