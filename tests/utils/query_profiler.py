from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

query_data = {"queries": [], "total_time": 0.0}

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.perf_counter()

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.perf_counter() - context._query_start_time
    query_data["queries"].append({
        "statement": statement,
        "parameters": parameters,
        "duration": total
    })
    query_data["total_time"] += total

def print_query_profile():
    print("\n===== QUERY PROFILE =====")
    print(f"Total queries: {len(query_data['queries'])}")
    print(f"Total duration: {query_data['total_time']:.4f}s")
    print("\nSlowest queries:")
    for i, query in enumerate(sorted(query_data['queries'], key=lambda x: x['duration'], reverse=True)[:5]):
        print(f"#{i+1} ({query['duration']:.4f}s): {query['statement']}")
    print("="*30)
