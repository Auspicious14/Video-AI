from typing import List, Dict
from .schema import ValidationIssue, QualityScores

class ScoringEngine:
    def compute_scores(self, issues: List[ValidationIssue]) -> QualityScores:
        # Initial scores start at 1.0
        scores = {
            "continuity_score": 1.0,
            "emotional_coherence_score": 1.0,
            "character_consistency_score": 1.0,
            "environment_consistency_score": 1.0,
            "cinematic_language_score": 1.0,
            "pacing_score": 1.0
        }
        
        # Penalties based on issue severity
        penalties = {
            "low": 0.05,
            "medium": 0.15,
            "high": 0.3,
            "critical": 0.6
        }
        
        # Map issue types to score categories
        type_to_category = {
            "character_drift": "character_consistency_score",
            "environment_reset": "environment_consistency_score",
            "wardrobe_inconsistency": "environment_consistency_score",
            "emotional_discontinuity": "emotional_coherence_score",
            "robotic_pacing": "emotional_coherence_score",
            "camera_language_inconsistency": "cinematic_language_score",
            "cinematic_style_break": "cinematic_language_score",
            "framing_consistency": "cinematic_language_score",
            "transition_appropriateness": "cinematic_language_score",
            "performance_consistency": "continuity_score",
            "pacing_problem": "pacing_score"
        }
        
        for issue in issues:
            category = type_to_category.get(issue.type, "continuity_score")
            penalty = penalties.get(issue.severity, 0.1)
            scores[category] = max(0.0, scores[category] - penalty)
            
            # Global continuity penalty for high/critical issues
            if issue.severity in ["high", "critical"]:
                scores["continuity_score"] = max(0.0, scores["continuity_score"] - (penalty * 0.5))

        # Compute overall score as weighted average
        weights = {
            "continuity_score": 0.25,
            "emotional_coherence_score": 0.2,
            "character_consistency_score": 0.15,
            "environment_consistency_score": 0.15,
            "cinematic_language_score": 0.15,
            "pacing_score": 0.1
        }
        
        overall_score = sum(scores[cat] * weights[cat] for cat in weights)
        
        return QualityScores(
            overall_score=round(overall_score, 4),
            continuity_score=round(scores["continuity_score"], 4),
            emotional_coherence_score=round(scores["emotional_coherence_score"], 4),
            character_consistency_score=round(scores["character_consistency_score"], 4),
            environment_consistency_score=round(scores["environment_consistency_score"], 4),
            cinematic_language_score=round(scores["cinematic_language_score"], 4),
            pacing_score=round(scores["pacing_score"], 4)
        )
