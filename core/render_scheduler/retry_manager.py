import time
from typing import Dict, Any, Optional
from core.render_scheduler.schema import RenderJobNode, RetryPolicy

class RetryManager:
    """
    Handles job retry logic, exponential backoff, and failure classification.
    """
    
    def __init__(self):
        # job_id -> current_retry_count
        self.retry_counts: Dict[str, int] = {}
        
    def should_retry(self, job: RenderJobNode, retry_policy: RetryPolicy, error_type: str) -> bool:
        """
        Determines if a failed job should be retried based on policy and error type.
        """
        current_retries = self.retry_counts.get(job.job_id, 0)
        
        # Classification of errors
        is_transient = self._is_transient_failure(error_type)
        
        if current_retries < retry_policy.max_retries and is_transient:
            return True
        return False

    def get_backoff_delay_sec(self, job: RenderJobNode, retry_policy: RetryPolicy) -> float:
        """
        Calculates the delay before the next retry attempt.
        """
        current_retries = self.retry_counts.get(job.job_id, 0)
        
        if retry_policy.backoff_strategy == "exponential":
            return 2.0 ** current_retries
        elif retry_policy.backoff_strategy == "linear":
            return 5.0 * (current_retries + 1)
        else: # fixed
            return 10.0

    def increment_retry(self, job_id: str):
        self.retry_counts[job_id] = self.retry_counts.get(job_id, 0) + 1

    def _is_transient_failure(self, error_type: str) -> bool:
        """
        Classifies errors as transient (retryable) or permanent.
        """
        transient_errors = [
            "gpu_timeout",
            "connection_error",
            "worker_preempted",
            "rate_limit",
            "transient_ai_failure"
        ]
        return any(err in error_type.lower() for err in transient_errors)
    
    def classify_failure(self, error_msg: str) -> str:
        """
        Determines the type of failure from error message.
        """
        error_msg = error_msg.lower()
        if "timeout" in error_msg or "cuda" in error_msg:
            return "gpu_timeout"
        if "ffmpeg" in error_msg:
            return "ffmpeg_failure"
        if "model" in error_msg or "weights" in error_msg:
            return "ai_model_failure"
        return "unknown_failure"
