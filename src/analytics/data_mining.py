import os
import sys
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Ensure print output is flushed
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

def format_item(item):
    prefix_map = {
        'pb:': 'pickup_borough',
        'pz:': 'pickup_zone',
        'db:': 'dropoff_borough',
        'dz:': 'dropoff_zone',
        'hb:': 'hour_bucket',
        'dn:': 'day_name',
        'dt:': 'day_type',
        'vn:': 'vendor'
    }
    for prefix, label in prefix_map.items():
        if item.startswith(prefix):
            return f"{label}={item[len(prefix):]}"
    return item

def format_rule_string(rule_str):
    items = [format_item(i.strip()) for i in rule_str.split(', ')]
    return ', '.join(items)

def run_apriori(transactions, min_support=0.005, min_confidence=0.2, min_lift=1.1):
    num_trans = len(transactions)
    if num_trans == 0:
        return []
    
    # Step 1: Frequent 1-itemsets
    item_counts = {}
    for t in transactions:
        for item in t:
            item_counts[item] = item_counts.get(item, 0) + 1
            
    frequent_1 = {item: count / num_trans for item, count in item_counts.items() if count / num_trans >= min_support}
    support_dict = {frozenset({item}): sup for item, sup in frequent_1.items()}
    
    # Step 2: Frequent 2-itemsets
    candidate_2_counts = {}
    for t in transactions:
        t_freq = [item for item in t if item in frequent_1]
        n_freq = len(t_freq)
        for i in range(n_freq):
            for j in range(i + 1, n_freq):
                cand = frozenset({t_freq[i], t_freq[j]})
                candidate_2_counts[cand] = candidate_2_counts.get(cand, 0) + 1
                
    frequent_2 = {cand: count / num_trans for cand, count in candidate_2_counts.items() if count / num_trans >= min_support}
    support_dict.update(frequent_2)
    
    # Step 3: Frequent 3-itemsets
    candidate_3_counts = {}
    for t in transactions:
        t_freq = [item for item in t if item in frequent_1]
        n_freq = len(t_freq)
        for i in range(n_freq):
            for j in range(i + 1, n_freq):
                for k in range(j + 1, n_freq):
                    cand = frozenset({t_freq[i], t_freq[j], t_freq[k]})
                    s1 = frozenset({t_freq[i], t_freq[j]})
                    s2 = frozenset({t_freq[i], t_freq[k]})
                    s3 = frozenset({t_freq[j], t_freq[k]})
                    if s1 in frequent_2 and s2 in frequent_2 and s3 in frequent_2:
                        candidate_3_counts[cand] = candidate_3_counts.get(cand, 0) + 1
                
    frequent_3 = {cand: count / num_trans for cand, count in candidate_3_counts.items() if count / num_trans >= min_support}
    support_dict.update(frequent_3)
    
    # Rule generation: A -> B where B has size 1 (consequent is a single dropoff item)
    rules = []
    for itemset, support in support_dict.items():
        if len(itemset) < 2:
            continue
        for item in itemset:
            # Consequent must be a dropoff item (prefixed with 'db:' or 'dz:')
            if not (item.startswith('db:') or item.startswith('dz:')):
                continue
            
            consequent = frozenset({item})
            antecedent = itemset - consequent
            
            # Antecedent cannot contain dropoff items (ensure pickup/time -> dropoff logic)
            if any(x.startswith('db:') or x.startswith('dz:') for x in antecedent):
                continue
                
            if antecedent in support_dict and consequent in support_dict:
                conf = support / support_dict[antecedent]
                lift = conf / support_dict[consequent]
                
                if conf >= min_confidence and lift >= min_lift:
                    rules.append({
                        'antecedent': format_rule_string(', '.join(sorted(list(antecedent)))),
                        'consequent': format_item(item),
                        'support': support,
                        'confidence': conf,
                        'lift': lift,
                        'antecedent_support': support_dict[antecedent],
                        'consequent_support': support_dict[consequent]
                    })
                    
    rules.sort(key=lambda x: x['lift'], reverse=True)
    return rules

