from typing import List, Dict, Any, Optional
from core.render_scheduler.schema import (
    CinematicRenderJobPlan, 
    RenderJobNode, 
    ResourceRequirements, 
    RetryPolicy, 
    FallbackRoutes, 
    DistributedMetadata
)
from core.render_scheduler.job_decomposer import JobDecomposer
from core.render_scheduler.dependency_graph_builder import DependencyGraphBuilder
from core.render_scheduler.resource_estimator import ResourceEstimator
from core.render_scheduler.worker_allocator import WorkerAllocator
from core.render_scheduler.retry_manager import RetryManager
from core.render_scheduler.fallback_router import FallbackRouter
from core.render_scheduler.execution_tracker import ExecutionTracker

from core.render_orchestrator.schema import RenderExecutionPlan
from core.shot_planner.schema import ShotPlan
from core.performance_dialogue_engine.schema import PerformanceSequencePlan

class RenderSchedulerService:
    """
    Main entry point for Phase 9: Cinematic Scheduling + Distributed Render Orchestration.
    Acts as the 'studio production scheduler' of the VideoAI platform.
    """
    
    def __init__(self):
        self.decomposer = JobDecomposer()
        self.graph_builder = DependencyGraphBuilder()
        self.estimator = ResourceEstimator()
        self.allocator = WorkerAllocator()
        self.retry_manager = RetryManager()
        self.fallback_router = FallbackRouter()
        self.tracker = ExecutionTracker()

    def create_cinematic_render_plan(
        self,
        render_execution_plan: RenderExecutionPlan,
        shot_plan: ShotPlan,
        performance_sequences: List[PerformanceSequencePlan],
        system_resources: Optional[Dict[str, Any]] = None
    ) -> CinematicRenderJobPlan:
        """
        Decomposes render tasks, builds dependency graph, and optimizes execution order.
        """
        # 1. Decompose into atomic jobs
        jobs = self.decomposer.decompose(
            render_execution_plan, 
            shot_plan, 
            performance_sequences
        )
        
        # 2. Build dependency graph and execution order
        execution_order = self.graph_builder.build_execution_order(jobs)
        
        # 3. Estimate resource requirements
        total_resources = self.estimator.estimate_total_requirements(jobs)
        
        # 4. Assign execution priority (defaulting to 0.5)
        priority_score = 0.5
        
        # 5. Define policies
        retry_policy = RetryPolicy(max_retries=3, backoff_strategy="exponential")
        fallback_routes = FallbackRoutes(deterministic_fallback_enabled=True)
        distributed_metadata = DistributedMetadata(
            shard_count=len(render_execution_plan.shots),
            worker_assignment_strategy="least_loaded"
        )
        
        # 6. Allocate workers
        worker_assignments = self.allocator.allocate_jobs(jobs, distributed_metadata)
        # Update jobs with worker info if needed (currently payload is where we store it)
        for job in jobs:
            job.payload["assigned_worker"] = worker_assignments.get(job.job_id)
            
        # 7. Produce final plan
        plan = CinematicRenderJobPlan(
            story_id=render_execution_plan.story_id,
            scene_id=render_execution_plan.scene_id,
            job_graph=jobs,
            execution_order=execution_order,
            resource_requirements=total_resources,
            priority_score=priority_score,
            retry_policy=retry_policy,
            fallback_routes=fallback_routes,
            distributed_metadata=distributed_metadata
        )
        
        # 8. Start tracking
        self.tracker.start_plan_tracking(plan)
        
        return plan

    def get_next_runnable_jobs(self, story_id: str) -> List[RenderJobNode]:
        """
        Returns jobs that are ready to be executed (dependencies met).
        """
        progress = self.tracker.get_plan_progress(story_id)
        if not progress:
            return []
            
        completed_ids = {
            job_id for job_id, status in progress["job_statuses"].items() 
            if status == "completed"
        }
        
        # Find the plan (we'd usually fetch this from a DB)
        # For MVP, we'll assume we have the plan list somewhere or re-derive
        # In a real system, we'd look up the plan by story_id
        return [] # Placeholder for actual logic

    def report_job_failure(self, story_id: str, job_id: str, error_msg: str) -> Optional[RenderJobNode]:
        """
        Handles job failure, applies retry logic or fallback routing.
        Returns a new job node if a retry or fallback is scheduled.
        """
        # 1. Classify failure
        failure_type = self.retry_manager.classify_failure(error_msg)
        
        # 2. Check for retry
        # (Need access to the job and policy)
        # For brevity, this is the logic flow:
        # if should_retry -> increment retry, return same job with updated status
        # elif fallback_possible -> return fallback job
        # else -> mark failed
        
        self.tracker.update_job_status(story_id, job_id, "failed", error_msg)
        self.tracker.add_job_log(job_id, f"FAILED: {error_msg}")
        
        return None
