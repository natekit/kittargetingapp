# Smart Matching System - Testing & Optimization

This document describes the comprehensive testing and optimization tools for the smart matching system.

## 🚀 Quick Start

### Run All Tests
```bash
cd api
python run_smart_tests.py
```

### Deploy Smart Matching System
```bash
cd api
python deploy_smart_matching.py
```

## 📋 Test Components

### 1. Performance Testing (`test_smart_matching.py`)

Tests smart matching performance with large datasets (1000-5000 creators).

**Features:**
- Tests with different dataset sizes (100, 500, 1000, 2000, 5000 creators)
- Multiple test scenarios (basic, with demographics, high budget)
- Performance metrics (execution time, creator counts, success rates)
- Scalability analysis

**Usage:**
```bash
python test_smart_matching.py
```

**Output:**
- Performance metrics for each dataset size
- Recommendations for optimization
- Success/failure rates

### 2. Similarity Computation (`compute_similarities.py`)

Pre-computes creator similarities for performance optimization.

**Features:**
- Topic-based similarity calculation
- Demographic similarity calculation
- Combined similarity scores
- Batch processing for large datasets
- Database storage optimization

**Usage:**
```bash
python compute_similarities.py
```

**Output:**
- Similarity scores stored in database
- Processing statistics
- Performance metrics

### 3. Database Optimization (`optimize_database.py`)

Optimizes database for smart matching performance.

**Features:**
- Creates performance indexes
- Analyzes query performance
- Optimizes database settings
- Health checks and monitoring

**Usage:**
```bash
python optimize_database.py
```

**Output:**
- Index creation status
- Query performance analysis
- Database health metrics

## 🧪 Test Scenarios

### Performance Test Cases

1. **Basic Smart Matching**
   - Budget: $10,000
   - CPC: $1.50
   - Target CPA: $5.00
   - Horizon: 30 days

2. **With Target Demographics**
   - Same as basic + demographic targeting
   - Age: 25-34, Gender: Mostly women
   - Location: US, Interests: cooking, fitness

3. **High Budget Scenario**
   - Budget: $50,000
   - CPC: $2.00
   - Target CPA: $10.00
   - Horizon: 60 days

### Scalability Testing

Tests with different dataset sizes:
- **100 creators**: Quick validation
- **500 creators**: Development testing
- **1000 creators**: Production baseline
- **2000 creators**: Stress testing
- **5000 creators**: Maximum load testing

## 📊 Performance Metrics

### Key Performance Indicators

1. **Execution Time**
   - Target: < 2 seconds for 1000 creators
   - Acceptable: < 5 seconds for 1000 creators
   - Slow: > 5 seconds for 1000 creators

2. **Creator Selection**
   - Average creators found per test
   - Budget utilization percentage
   - CPA target achievement

3. **Database Performance**
   - Query execution times
   - Index usage statistics
   - Memory consumption

### Optimization Targets

- **Query Performance**: < 100ms for similarity lookups
- **Memory Usage**: < 500MB for 5000 creators
- **CPU Usage**: < 80% during peak processing
- **Database Size**: < 1GB for similarity data

## 🔧 Optimization Features

### Database Indexes

1. **Creator Demographics Index**
   ```sql
   CREATE INDEX idx_creators_demographics 
   ON creators (age_range, gender_skew, location)
   ```

2. **Similarity Lookup Index**
   ```sql
   CREATE INDEX idx_creator_similarities_lookup 
   ON creator_similarities (creator_a_id, similarity_type, similarity_score DESC)
   ```

3. **Topic/Keyword Indexes**
   ```sql
   CREATE INDEX idx_creator_topics_lookup 
   ON creator_topics (creator_id, topic_id)
   ```

### Similarity Pre-computation

- **Topic Similarities**: Pre-computed topic-based matches
- **Demographic Similarities**: Pre-computed demographic alignments
- **Combined Scores**: Weighted combination of topic + demographic
- **Batch Processing**: Efficient processing of large datasets

## 📈 Monitoring & Health Checks

### Database Health Metrics

1. **Table Sizes**: Monitor growth of similarity tables
2. **Index Usage**: Track index effectiveness
3. **Query Performance**: Monitor slow queries
4. **Memory Usage**: Track database memory consumption

### Performance Monitoring

1. **Response Times**: Track API response times
2. **Throughput**: Monitor requests per second
3. **Error Rates**: Track failure rates
4. **Resource Usage**: Monitor CPU, memory, disk usage

## 🚨 Troubleshooting

### Common Issues

1. **Slow Performance**
   - Check database indexes
   - Run database optimization
   - Verify similarity data exists

2. **Memory Issues**
   - Reduce dataset size for testing
   - Check database memory settings
   - Monitor similarity table size

3. **Database Errors**
   - Verify database connection
   - Check migration status
   - Validate table structure

### Debug Commands

```bash
# Check database health
python optimize_database.py

# Test with smaller dataset
python test_smart_matching.py --quick

# Skip similarity computation
python deploy_smart_matching.py --skip-similarities
```

## 📝 Test Results Interpretation

### Success Criteria

- ✅ All tests pass
- ✅ Performance targets met
- ✅ Database optimized
- ✅ Similarities computed
- ✅ System validated

### Warning Signs

- ⚠️ Slow performance (> 5 seconds)
- ⚠️ High memory usage
- ⚠️ Database errors
- ⚠️ Missing similarity data

### Failure Indicators

- ❌ Tests failing
- ❌ Database connection issues
- ❌ Performance below thresholds
- ❌ System validation failures

## 🔄 Continuous Integration

### Automated Testing

The testing system can be integrated into CI/CD pipelines:

```bash
# Run quick tests in CI
python run_smart_tests.py --quick

# Deploy with validation
python deploy_smart_matching.py --skip-tests
```

### Performance Regression Testing

- Monitor performance metrics over time
- Alert on performance degradation
- Track optimization effectiveness
- Validate system health

## 📚 Additional Resources

- **Database Schema**: See `models.py` for table definitions
- **API Documentation**: See `analytics.py` for endpoint details
- **Frontend Integration**: See `PlannerPage.tsx` for UI components
- **Deployment Guide**: See `DEPLOYMENT.md` for production setup

## 🆘 Support

For issues with testing or optimization:

1. Check logs in `smart_matching_tests.log`
2. Verify database connectivity
3. Run individual test components
4. Review performance metrics
5. Contact development team

---

**Note**: These tools are designed for production use and should be run in a controlled environment. Always backup your database before running optimization scripts.
