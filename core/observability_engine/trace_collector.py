from typing import List, Dict, Any
import time
import uuid
from core.observability_engine.schema import PipelineEvent, PipelinePhase

class TraceCollector:
    """
    Responsible for collecting events across all phases and standardizing them.
    """
    
    def collect_events(
        self,
        story_id: str,
        state_graph: Any,
        scene_intents: List[Any],
        shot_plans: List[Any],
        render_jobs: List[Any],
        performance_outputs: List[Any]
    ) -> List[PipelineEvent]:
        events = []
        
        # 1. Collect State Phase Events
        events.extend(self._extract_state_events(state_graph))
        
        # 2. Collect Intent Phase Events
        events.extend(self._extract_intent_events(scene_intents))
        
        # 3. Collect Shots Phase Events
        events.extend(self._extract_shot_events(shot_plans))
        
        # 4. Collect Render & Scheduler Phase Events
        events.extend(self._extract_render_events(render_jobs))
        
        # 5. Collect Performance Phase Events
        events.extend(self._extract_performance_events(performance_outputs))
        
        # Sort events by timestamp
        events.sort(key=lambda x: x.timestamp)
        
        return events

    def _extract_state_events(self, state_graph: Any) -> List[PipelineEvent]:
        # Implementation depends on how CinematicStateGraph stores history
        # Mocking for now based on typical graph traversal/history
        events = []
        if hasattr(state_graph, 'history'):
            for entry in state_graph.history:
                events.append(PipelineEvent(
                    event_id=str(uuid.uuid4()),
                    phase=PipelinePhase.STATE,
                    timestamp=entry.get('timestamp', int(time.time())),
                    actor="CinematicStateGraph",
                    action=entry.get('action', 'transition'),
                    metadata=entry.get('metadata', {})
                ))
        return events

    def _extract_intent_events(self, scene_intents: List[Any]) -> List[PipelineEvent]:
        events = []
        for intent in scene_intents:
            events.append(PipelineEvent(
                event_id=str(uuid.uuid4()),
                phase=PipelinePhase.INTENT,
                timestamp=getattr(intent, 'created_at', int(time.time())),
                actor="SceneIntentSystem",
                action="generate_intent",
                metadata={"scene_id": getattr(intent, 'scene_id', 'unknown')}
            ))
        return events

    def _extract_shot_events(self, shot_plans: List[Any]) -> List[PipelineEvent]:
        events = []
        for plan in shot_plans:
            events.append(PipelineEvent(
                event_id=str(uuid.uuid4()),
                phase=PipelinePhase.SHOTS,
                timestamp=getattr(plan, 'created_at', int(time.time())),
                actor="ShotPlanner",
                action="create_shot_plan",
                metadata={"shot_id": getattr(plan, 'shot_id', 'unknown')}
            ))
        return events

    def _extract_render_events(self, render_jobs: List[Any]) -> List[PipelineEvent]:
        events = []
        for job in render_jobs:
            events.append(PipelineEvent(
                event_id=str(uuid.uuid4()),
                phase=PipelinePhase.RENDER,
                timestamp=getattr(job, 'started_at', int(time.time())),
                actor="RenderOrchestrator",
                action="start_render_job",
                metadata={"job_id": getattr(job, 'job_id', 'unknown')}
            ))
            if hasattr(job, 'finished_at') and job.finished_at:
                events.append(PipelineEvent(
                    event_id=str(uuid.uuid4()),
                    phase=PipelinePhase.RENDER,
                    timestamp=job.finished_at,
                    actor="RenderOrchestrator",
                    action="finish_render_job",
                    metadata={"job_id": getattr(job, 'job_id', 'unknown'), "status": getattr(job, 'status', 'unknown')}
                ))
        return events

    def _extract_performance_events(self, performance_outputs: List[Any]) -> List[PipelineEvent]:
        events = []
        for output in performance_outputs:
            events.append(PipelineEvent(
                event_id=str(uuid.uuid4()),
                phase=PipelinePhase.PERFORMANCE,
                timestamp=getattr(output, 'created_at', int(time.time())),
                actor="MultimodalPerformanceEngine",
                action="generate_performance",
                metadata={"output_id": getattr(output, 'id', 'unknown')}
            ))
        return events
