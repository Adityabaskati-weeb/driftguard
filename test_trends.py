"""test_trends.py

Unit tests for trend computation and detection logic.
"""

import pytest
import sqlite3
from app.trends import (
    detect_trend_direction,
    compute_trend_adjustment,
    compute_trends
)


class TestDetectTrendDirection:
    """Test trend direction detection from score sequences."""
    
    def test_improving_trend(self):
        """Test detection of improving trend."""
        scores = [50.0, 55.0, 62.0]
        assert detect_trend_direction(scores) == "improving"
    
    def test_declining_trend(self):
        """Test detection of declining trend."""
        scores = [80.0, 72.0, 65.0]
        assert detect_trend_direction(scores) == "declining"
    
    def test_stable_trend(self):
        """Test detection of stable trend."""
        scores = [70.0, 72.0, 71.0]
        assert detect_trend_direction(scores) == "stable"
    
    def test_single_score(self):
        """Test with single score returns stable."""
        scores = [75.0]
        assert detect_trend_direction(scores) == "stable"
    
    def test_two_scores_improving(self):
        """Test with two scores showing improvement."""
        scores = [60.0, 70.0]
        assert detect_trend_direction(scores) == "improving"
    
    def test_two_scores_declining(self):
        """Test with two scores showing decline."""
        scores = [80.0, 65.0]
        assert detect_trend_direction(scores) == "declining"
    
    def test_threshold_boundary_improving(self):
        """Test exactly at improving threshold."""
        scores = [50.0, 55.0]  # +5 points
        assert detect_trend_direction(scores) == "improving"
    
    def test_threshold_boundary_declining(self):
        """Test exactly at declining threshold."""
        scores = [70.0, 65.0]  # -5 points
        assert detect_trend_direction(scores) == "declining"
    
    def test_below_threshold(self):
        """Test change below threshold is stable."""
        scores = [70.0, 73.0]  # +3 points
        assert detect_trend_direction(scores) == "stable"


class TestComputeTrendAdjustment:
    """Test trend adjustment penalty calculation."""
    
    def test_no_penalty_for_improving(self):
        """No penalty for improving trends."""
        trend_data = {
            'score_change': 10.0,
            'trend_direction': 'improving'
        }
        assert compute_trend_adjustment(trend_data) == 0.0
    
    def test_no_penalty_for_stable(self):
        """No penalty for stable trends."""
        trend_data = {
            'score_change': 2.0,
            'trend_direction': 'stable'
        }
        assert compute_trend_adjustment(trend_data) == 0.0
    
    def test_severe_decline_penalty(self):
        """Severe decline gets maximum penalty."""
        trend_data = {
            'score_change': -25.0,
            'trend_direction': 'declining'
        }
        assert compute_trend_adjustment(trend_data) == 15.0
    
    def test_significant_decline_penalty(self):
        """Significant decline gets moderate penalty."""
        trend_data = {
            'score_change': -15.0,
            'trend_direction': 'declining'
        }
        assert compute_trend_adjustment(trend_data) == 10.0
    
    def test_moderate_decline_penalty(self):
        """Moderate decline gets small penalty."""
        trend_data = {
            'score_change': -7.0,
            'trend_direction': 'declining'
        }
        assert compute_trend_adjustment(trend_data) == 5.0
    
    def test_minor_decline_no_penalty(self):
        """Minor decline gets no penalty."""
        trend_data = {
            'score_change': -3.0,
            'trend_direction': 'declining'
        }
        assert compute_trend_adjustment(trend_data) == 0.0
    
    def test_boundary_at_20(self):
        """Test boundary at -20 points."""
        trend_data = {
            'score_change': -20.0,
            'trend_direction': 'declining'
        }
        assert compute_trend_adjustment(trend_data) == 15.0
    
    def test_boundary_at_10(self):
        """Test boundary at -10 points."""
        trend_data = {
            'score_change': -10.0,
            'trend_direction': 'declining'
        }
        assert compute_trend_adjustment(trend_data) == 10.0


