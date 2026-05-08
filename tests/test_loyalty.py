import pandas as pd


def test_points_balance():
    df = pd.DataFrame({
        "card_id": ["A", "A"],
        "points_delta": [100, -20],
    })

    balance = df.groupby("card_id")["points_delta"].sum()

    assert balance.iloc[0] == 80