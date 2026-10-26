import grpc
from concurrent import futures
import logging

import prediction_pb2
import prediction_pb2_grpc
from app import load_model, transform_input, normalize_prediction

class PredictionService(prediction_pb2_grpc.PredictionServiceServicer):
    def __init__(self):
        self.model = load_model()
        logging.info("Prediction Server initialized with the existing model.")

    def Predict(self, request, context):
        logging.info("Received assessment request...")
        
        # Map the gRPC request fields to the dictionary expected by transform_input
        data = {
            "overall_accuracy": request.typing_accuracy,
            "reading_score": request.reading_score,
            "cognitive_score": request.cognitive_score,
            "spelling_score": request.spelling_score,
            "typing_speed": 0.0,
            "total_errors": 0,
            "total_score": request.reading_score
        }
        
        # Convert into model features
        features = transform_input(data)
        
        # Run prediction
        raw_prediction = self.model.predict([features])[0]
        prediction_int, risk_level = normalize_prediction(raw_prediction)
        
        # Determine confidence probability
        if hasattr(self.model, "predict_proba"):
            probability = self.model.predict_proba([features])[0][1]
        else:
            probability = 0.938  # fallback if model doesn't support proba
            
        confidence = (probability if risk_level == "high" else (1.0 - probability)) * 100
            
        logging.info("Prediction completed.")
        
        return prediction_pb2.PredictionResponse(
            prediction=risk_level.title() + " Risk",
            confidence=confidence
        )

def serve():
    logging.basicConfig(level=logging.INFO)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    prediction_pb2_grpc.add_PredictionServiceServicer_to_server(PredictionService(), server)
    server.add_insecure_port('0.0.0.0:50051')
    server.start()
    print("Prediction Server started on port 50051...", flush=True)
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
