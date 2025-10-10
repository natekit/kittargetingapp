"""
Topic similarity matrix for smart planner matching.
This defines how similar different topics are to each other.
"""

TOPIC_SIMILARITIES = {
    # Food & Cooking
    "Food & Cooking": {
        "Food & Cooking": 1.0,
        "Kitchen & Household": 0.8,
        "Health & Wellness": 0.6,
        "Lifestyle": 0.5,
        "Parenting": 0.4,
        "Travel": 0.3,
        "Technology": 0.2,
        "Fashion & Beauty": 0.3,
        "Finance": 0.1,
        "Gaming": 0.1,
        "Sports & Fitness": 0.4,
        "Education": 0.2,
        "Entertainment": 0.2,
        "Home & Garden": 0.7,
        "Automotive": 0.1,
        "Business": 0.1,
    },
    
    # Kitchen & Household
    "Kitchen & Household": {
        "Food & Cooking": 0.8,
        "Kitchen & Household": 1.0,
        "Health & Wellness": 0.5,
        "Lifestyle": 0.6,
        "Parenting": 0.5,
        "Travel": 0.2,
        "Technology": 0.3,
        "Fashion & Beauty": 0.2,
        "Finance": 0.1,
        "Gaming": 0.1,
        "Sports & Fitness": 0.3,
        "Education": 0.2,
        "Entertainment": 0.2,
        "Home & Garden": 0.8,
        "Automotive": 0.1,
        "Business": 0.1,
    },
    
    # Health & Wellness
    "Health & Wellness": {
        "Food & Cooking": 0.6,
        "Kitchen & Household": 0.5,
        "Health & Wellness": 1.0,
        "Lifestyle": 0.7,
        "Parenting": 0.6,
        "Travel": 0.3,
        "Technology": 0.2,
        "Fashion & Beauty": 0.4,
        "Finance": 0.2,
        "Gaming": 0.1,
        "Sports & Fitness": 0.8,
        "Education": 0.3,
        "Entertainment": 0.2,
        "Home & Garden": 0.3,
        "Automotive": 0.1,
        "Business": 0.1,
    },
    
    # Lifestyle
    "Lifestyle": {
        "Food & Cooking": 0.5,
        "Kitchen & Household": 0.6,
        "Health & Wellness": 0.7,
        "Lifestyle": 1.0,
        "Parenting": 0.6,
        "Travel": 0.5,
        "Technology": 0.3,
        "Fashion & Beauty": 0.7,
        "Finance": 0.3,
        "Gaming": 0.2,
        "Sports & Fitness": 0.5,
        "Education": 0.3,
        "Entertainment": 0.4,
        "Home & Garden": 0.6,
        "Automotive": 0.2,
        "Business": 0.2,
    },
    
    # Parenting
    "Parenting": {
        "Food & Cooking": 0.4,
        "Kitchen & Household": 0.5,
        "Health & Wellness": 0.6,
        "Lifestyle": 0.6,
        "Parenting": 1.0,
        "Travel": 0.4,
        "Technology": 0.2,
        "Fashion & Beauty": 0.3,
        "Finance": 0.4,
        "Gaming": 0.1,
        "Sports & Fitness": 0.4,
        "Education": 0.7,
        "Entertainment": 0.3,
        "Home & Garden": 0.5,
        "Automotive": 0.2,
        "Business": 0.1,
    },
    
    # Travel
    "Travel": {
        "Food & Cooking": 0.3,
        "Kitchen & Household": 0.2,
        "Health & Wellness": 0.3,
        "Lifestyle": 0.5,
        "Parenting": 0.4,
        "Travel": 1.0,
        "Technology": 0.3,
        "Fashion & Beauty": 0.4,
        "Finance": 0.2,
        "Gaming": 0.1,
        "Sports & Fitness": 0.3,
        "Education": 0.4,
        "Entertainment": 0.5,
        "Home & Garden": 0.2,
        "Automotive": 0.3,
        "Business": 0.2,
    },
    
    # Technology
    "Technology": {
        "Food & Cooking": 0.2,
        "Kitchen & Household": 0.3,
        "Health & Wellness": 0.2,
        "Lifestyle": 0.3,
        "Parenting": 0.2,
        "Travel": 0.3,
        "Technology": 1.0,
        "Fashion & Beauty": 0.2,
        "Finance": 0.4,
        "Gaming": 0.6,
        "Sports & Fitness": 0.2,
        "Education": 0.5,
        "Entertainment": 0.4,
        "Home & Garden": 0.3,
        "Automotive": 0.4,
        "Business": 0.6,
    },
    
    # Fashion & Beauty
    "Fashion & Beauty": {
        "Food & Cooking": 0.3,
        "Kitchen & Household": 0.2,
        "Health & Wellness": 0.4,
        "Lifestyle": 0.7,
        "Parenting": 0.3,
        "Travel": 0.4,
        "Technology": 0.2,
        "Fashion & Beauty": 1.0,
        "Finance": 0.2,
        "Gaming": 0.1,
        "Sports & Fitness": 0.4,
        "Education": 0.2,
        "Entertainment": 0.5,
        "Home & Garden": 0.2,
        "Automotive": 0.1,
        "Business": 0.1,
    },
    
    # Finance
    "Finance": {
        "Food & Cooking": 0.1,
        "Kitchen & Household": 0.1,
        "Health & Wellness": 0.2,
        "Lifestyle": 0.3,
        "Parenting": 0.4,
        "Travel": 0.2,
        "Technology": 0.4,
        "Fashion & Beauty": 0.2,
        "Finance": 1.0,
        "Gaming": 0.1,
        "Sports & Fitness": 0.2,
        "Education": 0.4,
        "Entertainment": 0.1,
        "Home & Garden": 0.2,
        "Automotive": 0.3,
        "Business": 0.7,
    },
    
    # Gaming
    "Gaming": {
        "Food & Cooking": 0.1,
        "Kitchen & Household": 0.1,
        "Health & Wellness": 0.1,
        "Lifestyle": 0.2,
        "Parenting": 0.1,
        "Travel": 0.1,
        "Technology": 0.6,
        "Fashion & Beauty": 0.1,
        "Finance": 0.1,
        "Gaming": 1.0,
        "Sports & Fitness": 0.2,
        "Education": 0.3,
        "Entertainment": 0.8,
        "Home & Garden": 0.1,
        "Automotive": 0.1,
        "Business": 0.1,
    },
    
    # Sports & Fitness
    "Sports & Fitness": {
        "Food & Cooking": 0.4,
        "Kitchen & Household": 0.3,
        "Health & Wellness": 0.8,
        "Lifestyle": 0.5,
        "Parenting": 0.4,
        "Travel": 0.3,
        "Technology": 0.2,
        "Fashion & Beauty": 0.4,
        "Finance": 0.2,
        "Gaming": 0.2,
        "Sports & Fitness": 1.0,
        "Education": 0.3,
        "Entertainment": 0.3,
        "Home & Garden": 0.2,
        "Automotive": 0.2,
        "Business": 0.1,
    },
    
    # Education
    "Education": {
        "Food & Cooking": 0.2,
        "Kitchen & Household": 0.2,
        "Health & Wellness": 0.3,
        "Lifestyle": 0.3,
        "Parenting": 0.7,
        "Travel": 0.4,
        "Technology": 0.5,
        "Fashion & Beauty": 0.2,
        "Finance": 0.4,
        "Gaming": 0.3,
        "Sports & Fitness": 0.3,
        "Education": 1.0,
        "Entertainment": 0.3,
        "Home & Garden": 0.2,
        "Automotive": 0.2,
        "Business": 0.4,
    },
    
    # Entertainment
    "Entertainment": {
        "Food & Cooking": 0.2,
        "Kitchen & Household": 0.2,
        "Health & Wellness": 0.2,
        "Lifestyle": 0.4,
        "Parenting": 0.3,
        "Travel": 0.5,
        "Technology": 0.4,
        "Fashion & Beauty": 0.5,
        "Finance": 0.1,
        "Gaming": 0.8,
        "Sports & Fitness": 0.3,
        "Education": 0.3,
        "Entertainment": 1.0,
        "Home & Garden": 0.2,
        "Automotive": 0.1,
        "Business": 0.1,
    },
    
    # Home & Garden
    "Home & Garden": {
        "Food & Cooking": 0.7,
        "Kitchen & Household": 0.8,
        "Health & Wellness": 0.3,
        "Lifestyle": 0.6,
        "Parenting": 0.5,
        "Travel": 0.2,
        "Technology": 0.3,
        "Fashion & Beauty": 0.2,
        "Finance": 0.2,
        "Gaming": 0.1,
        "Sports & Fitness": 0.2,
        "Education": 0.2,
        "Entertainment": 0.2,
        "Home & Garden": 1.0,
        "Automotive": 0.2,
        "Business": 0.1,
    },
    
    # Automotive
    "Automotive": {
        "Food & Cooking": 0.1,
        "Kitchen & Household": 0.1,
        "Health & Wellness": 0.1,
        "Lifestyle": 0.2,
        "Parenting": 0.2,
        "Travel": 0.3,
        "Technology": 0.4,
        "Fashion & Beauty": 0.1,
        "Finance": 0.3,
        "Gaming": 0.1,
        "Sports & Fitness": 0.2,
        "Education": 0.2,
        "Entertainment": 0.1,
        "Home & Garden": 0.2,
        "Automotive": 1.0,
        "Business": 0.3,
    },
    
    # Business
    "Business": {
        "Food & Cooking": 0.1,
        "Kitchen & Household": 0.1,
        "Health & Wellness": 0.1,
        "Lifestyle": 0.2,
        "Parenting": 0.1,
        "Travel": 0.2,
        "Technology": 0.6,
        "Fashion & Beauty": 0.1,
        "Finance": 0.7,
        "Gaming": 0.1,
        "Sports & Fitness": 0.1,
        "Education": 0.4,
        "Entertainment": 0.1,
        "Home & Garden": 0.1,
        "Automotive": 0.3,
        "Business": 1.0,
    },
}


def get_topic_similarity(topic1: str, topic2: str) -> float:
    """
    Get similarity score between two topics.
    Returns 0.0 if either topic is not found.
    """
    if topic1 not in TOPIC_SIMILARITIES:
        return 0.0
    
    return TOPIC_SIMILARITIES[topic1].get(topic2, 0.0)


def get_all_topics() -> list[str]:
    """Get list of all available topics."""
    return list(TOPIC_SIMILARITIES.keys())
