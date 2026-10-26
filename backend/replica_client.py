import grpc
import threading
import time

import replica_pb2
import replica_pb2_grpc

ALL_REPLICAS = {
    "A": "localhost:60301",
    "B": "localhost:60302",
    "C": "localhost:60303"
}

def save(replica_name, key, content):
    address = ALL_REPLICAS[replica_name]
    try:
        with grpc.insecure_channel(address) as channel:
            stub = replica_pb2_grpc.ReplicaServiceStub(channel)
            update = replica_pb2.ValueUpdate(key=key, content=content)
            stub.SaveValue(update)
    except Exception as e:
        print(f"Failed to write to {replica_name}: {e}")

def read_all(key):
    results = {}
    for name, address in sorted(ALL_REPLICAS.items()):
        try:
            with grpc.insecure_channel(address) as channel:
                stub = replica_pb2_grpc.ReplicaServiceStub(channel)
                query = replica_pb2.ValueQuery(key=key)
                state = stub.GetValue(query)
                if state.key:
                    results[name] = f"\"{state.content}\" (ts={state.lamport_timestamp}, origin={state.origin_replica})"
                    results[f"_{name}_val"] = state.content
                else:
                    results[name] = "<empty>"
        except Exception as e:
            results[name] = f"<error: {e}>"
    return results

def run():
    key = "student-assessment-1"
    
    print("Writing conflicting updates concurrently...")
    # Fire two concurrent conflicting writes
    t1 = threading.Thread(
        target=save,
        args=("A", key, "value-from-writer-1")
    )
    t2 = threading.Thread(
        target=save,
        args=("C", key, "value-from-writer-2")
    )
    
    t1.start()
    # Very small delay to almost guarantee collision
    time.sleep(0.05)
    t2.start()
    
    t1.join()
    t2.join()
    
    print("\n=== Immediately after writes ===")
    immediate_results = read_all(key)
    for name in ["A", "B", "C"]:
        print(f"Replica-{name}: {immediate_results[name]}")
        
    print("\nWaiting 2s for gossip to finish propagating...")
    time.sleep(2)
    
    print("\n=== After convergence window ===")
    final_results = read_all(key)
    values = set()
    for name in ["A", "B", "C"]:
        # print the full string with ts and origin
        print(f"Replica-{name}: {final_results[name]}")
        if f"_{name}_val" in final_results:
            values.add(final_results[f"_{name}_val"])
            
    if len(values) == 1:
        val = list(values)[0]
        print(f"\n*** CONVERGED: all replicas agree on: \"{val}\" ***")
    else:
        print(f"\n*** NOT YET CONVERGED: {values} ***")

if __name__ == '__main__':
    run()
