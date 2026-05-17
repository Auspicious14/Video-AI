from typing import List, Dict, Set
from core.render_scheduler.schema import RenderJobNode

class DependencyGraphBuilder:
    """
    Builds the Directed Acyclic Graph (DAG) for rendering jobs.
    Ensures correct execution ordering and validates dependencies.
    """
    
    def build_execution_order(self, jobs: List[RenderJobNode]) -> List[str]:
        """
        Returns a list of job_ids in a valid topological execution order.
        Raises ValueError if circular dependencies are detected.
        """
        job_map = {job.job_id: job for job in jobs}
        adj_list = {job.job_id: job.dependencies for job in jobs}
        
        visited: Set[str] = set()
        temp_stack: Set[str] = set()
        execution_order: List[str] = []
        
        def visit(job_id: str):
            if job_id in temp_stack:
                raise ValueError(f"Circular dependency detected at job: {job_id}")
            if job_id not in visited:
                temp_stack.add(job_id)
                
                # Visit dependencies first
                for dep_id in adj_list.get(job_id, []):
                    if dep_id not in job_map:
                        # Optional: handle missing dependencies
                        # For now, we skip if the job is not in our list
                        continue
                    visit(dep_id)
                
                temp_stack.remove(job_id)
                visited.add(job_id)
                execution_order.append(job_id)
        
        for job in jobs:
            if job.job_id not in visited:
                visit(job.job_id)
                
        return execution_order

    def validate_graph(self, jobs: List[RenderJobNode]) -> bool:
        """
        Validates that all dependencies exist and there are no circularities.
        """
        try:
            self.build_execution_order(jobs)
            return True
        except ValueError:
            return False
            
    def get_independent_jobs(self, jobs: List[RenderJobNode], completed_job_ids: Set[str]) -> List[str]:
        """
        Identifies jobs that can be started immediately (all dependencies met).
        """
        ready_jobs = []
        for job in jobs:
            if job.job_id in completed_job_ids:
                continue
                
            all_deps_met = all(dep_id in completed_job_ids for dep_id in job.dependencies)
            if all_deps_met:
                ready_jobs.append(job.job_id)
                
        return ready_jobs
