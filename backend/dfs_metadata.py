import grpc
import time
import json
import threading
import random
from concurrent import futures
import dfs_pb2
import dfs_pb2_grpc
from net_config import METADATA_SERVER
from lamport_clock import LamportClock

class MetadataService(dfs_pb2_grpc.MetadataServiceServicer):
    def __init__(self):
        self.clock = LamportClock()
        self.lock = threading.Lock()
        self.nodes_last_heartbeat = {}
        self.metadata_file = "dfs_metadata_store.json"
        self.files = {} 
        self.load_metadata()

        # Monitor heartbeats to detect failover (timeout > 6s)
        threading.Thread(target=self.check_nodes, daemon=True).start()

    def load_metadata(self):
        try:
            with open(self.metadata_file, "r") as f:
                self.files = json.load(f)
        except FileNotFoundError:
            self.files = {}

    def save_metadata(self):
        with open(self.metadata_file, "w") as f:
            json.dump(self.files, f, indent=2)

    def check_nodes(self):
        while True:
            time.sleep(2)
            with self.lock:
                now = time.time()
                dead_nodes = [n for n, t in self.nodes_last_heartbeat.items() if now - t > 6]
                # Log dead nodes if any
                if dead_nodes:
                    pass

    def get_active_nodes(self):
        now = time.time()
        return [n for n, t in self.nodes_last_heartbeat.items() if now - t <= 6]

    def Heartbeat(self, request, context):
        with self.lock:
            self.clock.update(request.lamport_clock)
            self.nodes_last_heartbeat[request.node_id] = time.time()
        return dfs_pb2.HeartbeatRes(success=True)

    def GetUploadPlan(self, request, context):
        with self.lock:
            active = self.get_active_nodes()
            if len(active) < 2:
                return dfs_pb2.UploadPlan(success=False, error_message=f"Not enough active storage nodes (need 2, have {len(active)}).")

            allocations = {}
            for i in range(request.num_chunks):
                allocations[i] = dfs_pb2.NodeList(nodes=random.sample(active, 2))
            return dfs_pb2.UploadPlan(success=True, chunk_allocations=allocations)

    def CommitFile(self, request, context):
        with self.lock:
            chunks = {}
            for idx, meta in request.chunks.items():
                chunks[str(idx)] = {
                    "nodes": list(meta.nodes),
                    "checksum": meta.checksum
                }
            self.files[request.filename] = {
                "num_chunks": len(chunks),
                "chunks": chunks
            }
            self.save_metadata()
        return dfs_pb2.CommitRes(success=True)

    def GetFilePlan(self, request, context):
        with self.lock:
            if request.filename not in self.files:
                return dfs_pb2.FilePlan(success=False)
            
            f = self.files[request.filename]
            plan = dfs_pb2.FilePlan(success=True, num_chunks=f["num_chunks"])
            for idx, c in f["chunks"].items():
                plan.chunks[int(idx)].nodes.extend(c["nodes"])
                plan.chunks[int(idx)].checksum = c["checksum"]
            return plan

    def GetStatus(self, request, context):
        with self.lock:
            active = self.get_active_nodes()
            status = {
                "lamport_clock": self.clock.get_time(),
                "active_nodes": active,
                "files": self.files
            }
            return dfs_pb2.StatusRes(status_json=json.dumps(status, indent=2))

    def GetRepairPlan(self, request, context):
        with self.lock:
            active = self.get_active_nodes()
            plan = dfs_pb2.RepairPlan()
            
            for filename, fdata in self.files.items():
                for idx_str, cdata in fdata["chunks"].items():
                    live_replicas = [n for n in cdata["nodes"] if n in active]
                    if 0 < len(live_replicas) < 2:
                        target_candidates = [n for n in active if n not in cdata["nodes"]]
                        if target_candidates:
                            task_id = f"{filename}_{idx_str}"
                            task = plan.tasks[task_id]
                            task.filename = filename
                            task.chunk_index = int(idx_str)
                            task.source_node = live_replicas[0]
                            task.target_node = random.choice(target_candidates)
                            task.checksum = cdata["checksum"]
            return plan

    def RegisterRepair(self, request, context):
        with self.lock:
            idx_str = str(request.chunk_index)
            if request.filename in self.files and idx_str in self.files[request.filename]["chunks"]:
                nodes = self.files[request.filename]["chunks"][idx_str]["nodes"]
                if request.new_node not in nodes:
                    nodes.append(request.new_node)
                    self.save_metadata()
        return dfs_pb2.CommitRes(success=True)

def serve():
    port = METADATA_SERVER.split(":")[1]
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    dfs_pb2_grpc.add_MetadataServiceServicer_to_server(MetadataService(), server)
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    print(f"Metadata Server listening on port {port}")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
