import grpc
import threading
import time
import os

import prediction_pb2
import prediction_pb2_grpc

TARGET_ADDR = os.environ.get("TARGET_ADDR", "localhost:50051")

def send_request(req_id):
    try:
        # Crucial for K8s load balancing over Headless Service
        channel_options = [('grpc.lb_policy_name', 'round_robin')]
        
        with grpc.insecure_channel(TARGET_ADDR, options=channel_options) as channel:
            stub = prediction_pb2_grpc.PredictionServiceStub(channel)
            request = prediction_pb2.PredictionRequest(
                typing_accuracy=88.5,
                reading_score=75.0,
                cognitive_score=80.0,
                spelling_score=85.0,
                lamport_timestamp=0
            )
            response = stub.Predict(request)
            print(f"Request {req_id} completed -> Result: {response.prediction} | Target Addr: {TARGET_ADDR}", flush=True)
    except Exception as e:
        print(f"Request {req_id} failed: {e}", flush=True)

def run():
    print(f"Starting Load Test targeting: {TARGET_ADDR}", flush=True)
    NUM_REQUESTS = 15
    threads = []
    
    for i in range(1, NUM_REQUESTS + 1):
        t = threading.Thread(target=send_request, args=(i,))
        threads.append(t)
        t.start()
        time.sleep(0.1) # Small stagger to ensure connections are spread
        
    for t in threads:
        t.join()
        
    print("\nLoad Test Completed.", flush=True)

if __name__ == '__main__':
    run()
