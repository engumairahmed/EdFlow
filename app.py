import os
import socket
from dotenv import load_dotenv
from app import create_app

load_dotenv()

def find_available_port(start_port=5000):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1

app = create_app()

if __name__ == '__main__':
    port = find_available_port(5000)
    if __name__ == "__main__":
        host = os.environ.get('HOST', '0.0.0.0')
        port = int(os.environ.get('PORT', 5000))
        
        app.run(host=host, port=port, debug=True)
        app.run(debug=True, port=port, use_reloader=False)              
