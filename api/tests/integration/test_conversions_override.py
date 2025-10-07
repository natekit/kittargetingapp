import pytest
import io
import csv
from datetime import date
from sqlalchemy.dialects.postgresql import DATERANGE
from app.models import ConvUpload, Conversion


class TestConversionsOverride:
    """Test cases for conversions override logic."""

    def test_conversions_same_range_replacement(self, client, test_data, db_session):
        """Test: Insert 2025-09-01..2025-09-07, then re-upload same range → only the latest row remains."""
        
        # First upload
        csv_content_1 = "Acct Id,Conversions\nTEST123,10"
        files_1 = {"file": ("conversions1.csv", io.StringIO(csv_content_1), "text/csv")}
        
        response_1 = client.post(
            "/api/uploads/conversions",
            params={
                "advertiser_id": 1,
                "campaign_id": 1,
                "insertion_id": 1,
                "range_start": "2025-09-01",
                "range_end": "2025-09-07"
            },
            files=files_1
        )
        
        assert response_1.status_code == 200
        result_1 = response_1.json()
        assert result_1["inserted_rows"] == 1
        assert result_1["replaced_rows"] == 0
        
        # Check that conversion was inserted
        conversions_1 = db_session.query(Conversion).filter(
            Conversion.creator_id == 1,
            Conversion.insertion_id == 1
        ).all()
        assert len(conversions_1) == 1
        assert conversions_1[0].conversions == 10
        
        # Second upload with same range
        csv_content_2 = "Acct Id,Conversions\nTEST123,25"
        files_2 = {"file": ("conversions2.csv", io.StringIO(csv_content_2), "text/csv")}
        
        response_2 = client.post(
            "/api/uploads/conversions",
            params={
                "advertiser_id": 1,
                "campaign_id": 1,
                "insertion_id": 1,
                "range_start": "2025-09-01",
                "range_end": "2025-09-07"
            },
            files=files_2
        )
        
        assert response_2.status_code == 200
        result_2 = response_2.json()
        assert result_2["inserted_rows"] == 1
        assert result_2["replaced_rows"] == 1  # Should replace the previous one
        
        # Check that only the latest conversion remains
        conversions_2 = db_session.query(Conversion).filter(
            Conversion.creator_id == 1,
            Conversion.insertion_id == 1
        ).all()
        assert len(conversions_2) == 1
        assert conversions_2[0].conversions == 25

    def test_conversions_overlapping_range_replacement(self, client, test_data, db_session):
        """Test: Upload overlapping 2025-09-03..2025-09-10 → old overlaps removed before insert."""
        
        # First upload: 2025-09-01 to 2025-09-07
        csv_content_1 = "Acct Id,Conversions\nTEST123,15"
        files_1 = {"file": ("conversions1.csv", io.StringIO(csv_content_1), "text/csv")}
        
        response_1 = client.post(
            "/api/uploads/conversions",
            params={
                "advertiser_id": 1,
                "campaign_id": 1,
                "insertion_id": 1,
                "range_start": "2025-09-01",
                "range_end": "2025-09-07"
            },
            files=files_1
        )
        
        assert response_1.status_code == 200
        result_1 = response_1.json()
        assert result_1["inserted_rows"] == 1
        
        # Check initial conversion
        conversions_1 = db_session.query(Conversion).filter(
            Conversion.creator_id == 1,
            Conversion.insertion_id == 1
        ).all()
        assert len(conversions_1) == 1
        assert conversions_1[0].conversions == 15
        
        # Second upload with overlapping range: 2025-09-03 to 2025-09-10
        csv_content_2 = "Acct Id,Conversions\nTEST123,30"
        files_2 = {"file": ("conversions2.csv", io.StringIO(csv_content_2), "text/csv")}
        
        response_2 = client.post(
            "/api/uploads/conversions",
            params={
                "advertiser_id": 1,
                "campaign_id": 1,
                "insertion_id": 1,
                "range_start": "2025-09-03",
                "range_end": "2025-09-10"
            },
            files=files_2
        )
        
        assert response_2.status_code == 200
        result_2 = response_2.json()
        assert result_2["inserted_rows"] == 1
        assert result_2["replaced_rows"] == 1  # Should replace the overlapping one
        
        # Check that only the new conversion remains (overlapping one was removed)
        conversions_2 = db_session.query(Conversion).filter(
            Conversion.creator_id == 1,
            Conversion.insertion_id == 1
        ).all()
        assert len(conversions_2) == 1
        assert conversions_2[0].conversions == 30

    def test_conversions_non_overlapping_ranges(self, client, test_data, db_session):
        """Test: Non-overlapping ranges should not affect each other."""
        
        # First upload: 2025-09-01 to 2025-09-05
        csv_content_1 = "Acct Id,Conversions\nTEST123,10"
        files_1 = {"file": ("conversions1.csv", io.StringIO(csv_content_1), "text/csv")}
        
        response_1 = client.post(
            "/api/uploads/conversions",
            params={
                "advertiser_id": 1,
                "campaign_id": 1,
                "insertion_id": 1,
                "range_start": "2025-09-01",
                "range_end": "2025-09-05"
            },
            files=files_1
        )
        
        assert response_1.status_code == 200
        
        # Second upload: 2025-09-10 to 2025-09-15 (non-overlapping)
        csv_content_2 = "Acct Id,Conversions\nTEST123,20"
        files_2 = {"file": ("conversions2.csv", io.StringIO(csv_content_2), "text/csv")}
        
        response_2 = client.post(
            "/api/uploads/conversions",
            params={
                "advertiser_id": 1,
                "campaign_id": 1,
                "insertion_id": 1,
                "range_start": "2025-09-10",
                "range_end": "2025-09-15"
            },
            files=files_2
        )
        
        assert response_2.status_code == 200
        result_2 = response_2.json()
        assert result_2["inserted_rows"] == 1
        assert result_2["replaced_rows"] == 0  # No overlap, so no replacement
        
        # Check that both conversions exist
        conversions = db_session.query(Conversion).filter(
            Conversion.creator_id == 1,
            Conversion.insertion_id == 1
        ).all()
        assert len(conversions) == 2
        
        # Check that both have correct values
        conversion_values = [c.conversions for c in conversions]
        assert 10 in conversion_values
        assert 20 in conversion_values

    def test_conversions_multiple_creators_overlap(self, client, test_data, db_session):
        """Test: Overlap handling with multiple creators."""
        
        # Create second creator
        creator2 = Creator(
            creator_id=2,
            name="Test Creator 2",
            acct_id="TEST456",
            owner_email="creator2@example.com",
            topic="Test Topic 2",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z"
        )
        db_session.add(creator2)
        db_session.commit()
        
        # Upload for creator 1: 2025-09-01 to 2025-09-10
        csv_content_1 = "Acct Id,Conversions\nTEST123,10"
        files_1 = {"file": ("conversions1.csv", io.StringIO(csv_content_1), "text/csv")}
        
        response_1 = client.post(
            "/api/uploads/conversions",
            params={
                "advertiser_id": 1,
                "campaign_id": 1,
                "insertion_id": 1,
                "range_start": "2025-09-01",
                "range_end": "2025-09-10"
            },
            files=files_1
        )
        
        assert response_1.status_code == 200
        
        # Upload for creator 2: 2025-09-05 to 2025-09-15
        csv_content_2 = "Acct Id,Conversions\nTEST456,20"
        files_2 = {"file": ("conversions2.csv", io.StringIO(csv_content_2), "text/csv")}
        
        response_2 = client.post(
            "/api/uploads/conversions",
            params={
                "advertiser_id": 1,
                "campaign_id": 1,
                "insertion_id": 1,
                "range_start": "2025-09-05",
                "range_end": "2025-09-15"
            },
            files=files_2
        )
        
        assert response_2.status_code == 200
        
        # Upload overlapping for creator 1: 2025-09-03 to 2025-09-07
        csv_content_3 = "Acct Id,Conversions\nTEST123,30"
        files_3 = {"file": ("conversions3.csv", io.StringIO(csv_content_3), "text/csv")}
        
        response_3 = client.post(
            "/api/uploads/conversions",
            params={
                "advertiser_id": 1,
                "campaign_id": 1,
                "insertion_id": 1,
                "range_start": "2025-09-03",
                "range_end": "2025-09-07"
            },
            files=files_3
        )
        
        assert response_3.status_code == 200
        result_3 = response_3.json()
        assert result_3["replaced_rows"] == 1  # Should replace creator 1's conversion
        
        # Check final state
        conversions = db_session.query(Conversion).filter(
            Conversion.insertion_id == 1
        ).all()
        assert len(conversions) == 2  # One for each creator
        
        # Creator 1 should have the new value (30), creator 2 should be unchanged (20)
        creator1_conversion = next(c for c in conversions if c.creator_id == 1)
        creator2_conversion = next(c for c in conversions if c.creator_id == 2)
        
        assert creator1_conversion.conversions == 30
        assert creator2_conversion.conversions == 20
