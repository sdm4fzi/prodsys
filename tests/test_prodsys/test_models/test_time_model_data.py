"""
Tests for time_model_data module.
"""

import pytest
from prodsys.models.time_model_data import (
    FunctionTimeModelData,
    SampleTimeModelData,
    ScheduledTimeModelData,
    DistanceTimeModelData,
    TimeModelEnum,
)
from prodsys.util.statistical_functions import FunctionTimeModelEnum


class TestFunctionTimeModelData:
    """Tests for FunctionTimeModelData."""

    def test_creation_with_required_fields(self):
        """Test creating FunctionTimeModelData with required fields."""
        time_model = FunctionTimeModelData(
            ID="tm1",
            description="Test time model",
            distribution_function=FunctionTimeModelEnum.Normal,
            location=20.0,
            scale=5.0,
        )
        assert time_model.ID == "tm1"
        assert time_model.description == "Test time model"
        assert time_model.distribution_function == FunctionTimeModelEnum.Normal
        assert time_model.location == 20.0
        assert time_model.scale == 5.0
        assert time_model.batch_size == 100  # default value

    def test_hash(self):
        """Test hash method returns consistent values."""
        time_model1 = FunctionTimeModelData(
            ID="tm1",
            description="Test time model",
            distribution_function=FunctionTimeModelEnum.Normal,
            location=20.0,
            scale=5.0,
        )
        time_model2 = FunctionTimeModelData(
            ID="tm2",
            description="Different description",
            distribution_function=FunctionTimeModelEnum.Normal,
            location=20.0,
            scale=5.0,
        )
        time_model3 = FunctionTimeModelData(
            ID="tm3",
            description="Test time model",
            distribution_function=FunctionTimeModelEnum.Normal,
            location=20.0,
            scale=6.0,  # different scale
        )
        
        # Same parameters should produce same hash (ignoring ID/description)
        assert time_model1.hash() == time_model2.hash()
        # Different parameters should produce different hash
        assert time_model1.hash() != time_model3.hash()

    def test_different_distribution_functions(self):
        """Test creating time models with different distribution functions."""
        distributions = [
            FunctionTimeModelEnum.Normal,
            FunctionTimeModelEnum.Exponential,
            FunctionTimeModelEnum.Lognormal,
            FunctionTimeModelEnum.Constant,
        ]
        
        for dist in distributions:
            time_model = FunctionTimeModelData(
                ID=f"tm_{dist.value}",
                description=f"Test {dist.value}",
                distribution_function=dist,
                location=10.0,
                scale=2.0,
            )
            assert time_model.distribution_function == dist


class TestSampleTimeModelData:
    """Tests for SampleTimeModelData."""

    def test_creation_with_samples(self):
        """Test creating SampleTimeModelData with samples."""
        samples = [25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0]
        time_model = SampleTimeModelData(
            ID="sample_tm1",
            description="Sample time model",
            samples=samples,
        )
        assert time_model.ID == "sample_tm1"
        assert time_model.description == "Sample time model"
        assert time_model.samples == samples

    def test_hash(self):
        """Test hash method considers samples."""
        samples1 = [25.0, 13.0, 15.0, 16.0]
        samples2 = [25.0, 13.0, 15.0, 16.0]
        samples3 = [25.0, 13.0, 15.0, 17.0]  # different last value
        
        time_model1 = SampleTimeModelData(
            ID="tm1",
            description="Test 1",
            samples=samples1,
        )
        time_model2 = SampleTimeModelData(
            ID="tm2",
            description="Test 2",
            samples=samples2,
        )
        time_model3 = SampleTimeModelData(
            ID="tm3",
            description="Test 3",
            samples=samples3,
        )
        
        # Same samples should produce same hash
        assert time_model1.hash() == time_model2.hash()
        # Different samples should produce different hash
        assert time_model1.hash() != time_model3.hash()

    def test_empty_samples(self):
        """Test creating SampleTimeModelData with empty samples."""
        time_model = SampleTimeModelData(
            ID="empty_tm",
            description="Empty samples",
            samples=[],
        )
        assert time_model.samples == []
        assert time_model.hash() is not None


