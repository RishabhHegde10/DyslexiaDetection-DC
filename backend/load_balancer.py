import grpc
import threading
import time

import prediction_pb2
import prediction_pb2_grpc

BACKENDS = [
    "localhost:60201",
    "localhost:60202",
    "localhost:60203"
]

active = [0, 0, 0]
lock = threading.Lock()

def pick_least_connections(req_id):
    with lock:
        # Find the backend with the minimum active connection count
        min_conns = min(active)
        idx = active.index(min_conns)
        
        # Increment that backend's active count IMMEDIATELY
        active[idx] += 1
        
        # Print the routing decision
        print(f"\n[LB] Routing request {req_id} -> {BACKENDS[idx]}")
        print(f"[LB] Reason: least active connections (Current min is {min_conns})")
        print(f"[LB] Active connections after dispatch: {active}")
        
        return idx, BACKENDS[idx]

def release(idx, backend_address):
    with lock:
        active[idx] -= 1
        print(f"[LB] Released {backend_address}")
        print(f"[LB] Active connections: {active}")

def send_request(req_id):
    idx, backend_address = pick_least_connections(req_id)
    
    try:
        with grpc.insecure_channel(backend_address) as channel:
            stub = prediction_pb2_grpc.LoadBalancedPredictionServiceStub(channel)
            request = prediction_pb2.PredictionRequest(
                typing_accuracy=88.5,
                reading_score=75.0,
                cognitive_score=80.0,
                spelling_score=85.0,
                lamport_timestamp=0
            )
            response = stub.HandlePrediction(request)
            print(f"[LB] Request {req_id} -> handled by Prediction-Server-{idx+1} | Result: {response.prediction} ({response.confidence:.1f}%)")
    except Exception as e:
        print(f"[LB] Request {req_id} failed: {e}")
    finally:
        release(idx, backend_address)

def run():
    print("[LB] Load Balancer starting.")
    print("[LB] Backends:")
    for b in BACKENDS:
        print(b)
        
    NUM_REQUESTS = 9
    threads = []
    
    for i in range(1, NUM_REQUESTS + 1):
        t = threading.Thread(target=send_request, args=(i,))
        threads.append(t)
        t.start()
        # Stagger requests slightly so some overlap and counts diverge
        time.sleep(0.5)
        
    for t in threads:
        t.join()
        
    print("\n[LB] All requests processed.")
    print(f"[LB] Final active connection counts: {active}")

if __name__ == '__main__':
    run()