class TestComputeTrends:
    """Test full trend computation with database."""
    
    def setup_method(self):
        """Create in-memory database for testing."""
        self.conn = sqlite3.connect(':memory:')
        cursor = self.conn.cursor()
        
        # Create tables
        cursor.execute("""
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                repo TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE file_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                language TEXT,
                doc_drift INTEGER,
                test_drift INTEGER,
                complexity INTEGER,
                naming INTEGER,
                health_score REAL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        """)
        
        self.conn.commit()
    
    def teardown_method(self):
        """Close database connection."""
        self.conn.close()
    
    def test_no_data(self):
        """Test with no historical data."""
        result = compute_trends('app/test.py', self.conn)
        
        assert result['growth_rate'] == 0.0
        assert result['last_n_scores'] == []
        assert result['trend_direction'] == 'stable'
        assert result['score_change'] == 0.0
        assert result['volatility'] == 0.0
    
    def test_single_data_point(self):
        """Test with single data point."""
        cursor = self.conn.cursor()
        
        # Insert run and score
        cursor.execute(
            "INSERT INTO runs (run_id, timestamp, repo) VALUES (?, ?, ?)",
            ('run1', '2026-01-01T00:00:00Z', 'test')
        )
        cursor.execute(
            "INSERT INTO file_scores (run_id, file_path, health_score) VALUES (?, ?, ?)",
            ('run1', 'app/test.py', 75.0)
        )
        self.conn.commit()
        
        result = compute_trends('app/test.py', self.conn)
        
        assert result['growth_rate'] == 0.0
        assert result['last_n_scores'] == [75.0]
        assert result['trend_direction'] == 'stable'
        assert result['score_change'] == 0.0
        assert result['volatility'] == 0.0
    
    def test_improving_trend_data(self):
        """Test with improving trend data."""
        cursor = self.conn.cursor()
        
        # Insert runs and scores showing improvement
        scores = [60.0, 65.0, 72.0, 78.0]
        for i, score in enumerate(scores):
            run_id = f'run{i+1}'
            timestamp = f'2026-01-0{i+1}T00:00:00Z'
            
            cursor.execute(
                "INSERT INTO runs (run_id, timestamp, repo) VALUES (?, ?, ?)",
                (run_id, timestamp, 'test')
            )
            cursor.execute(
                "INSERT INTO file_scores (run_id, file_path, health_score) VALUES (?, ?, ?)",
                (run_id, 'app/test.py', score)
            )
        
        self.conn.commit()
        
        result = compute_trends('app/test.py', self.conn)
        
        assert result['growth_rate'] > 0  # Positive growth
        assert len(result['last_n_scores']) == 4
        assert result['trend_direction'] == 'improving'
        assert result['score_change'] == 18.0  # 78 - 60
        assert result['volatility'] > 0
    
    def test_declining_trend_data(self):
        """Test with declining trend data."""
        cursor = self.conn.cursor()
        
        # Insert runs and scores showing decline
        scores = [85.0, 78.0, 70.0, 62.0]
        for i, score in enumerate(scores):
            run_id = f'run{i+1}'
            timestamp = f'2026-01-0{i+1}T00:00:00Z'
            
            cursor.execute(
                "INSERT INTO runs (run_id, timestamp, repo) VALUES (?, ?, ?)",
                (run_id, timestamp, 'test')
            )
            cursor.execute(
                "INSERT INTO file_scores (run_id, file_path, health_score) VALUES (?, ?, ?)",
                (run_id, 'app/test.py', score)
            )
        
        self.conn.commit()
        
        result = compute_trends('app/test.py', self.conn)
        
        assert result['growth_rate'] < 0  # Negative growth
        assert len(result['last_n_scores']) == 4
        assert result['trend_direction'] == 'declining'
        assert result['score_change'] == -23.0  # 62 - 85
        assert result['volatility'] > 0
    
    def test_last_n_scores_limit(self):
        """Test that last_n_scores respects the limit."""
        cursor = self.conn.cursor()
        
        # Insert 10 data points
        for i in range(10):
            run_id = f'run{i+1}'
            timestamp = f'2026-01-{i+1:02d}T00:00:00Z'
            score = 70.0 + i
            
            cursor.execute(
                "INSERT INTO runs (run_id, timestamp, repo) VALUES (?, ?, ?)",
                (run_id, timestamp, 'test')
            )
            cursor.execute(
                "INSERT INTO file_scores (run_id, file_path, health_score) VALUES (?, ?, ?)",
                (run_id, 'app/test.py', score)
            )
        
        self.conn.commit()
        
        result = compute_trends('app/test.py', self.conn, n=6)
        
        # Should only return last 6 scores
        assert len(result['last_n_scores']) == 6
        assert result['last_n_scores'][0] == 74.0  # 70 + 4
        assert result['last_n_scores'][-1] == 79.0  # 70 + 9


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


# Made with Bob