def run_driver_segmentation(conn) -> int:
    """Run K-Means driver segmentation and save results."""
    print("Running Driver Segmentation using K-Means...")
    
    # Query features
    query = """
    WITH driver_trips AS (
        SELECT
            driver_key,
            AVG(trip_distance) AS average_trip_distance,
            SUM(tip_amount) / NULLIF(COUNT(trip_id), 0) AS tips_per_trip
        FROM analytics.trip_pickup
        GROUP BY driver_key
    ),
    driver_shifts AS (
        SELECT
            driver_key,
            driver_id,
            driver_name,
            COUNT(shift_id) AS completed_shifts,
            SUM(trip_count)::numeric / NULLIF(COUNT(shift_id), 0) AS trips_per_shift,
            SUM(total_revenue) * 60 / NULLIF(SUM(shift_duration_minutes), 0) AS revenue_per_hour,
            SUM(occupied_minutes) / NULLIF(SUM(shift_duration_minutes), 0) AS utilization_rate,
            SUM(idle_minutes)::numeric / NULLIF(COUNT(shift_id), 0) AS idle_minutes_per_shift
        FROM analytics.shift
        GROUP BY driver_key, driver_id, driver_name
    )
    SELECT
        s.driver_key,
        s.driver_id,
        s.driver_name,
        s.completed_shifts,
        COALESCE(s.trips_per_shift, 0)::float AS trips_per_shift,
        COALESCE(s.revenue_per_hour, 0)::float AS revenue_per_hour,
        COALESCE(s.utilization_rate, 0)::float AS utilization_rate,
        COALESCE(s.idle_minutes_per_shift, 0)::float AS idle_minutes_per_shift,
        COALESCE(t.average_trip_distance, 0)::float AS average_trip_distance,
        COALESCE(t.tips_per_trip, 0)::float AS tips_per_trip
    FROM driver_shifts s
    LEFT JOIN driver_trips t ON s.driver_key = t.driver_key;
    """
    df = pd.read_sql(query, conn)
    
    if len(df) < 3:
        print(f"Not enough drivers ({len(df)}) to cluster into 3 groups. Skipping driver clustering.")
        return 0
        
    features = [
        'revenue_per_hour', 'utilization_rate', 'trips_per_shift',
        'average_trip_distance', 'tips_per_trip', 'idle_minutes_per_shift',
        'completed_shifts'
    ]
    X = df[features]
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Fit KMeans
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df['cluster_id'] = kmeans.fit_predict(X_scaled)
    
    # Dynamic label mapping based on centroids
    cluster_means = df.groupby('cluster_id')[['revenue_per_hour', 'idle_minutes_per_shift', 'utilization_rate']].mean()
    
    # Highest revenue_per_hour -> High productivity
    high_prod_cluster = cluster_means['revenue_per_hour'].idxmax()
    
    # Highest idle_minutes_per_shift among the remaining -> High idle
    remaining = [c for c in cluster_means.index if c != high_prod_cluster]
    high_idle_cluster = cluster_means.loc[remaining, 'idle_minutes_per_shift'].idxmax()
    
    # Remaining is Average stable
    average_stable_cluster = [c for c in remaining if c != high_idle_cluster][0]
    
    label_map = {
        high_prod_cluster: 'High productivity',
        high_idle_cluster: 'High idle',
        average_stable_cluster: 'Average stable'
    }
    df['segment_label'] = df['cluster_id'].map(label_map)
    
    # Save to database
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE analytics.driver_segments")
        
        insert_query = """
        INSERT INTO analytics.driver_segments (
            driver_key, driver_id, driver_name, completed_shifts,
            trips_per_shift, revenue_per_hour, utilization_rate,
            idle_minutes_per_shift, average_trip_distance, tips_per_trip,
            cluster_id, segment_label
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        for _, row in df.iterrows():
            cur.execute(insert_query, (
                row['driver_key'], row['driver_id'], row['driver_name'], int(row['completed_shifts']),
                row['trips_per_shift'], row['revenue_per_hour'], row['utilization_rate'],
                row['idle_minutes_per_shift'], row['average_trip_distance'], row['tips_per_trip'],
                int(row['cluster_id']), row['segment_label']
            ))
            
    print(f"Successfully loaded {len(df)} driver segments into analytics.driver_segments.")
    return len(df)

def run_route_association_rules(conn) -> int:
    """Run Apriori route association rules and save results."""
    print("Running Route Association Rules using Apriori...")
    
    # Query trips
    query = """
    SELECT
        pickup_borough,
        pickup_zone,
        dropoff_borough,
        dropoff_zone,
        CASE
            WHEN pickup_hour BETWEEN 0 AND 5 THEN '00-05 Overnight'
            WHEN pickup_hour BETWEEN 6 AND 11 THEN '06-11 Morning'
            WHEN pickup_hour BETWEEN 12 AND 17 THEN '12-17 Afternoon'
            ELSE '18-23 Evening'
        END AS hour_bucket,
        pickup_day_name,
        CASE WHEN pickup_day_name IN ('Saturday', 'Sunday') THEN 'Weekend' ELSE 'Weekday' END AS day_type,
        vendor_name
    FROM analytics.trip_pickup
    LIMIT 50000;
    """
    df = pd.read_sql(query, conn)
    
    if len(df) == 0:
        print("No trip data found. Skipping association rules.")
        return 0
        
    # Build transactions
    transactions = []
    for _, row in df.iterrows():
        t = []
        if row['pickup_borough']: t.append(f"pb:{row['pickup_borough']}")
        if row['pickup_zone']: t.append(f"pz:{row['pickup_zone']}")
        if row['dropoff_borough']: t.append(f"db:{row['dropoff_borough']}")
        if row['dropoff_zone']: t.append(f"dz:{row['dropoff_zone']}")
        if row['hour_bucket']: t.append(f"hb:{row['hour_bucket']}")
        if row['pickup_day_name']: t.append(f"dn:{row['pickup_day_name']}")
        if row['day_type']: t.append(f"dt:{row['day_type']}")
        if row['vendor_name']: t.append(f"vn:{row['vendor_name']}")
        transactions.append(t)
        
    # Run Apriori
    rules = run_apriori(transactions, min_support=0.005, min_confidence=0.2, min_lift=1.1)
    
    # Save to database
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE analytics.route_association_rules")
        
        insert_query = """
        INSERT INTO analytics.route_association_rules (
            antecedent, consequent, support, confidence, lift,
            antecedent_support, consequent_support
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        for r in rules[:100]:
            cur.execute(insert_query, (
                r['antecedent'], r['consequent'], float(r['support']),
                float(r['confidence']), float(r['lift']),
                float(r['antecedent_support']), float(r['consequent_support'])
            ))
            
    print(f"Successfully loaded {min(len(rules), 100)} association rules into analytics.route_association_rules.")
    return min(len(rules), 100)

def execute_data_mining(conn) -> dict[str, int]:
    """Execute all data mining models and return loaded counts."""
    drivers_loaded = run_driver_segmentation(conn)
    rules_loaded = run_route_association_rules(conn)
    
    return {
        "rows_read": drivers_loaded + rules_loaded,
        "loaded": drivers_loaded + rules_loaded,
        "rejected": 0
    }
