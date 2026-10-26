import sys
import time
import grpc
from concurrent import futures
import threading

import replica_pb2
import replica_pb2_grpc
from lamport_clock import LamportClock

ALL_REPLICAS = {
    "A": "localhost:60301",
    "B": "localhost:60302",
    "C": "localhost:60303"
}

class ReplicaService(replica_pb2_grpc.ReplicaServiceServicer):
    def __init__(self, replica_name):
        self.replica_name = replica_name
        self.clock = LamportClock()
        self.store = {} # key -> (content, timestamp, origin)
        self.lock = threading.Lock()

    def _apply_if_newer(self, key, content, ts, origin):
        # Must be called under lock
        if key not in self.store:
            self.store[key] = (content, ts, origin)
            return True

        _, current_ts, current_origin = self.store[key]
        
        # Last-Write-Wins comparison
        if (ts, origin) > (current_ts, current_origin):
            self.store[key] = (content, ts, origin)
            return True
        return False

    def _gossip(self, key, content, ts, origin):
        # Asynchronously send SyncUpdate to peers
        for peer_name, address in ALL_REPLICAS.items():
            if peer_name == self.replica_name:
                continue
            
            try:
                channel = grpc.insecure_channel(address)
                stub = replica_pb2_grpc.ReplicaServiceStub(channel)
                update = replica_pb2.ValueUpdate(
                    key=key,
                    content=content,
                    lamport_timestamp=ts,
                    origin_replica=origin
                )
                stub.SyncUpdate(update, timeout=1)
                print(f"[{self.replica_name} t={self.clock.get_time()}] Gossiped '{key}' -> {peer_name}", flush=True)
            except Exception as e:
                print(f"[{self.replica_name} t={self.clock.get_time()}] Gossip to {peer_name} failed - peer unavailable", flush=True)

    def SaveValue(self, request, context):
        with self.lock:
            self.clock.increment()
            ts = self.clock.get_time()
            origin = self.replica_name
            
            self._apply_if_newer(request.key, request.content, ts, origin)
            print(f"[{self.replica_name} t={ts}] APPLIED '{request.key}' = \"{request.content}\" (ts={ts}, origin={origin})", flush=True)
            
            # Start asynchronous gossip
            threading.Thread(
                target=self._gossip,
                args=(request.key, request.content, ts, origin),
                daemon=True
            ).start()
            
            return replica_pb2.SaveAck(
                accepted=True,
                replica=self.replica_name,
                lamport_timestamp=ts
            )

    def SyncUpdate(self, request, context):
        with self.lock:
            self.clock.update(request.lamport_timestamp)
            
            applied = self._apply_if_newer(request.key, request.content, request.lamport_timestamp, request.origin_replica)
            
            if applied:
                print(f"[{self.replica_name} t={self.clock.get_time()}] APPLIED '{request.key}' = \"{request.content}\" (ts={request.lamport_timestamp}, origin={request.origin_replica})", flush=True)
            else:
                current_ts = self.store[request.key][1]
                current_origin = self.store[request.key][2]
                print(f"[{self.replica_name} t={self.clock.get_time()}] IGNORED stale update for '{request.key}'\n(incoming ts={request.lamport_timestamp}/{request.origin_replica} <= current ts={current_ts}/{current_origin})", flush=True)
                
            return replica_pb2.SaveAck(
                accepted=applied,
                replica=self.replica_name,
                lamport_timestamp=self.clock.get_time()
            )

    def GetValue(self, request, context):
        with self.lock:
            if request.key in self.store:
                content, ts, origin = self.store[request.key]
                return replica_pb2.ValueState(
                    key=request.key,
                    content=content,
                    lamport_timestamp=ts,
                    origin_replica=origin
                )
            else:
                return replica_pb2.ValueState()

def serve(replica_name, port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    replica_pb2_grpc.add_ReplicaServiceServicer_to_server(
        ReplicaService(replica_name), server
    )
    
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    
    print(f"Replica-{replica_name} listening on localhost:{port}", flush=True)
    server.wait_for_termination()

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python replica_node.py <Replica_Name> <Port>")
        sys.exit(1)
    serve(sys.argv[1], sys.argv[2])
