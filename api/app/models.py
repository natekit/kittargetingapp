from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, Boolean, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import CITEXT, DATERANGE
from sqlalchemy.orm import relationship
from sqlalchemy.schema import CheckConstraint
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from app.db import Base


class Advertiser(Base):
    __tablename__ = "advertisers"
    
    advertiser_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    category = Column(String(100), nullable=True)


class Campaign(Base):
    __tablename__ = "campaigns"
    
    campaign_id = Column(Integer, primary_key=True, index=True)
    advertiser_id = Column(Integer, ForeignKey("advertisers.advertiser_id"), nullable=False)
    name = Column(String(255), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    
    # Relationships
    advertiser = relationship("Advertiser", back_populates="campaigns")
    insertions = relationship("Insertion", back_populates="campaign")


class Insertion(Base):
    __tablename__ = "insertions"
    
    insertion_id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.campaign_id"), nullable=False)
    month_start = Column(Date, nullable=False)
    month_end = Column(Date, nullable=False)
    cpc = Column(Numeric(10, 4), nullable=False)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="insertions")
    placements = relationship("Placement", back_populates="insertion")
    perf_uploads = relationship("PerfUpload", back_populates="insertion")
    conv_uploads = relationship("ConvUpload", back_populates="insertion")
    conversions = relationship("Conversion", back_populates="insertion")


class Creator(Base):
    __tablename__ = "creators"
    
    creator_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    acct_id = Column(String(100), unique=True, nullable=False, index=True)
    owner_email = Column(CITEXT, unique=True, nullable=False, index=True)
    topic = Column(Text, nullable=True)
    conservative_click_estimate = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False)
    
    # Relationships
    placements = relationship("Placement", back_populates="creator")
    click_uniques = relationship("ClickUnique", back_populates="creator")
    conversions = relationship("Conversion", back_populates="creator")


class Placement(Base):
    __tablename__ = "placements"
    
    placement_id = Column(Integer, primary_key=True, index=True)
    insertion_id = Column(Integer, ForeignKey("insertions.insertion_id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("creators.creator_id"), nullable=False)
    notes = Column(Text, nullable=True)
    
    # Relationships
    insertion = relationship("Insertion", back_populates="placements")
    creator = relationship("Creator", back_populates="placements")


class PerfUpload(Base):
    __tablename__ = "perf_uploads"
    
    perf_upload_id = Column(Integer, primary_key=True, index=True)
    insertion_id = Column(Integer, ForeignKey("insertions.insertion_id"), nullable=False)
    uploaded_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()")
    filename = Column(Text, nullable=False)
    
    # Relationships
    insertion = relationship("Insertion", back_populates="perf_uploads")
    click_uniques = relationship("ClickUnique", back_populates="perf_upload")


class ClickUnique(Base):
    __tablename__ = "click_uniques"
    
    click_id = Column(Integer, primary_key=True, index=True)
    perf_upload_id = Column(Integer, ForeignKey("perf_uploads.perf_upload_id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("creators.creator_id"), nullable=False)
    execution_date = Column(Date, nullable=False)
    unique_clicks = Column(Integer, nullable=False)
    raw_clicks = Column(Integer, nullable=True)
    flagged = Column(Boolean, nullable=True)
    status = Column(String(50), nullable=True)
    
    # Relationships
    perf_upload = relationship("PerfUpload", back_populates="click_uniques")
    creator = relationship("Creator", back_populates="click_uniques")


class ConvUpload(Base):
    __tablename__ = "conv_uploads"
    
    conv_upload_id = Column(Integer, primary_key=True, index=True)
    advertiser_id = Column(Integer, ForeignKey("advertisers.advertiser_id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.campaign_id"), nullable=False)
    insertion_id = Column(Integer, ForeignKey("insertions.insertion_id"), nullable=False)
    uploaded_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()")
    filename = Column(Text, nullable=False)
    range_start = Column(Date, nullable=False)
    range_end = Column(Date, nullable=False)
    tz = Column(String(50), nullable=False, server_default="America/New_York")
    
    # Relationships
    advertiser = relationship("Advertiser")
    campaign = relationship("Campaign")
    insertion = relationship("Insertion", back_populates="conv_uploads")
    conversions = relationship("Conversion", back_populates="conv_upload")


class Conversion(Base):
    __tablename__ = "conversions"
    
    conversion_id = Column(Integer, primary_key=True, index=True)
    conv_upload_id = Column(Integer, ForeignKey("conv_uploads.conv_upload_id"), nullable=False)
    insertion_id = Column(Integer, ForeignKey("insertions.insertion_id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("creators.creator_id"), nullable=False)
    period = Column(DATERANGE, nullable=False)
    conversions = Column(Integer, nullable=False)
    
    # Relationships
    conv_upload = relationship("ConvUpload", back_populates="conversions")
    insertion = relationship("Insertion", back_populates="conversions")
    creator = relationship("Creator", back_populates="conversions")
    
    # GiST exclusion constraint to prevent overlapping periods per (creator_id, insertion_id)
    __table_args__ = (
        ExcludeConstraint(
            ("creator_id", "="),
            ("insertion_id", "="),
            ("period", "&&"),
            using="gist"
        ),
    )


class DeclinedCreator(Base):
    __tablename__ = "declined_creators"
    
    declined_id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("creators.creator_id"), nullable=False)
    advertiser_id = Column(Integer, ForeignKey("advertisers.advertiser_id"), nullable=False)
    declined_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()")
    reason = Column(String(255), nullable=True)  # Optional reason for decline
    
    # Relationships
    creator = relationship("Creator")
    advertiser = relationship("Advertiser")
    
    # Unique constraint to prevent duplicate declined records
    __table_args__ = (
        CheckConstraint("creator_id != advertiser_id", name="check_creator_not_advertiser"),
    )


# Update relationships
Advertiser.campaigns = relationship("Campaign", back_populates="advertiser")

