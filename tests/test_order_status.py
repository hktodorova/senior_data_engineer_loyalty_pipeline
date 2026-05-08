import pandas as pd


def test_is_fully_paid():
    df = pd.DataFrame({
        "net_collected_amount": [100],
        "order_expected_amount": [100],
    })

    result = (
        df["net_collected_amount"]
        >= df["order_expected_amount"]
    )

    assert result.iloc[0] == True