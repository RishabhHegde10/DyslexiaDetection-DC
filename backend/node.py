import sys
import time
import grpc
from concurrent import futures
import threading

import prediction_pb2
import prediction_pb2_grpc
from lamport_clock import LamportClock

PEERS = {
    1: "localhost:60051",
    2: "localhost:60052",
    3: "localhost:60053"
}

RELEASED = "RELEASED"
WANTED = "WANTED"
HELD = "HELD"

class MutexService(prediction_pb2_grpc.MutexServiceServicer):
    def __init__(self, node_id, clock, lock):
        self.node_id = node_id
        self.clock = clock
        self.lock = lock
        self.state = RELEASED
        self.request_timestamp = 0
        self.deferred_events = []

    def RequestAccess(self, request, context):
        with self.lock:
            self.clock.update(request.timestamp)
            print(f"Node-{self.node_id}: Received request from Node-{request.node_id}")

            defer = False
            if self.state == HELD:
                defer = True
                print(f"Node-{self.node_id}: DEFERRING request from Node-{request.node_id}")
                print(f"Reason: Node is currently HELD.")
            elif self.state == WANTED:
                # Priority: (timestamp, node_id)
                my_priority = (self.request_timestamp, self.node_id)
                incoming_priority = (request.timestamp, request.node_id)
                if my_priority < incoming_priority:
                    defer = True
                    print(f"Node-{self.node_id}: DEFERRING request from Node-{request.node_id}")
                    print(f"Reason: Node-{self.node_id} has priority based on (timestamp, node_id)")

            if not defer:
                print(f"Node-{self.node_id}: GRANTING request to Node-{request.node_id}")

            if defer:
                event = threading.Event()
                self.deferred_events.append(event)
        
        # Wait outside the lock!
        if defer:
            event.wait()

        with self.lock:
            self.clock.increment()
            reply_timestamp = self.clock.get_time()
            return prediction_pb2.AccessReply(node_id=self.node_id, timestamp=reply_timestamp)

def request_critical_section(node_id, clock, lock, mutex_service, stubs):
    with lock:
        clock.increment()
        mutex_service.request_timestamp = clock.get_time()
        mutex_service.state = WANTED
        req_timestamp = mutex_service.request_timestamp
        print(f"\nNode-{node_id}: Lamport clock = {req_timestamp}")
        print(f"Node-{node_id}: WANTS critical section")

    # Send requests
    for peer_id, stub in stubs.items():
        print(f"Node-{node_id}: Requesting access from Node-{peer_id}")
        request = prediction_pb2.AccessRequest(node_id=node_id, timestamp=req_timestamp)
        # This blocks until reply is received
        response = stub.RequestAccess(request)
        with lock:
            clock.update(response.timestamp)

    with lock:
        mutex_service.state = HELD

    # Critical Section
    print(f"\nNode-{node_id}: ENTERED CRITICAL SECTION")
    print(f"Node-{node_id}: Processing shared ML prediction/report resource...")
    time.sleep(1) # Simulate shared resource access
    print(f"Node-{node_id}: EXITED CRITICAL SECTION\n")

    with lock:
        mutex_service.state = RELEASED
        for event in mutex_service.deferred_events:
            event.set()
        mutex_service.deferred_events = []

def serve(node_id):
    clock = LamportClock()
    lock = threading.Lock()
    mutex_service = MutexService(node_id, clock, lock)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    prediction_pb2_grpc.add_MutexServiceServicer_to_server(mutex_service, server)
    port = PEERS[node_id].split(":")[1]
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()

    print(f"Node-{node_id} gRPC server started on {PEERS[node_id]}")

    stubs = {}
    for peer_id, address in PEERS.items():
        if peer_id == node_id:
            continue
        # Implement retry logic
        connected = False
        start_time = time.time()
        while time.time() - start_time < 30:
            try:
                channel = grpc.insecure_channel(address)
                grpc.channel_ready_future(channel).result(timeout=1)
                stubs[peer_id] = prediction_pb2_grpc.MutexServiceStub(channel)
                print(f"Node-{node_id}: Connected to Node-{peer_id}")
                connected = True
                break
            except grpc.FutureTimeoutError:
                pass
            except Exception as e:
                pass
            time.sleep(1)
        if not connected:
            print(f"Node-{node_id}: Failed to connect to Node-{peer_id} after 30 seconds.")
            return

    # To demonstrate contention, wait a little bit for everyone to be connected then request
    time.sleep(2)
    request_critical_section(node_id, clock, lock, mutex_service, stubs)
    
    # Keep running briefly so other nodes finish
    time.sleep(5)
    server.stop(0)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python node.py <node_id>")
        sys.exit(1)
    node_id = int(sys.argv[1])
    serve(node_id)
