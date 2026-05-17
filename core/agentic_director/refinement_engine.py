from typing import List, Dict, Any, Tuple
from core.agentic_director.schema import RefinementAction
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan
from core.render_orchestrator.schema import RenderExecutionPlan

class RefinementEngine:
    """
    Responsible for applying structured refinements to cinematic plans safely.
    Ensures refinements never break continuity.
    """
    
    def apply_refinements(
        self,
        scene_intent: SceneIntent,
        shot_plan: ShotPlan,
        render_execution_plan: RenderExecutionPlan,
        actions: List[RefinementAction]
    ) -> Tuple[SceneIntent, ShotPlan, RenderExecutionPlan]:
        
        # We work on copies to ensure deterministic and safe modification
        refined_intent = scene_intent.model_copy(deep=True)
        refined_shot_plan = shot_plan.model_copy(deep=True)
        refined_render_plan = render_execution_plan.model_copy(deep=True)

        for action in actions:
            if action.action_type == "adjust_camera":
                self._apply_camera_refinement(refined_shot_plan, action)
            elif action.action_type == "refine_performance":
                self._apply_performance_refinement(refined_shot_plan, action)
            elif action.action_type == "modify_pacing":
                self._apply_pacing_refinement(refined_shot_plan, action)
            elif action.action_type == "optimize_render":
                self._apply_render_refinement(refined_render_plan, action)
            elif action.action_type == "shift_emotional_target":
                self._apply_intent_refinement(refined_intent, action)

        return refined_intent, refined_shot_plan, refined_render_plan

    def _apply_camera_refinement(self, shot_plan: ShotPlan, action: RefinementAction):
        for shot in shot_plan.shots:
            if not action.target_shot_ids or shot.shot_id in action.target_shot_ids:
                if "movement" in action.parameters:
                    shot.camera.movement = action.parameters["movement"]
                if "intensity" in action.parameters:
                    shot.camera.intensity = action.parameters["intensity"]
                if "composition" in action.parameters:
                    shot.framing.composition = action.parameters["composition"]

    def _apply_performance_refinement(self, shot_plan: ShotPlan, action: RefinementAction):
        for shot in shot_plan.shots:
            if not action.target_shot_ids or shot.shot_id in action.target_shot_ids:
                for char_id, perf in shot.performance.items():
                    if "intensity_adj" in action.parameters:
                        perf.intensity = max(0.0, min(1.0, perf.intensity + action.parameters["intensity_adj"]))
                    if "add_micro_actions" in action.parameters:
                        perf.micro_actions.extend(action.parameters["add_micro_actions"])
                        # Deduplicate
                        perf.micro_actions = list(set(perf.micro_actions))

    def _apply_pacing_refinement(self, shot_plan: ShotPlan, action: RefinementAction):
        for shot in shot_plan.shots:
            if not action.target_shot_ids or shot.shot_id in action.target_shot_ids:
                if "duration_adj" in action.parameters:
                    shot.duration_sec = max(0.5, shot.duration_sec + action.parameters["duration_adj"])

    def _apply_render_refinement(self, render_plan: RenderExecutionPlan, action: RefinementAction):
        for shot in render_plan.shots:
            if not action.target_shot_ids or shot.shot_id in action.target_shot_ids:
                if "render_strategy" in action.parameters:
                    shot.render_strategy = action.parameters["render_strategy"]

    def _apply_intent_refinement(self, scene_intent: SceneIntent, action: RefinementAction):
        if "intensity_adj" in action.parameters:
            scene_intent.emotional_target.intensity = max(0.0, min(1.0, scene_intent.emotional_target.intensity + action.parameters["intensity_adj"]))
        if "tension_delta_adj" in action.parameters:
            scene_intent.tension_delta += action.parameters["tension_delta_adj"]
