# Contributing

Start with a synthetic example and an expected invariant. Explain how a proposed
change handles splits, merges, fees, incorrect claims and innocent recipients.
Never add real victims' private data, credentials, seed phrases or unverified
accusations to test fixtures.

Before submitting a change:

```bash
python -m unittest discover -s tests -v
python tools/build_demo.py
python tools/build_demo.py --check
```

Keep the runtime dependency-free. Document breaking schema changes. Tests should
check accounting and boundary behaviour rather than simply repeat code paths.
For any feature claiming to connect to a real chain, distinguish observation,
attribution and protocol enforcement explicitly.
