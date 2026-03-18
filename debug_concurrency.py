import requests
import time
import threading

def make_request(i):
    try:
        start = time.time()
        r = requests.get('http://127.0.0.1:8888/api/monitoring', timeout=5)
        end = time.time()
        print(f"Req {i}: Status {r.status_code} in {end-start:.2f}s")
    except Exception as e:
        print(f"Req {i}: Failed {e}")

print("Testing concurrent requests...")
threads = []
for i in range(5):
    t = threading.Thread(target=make_request, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
