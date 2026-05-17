from typing import Dict, List, Any, Optional
from datetime import datetime
from core.render_scheduler.schema import RenderJobNode, CinematicRenderJobPlan

class ExecutionTracker:
    """
    Tracks real-time progress of rendering jobs and plans.
    Provides status updates for monitoring and UI.
    """
    
    def __init__(self):
        # story_id -> plan_status
        self.plan_status: Dict[str, Dict[str, Any]] = {}
        # job_id -> logs
        self.job_logs: Dict[str, List[str]] = {}
        
    def start_plan_tracking(self, plan: CinematicRenderJobPlan):
        self.plan_status[plan.story_id] = {
            "story_id": plan.story_id,
            "scene_id": plan.scene_id,
            "start_time": datetime.now().isoformat(),
            "total_jobs": len(plan.job_graph),
            "completed_jobs": 0,
            "failed_jobs": 0,
            "status": "running",
            "progress_percent": 0.0,
            "job_statuses": {job.job_id: job.status for job in plan.job_graph}
        }

    def update_job_status(self, story_id: str, job_id: str, status: str, error_msg: Optional[str] = None):
        if story_id not in self.plan_status:
            return
            
        status_info = self.plan_status[story_id]
        old_status = status_info["job_statuses"].get(job_id)
        status_info["job_statuses"][job_id] = status
        
        if status == "completed" and old_status != "completed":
            status_info["completed_jobs"] += 1
        elif status == "failed" and old_status != "failed":
            status_info["failed_jobs"] += 1
            
        # Recalculate progress
        total = status_info["total_jobs"]
        if total > 0:
            status_info["progress_percent"] = (status_info["completed_jobs"] / total) * 100
            
        if status_info["completed_jobs"] + status_info["failed_jobs"] == total:
            status_info["status"] = "completed" if status_info["failed_jobs"] == 0 else "completed_with_errors"
            status_info["end_time"] = datetime.now().isoformat()

    def add_job_log(self, job_id: str, message: str):
        if job_id not in self.job_logs:
            self.job_logs[job_id] = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.job_logs[job_id].append(f"[{timestamp}] {message}")

    def get_plan_progress(self, story_id: str) -> Optional[Dict[str, Any]]:
        return self.plan_status.get(story_id)

    def get_job_logs(self, job_id: str) -> List[str]:
        return self.job_logs.get(job_id, [])
