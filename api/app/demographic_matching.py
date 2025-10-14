"""
Demographic matching utilities for smart planner.
Handles age range, gender, location, and interests matching.
"""

from typing import List, Tuple, Optional
import re


def match_age_ranges(creator_age: str, target_age: str) -> float:
    """
    Calculate age range similarity score.
    Returns 0.0 to 1.0 based on overlap.
    """
    if not creator_age or not target_age:
        return 0.0
    
    # Parse age ranges (e.g., "25-34", "18-24")
    creator_min, creator_max = _parse_age_range(creator_age)
    target_min, target_max = _parse_age_range(target_age)
    
    if creator_min is None or creator_max is None or target_min is None or target_max is None:
        return 0.0
    
    # Calculate overlap
    overlap_start = max(creator_min, target_min)
    overlap_end = min(creator_max, target_max)
    
    if overlap_start > overlap_end:
        return 0.0  # No overlap
    
    overlap_size = overlap_end - overlap_start + 1
    creator_size = creator_max - creator_min + 1
    target_size = target_max - target_min + 1
    
    # Return the overlap as a percentage of the smaller range
    return overlap_size / min(creator_size, target_size)


def _parse_age_range(age_range: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse age range string into min and max values."""
    if not age_range:
        return None, None
    
    # Handle different formats
    if '-' in age_range:
        try:
            parts = age_range.split('-')
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
        except ValueError:
            pass
    
    return None, None


def match_gender_skew(creator_gender: str, target_gender: str) -> float:
    """
    Calculate gender skew similarity score.
    Returns 1.0 for exact match, 0.5 for partial match, 0.0 for no match.
    """
    if not creator_gender or not target_gender:
        return 0.0
    
    creator_gender = creator_gender.lower().strip()
    target_gender = target_gender.lower().strip()
    
    if creator_gender == target_gender:
        return 1.0
    
    # Partial matches
    if "even" in creator_gender and "even" in target_gender:
        return 0.8
    
    if ("men" in creator_gender and "men" in target_gender) or \
       ("women" in creator_gender and "women" in target_gender):
        return 0.6
    
    return 0.0


def match_location(creator_location: str, target_location: str) -> float:
    """
    Calculate location similarity score.
    Returns 1.0 for exact match, 0.0 for no match.
    """
    if not creator_location or not target_location:
        return 0.0
    
    creator_location = creator_location.upper().strip()
    target_location = target_location.upper().strip()
    
    if creator_location == target_location:
        return 1.0
    
    return 0.0


def match_interests(creator_interests: str, target_interests: str) -> float:
    """
    Calculate interests similarity score.
    Returns 0.0 to 1.0 based on overlap percentage.
    """
    if not creator_interests or not target_interests:
        return 0.0
    
    # Parse comma-separated interests
    creator_list = _parse_interests(creator_interests)
    target_list = _parse_interests(target_interests)
    
    if not creator_list or not target_list:
        return 0.0
    
    # Calculate overlap
    creator_set = set(creator_list)
    target_set = set(target_list)
    
    intersection = creator_set.intersection(target_set)
    union = creator_set.union(target_set)
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)


def _parse_interests(interests: str) -> List[str]:
    """Parse comma-separated interests into a list."""
    if not interests:
        return []
    
    # Split by comma and clean up
    interests_list = [interest.strip().lower() for interest in interests.split(',')]
    
    # Remove empty strings
    return [interest for interest in interests_list if interest]


def calculate_demographic_similarity(
    creator_demographics: dict,
    target_demographics: dict
) -> float:
    """
    Calculate overall demographic similarity score.
    
    Args:
        creator_demographics: {
            'age_range': str,
            'gender_skew': str,
            'location': str,
            'interests': str
        }
        target_demographics: {
            'target_age_range': str,
            'target_gender_skew': str,
            'target_location': str,
            'target_interests': str
        }
    
    Returns:
        float: 0.0 to 1.0 similarity score
    """
    scores = []
    weights = []
    
    # Age range matching (weight: 0.3)
    if creator_demographics.get('age_range') and target_demographics.get('target_age_range'):
        age_score = match_age_ranges(
            creator_demographics['age_range'],
            target_demographics['target_age_range']
        )
        scores.append(age_score)
        weights.append(0.3)
    
    # Gender skew matching (weight: 0.2)
    if creator_demographics.get('gender_skew') and target_demographics.get('target_gender_skew'):
        gender_score = match_gender_skew(
            creator_demographics['gender_skew'],
            target_demographics['target_gender_skew']
        )
        scores.append(gender_score)
        weights.append(0.2)
    
    # Location matching (weight: 0.2)
    if creator_demographics.get('location') and target_demographics.get('target_location'):
        location_score = match_location(
            creator_demographics['location'],
            target_demographics['target_location']
        )
        scores.append(location_score)
        weights.append(0.2)
    
    # Interests matching (weight: 0.3)
    if creator_demographics.get('interests') and target_demographics.get('target_interests'):
        interests_score = match_interests(
            creator_demographics['interests'],
            target_demographics['target_interests']
        )
        scores.append(interests_score)
        weights.append(0.3)
    
    if not scores:
        return 0.0
    
    # Calculate weighted average
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
    
    weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
    return weighted_sum / total_weight
