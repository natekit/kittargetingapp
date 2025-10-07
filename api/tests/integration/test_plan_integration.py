import pytest
from datetime import date


class TestPlanIntegration:
    """Integration tests for the /plan endpoint."""

    def test_plan_with_synthetic_data(self, client, test_data, db_session):
        """Test: A lightweight /plan integration test with synthetic data returning a non-empty set."""
        
        # Create additional test data for planning
        # Add more creators with different performance
        creators_data = [
            {
                "creator_id": 2,
                "name": "High Performer",
                "acct_id": "HIGH001",
                "owner_email": "high@example.com",
                "topic": "High Performance",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z"
            },
            {
                "creator_id": 3,
                "name": "Medium Performer",
                "acct_id": "MED001",
                "owner_email": "medium@example.com",
                "topic": "Medium Performance",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z"
            },
            {
                "creator_id": 4,
                "name": "Low Performer",
                "acct_id": "LOW001",
                "owner_email": "low@example.com",
                "topic": "Low Performance",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z"
            }
        ]
        
        for creator_data in creators_data:
            creator = Creator(**creator_data)
            db_session.add(creator)
        
        # Create performance data (click_uniques) for the creators
        from app.models import PerfUpload, ClickUnique
        from datetime import datetime
        
        # Create a performance upload
        perf_upload = PerfUpload(
            perf_upload_id=1,
            insertion_id=1,
            uploaded_at=datetime.utcnow(),
            filename="test_performance.csv"
        )
        db_session.add(perf_upload)
        db_session.flush()
        
        # Add click data for each creator (simulating different performance levels)
        click_data = [
            {"creator_id": 1, "unique_clicks": 100, "execution_date": date(2025, 1, 1)},
            {"creator_id": 2, "unique_clicks": 500, "execution_date": date(2025, 1, 1)},
            {"creator_id": 3, "unique_clicks": 200, "execution_date": date(2025, 1, 1)},
            {"creator_id": 4, "unique_clicks": 50, "execution_date": date(2025, 1, 1)},
        ]
        
        for click_info in click_data:
            click_unique = ClickUnique(
                perf_upload_id=1,
                creator_id=click_info["creator_id"],
                execution_date=click_info["execution_date"],
                unique_clicks=click_info["unique_clicks"],
                raw_clicks=click_info["unique_clicks"] + 10,
                flagged=False,
                status="active"
            )
            db_session.add(click_unique)
        
        # Add conversion data for some creators
        from app.models import ConvUpload, Conversion
        from sqlalchemy.dialects.postgresql import DATERANGE
        
        conv_upload = ConvUpload(
            conv_upload_id=1,
            advertiser_id=1,
            campaign_id=1,
            insertion_id=1,
            uploaded_at=datetime.utcnow(),
            filename="test_conversions.csv",
            range_start=date(2025, 1, 1),
            range_end=date(2025, 1, 31),
            tz="America/New_York"
        )
        db_session.add(conv_upload)
        db_session.flush()
        
        # Add conversion data (simulating different conversion rates)
        conversion_data = [
            {"creator_id": 1, "conversions": 5},   # 5% CVR
            {"creator_id": 2, "conversions": 50},  # 10% CVR
            {"creator_id": 3, "conversions": 10},  # 5% CVR
            # Creator 4 has no conversions (0% CVR)
        ]
        
        for conv_info in conversion_data:
            conversion = Conversion(
                conv_upload_id=1,
                insertion_id=1,
                creator_id=conv_info["creator_id"],
                period=DATERANGE(date(2025, 1, 1), date(2025, 1, 31), '[]'),
                conversions=conv_info["conversions"]
            )
            db_session.add(conversion)
        
        db_session.commit()
        
        # Test the plan endpoint
        plan_request = {
            "category": "Test Category",
            "cpc": 0.50,
            "budget": 1000.0,
            "target_cpa": 5.0,
            "horizon_days": 30
        }
        
        response = client.post("/api/plan", json=plan_request)
        
        assert response.status_code == 200
        result = response.json()
        
        # Verify the response structure
        assert "picked_creators" in result
        assert "total_spend" in result
        assert "total_conversions" in result
        assert "blended_cpa" in result
        assert "budget_utilization" in result
        
        # Verify we got a non-empty result
        assert len(result["picked_creators"]) > 0
        
        # Verify the picked creators have the expected structure
        for creator in result["picked_creators"]:
            assert "creator_id" in creator
            assert "name" in creator
            assert "acct_id" in creator
            assert "expected_cvr" in creator
            assert "expected_cpa" in creator
            assert "expected_clicks" in creator
            assert "expected_spend" in creator
            assert "expected_conversions" in creator
            assert "value_ratio" in creator
            
            # Verify expected CPA is within target
            assert creator["expected_cpa"] <= 5.0
        
        # Verify totals make sense
        assert result["total_spend"] > 0
        assert result["total_spend"] <= 1000.0  # Should not exceed budget
        assert result["total_conversions"] > 0
        assert result["blended_cpa"] > 0
        assert result["budget_utilization"] > 0
        assert result["budget_utilization"] <= 1.0

    def test_plan_with_insertion_id(self, client, test_data, db_session):
        """Test: Plan with insertion_id instead of cpc."""
        
        # Create performance data
        from app.models import PerfUpload, ClickUnique
        from datetime import datetime
        
        perf_upload = PerfUpload(
            perf_upload_id=1,
            insertion_id=1,
            uploaded_at=datetime.utcnow(),
            filename="test_performance.csv"
        )
        db_session.add(perf_upload)
        db_session.flush()
        
        click_unique = ClickUnique(
            perf_upload_id=1,
            creator_id=1,
            execution_date=date(2025, 1, 1),
            unique_clicks=200,
            raw_clicks=220,
            flagged=False,
            status="active"
        )
        db_session.add(click_unique)
        
        # Create conversion data
        from app.models import ConvUpload, Conversion
        from sqlalchemy.dialects.postgresql import DATERANGE
        
        conv_upload = ConvUpload(
            conv_upload_id=1,
            advertiser_id=1,
            campaign_id=1,
            insertion_id=1,
            uploaded_at=datetime.utcnow(),
            filename="test_conversions.csv",
            range_start=date(2025, 1, 1),
            range_end=date(2025, 1, 31),
            tz="America/New_York"
        )
        db_session.add(conv_upload)
        db_session.flush()
        
        conversion = Conversion(
            conv_upload_id=1,
            insertion_id=1,
            creator_id=1,
            period=DATERANGE(date(2025, 1, 1), date(2025, 1, 31), '[]'),
            conversions=20
        )
        db_session.add(conversion)
        db_session.commit()
        
        # Test plan with insertion_id
        plan_request = {
            "category": "Test Category",
            "insertion_id": 1,
            "budget": 500.0,
            "target_cpa": 10.0,
            "horizon_days": 30
        }
        
        response = client.post("/api/plan", json=plan_request)
        
        assert response.status_code == 200
        result = response.json()
        
        # Verify we got results
        assert len(result["picked_creators"]) > 0
        assert result["total_spend"] > 0
        assert result["total_conversions"] > 0

    def test_plan_with_advertiser_id(self, client, test_data, db_session):
        """Test: Plan with advertiser_id instead of category."""
        
        # Create performance and conversion data (same as above)
        from app.models import PerfUpload, ClickUnique, ConvUpload, Conversion
        from datetime import datetime
        from sqlalchemy.dialects.postgresql import DATERANGE
        
        perf_upload = PerfUpload(
            perf_upload_id=1,
            insertion_id=1,
            uploaded_at=datetime.utcnow(),
            filename="test_performance.csv"
        )
        db_session.add(perf_upload)
        db_session.flush()
        
        click_unique = ClickUnique(
            perf_upload_id=1,
            creator_id=1,
            execution_date=date(2025, 1, 1),
            unique_clicks=300,
            raw_clicks=330,
            flagged=False,
            status="active"
        )
        db_session.add(click_unique)
        
        conv_upload = ConvUpload(
            conv_upload_id=1,
            advertiser_id=1,
            campaign_id=1,
            insertion_id=1,
            uploaded_at=datetime.utcnow(),
            filename="test_conversions.csv",
            range_start=date(2025, 1, 1),
            range_end=date(2025, 1, 31),
            tz="America/New_York"
        )
        db_session.add(conv_upload)
        db_session.flush()
        
        conversion = Conversion(
            conv_upload_id=1,
            insertion_id=1,
            creator_id=1,
            period=DATERANGE(date(2025, 1, 1), date(2025, 1, 31), '[]'),
            conversions=30
        )
        db_session.add(conversion)
        db_session.commit()
        
        # Test plan with advertiser_id
        plan_request = {
            "advertiser_id": 1,
            "cpc": 0.75,
            "budget": 750.0,
            "target_cpa": 8.0,
            "horizon_days": 30
        }
        
        response = client.post("/api/plan", json=plan_request)
        
        assert response.status_code == 200
        result = response.json()
        
        # Verify we got results
        assert len(result["picked_creators"]) > 0
        assert result["total_spend"] > 0
        assert result["total_conversions"] > 0
