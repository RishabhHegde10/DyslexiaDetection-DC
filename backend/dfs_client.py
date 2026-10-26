import sys, os, grpc, hashlib
import dfs_pb2, dfs_pb2_grpc
from net_config import METADATA_SERVER, STORAGE_NODES

CHUNK_SIZE = 64 * 1024 # 64 KB

def put(filepath):
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return

    filename = os.path.basename(filepath)
    size = os.path.getsize(filepath)
    num_chunks = (size + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    if size == 0:
        num_chunks = 1 # Handle empty file case

    print(f"Uploading {filename} ({size} bytes, {num_chunks} chunks)")

    with grpc.insecure_channel(METADATA_SERVER) as meta_channel:
        meta_stub = dfs_pb2_grpc.MetadataServiceStub(meta_channel)
        
        try:
            plan = meta_stub.GetUploadPlan(dfs_pb2.UploadReq(filename=filename, num_chunks=num_chunks))
        except Exception as e:
            print(f"Metadata Server unreachable: {e}")
            return
            
        if not plan.success:
            print(f"Failed to get upload plan: {plan.error_message}")
            return

        commit_req = dfs_pb2.CommitReq(filename=filename)

        with open(filepath, "rb") as f:
            for i in range(num_chunks):
                data = f.read(CHUNK_SIZE)
                if not data and size > 0:
                    break
                    
                checksum = hashlib.sha256(data).hexdigest()
                chunk_id = f"{filename}_part{i}"
                nodes = plan.chunk_allocations[i].nodes

                stored_count = 0
                for node in nodes:
                    addr = STORAGE_NODES[node]
                    try:
                        with grpc.insecure_channel(addr) as st_channel:
                            st_stub = dfs_pb2_grpc.StorageServiceStub(st_channel)
                            res = st_stub.StoreChunk(dfs_pb2.StoreReq(chunk_id=chunk_id, data=data, checksum=checksum))
                            if res.success:
                                stored_count += 1
                                print(f"Stored {chunk_id} on {node}")
                            else:
                                print(f"Warning: Checksum rejected by {node} for {chunk_id}")
                    except Exception as e:
                        print(f"Warning: Node {node} failed during upload: {e}")

                if stored_count == 0:
                    print(f"Error: Failed to store {chunk_id} on ANY node. Upload aborted.")
                    return

                # Record allocated nodes for commit
                commit_req.chunks[i].nodes.extend(nodes)
                commit_req.chunks[i].checksum = checksum

        meta_stub.CommitFile(commit_req)
        print(f"Successfully committed {filename} to metadata server.")

def get(filename, outpath):
    print(f"Requesting download plan for {filename}...")
    with grpc.insecure_channel(METADATA_SERVER) as meta_channel:
        meta_stub = dfs_pb2_grpc.MetadataServiceStub(meta_channel)
        
        try:
            plan = meta_stub.GetFilePlan(dfs_pb2.FileReq(filename=filename))
        except Exception as e:
            print(f"Metadata Server unreachable: {e}")
            return
            
        if not plan.success:
            print("File not found in DFS metadata.")
            return

        with open(outpath, "wb") as f:
            for i in range(plan.num_chunks):
                chunk_info = plan.chunks[i]
                chunk_id = f"{filename}_part{i}"
                data = None

                for node in chunk_info.nodes:
                    addr = STORAGE_NODES.get(node)
                    if not addr: continue
                    try:
                        with grpc.insecure_channel(addr) as st_channel:
                            st_stub = dfs_pb2_grpc.StorageServiceStub(st_channel)
                            res = st_stub.GetChunk(dfs_pb2.GetChunkReq(chunk_id=chunk_id))
                            
                            if res.success:
                                if res.checksum == chunk_info.checksum:
                                    print(f"Fetched {chunk_id} from {node}")
                                    data = res.data
                                    break
                                else:
                                    print(f"CORRUPTION DETECTED: Checksum mismatch for {chunk_id} on {node}. Falling back to next replica...")
                            else:
                                print(f"Chunk {chunk_id} missing on {node}. Falling back...")
                    except Exception as e:
                        print(f"Node {node} unavailable. Falling back...")

                if data is None:
                    print(f"CRITICAL ERROR: Could not retrieve valid replica for {chunk_id} from ANY node!")
                    return
                f.write(data)
                
        print(f"Successfully reconstructed {filename} at {outpath}")

def status():
    with grpc.insecure_channel(METADATA_SERVER) as meta_channel:
        meta_stub = dfs_pb2_grpc.MetadataServiceStub(meta_channel)
        try:
            res = meta_stub.GetStatus(dfs_pb2.StatusReq())
            print("--- DFS CLUSTER STATUS ---")
            print(res.status_json)
        except Exception as e:
            print(f"Error fetching status: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python dfs_client.py [put <file> | get <filename> <out> | status]")
        sys.exit(1)
        
    cmd = sys.argv[1]
    if cmd == "put": 
        put(sys.argv[2])
    elif cmd == "get": 
        get(sys.argv[2], sys.argv[3])
    elif cmd == "status": 
        status()
