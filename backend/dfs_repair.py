import grpc, sys
import dfs_pb2, dfs_pb2_grpc
from net_config import METADATA_SERVER, STORAGE_NODES

def run_repair():
    print("Connecting to Metadata Server for Repair Plan...")
    try:
        with grpc.insecure_channel(METADATA_SERVER) as meta_channel:
            meta_stub = dfs_pb2_grpc.MetadataServiceStub(meta_channel)
            plan = meta_stub.GetRepairPlan(dfs_pb2.RepairReq())

            if not plan.tasks:
                print("Cluster is fully replicated. No repair needed.")
                return

            print(f"Found {len(plan.tasks)} under-replicated chunks.")

            for task_id, task in plan.tasks.items():
                print(f"--> Repairing {task.filename} chunk {task.chunk_index}...")
                print(f"    Source (Healthy): {task.source_node}")
                print(f"    Target (New Replica): {task.target_node}")
                
                chunk_id = f"{task.filename}_part{task.chunk_index}"
                data = None

                # 1. Fetch from source
                try:
                    with grpc.insecure_channel(STORAGE_NODES[task.source_node]) as st_channel:
                        st_stub = dfs_pb2_grpc.StorageServiceStub(st_channel)
                        res = st_stub.GetChunk(dfs_pb2.GetChunkReq(chunk_id=chunk_id))
                        if res.success and res.checksum == task.checksum:
                            data = res.data
                        else:
                            print(f"    Failed: Source chunk {chunk_id} invalid or missing on {task.source_node}.")
                except Exception as e:
                    print(f"    Failed to fetch from source node {task.source_node}: {e}")
                    continue

                # 2. Upload to target
                if data:
                    try:
                        with grpc.insecure_channel(STORAGE_NODES[task.target_node]) as st_channel:
                            st_stub = dfs_pb2_grpc.StorageServiceStub(st_channel)
                            res = st_stub.StoreChunk(dfs_pb2.StoreReq(chunk_id=chunk_id, data=data, checksum=task.checksum))
                            
                            if res.success:
                                meta_stub.RegisterRepair(dfs_pb2.RegisterRepairReq(
                                    filename=task.filename,
                                    chunk_index=task.chunk_index,
                                    new_node=task.target_node
                                ))
                                print(f"    SUCCESS: Chunk {task.chunk_index} safely replicated to {task.target_node}.")
                            else:
                                print(f"    Failed: Target node {task.target_node} rejected chunk.")
                    except Exception as e:
                        print(f"    Failed to store on target node {task.target_node}: {e}")

    except Exception as e:
        print(f"Repair process encountered a fatal error: {e}")

if __name__ == '__main__':
    run_repair()
