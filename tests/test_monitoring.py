import numpy as np
import pandas as pd

from world_cup_intelligence.monitoring import population_stability_index


def test_population_stability_index_is_zero_for_same_sample():
    sample = pd.Series(np.arange(100))
    assert np.isclose(population_stability_index(sample, sample), 0)
