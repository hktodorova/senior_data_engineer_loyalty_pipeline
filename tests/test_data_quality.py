import pandas as pd


def test_duplicate_detection():
    df = pd.DataFrame({
        "order_id": [1, 1, 2]
    })

    duplicates = df["order_id"].duplicated(keep=False).sum()

    assert duplicates == 2