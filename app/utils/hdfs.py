
from hdfs import InsecureClient
from config import Config


HDFS_IP = "192.168.100.23"
HDFS_WEBHDFS_PORT = "50070"
# HDFS_URL = f"http://{HDFS_IP}:{HDFS_WEBHDFS_PORT}"
HDFS_URL = Config.HDFS_URL
HDFS_USER = Config.HDFS_USER

# Global HDFS client
client = InsecureClient(HDFS_URL, user=HDFS_USER)

def hdfs_client_connect():
    try:
        print("Attempting to connect to HDFS...")
        hdfs_client = InsecureClient(HDFS_URL, user=HDFS_USER)
        print("HDFS client connection successful.")
        return hdfs_client
    except Exception as e:
        print(f"HDFS connection failed with error: {e}")
        return None

def upload_file_to_hdfs_temp(local_filepath, hdfs_path):
    """
    Uploads a local file to HDFS at the given path.
    """
    hdfs_client = hdfs_client_connect()
    if not hdfs_client:
        raise Exception("HDFS connection not available.")

    try:
        hdfs_client.upload(hdfs_path, local_filepath, overwrite=True)
        print(f"File uploaded to HDFS at {hdfs_path}")
    except Exception as e:
        raise Exception(f"Failed to upload file to HDFS: {e}")

def test_hdfs_connection():
    try:
        hdfs_client = InsecureClient(HDFS_URL, user=HDFS_USER)
        print("HDFS client connection successful.")
        return hdfs_client
    except Exception as e:
        print(f"Failed to connect to HDFS: {e}")
        return None

def list_hdfs_root():
    try:
        files = client.list('/')
        print(files)
    except Exception as e:
        print({"status": "error", "message": str(e)}), 500

def hdfs_test():
    try:
        files = client.list('/')
        return {'status': 'success', 'files': files}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def hdfs_file_count(path='/user/hdfs/temp/'):
    try:
        # Check if HDFS client is configured
        if 'client' not in globals() or client is None:
            return {'status': 'error', 'message': 'HDFS is not configured'}

        files = client.list(path)  # Attempt to list files in the path
        
        if not files:  # If list is empty
            return {'status': 'success', 'count': 0}
        
        return {'status': 'success', 'count': len(files)}

    except Exception as e:
        # Handle config-related errors
        if "Connection refused" in str(e) or "No such host" in str(e):
            return {'status': 'error', 'message': 'HDFS is not configured'}
        
        return {'status': 'error', 'message': str(e)}
