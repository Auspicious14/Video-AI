from typing import List, Dict, Optional
from core.render_scheduler.schema import RenderJobNode, DistributedMetadata

class WorkerAllocator:
    """
    Assigns jobs to workers and balances GPU load.
    Supports single-node MVP and future multi-node clusters.
    """
    
    def __init__(self):
        self.workers: List[str] = ["local_worker_0"] # Default MVP worker
        self.worker_load: Dict[str, float] = {"local_worker_0": 0.0}
        
    def allocate_jobs(
        self, 
        jobs: List[RenderJobNode], 
        metadata: DistributedMetadata
    ) -> Dict[str, str]:
        """
        Assigns each job to a worker based on the strategy in metadata.
        Returns a mapping of job_id -> worker_id.
        """
        assignments: Dict[str, str] = {}
        
        if metadata.worker_assignment_strategy == "round_robin":
            for i, job in enumerate(jobs):
                worker_id = self.workers[i % len(self.workers)]
                assignments[job.job_id] = worker_id
                
        elif metadata.worker_assignment_strategy == "least_loaded":
            for job in jobs:
                # Find worker with least load
                worker_id = min(self.worker_load, key=self.worker_load.get)
                assignments[job.job_id] = worker_id
                # Update load (naive estimation)
                self.worker_load[worker_id] += job.estimated_duration_sec
                
        elif metadata.worker_assignment_strategy == "gpu_affinity":
            # Priority: assign GPU jobs to workers with active GPUs
            # (In MVP, we just assign everything to local)
            for job in jobs:
                assignments[job.job_id] = "local_worker_0"
                
        return assignments

    def add_worker(self, worker_id: str):
        if worker_id not in self.workers:
            self.workers.append(worker_id)
            self.worker_load[worker_id] = 0.0

    def get_worker_status(self) -> Dict[str, Any]:
        return {
            "worker_count": len(self.workers),
            "loads": self.worker_load
        }
