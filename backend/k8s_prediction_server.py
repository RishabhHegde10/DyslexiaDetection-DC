import sys
import time
import socket
import grpc
from concurrent import futures
import logging
import os

import prediction_pb2
import prediction_pb2_grpc
from ml_engine import load_model, transform_input, normalize_prediction

class K8sPredictionService(prediction_pb2_grpc.PredictionServiceServicer):
    def __init__(self):
        self.hostname = socket.gethostname()
        self.model = load_model()
        logging.info(f"K8s Prediction Server initialized on pod: {self.hostname}")

    def Predict(self, request, context):
        print(f"[{self.hostname}] Handling request...", flush=True)

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
        
        print(f"[{self.hostname}] Prediction generated: {risk_level.title()} Risk ({confidence:.1f}%)", flush=True)
        
        return prediction_pb2.PredictionResponse(
            prediction=risk_level.title() + " Risk",
            confidence=confidence,
            lamport_timestamp=0
        )

def serve():
    logging.basicConfig(level=logging.INFO)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    prediction_pb2_grpc.add_PredictionServiceServicer_to_server(
        K8sPredictionService(), server
    )
    
    port = os.environ.get("PORT", "50051")
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    
    print(f"K8s Server listening on 0.0.0.0:{port} (Pod: {socket.gethostname()})", flush=True)
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
