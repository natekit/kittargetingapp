import pytest
from app.routers.uploads import extract_email_from_creator


class TestExtractEmailFromCreator:
    """Test cases for extract_email_from_creator function."""

    def test_real_mom_nutrition_simple_email(self):
        """Test: Real Mom Nutrition (sally.kuz@gmail.com)"""
        creator_field = "Real Mom Nutrition (sally.kuz@gmail.com)"
        result = extract_email_from_creator(creator_field)
        assert result == "sally.kuz@gmail.com"

    def test_real_mom_nutrition_markdown_email(self):
        """Test: Real Mom Nutrition ([sally.kuz@gmail.com](mailto:sally.kuz@gmail.com))"""
        creator_field = "Real Mom Nutrition ([sally.kuz@gmail.com](mailto:sally.kuz@gmail.com))"
        result = extract_email_from_creator(creator_field)
        assert result == "sally.kuz@gmail.com"

    def test_name_with_angle_brackets(self):
        """Test: Name <owner@example.co.uk>"""
        creator_field = "Name <owner@example.co.uk>"
        result = extract_email_from_creator(creator_field)
        assert result == "owner@example.co.uk"

    def test_simple_email_only(self):
        """Test: owner@example.com"""
        creator_field = "owner@example.com"
        result = extract_email_from_creator(creator_field)
        assert result == "owner@example.com"

    def test_markdown_mailto_format(self):
        """Test: [mailto:email@domain.com] format"""
        creator_field = "Creator Name [mailto:email@domain.com]"
        result = extract_email_from_creator(creator_field)
        assert result == "email@domain.com"

    def test_markdown_mailto_with_text(self):
        """Test: [email@domain.com](mailto:email@domain.com) format"""
        creator_field = "Creator Name [email@domain.com](mailto:email@domain.com)"
        result = extract_email_from_creator(creator_field)
        assert result == "email@domain.com"

    def test_multiple_emails_returns_first(self):
        """Test: Multiple emails should return the first one found"""
        creator_field = "Creator Name (first@example.com) and (second@example.com)"
        result = extract_email_from_creator(creator_field)
        assert result == "first@example.com"

    def test_markdown_priority_over_regex(self):
        """Test: [mailto:...] format takes priority over regex pattern"""
        creator_field = "Creator [mailto:priority@example.com] (other@example.com)"
        result = extract_email_from_creator(creator_field)
        assert result == "priority@example.com"

    def test_case_insensitive_markdown(self):
        """Test: [MAILTO:...] should work case-insensitively"""
        creator_field = "Creator [MAILTO:EMAIL@EXAMPLE.COM]"
        result = extract_email_from_creator(creator_field)
        assert result == "email@example.com"

    def test_email_with_subdomain(self):
        """Test: Email with subdomain"""
        creator_field = "Creator (user@mail.example.com)"
        result = extract_email_from_creator(creator_field)
        assert result == "user@mail.example.com"

    def test_email_with_plus_sign(self):
        """Test: Email with plus sign (common in Gmail)"""
        creator_field = "Creator (user+tag@gmail.com)"
        result = extract_email_from_creator(creator_field)
        assert result == "user+tag@gmail.com"

    def test_email_with_dash_in_domain(self):
        """Test: Email with dash in domain"""
        creator_field = "Creator (user@example-site.com)"
        result = extract_email_from_creator(creator_field)
        assert result == "user@example-site.com"

    def test_no_email_found(self):
        """Test: No email in the field"""
        creator_field = "Creator Name without email"
        result = extract_email_from_creator(creator_field)
        assert result is None

    def test_empty_string(self):
        """Test: Empty string"""
        creator_field = ""
        result = extract_email_from_creator(creator_field)
        assert result is None

    def test_none_input(self):
        """Test: None input"""
        creator_field = None
        result = extract_email_from_creator(creator_field)
        assert result is None

    def test_whitespace_handling(self):
        """Test: Whitespace around email is trimmed"""
        creator_field = "  Creator Name (  email@example.com  )  "
        result = extract_email_from_creator(creator_field)
        assert result == "email@example.com"

    def test_invalid_email_format(self):
        """Test: Invalid email format returns None"""
        creator_field = "Creator (not-an-email)"
        result = extract_email_from_creator(creator_field)
        assert result is None

    def test_email_with_special_characters(self):
        """Test: Email with special characters in local part"""
        creator_field = "Creator (user.name+tag@example.com)"
        result = extract_email_from_creator(creator_field)
        assert result == "user.name+tag@example.com"
