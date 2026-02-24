"""
Cluster Sizing, Topology, and Capacity Growth Definitions.
Enforces institutional hardware requirements for the distributed architecture.
"""

# ── Hardware Sizing Definitions ──────────────────────────────
FAISS_SHARD_RAM_GB_MIN = 64         # Minimum RAM per FAISS shard
FAISS_SHARD_VCPU_MIN = 16           # Minimum cores for parallel batch distance scans
FAISS_SHARD_NVME_IOPS_MIN = 50_000  # Minimum IOPS for double-buffered index writes
MAX_NETWORK_LATENCY_MS = 2          # Bounded latency between shards and coordinator

# ── Distributed Deployment Topology ──────────────────────────
REPLICATION_FACTOR = 2              # Primary shard + Replica shard
MULTI_AZ_ENABLED = True             # Enforce spread across Availability Zones
STANDBY_MODE = "HOT"                # Replicas immediately route queries on master failover

# ── Capacity Growth Model ────────────────────────────────────
MONTHLY_VECTOR_GROWTH_ESTIMATE = 2_000_000   # ~2000 assets x 5 timeframes
MONTHLY_RAM_GROWTH_GB_ESTIMATE = 2.4         # Indexing overhead
REBUILD_SCALING_O_COMPLEXITY = "N_log_N"     # 50M vectors ≈ 45m background rebuild
