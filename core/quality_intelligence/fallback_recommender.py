from typing import List, Tuple
from .schema import ValidationIssue, QualityScores

class FallbackRecommender:
    def determine_strategy(
        self, 
        scores: QualityScores, 
        issues: List[ValidationIssue]
    ) -> Tuple[bool, bool, List[str]]:
        """
        Returns: (regeneration_required, fallback_recommended, recommendations)
        """
        regeneration_required = False
        fallback_recommended = False
        recommendations = []
        
        # 1. Check for Critical/High issues
        has_critical = any(i.severity == "critical" for i in issues)
        has_high = any(i.severity == "high" for i in issues)
        
        if has_critical:
            regeneration_required = True
            recommendations.append("Critical continuity errors detected. Full scene regeneration required.")
        
        # 2. Check scores
        if scores.overall_score < 0.4:
            regeneration_required = True
            recommendations.append("Overall quality below threshold. Re-planning or regeneration recommended.")
        elif scores.overall_score < 0.7:
            fallback_recommended = True
            recommendations.append("Quality issues detected. Recommending deterministic fallback for problematic shots.")
            
        # 3. specific issues
        for issue in issues:
            if issue.severity in ["high", "critical"] and issue.type == "character_drift":
                regeneration_required = True
                recommendations.append(f"Character drift in {issue.affected_shot_ids} requires regeneration with character-lock.")
                
            if issue.type == "environment_reset":
                regeneration_required = True
                recommendations.append(f"Environment reset in {issue.affected_shot_ids} requires regeneration with consistent seed.")

        # Deduplicate recommendations
        recommendations = list(dict.fromkeys(recommendations))
        
        return regeneration_required, fallback_recommended, recommendations
