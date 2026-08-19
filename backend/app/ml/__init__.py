"""Machine learning that runs in production.

Training scripts live in `ml/`; anything the API needs at request time lives
here, so that the features computed during training and the features computed
during serving come from the same code. Two copies of a feature definition
drift, and the drift is silent -- the model keeps returning confident answers
about vectors that no longer mean what it was trained on.
"""
