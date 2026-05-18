from typing import List, Any
from core.observability_engine.schema import PipelinePhase, BottleneckReport, CinematicQualityMetrics

class OptimizationEngine:
    """
    Suggests architectural and pipeline optimizations based on evidence.
    """
    
    def generate_suggestions(
        self,
        bottlenecks: List[BottleneckReport],
        quality_metrics: CinematicQualityMetrics
    ) -> List[str]:
        suggestions = []
        
        # 1. Address Bottlenecks
        for b in bottlenecks:
            if b.severity in ["high", "critical"]:
                suggestions.append(f"FIX: {b.recommended_fix} (Reason: {b.type})")
                
        # 2. Quality-based Optimizations
        if quality_metrics.emotional_realism_score < 0.7:
            suggestions.append("IMPROVE: Increase Agentic Director iterations for emotional realism refinement.")
            
        if quality_metrics.continuity_score < 0.7:
            suggestions.append("IMPROVE: Enable stricter CharacterIdentity validation in Phase 6.")
            
        # 3. Efficiency-based Optimizations
        # (Generic suggestions based on system patterns)
        suggestions.append("OPTIMIZE: Implement layer-based caching for background render assets.")
        
        return list(set(suggestions))

    def calculate_health_score(
        self,
        bottlenecks: List[BottleneckReport],
        quality_metrics: CinematicQualityMetrics
    ) -> float:
        # Simple health score calculation
        base_score = 1.0
        
        # Penalty for bottlenecks
        for b in bottlenecks:
            if b.severity == "critical": base_score -= 0.3
            elif b.severity == "high": base_score -= 0.15
            elif b.severity == "medium": base_score -= 0.05
            
        # Penalty for low quality
        avg_quality = (
            quality_metrics.emotional_realism_score + 
            quality_metrics.continuity_score + 
            quality_metrics.pacing_score
        ) / 3.0
        
        if avg_quality < 0.8:
            base_score -= (0.8 - avg_quality)
            
        return max(0.0, min(1.0, base_score))
