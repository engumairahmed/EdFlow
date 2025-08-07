
# spark_deduplicate.py

import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp
import os
import subprocess


# Argument check
if len(sys.argv) != 3:
    print("Usage: spark_deduplicate.py <new_data_path> <final_data_path>")
    sys.exit(-1)

new_data_path = sys.argv[1] # /user/hdfs/temp/new_data.csv
final_data_path = sys.argv[2] # /user/hdfs/student_data.csv

# Spark Session
spark = SparkSession.builder.appName("StudentDataDeduplication").getOrCreate()

try:
    # 1. HDFS se purani aur nayi dono files load karein
    if final_data_path:
        old_df = spark.read.csv(final_data_path, header=True, inferSchema=True)
    else:
        old_df = spark.createDataFrame([], old_df.schema)

    new_df = spark.read.csv(new_data_path, header=True, inferSchema=True)

    # 2. Dono dataframes ko merge karein
    combined_df = old_df.union(new_df)
    
    # 3. Deduplication logic (Important: apne column names check karein)
    # Humein sab se latest record chahiye.
    # 'Student ID' aur 'Update Date' columns ke mutabiq duplicates remove karein.
    
    # Pehle date column ko timestamp mein convert karein
    combined_df = combined_df.withColumn(
        "Update_Date_ts", to_timestamp(col("Update Date"), "MM/dd/yyyy HH:mm")
    )
    
    # Sort karke latest records rakhein
    deduplicated_df = combined_df.sort(
        "Student ID", "Update_Date_ts", ascending=False
    ).dropDuplicates(subset=["Student ID"])
    
    # Final data ko HDFS par overwrite kar dein
    deduplicated_df.write.mode("overwrite").csv(final_data_path, header=True)
    
    print("Deduplication and saving successful!")

except Exception as e:
    print(f"An error occurred in Spark job: {e}")

finally:
    spark.stop()
    # Temporary file ko HDFS se delete karein
    subprocess.run(['hdfs', 'dfs', '-rm', new_data_path], check=True)