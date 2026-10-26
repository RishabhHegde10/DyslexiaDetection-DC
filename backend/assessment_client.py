import grpc
import prediction_pb2
import prediction_pb2_grpc

def run():
    print("Connecting to Prediction Service...\n")
    
    # Establish connection with the server
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = prediction_pb2_grpc.PredictionServiceStub(channel)
        
        # Create a sample assessment request
        request = prediction_pb2.PredictionRequest(
            typing_accuracy=88.5,
            reading_score=75.0,
            cognitive_score=80.0,
            spelling_score=85.0
        )
        
        # Invoke the remote Predict method
        response = stub.Predict(request)
        
        # Print output format as specified
        print(f"Prediction: {response.prediction}")
        print(f"Confidence: {response.confidence:.1f}%")

if __name__ == '__main__':
    run()
