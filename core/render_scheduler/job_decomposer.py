from typing import List, Dict, Any
from core.render_scheduler.schema import RenderJobNode
from core.render_orchestrator.schema import RenderExecutionPlan, RenderShot
from core.shot_planner.schema import ShotPlan, Shot
from core.performance_dialogue_engine.schema import PerformanceSequencePlan

class JobDecomposer:
    """
    Responsible for breaking rendering pipeline into atomic jobs.
    Splits shots into execution units and defines dependencies between them.
    """
    
    def decompose(
        self, 
        render_execution_plan: RenderExecutionPlan,
        shot_plan: ShotPlan,
        performance_sequences: List[PerformanceSequencePlan]
    ) -> List[RenderJobNode]:
        """
        Decomposes a full cinematic scene into a list of atomic RenderJobNodes.
        """
        all_jobs: List[RenderJobNode] = []
        
        # Map performance sequences by shot_id for easy lookup
        perf_map = {ps.shot_id: ps for ps in performance_sequences}
        # Map shots by shot_id
        shot_map = {s.shot_id: s for s in shot_plan.shots}
        
        for render_shot in render_execution_plan.shots:
            shot_id = render_shot.shot_id
            shot_data = shot_map.get(shot_id)
            perf_data = perf_map.get(shot_id)
            
            shot_jobs = self._decompose_shot(render_shot, shot_data, perf_data)
            all_jobs.extend(shot_jobs)
            
        return all_jobs

    def _decompose_shot(
        self, 
        render_shot: RenderShot, 
        shot_data: Shot, 
        perf_data: PerformanceSequencePlan
    ) -> List[RenderJobNode]:
        """
        Breaks a single shot into its component jobs.
        """
        jobs: List[RenderJobNode] = []
        shot_id = render_shot.shot_id
        
        # 1. Image Generation Job (GPU)
        image_job_id = f"{shot_id}_image_gen"
        if render_shot.asset_requirements.requires_image_generation:
            jobs.append(RenderJobNode(
                job_id=image_job_id,
                stage="image_generation",
                resource_type="gpu",
                estimated_duration_sec=5,  # Baseline estimate
                payload={
                    "shot_id": shot_id,
                    "generation_plan": render_shot.generation_plan.dict(),
                    "framing": shot_data.framing.dict() if shot_data else None
                }
            ))
            
        # 2. Motion Generation Job (GPU)
        motion_job_id = f"{shot_id}_motion_gen"
        if render_shot.asset_requirements.requires_video_generation:
            deps = [image_job_id] if render_shot.asset_requirements.requires_image_generation else []
            jobs.append(RenderJobNode(
                job_id=motion_job_id,
                stage="ai_motion",
                dependencies=deps,
                resource_type="gpu",
                estimated_duration_sec=15,
                payload={
                    "shot_id": shot_id,
                    "ai_motion_plan": render_shot.ai_motion_plan.dict(),
                    "camera": shot_data.camera.dict() if shot_data else None
                }
            ))

        # 3. Audio Generation Job (CPU/Hybrid)
        audio_job_id = f"{shot_id}_audio_gen"
        if render_shot.asset_requirements.requires_voice:
            jobs.append(RenderJobNode(
                job_id=audio_job_id,
                stage="audio_generation",
                resource_type="gpu", # Often GPU for modern TTS
                estimated_duration_sec=3,
                payload={
                    "shot_id": shot_id,
                    "audio_plan": render_shot.audio_plan.dict(),
                    "dialogue": perf_data.dialogue_blocks[0].dict() if perf_data and perf_data.dialogue_blocks else None
                }
            ))

        # 4. Lip Sync Processing Job (GPU)
        lipsync_job_id = f"{shot_id}_lipsync"
        if render_shot.asset_requirements.requires_lipsync:
            deps = []
            if render_shot.asset_requirements.requires_video_generation:
                deps.append(motion_job_id)
            elif render_shot.asset_requirements.requires_image_generation:
                deps.append(image_job_id)
            
            if render_shot.asset_requirements.requires_voice:
                deps.append(audio_job_id)
                
            jobs.append(RenderJobNode(
                job_id=lipsync_job_id,
                stage="lipsync_processing",
                dependencies=deps,
                resource_type="gpu",
                estimated_duration_sec=10,
                payload={
                    "shot_id": shot_id,
                    "lipsync_timeline": [b.dict() for b in perf_data.lipsync_timeline] if perf_data else []
                }
            ))

        # 5. FFmpeg Composition Job (CPU)
        composition_job_id = f"{shot_id}_composition"
        comp_deps = []
        if render_shot.asset_requirements.requires_lipsync:
            comp_deps.append(lipsync_job_id)
        elif render_shot.asset_requirements.requires_video_generation:
            comp_deps.append(motion_job_id)
        elif render_shot.asset_requirements.requires_image_generation:
            comp_deps.append(image_job_id)
            
        if render_shot.asset_requirements.requires_voice:
            comp_deps.append(audio_job_id)
            
        jobs.append(RenderJobNode(
            job_id=composition_job_id,
            stage="ffmpeg_composition",
            dependencies=comp_deps,
            resource_type="cpu",
            estimated_duration_sec=2,
            payload={
                "shot_id": shot_id,
                "ffmpeg_plan": render_shot.ffmpeg_plan.dict(),
                "duration_sec": shot_data.duration_sec if shot_data else 0.0
            }
        ))

        # 6. Post Processing Job (Hybrid)
        post_job_id = f"{shot_id}_post_processing"
        jobs.append(RenderJobNode(
            job_id=post_job_id,
            stage="post_processing",
            dependencies=[composition_job_id],
            resource_type="hybrid",
            estimated_duration_sec=3,
            payload={
                "shot_id": shot_id,
                "continuity_constraints": render_shot.continuity_constraints.dict()
            }
        ))
        
        return jobs
