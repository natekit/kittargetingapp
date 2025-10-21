import re
from typing import Optional


def extract_first_email(s: str) -> Optional[str]:
    """
    Extract the first email address from a string that may contain mailto links.
    
    Handles patterns like:
    - "Contact us at john@example.com"
    - "Email: (mailto:jane@example.com)"
    - "Send to (mailto:admin@company.com) for support"
    
    Args:
        s: String that may contain email addresses or mailto links
        
    Returns:
        First email address found, or None if no email found
    """
    if not s:
        return None
    
    # Pattern to match email addresses, including those in mailto links
    # This regex handles both plain emails and mailto: prefixed emails
    email_pattern = r'(?:mailto:)?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    
    matches = re.findall(email_pattern, s, re.IGNORECASE)
    
    if matches:
        return matches[0]
    
    return None







