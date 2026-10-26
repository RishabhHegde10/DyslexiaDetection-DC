import os, sys, time, threading, grpc, hashlib
from concurrent import futures
import dfs_pb2, dfs_pb2_grpc
from net_config import METADATA_SERVER, STORAGE_NODES
from lamport_clock import LamportClock

class StorageService(dfs_pb2_grpc.StorageServiceServicer):
    def __init__(self, node_id):
        self.node_id = node_id
        self.clock = LamportClock()
        self.data_dir = f"dfs_data_{node_id}"
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Start heartbeat daemon (sends ping every 2 seconds)
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()

    def heartbeat_loop(self):
        while True:
            try:
                with grpc.insecure_channel(METADATA_SERVER) as channel:
                    stub = dfs_pb2_grpc.MetadataServiceStub(channel)
                    self.clock.increment()
                    stub.Heartbeat(dfs_pb2.HeartbeatReq(
                        node_id=self.node_id, 
                        lamport_clock=self.clock.get_time()
                    ))
            except Exception:
                pass # Metadata server might be unreachable
            time.sleep(2)

    def StoreChunk(self, request, context):
        computed = hashlib.sha256(request.data).hexdigest()
        if computed != request.checksum:
            print(f"[{self.node_id}] Checksum mismatch for {request.chunk_id}! Rejected.")
            return dfs_pb2.StoreRes(success=False)
            
        path = os.path.join(self.data_dir, request.chunk_id)
        with open(path, "wb") as f:
            f.write(request.data)
        print(f"[{self.node_id}] Successfully stored {request.chunk_id}")
        return dfs_pb2.StoreRes(success=True)

    def GetChunk(self, request, context):
        path = os.path.join(self.data_dir, request.chunk_id)
        if not os.path.exists(path):
            return dfs_pb2.GetChunkRes(success=False)
            
        with open(path, "rb") as f:
            data = f.read()
            
        checksum = hashlib.sha256(data).hexdigest()
        return dfs_pb2.GetChunkRes(success=True, data=data, checksum=checksum)

def serve(node_id):
    if node_id not in STORAGE_NODES:
        print(f"Invalid node_id. Must be one of: {list(STORAGE_NODES.keys())}")
        sys.exit(1)
        
    port = STORAGE_NODES[node_id].split(":")[1]
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    dfs_pb2_grpc.add_StorageServiceServicer_to_server(StorageService(node_id), server)
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    print(f"Storage Node {node_id} active on port {port}. Heartbeating to {METADATA_SERVER}...")
    server.wait_for_termination()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python dfs_storage.py <node_id>")
        sys.exit(1)
    serve(sys.argv[1])
