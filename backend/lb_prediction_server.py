import sys
import time
import random
import grpc
from concurrent import futures
import logging

import prediction_pb2
import prediction_pb2_grpc
from ml_engine import load_model, transform_input, normalize_prediction

class LoadBalancedPredictionService(prediction_pb2_grpc.LoadBalancedPredictionServiceServicer):
    def __init__(self, server_name):
        self.server_name = server_name
        self.model = load_model()
        logging.info(f"{self.server_name} initialized with the existing ML model.")
        self.request_counter = 0

    def HandlePrediction(self, request, context):
        self.request_counter += 1
        req_id = self.request_counter
        
        work_time = random.uniform(0.5, 2.5)
        print(f"[{self.server_name}] Handling request {req_id} (will take {work_time:.2f}s)", flush=True)
        
        # Simulate variable load
        time.sleep(work_time)

        # Existing ML Logic
        data = {
            "overall_accuracy": request.typing_accuracy,
            "reading_score": request.reading_score,
            "cognitive_score": request.cognitive_score,
            "spelling_score": request.spelling_score,
            "typing_speed": 0.0,
            "total_errors": 0,
            "total_score": request.reading_score
        }
        features = transform_input(data)
        
        raw_prediction = self.model.predict([features])[0]
        prediction_int, risk_level = normalize_prediction(raw_prediction)
        
        if hasattr(self.model, "predict_proba"):
            probability = self.model.predict_proba([features])[0][1]
        else:
            probability = 0.938
            
        confidence = (probability if risk_level == "high" else (1.0 - probability)) * 100
        
        print(f"[{self.server_name}] Finished request {req_id}", flush=True)
        
        # We reuse PredictionResponse but pass 0 for lamport_timestamp
        return prediction_pb2.PredictionResponse(
            prediction=risk_level.title() + " Risk",
            confidence=confidence,
            lamport_timestamp=0
        )

def serve(port):
    logging.basicConfig(level=logging.ERROR) # Only show our custom prints
    server_name = f"Prediction-Server-{port[-1]}"
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    prediction_pb2_grpc.add_LoadBalancedPredictionServiceServicer_to_server(
        LoadBalancedPredictionService(server_name), server
    )
    
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    
    print(f"{server_name} listening on localhost:{port}", flush=True)
    server.wait_for_termination()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python lb_prediction_server.py <port>")
        sys.exit(1)
    serve(sys.argv[1])