class TestScheduledTimeModelData:
    """Tests for ScheduledTimeModelData."""

    def test_creation_with_schedule(self):
        """Test creating ScheduledTimeModelData with schedule."""
        schedule = [3.0, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0]
        time_model = ScheduledTimeModelData(
            ID="scheduled_tm1",
            description="Scheduled time model",
            schedule=schedule,
            absolute=True,
            cyclic=False,
        )
        assert time_model.ID == "scheduled_tm1"
        assert time_model.description == "Scheduled time model"
        assert time_model.schedule == schedule
        assert time_model.absolute is True
        assert time_model.cyclic is False

    def test_default_cyclic(self):
        """Test that cyclic defaults to False."""
        time_model = ScheduledTimeModelData(
            ID="scheduled_tm1",
            description="Scheduled time model",
            schedule=[3.0, 5.0],
            absolute=True,
        )
        assert time_model.cyclic is False

    def test_hash(self):
        """Test hash method considers schedule and flags."""
        schedule = [3.0, 5.0, 7.0]
        
        time_model1 = ScheduledTimeModelData(
            ID="tm1",
            description="Test 1",
            schedule=schedule,
            absolute=True,
            cyclic=False,
        )
        time_model2 = ScheduledTimeModelData(
            ID="tm2",
            description="Test 2",
            schedule=schedule,
            absolute=True,
            cyclic=False,
        )
        time_model3 = ScheduledTimeModelData(
            ID="tm3",
            description="Test 3",
            schedule=schedule,
            absolute=False,  # different absolute
            cyclic=False,
        )
        time_model4 = ScheduledTimeModelData(
            ID="tm4",
            description="Test 4",
            schedule=schedule,
            absolute=True,
            cyclic=True,  # different cyclic
        )
        
        # Same parameters should produce same hash
        assert time_model1.hash() == time_model2.hash()
        # Different parameters should produce different hash
        assert time_model1.hash() != time_model3.hash()
        assert time_model1.hash() != time_model4.hash()


class TestDistanceTimeModelData:
    """Tests for DistanceTimeModelData."""

    def test_creation_with_speed_and_reaction_time(self):
        """Test creating DistanceTimeModelData with speed and reaction time."""
        time_model = DistanceTimeModelData(
            ID="distance_tm1",
            description="Distance time model",
            speed=180.0,
            reaction_time=0.15,
            metric="manhattan",
        )
        assert time_model.ID == "distance_tm1"
        assert time_model.description == "Distance time model"
        assert time_model.speed == 180.0
        assert time_model.reaction_time == 0.15
        assert time_model.metric == "manhattan"

    def test_default_metric(self):
        """Test that metric defaults to manhattan."""
        time_model = DistanceTimeModelData(
            ID="distance_tm1",
            description="Distance time model",
            speed=180.0,
            reaction_time=0.15,
        )
        assert time_model.metric == "manhattan"

    def test_euclidean_metric(self):
        """Test creating with euclidean metric."""
        time_model = DistanceTimeModelData(
            ID="distance_tm1",
            description="Distance time model",
            speed=180.0,
            reaction_time=0.15,
            metric="euclidean",
        )
        assert time_model.metric == "euclidean"

    def test_hash(self):
        """Test hash method considers speed, reaction_time, and metric."""
        time_model1 = DistanceTimeModelData(
            ID="tm1",
            description="Test 1",
            speed=180.0,
            reaction_time=0.15,
            metric="manhattan",
        )
        time_model2 = DistanceTimeModelData(
            ID="tm2",
            description="Test 2",
            speed=180.0,
            reaction_time=0.15,
            metric="manhattan",
        )
        time_model3 = DistanceTimeModelData(
            ID="tm3",
            description="Test 3",
            speed=190.0,  # different speed
            reaction_time=0.15,
            metric="manhattan",
        )
        time_model4 = DistanceTimeModelData(
            ID="tm4",
            description="Test 4",
            speed=180.0,
            reaction_time=0.15,
            metric="euclidean",  # different metric
        )
        
        # Same parameters should produce same hash
        assert time_model1.hash() == time_model2.hash()
        # Different parameters should produce different hash
        assert time_model1.hash() != time_model3.hash()
        assert time_model1.hash() != time_model4.hash()

