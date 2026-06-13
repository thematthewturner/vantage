"""The vantage web terminal: a thin Streamlit dashboard over the package.

Like the notebooks, this is a *driver* -- all the real logic lives in
``vantage.storage`` / ``vantage.index`` / ``vantage.transforms``. The dashboard
only queries the store (read-only) and draws charts.

Run it with::

    streamlit run src/vantage/app/dashboard.py

or ``make dash``.
"""
