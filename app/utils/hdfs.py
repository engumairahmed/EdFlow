from hdfs import InsecureClient
import pandas as pd

HDFS_URL = "http://localhost:9870"  # Replace if different
HDFS_USER = "hdfs"

client = InsecureClient(HDFS_URL, user=HDFS_USER)

def write_to_hdfs(df: pd.DataFrame, hdfs_path: str):
    with client.write(hdfs_path, encoding='utf-8', overwrite=True) as writer:
        df.to_csv(writer, index=False)
