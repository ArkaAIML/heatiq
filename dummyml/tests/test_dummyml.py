from backend.thermalengine.schemas import ThermalOutput
from dummyml import dummy_prediction_and_recommendation, dummy_prediction_and_recommendation_batch


def test_dummy_ml_ignores_thermal_values_and_returns_dummy_status():
    """
    Test that a valid ThermalOutput can be accepted,
    and a completely different ThermalOutput produces the same dummy prediction/recommendation content.
    No thermal calculations occur.
    """
    # First input
    output_1 = ThermalOutput(
        area_id="WARD_1",
        timestamp="2026-05-20T14:00:00Z",
        heat_index_c=10.0,
        utci_c=10.0,
        wbgt_c=10.0,
        htsi=10.0,
        htsi_category="LOW"
    )

    # Second input with completely different thermal values
    output_2 = ThermalOutput(
        area_id="WARD_1",
        timestamp="2026-05-20T14:00:00Z",
        heat_index_c=95.0,
        utci_c=95.0,
        wbgt_c=95.0,
        htsi=95.0,
        htsi_category="EXTREME"
    )

    res_1 = dummy_prediction_and_recommendation(output_1)
    res_2 = dummy_prediction_and_recommendation(output_2)

    # Prediction and recommendation output is identical except it maps to the same area_id
    assert res_1.prediction.status == "DUMMY"
    assert res_1.recommendation.status == "DUMMY"
    assert res_1.prediction.message == "Prediction engine is currently staring at the weather and doing absolutely nothing."
    assert res_1.recommendation.message == "Recommendation engine unavailable. Please consult the nearest sensible human."

    assert res_1.prediction.to_dict() == res_2.prediction.to_dict()
    assert res_1.recommendation.to_dict() == res_2.recommendation.to_dict()


def test_dummy_ml_batch():
    """
    Test that the batch interface preserves ward identity (area_id) and input order.
    """
    output_1 = ThermalOutput(
        area_id="WARD_1",
        timestamp="2026-05-20T14:00:00Z",
        heat_index_c=10.0,
        utci_c=10.0,
        wbgt_c=10.0,
        htsi=10.0,
        htsi_category="LOW"
    )

    output_2 = ThermalOutput(
        area_id="WARD_2",
        timestamp="2026-05-20T14:00:00Z",
        heat_index_c=95.0,
        utci_c=95.0,
        wbgt_c=95.0,
        htsi=95.0,
        htsi_category="EXTREME"
    )

    results = dummy_prediction_and_recommendation_batch([output_1, output_2])

    assert len(results) == 2
    assert results[0].prediction.area_id == "WARD_1"
    assert results[1].prediction.area_id == "WARD_2"
    
    assert results[0].prediction.status == "DUMMY"
    assert results[1].recommendation.status == "DUMMY"
