import pandas as pd


def test_net_collected_amount():
    df = pd.DataFrame({
        "total_cash_collected_amount": [100],
        "total_refund_amount": [20],
    })

    df["net_collected_amount"] = (
        df["total_cash_collected_amount"]
        - df["total_refund_amount"]
    )

    assert df["net_collected_amount"].iloc[0] == 80